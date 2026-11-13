import { expect, test } from "@playwright/test";
import { createHmac } from "node:crypto";

// Uses its own disposable account, because it turns two-step sign-in on and off.
const username = process.env.RIPIANO_E2E_2FA_USERNAME;
const password = process.env.RIPIANO_E2E_2FA_PASSWORD;

function totp(secret: string, offset = 0) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const char of secret.replace(/=+$/, "")) bits += alphabet.indexOf(char).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g)!.map((byte) => parseInt(byte, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000) + offset));
  const digest = createHmac("sha1", key).update(counter).digest();
  const start = digest[digest.length - 1] & 0x0f;
  return String((digest.readUInt32BE(start) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

test("two-step sign-in can be turned on, used with a recovery code, and turned off", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_2FA_USERNAME and RIPIANO_E2E_2FA_PASSWORD");
  test.skip(testInfo.project.name !== "desktop", "One account is shared, so this runs once");
  async function signIn(code?: string) {
    await page.getByLabel("Username").fill(username!);
    await page.getByLabel("Password").fill(password!);
    await page.getByRole("button", { name: "Sign in" }).click();
    if (code !== undefined) {
      await page.getByLabel(/Authenticator code/).fill(code);
      await page.getByRole("button", { name: "Sign in" }).click();
    }
    await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  }
  await page.goto("/");
  await signIn();
  await page.getByRole("button", { name: "Security", exact: true }).click();
  await expect(page.getByText("Two-step sign-in is off")).toBeVisible();
  await page.getByLabel("Your password").fill(password!);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("img", { name: "QR code for your authenticator app" })).toBeVisible();
  const secret = (await page.locator(".security-secret").textContent())!.trim();
  await page.getByLabel("Code from the app").fill(totp(secret));
  await page.getByRole("button", { name: "Turn on" }).click();
  await expect(page.getByRole("status")).toContainText("Two-step sign-in is on");
  const codes = await page.locator(".security-recovery code").allTextContents();
  expect(codes).toHaveLength(10);
  await page.locator(".agent-layout").screenshot({ path: testInfo.outputPath("security.png"), animations: "disabled" });

  await page.locator("button[title=\"Sign out\"]").click();
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByLabel(/Authenticator code/)).toBeVisible();
  await page.getByLabel(/Authenticator code/).fill("000000");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toContainText("That code is not valid");
  await page.getByLabel(/Authenticator code/).fill(codes[0]);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("button[title=\"Sign out\"]")).toBeVisible();

  await page.getByRole("button", { name: "Security", exact: true }).click();
  await expect(page.getByText("9 recovery codes left")).toBeVisible();
  await page.getByLabel("Your password").fill(password!);
  await page.getByLabel("Authenticator or recovery code").fill(codes[1]);
  await page.getByRole("button", { name: "Turn off two-step sign-in" }).click();
  await expect(page.getByRole("status")).toHaveText("Two-step sign-in is off.");
});
