import sys
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import os
import re
import json
import numpy as np
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.vector_store import VectorStore

load_dotenv()

class Neo4jGraphBuilder:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        self.user = os.getenv("NEO4J_USER")
        self.password = os.getenv("NEO4J_PASSWORD")
        if not all([self.uri, self.user, self.password]):
            raise ValueError("Lỗi")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self._test_connection()

    def _test_connection(self):
        try:
            with self.driver.session() as s:
                s.run("RETURN 1").single()
        except Exception as e:
            raise ConnectionError(e)

    def close(self):
        self.driver.close()

    def clear_database(self):
        with self.driver.session() as s:
            s.run("DROP CONSTRAINT similarity_pair IF EXISTS")
            s.run("MATCH (n) DETACH DELETE n")

    def create_constraints(self):
        with self.driver.session() as s:
            for c in [
                "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
                "CREATE CONSTRAINT collection_name IF NOT EXISTS FOR (c:Collection) REQUIRE c.name IS UNIQUE",
                "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            ]:
                s.run(c)

    def create_product_node(self, product_id, name, url, price=None, description=None, images=None):
        with self.driver.session() as s:
            return s.run("""
                MERGE (p:Product {id: $id})
                SET p.name=$name, p.url=$url, p.price=$price,
                    p.description=$description, p.images=$images, p.updated_at=datetime()
                RETURN p
            """, id=product_id, name=name, url=url, price=price, 
                 description=description, images=images or []).single()["p"]

    def create_category_node(self, name):
        with self.driver.session() as s:
            return s.run("MERGE (c:Category {name:$name}) SET c.updated_at=datetime() RETURN c", name=name).single()["c"]

    def create_collection_node(self, name):
        with self.driver.session() as s:
            return s.run("MERGE (c:Collection {name:$name}) SET c.updated_at=datetime() RETURN c", name=name).single()["c"]

    def create_entity_node(self, name, entity_type):
        with self.driver.session() as s:
            return s.run("""
                MERGE (e:Entity {name:$name}) SET e.type=$type, e.updated_at=datetime() RETURN e
            """, name=name, type=entity_type).single()["e"]

    def link_product_to_category(self, product_id, category_name):
        with self.driver.session() as s:
            return s.run("""
                MATCH (p:Product {id:$pid}), (c:Category {name:$cat})
                MERGE (p)-[:BELONGS_TO]->(c) RETURN p, c
            """, pid=product_id, cat=category_name).single()

    def link_product_to_collection(self, product_id, collection_name):
        with self.driver.session() as s:
            return s.run("""
                MATCH (p:Product {id:$pid}), (c:Collection {name:$coll})
                MERGE (p)-[:PART_OF]->(c) RETURN p, c
            """, pid=product_id, coll=collection_name).single()

    def link_product_to_entity(self, product_id, entity_name):
        with self.driver.session() as s:
            return s.run("""
                MATCH (p:Product {id:$pid}), (e:Entity {name:$ename})
                MERGE (p)-[:HAS_ENTITY]->(e) RETURN p, e
            """, pid=product_id, ename=entity_name).single()

    def _extract_category(self, product):
        name = product.get("name", "").lower()
        if "gift set" in name or "giftset" in name or "bộ quà" in name:
            return "Giftset"
        if "tinh dầu" in name:
            return "Tinh dầu"
        if "đá thơm" in name or "thẻ thơm" in name or "khuếch" in name:
            return "Khuếch hương"
        if "nến" in name:
            return "Nến thơm"
        return "Khác"

    def _parse_price(self, price_str):
        if not price_str:
            return 0
        cleaned = re.sub(r"[^\d]", "", price_str)
        return int(cleaned) if cleaned else 0

    def _extract_entities(self, description):
        if not description:
            return []
        desc = description.lower()
        entities = []
        scent_map = {
            "trầm": "Hương trầm", "oải hương": "Oải hương", "lavender": "Oải hương",
            "hoa hồng": "Hoa hồng", "gỗ đàn hương": "Đàn hương", "đàn hương": "Đàn hương",
            "cam chanh": "Cam chanh", "bạc hà": "Bạc hà", "quế": "Quế",
            "nhài": "Hoa nhài", "jasmine": "Hoa nhài", "vanilla": "Vanilla",
            "hoa cúc": "Hoa cúc", "chanh sả": "Chanh sả", "sả chanh": "Chanh sả",
            "thông": "Hương thông", "tuyết tùng": "Tuyết tùng", "cedar": "Tuyết tùng",
        }
        for keyword, label in scent_map.items():
            if keyword in desc:
                entities.append((label, "Scent"))
        occasion_map = {
            "sinh nhật": "Sinh nhật", "valentine": "Valentine",
            "cưới": "Cưới hỏi", "wedding": "Cưới hỏi",
            "tân gia": "Tân gia", "giáng sinh": "Giáng sinh",
            "noel": "Giáng sinh", "tết": "Tết",
        }
        for keyword, label in occasion_map.items():
            if keyword in desc:
                entities.append((label, "Occasion"))
        material_map = {
            "sáp đậu nành": "Sáp đậu nành", "soy wax": "Sáp đậu nành",
            "sáp ong": "Sáp ong", "beeswax": "Sáp ong",
            "xi măng": "Xi măng", "cement": "Xi măng",
            "thủy tinh": "Thủy tinh", "gỗ": "Gỗ",
        }
        for keyword, label in material_map.items():
            if keyword in desc:
                entities.append((label, "Material"))
        seen = set()
        unique = []
        for name, etype in entities:
            if name not in seen:
                seen.add(name)
                unique.append((name, etype))
        return unique

    def load_products_from_json(self, filepath, collection_name="all"):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        products = []
        if isinstance(data, dict):
            if "collections" in data:
                for col in data["collections"]:
                    coll_name = col.get("name", collection_name)
                    self.create_collection_node(coll_name)
                    for item in col.get("products", []):
                        item["collection_name"] = coll_name
                        products.append(item)
            else:
                for coll_name, items in data.items():
                    if not isinstance(items, list):
                        continue
                    self.create_collection_node(coll_name)
                    for item in items:
                        item["collection_name"] = coll_name
                        products.append(item)
        else:
            products = data
            self.create_collection_node(collection_name)
        
        for idx, product in enumerate(products):

            pid = f"product_{idx}"

            price = self._parse_price(
                product.get("price")
            )

            self.create_product_node(
                pid,
                product.get("name", ""),
                product.get("url", ""),
                price,
                product.get("description"),
                product.get("images", [])
            )

            coll = product.get(
                "collection_name",
                collection_name
            )

            self.link_product_to_collection(
                pid,
                coll
            )

            cat = (
                product.get("category")
                or self._extract_category(product)
            )

            self.create_category_node(cat)

            self.link_product_to_category(
                pid,
                cat
            )

        return len(products)

    def extract_and_link_entities(self, filepath):

        with open(filepath,"r",encoding="utf8") as f:
            raw=json.load(f)

        products=[]

        if isinstance(raw,dict):
            if "collections" in raw:
                for col in raw["collections"]:
                    products.extend(col.get("products", []))
            else:
                for items in raw.values():
                    if isinstance(items, list):
                        products.extend(items)
        else:
            products=raw

        count=0

        for idx,product in enumerate(products):

            pid=f"product_{idx}"

            entities=self._extract_entities(
                product.get("description")
            )

            for ename,etype in entities:

                self.create_entity_node(
                    ename,
                    etype
                )

                self.link_product_to_entity(
                    pid,
                    ename
                )

                count+=1

        return count

    def build_similarity_edges(self, threshold=0.7):
        with self.driver.session() as s:
            s.run("MATCH ()-[r:SIMILAR_TO]->() DELETE r")

        store = VectorStore()
        if not store.available:
            return 0

        ids, vectors, payloads = store.get_all_points()
        n = len(vectors)
        if n == 0:
            return 0

        similarities = []
        for i in range(n):
            query_vec = vectors[i].reshape(1, -1)
            scores = vectors @ query_vec.T
            scores = scores.flatten()
            top_indices = np.argsort(-scores)[:min(50, n)]
            for idx in top_indices:
                if idx <= i or idx >= n:
                    continue
                score = float(scores[idx])
                if score >= threshold:
                    source_name = payloads[i].get("name", "")
                    target_name = payloads[idx].get("name", "")
                    if not source_name or not target_name:
                        continue
                    similarities.append({
                        "source_name": source_name,
                        "target_name": target_name,
                        "similarity": round(score, 4),
                        "pair_id": f"{i}_{idx}",
                    })

        with self.driver.session() as s:
            for sim in similarities:
                s.run("""
                    MATCH (p1:Product {name:$s}), (p2:Product {name:$t})
                    MERGE (p1)-[r:SIMILAR_TO {pair_id:$pid}]->(p2)
                    SET r.similarity=$sim, r.created_at=datetime()
                """, s=sim["source_name"], t=sim["target_name"],
                    pid=sim["pair_id"], sim=sim["similarity"])
        return len(similarities)

    def build_all(self, filepath, similarity_threshold=0.7):
        self.create_constraints()
        n_products = self.load_products_from_json(filepath)
        n_entities = self.extract_and_link_entities(filepath)
        n_sim = self.build_similarity_edges(similarity_threshold)
        stats = self.get_statistics()
        return stats

    def query_graph(self, cypher, params=None):
        with self.driver.session() as s:
            return [r.data() for r in s.run(cypher, params or {})]

    def get_products_by_category(self, category_name):
        return self.query_graph("""
            MATCH (p:Product)-[:BELONGS_TO]->(c:Category {name:$cat})
            RETURN p.id AS id, p.name AS name, p.price AS price, p.url AS url ORDER BY p.name
        """, {"cat": category_name})

    def get_products_by_price_range(self, min_price=0, max_price=999999999):
        return self.query_graph("""
            MATCH (p:Product) WHERE p.price >= $min AND p.price <= $max
            RETURN p.id AS id, p.name AS name, p.price AS price, p.url AS url ORDER BY p.price
        """, {"min": min_price, "max": max_price})

    def search_products_by_name(self, term):
        return self.query_graph("""
            MATCH (p:Product) WHERE toLower(p.name) CONTAINS toLower($term)
            RETURN p.id AS id, p.name AS name, p.price AS price, p.url AS url LIMIT 10
        """, {"term": term})

    def get_entity_context(self, entity_name):
        return self.query_graph("""
            MATCH (e:Entity {name:$name})
            OPTIONAL MATCH (e)-[r]-(related:Entity)
            RETURN e.name AS entity, e.type AS type,
                collect(DISTINCT {rel: type(r), related: related.name, rtype: related.type}) AS connections
        """, {"name": entity_name})

    def get_statistics(self):
        with self.driver.session() as s:
            return {
                "total_nodes": s.run("MATCH (n) RETURN count(n) AS c").single()["c"],
                "total_relationships": s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"],
                "product_count": s.run("MATCH (p:Product) RETURN count(p) AS c").single()["c"],
                "category_count": s.run("MATCH (c:Category) RETURN count(c) AS c").single()["c"],
                "entity_count": s.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"],
                "similarity_edges": s.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS c").single()["c"],
            }

if __name__ == "__main__":
    builder = Neo4jGraphBuilder()
    builder.clear_database()
    builder.build_all("data/cache/merged_collection_products.json", similarity_threshold=0.7)
    builder.close()
