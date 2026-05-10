"""Optional sentence-transformer embedder for bio similarity.

Lazy-loaded so the heavy `sentence-transformers` / `torch` / `transformers`
stack is only imported when ``--use-embeddings`` is set.

We do three things at module load time to defuse three recurring failure
modes when running inside an asyncio event loop (CLI's ``asyncio.run`` *or*
the Textual TUI's worker loop):

1. **tqdm progress bar inside transformers**. ``transformers`` wraps weight
   loading in ``tqdm(...)``. tqdm's class-level lock is a
   ``multiprocessing.RLock`` by default, and constructing one triggers a
   spawn of the multiprocessing ``resource_tracker`` subprocess. On Python
   3.14, that spawn validates the parent's inheritable fds and fails with
   ``ValueError: bad value(s) in fds_to_keep`` whenever there are open
   asyncio internals (selfpipe, signal pipe) — which is always, inside any
   event loop. Replacing tqdm's lock with a ``threading.RLock`` keeps it
   inside one process and skips the multiprocessing dance entirely.
2. **HuggingFace tokenizers thread-then-fork**. The Rust tokenizer pool
   starts threads on first use; a subsequent ``fork()`` (HF Hub helpers,
   torch data loaders) then warns / aborts. ``TOKENIZERS_PARALLELISM=false``
   forces single-threaded tokenization so there's nothing to break.
3. **HF Hub telemetry / progress bars** can hang on restricted networks and
   add noise to the TUI. Disabled via env var.

Env vars and the tqdm lock swap are only effective if set / installed before
the relevant library imports, so we do both at the top of this module.
"""
from __future__ import annotations

import os
import threading

# Must be set before any sentence-transformers / transformers import. Use
# setdefault so we never override a value the caller set deliberately.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

# Replace tqdm's default multiprocessing lock with a threading lock so
# `transformers`' weight-loading progress bar doesn't spawn the
# multiprocessing resource_tracker subprocess (which fails inside any
# asyncio event loop on Python 3.14 — see module docstring).
try:
    import tqdm as _tqdm

    _tqdm.tqdm.set_lock(threading.RLock())
except Exception:
    # tqdm not installed yet, or set_lock signature changed — the explicit
    # ValueError handler in __init__ below still gives a clear message.
    pass

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceTransformerEmbedder:
    """Lazy-loaded sentence-transformers embedder. Requires `aliasgraph[ml]` extra."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise SystemExit(
                "sentence-transformers is not installed. "
                "Reinstall with `uv pip install -e '.[ml]'` to use --use-embeddings."
            ) from e
        try:
            self._model = SentenceTransformer(model_name)
        except ValueError as e:
            # Most commonly: ``bad value(s) in fds_to_keep`` from a fork
            # attempted while httpx async sockets are open. Surface it with a
            # human-readable hint instead of the raw stdlib message.
            if "fds_to_keep" in str(e):
                raise SystemExit(
                    "sentence-transformers failed to load due to a fork/subprocess "
                    "conflict (open async sockets at the time of fork). Re-run with "
                    "TOKENIZERS_PARALLELISM=false in the environment, or download the "
                    "model once outside the pipeline first:\n"
                    f"    python -c \"from sentence_transformers import SentenceTransformer; "
                    f"SentenceTransformer('{model_name}')\""
                ) from e
            raise
        self._cache: dict[str, list[float]] = {}

    def _encode(self, text: str) -> list[float]:
        if text not in self._cache:
            vec = self._model.encode(text, normalize_embeddings=True)
            self._cache[text] = vec.tolist() if hasattr(vec, "tolist") else list(vec)
        return self._cache[text]

    def similarity(self, a: str | None, b: str | None) -> float | None:
        if not a or not b:
            return None
        va = self._encode(a)
        vb = self._encode(b)
        # vectors are already normalized; dot product == cosine similarity.
        s = sum(x * y for x, y in zip(va, vb, strict=True))
        return max(0.0, min(1.0, float(s)))
