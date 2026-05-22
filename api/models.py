from pydantic import BaseModel
from typing import Optional, List


class ProductResult(BaseModel):
    name: str
    price: str
    original_price: Optional[str] = ""
    discount: Optional[str] = ""
    url: str
    image: str
    score: float
    categories: List[str]


class ChatRequest(BaseModel):
    message: str
    image: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    results: List[ProductResult]
    session_id: str = ""


class StatsResponse(BaseModel):
    products: int | str
    categories: int | str
    chat_messages: int
    session_id: str = ""


class HealthResponse(BaseModel):
    status: str
    neo4j: str
    graph_rag: str


class SessionInfo(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class MessageItem(BaseModel):
    role: str
    content: str
    created_at: str
    results: Optional[List[ProductResult]] = []
