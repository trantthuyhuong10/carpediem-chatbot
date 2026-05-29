import argparse
import os
import re
import sqlite3
import sys
import unicodedata
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from crawl.product_db import ProductDatabase


START_MARKER = "hop qua tang bao gom"
END_MARKER = "cam ket tai carpe diem"

ALIASES = {
    "nen thom lien dai": ["nen thom diep lien", "nen thom"],
    "nen thom signature": ["nen thom signature"],
    "nen thom mini bowl": ["nen thom mini bowl"],
    "the thom khuech huong": ["the khuech huong"],
    "xit thom 30ml": ["xit thom - 30ml", "tinh dau nuoc hoa nho giot - 30ml"],
    "tinh dau nuoc hoa 30ml": ["tinh dau nuoc hoa nho giot - 30ml", "xit thom - 30ml"],
    "tinh dau nuoc hoa 10ml": ["tinh dau nuoc hoa nho giot - 10ml"],
    "tinh dau khuech tan 100ml": ["tinh dau khuech tan - 100ml"],
    "khan lua": ["khan lua bandana"],
    "hop dung da": ["hop dung da thom"],
    "da ho phach": ["da ho phach"],
    "da nham thach": ["da nham thach"],
    "diem dai carpe diem": [],
    "hop giay my thuat": [],
    "bo an pham": [],
    "candle story": [],
    "thiep viet tay": [],
}


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def clean_component_line(line: str) -> str:
    text = normalize_text(line)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"^[\-•*\s]+", "", text)
    text = re.sub(r"^\d+\s*", "", text)
    text = re.sub(r"^\d+(?:[.,]\d+)?\s*(?:g|kg|ml|l)\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -:.")
    return text


def extract_component_lines(description: str) -> List[str]:
    if not description:
        return []
    normalized = normalize_text(description)

    start = normalized.find(START_MARKER)
    if start == -1:
        return []
    start += len(START_MARKER)

    end = normalized.find(END_MARKER, start)
    segment = normalized[start:end] if end != -1 else normalized[start:]

    segment = segment.replace("?", " ")
    segment = segment.replace("•", " ")
    segment = re.sub(r"\s+", " ", segment).strip()
    segment = re.sub(r"(?:^|\s)(\d{1,3}(?:[.,]\d+)?\s*(?:g|kg|ml|l)?\s+)", r"\n\1", segment)

    raw_lines = re.split(r"[\r\n]+", segment)
    lines = []
    for raw in raw_lines:
        cleaned = clean_component_line(raw)
        if cleaned and len(cleaned) >= 3:
            lines.append(cleaned)
    return lines


def score_candidate(component: str, product_name: str) -> float:
    if component == product_name:
        return 1.0
    if component in product_name or product_name in component:
        return 0.95
    return SequenceMatcher(None, component, product_name).ratio()


def find_best_product_match(component: str, products: List[Tuple[str, str]], threshold: float, force: bool = False) -> Optional[str]:
    alias_targets = ALIASES.get(component, [])
    if alias_targets:
        normalized_targets = [normalize_text(x) for x in alias_targets]
        for product_id, raw_name in products:
            name = normalize_text(raw_name)
            if any(t and t == name for t in normalized_targets):
                return product_id

    best_product_id = None
    best_score = 0.0
    for product_id, raw_name in products:
        name = normalize_text(raw_name)
        if not name:
            continue
        score = score_candidate(component, name)
        if score > best_score:
            best_score = score
            best_product_id = product_id
    if best_score >= threshold or (force and best_product_id is not None):
        return best_product_id
    return None


def fetch_products(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    rows = conn.execute("SELECT id, name FROM Products").fetchall()
    return [(row["id"], row["name"] or "") for row in rows]


def fetch_giftsets(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute("SELECT id, name, description FROM Giftset").fetchall()


def link_components(db: ProductDatabase, threshold: float = 0.8, force: bool = False) -> dict:
    conn = db.conn
    products = fetch_products(conn)
    giftsets = fetch_giftsets(conn)

    total_giftsets = 0
    total_components = 0
    matched_components = 0
    inserted_links = 0
    unmatched_samples = []

    for giftset in giftsets:
        description = giftset["description"] or ""
        components = extract_component_lines(description)
        if not components:
            continue

        total_giftsets += 1
        for component in components:
            total_components += 1
            product_id = find_best_product_match(component, products, threshold=threshold, force=force)
            if not product_id:
                if len(unmatched_samples) < 20:
                    unmatched_samples.append(f"{giftset['name']}: {component}")
                continue

            matched_components += 1
            link_id = db.add_products_giftset(product_id=product_id, giftset_id=giftset["id"])
            if link_id:
                inserted_links += 1

    return {
        "giftsets_with_components": total_giftsets,
        "components_found": total_components,
        "components_matched": matched_components,
        "links_inserted_or_existing": inserted_links,
        "unmatched_samples": unmatched_samples,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Link Giftset description components into Products_Giftset table")
    parser.add_argument("--db-path", default=None, help="Optional path to SQLite database")
    parser.add_argument("--threshold", type=float, default=0.8, help="Similarity threshold from 0 to 1")
    parser.add_argument("--force", action="store_true", help="Force-map unmatched lines to best product candidate")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db = ProductDatabase(db_path=args.db_path)
    try:
        result = link_components(db, threshold=args.threshold, force=args.force)
        print("Giftset component linking done")
        print(f"- Giftsets parsed: {result['giftsets_with_components']}")
        print(f"- Components found: {result['components_found']}")
        print(f"- Components matched: {result['components_matched']}")
        print(f"- Links inserted/existing: {result['links_inserted_or_existing']}")
        if result["unmatched_samples"]:
            print("- Unmatched samples:")
            for item in result["unmatched_samples"]:
                safe_item = item.encode("cp1252", errors="replace").decode("cp1252")
                print(f"  * {safe_item}")
    finally:
        db.close()


if __name__ == "__main__":
    main()