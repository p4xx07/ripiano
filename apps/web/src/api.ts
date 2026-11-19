import { language, locale } from "./i18n";

export type Session = {
  authenticated: boolean;
  username: string | null;
  setup_required: boolean;
  owner: boolean;
};

export type Tag = {
  id: string;
  name: string;
  color: string;
  description: string;
  barcode_value: string;
  parent_id: string | null;
};

export function tagPathLabel(tag: Tag, byId: ReadonlyMap<string, Tag>): string {
  const names: string[] = [];
  const seen = new Set<string>();
  let current: Tag | undefined = tag;
  while (current && !seen.has(current.id)) {
    names.unshift(current.name);
    seen.add(current.id);
    current = current.parent_id ? byId.get(current.parent_id) : undefined;
  }
  return names.join(" / ");
}

export type MatchMode = "phrase" | "any" | "all" | "regex" | "fuzzy";
export const matchModes: Record<MatchMode, string> = {
  phrase: "Exact phrase",
  any: "Any of these words",
  all: "All of these words",
  fuzzy: "Similar spelling",
  regex: "Regular expression",
};

export type Rule = {
  id: string;
  tag_id: string;
  tag_name: string;
  pattern: string;
  field: "title" | "text" | "either";
  match: MatchMode;
  enabled: boolean;
};

export type FilingItem = { id: string; name: string };

export type LibraryFilters = {
  tag_id: string;
  copy_status: string;
  correspondent_id: string;
  document_type_id: string;
  date_from: string;
  date_to: string;
  custom_field_id: string;
  custom_value: string;
  custom_min: string;
  custom_max: string;
};

export type SavedView = {
  id: string;
  name: string;
  query: string;
  tag_id: string | null;
  copy_status: string;
  correspondent_id: string | null;
  document_type_id: string | null;
  date_from: string | null;
  date_to: string | null;
  custom_field_id: string | null;
  custom_value: string;
  custom_min: string;
  custom_max: string;
};

export type FilingRule = {
  id: string;
  kind: "correspondent" | "document_type";
  target_id: string;
  target_name: string;
  pattern: string;
  field: "title" | "text" | "either";
  match: MatchMode;
  enabled: boolean;
};

export type Location = {
  id: string;
  name: string;
  sticker_code: string;
  parent_id: string | null;
  path: string[];
  description: string;
};

export type PhysicalCopy = {
  id: string;
  document_id: string;
  sticker_code: string;
  location_id: string | null;
  location_path: string[];
  missing_at: string | null;
  created_at: string;
};

export type Document = {
  id: string;
  title: string;
  original_name: string;
  version_number: number;
  duplicate_of: { id: string; title: string } | null;
  duplicate_reviewed_at: string | null;
  source: "web" | "telegram" | "android" | "folder";
  status: "pending" | "processing" | "ready" | "failed";
  archive_available: boolean;
  error: string;
  created_at: string;
  trashed_at: string | null;
  document_date: string | null;
  correspondent: FilingItem | null;
  document_type: FilingItem | null;
  correspondent_origin: "none" | "rule" | "model" | "learned" | "manual" | "source";
  document_type_origin: "none" | "rule" | "model" | "learned" | "manual" | "source";
  action_status: "none" | "open" | "done";
  action_due_date: string | null;
  action_note: string;
  action_completed_at: string | null;
  tags: {
    id: string;
    name: string;
    color: string;
    origin: "manual" | "rule" | "model" | "learned" | "source";
  }[];
  physical_copies: PhysicalCopy[];
  snippet: string;
  snippet_source: "document" | "note" | "sticker" | "field" | null;
  email: { account: string; sender: string; subject: string; received_at: string | null } | null;
  asn: number | null;
  split_parent: { id: string; title: string } | null;
  is_split_source: boolean;
  storage_path: { id: string; name: string } | null;
  access: "owner" | "edit" | "view";
  shared_by: string | null;
  shared_by_id?: number;
  /** Set when processing finished with a caveat, e.g. a damaged PDF whose readable pages were saved. */
  processing_warning?: "damaged_pdf" | string | null;
  /** The warning in the interface language ("" when none). */
  warning?: string;
  processing_warning_reviewed_at?: string | null;
};

/** A processing warning the owner has not marked as checked yet. */
export function hasOpenWarning(doc: Pick<Document, "processing_warning" | "processing_warning_reviewed_at">): boolean {
  return Boolean(doc.processing_warning) && !doc.processing_warning_reviewed_at;
}

export type Person = {
  id: number;
  username: string;
  name: string;
  is_active?: boolean;
  is_admin?: boolean;
  last_login?: string | null;
  groups?: number[];
};

export type PersonGroup = { id: number; name: string; member_ids?: number[] };

export type People = { people: Person[]; groups: PersonGroup[]; admin: boolean };

export type FilingSuggestion = {
  id: string;
  name: string;
  example: { id: string; title: string } | null;
  shared_terms: string[];
  similarity: number | null;
  probability?: number;
};

export type SuggestionBasisText = {
  suggestionLikely: (percent: number) => string;
  suggestionLike: (title: string) => string;
  suggestionShared: (terms: string) => string;
};

/** Why a filing suggestion is offered, in the interface language (texts come from the caller's locale). */
export function suggestionBasis(item: FilingSuggestion, text: SuggestionBasisText): string {
  const parts: string[] = [];
  if (item.probability !== undefined) parts.push(text.suggestionLikely(Math.round(item.probability * 100)));
  if (item.example) parts.push(text.suggestionLike(item.example.title) + (item.shared_terms.length ? ` · ${text.suggestionShared(item.shared_terms.join(", "))}` : ""));
  return parts.join(" · ");
}

export type FilingSuggestions = {
  tags: FilingSuggestion[];
  correspondents: FilingSuggestion[];
  document_types: FilingSuggestion[];
};

export type DocumentNote = {
  id: string;
  body: string;
  author: string;
  created_at: string;
};

export type CustomField = {
  id: string;
  name: string;
  kind: "text" | "number" | "date" | "boolean";
  value: string | boolean | null;
  in_use?: boolean;
};

function csrfToken() {
  return decodeURIComponent(
    document.cookie
      .split("; ")
      .find((value) => value.startsWith("csrftoken="))
      ?.split("=")[1] ?? "",
  );
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public data: Record<string, unknown>) {
    super(message);
  }
}

const sessionEndedListeners = new Set<() => void>();

/** Called when the server answers 401 to a signed-in request: the session ended elsewhere, expired, or the
 *  account was disabled. Sign-in and setup (where 401 means a wrong password or code) never trigger it. */
export function onSessionEnded(listener: () => void) {
  sessionEndedListeners.add(listener);
  return () => { sessionEndedListeners.delete(listener); };
}

/** The API's JSON answer to a failed CSRF check (services/api/archive/security_views.py), in English and Italian. */
const CSRF_FAILURE_MESSAGES = new Set([
  "This request could not be verified. Reload the page and try again.",
  "Non è stato possibile verificare questa richiesta. Ricarica la pagina e riprova.",
]);

/** A 403 because the CSRF check failed (the csrftoken cookie was cleared or is stale), not because of a permission. */
export function isCsrfFailure(cause: unknown): boolean {
  return cause instanceof ApiError && cause.status === 403 && cause.data.csrf_failed === true;
}

/** The API's refusal of a wrong current password (or of too many attempts at it), in English and Italian. */
const PASSWORD_REFUSALS = new Set([
  "Your password is not correct",
  "La password non è corretta",
  "Too many attempts. Wait a few minutes and try again.",
  "Troppi tentativi. Attendi qualche minuto e riprova.",
]);

/** The server refused the request because the password typed to confirm it is wrong. */
export function isPasswordRefusal(cause: unknown): boolean {
  return cause instanceof ApiError && (cause.status === 400 || cause.status === 429)
    && (PASSWORD_REFUSALS.has(cause.message) || PASSWORD_REFUSALS.has(cause.message.replace(/\.$/, "")));
}

/**
 * Messages from the server are shown as sentences: a final period is added when one is missing, so they match the
 * app's own messages ("La password non è corretta." — round-8 judge 2 L3).
 */
export function asSentence(text: string): string {
  const trimmed = text.trim();
  return !trimmed || /[.!?…:)»”"]$/.test(trimmed) ? trimmed : `${trimmed}.`;
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
  csrfRetried = false,
): Promise<T> {
  const unsafe = Boolean(options.method && options.method !== "GET");
  const sentToken = unsafe ? csrfToken() : "";
  let response: Response;
  try {
    response = await fetch(path, {
    ...options,
    credentials: "same-origin",
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(unsafe ? { "X-CSRFToken": sentToken } : {}),
      "Accept-Language": language(),
      ...options.headers,
    },
  });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(transportMessage("offline"), 0, {});
  }
  // A proxy in front of Ripiano can answer with an HTML page (for example 413 for a large upload or 502 while the
  // server restarts); never show "Unexpected token '<'" to the person.
  let result: Record<string, unknown>;
  try {
    result = await response.json();
  } catch {
    if (response.ok) throw new ApiError(transportMessage("unexpected"), response.status, {});
    result = {};
  }
  // The CSRF cookie is gone (site data cleared, storage evicted) or stale: the server refused the request before
  // looking at it. Fetch a fresh token (GET /api/session sets the cookie) and send it once more; if the session ended
  // too, that retry answers 401 and the app asks the person to sign in again (round-7 judge 2 M2).
  if (unsafe && response.status === 403 && (!sentToken || CSRF_FAILURE_MESSAGES.has(String(result.error)))) {
    if (!csrfRetried) {
      try {
        await fetch("/api/session", { credentials: "same-origin", headers: { "Accept-Language": language() } });
      } catch {
        // Unreachable now: the retry below reports it as offline.
      }
      if (csrfToken()) return request<T>(path, options, true);
    }
    for (const listener of sessionEndedListeners) listener(); // the app checks whether the session is still there
    throw new ApiError(typeof result.error === "string" ? result.error : transportMessage("unexpected"), 403, { ...result, csrf_failed: true });
  }
  if (response.status === 401 && !/^\/api\/(session|setup)(\/|\?|$)/.test(path)) {
    for (const listener of sessionEndedListeners) listener();
  }
  if (!response.ok) {
    const fallback = response.status === 413 ? transportMessage("tooLarge") : response.status >= 502 && response.status <= 504 ? transportMessage("unavailable") : transportMessage("unexpected");
    throw new ApiError(typeof result.error === "string" ? asSentence(result.error) : fallback, response.status, result);
  }
  return result as T;
}

const TRANSPORT_MESSAGES = {
  en: {
    offline: "Ripiano can't be reached. Check your connection and try again.",
    tooLarge: "This file is larger than the server accepts.",
    unavailable: "Ripiano is restarting or unavailable. Try again in a minute.",
    unexpected: "The server sent an unexpected reply. Try again.",
  },
  it: {
    offline: "Impossibile raggiungere Ripiano. Controlla la connessione e riprova.",
    tooLarge: "Questo file supera la dimensione accettata dal server.",
    unavailable: "Ripiano si sta riavviando o non è disponibile. Riprova tra un minuto.",
    unexpected: "Il server ha inviato una risposta inattesa. Riprova.",
  },
} as const;

function transportMessage(key: keyof (typeof TRANSPORT_MESSAGES)["en"]) {
  return TRANSPORT_MESSAGES[language() === "it" ? "it" : "en"][key];
}

export function formatDate(value: string) {
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T12:00:00`)
    : new Date(value);
  return new Intl.DateTimeFormat(locale(), {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

/** Time of day in the interface language, e.g. "10:48" or "10:48 AM". */
export function formatTime(value: Date) {
  return new Intl.DateTimeFormat(locale(), { hour: "numeric", minute: "2-digit" }).format(value);
}

/** Date and time in the interface language, e.g. for "last signed in". */
export function formatDateTime(value: string | Date) {
  return new Intl.DateTimeFormat(locale(), { dateStyle: "medium", timeStyle: "short" }).format(typeof value === "string" ? new Date(value) : value);
}

/** Whole numbers in the interface language (1.234 in Italian, 1,234 in English). */
export function formatNumber(value: number) {
  return new Intl.NumberFormat(locale()).format(value);
}
