import { expect, test } from "@playwright/test";
import type { Document, PaperCategory, Tag } from "../src/api";
import { suggestPaperCategory } from "../src/paperCategorySuggestion";

const categories: PaperCategory[] = [
  { id: "1", prefix: "MED", name: "Medical" },
  { id: "2", prefix: "HOM", name: "Home" },
  { id: "3", prefix: "VAR", name: "Other" },
  { id: "5", prefix: "AUT", name: "Vehicles" },
];
const tag = (id: string, name: string, parent_id: string | null = null): Tag => ({ id, name, parent_id, color: "", description: "", barcode_value: "" });
const attached = (id: string, name: string): Document["tags"][number] => ({ id, name, color: "", origin: "rule" });

test("paper topic suggestion uses one broad tag or parent and stays neutral when topics conflict", () => {
  const available = [tag("health", "Health"), tag("report", "Lab report", "health"), tag("home", "Home")];
  expect(suggestPaperCategory([attached("report", "Lab report")], [], categories, available)).toEqual({ prefix: "MED", tag: "Health" });
  expect(suggestPaperCategory([attached("report", "Lab report"), attached("home", "Home")], [], categories, available)).toEqual({ prefix: "VAR", tag: null, ambiguous: true });
  expect(suggestPaperCategory([attached("unknown", "Bollettini")], [], categories, available)).toEqual({ prefix: "VAR", tag: null, ambiguous: false });
  expect(suggestPaperCategory([attached("auto", "Auto")], [], categories, available)).toEqual({ prefix: "VAR", tag: null, ambiguous: false });
  expect(suggestPaperCategory([attached("home", "Home")], [], [...categories, { id: "4", prefix: "CAS", name: "Home" }], available)).toEqual({ prefix: "VAR", tag: null, ambiguous: true });
  expect(suggestPaperCategory([attached("home", "Home")], [{ category_prefix: "MED" } as Document["physical_copies"][number]], categories, available)).toEqual({ prefix: "MED", tag: null });
});

test("every starter tag area maps to its default paper category, through renamed Italian parents too", () => {
  const defaults: PaperCategory[] = [
    ["MED", "Medical"], ["HOM", "Home"], ["FIN", "Finance and taxes"], ["AUT", "Vehicles"],
    ["PER", "Personal"], ["EVT", "Events and travel"], ["VAR", "Other"],
  ].map(([prefix, name], index) => ({ id: String(index), prefix, name }));
  const starter: [string, string, string][] = [
    ["Health", "Pharmacy", "MED"], ["Home", "Utilities", "HOM"], ["Finance and taxes", "Bank", "FIN"],
    ["Vehicles", "Car insurance", "AUT"], ["Personal", "School", "PER"], ["Events and travel", "Tickets", "EVT"],
  ];
  for (const [parent, child, prefix] of starter) {
    const available = [tag("p", parent), tag("c", child, "p")];
    expect(suggestPaperCategory([attached("c", child)], [], defaults, available)).toEqual({ prefix, tag: parent });
  }
  for (const [parent, prefix] of [["Salute", "MED"], ["Casa", "HOM"], ["Finanze e tasse", "FIN"], ["Veicoli", "AUT"], ["Personale", "PER"], ["Eventi e viaggi", "EVT"]]) {
    expect(suggestPaperCategory([attached("c", "Child")], [], defaults, [tag("p", parent), tag("c", "Child", "p")])).toEqual({ prefix, tag: parent });
  }
  // Warranties has no paper area of its own: with Home it files under Home, alone it stays Other without a warning.
  const available = [tag("w", "Warranties"), tag("h", "Home")];
  expect(suggestPaperCategory([attached("w", "Warranties"), attached("h", "Home")], [], defaults, available)).toEqual({ prefix: "HOM", tag: "Home" });
  expect(suggestPaperCategory([attached("w", "Warranties")], [], defaults, available)).toEqual({ prefix: "VAR", tag: null, ambiguous: false });
});
