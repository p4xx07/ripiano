# Date and email sender detection (judge finding H2) — doc text to merge

## FEATURE_PARITY.md — row "Tags, nested tags, correspondents, document types, storage paths, dates"

Ripiano now fills an empty document date during processing: the first plausible date in the text (numeric DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY, YYYY-MM-DD, two-digit years 2000–today, and written Italian/English dates such as "10 novembre 2026", "1° marzo 2026", "10 Nov 2026", "November 10, 2026"), ignoring dates after tomorrow or before 1900. Ambiguous numeric dates are day-first by default (`RIPIANO_DATE_ORDER=DMY`, or `MDY`/`YMD`); `RIPIANO_DATE_DETECTION=0` turns text detection off. Emails (.eml, .msg, mail-rule imports) take the message Date header instead, and their sender is filed only when it exactly matches an existing correspondent's name, address, or domain (never created, never replacing a rule or manual choice). A date set or cleared by hand (`document_date_origin=manual`) is never replaced, including on Retry OCR; each automatic change appears in the document's Changes list. Covered by `archive/test_date_detection.py`.

## USER_GUIDE.md — document date

When a document is processed and has no date yet, Ripiano looks for the first date near the start of its text (for example "Milano, 10 novembre 2026" or "10/11/2026", read as day/month) and uses it as the document date; emails use the date they were sent. If an email's sender has the same name, address, or domain as one of your senders, the email is filed under that sender. A date you enter or clear yourself is always kept, even if you retry text recognition, and the document's Changes list shows "Date and sender detection" for anything Ripiano filled in.
