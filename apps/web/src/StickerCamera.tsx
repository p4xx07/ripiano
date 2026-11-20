import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { Button, Modal } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/StickerCamera";

/** The browser's built-in QR reader (Chrome on Android, Edge, Samsung Internet; not iOS Safari). */
type BarcodeDetectorLike = { detect(source: CanvasImageSource): Promise<{ rawValue: string }[]> };
type BarcodeDetectorClass = {
  new (options?: { formats: string[] }): BarcodeDetectorLike;
  getSupportedFormats?: () => Promise<string[]>;
};

function detectorClass(): BarcodeDetectorClass | null {
  if (typeof window === "undefined") return null;
  const found = (window as unknown as { BarcodeDetector?: BarcodeDetectorClass }).BarcodeDetector;
  return found && typeof navigator.mediaDevices?.getUserMedia === "function" ? found : null;
}

/** True once it is known that this browser can read QR codes from the camera. */
export function useCameraQrSupport(): boolean {
  const [supported, setSupported] = useState(false);
  useEffect(() => {
    const Detector = detectorClass();
    if (!Detector) return;
    let active = true;
    Promise.resolve(Detector.getSupportedFormats ? Detector.getSupportedFormats() : ["qr_code"])
      .then((formats) => { if (active && formats.includes("qr_code")) setSupported(true); })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);
  return supported;
}

/**
 * A small dialog with the rear camera: reads the first QR code it sees and hands its text back. The camera is
 * stopped when a code is read, when the dialog closes, and when it is unmounted.
 */
export default function StickerCamera({ onCode, onClose }: { onCode: (text: string) => void; onClose: () => void }) {
  const m = useMessages(messages);
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const codeRef = useRef(onCode);
  codeRef.current = onCode;

  useEffect(() => {
    const Detector = detectorClass();
    if (!Detector) {
      setError(m.unsupported);
      return;
    }
    let stream: MediaStream | null = null;
    let timer: number | null = null;
    let stopped = false;
    const stop = () => {
      stopped = true;
      if (timer !== null) window.clearTimeout(timer);
      stream?.getTracks().forEach((track) => track.stop());
      if (video.current) video.current.srcObject = null;
    };
    const detector = new Detector({ formats: ["qr_code"] });
    async function scan() {
      if (stopped || !video.current) return;
      try {
        const codes = await detector.detect(video.current);
        const text = codes.find((code) => code.rawValue.trim())?.rawValue;
        if (text && !stopped) {
          stop();
          codeRef.current(text);
          return;
        }
      } catch {
        // The video has no frame yet: try again shortly.
      }
      if (!stopped) timer = window.setTimeout(() => void scan(), 250);
    }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false })
      .then(async (media) => {
        if (stopped) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = media;
        if (video.current) {
          video.current.srcObject = media;
          await video.current.play().catch(() => undefined);
        }
        setReady(true);
        void scan();
      })
      .catch((cause: unknown) => {
        const name = cause instanceof DOMException ? cause.name : "";
        setError(name === "NotAllowedError" || name === "SecurityError" ? m.denied
          : name === "NotFoundError" || name === "OverconstrainedError" ? m.noCamera : m.cameraError);
      });
    return stop;
  }, [m]);

  return (
    <Modal titleId="sticker-camera-title" onClose={onClose} panelClassName="add-modal sticker-camera">
      <button type="button" className="modal-close" onClick={onClose} aria-label={m.close}><X size={20} aria-hidden="true" /></button>
      <h2 id="sticker-camera-title">{m.heading}</h2>
      {error
        ? <p className="inline-error" role="alert">{error}</p>
        : <p role="status">{ready ? m.pointCamera : m.starting}</p>}
      {!error && <video ref={video} muted playsInline aria-label={m.preview} />}
      <Button type="button" variant="secondary" onClick={onClose}>{error ? m.typeInstead : m.cancel}</Button>
    </Modal>
  );
}
