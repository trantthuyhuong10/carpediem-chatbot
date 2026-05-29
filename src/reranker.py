import numpy as np
from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self, model_name="BAAI/bge-reranker-v2-m3"):
        self._available = True
        try:
            self.model = CrossEncoder(model_name)
            print(f"[Reranker] Loaded {model_name}")
        except Exception as e:
            print(f"[Reranker] {model_name} failed: {e}")
            try:
                fallback = "jinaai/jina-reranker-v2-base-multilingual"
                self.model = CrossEncoder(fallback)
                print(f"[Reranker] Fallback to {fallback}")
            except Exception as e2:
                print(f"[Reranker] Fallback also failed: {e2}")
                self._available = False

    @property
    def available(self):
        return self._available

    def rerank(self, query: str, candidates: list, top_k: int = 5) -> list:
        if not self._available or not candidates:
            return candidates[:top_k]
        pairs = [
            (query, f"{c.get('name', '')} {c.get('description', '')}")
            for c in candidates
        ]
        try:
            scores = self.model.predict(pairs)
        except Exception as e:
            print(f"[Reranker] Predict failed: {e}")
            return candidates[:top_k]
        scored = list(zip(candidates, scores))
        scored.sort(key=lambda x: float(x[1]), reverse=True)
        result = scored[:top_k]
        for c, s in result:
            c["score"] = float(s)
        return [c for c, _ in result]
