import os
import json
import re
import base64
from typing import List, Dict, Optional
from io import BytesIO
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

from src.graph_rag import GraphRAG

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

Người dùng hỏi: {query}

Kết quả tìm kiếm được:
{results}

Hãy trả lời bằng tiếng Việt:
- Thân thiện, chuyên nghiệp, ngắn gọn
- Liệt kê sản phẩm gợi ý kèm tên, giá, điểm nổi bật
- Nếu không có sản phẩm phù hợp, nói lịch sự và gợi ý người dùng mô tả cụ thể hơn
- KHÔNG bịa thông tin sản phẩm, chỉ dùng dữ liệu trên
"""

    GENERAL_PROMPT = """Bạn là trợ lý AI cho thương hiệu Carpediem - chuyên về nến thơm, tinh dầu, đá thơm và giftset cao cấp tại Việt Nam.

Thông tin về Carpediem:
- Thương hiệu nến thơm và sản phẩm mùi hương Việt Nam
- Sản phẩm: nến thơm, tinh dầu, đá thơm khuếch hương, giftset quà tặng
- Website: https://carpediem.vn

Người dùng hỏi: {query}

Trả lời bằng tiếng Việt, thân thiện, chuyên nghiệp.
Nếu câu hỏi không liên quan đến Carpediem hoặc sản phẩm mùi hương, vẫn trả lời lịch sự nhưng khéo léo hướng về thương hiệu nếu có thể.
Nếu không biết câu trả lời, nói thẳng là không rõ và gợi ý liên hệ Carpediem để được hỗ trợ.
"""

    IMAGE_PROMPT = """Bạn là trợ lý AI cho thương hiệu Carpediem - chuyên về nến thơm, tinh dầu, đá thơm và giftset cao cấp tại Việt Nam.

Hãy phân tích ảnh này và trả lời bằng tiếng Việt:
- Mô tả ngắn gọn nội dung ảnh
- Nếu ảnh liên quan đến không gian, phong cách, hoặc mood → gợi ý sản phẩm Carpediem phù hợp
- Nếu ảnh là sản phẩm Carpediem → nhận diện và cung cấp thông tin
- Nếu ảnh không liên quan → trả lời lịch sự, vui vẻ

Sản phẩm hiện có trong kho:
{products}
"""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("lỗi")
        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel(model_name)
        self.rag = GraphRAG()
        self.history: List[Dict[str, str]] = []
        self.system_context = (
            "Bạn là trợ lý AI cho thương hiệu Carpediem - chuyên về nến thơm, "
            "tinh dầu, đá thơm và giftset cao cấp tại Việt Nam. "
            "Website: https://carpediem.vn"
        )

    def close(self):
        self.rag.close()

    def classify_intent(self, query: str) -> str:
        prompt = self.INTENT_PROMPT.format(query=query)
        response = self.model.generate_content(prompt)
        intent = response.text.strip().strip('"').strip("'").lower()
        if intent not in ("product_search", "general_qa", "image_analysis"):
            intent = "product_search"
        return intent

    def _get_all_products_summary(self) -> str:
        all_products = self.rag.query("", top_k=51)
        lines = []
        for p in all_products:
            cats = ", ".join(p.get("categories", []))
            lines.append(f"- {p['name']} ({p.get('price', '')}) - {cats}")
        return "\n".join(lines)

    def handle_product_search(self, query: str) -> str:
        results = self.rag.query(query, top_k=5)
        formatted = self.rag.get_product_context(results)
        prompt = self.PRODUCT_PROMPT.format(query=query, results=formatted)

        chat = self.model.start_chat(history=[])
        response = chat.send_message(prompt)
        answer = response.text.strip()

        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": answer})

        return answer, results

    def handle_general_qa(self, query: str) -> str:
        prompt = self.GENERAL_PROMPT.format(query=query)

        history_for_context = []
        for msg in self.history[-6:]:
            history_for_context.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [msg["content"]],
            })

        chat = self.model.start_chat(history=history_for_context)
        response = chat.send_message(prompt)
        answer = response.text.strip()

        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": answer})

        return answer

    def handle_image(self, image_data, query: str = "") -> str:
        if isinstance(image_data, bytes):
            image = Image.open(BytesIO(image_data))
        elif isinstance(image_data, str):
            if image_data.startswith("data:"):
                header, encoded = image_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                image = Image.open(BytesIO(image_bytes))
            else:
                image = Image.open(image_data)
        elif isinstance(image_data, Image.Image):
            image = image_data
        else:
            return "lỗi ảnh"

        products_summary = self._get_all_products_summary()
        text_prompt = self.IMAGE_PROMPT.format(products=products_summary)
        if query:
            text_prompt += f"\n\nUser: {query}"

        response = self.model.generate_content([text_prompt, image])
        answer = response.text.strip()

        display_query = query if query else "Phân tích ảnh"
        self.history.append({"role": "user", "content": display_query})
        self.history.append({"role": "assistant", "content": answer})

        return answer

    def chat(self, message: str, image=None) -> tuple:
        message = message.strip()
        if not message and image is None:
            return "lỗi nhập", []

        if image is not None:
            answer = self.handle_image(image, message)
            return answer, []

        if not message:
            return self.handle_image(image), []

        intent = self.classify_intent(message)

        if intent == "product_search":
            answer, results = self.handle_product_search(message)
            return answer, results
        elif intent == "image_analysis":
            return "nhập ảnh", []
        else:
            answer = self.handle_general_qa(message)
            return answer, []

    def reset_history(self):
        self.history = []

    def get_stats(self):
        try:
            with self.rag.driver.session() as session:
                product_count = session.run("MATCH (p:Product) RETURN count(p) AS cnt").single()["cnt"]
                category_count = session.run("MATCH (c:Category) RETURN count(c) AS cnt").single()["cnt"]
                return {"products": product_count, "categories": category_count, "chat_messages": len(self.history)}
        except Exception:
            return {"products": "N/A", "categories": "N/A", "chat_messages": len(self.history)}
