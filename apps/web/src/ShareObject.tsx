import { useState } from "react";
import { Users } from "lucide-react";
import DocumentAccessPanel, { Wording } from "./DocumentAccessPanel";
import { useMessages } from "./i18n";
import messages from "./locales/ShareObject";

export type ShareKind = "tag" | "correspondent" | "document_type" | "saved_view";

type ShareMessages = typeof messages.en;

export function shareWording(kind: ShareKind, m: ShareMessages): Wording {
  return {
    heading: m.heading(kind),
    intro: m.intro(kind),
    empty: m.empty(kind),
    editLabel: m.editLabel,
    removed: m.removed(kind),
    granted: m.granted(kind),
  };
}

/** A small "Share" button that opens the people-with-access panel for one filing object. */
export function ShareButton({ kind, id, name, open, onToggle }: { kind: ShareKind; id: string; name: string; open: boolean; onToggle: () => void }) {
  const m = useMessages(messages);
  return <button type="button" className="share-object-button" aria-pressed={open} aria-label={m.shareNamed(kind, name)} title={m.share(kind)} onClick={onToggle}>
    <Users size={16} />
  </button>;
}

export function SharePanel({ kind, id }: { kind: ShareKind; id: string }) {
  const m = useMessages(messages);
  return <div className="share-object-panel">
    <DocumentAccessPanel endpoint={`/api/object-access/${kind}/${id}`} wording={shareWording(kind, m)} startOpen />
  </div>;
}

export function useShareToggle() {
  const [openId, setOpenId] = useState<string | null>(null);
  return { openId, toggle: (id: string) => setOpenId((current) => current === id ? null : id) };
}
