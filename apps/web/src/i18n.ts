import { useSyncExternalStore } from "react";

/**
 * Interface languages. Each screen keeps its own messages next to it (see `locales/`), defined
 * with `defineMessages(en, it)`, so the Italian set must have exactly the same keys and argument
 * types as the English one. Components read them with `useMessages(messages)`.
 */
export type Language = "en" | "it";
export type LanguagePreference = "system" | Language;

type Message = string | ((...args: never[]) => string);
export type Messages<E extends Record<string, Message>> = { en: E; it: { [K in keyof E]: E[K] } };

const key = "ripiano.language";
const listeners = new Set<() => void>();

export function readLanguagePreference(): LanguagePreference {
  try {
    const stored = localStorage.getItem(key);
    return stored === "en" || stored === "it" || stored === "system" ? stored : "en";
  } catch {
    return "en";
  }
}

function resolve(preference: LanguagePreference): Language {
  if (preference !== "system") return preference;
  const wanted = typeof navigator === "undefined" ? [] : (navigator.languages?.length ? navigator.languages : [navigator.language]);
  for (const tag of wanted) {
    const base = tag?.toLowerCase().split("-")[0];
    if (base === "it" || base === "en") return base;
  }
  return "en";
}

let preference = readLanguagePreference();
let current = resolve(preference);

function apply() {
  if (typeof document !== "undefined") document.documentElement.lang = current;
}
apply();

export function language(): Language {
  return current;
}

/** The BCP 47 tag used for dates and numbers. */
export function locale(): string {
  if (current === "it") return "it-IT";
  // English keeps the device's English region (US or UK date order); otherwise British English.
  const device = typeof navigator === "undefined" ? "" : navigator.language ?? "";
  return device.toLowerCase().startsWith("en") ? device : "en-GB";
}

export function languagePreference(): LanguagePreference {
  return preference;
}

export function setLanguagePreference(next: LanguagePreference) {
  preference = next;
  try {
    localStorage.setItem(key, next);
  } catch {
    // Private browsing still changes the language for this session.
  }
  current = resolve(next);
  apply();
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useLanguage(): Language {
  return useSyncExternalStore(subscribe, language, language);
}

export function useLanguagePreference(): LanguagePreference {
  return useSyncExternalStore(subscribe, languagePreference, languagePreference);
}

export function defineMessages<E extends Record<string, Message>>(en: E, it: { [K in keyof E]: E[K] }): Messages<E> {
  return { en, it };
}

export function useMessages<E extends Record<string, Message>>(messages: Messages<E>): E {
  return messages[useLanguage()] as E;
}

/** For code outside components (for example request helpers). */
export function messagesFor<E extends Record<string, Message>>(messages: Messages<E>): E {
  return messages[current] as E;
}
