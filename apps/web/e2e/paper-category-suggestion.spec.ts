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
  expect(suggestPaperCategory([attached("report", "Lab report"), attached("home", "Home")], [], categories, available)).toEqual({ prefix: "VAR", tag: null });
  expect(suggestPaperCategory([attached("unknown", "Bollettini")], [], categories, available)).toEqual({ prefix: "VAR", tag: null });
  expect(suggestPaperCategory([attached("auto", "Auto")], [], categories, available)).toEqual({ prefix: "VAR", tag: null });
  expect(suggestPaperCategory([attached("home", "Home")], [], [...categories, { id: "4", prefix: "CAS", name: "Home" }], available)).toEqual({ prefix: "VAR", tag: null });
  expect(suggestPaperCategory([attached("home", "Home")], [{ category_prefix: "MED" } as Document["physical_copies"][number]], categories, available)).toEqual({ prefix: "MED", tag: null });
});
