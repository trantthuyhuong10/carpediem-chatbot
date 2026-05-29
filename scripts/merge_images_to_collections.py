import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DETAILS_PATH = "data/cache/product_details.json"
MERGED_PATH = "data/cache/merged_collection_products.json"


def merge():
    with open(DETAILS_PATH, "r", encoding="utf-8") as f:
        details = json.load(f)

    detail_by_url = {}
    for p in details:
        url = p.get("url", "")
        if url:
            detail_by_url[url] = p

    with open(MERGED_PATH, "r", encoding="utf-8") as f:
        merged = json.load(f)

    updated = 0
    skipped = 0
    for col in merged.get("collections", []):
        for product in col.get("products", []):
            url = product.get("url", "")
            detail = detail_by_url.get(url)
            if not detail:
                skipped += 1
                continue

            new_images = detail.get("images", [])
            if new_images:
                product["images"] = new_images
                updated += 1

    with open(MERGED_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Updated: {updated} products")
    print(f"Skipped (no match): {skipped}")
    print(f"Saved to {MERGED_PATH}")


if __name__ == "__main__":
    merge()
