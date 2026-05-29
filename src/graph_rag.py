import json
import os
import sys
import re
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.vector_store import VectorStore
from src.reranker import Reranker

load_dotenv()


class GraphRAG:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model_name)
        self.store = VectorStore()
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        )
        self.reranker = Reranker()

    def close(self):
        self.driver.close()

    def _run_neo4j_query(self, cypher, params=None, default=None):
        if default is None:
            default = []
        try:
            with self.driver.session() as s:
                return [r.data() for r in s.run(cypher, **(params or {}))]
        except (ServiceUnavailable, Exception) as e:
            print(f"[GraphRAG] Neo4j unavailable or query failed: {e}")
            return default

    def semantic_search(self, query, top_k=5):
        if not self.store.available:
            return []
        emb = self.model.encode([query], convert_to_numpy=True)
        results = self.store.search(emb[0], top_k)
        return results

    def sparse_search(self, query, top_k=5):
        if not self.store.available:
            return []
        return self.store.sparse_search(query, top_k)

    @staticmethod
    def _merge_results(dense, sparse):
        seen = {}
        for r in dense + sparse:
            name = r.get("name", "")
            if name:
                if name not in seen or r.get("score", 0) > seen[name].get("score", 0):
                    seen[name] = r
        return list(seen.values())

    def graph_filter_by_category(self, names, category):
        rows = self._run_neo4j_query("""
            MATCH (p:Product)-[:BELONGS_TO]->(c:Category {name:$cat})
            WHERE p.name IN $names RETURN p.name AS name
        """, {"cat": category, "names": names}, default=[])
        return [r["name"] for r in rows]

    def graph_filter_by_price(self, names, min_p, max_p):
        rows = self._run_neo4j_query("""
            MATCH (p:Product) WHERE p.name IN $names AND p.price >= $min AND p.price <= $max
            RETURN p.name AS name ORDER BY p.price
        """, {"names": names, "min": min_p, "max": max_p}, default=[])
        return [r["name"] for r in rows]

    def graph_expand(self, names):
        return self._run_neo4j_query("""
            MATCH (p:Product) WHERE p.name IN $names
            OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
            OPTIONAL MATCH (p)-[:PART_OF]->(col:Collection)
            OPTIONAL MATCH (p)-[:HAS_ENTITY]->(e:Entity)
            RETURN p.name AS name, p.price AS price, p.url AS url, p.description AS description,
                collect(DISTINCT c.name) AS categories, collect(DISTINCT col.name) AS collections,
                [x IN collect(DISTINCT {name: e.name, type: e.type}) WHERE x.name IS NOT NULL] AS entities
        """, {"names": names}, default=[])

    def graph_find_similar(self, name, top_k=3):
        return self._run_neo4j_query("""
            MATCH (p1:Product {name:$name})-[r:SIMILAR_TO]-(p2:Product)
            OPTIONAL MATCH (p2)-[:BELONGS_TO]->(c:Category)
            RETURN p2.name AS name, p2.price AS price, p2.url AS url,
                r.similarity AS sim, collect(DISTINCT c.name) AS categories
            ORDER BY r.similarity DESC LIMIT $limit
        """, {"name": name, "limit": top_k}, default=[])

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
        wide_k = top_k * 3
        dense = self.semantic_search(query, wide_k)
        sparse = self.sparse_search(query, wide_k)
        merged = self._merge_results(dense, sparse)
        if not merged:
            return []

        names = [r["name"] for r in merged]

        price_range = self.extract_price_range(query)
        if price_range:
            min_p = int(min(price_range)) if len(price_range) >= 2 else 0
            max_p = int(max(price_range)) if len(price_range) >= 2 else int(price_range[0])
            filtered = self.graph_filter_by_price(names, min_p, max_p)
            merged = [r for r in merged if r["name"] in filtered]
            names = [r["name"] for r in merged]

        cat_map = {"nen": "Nến thơm", "nến": "Nến thơm", "tinh dầu": "Tinh dầu",
                    "gift": "Giftset", "set quà": "Giftset", "đá thơm": "Khuếch hương"}
        for kw, cat in cat_map.items():
            if kw in query.lower():
                cat_filtered = self.graph_filter_by_category(names, cat)
                if cat_filtered:
                    merged = [r for r in merged if r["name"] in cat_filtered]
                break

        reranked = self.reranker.rerank(query, merged, top_k)
        if not reranked:
            reranked = merged[:top_k]

        enriched = {e["name"]: e for e in self.graph_expand([r["name"] for r in reranked])}
        for r in reranked:
            e = enriched.get(r["name"], {})
            r["categories"] = e.get("categories", [])
            r["collections"] = e.get("collections", [])
            r["entities"] = e.get("entities", [])
        return reranked[:top_k]

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
        if not results:
            return []
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

    def _preprocess_query(self, query):
        cleaned = query.lower()
        filler_patterns = [
            r"cho\s+tôi\s+(biết\s+)?",
            r"tìm\s+giúp\s+(tôi\s+)?",
            r"tìm\s+cho\s+tôi",
            r"thông\s+tin\s+(về\s+)?",
            r"sản\s+phẩm\s+",
            r"mô\s+tả\s+(chi\s+tiết\s+)?(về\s+)?",
            r"đưa\s+ra\s+",
            r"cho\s+mình\s+xem\s+",
            r"mình\s+muốn\s+tìm\s+",
            r"tôi\s+cần\s+tìm\s+",
            r"có\s+(những\s+)?",
            r"gợi\s+ý\s+(cho\s+)?",
            r"cho\s+tôi\s+xem\s+",
            r"hãy\s+(chỉ\s+)?(cho\s+)?(tôi\s+)?(biết\s+)?",
            r"tôi\s+muốn\s+",
            r"tôi\s+đang\s+tìm\s+",
            r"liệt\s+kê\s+(các\s+)?",
            r"cho\s+mình\s+hỏi\s+",
            r"mình\s+cần\s+tìm\s+",
            r"^tìm\s+",
            r"\s+nào\s+(phù\s+hợp|bán\s+chạy|tốt|hay)",
            r"\s+nào\s*$",
            r"\s+phù\s+hợp\s*$",
            r"\s+bán\s+chạy\s*$",
            r"\s+có\s+giá\s+bao\s+nhiêu",
            r"\s+giá\s+bao\s+nhiêu",
            r"\s+giá\s+là\s+bao\s+nhiêu",
            r"\s+rẻ\s+không",
            r"\s+đắt\s+không",
            r"\s+mua\s+ở\s+đâu",
            r"\s+link\s+mua",
            r"\s+review",
            r"\s+đánh\s+giá",
        ]
        for pattern in filler_patterns:
            cleaned = re.sub(pattern, "", cleaned).strip()
        return cleaned if cleaned else query.lower()

    def _format_price(self, price):
        if price is None or price == 0:
            return ""
        if isinstance(price, str):
            return price
        return f"{price:,.0f}".replace(",", ".") + "₫"

    def neo4j_text_search(self, query, top_k=5):
        keywords = [w for w in query.lower().split() if len(w) >= 2]
        if not keywords:
            return []
        conditions = " OR ".join([f"toLower(p.name) CONTAINS toLower(${i})" for i in range(len(keywords))])
        score_expr = " + ".join([f"CASE WHEN toLower(p.name) CONTAINS toLower(${i}) THEN 1 ELSE 0 END" for i in range(len(keywords))])
        params = {str(i): kw for i, kw in enumerate(keywords)}
        params["limit"] = top_k
        results = self._run_neo4j_query(f"""
            MATCH (p:Product) WHERE {conditions}
            OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
            OPTIONAL MATCH (p)-[:PART_OF]->(col:Collection)
            OPTIONAL MATCH (p)-[:HAS_ENTITY]->(e:Entity)
            RETURN p.name AS name, p.price AS price, p.url AS url,
                   p.description AS description, p.original_price AS original_price,
                   p.discount AS discount, p.images AS images,
                   collect(DISTINCT c.name) AS categories,
                   collect(DISTINCT col.name) AS collections,
                   collect(DISTINCT {{name: e.name, type: e.type}}) AS raw_entities,
                   {score_expr} AS match_score
            ORDER BY match_score DESC, p.name LIMIT $limit
        """, params, default=[])
        for r in results:
            r["entities"] = [e for e in r.pop("raw_entities", []) if e.get("name")]
            r["score"] = r.pop("match_score", 0)
            price = r.get("price")
            if isinstance(price, (int, float)):
                r["price"] = self._format_price(price)
            original = r.get("original_price")
            if isinstance(original, (int, float)):
                r["original_price"] = self._format_price(original)
        return results

    def query(self, user_input, top_k=5, mode="auto"):
        user_input = user_input.strip()
        if mode == "occasion" or any(k in user_input.lower() for k in ["sinh nhật", "valentine", "8/3", "20/10", "cưới", "tân gia", "giáng sinh", "tết"]):
            results = self.recommend_by_occasion(user_input, top_k)
        elif mode == "budget" or any(k in user_input.lower() for k in ["dưới", "trên", "khoảng", "từ", "đến", "ngân sách", "budget"]):
            results = self.recommend_by_budget(user_input, top_k)
        else:
            cleaned = self._preprocess_query(user_input)
            search_query = cleaned if cleaned != user_input.lower() else user_input
            try:
                results = self.graph_vector_hybrid_search(search_query, top_k)
                if results:
                    top_name = results[0].get("name", "").lower()
                    keywords = [w for w in search_query.lower().split() if len(w) >= 2]
                    has_match = any(kw in top_name for kw in keywords)
                    if not has_match:
                        results = self.neo4j_text_search(search_query, top_k)
                if not results:
                    results = self.neo4j_text_search(search_query, top_k)
            except (ServiceUnavailable, Exception) as e:
                print(f"[GraphRAG] Neo4j fallback active: {e}")
                results = self.semantic_search(search_query, top_k)
        return [self.format_product(p) for p in results]

    def format_product(self, p):
        url = p.get("url", "")
        if not url.startswith("http"):
            url = f"https://carpediem.vn{url}"
        images = p.get("images", [])
        return {
            "name": p.get("name", ""),
            "price": p.get("price", ""),
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
            entities = [e["name"] for e in p.get("entities", [])[:5] if e.get("name")]
            entities_str = ", ".join(entities) if entities else "N/A"
            lines.append(
                f"{i}. {p['name']} - Giá: {p.get('price', 'Liên hệ')}\n"
                f"   Link: {p['url']}\n"
                f"   Danh mục: {', '.join(p.get('categories', []))}\n"
                f"   Điểm nổi bật: {entities_str}"
            )
        return "\n\n".join(lines)

if __name__ == "__main__":
    rag = GraphRAG()
    print("Type 'exit' or 'quit' to quit\n")
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
