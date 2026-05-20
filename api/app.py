import os
import sys
import base64
from io import BytesIO

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from src.chatbot import ChatBot
from api.models import ChatRequest, ChatResponse, StatsResponse, HealthResponse, ProductResult

app = FastAPI(title="Carpediem", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bot: ChatBot = None

@app.on_event("startup")
async def startup():
    global bot
    try:
        bot = ChatBot()
        print("[OK] ChatBot initialized")
    except Exception as e:
        print(f"[ERROR] ChatBot init failed: {e}")
        raise


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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message and not request.image:
        raise HTTPException(status_code=400, detail="message or image is required")

    try:
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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/upload", response_model=ChatResponse)
async def chat_with_upload(message: str = Form(""), image: UploadFile = File(None)):
    try:
        image_data = None
        if image:
            image_data = await image.read()

        answer, results = bot.chat(message, image=image_data)

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
        raise HTTPException(status_code=500, detail=str(e))


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
            chat_messages=stats["chat_messages"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
