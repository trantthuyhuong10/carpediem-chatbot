import json
import os
import re
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from typing import List, Dict
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

class GraphRAG:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model_name)
        self.index = faiss.read_index("data/embeddings/products.index")
        with open("data/embeddings/products_metadata.json", "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        )

    def close(self):
        self.driver.close()

    def semantic_search(self, query, top_k=5):
        emb = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(emb)
        scores, indices = self.index.search(emb, min(top_k * 2, len(self.metadata)))
        results = []
        for i, idx in enumerate(indices[0]):
            if 0 <= idx < len(self.metadata):
                item = self.metadata[idx].copy()
                item["score"] = float(scores[0][i])
                results.append(item)
        return results

    def graph_filter_by_category(self, names, category):
        with self.driver.session() as s:
            return [r["name"] for r in s.run("""
                MATCH (p:Product)-[:BELONGS_TO]->(c:Category {name:$cat})
                WHERE p.name IN $names RETURN p.name AS name
            """, cat=category, names=names)]

    def graph_filter_by_price(self, names, min_p, max_p):
        with self.driver.session() as s:
            return [r["name"] for r in s.run("""
                MATCH (p:Product) WHERE p.name IN $names AND p.price >= $min AND p.price <= $max
                RETURN p.name AS name ORDER BY p.price
            """, names=names, min=min_p, max=max_p)]

    def graph_expand(self, names):
        with self.driver.session() as s:
            return [r.data() for r in s.run("""
                MATCH (p:Product) WHERE p.name IN $names
                OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
                OPTIONAL MATCH (p)-[:PART_OF]->(col:Collection)
                OPTIONAL MATCH (p)-[:HAS_ENTITY]->(e:Entity)
                RETURN p.name AS name, p.price AS price, p.url AS url, p.description AS description,
                    collect(DISTINCT c.name) AS categories, collect(DISTINCT col.name) AS collections,
                    collect(DISTINCT {name: e.name, type: e.type}) AS entities
            """, names=names)]

    def graph_find_similar(self, name, top_k=3):
        with self.driver.session() as s:
            return [r.data() for r in s.run("""
                MATCH (p1:Product {name:$name})-[r:SIMILAR_TO]-(p2:Product)
                OPTIONAL MATCH (p2)-[:BELONGS_TO]->(c:Category)
                RETURN p2.name AS name, p2.price AS price, p2.url AS url,
                    r.similarity AS sim, collect(DISTINCT c.name) AS categories
                ORDER BY r.similarity DESC LIMIT $limit
            """, name=name, limit=top_k)]

    def extract_price_range(self, query):
        numbers = re.findall(r"(\d[\d.]*)\s*(k|K|nghìn|triệu|tr)?", query)
        prices = []
        for num, unit in numbers:
            n = float(num.replace(".", ""))
            if unit.lower() in ["k", "nghìn"]:
                prices.append(n * 1000)
            elif unit.lower() in ["tr", "triệu"]:
                prices.append(n * 1000000)
            else:
                prices.append(n * 1000 if n < 100 else n)
        return prices

    def graph_vector_hybrid_search(self, query, top_k=5):
        results = self.semantic_search(query, top_k * 2)
        names = [r["name"] for r in results]

        price_range = self.extract_price_range(query)
        if price_range:
            min_p = int(min(price_range)) if len(price_range) >= 2 else 0
            max_p = int(max(price_range)) if len(price_range) >= 2 else int(price_range[0])
            filtered = self.graph_filter_by_price(names, min_p, max_p)
            results = [r for r in results if r["name"] in filtered]
            names = filtered

        cat_map = {"nen": "Nến thơm", "nến": "Nến thơm", "tinh dầu": "Tinh dầu",
                    "gift": "Giftset", "set quà": "Giftset", "đá thơm": "Khuếch hương"}
        for kw, cat in cat_map.items():
            if kw in query.lower():
                cat_filtered = self.graph_filter_by_category(names, cat)
                if cat_filtered:
                    results = [r for r in results if r["name"] in cat_filtered]
                break

        enriched = {e["name"]: e for e in self.graph_expand([r["name"] for r in results])}
        for r in results:
            e = enriched.get(r["name"], {})
            r["categories"] = e.get("categories", [])
            r["collections"] = e.get("collections", [])
            r["entities"] = e.get("entities", [])
        return results[:top_k]

    def recommend_by_occasion(self, occasion, top_k=5):
        kw = {
            "sinh nhật": "sinh nhật quà tặng birthday",
            "valentine": "valentine tình yêu romantic",
            "8/3": "phụ nữ mẹ vợ bạn gái",
            "20/10": "phụ nữ việt nam",
            "cưới": "cưới hôn lễ wedding sang trọng",
            "tân gia": "tân gia nhà mới",
            "giáng sinh": "giáng sinh noel christmas",
            "tết": "tết nguyên đán xuân",
        }
        expanded = occasion
        for key, val in kw.items():
            if key in occasion.lower():
                expanded = f"{occasion} {val}"
                break
        return self.graph_vector_hybrid_search(expanded, top_k)

    def recommend_by_budget(self, budget, top_k=5):
        price_range = self.extract_price_range(budget)
        if not price_range:
            return self.graph_vector_hybrid_search(budget, top_k)
        if len(price_range) == 1:
            max_p, min_p = int(price_range[0]), int(price_range[0] * 0.5)
        else:
            min_p, max_p = int(min(price_range)), int(max(price_range))
        results = self.semantic_search("sản phẩm quà tặng", top_k * 3)
        names = [r["name"] for r in results]
        filtered = self.graph_filter_by_price(names, min_p, max_p)
        results = [r for r in results if r["name"] in filtered]
        enriched = {e["name"]: e for e in self.graph_expand([r["name"] for r in results])}
        for r in results:
            e = enriched.get(r["name"], {})
            r["categories"] = e.get("categories", [])
            r["collections"] = e.get("collections", [])
        return results[:top_k]

    def find_similar_products(self, name, top_k=5):
        similar = self.graph_find_similar(name, top_k)
        enriched = {e["name"]: e for e in self.graph_expand([r["name"] for r in similar])}
        final = []
        for r in similar:
            e = enriched.get(r["name"], {})
            final.append({
                "name": r["name"], "price": r["price"], "url": r["url"],
                "score": r.get("sim", 0), "categories": e.get("categories", []),
                "collections": e.get("collections", []),
            })
        return [self.format_product(p) for p in final]

    def query(self, user_input, top_k=5, mode="auto"):
        user_input = user_input.strip()
        if mode == "occasion" or any(k in user_input.lower() for k in ["sinh nhật", "valentine", "8/3", "20/10", "cưới", "tân gia", "giáng sinh", "tết"]):
            results = self.recommend_by_occasion(user_input, top_k)
        elif mode == "budget" or any(k in user_input.lower() for k in ["dưới", "trên", "khoảng", "từ", "đến", "ngân sách", "budget"]):
            results = self.recommend_by_budget(user_input, top_k)
        else:
            results = self.graph_vector_hybrid_search(user_input, top_k)
        return [self.format_product(p) for p in results]

    def format_product(self, p):
        url = p.get("url", "")
        if not url.startswith("http"):
            url = f"https://carpediem.vn{url}"
        images = p.get("images", [])
        return {
            "name": p.get("name", ""),
            "original_price": p.get("original_price", ""),
            "price": p.get("price", ""),
            "discount": p.get("discount", ""),
            "url": url,
            "image": images[0] if images else "",
            "score": p.get("score", 0),
            "categories": p.get("categories", []),
            "collections": p.get("collections", []),
            "entities": p.get("entities", []),
            "description": p.get("description", ""),
        }

    def get_product_context(self, results):
        if not results:
            return "Không tìm thấy sản phẩm phù hợp."
        lines = []
        for i, p in enumerate(results, 1):
            entities = ", ".join(e["name"] for e in p.get("entities", [])[:5])
            lines.append(
                f"{i}. {p['name']} - Giá: {p.get('price', 'Liên hệ')}\n"
                f"   Link: {p['url']}\n"
                f"   Danh mục: {', '.join(p.get('categories', []))}\n"
                f"   Điểm nổi bật: {entities}"
            )
        return "\n\n".join(lines)

if __name__ == "__main__":
    rag = GraphRAG()
    print("Type 'exit' to quit\n")
    while True:
        q = input("User: ").strip()
        if q in ["exit", "quit"]:
            break
        if q.startswith("similar "):
            for i, r in enumerate(rag.find_similar_products(q[8:].strip(), 5), 1):
                print(f"  {i}. {r['name']} | {r['price']}")
        else:
            for i, r in enumerate(rag.query(q, 3), 1):
                print(f"  {i}. {r['name']} | {r['price']}")
    rag.close()
