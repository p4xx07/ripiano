// Runs before the app (render-blocking, no inline script so the page can use a strict Content-Security-Policy).
let preference, language;
try { preference = localStorage.getItem("ripiano.theme"); language = localStorage.getItem("ripiano.language"); } catch {}
// The page language before the app loads matches the interface language (see src/i18n.ts).
if (language !== "en" && language !== "it") {
  language = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language])
    .map((tag) => String(tag || "").toLowerCase().split("-")[0]).find((base) => base === "it" || base === "en") || "en";
}
document.documentElement.lang = language;
const theme = preference === "amoled" || preference === "dark" || preference === "light"
  ? preference
  : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
document.documentElement.dataset.theme = theme;
document.documentElement.style.colorScheme = theme === "light" ? "light" : "dark";
document.querySelector('meta[name="theme-color"]').content =
  theme === "amoled" ? "#000000" : theme === "dark" ? "#14251b" : "#173b30";
