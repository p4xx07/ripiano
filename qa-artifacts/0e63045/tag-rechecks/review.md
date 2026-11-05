# Targeted automatic tag rechecks

Adding or removing a tag phrase now rechecks ready documents that could be affected by that phrase. Title-only and OCR-text-only phrases limit the candidate set to the selected field. Removing a phrase rechecks documents carrying its automatic tag; manual tags remain in place. Deleting a tag removes its links directly. Rule changes take the same PostgreSQL owner row lock as classification.

Verification on the local development stack: 30 API tests passed, Django system check passed, and 24 desktop/mobile browser journeys passed in 51.3 seconds. The browser archive journey creates a tag with an OCR keyword and retrieves the uploaded document by that tag. A synthetic two-thread PostgreSQL probe paused a classifier after matching a tag rule, started deletion, confirmed deletion waited, and then confirmed the final document had no automatic tag.

The independent code judge could not run this slice because its usage limit was reached. This checkpoint records implementation evidence, not an independent release score. The app remains short of full Paperless parity and real-device capture verification.
