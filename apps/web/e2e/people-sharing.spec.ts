import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const owner = { username: process.env.RIPIANO_E2E_USERNAME, password: process.env.RIPIANO_E2E_PASSWORD };
// The second disposable account (also used by the two-step sign-in journey, which leaves it with 2FA off).
const reader = { username: process.env.RIPIANO_E2E_2FA_USERNAME, password: process.env.RIPIANO_E2E_2FA_PASSWORD };
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

async function signIn(page: Page, account: { username?: string; password?: string }) {
  await page.getByLabel("Username").fill(account.username!);
  await page.getByLabel("Password").fill(account.password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
}

async function openNav(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("share one document with another person, who can edit its details but nothing else", async ({ page }, testInfo) => {
  test.skip(!owner.username || !owner.password || !reader.username || !reader.password, "Set the RIPIANO_E2E_* and RIPIANO_E2E_2FA_* accounts");
  test.skip(testInfo.project.name !== "desktop", "The second account is shared, so this runs once");
  test.setTimeout(120000);
  await page.goto("/");
  await signIn(page, owner);

  const name = `shared-${Date.now()}`;
  await page.getByRole("button", { name: "Add document", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  await page.getByRole("button", { name, exact: true }).click();
  let dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await dialog.getByText("Manage access").click();
  await dialog.getByLabel("Person or group").selectOption({ label: reader.username! });
  await dialog.locator(".access-panel .share-controls").getByLabel("Access").selectOption("edit");
  await dialog.getByRole("button", { name: "Share", exact: true }).click();
  await expect(dialog.locator(".access-panel").getByRole("status")).toContainText("can now view and edit details");
  await expect(dialog.getByLabel(`Access for ${reader.username}`, { exact: true })).toHaveValue("edit");
  await dialog.locator(".access-panel").screenshot({ path: testInfo.outputPath("document-access.png") });
  await dialog.getByRole("button", { name: "Close" }).click();
  await page.locator("button[title=\"Sign out\"]").click();

  await signIn(page, reader);
  // The reader's own Library stays theirs; the document is under Shared with me.
  await expect(page.getByRole("button", { name, exact: true })).toHaveCount(0);
  await openNav(page, "Shared with me");
  await expect(page.getByRole("heading", { name: /Shared with me/ })).toBeVisible();
  await page.getByRole("textbox", { name: "Search shared documents" }).fill(name);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".document-row")).toHaveCount(1);
  await expect(page.locator(".document-row")).toContainText(`Shared by ${owner.username} · Can edit details`);
  await page.getByRole("button", { name, exact: true }).click();
  dialog = page.getByRole("dialog", { name });
  await expect(dialog.getByText(`Shared by ${owner.username}`)).toBeVisible();
  await expect(dialog.getByText("Manage access")).toHaveCount(0);
  await expect(dialog.getByText("Move to Trash")).toHaveCount(0);
  const download = await page.request.get(await dialog.getByRole("link", { name: "Download original" }).getAttribute("href") as string);
  expect(Buffer.from(await download.body())).toEqual(readFileSync(fixture));
  await dialog.getByLabel("Title").fill(`${name} reviewed`);
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog.getByRole("status")).toContainText("Changes saved.");
  await dialog.getByRole("textbox", { name: "New note" }).fill("Checked the amounts");
  await dialog.getByRole("button", { name: "Add note" }).click();
  await expect(dialog.locator(".note-list")).toContainText("Checked the amounts");
  await dialog.screenshot({ path: testInfo.outputPath("shared-document.png") });
  await dialog.getByRole("button", { name: "Close" }).click();
  await page.locator("button[title=\"Sign out\"]").click();

  // The owner sees the reader's change and note, then removes access.
  await signIn(page, owner);
  await page.getByRole("textbox", { name: "Search documents" }).fill(`${name} reviewed`);
  await page.getByRole("button", { name: `${name} reviewed`, exact: true }).click();
  dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await expect(dialog.locator(".note-list")).toContainText(`${reader.username}`);
  await dialog.getByText("Manage access").click();
  await dialog.getByRole("button", { name: `Remove access for ${reader.username}` }).click();
  await expect(dialog.locator(".access-panel")).toContainText("Only you can open this document.");
  await dialog.getByRole("button", { name: "Close" }).click();
  await page.locator("button[title=\"Sign out\"]").click();

  await signIn(page, reader);
  await openNav(page, "Shared with me");
  await page.getByRole("textbox", { name: "Search shared documents" }).fill(name);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("heading", { name: "No matches." })).toBeVisible();
});

// Round-9 review M2: two people with edit access. The shared editor's save carries the version it was loaded with
// and only the details that person changed, so the owner's newer changes are never overwritten silently.
test("a shared editor's save keeps the owner's newer changes and asks about a detail both changed", async ({ page, browser }, testInfo) => {
  test.skip(!owner.username || !owner.password || !reader.username || !reader.password, "Set the RIPIANO_E2E_* and RIPIANO_E2E_2FA_* accounts");
  test.skip(testInfo.project.name !== "desktop", "The second account is shared, so this runs once");
  test.setTimeout(180000);
  await page.goto("/");
  await signIn(page, owner);
  const headers = { "X-CSRFToken": (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value ?? "" };
  const name = `shared-conflict-${Date.now()}`;
  const uploaded = await page.request.post("/api/documents", { headers, multipart: { document: { name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) } } });
  expect(uploaded.status()).toBe(202);
  const id = (await uploaded.json()).id as string;
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 90000 }).toBe("ready");
  const people = (await (await page.request.get("/api/people")).json()).people as { id: number; username: string }[];
  const shared = await page.request.post(`/api/documents/${id}/access`, { headers, data: { user_id: people.find((person) => person.username === reader.username)!.id, level: "edit" } });
  expect(shared.ok()).toBe(true);

  const other = await browser.newContext({ baseURL: testInfo.project.use.baseURL, locale: "en-US", viewport: { width: 1440, height: 900 }, serviceWorkers: "block" });
  try {
    const theirs = await other.newPage();
    await theirs.goto("/");
    await signIn(theirs, reader);
    await openNav(theirs, "Shared with me");
    await theirs.getByRole("textbox", { name: "Search shared documents" }).fill(name);
    await theirs.getByRole("button", { name: "Search", exact: true }).click();
    await theirs.getByRole("button", { name, exact: true }).click();
    const dialog = theirs.getByRole("dialog", { name });
    await expect(dialog.getByLabel("Title")).toHaveValue(name);

    // The owner renames the document and sets a follow-up while the shared editor's dialog is open.
    const first = await page.request.patch(`/api/documents/${id}`, { headers, data: { title: `${name} by owner`, action_status: "open", action_due_date: "2026-12-24" } });
    expect(first.ok()).toBe(true);

    // The editor only sets the date: nothing else is sent, so nothing of the owner's is replaced.
    const bodies: Record<string, unknown>[] = [];
    theirs.on("request", (sent) => {
      if (sent.method() === "PATCH" && sent.url().endsWith(`/api/documents/${id}`)) bodies.push(sent.postDataJSON() as Record<string, unknown>);
    });
    await dialog.getByLabel("Document date").fill("2026-02-03");
    await dialog.getByRole("button", { name: "Save changes" }).click();
    await expect(dialog.getByRole("status").filter({ hasText: "Changes saved." })).toBeVisible();
    expect(Object.keys(bodies[0]).sort()).toEqual(["base_version", "document_date"]);
    let saved = await (await page.request.get(`/api/documents/${id}`)).json();
    expect(saved.title).toBe(`${name} by owner`);
    expect(saved.action_due_date).toBe("2026-12-24");
    expect(saved.document_date).toBe("2026-02-03");
    await expect(dialog.getByLabel("Title")).toHaveValue(`${name} by owner`);

    // Both change the title: the editor's save is refused, shows the owner's value, and offers their own.
    const second = await page.request.patch(`/api/documents/${id}`, { headers, data: { title: `${name} owner again` } });
    expect(second.ok()).toBe(true);
    await dialog.getByLabel("Title").fill(`${name} by editor`);
    await dialog.getByRole("button", { name: "Save changes" }).click();
    const box = dialog.locator(".draft-restored");
    await expect(box).toContainText("Someone else saved this document while you were editing it.");
    await expect(box).toBeFocused();
    await expect(dialog.getByLabel("Title")).toHaveValue(`${name} owner again`);
    expect((await (await page.request.get(`/api/documents/${id}`)).json()).title).toBe(`${name} owner again`);
    const conflict = box.locator(".draft-conflict-list li").filter({ hasText: "Title" });
    await expect(conflict).toContainText(`Your value: ${name} by editor`);
    await conflict.getByRole("button", { name: "Use my value for Title" }).click();
    await expect(dialog.getByLabel("Title")).toHaveValue(`${name} by editor`);
    await dialog.getByRole("button", { name: "Save changes" }).click();
    await expect(dialog.getByRole("status").filter({ hasText: "Changes saved." })).toBeVisible();
    saved = await (await page.request.get(`/api/documents/${id}`)).json();
    expect(saved.title).toBe(`${name} by editor`);
    expect(saved.action_due_date).toBe("2026-12-24");
    await theirs.locator("button[title=\"Sign out\"]").click().catch(() => undefined);
  } finally {
    await other.close();
    const grants = (await (await page.request.get(`/api/documents/${id}/access`)).json()).grants as { id: string }[];
    for (const grant of grants ?? []) await page.request.delete(`/api/documents/${id}/access/${grant.id}`, { headers });
  }
});
