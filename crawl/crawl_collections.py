import requests
from bs4 import BeautifulSoup
import time
import json
import os
from crawl.product_db import ProductDatabase


class CollectionsCrawler:
    
    def __init__(self):
        self.base_url = "https://carpediem.vn"
        self.collections_page = "https://carpediem.vn" 
        self.delay = 2
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.visited_urls = set()
        self.collections = []

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
            print(e)
            return None

    def parse_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        return soup

    def extract_collections(self, soup):
        collections_found = set()
        
        elements = soup.find_all("a", href=True)
        
        for element in elements:
            try:
                href = element.get("href", "").strip()
                name = element.get_text(strip=True)
                
                if not href or not name:
                    continue
                
                if "/bst-" not in href.lower():
                    continue
                
                if "BST" not in name:
                    continue
                
                if not href.startswith("http"):
                    href = self.base_url + href if not href.startswith("/") else self.base_url + href
                
                collections_found.add((name, href))
            except Exception:
                continue
        
        return list(collections_found)

    def crawl(self, save_json=True):
        html = self.fetch_page(self.collections_page)
        
        if not html:
            return
        
        soup = self.parse_page(html)
        collections_data = self.extract_collections(soup)
        
        unique_collections = {}
        for name, url in collections_data:
            if url not in unique_collections:
                unique_collections[url] = name
        
        print(f"\nFound {len(unique_collections)} unique collections")
        
        for url, name in unique_collections.items():
            collection_item = {
                "name": name,
                "url": url
            }
            self.collections.append(collection_item)
            print(f"  - {name}")
        
        if save_json:
            os.makedirs("data/cache", exist_ok=True)
            with open("data/cache/collections.json", "w", encoding="utf-8") as f:
                json.dump(self.collections, f, ensure_ascii=False, indent=2)
            print(f"\nSaved {len(self.collections)} collections to data/cache/collections.json")

    def save_to_db(self, db_path=None):
        """Save collections to SQLite database"""
        db = ProductDatabase(db_path=db_path)
        print(f"\nSaving {len(self.collections)} collections to database...")
        
        for collection in self.collections:
            try:
                name = collection.get("name", "").strip()
                url = collection.get("url", "").strip()
                
                if name:
                    bst_id = db.get_or_create_bst(name, url)
                    print(f"{name} (ID: {bst_id})")
            except Exception as e:
                print(f"Error saving {collection.get('name')}: {e}")
        
        db.close()

if __name__ == "__main__":
    crawler = CollectionsCrawler()
    crawler.crawl(save_json=True)
    crawler.save_to_db()
