# Filing metadata UX judge follow-up

Base commit: `c33dcee`. The code judge cleared the additive models, owner-scoped API, search, signed paging, and tests. The UX judge found three medium issues: long vocabulary lists lacked filtering, search copy hid the new fields, and rename/delete focus was lost.

The Tags & filing page now has an accessible filter in each vocabulary card. Long lists scroll inside a bounded area, leaving the second card reachable. The Library search hint names sender, type, tag, and sticker, and result rows label “From” and “Type.” Rename editing takes focus; Save and Cancel return focus to the row’s rename control; Delete moves focus to the card filter. A polite status announces each completed action.

Verification: `npm run build` passed; the local web container rebuilt. The full Playwright suite passed 22 desktop/mobile journeys before the final list-height adjustment; the focused filing journey passed again after it and after the Cancel keyboard assertion was added. The journey uses keyboard activation and checks focus after Rename, Save, Cancel, and Delete, filters both cards, and searches by sender and type. Updated [desktop](filing/desktop/vocabularies.png) and [mobile](filing/mobile/vocabularies.png) vocabulary captures plus [mobile search](filing/mobile/search.png) were inspected. The mobile cards and list stay within the viewport.

This is an incremental UX gate. Automatic sender/type classification, installed PWA capture, and Android hardware capture remain outside this slice.
