import { useState } from "react";
import { Users } from "lucide-react";
import DocumentAccessPanel, { Wording } from "./DocumentAccessPanel";

export type ShareKind = "tag" | "correspondent" | "document_type" | "saved_view";

const nouns: Record<ShareKind, string> = { tag: "tag", correspondent: "sender", document_type: "document type", saved_view: "saved view" };

export function shareWording(kind: ShareKind): Wording {
  const noun = nouns[kind];
  return {
    heading: `Share this ${noun}`,
    intro: kind === "saved_view"
      ? "People you share it with can apply it to the documents you shared with them. With edit access they can also rename it and change its search. Deleting stays with you."
      : `People you share it with see it under Shared with me and can use it to file your documents they may edit. With edit access they can also rename it${kind === "tag" ? " and change its colour and description" : ""}. Deleting stays with you.`,
    empty: `Only you can use this ${noun}.`,
    editLabel: "Can also edit",
    removed: `can no longer use this ${noun}.`,
    granted: "use and edit it",
  };
}

/** A small "Share" button that opens the people-with-access panel for one filing object. */
export function ShareButton({ kind, id, name, open, onToggle }: { kind: ShareKind; id: string; name: string; open: boolean; onToggle: () => void }) {
  return <button type="button" className="share-object-button" aria-pressed={open} aria-label={`Share ${nouns[kind]} ${name}`} title={`Share ${nouns[kind]}`} onClick={onToggle}>
    <Users size={16} />
  </button>;
}

export function SharePanel({ kind, id }: { kind: ShareKind; id: string }) {
  return <div className="share-object-panel">
    <DocumentAccessPanel endpoint={`/api/object-access/${kind}/${id}`} wording={shareWording(kind)} startOpen />
  </div>;
}

export function useShareToggle() {
  const [openId, setOpenId] = useState<string | null>(null);
  return { openId, toggle: (id: string) => setOpenId((current) => current === id ? null : id) };
}
