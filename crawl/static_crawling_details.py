import requests
from bs4 import BeautifulSoup
import time
import json
import os
from crawl.product_db import ProductDatabase

class DetailCrawler:
    def __init__(self):
        self.base_url = "https://carpediem.vn"
        self.delay = 2
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.visited_urls = set()
        self.products_details = []

    def load_products(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def fetch_page(self, url):
        try:
            if url in self.visited_urls:
                return None
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            self.visited_urls.add(url)
            time.sleep(self.delay)
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def parse_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        return soup

    def extract_product_detail(self, soup, product_url):
        detail = {"url": product_url}

        try:
            title_tag = soup.select_one("h1.main-product-title")
            detail["name"] = title_tag.text.strip() if title_tag else ""
        except:
            detail["name"] = ""

        try:
            price_tag = soup.select_one(".main-product-price-this")
            detail["price"] = price_tag.text.strip() if price_tag else ""
        except:
            detail["price"] = ""

        try:
            desc_tag = soup.select_one(".main-product-description-item-data")
            detail["description"] = desc_tag.text.strip() if desc_tag else ""
        except:
            detail["description"] = ""

        try:
            images = []
            img_tags = soup.select("img.w-auto[src*='bizweb.dktcdn.net']")
            for img in img_tags:
                src = img.get("src") or img.get("data-src")
                if src and "product" in src:
                    if src.startswith("//"):
                        src = "https:" + src
                    images.append(src)
            if not images:
                og_image = soup.select_one('meta[property="og:image"]')
                if og_image and og_image.get("content"):
                    images.append(og_image["content"])
            detail["images"] = images
        except:
            detail["images"] = []

        return detail

    def crawl_details(self, products, max_products=None):
        if max_products:
            products = products[:max_products]

        for i, product in enumerate(products):
            url = product.get("url", "")
            if not url:
                continue

            if not url.startswith("http"):
                url = self.base_url + url

            html = self.fetch_page(url)
            if html:
                soup = self.parse_page(html)
                detail = self.extract_product_detail(soup, url)
                self.products_details.append(detail)
            else:
                pass

    def save_json(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.products_details, f, ensure_ascii=False, indent=2)

    def save_db(self, db_path: str = None):
        db = ProductDatabase(db_path=db_path)
        db.load_items(self.products_details)
        db.close()

if __name__ == "__main__":
    crawler = DetailCrawler()

    products = crawler.load_products("data/cache/product_details.json")

    crawler.crawl_details(products)

    crawler.save_json("data/cache/product_details.json")
    crawler.save_db()
