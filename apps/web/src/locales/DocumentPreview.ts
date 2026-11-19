import { defineMessages } from "../i18n";

/** First-page preview in the document dialog. */
export default defineMessages({
  region: "Preview",
  imageAlt: (title: string) => `First page of “${title}”`,
  loading: "Loading the preview…",
  processing: "The preview appears when processing finishes.",
  unavailable: "No preview for this document.",
  showLarger: "Show larger",
  showSmaller: "Show smaller",
  openFullSize: "Open full size",
}, {
  region: "Anteprima",
  imageAlt: (title: string) => `Prima pagina di “${title}”`,
  loading: "Caricamento dell'anteprima…",
  processing: "L'anteprima compare quando l'elaborazione è finita.",
  unavailable: "Nessuna anteprima per questo documento.",
  showLarger: "Mostra più grande",
  showSmaller: "Mostra più piccola",
  openFullSize: "Apri a grandezza intera",
});
