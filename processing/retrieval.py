import json
import os
import re
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

class RetrievalSystem:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model_name)
        self.index_path = "data/embeddings/products.index"
        self.metadata_path = "data/embeddings/products_metadata.json"
        self.index = faiss.read_index(self.index_path)
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

    def extract_price_range(self, query):
        numbers = re.findall(r"(\d[\d.]*)\s*(k|K|nghìn|triệu|tr)?", query)
        prices = []
        for num, unit in numbers:
            num = float(num.replace(".", ""))
            if unit.lower() in ["k", "nghìn"]:
                prices.append(num * 1000)
            elif unit.lower() in ["tr", "triệu"]:
                prices.append(num * 1000000)
            else:
                if num < 100:
                    prices.append(num * 1000)
                else:
                    prices.append(num)
        return prices

    def parse_price_from_metadata(self, price_str):
        if not price_str:
            return 0
        cleaned = re.sub(r"[^\d]", "", price_str)
        return int(cleaned) if cleaned else 0

    def filter_by_price(self, results, min_price=None, max_price=None):
        filtered = []
        for r in results:
            price = self.parse_price_from_metadata(r["price"])
            if min_price and price < min_price:
                continue
            if max_price and price > max_price:
                continue
            filtered.append(r)
        return filtered

    def semantic_search(self, query, top_k=5):
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_embedding)
        scores, indices = self.index.search(query_embedding, min(top_k * 2, len(self.metadata)))
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            item = self.metadata[idx].copy()
            item["score"] = float(scores[0][i])
            results.append(item)
        return results

    def search(self, query, top_k=5, min_price=None, max_price=None):
        results = self.semantic_search(query, top_k)
        price_range = self.extract_price_range(query)
        if not min_price and price_range:
            if len(price_range) == 1:
                max_price = price_range[0]
            elif len(price_range) >= 2:
                min_price, max_price = min(price_range), max(price_range)
        if min_price or max_price:
            results = self.filter_by_price(results, min_price, max_price)
        results = sorted(results, key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def recommend_by_occasion(self, occasion, top_k=5):
        occasion_keywords = {
            "sinh nhật": "sinh nhật quà tặng birthday",
            "valentine": "valentine tình yêu romantic couple",
            "8/3": "phụ nữ mẹ vợ bạn gái",
            "20/10": "phụ nữ việt nam mẹ vợ",
            "cưới": "cưới hôn lễ wedding sang trọng cao cấp",
            "tân gia": "tân gia nhà mới chuyển nhà",
            "giáng sinh": "giáng sinh noel christmas",
            "tết": "tết nguyên đán xuân năm mới",
        }
        expanded_query = occasion
        for key, value in occasion_keywords.items():
            if key in occasion.lower():
                expanded_query = f"{occasion} {value}"
                break
        return self.search(expanded_query, top_k)

    def recommend_by_budget(self, budget, top_k=5):
        price_range = self.extract_price_range(budget)
        if not price_range:
            return self.search(budget, top_k)
        if len(price_range) == 1:
            max_price = price_range[0]
            min_price = max_price * 0.5
        else:
            min_price, max_price = min(price_range), max(price_range)
        results = self.semantic_search("sản phẩm quà tặng", top_k * 3)
        return self.filter_by_price(results, min_price, max_price)[:top_k]

    def get_product_link(self, product):
        url = product.get("url", "")
        if not url.startswith("http"):
            url = f"https://carpediem.vn{url}"
        return url

    def format_product(self, product):
        name = product.get("name", "")
        original_price = product.get("original_price", "")
        price = product.get("price", "")
        discount = product.get("discount", "")
        url = self.get_product_link(product)
        images = product.get("images", [])
        image_url = images[0] if images else ""
        return {
            "name": name,
            "original_price": original_price,
            "price": price,
            "discount": discount,
            "url": url,
            "image": image_url,
            "score": product.get("score", 0),
        }

    def query(self, user_input, top_k=5, mode="auto"):
        user_input = user_input.strip()
        if mode == "occasion" or any(k in user_input.lower() for k in ["sinh nhật", "valentine", "8/3", "20/10", "cưới", "tân gia", "giáng sinh", "tết"]):
            results = self.recommend_by_occasion(user_input, top_k)
        elif mode == "budget" or any(k in user_input.lower() for k in ["dưới", "trên", "khoảng", "từ", "đến", "ngân sách", "budget"]):
            results = self.recommend_by_budget(user_input, top_k)
        else:
            results = self.search(user_input, top_k)
        return [self.format_product(p) for p in results]


if __name__ == "__main__":
    retrieval = RetrievalSystem()

    while True: 
        query = input("User: ")
        if query in ["exit", "quit"]:
            break
        results = retrieval.query(query, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['name']}")
            print(f"     Price: {r['price']}")
            print(f"     URL: {r['url']}")
