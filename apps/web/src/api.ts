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

export type Rule = {
  id: string;
  tag_id: string;
  tag_name: string;
  pattern: string;
  field: "title" | "text" | "either";
  enabled: boolean;
};

export type FilingItem = { id: string; name: string };

export type LibraryFilters = {
  tag_id: string;
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
  correspondent_origin: "none" | "rule" | "manual" | "source";
  document_type_origin: "none" | "rule" | "manual" | "source";
  action_status: "none" | "open" | "done";
  action_due_date: string | null;
  action_note: string;
  action_completed_at: string | null;
  tags: {
    id: string;
    name: string;
    color: string;
    origin: "manual" | "rule" | "model" | "source";
  }[];
  physical_copies: PhysicalCopy[];
  snippet: string;
  snippet_source: "document" | "note" | "sticker" | "field" | null;
  email: { account: string; sender: string; subject: string; received_at: string | null } | null;
  asn: number | null;
  split_parent: { id: string; title: string } | null;
  is_split_source: boolean;
};

export type FilingSuggestion = {
  id: string;
  name: string;
  example: { id: string; title: string };
  shared_terms: string[];
  similarity: number;
};

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

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    credentials: "same-origin",
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(options.method && options.method !== "GET"
        ? { "X-CSRFToken": csrfToken() }
        : {}),
      ...options.headers,
    },
  });
  const result = await response.json();
  if (!response.ok)
    throw new ApiError(result.error ?? `Request failed (${response.status})`, response.status, result);
  return result as T;
}

export function formatDate(value: string) {
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T12:00:00`)
    : new Date(value);
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}
