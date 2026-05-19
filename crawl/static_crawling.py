import requests
from bs4 import BeautifulSoup
import time
import json

class Crawler:
    def __init__(self):
        self.base_url = "https://carpediem.vn/collections/all"
        self.delay=5
        self.headers={
            "User-Agent": 
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
        }
        self.session=requests.Session()
        self.session.headers.update(
            self.headers
        )
        self.visited_urls=set()
        self.products=[]
        
    def fetch_page(self, url):
        try:
            if url in self.visited_urls:
                return None
            response=self.session.get(url, timeout=10)
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
    
    def extract_data(self, soup):
        products_elements = soup.select(".product-item-detail-title")
        for product in products_elements:
            try:
                h_tag = product.select_one("a")
                href = h_tag["href"]
                name = h_tag.text.strip()
                item = {"name": name, "url": href}
                self.products.append(item)
                print(item)
            except:
                continue
            
    def crawl(self, total=7):
        for page in range(1, total + 1):
            url = f"{self.base_url}?page={page}"
            html = self.fetch_page(url)
            if html:
                soup = self.parse_page(html)
                self.extract_data(soup)
            
    def save_json(self):
        with open("data/cache/product_details.json", "w", encoding="utf-8") as f:
            json.dump(self.products, f, ensure_ascii=False, indent=2)
            
if __name__ == "__main__":
    crawler = Crawler()
    crawler.crawl()
    crawler.save_json()