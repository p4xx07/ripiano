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

export type Rule = {
  id: string;
  tag_id: string;
  tag_name: string;
  pattern: string;
  field: "title" | "text" | "either";
  enabled: boolean;
};

export type Location = {
  id: string;
  name: string;
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
  created_at: string;
};

export type Document = {
  id: string;
  title: string;
  original_name: string;
  duplicate_of: { id: string; title: string } | null;
  source: "web" | "telegram" | "android" | "folder";
  status: "pending" | "processing" | "ready" | "failed";
  archive_available: boolean;
  error: string;
  created_at: string;
  document_date: string | null;
  tags: {
    id: string;
    name: string;
    color: string;
    origin: "manual" | "rule" | "model";
  }[];
  physical_copies: PhysicalCopy[];
  snippet: string;
};

function csrfToken() {
  return decodeURIComponent(
    document.cookie
      .split("; ")
      .find((value) => value.startsWith("csrftoken="))
      ?.split("=")[1] ?? "",
  );
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
    throw new Error(result.error ?? `Request failed (${response.status})`);
  return result as T;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}
