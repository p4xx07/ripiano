import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";

// Needs the local test mail server: docker compose -f deploy/compose.mailtest.yaml up -d
const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const smtpPort = Number(process.env.RIPIANO_E2E_SMTP_PORT ?? 3025);
const imapHost = process.env.RIPIANO_E2E_IMAP_HOST ?? "mailtest";
const fixture = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

function sendMail(to: string, from: string, subject: string, filename: string) {
  const boundary = `b${Date.now()}`;
  const attachment = fixture.toString("base64").replace(/.{76}/g, "$&\r\n");
  const body = [
    `From: ${from}`, `To: ${to}`, `Subject: ${subject}`, `Message-ID: <${boundary}@ripiano.test>`,
    `Date: ${new Date().toUTCString()}`, "MIME-Version: 1.0", `Content-Type: multipart/mixed; boundary="${boundary}"`, "",
    `--${boundary}`, "Content-Type: text/plain; charset=utf-8", "", "Receipt attached.", "",
    `--${boundary}`, `Content-Type: image/png; name="${filename}"`, `Content-Disposition: attachment; filename="${filename}"`,
    "Content-Transfer-Encoding: base64", "", attachment, `--${boundary}--`, "",
  ].join("\r\n");
  const commands = ["EHLO ripiano.test", `MAIL FROM:<${from.replace(/.*<|>.*/g, "")}>`, `RCPT TO:<${to}>`, "DATA", `${body}\r\n.`, "QUIT"];
  return new Promise<void>((resolve, reject) => {
    const socket = net.connect(smtpPort, "127.0.0.1");
    let buffer = "";
    socket.setEncoding("utf8");
    socket.on("data", (chunk: string) => {
      buffer += chunk;
      if (!/(^|\r\n)\d{3} [^\r\n]*\r\n$/.test(buffer)) return;
      if (/^[45]|\r\n[45]\d\d /.test(buffer)) return reject(new Error(buffer));
      buffer = "";
      const next = commands.shift();
      if (next) socket.write(`${next}\r\n`);
    });
    socket.on("end", resolve);
    socket.on("error", reject);
  });
}

test("a mail rule imports matching attachments and leaves other mail alone", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const mailbox = `inbox-${suffix}@ripiano.test`;
  const subject = `Receipt ${suffix}`;
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Email", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Email." })).toBeVisible();

  const accountForm = page.getByRole("form", { name: "Mailbox settings" });
  await accountForm.getByLabel("Name", { exact: true }).fill(`Mail ${suffix}`);
  await accountForm.getByLabel("IMAP server").fill(imapHost);
  await accountForm.getByLabel("Security").selectOption("none");
  await accountForm.getByLabel("Port", { exact: true }).fill("3143");
  await accountForm.getByLabel("Username").fill(mailbox);
  await accountForm.getByLabel("Password").fill("local-test");
  await accountForm.getByRole("button", { name: "Connect and test" }).click();
  const card = page.locator(".mail-card").filter({ hasText: mailbox });
  await expect(card).toContainText(/Connected · \d+ folders?/);

  const ruleForm = page.getByRole("form", { name: "Mail rule" });
  await ruleForm.getByLabel("Rule name").fill(`Receipts ${suffix}`);
  await ruleForm.getByRole("combobox", { name: "Mailbox", exact: true }).selectOption({ label: `Mail ${suffix}` });
  await ruleForm.getByLabel("Sender contains").fill(`shop-${suffix}`);
  await ruleForm.getByRole("button", { name: "Add rule" }).click();
  await expect(page.getByRole("status")).toContainText(`Rule “Receipts ${suffix}” saved`);

  await sendMail(mailbox, `Shop <shop-${suffix}@example.test>`, subject, `receipt-${suffix}.png`);
  await sendMail(mailbox, `Friend <friend-${suffix}@example.test>`, `Holiday ${suffix}`, `holiday-${suffix}.png`);
  await card.getByRole("button", { name: "Check now" }).click();
  await expect(card).toContainText(/Checked .* · 1 new/, { timeout: 30000 });
  const recent = page.locator(".agent-events");
  await expect(recent).toContainText(subject);
  await expect(recent).toContainText("1 document added");
  await expect(recent).toContainText(`Holiday ${suffix}`);
  await page.locator(".agent-layout").screenshot({ path: testInfo.outputPath("email-intake.png"), animations: "disabled" });

  const found = await (await page.request.get(`/api/documents?q=${encodeURIComponent(suffix)}`)).json();
  const titles = found.documents.map((item: { title: string }) => item.title);
  expect(titles).toContain(subject);
  expect(titles).not.toContain(`Holiday ${suffix}`);
  const document = found.documents.find((item: { title: string }) => item.title === subject);
  expect(document.source).toBe("email");
  const original = await page.request.get(`/api/documents/${document.id}/original`);
  expect(await original.body()).toEqual(fixture);

  // A second check finds nothing new: each message is handled once.
  await card.getByRole("button", { name: "Check now" }).click();
  await expect(card).toContainText(/Checked .* · 0 new/, { timeout: 30000 });

  // Removing the mailbox removes its rules but keeps imported documents.
  await card.getByRole("button", { name: `Remove mailbox Mail ${suffix}` }).click();
  await card.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(card).toHaveCount(0);
  await expect(page.locator(".mail-card").filter({ hasText: `Receipts ${suffix}` })).toHaveCount(0);

  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "All documents" }).click();
  await page.getByRole("button", { name: subject, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await expect(dialog.locator(".email-origin")).toContainText(`From email · Shop <shop-${suffix}@example.test> · “${subject}”`);
  await dialog.locator(".email-origin").screenshot({ path: testInfo.outputPath("email-origin.png"), animations: "disabled" });
});
