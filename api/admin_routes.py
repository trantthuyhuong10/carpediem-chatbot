import os
import sys
from typing import Optional

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.auth import check_password, generate_token, require_auth
from api import pipeline

router = APIRouter(prefix="/api/admin", tags=["admin"])

class LoginRequest(BaseModel):
    password: str

class PipelineRequest(BaseModel):
    total_pages: Optional[int] = 7
    batch_size: Optional[int] = 10
    max_products: Optional[int] = None

@router.post("/login")
async def login(request: LoginRequest):
    if not check_password(request.password):
        raise HTTPException(status_code=401, detail="Sai mật khẩu")
    token = generate_token()
    return {"token": token, "status": "ok"}

@router.get("/status")
async def get_pipeline_status(request: Request):
    await require_auth(request)
    return pipeline.get_status()

@router.post("/crawl")
async def trigger_crawl(request_data: PipelineRequest, request: Request):
    await require_auth(request)
    if any(s["running"] for s in pipeline.get_status().values()):
        raise HTTPException(status_code=400, detail="Đang có pipeline khác đang chạy")
    return pipeline.run_pipeline_async("crawl", total_pages=request_data.total_pages)

@router.post("/crawl-details")
async def trigger_crawl_details(request_data: PipelineRequest, request: Request):
    await require_auth(request)
    if any(s["running"] for s in pipeline.get_status().values()):
        raise HTTPException(status_code=400, detail="Đang có pipeline khác đang chạy")
    return pipeline.run_pipeline_async("crawl_details", max_products=request_data.max_products)

@router.post("/chunk")
async def trigger_chunking(request_data: PipelineRequest, request: Request):
    await require_auth(request)
    
    current_status = pipeline.get_status()
    
    running_pipelines = [name for name, s in current_status.items() if s["running"]]
    
    if any(s["running"] for s in current_status.values()):
        raise HTTPException(
            status_code=400, 
        )
    
    return pipeline.run_pipeline_async("chunking", batch_size=request_data.batch_size)

@router.post("/embed")
async def trigger_embedding(request: Request):
    await require_auth(request)
    if any(s["running"] for s in pipeline.get_status().values()):
        raise HTTPException(status_code=400, detail="Đang có pipeline khác đang chạy")
    return pipeline.run_pipeline_async("embedding")

@router.post("/run-full-pipeline")
async def trigger_full_pipeline(request_data: PipelineRequest, request: Request):
    await require_auth(request)
    if any(s["running"] for s in pipeline.get_status().values()):
        raise HTTPException(status_code=400, detail="Đang có pipeline khác đang chạy")
    return pipeline.run_pipeline_async(
        "full_pipeline",
        total_pages=request_data.total_pages,
        batch_size=request_data.batch_size,
    )

@router.get("/products")
async def get_products(request: Request):
    await require_auth(request)
    try:
        from src.graph_rag import GraphRAG
        rag = GraphRAG()
        with rag.driver.session() as session:
            result = session.run("""
                MATCH (p:Product)
                OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
                RETURN p.name AS name, p.price AS price, p.url AS url,
                       p.description AS description, p.original_price AS original_price,
                       p.discount AS discount,
                       collect(DISTINCT c.name) AS categories
                ORDER BY p.name
            """)
            products = [dict(r) for r in result]
        rag.close()
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/products/{product_name}")
async def delete_product(product_name: str, request: Request):
    await require_auth(request)
    try:
        from src.graph_rag import GraphRAG
        rag = GraphRAG()
        with rag.driver.session() as session:
            session.run("MATCH (p:Product {name: $name}) DETACH DELETE p", name=product_name)
        rag.close()
        return {"status": "ok", "message": f"Đã xóa sản phẩm: {product_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions")
async def get_all_sessions(request: Request):
    await require_auth(request)
    try:
        bot = request.app.state.bot
        sessions = bot.memory.list_recent_sessions(limit=100)
        result = []
        for s in sessions:
            messages = bot.memory.get_recent_messages(s["id"], limit=1)
            title = "Cuộc hội thoại mới"
            if messages:
                first_msg = messages[0]["content"]
                title = first_msg[:50] + ("..." if len(first_msg) > 50 else "")
            result.append({
                "id": s["id"],
                "title": title,
                "created_at": s["created_at"],
                "updated_at": s["updated_at"],
                "message_count": s["message_count"],
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    await require_auth(request)
    try:
        bot = request.app.state.bot
        bot.memory.delete_session(session_id)
        return {"status": "ok", "message": "Đã xóa session"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_admin_stats(request: Request):
    await require_auth(request)
    try:
        bot = request.app.state.bot
        bot_stats = bot.get_stats()

        import json
        products_count = 0
        try:
            with open("data/cache/product_details.json", "r", encoding="utf-8") as f:
                products = json.load(f)
                products_count = len(products)
        except:
            pass

        import os
        chunks_count = 0
        chunks_dir = "data/chunks"
        if os.path.exists(chunks_dir):
            chunks_count = len([f for f in os.listdir(chunks_dir) if f.endswith(".json")])

        embeddings_count = 0
        try:
            with open("data/embeddings/products_metadata.json", "r", encoding="utf-8") as f:
                embeddings = json.load(f)
                embeddings_count = len(embeddings)
        except:
            pass

        return {
            "products_in_cache": products_count,
            "chunks": chunks_count,
            "embeddings": embeddings_count,
            "neo4j_products": bot_stats.get("products", 0),
            "total_sessions": bot_stats.get("session_messages", 0),
            "current_session_messages": bot_stats.get("session_messages", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
