import type { ShareKind } from "../ShareObject";
import { defineMessages } from "../i18n";

const nouns: Record<ShareKind, string> = { tag: "tag", correspondent: "sender", document_type: "document type", saved_view: "saved view" };

// Italian nouns differ in gender, so each phrase names its object in full.
const feminine = (kind: ShareKind) => kind === "tag" || kind === "saved_view";
const this_ = (kind: ShareKind) => ({ tag: "questa etichetta", correspondent: "questo mittente", document_type: "questo tipo di documento", saved_view: "questa vista salvata" })[kind];
const the = (kind: ShareKind) => ({ tag: "l'etichetta", correspondent: "il mittente", document_type: "il tipo di documento", saved_view: "la vista salvata" })[kind];
const bare = (kind: ShareKind) => ({ tag: "etichetta", correspondent: "mittente", document_type: "tipo di documento", saved_view: "vista salvata" })[kind];

export default defineMessages({
  heading: (kind: ShareKind) => `Share this ${nouns[kind]}`,
  intro: (kind: ShareKind) => kind === "saved_view"
    ? "People you share it with can apply it to the documents you shared with them. With edit access they can also rename it and change its search. Deleting stays with you."
    : `People you share it with see it under Shared with me and can use it to file your documents they may edit. With edit access they can also rename it${kind === "tag" ? " and change its colour and description" : ""}. Deleting stays with you.`,
  empty: (kind: ShareKind) => `Only you can use this ${nouns[kind]}.`,
  editLabel: "Can also edit",
  removed: (kind: ShareKind) => `can no longer use this ${nouns[kind]}.`,
  granted: (_kind: ShareKind) => "use and edit it",
  shareNamed: (kind: ShareKind, name: string) => `Share ${nouns[kind]} ${name}`,
  share: (kind: ShareKind) => `Share ${nouns[kind]}`,
}, {
  heading: (kind: ShareKind) => `Condividi ${this_(kind)}`,
  intro: (kind: ShareKind) => kind === "saved_view"
    ? "Le persone con cui la condividi possono applicarla ai documenti che hai condiviso con loro. Con l'accesso in modifica possono anche rinominarla e cambiarne la ricerca. Solo tu puoi eliminarla."
    : feminine(kind)
      ? `Le persone con cui la condividi la vedono in Condivisi con me e possono usarla per archiviare i tuoi documenti che possono modificare. Con l'accesso in modifica possono anche rinominarla${kind === "tag" ? " e cambiarne colore e descrizione" : ""}. Solo tu puoi eliminarla.`
      : "Le persone con cui lo condividi lo vedono in Condivisi con me e possono usarlo per archiviare i tuoi documenti che possono modificare. Con l'accesso in modifica possono anche rinominarlo. Solo tu puoi eliminarlo.",
  empty: (kind: ShareKind) => `Solo tu puoi usare ${this_(kind)}.`,
  editLabel: "Può anche modificare",
  removed: (kind: ShareKind) => `non può più usare ${this_(kind)}.`,
  granted: (kind: ShareKind) => feminine(kind) ? "usarla e modificarla" : "usarlo e modificarlo",
  shareNamed: (kind: ShareKind, name: string) => `Condividi ${the(kind)} ${name}`,
  share: (kind: ShareKind) => `Condividi ${bare(kind)}`,
});
