export type ThemePreference = "system" | "light" | "dark" | "amoled";

const key = "ripiano.theme";
const colors = { light: "#173b30", dark: "#14251b", amoled: "#000000" } as const;
const valid = new Set<ThemePreference>(["system", "light", "dark", "amoled"]);

export function readThemePreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(key) as ThemePreference | null;
    return stored && valid.has(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(preference: ThemePreference) {
  const resolved = preference === "system"
    ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : preference;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved === "light" ? "light" : "dark";
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", colors[resolved]);
  const manifest = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
  if (manifest) manifest.href = resolved === "light" ? "/manifest.webmanifest" : `/manifest-${resolved}.webmanifest`;
  window.RipianoAndroid?.postMessage(`theme:${resolved}`);
}

export function saveThemePreference(preference: ThemePreference) {
  try {
    localStorage.setItem(key, preference);
  } catch {
    // Private browsing or disabled storage still permits changing this session.
  }
  applyTheme(preference);
}
