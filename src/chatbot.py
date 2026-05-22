import os
import json
import re
import base64
import time
import requests
from typing import List, Dict, Optional
from io import BytesIO
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

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
        self.memory = MemoryStore()
        self.session_id = self.memory.load_or_create_session()
        self.system_context = (
            "Bạn là trợ lý AI cho thương hiệu Carpediem - chuyên về nến thơm, "
            "tinh dầu, đá thơm và giftset cao cấp tại Việt Nam. "
            "Website: https://carpediem.vn"
        )

    def close(self):
        self.rag.close()
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
        messages = self.memory.get_recent_messages(self.session_id, limit=self.max_turns * 2)
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

    def classify_intent(self, query: str) -> str:
        prompt = self.INTENT_PROMPT.format(query=query)
        response = self._call_openai([{"role": "user", "content": prompt}])
        intent = response.strip().strip('"').strip("'").lower()
        if intent not in ("product_search", "general_qa", "image_analysis"):
            intent = "product_search"
        return intent

    def handle_product_search(self, query: str) -> tuple:
        resolved_query = self._resolve_contextual_query(query)
        results = self.rag.query(resolved_query, top_k=5)
        formatted = self.rag.get_product_context(results)
        context = self._build_conversation_context()
        prompt = self.PRODUCT_PROMPT.format(query=query, results=formatted, conversation_context=context)

        answer = self._call_openai([{"role": "user", "content": prompt}])

        self._save_turn(query, answer)

        return answer, results

    def handle_general_qa(self, query: str) -> str:
        context = self._build_conversation_context()
        messages = [{"role": "system", "content": self.system_context}]

        messages.append({"role": "user", "content": self.GENERAL_PROMPT.format(query=query, conversation_context=context)})

        answer = self._call_openai(messages)

        self._save_turn(query, answer)

        return answer

    def _image_to_base64(self, image: Image.Image) -> str:
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode()

    def handle_image(self, image_data, query: str = "") -> tuple:
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

        if results:
            formatted = self.rag.get_product_context(results)
        else:
            formatted = "Không tìm thấy sản phẩm khớp trong database."

        context = self._build_conversation_context()
        prompt = self.IMAGE_PROMPT.format(results=formatted, conversation_context=context)
        if query:
            prompt += f"\n\nNgười dùng hỏi: {query}"

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]
        }]

        answer = self._call_openai(messages)

        display_query = query if query else "Phân tích ảnh"
        self._save_turn(display_query, answer)

        return answer, results

    def chat(self, message: str, image=None) -> tuple:
        message = message.strip()
        if not message and image is None:
            return "Vui lòng nhập câu hỏi hoặc gửi ảnh.", []

        if image is not None:
            answer, results = self.handle_image(image, message)
            return answer, results

        intent = self.classify_intent(message)

        if intent == "product_search":
            answer, results = self.handle_product_search(message)
            return answer, results
        elif intent == "image_analysis":
            return "Bạn muốn phân tích ảnh? Vui lòng gửi kèm ảnh nhé.", []
        else:
            answer = self.handle_general_qa(message)
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
