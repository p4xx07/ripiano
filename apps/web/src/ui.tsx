import { ComponentPropsWithoutRef, ReactNode, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

type ButtonProps = ComponentPropsWithoutRef<"button"> & {
  variant?: "primary" | "secondary";
};

export function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  return <button className={`button button-${variant} ${className}`.trim()} {...props} />;
}

export function Field({ label, hint, className = "", children }: {
  label: string;
  hint?: string;
  className?: string;
  children: ReactNode;
}) {
  return <label className={className}>{label}{hint && <small>{hint}</small>}{children}</label>;
}

type ModalProps = {
  titleId: string;
  onClose: () => void;
  panelClassName: string;
  backdropClassName?: string;
  children: ReactNode;
};

const focusable = "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

export function Modal({ titleId, onClose, panelClassName, backdropClassName = "", children }: ModalProps) {
  const dialog = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const app = document.getElementById("root");
    const wasInert = app?.inert ?? false;
    if (app) app.inert = true;
    dialog.current?.focus();

    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialog.current) return;
      const items = Array.from(dialog.current.querySelectorAll<HTMLElement>(focusable))
        .filter((item) => item.tabIndex >= 0 && item.getClientRects().length > 0);
      if (!items.length) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      if (app) app.inert = wasInert;
      previous?.focus();
    };
  }, []);

  return createPortal(
    <div
      className={`modal-backdrop ${backdropClassName}`.trim()}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialog}
        className={panelClassName}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}
