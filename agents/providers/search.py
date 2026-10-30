"""Policy RAG: local embeddings + FAISS over `policy/*.md` (default) or Azure AI Search (prod)."""

from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

from agents.providers.base import PolicyChunk
from core.settings import get_settings

_HEADING = re.compile(r"^###\s+§(\d+\.\d+)\s+(.*)$")


def load_policy_chunks() -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    for path in sorted(get_settings().policy_dir.glob("*.md")):
        current: PolicyChunk | None = None
        for line in path.read_text().splitlines():
            m = _HEADING.match(line)
            if m:
                if current:
                    chunks.append(current)
                current = PolicyChunk(section=m.group(1), title=m.group(2).strip(), text="")
            elif line.startswith("## ") and current:
                chunks.append(current)
                current = None
            elif current is not None:
                current.text += line + "\n"
        if current:
            chunks.append(current)
    for c in chunks:
        c.text = c.text.strip()
    return chunks


class _Embedder:
    def __init__(self, corpus: list[str]) -> None:
        self.kind = "tfidf"
        if get_settings().embeddings == "sentence_transformers":
            try:
                from sentence_transformers import SentenceTransformer

                self._st = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                self.kind = "sentence_transformers"
                return
            except Exception:  # model or package unavailable offline -> TF-IDF
                pass
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._tfidf = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english").fit(corpus)

    def encode(self, texts: list[str]) -> np.ndarray:
        if self.kind == "sentence_transformers":
            v = np.asarray(self._st.encode(texts), dtype="float32")
        else:
            v = self._tfidf.transform(texts).toarray().astype("float32")
        norms = np.linalg.norm(v, axis=1, keepdims=True)
        return v / np.where(norms == 0, 1, norms)


class LocalPolicySearch:
    """Embeddings + FAISS inner-product index (cosine on normalised vectors). Falls back to numpy."""

    def __init__(self) -> None:
        self.chunks = load_policy_chunks()
        corpus = [f"{c.title}. {c.text}" for c in self.chunks]
        self.embedder = _Embedder(corpus)
        self.vectors = self.embedder.encode(corpus)
        try:
            import faiss

            self.index = faiss.IndexFlatIP(self.vectors.shape[1])
            self.index.add(self.vectors)
        except ImportError:
            self.index = None

    def search(self, query: str, k: int = 4) -> list[PolicyChunk]:
        q = self.embedder.encode([query])
        if self.index is not None:
            scores, idx = self.index.search(q, k)
            pairs = zip(idx[0], scores[0])
        else:
            sims = self.vectors @ q[0]
            top = np.argsort(-sims)[:k]
            pairs = zip(top, sims[top])
        out = []
        for i, sc in pairs:
            if i < 0:
                continue
            c = self.chunks[int(i)]
            out.append(PolicyChunk(c.section, c.title, c.text, round(float(sc), 4)))
        return out

    def get(self, section: str) -> PolicyChunk | None:
        return next((c for c in self.chunks if c.section == section), None)


class AzureAISearch:  # pragma: no cover - production adapter
    """Azure AI Search hybrid (BM25 + vector) over the indexed policy corpus."""

    def __init__(self) -> None:
        import os

        self.endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
        if not self.endpoint:
            raise RuntimeError("AZURE_SEARCH_ENDPOINT not set; use UP_SEARCH_PROVIDER=local")
        self._local = LocalPolicySearch()  # section lookup stays local (policy is versioned in git)

    def search(self, query: str, k: int = 4) -> list[PolicyChunk]:
        raise NotImplementedError("Wire azure-search-documents SearchClient(hybrid query) here")

    def get(self, section: str) -> PolicyChunk | None:
        return self._local.get(section)


@lru_cache
def get_search() -> LocalPolicySearch:
    if get_settings().search_provider == "azure_ai_search":
        return AzureAISearch()  # type: ignore[return-value]
    return LocalPolicySearch()
