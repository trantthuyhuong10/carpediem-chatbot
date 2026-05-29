import os
import sys
import base64
from io import BytesIO
from pathlib import Path

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from src.chatbot import ChatBot
from src.storage import MinioStorage
from api.models import ChatRequest, ChatResponse, StatsResponse, HealthResponse, ProductResult, SessionInfo, MessageItem
from fastapi.security import HTTPBearer
from api.admin_routes import router as admin_router

app = FastAPI(title="Carpediem", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bot: ChatBot = None
storage: MinioStorage = None

static_dir = Path(project_root) / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(admin_router)
security = HTTPBearer()

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title="Pipeline API",
        version="1.0.0",
        routes=app.routes,
    )
    
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer"
        }
    }
    
    # Auto-apply security to all /api/admin/* endpoints
    for path, methods in openapi_schema["paths"].items():
        if path.startswith("/api/admin") and path != "/api/admin/login":
            for method in methods.values():
                if isinstance(method, dict):
                    method["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.on_event("startup")
async def startup():
    global bot, storage
    try:
        bot = ChatBot()
        app.state.bot = bot
        print("[OK] ChatBot initialized")
    except Exception as e:
        print(f"[ERROR] ChatBot init failed: {e}")
        raise
    try:
        storage = MinioStorage()
        app.state.storage = storage
    except Exception as e:
        print(f"[WARN] MinIO init failed: {e}")


@app.get("/")
async def serve_frontend():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/admin")
async def serve_admin():
    return FileResponse(str(static_dir / "admin.html"))


@app.on_event("shutdown")
async def shutdown():
    global bot
    if bot:
        bot.close()
        print("[OK] ChatBot closed")


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    neo4j_status = "ok"
    rag_status = "ok"
    try:
        stats = bot.get_stats()
        neo4j_status = "ok"
    except Exception:
        neo4j_status = "error"
        rag_status = "error"
    return HealthResponse(status="healthy", neo4j=neo4j_status, graph_rag=rag_status)


def _resolve_product_images(results):
    s = getattr(app.state, "storage", None)
    if not s or not s.available:
        return results
    for r in results:
        img = r.get("image", "")
        if s.is_minio_key(img):
            r["image"] = s.resolve(img, expires=7200)
    return results


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message and not request.image:
        raise HTTPException(status_code=400, detail="message or image is required")

    try:
        if request.session_id:
            bot.load_session(request.session_id)
        elif bot.get_session_id() is None:
            pass

        image_data = None
        if request.image:
            if request.image.startswith(("http://", "https://")):
                image_data = request.image
            elif request.image.startswith("data:"):
                image_data = request.image
            else:
                try:
                    decoded = base64.b64decode(request.image)
                    image_data = decoded
                except Exception:
                    image_data = request.image

        answer, results = bot.chat(request.message, image=image_data)
        results = _resolve_product_images(results)

        product_results = []
        for r in results:
            product_results.append(ProductResult(
                name=r.get("name", ""),
                price=r.get("price", ""),
                original_price=r.get("original_price", ""),
                discount=r.get("discount", ""),
                url=r.get("url", ""),
                image=r.get("image", ""),
                score=r.get("score", 0),
                categories=r.get("categories", []),
            ))

        return ChatResponse(answer=answer, results=product_results, session_id=bot.get_session_id())
    except Exception as e:
        request_id = os.urandom(4).hex()
        print(f"[API][chat][{request_id}] ERROR: {e}")
        fallback_answer = (
            "Xin lỗi, hệ thống đang bận hoặc gặp lỗi tạm thời nên chưa trả lời được. "
            "Bạn vui lòng thử lại sau ít giây, hoặc đặt câu hỏi ngắn gọn hơn."
        )
        return ChatResponse(answer=fallback_answer, results=[], session_id=bot.get_session_id() if bot else "")


@app.post("/api/chat/upload", response_model=ChatResponse)
async def chat_with_upload(message: str = Form(""), image: UploadFile = File(None)):
    try:
        image_data = None
        if image:
            image_data = await image.read()

        answer, results = bot.chat(message, image=image_data)
        results = _resolve_product_images(results)

        product_results = []
        for r in results:
            product_results.append(ProductResult(
                name=r.get("name", ""),
                price=r.get("price", ""),
                original_price=r.get("original_price", ""),
                discount=r.get("discount", ""),
                url=r.get("url", ""),
                image=r.get("image", ""),
                score=r.get("score", 0),
                categories=r.get("categories", []),
            ))

        return ChatResponse(answer=answer, results=product_results)
    except Exception as e:
        request_id = os.urandom(4).hex()
        print(f"[API][chat_upload][{request_id}] ERROR: {e}")
        fallback_answer = (
            "Xin lỗi, hệ thống đang bận hoặc gặp lỗi tạm thời nên chưa trả lời được. "
            "Bạn vui lòng thử lại sau ít giây, hoặc đặt câu hỏi ngắn gọn hơn."
        )
        return ChatResponse(answer=fallback_answer, results=[], session_id=bot.get_session_id() if bot else "")


@app.post("/api/reset")
async def reset_chat():
    try:
        bot.reset_history()
        return {"status": "ok", "message": "Chat history cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    try:
        stats = bot.get_stats()
        return StatsResponse(
            products=stats["products"],
            categories=stats["categories"],
            chat_messages=stats["session_messages"],
            session_id=stats.get("session_id", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def list_sessions():
    try:
        sessions = bot.list_sessions(limit=50)
        result = []
        for s in sessions:
            messages = bot.memory.get_recent_messages(s["id"], limit=1)
            title = "Cuộc hội thoại mới"
            if messages:
                first_msg = messages[0]["content"]
                title = first_msg[:50] + ("..." if len(first_msg) > 50 else "")
            result.append(SessionInfo(
                id=s["id"],
                title=title,
                created_at=s["created_at"],
                updated_at=s["updated_at"],
                message_count=s["message_count"],
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions")
async def create_session():
    try:
        session_id = bot.memory.create_session()
        return {"session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
async def get_session_messages(session_id: str):
    try:
        messages = bot.memory.get_recent_messages(session_id, limit=200)
        if not messages:
            return []

        result = []
        for msg in messages:
            result.append(MessageItem(
                role=msg["role"],
                content=msg["content"],
                created_at=msg.get("created_at", ""),
                results=[],
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        bot.memory.delete_session(session_id)
        if bot.get_session_id() == session_id:
            bot.session_id = bot.memory.create_session()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
