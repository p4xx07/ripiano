// Run against the local demo archive; credentials must be supplied as environment variables.
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("playwright");
const username = process.env.RIPIANO_SHOWCASE_USERNAME;
const password = process.env.RIPIANO_SHOWCASE_PASSWORD;
if (!username || !password) throw new Error("Set RIPIANO_SHOWCASE_USERNAME and RIPIANO_SHOWCASE_PASSWORD");

const origin = process.env.RIPIANO_SHOWCASE_ORIGIN ?? "http://localhost:18080";
const output = path.resolve("qa-artifacts/20261111-appearance");
const browser = await chromium.launch({ channel: "chrome", headless: true });

async function check(theme, mobile) {
  const name = mobile ? "mobile" : "desktop";
  const directory = path.join(output, theme, name);
  await mkdir(directory, { recursive: true });
  const context = await browser.newContext({
    viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 },
    isMobile: mobile,
    hasTouch: mobile,
    deviceScaleFactor: 1,
    colorScheme: "light",
  });
  const page = await context.newPage();
  await page.goto(origin);
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: /Everything in its place/ }).waitFor();
  if (mobile) await page.getByRole("button", { name: "Toggle menu" }).click();
  await page.getByRole("combobox", { name: "Appearance" }).selectOption(theme);
  const state = await page.evaluate(() => ({
    theme: document.documentElement.dataset.theme,
    canvas: getComputedStyle(document.documentElement).getPropertyValue("--color-canvas").trim(),
    meta: document.querySelector('meta[name="theme-color"]')?.getAttribute("content"),
    manifest: document.querySelector('link[rel="manifest"]')?.getAttribute("href"),
    stored: localStorage.getItem("ripiano.theme"),
  }));
  const expectedCanvas = theme === "amoled" ? "#000000" : "#101a14";
  const expectedMeta = theme === "amoled" ? "#000000" : "#14251b";
  const expectedManifest = `/manifest-${theme}.webmanifest`;
  if (state.theme !== theme || state.canvas !== expectedCanvas ||
      state.meta !== expectedMeta || state.manifest !== expectedManifest ||
      state.stored !== theme) {
    throw new Error(`Invalid ${theme} state: ${JSON.stringify(state)}`);
  }
  const manifest = await page.evaluate(async (url) => {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Manifest HTTP ${response.status}`);
    return response.json();
  }, expectedManifest);
  if (manifest.id !== "/" || manifest.theme_color !== expectedMeta ||
      manifest.background_color !== expectedCanvas) {
    throw new Error(`Invalid ${theme} install manifest: ${JSON.stringify(manifest)}`);
  }
  if (mobile) {
    await page.screenshot({ path: path.join(directory, "appearance-menu.png"), animations: "disabled" });
    await page.getByRole("button", { name: "Dismiss navigation" }).click();
  }
  await page.getByRole("button", { name: "Home insurance policy", exact: true }).waitFor();
  await page.screenshot({ path: path.join(directory, "library.png"), fullPage: true, animations: "disabled" });
  await page.reload();
  await page.getByRole("heading", { name: /Everything in its place/ }).waitFor();
  const reloaded = await page.evaluate(() => document.documentElement.dataset.theme);
  if (reloaded !== theme) throw new Error(`Theme did not survive reload: ${reloaded}`);
  await context.close();
  console.log(`${theme} ${name}: persisted, colors and metadata correct`);
}

try {
  for (const theme of ["dark", "amoled"]) {
    await check(theme, false);
    await check(theme, true);
  }
  const context = await browser.newContext({ colorScheme: "dark" });
  const page = await context.newPage();
  await page.goto(origin);
  await page.getByRole("combobox", { name: "Appearance" }).waitFor();
  const system = await page.evaluate(() => document.documentElement.dataset.theme);
  if (system !== "dark") throw new Error(`System dark preference did not apply: ${system}`);
  await page.emulateMedia({ colorScheme: "light" });
  await page.waitForFunction(() => document.documentElement.dataset.theme === "light");
  const changed = await page.evaluate(() => document.documentElement.dataset.theme);
  if (changed !== "light") throw new Error(`System light change did not apply: ${changed}`);
  await page.getByRole("combobox", { name: "Appearance" }).selectOption("amoled");
  await page.reload();
  const loginTheme = await page.evaluate(() => document.documentElement.dataset.theme);
  if (loginTheme !== "amoled") throw new Error(`Sign-in theme did not persist: ${loginTheme}`);
  await context.close();
  console.log("system preference: OS changes applied; sign-in choice persisted");
} finally {
  await browser.close();
}
