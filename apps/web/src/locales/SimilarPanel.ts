import { defineMessages } from "../i18n";

export default defineMessages({
  loadError: "Could not find similar documents",
  heading: "Similar documents",
  intro: "Found on your server by the words documents share. Nothing is sent elsewhere.",
  find: "Find similar documents",
  notReady: "Available once processing has finished",
  exactCopy: "Exact copy · ",
  likelyDuplicate: "Likely duplicate · ",
  similarity: (pct: number, terms: string) => `${pct}% similar · shares ${terms}`,
  empty: "No similar documents yet.",
}, {
  loadError: "Impossibile trovare documenti simili",
  heading: "Documenti simili",
  intro: "Trovati sul tuo server in base alle parole che i documenti hanno in comune. Nulla viene inviato altrove.",
  find: "Trova documenti simili",
  notReady: "Disponibile al termine dell'elaborazione",
  exactCopy: "Copia identica · ",
  likelyDuplicate: "Probabile duplicato · ",
  similarity: (pct: number, terms: string) => `Simile al ${pct}% · in comune: ${terms}`,
  empty: "Ancora nessun documento simile.",
});
