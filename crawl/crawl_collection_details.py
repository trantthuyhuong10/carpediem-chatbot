import requests
from bs4 import BeautifulSoup
import time
import json
import os
from crawl.product_db import ProductDatabase


class CollectionDetailsCrawler:
    
    def __init__(self):
        self.base_url = "https://carpediem.vn"
        self.delay = 2
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.visited_urls = set()
        self.collections_details = []

    def load_collections(self, filepath):
        """Load collections from JSON file"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"File {filepath} not found!")
            return []

    def fetch_page(self, url):
        """Fetch a page and return HTML content"""
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
        """Parse HTML and return BeautifulSoup object"""
        soup = BeautifulSoup(html, "html.parser")
        return soup

    def extract_products(self, soup, collection_url):
        """Extract product names and URLs from a collection page"""
        products = []
        
        # Thử các selector phổ biến để tìm sản phẩm
        product_selectors = [
            ".product-item-detail-title a",     # từ static_crawling.py
            ".product-item a",                   # generic product item
            ".product-item__title a",            # variant with __
            ".product-card a",                   # product card
            ".product-title a",                  # product title
            ".item-product a",                   # item-product
        ]
        
        for selector in product_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    try:
                        href = element.get("href", "").strip()
                        text = element.get_text(strip=True)
                        
                        if not href or not text:
                            continue
                        
                        # Nếu URL không bắt đầu bằng http, thêm domain
                        if not href.startswith("http"):
                            href = self.base_url + href if not href.startswith("/") else self.base_url + href
                        
                        product_item = {
                            "name": text,
                            "url": href
                        }
                        
                        # Tránh duplicates
                        if product_item not in products:
                            products.append(product_item)
                    except Exception:
                        continue
                
                # Nếu tìm được sản phẩm với selector này, dừng và trả về
                if products:
                    break
        
        return products

    def crawl_collection(self, collection):
        """Crawl a single collection and extract products"""
        collection_name = collection.get("name", "Unknown")
        collection_url = collection.get("url", "")
        
        if not collection_url:
            print(f"Skipping collection '{collection_name}' - no URL")
            return None
        
        # Đảm bảo URL có domain đầy đủ
        if not collection_url.startswith("http"):
            full_url = self.base_url + (collection_url if collection_url.startswith("/") else "/" + collection_url)
        else:
            full_url = collection_url
        
        print(f"\nCrawling collection: {collection_name}")
        print(f"URL: {full_url}")
        
        html = self.fetch_page(full_url)
        if not html:
            print(f"  -> Failed to fetch")
            return None
        
        soup = self.parse_page(html)
        products = self.extract_products(soup, full_url)
        
        print(f"  -> Found {len(products)} products")
        
        collection_detail = {
            "name": collection_name,
            "url": collection_url,
            "products": products
        }
        
        return collection_detail

    def crawl(self, collections_json_path="data/cache/collections.json", save_json=True):
        """Crawl all collections and save details"""
        print(f"Loading collections from {collections_json_path}...")
        collections = self.load_collections(collections_json_path)
        
        if not collections:
            print("No collections found!")
            return
        
        print(f"Found {len(collections)} collections to crawl\n")
        
        for collection in collections:
            detail = self.crawl_collection(collection)
            if detail:
                self.collections_details.append(detail)
        
        print(f"\n{'='*50}")
        print(f"Total crawled: {len(self.collections_details)} collections")
        
        if save_json:
            os.makedirs("data/cache", exist_ok=True)
            with open("data/cache/collection_details.json", "w", encoding="utf-8") as f:
                json.dump(self.collections_details, f, ensure_ascii=False, indent=2)
            print(f"Saved to data/cache/collection_details.json")

    def save_to_db(self, db_path=None):
        """Assign collection IDs for existing products in SQLite database"""
        db = ProductDatabase(db_path=db_path)
        print(f"\nAssigning collections for products from {len(self.collections_details)} collections...")

        assigned = db.assign_collections_from_details()
        db.close()

        print(f"\n{'='*50}")
        print(f"Database assignments completed! ({assigned} products/giftsets assigned)")

if __name__ == "__main__":
    crawler = CollectionDetailsCrawler()
    crawler.crawl(
        collections_json_path="data/cache/collections.json",
        save_json=True
    )
    crawler.save_to_db()
