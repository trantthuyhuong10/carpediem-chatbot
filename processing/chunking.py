import json
import os
import math

class DataChunker:
    def __init__(self):
        self.source_file = "data/cache/product_details.json"
        self.output_dir = "data/chunks"

    def load_data(self):
        with open(self.source_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def chunk_by_batch(self, data, batch_size=10):
        chunks = []
        for i in range(0, len(data), batch_size):
            chunk = data[i : i + batch_size]
            chunks.append(chunk)
        return chunks

    def chunk_by_category(self, data, category_field="category"):
        categories = {}
        for item in data:
            cat = item.get(category_field, "uncategorized")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        return list(categories.values())

    def save_chunks(self, chunks, prefix="chunk"):
        os.makedirs(self.output_dir, exist_ok=True)
        for i, chunk in enumerate(chunks, 1):
            filename = f"{prefix}_{i:02d}.json"
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(chunk, f, ensure_ascii=False, indent=2)

    def run(self, mode="batch", batch_size=10, category_field="category"):
        data = self.load_data()

        if mode == "batch":
            chunks = self.chunk_by_batch(data, batch_size)
        elif mode == "category":
            chunks = self.chunk_by_category(data, category_field)
        else:
            raise ValueError("mode must be 'batch' or 'category'")

        self.save_chunks(chunks)

        return {
            "total_products": len(data),
            "total_chunks": len(chunks),
            "output_dir": self.output_dir,
        }

if __name__ == "__main__":
    chunker = DataChunker()
    result = chunker.run(mode="batch", batch_size=10)

