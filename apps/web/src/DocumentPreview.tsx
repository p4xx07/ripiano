import { useEffect, useState } from "react";
import { ExternalLink, FileText, Maximize2, Minimize2 } from "lucide-react";
import type { Document } from "./api";
import { useMessages } from "./i18n";
import messages from "./locales/DocumentPreview";

/**
 * First page of a document, so the owner can check sender, date, and title while filing.
 * It reuses the page-image endpoint of Pages & versions (a small PNG, rendered once per version
 * and cached by the server). That endpoint works on a PDF original at any time, and on other
 * formats (photos, Office files, email) once their searchable PDF exists. Anything else gets a
 * calm placeholder instead of a broken image.
 */
export default function DocumentPreview({ document: doc }: { document: Document }) {
  const m = useMessages(messages);
  const [state, setState] = useState<"loading" | "loaded" | "failed">("loading");
  const [expanded, setExpanded] = useState(false);
  const isPdf = doc.original_name.toLowerCase().endsWith(".pdf");
  const busy = doc.status === "pending" || doc.status === "processing";
  const available = (doc.access ?? "owner") === "owner" && (isPdf || doc.status === "ready");
  const src = available ? `/api/documents/${doc.id}/pages/1.png?v=${doc.version_number}` : "";
  useEffect(() => setState("loading"), [src]);

  const placeholder = !available || state === "failed"
    ? (busy && !available ? m.processing : m.unavailable)
    : "";
  const fullSize = doc.archive_available ? `/api/documents/${doc.id}/archive` : isPdf ? `/api/documents/${doc.id}/original` : "";

  return (
    <section className={`detail-preview${expanded ? " expanded" : ""}`} aria-label={m.region}>
      <div className="detail-preview-frame" id={`detail-preview-${doc.id}`}>
        {placeholder ? (
          <p className="detail-preview-placeholder"><FileText size={22} aria-hidden="true" /> {placeholder}</p>
        ) : (
          <>
            {state === "loading" && <span className="detail-preview-loading">{m.loading}</span>}
            <img key={src} src={src} alt={m.imageAlt(doc.title)} width={397} height={562} loading="lazy" decoding="async"
              className={state === "loaded" ? "loaded" : undefined}
              onLoad={() => setState("loaded")} onError={() => setState("failed")} />
          </>
        )}
      </div>
      {!placeholder && (
        <div className="detail-preview-actions">
          <button type="button" className="text-action detail-preview-toggle" aria-expanded={expanded}
            aria-controls={`detail-preview-${doc.id}`} onClick={() => setExpanded((value) => !value)}>
            {expanded ? <Minimize2 size={15} aria-hidden="true" /> : <Maximize2 size={15} aria-hidden="true" />} {expanded ? m.showSmaller : m.showLarger}
          </button>
          {fullSize && (
            <a className="text-action" href={fullSize} target="_blank" rel="noreferrer">
              <ExternalLink size={15} aria-hidden="true" /> {m.openFullSize}
            </a>
          )}
        </div>
      )}
    </section>
  );
}
