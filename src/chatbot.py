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

Nhìn ảnh này và trả lời bằng tiếng Việt:
- Nếu ảnh là sản phẩm Carpediem → xác nhận và cung cấp thông tin CHÍNH XÁC từ kết quả tìm kiếm: tên, giá, link mua, điểm nổi bật
- Nếu ảnh là không gian/phong cách → gợi ý sản phẩm phù hợp từ kết quả
- Nếu không tìm thấy sản phẩm khớp → nói lịch sự

KHÔNG bịa thông tin. Chỉ dùng dữ liệu từ kết quả tìm kiếm.

Kết quả tìm kiếm:
{results}
"""

    def __init__(self, model_name: str = None):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Thiếu OPENAI_API_KEY trong file .env")

        base_url = os.getenv("OPENAI_BASE_URL")
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
        self.rag = GraphRAG()
        self.history: List[Dict[str, str]] = []
        self.system_context = (
            "Bạn là trợ lý AI cho thương hiệu Carpediem - chuyên về nến thơm, "
            "tinh dầu, đá thơm và giftset cao cấp tại Việt Nam. "
            "Website: https://carpediem.vn"
        )

    def close(self):
        self.rag.close()

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

    def classify_intent(self, query: str) -> str:
        prompt = self.INTENT_PROMPT.format(query=query)
        response = self._call_openai([{"role": "user", "content": prompt}])
        intent = response.strip().strip('"').strip("'").lower()
        if intent not in ("product_search", "general_qa", "image_analysis"):
            intent = "product_search"
        return intent

    def handle_product_search(self, query: str) -> tuple:
        results = self.rag.query(query, top_k=5)
        formatted = self.rag.get_product_context(results)
        prompt = self.PRODUCT_PROMPT.format(query=query, results=formatted)

        answer = self._call_openai([{"role": "user", "content": prompt}])

        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": answer})

        return answer, results

    def handle_general_qa(self, query: str) -> str:
        messages = [{"role": "system", "content": self.system_context}]

        for msg in self.history[-6:]:
            messages.append({
                "role": "assistant" if msg["role"] == "assistant" else "user",
                "content": msg["content"],
            })

        messages.append({"role": "user", "content": self.GENERAL_PROMPT.format(query=query)})

        answer = self._call_openai(messages)

        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": answer})

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

        prompt = self.IMAGE_PROMPT.format(results=formatted)
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
        self.history.append({"role": "user", "content": display_query})
        self.history.append({"role": "assistant", "content": answer})

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
        self.history = []

    def get_stats(self):
        try:
            with self.rag.driver.session() as session:
                product_count = session.run("MATCH (p:Product) RETURN count(p) AS cnt").single()["cnt"]
                category_count = session.run("MATCH (c:Category) RETURN count(c) AS cnt").single()["cnt"]
                return {"products": product_count, "categories": category_count, "chat_messages": len(self.history)}
        except Exception:
            return {"products": "N/A", "categories": "N/A", "chat_messages": len(self.history)}
