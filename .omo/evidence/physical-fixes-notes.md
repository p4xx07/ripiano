# Paper archive location fixes (judge 1, M2 and M3): user-guide text

## English

In **Paper archive → Add a location**, the button tells you where the new location goes ("Add location at top level" or "Add location inside Shelf / Box"). After you add a location, "Inside" goes back to the top level. To fix a mistake, choose **Edit** next to a location. You can rename it or choose a new "Inside" location. Paper copies, stickers, printed labels, and their history stay attached, and any locations inside it move with it. **Delete location** asks you to confirm first. It works only when the location is empty, so move its paper copies and any locations inside it somewhere else first. Printed stickers keep the code on one line and show the innermost locations when the full path is too long.

## Italiano

In **Archivio cartaceo → Aggiungi una posizione**, il pulsante indica dove verrà creata la nuova posizione ("Aggiungi posizione al livello principale" oppure "Aggiungi posizione dentro Scaffale / Scatola"). Dopo che hai aggiunto una posizione, "Dentro" torna al livello principale. Per correggere un errore, scegli **Modifica** accanto a una posizione. Puoi rinominarla o scegliere una nuova posizione in "Dentro". Copie cartacee, adesivi, etichette stampate e cronologia restano collegati, e le posizioni contenute vengono spostate insieme. **Elimina posizione** chiede prima una conferma. Funziona solo se la posizione è vuota, quindi sposta altrove le copie cartacee e le posizioni che contiene. Sulle etichette stampate il codice resta su una riga, e se il percorso è troppo lungo vengono mostrate le posizioni più interne.

## Verification notes

- API: `PATCH /api/locations/<id>` accepts `{name?, parent_id?}`. It is owner-scoped (404 for another owner), refuses cycles (400), and refuses a duplicate name among siblings, ignoring case (409). It changes only the location row, so copy IDs, stickers, and Movement rows are unchanged. `DELETE` returns a specific 409 for child locations, for paper copies stored there, and for copies of documents in Trash.
- Labels: rendered in Chrome at 70 × 40 mm, with one PDF page per label (MediaBox 198 × 113 pt). The worst-case code `R-WWWWWWWW` auto-sizes to about 9.3pt with no horizontal overflow, and a typical code renders at 12pt. The title is limited to 3 lines and the path to 3 lines. A path longer than 60 characters drops outer locations first ("… / Scatola 2026 / Cartella blu").
- Resource impact: none. There are no new dependencies, and the code adds one in-memory walk of the owner's locations per PATCH.
