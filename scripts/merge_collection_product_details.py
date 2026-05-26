import argparse
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def slugify(value: Optional[str]) -> str:
    if not value:
        return ""
    text = normalize_text(value)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "unknown"


def get_collection_id(collection_url: Optional[str], collection_name: Optional[str]) -> str:
    if collection_url:
        parsed = urlparse(collection_url)
        path = parsed.path or ""
        if path:
            candidate = path.rstrip("/").split("/")[-1]
            if candidate:
                return slugify(candidate)
    return slugify(collection_name)


def load_json(filepath: str) -> Any:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def build_product_lookup(products: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for product in products:
        url_key = normalize_text(product.get("url"))
        name_key = normalize_text(product.get("name"))
        if url_key:
            lookup[url_key] = product
        elif name_key and name_key not in lookup:
            lookup[name_key] = product
    return lookup


def build_collection_products(
    collections: List[Dict[str, Any]],
    product_lookup: Dict[str, Dict[str, Any]],
    matched_keys: set,
) -> List[Dict[str, Any]]:
    merged_collections: List[Dict[str, Any]] = []

    for collection in collections:
        collection_name = collection.get("name") or ""
        collection_url = collection.get("url")
        collection_id = get_collection_id(collection_url, collection_name)

        merged_products: List[Dict[str, Any]] = []
        for product in collection.get("products", []):
            product_url = product.get("url")
            product_name = product.get("name")
            detail = None

            if product_url:
                detail = product_lookup.get(normalize_text(product_url))
            if not detail and product_name:
                detail = product_lookup.get(normalize_text(product_name))

            if detail:
                matched_key = normalize_text(detail.get("url")) or normalize_text(detail.get("name"))
                matched_keys.add(matched_key)
                merged_products.append(
                    {
                        "name": detail.get("name") or product_name or "",
                        "url": detail.get("url") or product_url or "",
                        "price": detail.get("price") or "",
                        "description": detail.get("description") or "",
                        "images": detail.get("images") or [],
                        "status": "complete",
                    }
                )
            else:
                merged_products.append(
                    {
                        "name": product_name or "",
                        "url": product_url or "",
                        "price": "",
                        "description": "",
                        "images": [],
                        "status": "incomplete",
                    }
                )

        merged_collections.append(
            {
                "id": collection_id,
                "name": collection_name,
                "url": collection_url,
                "product_count": len(merged_products),
                "products": merged_products,
            }
        )

    return merged_collections


def build_orphan_collection(
    products: List[Dict[str, Any]],
    matched_keys: set,
) -> Optional[Dict[str, Any]]:
    orphan_products: List[Dict[str, Any]] = []

    for product in products:
        key = normalize_text(product.get("url")) or normalize_text(product.get("name"))
        if not key or key in matched_keys:
            continue

        orphan_products.append(
            {
                "name": product.get("name") or "",
                "url": product.get("url") or "",
                "price": product.get("price") or "",
                "description": product.get("description") or "",
                "images": product.get("images") or [],
                "status": "orphan",
            }
        )
        matched_keys.add(key)

    if not orphan_products:
        return None

    return {
        "id": "other-products",
        "name": "Sản phẩm khác",
        "url": None,
        "is_orphan": True,
        "product_count": len(orphan_products),
        "products": orphan_products,
    }


def build_metadata(
    collections: List[Dict[str, Any]],
    matched_keys: set,
    orphan_count: int,
) -> Dict[str, Any]:
    complete_count = 0
    incomplete_count = 0
    seen_keys = set()

    for collection in collections:
        for product in collection.get("products", []):
            key = normalize_text(product.get("url")) or normalize_text(product.get("name"))
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            if product.get("status") == "complete":
                complete_count += 1
            elif product.get("status") == "incomplete":
                incomplete_count += 1

    total_products = complete_count + incomplete_count + orphan_count

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "total_collections": len(collections) + (1 if orphan_count > 0 else 0),
        "total_products": total_products,
        "statistics": {
            "complete": complete_count,
            "incomplete": incomplete_count,
            "orphan": orphan_count,
        },
    }


def save_json(data: Any, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge collection_details.json and product_details.json into a single combined JSON file."
    )
    parser.add_argument(
        "--collections",
        default=os.path.join("data", "cache", "collection_details.json"),
        help="Path to collection_details.json",
    )
    parser.add_argument(
        "--products",
        default=os.path.join("data", "cache", "product_details.json"),
        help="Path to product_details.json",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("data", "cache", "merged_collection_products.json"),
        help="Output path for the merged JSON file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    collections_path = args.collections
    products_path = args.products
    output_path = args.output

    if not os.path.exists(collections_path) or not os.path.exists(products_path):
        raise FileNotFoundError(
            f"Cần có cả hai file: {collections_path} và {products_path}"
        )

    collections = load_json(collections_path)
    products = load_json(products_path)

    if not isinstance(collections, list):
        raise ValueError("Dữ liệu collection_details.json phải là một danh sách các collection.")
    if not isinstance(products, list):
        raise ValueError("Dữ liệu product_details.json phải là một danh sách các sản phẩm.")

    matched_keys: set = set()
    merged_collections = build_collection_products(collections, build_product_lookup(products), matched_keys)
    orphan_collection = build_orphan_collection(products, matched_keys)

    output_collections = merged_collections.copy()
    if orphan_collection:
        output_collections.append(orphan_collection)

    orphan_count = len(orphan_collection["products"]) if orphan_collection else 0
    metadata = build_metadata(merged_collections, matched_keys, orphan_count)

    result = {
        "metadata": metadata,
        "collections": output_collections,
    }

    save_json(result, output_path)
    print(f"Saved merged data to {output_path}")


if __name__ == "__main__":
    main()
