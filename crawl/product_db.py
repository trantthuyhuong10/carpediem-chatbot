import json
import os
import re
import sqlite3
import uuid
from typing import Dict, List, Optional
from urllib.parse import urlparse

DB_PATH = os.path.join("data", "carpediem_products.db")

class ProductDatabase:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = DB_PATH
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.execute("PRAGMA foreign_keys = ON")
        if self._should_recreate_schema():
            self._drop_all_tables()

        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS BoSuuTap (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    url TEXT
                );

                CREATE TABLE IF NOT EXISTS Products (
                    id TEXT PRIMARY KEY,
                    id_bst TEXT,
                    name TEXT,
                    url TEXT UNIQUE,
                    price TEXT,
                    description TEXT,
                    image TEXT,
                    type_product TEXT,
                    FOREIGN KEY (id_bst) REFERENCES BoSuuTap(id)
                );

                CREATE TABLE IF NOT EXISTS Giftset (
                    id TEXT PRIMARY KEY,
                    id_bst TEXT,
                    name TEXT,
                    image TEXT,
                    url TEXT UNIQUE,
                    price TEXT,
                    description TEXT,
                    FOREIGN KEY (id_bst) REFERENCES BoSuuTap(id)
                );

                CREATE TABLE IF NOT EXISTS Products_Giftset (
                    id TEXT PRIMARY KEY,
                    id_product TEXT,
                    id_giftset TEXT,
                    FOREIGN KEY (id_product) REFERENCES Products(id),
                    FOREIGN KEY (id_giftset) REFERENCES Giftset(id)
                );

                CREATE TABLE IF NOT EXISTS Collection_Products (
                    id TEXT PRIMARY KEY,
                    id_bst TEXT NOT NULL,
                    id_product TEXT NOT NULL,
                    FOREIGN KEY (id_bst) REFERENCES BoSuuTap(id),
                    FOREIGN KEY (id_product) REFERENCES Products(id),
                    UNIQUE(id_bst, id_product)
                );

                CREATE TABLE IF NOT EXISTS Collection_Giftsets (
                    id TEXT PRIMARY KEY,
                    id_bst TEXT NOT NULL,
                    id_giftset TEXT NOT NULL,
                    FOREIGN KEY (id_bst) REFERENCES BoSuuTap(id),
                    FOREIGN KEY (id_giftset) REFERENCES Giftset(id),
                    UNIQUE(id_bst, id_giftset)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_bsts_name ON BoSuuTap(name);
                CREATE INDEX IF NOT EXISTS idx_products_bst ON Products(id_bst);
                CREATE INDEX IF NOT EXISTS idx_giftset_bst ON Giftset(id_bst);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_products_url ON Products(url);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_giftset_url ON Giftset(url);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_products_giftset ON Products_Giftset(id_product, id_giftset);
                CREATE INDEX IF NOT EXISTS idx_collection_products ON Collection_Products(id_bst);
                CREATE INDEX IF NOT EXISTS idx_collection_giftsets ON Collection_Giftsets(id_bst);
            """)

    def _should_recreate_schema(self) -> bool:
        expected = {
            "BoSuuTap": {"id": "TEXT", "name": "TEXT", "url": "TEXT"},
            "Products": {"id": "TEXT", "id_bst": "TEXT", "name": "TEXT", "url": "TEXT", "price": "TEXT", "description": "TEXT", "image": "TEXT", "type_product": "TEXT"},
            "Giftset": {"id": "TEXT", "id_bst": "TEXT", "name": "TEXT", "image": "TEXT", "url": "TEXT", "price": "TEXT", "description": "TEXT"},
            "Products_Giftset": {"id": "TEXT", "id_product": "TEXT", "id_giftset": "TEXT"},
            "Collection_Products": {"id": "TEXT", "id_bst": "TEXT", "id_product": "TEXT"},
            "Collection_Giftsets": {"id": "TEXT", "id_bst": "TEXT", "id_giftset": "TEXT"},
        }

        for table_name, columns in expected.items():
            rows = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            if not rows:
                continue
            actual = {row[1]: row[2].upper() for row in rows}
            for col_name, expected_type in columns.items():
                if col_name not in actual or actual[col_name] != expected_type:
                    return True
        return False

    def _drop_all_tables(self) -> None:
        with self.conn:
            self.conn.executescript("""
                DROP TABLE IF EXISTS Collection_Giftsets;
                DROP TABLE IF EXISTS Collection_Products;
                DROP TABLE IF EXISTS Products_Giftset;
                DROP TABLE IF EXISTS Giftset;
                DROP TABLE IF EXISTS Products;
                DROP TABLE IF EXISTS BoSuuTap;
            """)

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    def clear_all_data(self) -> None:
        """Clear all data from all tables"""
        with self.conn:
            self.conn.executescript("""
                DELETE FROM Products_Giftset;
                DELETE FROM Collection_Products;
                DELETE FROM Collection_Giftsets;
                DELETE FROM Products;
                DELETE FROM Giftset;
                DELETE FROM BoSuuTap;
            """)

    def _normalize(self, value: Optional[str]) -> str:
        return (value or "").strip()

    def _guess_type_product(self, name: str, description: str) -> str:
        text = name.lower()
        if "nến thơm" in text or "nen thom" in text or "nến" in text or "nen" in text:
            return "NenThom"
        if "đá thơm" in text or "da thom" in text or "đá" in text:
            return "DaThom"
        if "khăn" in text or "khan" in text:
            return "Khan"
        if "tinh dầu" in text or "tinh dau" in text:
            return "TinhDau"
        return ""

    def _guess_collection_name(self, text: str) -> str:
        return "Uncategorized"

    def _url_variants(self, url: Optional[str]) -> List[str]:
        if not url:
            return []
        url = self._normalize(url)
        variants = {url}

        try:
            parsed = urlparse(url)
            if parsed.path:
                variants.add(parsed.path)
                variants.add(parsed.path.lstrip("/"))
            if parsed.netloc and parsed.scheme:
                if parsed.path:
                    variants.add(parsed.scheme + "://" + parsed.netloc + parsed.path)
        except Exception:
            pass

        return [v for v in variants if v]

    def get_product_by_url(self, url: str) -> Optional[sqlite3.Row]:
        variants = self._url_variants(url)
        if not variants:
            return None
        placeholders = ",".join("?" for _ in variants)
        query = f"SELECT * FROM Products WHERE url IN ({placeholders})"
        return self.conn.execute(query, variants).fetchone()

    def get_giftset_by_url(self, url: str) -> Optional[sqlite3.Row]:
        variants = self._url_variants(url)
        if not variants:
            return None
        placeholders = ",".join("?" for _ in variants)
        query = f"SELECT * FROM Giftset WHERE url IN ({placeholders})"
        return self.conn.execute(query, variants).fetchone()

    def get_product_by_name(self, name: str) -> Optional[sqlite3.Row]:
        name = self._normalize(name)
        if not name:
            return None
        return self.conn.execute(
            "SELECT * FROM Products WHERE lower(name) = ?",
            (name.lower(),)
        ).fetchone()

    def get_giftset_by_name(self, name: str) -> Optional[sqlite3.Row]:
        name = self._normalize(name)
        if not name:
            return None
        return self.conn.execute(
            "SELECT * FROM Giftset WHERE lower(name) = ?",
            (name.lower(),)
        ).fetchone()

    def set_product_bst(self, product_id: str, id_bst: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE Products SET id_bst = ? WHERE id = ?",
                (id_bst, product_id)
            )

    def set_giftset_bst(self, giftset_id: str, id_bst: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE Giftset SET id_bst = ? WHERE id = ?",
                (id_bst, giftset_id)
            )

    def _is_giftset(self, name: str, url: str) -> bool:
        text = f"{name} {url}".lower()
        return "gift set" in text or "gift-set" in text or "giftset" in text

    def find_existing_item(self, product: Dict) -> tuple[Optional[str], Optional[sqlite3.Row]]:
        url = self._normalize(product.get("url"))
        name = self._normalize(product.get("name"))

        if url:
            row = self.get_product_by_url(url)
            if row:
                return "product", row
            row = self.get_giftset_by_url(url)
            if row:
                return "giftset", row

        if name:
            row = self.get_product_by_name(name)
            if row:
                return "product", row
            row = self.get_giftset_by_name(name)
            if row:
                return "giftset", row

        return None, None

    def ensure_uncategorized_bst(self) -> str:
        return self.get_or_create_bst("Uncategorized", "")

    def assign_uncategorized_items(self, uncategorized_id: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE Products SET id_bst = ? WHERE id_bst IS NULL",
                (uncategorized_id,)
            )
            self.conn.execute(
                "UPDATE Giftset SET id_bst = ? WHERE id_bst IS NULL",
                (uncategorized_id,)
            )

    def assign_collections_from_details(self, details_path: str = "data/cache/collection_details.json") -> int:
        if not os.path.exists(details_path):
            return 0

        with open(details_path, "r", encoding="utf-8") as f:
            collection_details = json.load(f)

        uncategorized_id = self.ensure_uncategorized_bst()
        total_assigned = 0

        for collection in collection_details:
            bst_name = self._normalize(collection.get("name"))
            bst_url = self._normalize(collection.get("url"))
            if not bst_name:
                continue

            bst_id = self.get_or_create_bst(bst_name, bst_url)
            for product in collection.get("products", []):
                product_type, row = self.find_existing_item(product)
                if not row:
                    continue

                if product_type == "product":
                    self.set_product_bst(row["id"], bst_id)
                    self.add_collection_product(bst_id, row["id"])
                else:
                    self.set_giftset_bst(row["id"], bst_id)
                    self.add_collection_giftset(bst_id, row["id"])
                total_assigned += 1

        self.assign_uncategorized_items(uncategorized_id)
        return total_assigned

    def get_or_create_bst(self, name: str, url: Optional[str] = None) -> str:
        name = self._normalize(name) or "Uncategorized"
        row = self.conn.execute("SELECT id FROM BoSuuTap WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        bst_id = self._new_id()
        with self.conn:
            self.conn.execute(
                "INSERT INTO BoSuuTap (id, name, url) VALUES (?, ?, ?)",
                (bst_id, name, self._normalize(url))
            )
        return bst_id

    def add_product(self, product: Dict, id_bst: Optional[str] = None) -> str:
        url = self._normalize(product.get("url"))
        name = self._normalize(product.get("name"))
        price = self._normalize(product.get("price"))
        description = self._normalize(product.get("description"))
        images = product.get("images") or []
        image = images[0] if isinstance(images, list) and images else self._normalize(product.get("image"))
        type_product = self._guess_type_product(name, description)

        product_id = self._new_id()
        with self.conn:
            self.conn.execute(
                "INSERT INTO Products (id, id_bst, name, url, price, description, image, type_product) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET "
                "id_bst = excluded.id_bst, name = excluded.name, price = excluded.price, description = excluded.description, "
                "image = excluded.image, type_product = excluded.type_product",
                (product_id, id_bst, name, url, price, description, image, type_product)
            )
        row = self.conn.execute("SELECT id FROM Products WHERE url = ?", (url,)).fetchone()
        return row["id"] if row else ""

    def add_giftset(self, giftset: Dict, id_bst: Optional[str] = None) -> str:
        url = self._normalize(giftset.get("url"))
        name = self._normalize(giftset.get("name"))
        price = self._normalize(giftset.get("price"))
        description = self._normalize(giftset.get("description"))
        images = giftset.get("images") or []
        image = images[0] if isinstance(images, list) and images else self._normalize(giftset.get("image"))

        giftset_id = self._new_id()
        with self.conn:
            self.conn.execute(
                "INSERT INTO Giftset (id, id_bst, name, image, url, price, description) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET "
                "id_bst = excluded.id_bst, name = excluded.name, image = excluded.image, price = excluded.price, description = excluded.description",
                (giftset_id, id_bst, name, image, url, price, description)
            )
        row = self.conn.execute("SELECT id FROM Giftset WHERE url = ?", (url,)).fetchone()
        return row["id"] if row else ""

    def add_products_giftset(self, product_id: str, giftset_id: str) -> str:
        row_id = self._new_id()
        with self.conn:
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO Products_Giftset (id, id_product, id_giftset) VALUES (?, ?, ?)",
                (row_id, product_id, giftset_id)
            )
            if cursor.rowcount:
                return row_id
            row = self.conn.execute(
                "SELECT id FROM Products_Giftset WHERE id_product = ? AND id_giftset = ?", (product_id, giftset_id)).fetchone()
            return row["id"] if row else ""

    def add_collection_product(self, id_bst: str, id_product: str) -> str:
        """Add product to a collection (many-to-many relationship)"""
        row_id = self._new_id()
        with self.conn:
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO Collection_Products (id, id_bst, id_product) VALUES (?, ?, ?)",
                (row_id, id_bst, id_product)
            )
            if cursor.rowcount:
                return row_id
            row = self.conn.execute(
                "SELECT id FROM Collection_Products WHERE id_bst = ? AND id_product = ?",
                (id_bst, id_product)
            ).fetchone()
            return row["id"] if row else ""

    def add_collection_giftset(self, id_bst: str, id_giftset: str) -> str:
        """Add giftset to a collection (many-to-many relationship)"""
        row_id = self._new_id()
        with self.conn:
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO Collection_Giftsets (id, id_bst, id_giftset) VALUES (?, ?, ?)",
                (row_id, id_bst, id_giftset)
            )
            if cursor.rowcount:
                return row_id
            row = self.conn.execute(
                "SELECT id FROM Collection_Giftsets WHERE id_bst = ? AND id_giftset = ?",
                (id_bst, id_giftset)
            ).fetchone()
            return row["id"] if row else ""

    def load_items(self, items: List[Dict]) -> None:
        for item in items:
            name = self._normalize(item.get("name"))
            url = self._normalize(item.get("url"))
            if self._is_giftset(name, url):
                self.add_giftset(item)
            else:
                self.add_product(item)

    def load_from_json(self, filepath: str) -> None:
        with open(filepath, "r", encoding="utf-8") as f:
            items = json.load(f)
        self.load_items(items)

    def export_summary(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT id, name, url FROM BoSuuTap ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]

    def _row_to_dict(self, row) -> Dict:
        return {
            "name": row["name"],
            "url": row["url"],
            "price": row["price"],
            "description": row["description"],
            "image": row["image"],
            "type_product": row["type_product"],
        }

    def get_products_by_names(self, names: List[str]) -> List[Dict]:
        if not names:
            return []
        lower_names = [name.lower() for name in names]
        placeholders = ",".join("?" for _ in lower_names)
        query = f"""
            SELECT name, url, price, description, image, type_product
            FROM Products
            WHERE lower(name) IN ({placeholders})
            UNION ALL
            SELECT name, url, price, description, image, '' AS type_product
            FROM Giftset
            WHERE lower(name) IN ({placeholders})
        """
        params = lower_names + lower_names
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def search_items(self, query_text: str, top_k: int = 5) -> List[Dict]:
        if not query_text or not query_text.strip():
            return []
        keywords = [w.lower() for w in re.findall(r"\w+", query_text) if len(w) > 1]
        if not keywords:
            return []

        clauses = []
        params = []
        for kw in keywords:
            clauses.append("(lower(name) LIKE ? OR lower(description) LIKE ?)")
            params.extend([f"%{kw}%", f"%{kw}%"])

        where_clause = " OR ".join(clauses)
        query = f"""
            SELECT name, url, price, description, image, type_product
            FROM Products
            WHERE {where_clause}
            UNION ALL
            SELECT name, url, price, description, image, '' AS type_product
            FROM Giftset
            WHERE {where_clause}
            LIMIT ?
        """
        params.append(top_k)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]


if __name__ == "__main__":
    db = ProductDatabase()
    db.clear_all_data()    
    db.load_from_json("data/cache/product_details.json")
    print(f"SQLite DB saved to {DB_PATH}")
    db.close()
