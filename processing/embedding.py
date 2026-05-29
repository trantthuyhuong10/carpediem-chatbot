import json
import os
import sys
import numpy as np
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.vector_store import VectorStore, VECTOR_SIZE


class EmbeddingPipeline:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.chunks_dir = "data/chunks"
        self.store = VectorStore()

    def load_chunks(self):
        all_products = []
        for filename in sorted(os.listdir(self.chunks_dir)):
            if filename.endswith(".json"):
                filepath = os.path.join(self.chunks_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    chunk = json.load(f)
                    all_products.extend(chunk)
        return all_products

    def prepare_text(self, product):
        name = product.get("name", "")
        collection_name = product.get("collection_name", "")
        description = product.get("description", "")
        price = product.get("price", "")
        text = f"{name} {description} {price}".strip()
        return text

    def create_embeddings(self, products):
        texts = [self.prepare_text(p) for p in products]
        embeddings = self.model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        return embeddings

    def create_payloads(self, products):
        payloads = []
        for p in products:
            payloads.append({
                "collection_id": p.get("collection_id", ""),
                "collection_name": p.get("collection_name", ""),
                "collection_url": p.get("collection_url", ""),
                "name": p.get("name", ""),
                "url": p.get("url", ""),
                "price": p.get("price", ""),
                "description": p.get("description", ""),
                "images": p.get("images", []),
                "status": p.get("status", ""),
            })
        return payloads

    def run(self):
        products = self.load_chunks()
        if not self.store.available:
            return {"total_products": 0, "error": "Qdrant not available"}

        self.store.delete_collection()
        self.store._ensure_collection()
        embeddings = self.create_embeddings(products)
        payloads = self.create_payloads(products)
        self.store.upsert(embeddings, payloads)

        return {
            "total_products": len(products),
            "embedding_dim": embeddings.shape[1],
            "vector_store": "qdrant",
        }


if __name__ == "__main__":
    pipeline = EmbeddingPipeline()
    result = pipeline.run()
