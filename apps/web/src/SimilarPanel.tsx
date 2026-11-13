import { useState } from "react";
import { Sparkles } from "lucide-react";
import { request } from "./api";
import { Button } from "./ui";

type Similar = { id: string; title: string; score: number; created_at: string; shared_terms: string[]; exact_copy: boolean; likely_duplicate: boolean };

export default function SimilarPanel({ documentId, ready, onOpenDocument }: { documentId: string; ready: boolean; onOpenDocument: (id: string) => void }) {
  const [items, setItems] = useState<Similar[] | null>(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      setItems((await request<{ similar: Similar[] }>(`/api/documents/${documentId}/similar`)).similar);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not find similar documents");
    }
  }

  return (
    <section className="pages-section similar-panel" aria-labelledby="similar-heading">
      <h3 id="similar-heading"><Sparkles size={17} aria-hidden="true" /> Similar documents</h3>
      <p>Found on your server by the words documents share. Nothing is sent elsewhere.</p>
      {error && <div className="inline-error" role="alert">{error}</div>}
      {items === null ? (
        <Button type="button" variant="secondary" disabled={!ready} onClick={() => void load()}>{ready ? "Find similar documents" : "Available once processing has finished"}</Button>
      ) : items.length ? (
        <ul className="similar-list">
          {items.map((item) => (
            <li key={item.id}>
              <button type="button" className="text-action" onClick={() => onOpenDocument(item.id)}>{item.title}</button>
              <span>
                {item.exact_copy ? "Exact copy · " : item.likely_duplicate ? "Likely duplicate · " : ""}
                {Math.round(item.score * 100)}% similar · shares {item.shared_terms.join(", ")}
              </span>
            </li>
          ))}
        </ul>
      ) : <p>No similar documents yet.</p>}
    </section>
  );
}
