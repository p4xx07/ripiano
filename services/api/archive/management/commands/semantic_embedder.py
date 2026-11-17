"""Optional NAS embedding service for semantic search (Compose profile "semantic").

Speaks Ollama's `POST /api/embed` contract ({"model", "input", "keep_alive"} -> {"embeddings"}), so
Ripiano uses one code path for this service and for Ollama on another computer.

- Packages (fastembed, onnxruntime, …) are not in the Ripiano image. On first start they are installed
  into RIPIANO_EMBEDDER_DIR from semantic-requirements.txt, with every file's hash verified.
- The model loads on the first request and unloads after its keep_alive expires ("10m" by default;
  -1 keeps it loaded). The process runs at low CPU priority with RIPIANO_EMBEDDER_THREADS threads.
- It listens only on the private Compose network; Compose publishes no port for it.
"""

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)
ALLOWED_MODELS = {
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "intfloat/multilingual-e5-large",
}
MAX_INPUTS = 64
MAX_CHARS = 8000
MAX_BODY = 2 * 1024 * 1024
DEFAULT_KEEP_ALIVE = 600.0


def parse_keep_alive(value):
    """Seconds to keep the model after a request; None means forever. Accepts Ollama's forms: -1, 0, 300, "10m", "1h"."""
    if value is None:
        return DEFAULT_KEEP_ALIVE
    if isinstance(value, bool):
        raise ValueError("keep_alive must be a number or a duration")
    if isinstance(value, (int, float)):
        return None if value < 0 else float(value)
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*([smh]?)\s*", str(value))
    if not match:
        raise ValueError("keep_alive must be a number or a duration like 10m")
    amount = float(match[1])
    if amount < 0:
        return None
    return amount * {"": 1, "s": 1, "m": 60, "h": 3600}[match[2]]


class ModelHolder:
    """Loads one model on demand and unloads it after the requested idle time."""

    def __init__(self, cache_dir, threads, loader=None):
        self.cache_dir, self.threads = cache_dir, threads
        self.loader = loader or self._load
        self.lock = threading.Lock()
        self.model, self.name, self.expires = None, None, None

    def _load(self, name):
        from fastembed import TextEmbedding

        return TextEmbedding(name, cache_dir=str(self.cache_dir), threads=self.threads)

    def embed(self, name, texts, keep_alive):
        with self.lock:
            if self.name != name:
                self.model, self.name = None, None
                logger.info("Loading embedding model %s", name)
                self.model, self.name = self.loader(name), name
            vectors = [[float(value) for value in vector] for vector in self.model.embed(texts, batch_size=8)]
            self.expires = None if keep_alive is None else time.monotonic() + keep_alive
            if keep_alive == 0:
                self._unload()
            return vectors

    def _unload(self):
        if self.model is not None:
            logger.info("Unloading embedding model %s", self.name)
        self.model, self.name, self.expires = None, None, None
        import gc

        gc.collect()

    def unload_if_idle(self):
        with self.lock:
            if self.model is not None and self.expires is not None and time.monotonic() >= self.expires:
                self._unload()


def make_handler(holder):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RipianoEmbedder"

        def log_message(self, format, *args):  # noqa: A002 - keep request logs out of the console
            pass

        def _send(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/healthz":
                self._send(200, {"ok": True, "loaded": holder.name})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/embed":
                return self._send(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 < length <= MAX_BODY:
                return self._send(413, {"error": "request too large"})
            try:
                body = json.loads(self.rfile.read(length))
                name = body.get("model")
                inputs = body.get("input")
                inputs = [inputs] if isinstance(inputs, str) else inputs
                keep_alive = parse_keep_alive(body.get("keep_alive"))
            except (ValueError, AttributeError):
                return self._send(400, {"error": "invalid request"})
            if name not in ALLOWED_MODELS:
                return self._send(400, {"error": f"model not offered here; use one of {sorted(ALLOWED_MODELS)}"})
            if not isinstance(inputs, list) or not 0 < len(inputs) <= MAX_INPUTS or not all(isinstance(item, str) and len(item) <= MAX_CHARS for item in inputs):
                return self._send(400, {"error": f"input must be 1-{MAX_INPUTS} texts of up to {MAX_CHARS} characters"})
            try:
                vectors = holder.embed(name, inputs, keep_alive)
            except Exception:  # noqa: BLE001 - report without internals; details go to the log
                logger.exception("Embedding failed")
                return self._send(500, {"error": "embedding failed; see the embedder log"})
            self._send(200, {"model": name, "embeddings": vectors})

    return Handler


def ensure_packages(target, requirements):
    """Make fastembed importable, installing the hash-pinned packages into ``target`` once."""
    sys.path.insert(0, str(target))
    try:
        import fastembed  # noqa: F401
        return
    except ImportError:
        pass
    logger.info("Installing semantic search packages into %s (first start only)", target)
    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["uv", "pip", "install", "--quiet", "--require-hashes", "--no-deps", "--python", sys.executable,
         "--target", str(target), "-r", str(requirements)],
        capture_output=True, text=True, timeout=1800,
    )
    if result.returncode != 0:
        raise CommandError(f"Installing semantic search packages failed: {result.stderr.strip()[-500:]}")
    import importlib

    importlib.invalidate_caches()


class Command(BaseCommand):
    help = "Run the optional NAS embedding service used by semantic search"

    def handle(self, *args, **options):
        base = Path(os.environ.get("RIPIANO_EMBEDDER_DIR", "/models"))
        try:
            threads = max(1, int(os.environ.get("RIPIANO_EMBEDDER_THREADS", "1")))
            port = int(os.environ.get("RIPIANO_EMBEDDER_PORT", "8002"))
        except ValueError as exc:
            raise CommandError("RIPIANO_EMBEDDER_THREADS and RIPIANO_EMBEDDER_PORT must be whole numbers") from exc
        try:
            os.nice(10)  # indexing must never slow down the archive itself
        except OSError:
            pass
        ensure_packages(base / "python", Path(__file__).resolve().parents[3] / "semantic-requirements.txt")
        holder = ModelHolder(base / "cache", threads)

        def reaper():
            while True:
                time.sleep(30)
                holder.unload_if_idle()

        threading.Thread(target=reaper, daemon=True).start()
        server = HTTPServer(("0.0.0.0", port), make_handler(holder))  # noqa: S104 - private Compose network only
        self.stdout.write(f"Embedder listening on port {port} with {threads} thread(s)")
        server.serve_forever()
