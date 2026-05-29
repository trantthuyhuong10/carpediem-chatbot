import os
import json
import re
import base64
import time
import uuid
import requests
from typing import List, Dict, Optional
from io import BytesIO
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

from crawl.product_db import ProductDatabase
from src.graph_rag import GraphRAG
from src.memory_store import MemoryStore

load_dotenv()

class ChatBot:
    INTENT_PROMPT = """Phân loại câu hỏi sau thành 1 trong 3 loại:
- "product_search": hỏi về sản phẩm, gợi ý quà, tìm nến thơm/tinh dầu/giftset, hỏi giá, hỏi theo dịp/ngân sách
- "general_qa": hỏi thông tin chung, chính sách, giao hàng, thanh toán, giới thiệu thương hiệu, hoặc câu hỏi không liên quan sản phẩm
- "image_analysis": người dùng gửi kèm ảnh hoặc yêu cầu phân tích ảnh

Chỉ trả về đúng 1 từ khóa, không giải thích.

Câu hỏi: {query}
"""

    PRODUCT_PROMPT = """Bạn là trợ lý AI cho thương hiệu Carpediem - chuyên về nến thơm, tinh dầu, đá thơm và giftset cao cấp tại Việt Nam.

{conversation_context}

Người dùng hỏi: {query}

Kết quả tìm kiếm được:
{results}

Hãy trả lời bằng tiếng Việt:
- Thân thiện, chuyên nghiệp, ngắn gọn
- Liệt kê sản phẩm gợi ý kèm tên, giá, điểm nổi bật
- Nếu không có sản phẩm phù hợp, nói lịch sự và gợi ý người dùng mô tả cụ thể hơn
- KHÔNG bịa thông tin sản phẩm, chỉ dùng dữ liệu trên
- Nếu người dùng hỏi follow-up về sản phẩm đã đề cập trước đó, trả lời dựa trên context và kết quả tìm kiếm
"""

    GENERAL_PROMPT = """Bạn là trợ lý AI cho thương hiệu Carpediem - chuyên về nến thơm, tinh dầu, đá thơm và giftset cao cấp tại Việt Nam.

Thông tin về Carpediem:
- Thương hiệu nến thơm và sản phẩm mùi hương Việt Nam
- Sản phẩm: nến thơm, tinh dầu, đá thơm khuếch hương, giftset quà tặng
- Website: https://carpediem.vn

{conversation_context}

Người dùng hỏi: {query}

Trả lời bằng tiếng Việt, thân thiện, chuyên nghiệp.
Nếu câu hỏi không liên quan đến Carpediem hoặc sản phẩm mùi hương, vẫn trả lời lịch sự nhưng khéo léo hướng về thương hiệu nếu có thể.
Nếu không biết câu trả lời, nói thẳng là không rõ và gợi ý liên hệ Carpediem để được hỗ trợ.
"""

    IMAGE_PROMPT = """Bạn là trợ lý AI cho thương hiệu Carpediem - chuyên về nến thơm, tinh dầu, đá thơm và giftset cao cấp tại Việt Nam.

{conversation_context}

Nhìn ảnh này và trả lời bằng tiếng Việt:
- Nếu ảnh là sản phẩm Carpediem → xác nhận và cung cấp thông tin CHÍNH XÁC từ kết quả tìm kiếm: tên, giá, link mua, điểm nổi bật
- Nếu ảnh là không gian/phong cách → gợi ý sản phẩm phù hợp từ kết quả
- Nếu không tìm thấy sản phẩm khớp → nói lịch sự

KHÔNG bịa thông tin. Chỉ dùng dữ liệu từ kết quả tìm kiếm.

Kết quả tìm kiếm:
{results}
"""

    def __init__(self, model_name: str = None, max_turns: int = 5):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Thiếu OPENAI_API_KEY trong file .env")

        base_url = os.getenv("OPENAI_BASE_URL")
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.max_turns = max_turns

        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
        self.rag = GraphRAG()
        self.product_db = ProductDatabase()
        self.memory = MemoryStore()
        self.session_id = self.memory.load_or_create_session()
        self.system_context = (
            "Bạn là trợ lý AI cho thương hiệu Carpediem - chuyên về nến thơm, "
            "tinh dầu, đá thơm và giftset cao cấp tại Việt Nam. "
            "Website: https://carpediem.vn"
        )
        self.debug = os.getenv("CHATBOT_DEBUG", "1").lower() not in {"0", "false", "no", "off"}

    def _log(self, request_id: str, stage: str, message: str):
        if not self.debug:
            return
        print(f"[ChatBot][{request_id}][{stage}] {message}")

    def _summarize_results(self, results, top_n: int = 3) -> str:
        if not results:
            return "0 results"
        parts = []
        for item in results[:top_n]:
            name = item.get("name", "")
            score = item.get("score", 0)
            parts.append(f"{name}({score:.3f})")
        return f"{len(results)} results | top: " + ", ".join(parts)

    def close(self):
        self.rag.close()
        self.product_db.close()
        self.memory.close()

    def _call_openai(self, messages, max_retries=1):
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                error_str = str(e)
                if "429" in error_str and attempt < max_retries:
                    match = re.search(r'retry in ([\d.]+)s', error_str)
                    wait = int(float(match.group(1))) + 5 if match else 30
                    print(f"[OpenAI quota] Waiting {wait}s before retry...")
                    time.sleep(wait)
                else:
                    raise

    def _save_turn(self, user_msg: str, assistant_msg: str):
        stats = self.memory.get_session_stats(self.session_id)
        turn_number = (stats["message_count"] // 2) + 1 if stats else 1
        self.memory.save_turn(self.session_id, user_msg, assistant_msg, turn_number)

    def _build_conversation_context(self) -> str:
        max_messages = min(self.max_turns * 2, 6)
        messages = self.memory.get_recent_messages(self.session_id, limit=max_messages)
        if not messages:
            return ""
        context_lines = ["Lịch sử hội thoại gần đây:"]
        for msg in messages:
            role = "Bạn" if msg["role"] == "user" else "Trợ lý"
            content = msg["content"][:300]
            context_lines.append(f"- {role}: {content}")
        return "\n".join(context_lines)

    def _get_recent_products_from_history(self) -> List[str]:
        products = []
        messages = self.memory.get_recent_messages(self.session_id, limit=self.max_turns * 2)
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                matches = re.findall(r"(\d+)[\.\)]\s*([^\n\-–]+?)(?:\s*[\-–]|$)", msg["content"])
                for _, name in matches:
                    name = name.strip().rstrip(".,;:")
                    if name and len(name) > 2 and name not in products:
                        products.append(name)
            if len(products) >= 3:
                break
        return products

    def _resolve_contextual_query(self, query: str) -> str:
        pronouns = ["đó", "này", "kia", "nó", "cái đó", "cái này",
                    "sản phẩm đó", "món đó", "loại đó", "em đó",
                    "cái nào", "món nào", "loại nào"]
        has_pronoun = any(p in query.lower() for p in pronouns)
        if not has_pronoun:
            return query
        last_products = self._get_recent_products_from_history()
        if last_products:
            names = ", ".join(last_products[:2])
            return f"{query} (đang nói về: {names})"
        return query

    def _hydrate_results_from_db(self, results):
        if not results:
            return results
        names = [r.get("name", "").strip() for r in results if r.get("name")]
        db_items = self.product_db.get_products_by_names(names)
        db_map = {item["name"].strip().lower(): item for item in db_items}
        for r in results:
            key = r.get("name", "").strip().lower()
            if not key or key not in db_map:
                continue
            row = db_map[key]
            if row.get("price"):
                r["price"] = row["price"]
            if row.get("description"):
                r["description"] = row["description"]
            if row.get("image"):
                r["image"] = row["image"]
            if row.get("url"):
                r["url"] = row["url"]
        return results

    def _fallback_db_search(self, query: str, top_k: int = 5):
        items = self.product_db.search_items(query, top_k=top_k)
        if not items:
            return []
        formatted = []
        for item in items:
            formatted.append({
                "name": item.get("name", ""),
                "price": item.get("price", ""),
                "url": item.get("url", ""),
                "image": item.get("image", ""),
                "score": 0.0,
                "categories": [],
                "collections": [],
                "entities": [],
                "description": item.get("description", ""),
            })
        return formatted

    def classify_intent(self, query: str) -> str:
        lower_query = query.lower()
        image_keywords = ["ảnh", "hình", "photo", "image", "upload", "camera", "gửi ảnh"]
        product_keywords = [
            "nến", "tinh dầu", "giftset", "quà", "sinh nhật", "valentine", "8/3", "20/10",
            "giáng sinh", "tết", "giá", "mua", "link", "shop", "gợi ý", "tìm", "đề xuất",
            "phù hợp", "mẫu", "loại", "set quà", "quà tặng", "bán chạy", "ưu đãi", "sale"
        ]

        if any(keyword in lower_query for keyword in image_keywords):
            return "image_analysis"
        if any(keyword in lower_query for keyword in product_keywords):
            return "product_search"
        return "general_qa"

    def handle_product_search(self, query: str, request_id: str = "-") -> tuple:
        resolved_query = self._resolve_contextual_query(query)
        if resolved_query != query:
            self._log(request_id, "context", f"resolved contextual query: '{query}' -> '{resolved_query}'")

        results = self.rag.query(resolved_query, top_k=5)
        self._log(request_id, "retrieval", f"GraphRAG returned {self._summarize_results(results)}")

        results = self._hydrate_results_from_db(results)
        self._log(request_id, "hydrate", f"after SQLite hydration: {self._summarize_results(results)}")

        if not results:
            try:
                results = self._fallback_db_search(query, top_k=5)
                self._log(request_id, "fallback", f"fallback SQLite search used: {self._summarize_results(results)}")
            except Exception as e:
                self._log(request_id, "fallback_error", f"SQLite fallback failed: {e}")
                raise

        formatted = self.rag.get_product_context(results)
        context = self._build_conversation_context()
        prompt = self.PRODUCT_PROMPT.format(query=query, results=formatted, conversation_context=context)
        self._log(request_id, "prompt", f"product prompt built | context_chars={len(context)} | results_count={len(results)}")

        answer = self._call_openai([{"role": "user", "content": prompt}])
        self._log(request_id, "openai", f"answer generated | answer_chars={len(answer)}")

        self._save_turn(query, answer)
        self._log(request_id, "memory", "conversation turn saved")

        return answer, results

    def handle_general_qa(self, query: str, request_id: str = "-") -> str:
        context = self._build_conversation_context()
        messages = [{"role": "system", "content": self.system_context}]

        messages.append({"role": "user", "content": self.GENERAL_PROMPT.format(query=query, conversation_context=context)})
        self._log(request_id, "prompt", f"general prompt built | context_chars={len(context)}")

        answer = self._call_openai(messages)
        self._log(request_id, "openai", f"answer generated | answer_chars={len(answer)}")

        self._save_turn(query, answer)
        self._log(request_id, "memory", "conversation turn saved")

        return answer

    def _image_to_base64(self, image: Image.Image) -> str:
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode()

    def handle_image(self, image_data, query: str = "", request_id: str = "-") -> tuple:
        if isinstance(image_data, bytes):
            image = Image.open(BytesIO(image_data))
        elif isinstance(image_data, str):
            if image_data.startswith("data:"):
                header, encoded = image_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                image = Image.open(BytesIO(image_bytes))
            elif image_data.startswith(("http://", "https://")):
                resp = requests.get(image_data, timeout=10)
                resp.raise_for_status()
                image = Image.open(BytesIO(resp.content))
            else:
                image = Image.open(image_data)
        elif isinstance(image_data, Image.Image):
            image = image_data
        else:
            return "Không thể xử lý ảnh. Vui lòng gửi ảnh dưới dạng PNG, JPG hoặc JPEG.", []

        image = image.convert("RGB")
        image_b64 = self._image_to_base64(image)

        search_query = query if query else "nến thơm tinh dầu quà tặng"
        results = self.rag.query(search_query.strip(), top_k=5)
        self._log(request_id, "retrieval", f"image-mode retrieval for '{search_query}': {self._summarize_results(results)}")

        if results:
            formatted = self.rag.get_product_context(results)
        else:
            formatted = "Không tìm thấy sản phẩm khớp trong database."

        context = self._build_conversation_context()
        prompt = self.IMAGE_PROMPT.format(results=formatted, conversation_context=context)
        if query:
            prompt += f"\n\nNgười dùng hỏi: {query}"
        self._log(request_id, "prompt", f"image prompt built | context_chars={len(context)} | results_count={len(results)}")

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]
        }]

        answer = self._call_openai(messages)
        self._log(request_id, "openai", f"answer generated | answer_chars={len(answer)}")

        display_query = query if query else "Phân tích ảnh"
        self._save_turn(display_query, answer)
        self._log(request_id, "memory", "conversation turn saved")

        return answer, results

    def chat(self, message: str, image=None) -> tuple:
        request_id = uuid.uuid4().hex[:8]
        message = message.strip()
        self._log(request_id, "start", f"session={self.session_id} | has_image={image is not None} | message='{message[:120]}'")

        if not message and image is None:
            self._log(request_id, "reject", "empty message and no image")
            return "Vui lòng nhập câu hỏi hoặc gửi ảnh.", []

        if image is not None:
            answer, results = self.handle_image(image, message, request_id=request_id)
            self._log(request_id, "done", f"image flow complete: {self._summarize_results(results)}")
            return answer, results

        intent = self.classify_intent(message)
        self._log(request_id, "intent", f"classified='{intent}'")

        if intent == "product_search":
            answer, results = self.handle_product_search(message, request_id=request_id)
            self._log(request_id, "done", f"product flow complete: {self._summarize_results(results)}")
            return answer, results
        elif intent == "image_analysis":
            self._log(request_id, "done", "image intent detected without image payload")
            return "Bạn muốn phân tích ảnh? Vui lòng gửi kèm ảnh nhé.", []
        else:
            answer = self.handle_general_qa(message, request_id=request_id)
            self._log(request_id, "done", "general flow complete")
            return answer, []

    def reset_history(self):
        self.memory.delete_session(self.session_id)
        self.session_id = self.memory.create_session()

    def get_session_id(self) -> str:
        return self.session_id

    def list_sessions(self, limit: int = 10) -> List[Dict]:
        return self.memory.list_recent_sessions(limit)

    def load_session(self, session_id: str) -> bool:
        stats = self.memory.get_session_stats(session_id)
        if stats:
            self.session_id = session_id
            return True
        return False

    def get_session_id(self) -> str:
        return self.session_id

    def get_stats(self):
        try:
            with self.rag.driver.session() as session:
                product_count = session.run("MATCH (p:Product) RETURN count(p) AS cnt").single()["cnt"]
                category_count = session.run("MATCH (c:Category) RETURN count(c) AS cnt").single()["cnt"]
        except Exception:
            product_count = "N/A"
            category_count = "N/A"
        session_stats = self.memory.get_session_stats(self.session_id)
        return {
            "products": product_count,
            "categories": category_count,
            "session_id": self.session_id,
            "session_messages": session_stats["message_count"] if session_stats else 0,
        }
