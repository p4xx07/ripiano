import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

// Round-4 judge 2 regressions: Trash focus and Undo (M1), phone drawer focus containment (M2), damaged
// file message (M3), offline reload screen (M4), and the quick Low items (L1, L2, L3, L6).
const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const image = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

test.use({ serviceWorkers: "block" });

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
}

async function uploadReady(page: Page, name: string) {
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: image });
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible({ timeout: 60000 });
  // Trash refuses documents still being processed, so wait until OCR has finished.
  await expect.poll(async () => {
    const found = (await (await page.request.get(`/api/documents?q=${encodeURIComponent(name)}`)).json()).documents as { title: string; status: string }[];
    return found.find((item) => item.title === name)?.status;
  }, { timeout: 90000 }).toBe("ready");
  await page.reload();
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
}

test("moving a document to Trash keeps focus, announces it, and Undo puts it back", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r4-trash-${Date.now()}-${testInfo.project.name}`;
  await uploadReady(page, name);
  await page.getByRole("button", { name, exact: true }).focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Move to Trash" }).focus();
  await page.keyboard.press("Enter");
  await expect(dialog.getByRole("button", { name: "Confirm move" })).toBeFocused();
  await dialog.locator(".trash-confirm").getByRole("button", { name: "Cancel" }).press("Enter");
  await expect(dialog.getByRole("button", { name: "Move to Trash" })).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Enter"); // Confirm move
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const status = page.locator(".trash-undo-region");
  await expect(status).toHaveAttribute("aria-live", "polite");
  await expect(status).toContainText(`Moved “${name}” to Trash.`);
  // Focus is on the list (the row now in its place) or the Library heading, never the page body.
  await expect.poll(() => page.evaluate(() => document.activeElement?.tagName)).not.toBe("BODY");
  const focusedInList = await page.evaluate(() => Boolean(document.activeElement?.closest(".document-row") || document.activeElement?.tagName === "H1"));
  expect(focusedInList).toBe(true);

  await page.getByRole("button", { name: `Undo: put “${name}” back` }).click();
  await expect(status).toContainText(`“${name}” is back in your documents.`);
  await expect(page.getByRole("button", { name, exact: true })).toBeFocused();
});

test("the open phone menu keeps Tab inside the drawer and makes the page behind inert", async ({ page, isMobile }) => {
  test.skip(!isMobile || !username || !password, "The drawer exists only on narrow screens");
  await signIn(page);
  const menu = page.getByRole("button", { name: "Toggle menu" });
  await menu.click();
  await expect(page.locator("#main-content")).toHaveAttribute("inert", "");
  for (let step = 0; step < 40; step += 1) {
    await page.keyboard.press(step % 7 === 6 ? "Shift+Tab" : "Tab");
    expect(await page.evaluate(() => Boolean(document.activeElement?.closest("#app-sidebar")))).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await expect(menu).toBeFocused();
  await expect(page.locator("#main-content")).not.toHaveAttribute("inert", "");
});

test("a damaged file named like a PDF is reported as damaged, not as the wrong type", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: "r4-bad.pdf", mimeType: "application/pdf", buffer: Buffer.from("just text, not a PDF") });
  const report = page.locator(".upload-report");
  await expect(report).toContainText("could not be read as a PDF");
  await expect(report).not.toContainText("Use PDF, JPEG, PNG");
});

test("reloading while offline shows who is signed in and the files waiting, then reconnects", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  // Only the username is remembered on the device, never a secret.
  expect(await page.evaluate(() => localStorage.getItem("ripiano.lastSignedIn"))).toBe(username);
  await page.evaluate(([owner]) => new Promise<void>((resolve, reject) => {
    const open = indexedDB.open("ripiano-uploads", 1);
    open.onsuccess = () => {
      const tx = open.result.transaction("pending", "readwrite");
      tx.objectStore("pending").put({ id: "r4-offline-probe", owner, name: "r4-probe.png", type: "image/png", blob: new Blob(["x"]), addedAt: Date.now() });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    };
  }), [username!]);
  // The app shell still loads (as from the installed PWA's cache); Ripiano itself cannot be reached.
  await page.route("**/api/**", (route) => route.abort("internetdisconnected"));
  await page.reload().catch(() => undefined);
  // The device is online; only the server is unreachable, so it is not called "offline" (round-11 judge 3 L2).
  await expect(page.getByRole("heading", { name: "Ripiano can't be reached" })).toBeVisible();
  await expect(page.getByText(`Last signed in on this device as ${username}.`)).toBeVisible();
  await expect(page.getByText("1 file is waiting on this device")).toBeVisible();
  await expect(page.getByLabel("Password")).toHaveCount(0); // not shown as signed out
  // Remove the probe before reconnecting so it is never sent.
  await page.evaluate(() => new Promise<void>((resolve) => {
    const open = indexedDB.open("ripiano-uploads", 1);
    open.onsuccess = () => {
      const tx = open.result.transaction("pending", "readwrite");
      tx.objectStore("pending").delete("r4-offline-probe");
      tx.oncomplete = () => resolve();
    };
  }));
  await page.unroute("**/api/**");
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
});

test("Agents, Paper archive and Backups fit 320px in Italian; agent choices are touch-sized lists", async ({ page, isMobile }) => {
  test.skip(!isMobile || !username || !password, "Use the mobile project");
  await signIn(page);
  await page.route("**/api/backups", (route) => route.request().method() === "GET"
    ? route.fulfill({ json: { schedule: "10:00", runs: [] } })
    : route.fallback());
  await page.evaluate(() => localStorage.setItem("ripiano.language", "it"));
  await page.setViewportSize({ width: 320, height: 640 });
  for (const route of ["/agents", "/paper", "/backups"]) {
    await page.goto(route);
    await expect(page.locator("main h1")).toBeVisible();
    const { width, scrollWidth } = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    expect(scrollWidth, `${route} at 320px`).toBeLessThanOrEqual(width + 1);
  }
  await page.goto("/agents");
  for (const choice of await page.locator(".agent-create-card .agent-scope-choice").all()) {
    expect((await choice.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect((await choice.locator("input").boundingBox())!.width).toBeGreaterThanOrEqual(24);
  }
  await expect(page.getByLabel("La tua password (per creare un token dell'agente)")).toHaveAttribute("type", "password");
  if (await page.locator(".agent-events").count()) await expect(page.locator("ul.agent-events > li").first()).toBeVisible();
});

test("the ASN field is named briefly and described by its hint", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r4-asn-${Date.now()}-${testInfo.project.name}`;
  await uploadReady(page, name);
  await page.getByRole("button", { name, exact: true }).click();
  const field = page.getByRole("dialog").getByRole("textbox", { name: "Archive number (ASN)", exact: true });
  await expect(field).toBeVisible();
  await expect(field).toHaveAccessibleDescription(/your own running number/);
});
