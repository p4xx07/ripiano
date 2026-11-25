import type { Document, PaperCategory, PhysicalCopy, Tag } from "./api";

const TOPIC_ALIASES: Record<string, string> = {
  health: "MED", salute: "MED", medicina: "MED", medico: "MED", referti: "MED",
  house: "HOM", casa: "HOM", abitazione: "HOM",
  finances: "FIN", taxes: "FIN", finanza: "FIN", finanze: "FIN", tasse: "FIN", fisco: "FIN", "finanze e tasse": "FIN",
  vehicle: "AUT", vehicles: "AUT", car: "AUT", veicoli: "AUT", automobile: "AUT",
  identity: "PER", identita: "PER", personale: "PER",
  events: "EVT", travel: "EVT", eventi: "EVT", viaggi: "EVT", concerts: "EVT", concerti: "EVT", "eventi e viaggi": "EVT",
};

function key(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
}

/** Suggest only when one attached tag (or its parent) names a broad paper topic unambiguously. */
export function suggestPaperCategory(
  attached: Document["tags"], copies: PhysicalCopy[], categories: PaperCategory[], available: Tag[],
): { prefix: string; tag: string | null; ambiguous?: boolean } {
  const existing = copies[0]?.category_prefix;
  if (existing && categories.some((category) => category.prefix === existing)) return { prefix: existing, tag: null };
  const byId = new Map(available.map((tag) => [tag.id, tag]));
  const byName = new Map<string, string[]>();
  for (const category of categories) byName.set(key(category.name), [...(byName.get(key(category.name)) ?? []), category.prefix]);
  const matches = new Map<string, string>();
  for (const entry of attached) {
    let current: Pick<Tag, "id" | "name" | "parent_id"> | undefined = byId.get(entry.id) ?? { id: entry.id, name: entry.name, parent_id: null };
    const visited = new Set<string>();
    while (current && !visited.has(current.id)) {
      visited.add(current.id);
      const name = key(current.name);
      for (const prefix of [...(byName.get(name) ?? []), TOPIC_ALIASES[name]]) {
        if (prefix && prefix !== "VAR" && categories.some((category) => category.prefix === prefix)) matches.set(prefix, current.name);
      }
      current = current.parent_id ? byId.get(current.parent_id) : undefined;
    }
  }
  if (matches.size === 1) {
    const [prefix, tag] = [...matches][0];
    return { prefix, tag };
  }
  // Tags from two or more paper areas: propose Other and ask the person to choose.
  return { prefix: "VAR", tag: null, ambiguous: matches.size > 1 };
}
