import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage import MinioStorage
from crawl.product_db import ProductDatabase

PRODUCT_DETAILS_PATH = "data/cache/product_details.json"
MERGED_PATH = "data/cache/merged_collection_products.json"

def upload_all():
    storage = MinioStorage()
    if not storage.available:
        print("[ERROR] MinIO not available. Exit.")
        return

    with open(PRODUCT_DETAILS_PATH, "r", encoding="utf-8") as f:
        products = json.load(f)

    total = len(products)
    success = 0
    failed = 0

    for idx, product in enumerate(products):
        images = product.get("images") or []
        if not images:
            print(f"  [{idx+1}/{total}] {product['name'][:40]:40s} → no images, skip")
            continue

        product_url = product.get("url", "")
        if not product_url:
            print(f"  [{idx+1}/{total}] {product['name'][:40]:40s} → no url, skip")
            continue

        if not product_url.startswith("http"):
            product_url = "https://carpediem.vn" + product_url

        new_images = []
        old_is_minio = False
        for i, img_url in enumerate(images):
            if storage.is_minio_key(img_url):
                new_images.append(img_url)
                old_is_minio = True
                continue

            key = storage.product_image_key(product_url, index=i)
            print(f"  [{idx+1}/{total}] Uploading {key} ...", end=" ", flush=True)
            uploaded = storage.upload_from_url(key, img_url)
            if uploaded:
                new_images.append(uploaded)
                success += 1
                print("OK")
            else:
                new_images.append(img_url)
                failed += 1
                print("FAIL (keep original)")

        if new_images and not old_is_minio:
            product["images"] = new_images
            if new_images and storage.is_minio_key(new_images[0]):
                product["image"] = new_images[0]

    with open(PRODUCT_DETAILS_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    db = ProductDatabase()
    db.load_items(products)
    db.close()

    print(f"\n[DONE] Uploaded: {success}, Failed: {failed}, Total: {total}")

if __name__ == "__main__":
    upload_all()
