import os
import sys
import json
import time
import threading
from typing import Dict, Optional

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from crawl.static_crawling import Crawler
from crawl.static_crawling_details import DetailCrawler
from crawl.product_db import ProductDatabase
from processing.chunking import DataChunker
from processing.embedding import EmbeddingPipeline

_pipeline_status: Dict[str, dict] = {
    "crawl": {"running": False, "progress": 0, "message": "", "last_run": None, "result": None},
    "crawl_details": {"running": False, "progress": 0, "message": "", "last_run": None, "result": None},
    "chunking": {"running": False, "progress": 0, "message": "", "last_run": None, "result": None},
    "embedding": {"running": False, "progress": 0, "message": "", "last_run": None, "result": None},
    "full_pipeline": {"running": False, "progress": 0, "message": "", "last_run": None, "result": None},
}

_lock = threading.Lock()

def _update_status(step: str, running: bool = None, progress: int = None, message: str = None, result: dict = None):
    with _lock:
        status = _pipeline_status[step]
        if running is not None:
            status["running"] = running
        if progress is not None:
            status["progress"] = progress
        if message is not None:
            status["message"] = message
        if result is not None:
            status["result"] = result
            status["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")

def get_status(step: str = None) -> dict:
    if step:
        return _pipeline_status.get(step, {})
    return dict(_pipeline_status)

def run_crawl(total_pages: int = 7) -> dict:
    try:
        _update_status("crawl", running=True, progress=10, message="Đang crawl danh sách sản phẩm...")
        crawler = Crawler()
        crawler.crawl(total=total_pages)
        crawler.save_json()

        with open("data/cache/product_details.json", "r", encoding="utf-8") as f:
            products = json.load(f)

        _update_status("crawl", running=False, progress=100, message=f"Đã crawl {len(products)} sản phẩm", result={"products_count": len(products)})
        return {"status": "ok", "products_count": len(products)}
    except Exception as e:
        _update_status("crawl", running=False, progress=0, message=f"Lỗi: {str(e)}")
        return {"status": "error", "error": str(e)}

def run_crawl_details(max_products: int = None) -> dict:
    try:
        _update_status("crawl_details", running=True, progress=10, message="Đang crawl chi tiết sản phẩm...")

        with open("data/cache/product_details.json", "r", encoding="utf-8") as f:
            products = json.load(f)

        crawler = DetailCrawler()
        crawler.crawl_details(products, max_products=max_products)
        crawler.save_json("data/cache/product_details.json")
        db = ProductDatabase()
        db.load_items(crawler.products_details)
        db.close()

        with open("data/cache/product_details.json", "r", encoding="utf-8") as f:
            details = json.load(f)

        _update_status("crawl_details", running=False, progress=100, message=f"Đã crawl chi tiết {len(details)} sản phẩm", result={"details_count": len(details)})
        return {"status": "ok", "details_count": len(details)}
    except Exception as e:
        _update_status("crawl_details", running=False, progress=0, message=f"Lỗi: {str(e)}")
        return {"status": "error", "error": str(e)}

def run_chunking(batch_size: int = 10) -> dict:
    try:
        _update_status("chunking", running=True, progress=10, message="Đang chia nhỏ dữ liệu...")
        chunker = DataChunker()
        result = chunker.run(batch_size=batch_size)
        _update_status("chunking", running=False, progress=100, message=f"Đã tạo {result['total_chunks']} chunks từ {result['total_products']} sản phẩm", result=result)
        return {"status": "ok", **result}
    except Exception as e:
        _update_status("chunking", running=False, progress=0, message=f"Lỗi: {str(e)}")
        return {"status": "error", "error": str(e)}

def run_embedding() -> dict:
    try:
        _update_status("embedding", running=True, progress=10, message="Đang tạo embeddings...")
        pipeline = EmbeddingPipeline()
        result = pipeline.run()
        _update_status("embedding", running=False, progress=100, message=f"Đã tạo embeddings cho {result['total_products']} sản phẩm", result=result)
        return {"status": "ok", **result}
    except Exception as e:
        _update_status("embedding", running=False, progress=0, message=f"Lỗi: {str(e)}")
        return {"status": "error", "error": str(e)}

def run_full_pipeline(total_pages: int = 7, batch_size: int = 10) -> dict:
    try:
        _update_status("full_pipeline", running=True, progress=5, message="Bắt đầu pipeline đầy đủ...")

        _update_status("full_pipeline", progress=10, message="Bước 1/4: Crawl danh sách sản phẩm...")
        crawl_result = run_crawl(total_pages)
        if crawl_result.get("status") != "ok":
            raise Exception(f"Crawl failed: {crawl_result.get('error')}")

        _update_status("full_pipeline", progress=30, message="Bước 2/4: Crawl chi tiết sản phẩm...")
        details_result = run_crawl_details()
        if details_result.get("status") != "ok":
            raise Exception(f"Crawl details failed: {details_result.get('error')}")

        _update_status("full_pipeline", progress=50, message="Bước 3/4: Chunking dữ liệu...")
        chunk_result = run_chunking(batch_size)
        if chunk_result.get("status") != "ok":
            raise Exception(f"Chunking failed: {chunk_result.get('error')}")

        _update_status("full_pipeline", progress=70, message="Bước 4/4: Tạo embeddings...")
        embed_result = run_embedding()
        if embed_result.get("status") != "ok":
            raise Exception(f"Embedding failed: {embed_result.get('error')}")

        _update_status("full_pipeline", running=False, progress=100, message="Pipeline hoàn tất!", result={
            "crawl": crawl_result,
            "details": details_result,
            "chunking": chunk_result,
            "embedding": embed_result,
        })
        return {"status": "ok", "message": "Pipeline hoàn tất"}
    except Exception as e:
        _update_status("full_pipeline", running=False, progress=0, message=f"Lỗi: {str(e)}")
        return {"status": "error", "error": str(e)}

def run_pipeline_async(step: str, **kwargs):
    def _run():
        if step == "crawl":
            run_crawl(**kwargs)
        elif step == "crawl_details":
            run_crawl_details(**kwargs)
        elif step == "chunking":
            run_chunking(**kwargs)
        elif step == "embedding":
            run_embedding()
        elif step == "full_pipeline":
            run_full_pipeline(**kwargs)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "step": step}
