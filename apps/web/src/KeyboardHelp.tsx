import { X } from "lucide-react";
import { useMessages } from "./i18n";
import messages from "./locales/KeyboardHelp";
import { Modal } from "./ui";

export const GO_TO_KEYS = ["l", "i", "a", "t", "p", "o", "s", "w", "r"] as const;

/** The list of keyboard shortcuts, opened with "?". */
export default function KeyboardHelp({ onClose }: { onClose: () => void }) {
  const m = useMessages(messages);
  const row = (keys: string[], label: string) => (
    <div className="shortcut-row" key={label}>
      <dt>{keys.map((key, index) => <span key={key + index}>{index > 0 && <small> {m.then} </small>}<kbd>{key}</kbd></span>)}</dt>
      <dd>{label}</dd>
    </div>
  );
  return (
    <Modal titleId="shortcuts-title" onClose={onClose} panelClassName="shortcuts-dialog">
      <div className="shortcuts-head">
        <h2 id="shortcuts-title">{m.title}</h2>
        <button type="button" className="tag-icon-button" aria-label={m.close} onClick={onClose}><X size={18} /></button>
      </div>
      <p>{m.intro}</p>
      <h3>{m.general}</h3>
      <dl>
        {row(["/"], m.search)}
        {row(["n"], m.add)}
        {row(["?"], m.help)}
        {row(["Esc"], m.closeDialog)}
        {GO_TO_KEYS.map((key) => row(["g", key], m.goTo(key)))}
      </dl>
      <h3>{m.library}</h3>
      <dl>
        {row(["Esc"], m.leaveSearch)}
        {row(["j"], m.next)}
        {row(["k"], m.previous)}
        {row([m.enterKey], m.open)}
      </dl>
    </Modal>
  );
}
