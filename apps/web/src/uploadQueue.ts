/**
 * Uploads that could not reach Ripiano (offline, server restarting) wait here, in this browser's IndexedDB, and are
 * sent again when the connection returns. Each file keeps the scan ID of its first attempt, so a file the server already
 * received (the answer was lost) is recognised on retry instead of being stored twice. Entries belong to one signed-in person and are only sent while that
 * person is signed in; signing out asks whether to keep or discard them.
 */

const DB_NAME = "ripiano-uploads";
const STORE = "pending";

/** `scanId` is sent as X-Ripiano-Scan-ID so a retry of a file the server already received is recognised, not added twice.
 *  Entries saved before it existed have none and get one when they are sent. */
export type PendingUpload = { id: string; owner: string; name: string; type: string; blob: Blob; addedAt: number; scanId?: string };

/** A random UUID (version 4). crypto.randomUUID needs a secure context; a server on plain http does not have one. */
export function newScanId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error("blocked"));
  });
}

async function run<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  try {
    return await new Promise<T>((resolve, reject) => {
      const transaction = db.transaction(STORE, mode);
      const request = action(transaction.objectStore(STORE));
      transaction.oncomplete = () => resolve(request.result);
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally {
    db.close();
  }
}

/** An ID for a queue entry. The caller can make it first, to mark the entry as "being sent" before it exists. */
export function newEntryId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** How long storing a file may take before the upload goes ahead without it. A browser whose storage never answers
 *  (blocked, broken profile) must not stop the upload from starting. */
const KEEP_TIME_LIMIT = 3000;

/** Keep a file on this device: before it is sent (so a reload or a closed tab mid-request does not lose it) and for
 *  a later retry. Returns the entry's ID, or null when the browser cannot store it (private mode, quota, no answer
 *  in time). A store that finishes after the time limit leaves an entry that is sent later with the same scan ID,
 *  which the server recognises. */
export async function keep(owner: string, file: File, scanId: string = newScanId(), id: string = newEntryId()): Promise<string | null> {
  let timer = 0;
  const stored = run("readwrite", (store) => store.put({ id, owner, name: file.name, type: file.type, blob: file, addedAt: Date.now(), scanId } satisfies PendingUpload))
    .then(() => id, () => null);
  const gaveUp = new Promise<null>((resolve) => { timer = window.setTimeout(() => resolve(null), KEEP_TIME_LIMIT); });
  try {
    return await Promise.race([stored, gaveUp]);
  } finally {
    window.clearTimeout(timer);
  }
}

export async function pending(owner: string): Promise<PendingUpload[]> {
  try {
    const all = await run<PendingUpload[]>("readonly", (store) => store.getAll());
    return all.filter((item) => item.owner === owner).sort((a, b) => a.addedAt - b.addedAt);
  } catch {
    return [];
  }
}

export async function forget(id: string): Promise<void> {
  try {
    await run("readwrite", (store) => store.delete(id));
  } catch {
    // Nothing to do: the entry is retried later and recognised as a duplicate by the server.
  }
}

/** Network failures, a temporarily unavailable server, an ended session, and a failed CSRF check (the cookie was
 *  cleared; signing in again or reloading gives a fresh one) keep the file for its owner. Any other 403 is a refusal. */
export function isRetryable(status: number, csrfFailed = false) {
  return status === 0 || status === 401 || status === 502 || status === 503 || status === 504 || (status === 403 && csrfFailed);
}

/** Only a refusal of the file itself removes it from the queue; anything else (signed out, throttled, server error) keeps it. */
export function isRefusal(status: number) {
  return status === 400 || status === 409 || status === 413 || status === 415;
}

/** Remove every waiting file of one person (when they sign out and choose to discard them). */
export async function forgetAll(owner: string): Promise<void> {
  for (const item of await pending(owner)) await forget(item.id);
}
