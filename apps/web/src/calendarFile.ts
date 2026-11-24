/** A local, all-day calendar entry. No account connection or network request is made. */
export function calendarFile(title: string, day: string, documentId: string, now = new Date()): string {
  const start = new Date(`${day}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || Number.isNaN(start.getTime()) || start.toISOString().slice(0, 10) !== day) {
    throw new Error("Invalid calendar date");
  }
  const next = new Date(start.getTime() + 86_400_000).toISOString().slice(0, 10).replace(/-/g, "");
  const stamp = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const escape = (value: string) => value.replace(/\\/g, "\\\\").replace(/\r?\n/g, "\\n").replace(/,/g, "\\,").replace(/;/g, "\\;");
  const encoder = new TextEncoder();
  const fold = (line: string) => {
    const lines: string[] = [];
    let current = "", bytes = 0;
    for (const char of line) {
      const size = encoder.encode(char).length;
      if (bytes + size > 73) { lines.push(current); current = ` ${char}`; bytes = 1; }
      else current += char;
      bytes += size;
    }
    lines.push(current);
    return lines.join("\r\n");
  };
  return [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Ripiano//Document calendar//EN", "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT", `UID:ripiano-${documentId}-${day}@local`, `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${day.replace(/-/g, "")}`, `DTEND;VALUE=DATE:${next}`,
    fold(`SUMMARY:${escape(title)}`), "END:VEVENT", "END:VCALENDAR", "",
  ].join("\r\n");
}

export function downloadCalendarEvent(title: string, day: string, documentId: string): void {
  const file = new Blob([calendarFile(title, day, documentId)], { type: "text/calendar;charset=utf-8" });
  const address = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = address;
  link.download = `ripiano-${day}.ics`;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(address), 60_000);
}
