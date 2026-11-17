import { expect, Page, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

/**
 * Basic accessibility checks that need no extra dependency: every visible control has an accessible
 * name, every form field a label, ids are unique, images have alt text, headings do not skip levels,
 * and the page has a main landmark and a language. (A full axe-core scan can be added later.)
 */
async function audit(page: Page) {
  return page.evaluate(() => {
    const problems: string[] = [];
    const visible = (el: Element) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
    const short = (el: Element) => el.outerHTML.slice(0, 90);
    for (const el of document.querySelectorAll("button, a[href], [role=button]")) {
      if (!visible(el)) continue;
      const name = (el.getAttribute("aria-label") || el.textContent || el.getAttribute("title") || "").trim();
      if (!name) problems.push(`no accessible name: ${short(el)}`);
    }
    for (const el of document.querySelectorAll("input:not([type=hidden]), select, textarea")) {
      if (!visible(el)) continue;
      const labelledBy = (el.getAttribute("aria-labelledby") || "").split(" ").map((id) => document.getElementById(id)?.textContent ?? "").join("");
      const forLabel = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent ?? "" : "";
      const label = el.getAttribute("aria-label") || labelledBy || forLabel || el.closest("label")?.textContent || el.getAttribute("title") || el.getAttribute("placeholder");
      if (!label?.trim()) problems.push(`form field without label: ${short(el)}`);
    }
    const ids = new Map<string, number>();
    for (const el of document.querySelectorAll("[id]")) ids.set(el.id, (ids.get(el.id) ?? 0) + 1);
    for (const [id, count] of ids) if (count > 1) problems.push(`duplicate id "${id}" ×${count}`);
    for (const img of document.querySelectorAll("img")) if (visible(img) && !img.hasAttribute("alt")) problems.push(`image without alt: ${short(img)}`);
    let last = 0;
    for (const heading of document.querySelectorAll("h1, h2, h3, h4, h5, h6")) {
      if (!visible(heading) && !heading.classList.contains("visually-hidden")) continue;
      const level = Number(heading.tagName[1]);
      if (last && level > last + 1) problems.push(`heading jumps from h${last} to h${level}: ${heading.textContent?.trim().slice(0, 40)}`);
      last = level;
    }
    if (!document.querySelector("main")) problems.push("no <main> landmark");
    if (!document.documentElement.lang) problems.push("no lang attribute");
    return problems;
  });
}

test("sign-in and main screens pass basic accessibility checks", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  expect(await audit(page), "sign-in").toEqual([]);
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  expect(await audit(page), "Library").toEqual([]);
  // "g" then a letter moves between screens (also checks the shortcut works).
  for (const [key, heading] of [["i", /Inbox|Nothing needs/], ["a", /Needs action|All clear/], ["t", /Tags/], ["o", "Overview."], ["r", "Sources."], ["w", "Workflows."], ["s", "Shared with me."]] as const) {
    await page.keyboard.press("g");
    await page.keyboard.press(key);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    expect(await audit(page), `screen g ${key}`).toEqual([]);
  }
});

test("keyboard: ? lists shortcuts, j/k/Enter open a Library document, and the skip link reaches the content", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await page.keyboard.press("?");
  await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  if (await page.locator(".document-row").count()) {
    await page.keyboard.press("j");
    await expect(page.locator(".document-row.keyboard-active")).toHaveCount(1);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
  }
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
});
