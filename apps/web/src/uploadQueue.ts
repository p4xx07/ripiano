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

/** A random UUID (version 4). crypto.randomUUID needs a secure context; a NAS on plain http does not have one. */
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

/** Keep a file for a later retry. Returns false when the browser cannot store it (private mode, quota). */
export async function keep(owner: string, file: File, scanId: string = newScanId()): Promise<boolean> {
  try {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    await run("readwrite", (store) => store.put({ id, owner, name: file.name, type: file.type, blob: file, addedAt: Date.now(), scanId } satisfies PendingUpload));
    return true;
  } catch {
    return false;
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

/** Network failures (no answer, or the proxy says the server is down) are worth retrying; refusals are not. */
export function isRetryable(status: number) {
  return status === 0 || status === 502 || status === 503 || status === 504;
}

/** Only a refusal of the file itself removes it from the queue; anything else (signed out, throttled, server error) keeps it. */
export function isRefusal(status: number) {
  return status === 400 || status === 409 || status === 413 || status === 415;
}

/** Remove every waiting file of one person (when they sign out and choose to discard them). */
export async function forgetAll(owner: string): Promise<void> {
  for (const item of await pending(owner)) await forget(item.id);
}
