from __future__ import annotations

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
        self._model = SentenceTransformer(model_name)
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
