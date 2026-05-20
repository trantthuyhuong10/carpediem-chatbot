import json
import os

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

    def save_chunks(self, chunks, prefix="chunk"):
        os.makedirs(self.output_dir, exist_ok=True)
        for i, chunk in enumerate(chunks, 1):
            filename = f"{prefix}_{i:02d}.json"
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(chunk, f, ensure_ascii=False, indent=2)

    def run(self, batch_size=10):
        data = self.load_data()
        chunks = self.chunk_by_batch(data, batch_size)
        self.save_chunks(chunks)
        return {
            "total_products": len(data),
            "total_chunks": len(chunks),
            "output_dir": self.output_dir,
        }

if __name__ == "__main__":
    chunker = DataChunker()
    result = chunker.run(batch_size=10)

