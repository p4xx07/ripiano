# One paper label per document — proposal (2026-11-23)

**Status: implemented for the daily and replacement flows (2026-11-23).** New copies use owner-scoped category sequences, categories can be added and renamed, the ordinary document screen hides ASN, and old labels still scan. Replace label keeps previous QR codes as aliases. A category is suggested from one unambiguous broad attached tag or parent; otherwise `VAR` is proposed for review. Current behaviour is documented in [USER_GUIDE.md](USER_GUIDE.md#paper-copies). `Document.asn` remains an optional legacy archive number used by barcode splitting; a container still has an `L-…` code.

## Recommended daily flow

1. Upload or import a document. OCR makes it searchable; no physical identifier or filing form is needed.
2. If keeping paper, choose **Keep paper copy**. Ripiano suggests one broad, stable **paper category** from an explicit rule or a confident tag; otherwise it proposes `VAR`. Confirm or change it once before printing. A location is optional at this step.
3. Ripiano allocates one code and prints a label with the code in large text, a QR opening the document, the title, and the category. Put it on the paper and optionally choose its box or shelf. Moving the paper changes its location in Ripiano, never its code.
4. Searching the whole code, the `MED-00042` part, the title, OCR text, or scanning the QR finds the document and its latest recorded location. A digital-only document has no paper code.

The ordinary document screen shows **Paper copy: MED-00042 · Box A** or **Digital only**, with **Print label**, **Move**, and **Mark missing** when relevant. It does not show an ASN box or an **Add another copy** button in the main flow. A second physical copy, if ever needed, is available under an advanced action and gets its own code; this preserves accurate locations and movement history.

## Code

Example: **`MED-00042`**.

- `MED` is one of a small set of broad paper categories, independent of a document's mutable tags and current shelf: for example `MED` health, `HOM` home, `FIN` finance/tax, `AUT` vehicles, `PER` personal, `EVT` events/travel, `VAR` other. The owner can rename categories and their displayed descriptions, but printed prefixes remain reserved. A bill can have the flexible tag “Bollettini” while its stable paper category is `HOM` or `FIN`.
- `00042` is an atomic, never-reused sequence **within that owner's category**. Do not allocate a number for digital-only documents. Padding is a minimum of five digits, not a lifetime maximum.

Do not put a shelf, box, year, detailed tag, or sender in the code: those can change, and a printed label would then be misleading. For a mistaken category after printing, offer **Replace label**; keep the former code as an alias to the same physical record so an old QR never becomes a dead end. Do not silently renumber paper after a tag change.

## Migration and compatibility

- Keep existing `R-…` stickers and `L-…` location labels working indefinitely. Do not rewrite paper labels in a migration.
- Hide ASN from the ordinary document form, but retain existing ASN search and `ASN00042` barcode parsing/splitting as a legacy advanced/import feature until a replacement scan workflow is verified. An ASN on a digital-only document must not fabricate a paper copy.
- Add a new category and per-owner/category counter, with a transaction and uniqueness constraint; store old codes as lookup aliases. Allocate only when **Keep paper copy** is chosen. A safe migration leaves existing copies and movement history untouched.
- Test concurrent allocations, category changes, QR and typed-code lookup, aliases, legacy ASN split scans, restores, multiple copies under the advanced action, and permission boundaries between accounts.

## Owner decisions

Use the simple visible code `MED-00042`, with a separate sequence for each prefix. Start with `MED`, `HOM`, `FIN`, `AUT`, `PER`, `EVT`, and `VAR`; the owner can add more categories later. Locations and mutable tags stay outside the code.
