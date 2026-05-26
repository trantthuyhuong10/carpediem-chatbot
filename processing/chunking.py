import json
import os

class DataChunker:
    def __init__(self):
        self.source_file = "data/cache/merged_collection_products.json"
        self.output_dir = "data/chunks"

    def load_data(self):
        with open(self.source_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def flatten_products(self, data):
        products = []
        for collection in data.get("collections", []):
            collection_id = collection.get("id")
            collection_name = collection.get("name")
            collection_url = collection.get("url")
            for product in collection.get("products", []):
                flattened = {
                    "collection_id": collection_id,
                    "collection_name": collection_name,
                    "collection_url": collection_url,
                    "name": product.get("name", ""),
                    "url": product.get("url", ""),
                    "price": product.get("price", ""),
                    "description": product.get("description", ""),
                    "images": product.get("images", []),
                    "status": product.get("status", ""),
                }
                products.append(flattened)
        return products

    def chunk_by_batch(self, data, batch_size=10):
        chunks = []
        for i in range(0, len(data), batch_size):
            chunk = data[i : i + batch_size]
            chunks.append(chunk)
        return chunks

    def save_chunks(self, chunks, prefix="chunk"):
        os.makedirs(self.output_dir, exist_ok=True)
        for i, chunk in enumerate(chunks, 1):
            filename = f"{prefix}_{i:02d}.json"
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(chunk, f, ensure_ascii=False, indent=2)

    def run(self, batch_size=10):
        data = self.load_data()
        products = self.flatten_products(data)
        chunks = self.chunk_by_batch(products, batch_size)
        self.save_chunks(chunks)
        return {
            "total_products": len(products),
            "total_chunks": len(chunks),
            "output_dir": self.output_dir,
        }

if __name__ == "__main__":
    chunker = DataChunker()
    result = chunker.run(batch_size=10)

