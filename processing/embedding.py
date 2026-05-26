import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

class EmbeddingPipeline:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.chunks_dir = "data/chunks"
        self.output_dir = "data/embeddings"
        self.index_path = os.path.join(self.output_dir, "products.index")
        self.metadata_path = os.path.join(self.output_dir, "metadata.json")

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

    def build_faiss_index(self, embeddings):
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)
        faiss.normalize_L2(embeddings)
        index.add(embeddings)
        return index

    def create_metadata(self, products):
        metadata = []
        for p in products:
            metadata.append({
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
        return metadata

    def save(self, index, metadata):
        os.makedirs(self.output_dir, exist_ok=True)
        faiss.write_index(index, self.index_path)
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def run(self):
        products = self.load_chunks()
        embeddings = self.create_embeddings(products)
        index = self.build_faiss_index(embeddings)
        metadata = self.create_metadata(products)
        self.save(index, metadata)
        return {
            "total_products": len(products),
            "embedding_dim": embeddings.shape[1],
            "output_dir": self.output_dir,
        }

if __name__ == "__main__":
    pipeline = EmbeddingPipeline()
    result = pipeline.run()
