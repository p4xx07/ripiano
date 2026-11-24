import { expect, test } from "@playwright/test";
import { calendarFile } from "../src/calendarFile";

test("local calendar file keeps the date, escapes the title, and crosses month/year boundaries", () => {
  const calendar = calendarFile("Concerto, casa; Nuovo\\anno", "2026-12-31", "document-1", new Date("2026-11-24T08:30:00Z"));
  expect(calendar).toContain("DTSTART;VALUE=DATE:20261231\r\nDTEND;VALUE=DATE:20270101");
  expect(calendar).toContain("DTSTAMP:20261124T083000Z");
  expect(calendar).toContain("SUMMARY:Concerto\\, casa\\; Nuovo\\\\anno");
  expect(calendar).toContain("UID:ripiano-document-1-2026-12-31@local");
  expect(calendar).not.toContain("https://");
  expect(() => calendarFile("Invalid", "2027-02-30", "document-1")).toThrow("Invalid calendar date");
});
