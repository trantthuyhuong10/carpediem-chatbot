# Carpediem Chatbot

Đây là dự án xây dựng Chatbot - Trợ lý AI cho thương hiệu chuyên về mùi hương Carpediem, hỗ trợ tư vấn nến thơm, tinh dầu, đá thơm khuếch hương và giftset. Dự án kết hợp FastAPI, OpenAI API, Neo4j, FAISS và Sentence Transformers để xây dựng hệ thống chatbot có khả năng tìm kiếm sản phẩm theo ngữ nghĩa, gợi ý theo dịp/ngân sách, phân tích ảnh và lưu lịch sử hội thoại.

## Mục Lục

- [Tính năng chính](#tính-năng-chính)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt](#cài-đặt)
- [Cấu hình môi trường](#cấu-hình-môi-trường)
- [Chuẩn bị dữ liệu](#chuẩn-bị-dữ-liệu)
- [Chạy ứng dụng](#chạy-ứng-dụng)
- [API endpoints](#api-endpoints)
- [Admin dashboard](#admin-dashboard)
- [CLI demo](#cli-demo)
- [Troubleshooting](#troubleshooting)
- [Đóng góp](#đóng-góp)

## Tính Năng Chính

- Chatbot tư vấn sản phẩm bằng tiếng Việt cho thương hiệu Carpediem.
- Tìm kiếm sản phẩm bằng Graph RAG kết hợp FAISS vector search và Neo4j graph filtering.
- Gợi ý sản phẩm theo dịp như sinh nhật, Valentine, 8/3, 20/10, cưới hỏi, tân gia, Giáng sinh và Tết.
- Gợi ý theo ngân sách, danh mục và nội dung mô tả sản phẩm.
- Phân tích ảnh sản phẩm hoặc không gian để đề xuất sản phẩm phù hợp.
- Lưu lịch sử hội thoại theo session bằng SQLite.
- Web chat UI tĩnh phục vụ qua FastAPI.
- Admin dashboard để theo dõi dữ liệu, session và kích hoạt pipeline xử lý dữ liệu.
- Streamlit interface cho trải nghiệm demo độc lập.
- CLI demo cho kiểm thử nhanh trong terminal.

## Kiến Trúc Hệ Thống

```text
User
  |
  | Web UI / Streamlit / CLI
  v
FastAPI API Layer
  |
  |-- ChatBot Orchestrator
  |     |-- OpenAI Chat Completion
  |     |-- GraphRAG Retrieval
  |     |-- SQLite Memory Store
  |
  |-- Admin Pipeline
        |-- Crawl products
        |-- Crawl product details
        |-- Chunk product data
        |-- Generate embeddings
        |-- Build Neo4j graph

Data Layer
  |-- data/cache/product_details.json
  |-- data/chunks/*.json
  |-- data/embeddings/products.index
  |-- data/embeddings/products_metadata.json
  |-- data/carpediem_chat.db
  |-- Neo4j graph database
```

Luồng xử lý chat chính:

1. Người dùng gửi tin nhắn hoặc ảnh.
2. `ChatBot` phân loại intent thành `product_search`, `general_qa` hoặc `image_analysis`.
3. Với câu hỏi sản phẩm, hệ thống tìm kiếm bằng FAISS, lọc/enrich bằng Neo4j và lấy context sản phẩm liên quan.
4. OpenAI model sinh câu trả lời dựa trên prompt, lịch sử hội thoại và kết quả truy xuất.
5. Tin nhắn được lưu vào SQLite để hỗ trợ hội thoại nhiều lượt.

## Công Nghệ Sử Dụng

- Python 3.10+
- FastAPI và Uvicorn cho HTTP API.
- OpenAI Python SDK cho mô hình hội thoại và xử lý ảnh.
- Neo4j cho graph database sản phẩm, danh mục, collection, entity và quan hệ tương đồng.
- FAISS cho vector similarity search.
- Sentence Transformers với model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` để tạo embedding đa ngôn ngữ.
- SQLite cho lưu session và lịch sử chat.
- Streamlit cho giao diện demo.
- BeautifulSoup và Requests cho crawler.
- HTML, CSS, JS để xây dựng giao diện cho hệ thống.

## Cấu Trúc Thư Mục

```text
carpediem-mini-project/
├── api/                                # FastAPI app, models, auth, admin routes, pipeline API
│   ├── app.py                          # Entry point FastAPI
│   ├── admin_routes.py                 # API quản trị và pipeline
│   ├── auth.py                         # Xác thực admin bằng token
│   ├── models.py                       # Pydantic schemas
│   └── pipeline.py                     # Chạy crawl/chunk/embedding bất đồng bộ
├── crawl/                              # Crawler dữ liệu sản phẩm Carpediem
│   ├── static_crawling_details.py      # Crawl chi tiết sản phẩm từ url được crawl từ file static_crawling.py
│   └── static_crawling.py              # Crawl tên và link sản phẩm             
├── data/                               # Dữ liệu cache, chunks, embeddings và SQLite DB
│   ├── cache/
│   ├── chunks/
│   ├── embeddings/
│   └── carpediem_chat.db
├── interface/                          # Streamlit UI
├── processing/                         # Chunking và embedding pipeline
│   ├── chunking.py                     # Chunk dữ liệu
│   └── embedding.py                    # Embed các chunk
├── scripts/                            # Script demo CLI
├── src/                                 
│   ├── chatbot.py                      # Core chatbot
│   ├── graph_builder.py                # Neo4j builder
│   ├── graph_rag.py                    # Graph RAG
│   └── memory_store.py                     # memory store
├── static/                             # Web chat UI và admin UI tĩnh
├── requirements.txt                    # Python dependencies
└── README.md
```

## Yêu Cầu Hệ Thống

- Python 3.10 trở lên.
- Neo4j đang chạy và có thể truy cập từ máy local hoặc server.
- OpenAI API key hợp lệ.
- Kết nối Internet để tải model Sentence Transformers trong lần chạy đầu tiên.
- Dung lượng đủ cho dữ liệu embeddings và model cache.

## Cài Đặt

Clone repository và di chuyển vào thư mục dự án:

```bash
git clone <repository-url>
cd carpediem-chatbot
```

Tạo virtual environment:

```bash
python -m venv venv
```

Kích hoạt virtual environment trên Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Kích hoạt virtual environment trên macOS/Linux:

```bash
source venv/bin/activate
```

Cài đặt dependencies:

```bash
pip install -r requirements.txt
```

## Cấu Hình Môi Trường

Tạo file `.env` tại root của dự án:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

ADMIN_PASSWORD=your_admin_password
```

Ý nghĩa các biến môi trường:

| Biến | Bắt buộc | Mô tả |
| --- | --- | --- |
| `OPENAI_API_KEY` | Có | API key dùng để gọi OpenAI Chat Completion. |
| `OPENAI_MODEL` | Không | Model hội thoại, mặc định là `gpt-4o-mini`. |
| `OPENAI_BASE_URL` | Không | Base URL tùy chỉnh nếu dùng gateway hoặc provider tương thích OpenAI. |
| `NEO4J_URI` | Có | URI kết nối Neo4j, ví dụ `bolt://localhost:7687`. |
| `NEO4J_USER` | Có | Username Neo4j. |
| `NEO4J_PASSWORD` | Có | Password Neo4j. |
| `ADMIN_PASSWORD` | Có nếu dùng admin | Mật khẩu đăng nhập trang admin. |

Không commit file `.env` vì file này chứa thông tin nhạy cảm.

## Chuẩn Bị Dữ Liệu

Dự án cần các dữ liệu sau để chatbot truy xuất sản phẩm:

- `data/cache/product_details.json`: dữ liệu sản phẩm đã crawl.
- `data/chunks/*.json`: dữ liệu sản phẩm đã chia chunk.
- `data/embeddings/products.index`: FAISS index.
- `data/embeddings/products_metadata.json`: metadata tương ứng với vector index.
- Neo4j graph chứa node `Product`, `Category`, `Collection`, `Entity` và relationship liên quan.

Nếu dữ liệu đã có sẵn trong thư mục `data/`, bạn có thể bỏ qua bước crawl/chunk/embedding và chỉ cần đảm bảo Neo4j đã được build.

Chạy từng bước pipeline bằng Python:

```bash
python crawl/static_crawling.py
python crawl/static_crawling_details.py
python processing/chunking.py
python processing/embedding.py
python src/graph_builder.py
```

Hoặc chạy pipeline qua Admin API sau khi khởi động FastAPI:

```http
POST /api/admin/run-full-pipeline
```

Lưu ý: `run-full-pipeline` hiện thực hiện crawl, crawl details, chunking và embedding. Sau khi tạo embedding, nếu cần đồng bộ Neo4j graph đầy đủ, chạy thêm:

```bash
python src/graph_builder.py
```

## Chạy Ứng Dụng

### FastAPI Web App

Khởi động API server:

```bash
uvicorn api.app:app --reload
```

Sau khi server chạy, truy cập:

- Web chat UI: `http://localhost:8000/`
- Admin UI: `http://localhost:8000/admin`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`

### Streamlit Interface

Chạy giao diện Streamlit:

```bash
streamlit run interface/app.py
```

### CLI Demo

Chạy chatbot trong terminal:

```bash
python scripts/demo_cli.py
```

Các lệnh CLI hỗ trợ:

| Lệnh | Mô tả |
| --- | --- |
| `/help` | Hiển thị danh sách lệnh. |
| `/stats` | Xem thống kê graph database. |
| `/reset` | Xóa lịch sử chat hiện tại. |
| `/image <path>` | Gửi ảnh để phân tích. |
| `/exit` | Thoát CLI. |

## API Endpoints

### Public Chat API

| Method | Endpoint | Mô tả |
| --- | --- | --- |
| `GET` | `/` | Trả về web chat UI. |
| `GET` | `/admin` | Trả về admin UI. |
| `GET` | `/api/health` | Kiểm tra trạng thái app, Neo4j và Graph RAG. |
| `POST` | `/api/chat` | Gửi tin nhắn hoặc ảnh dạng URL/base64/data URL. |
| `POST` | `/api/chat/upload` | Gửi tin nhắn kèm file ảnh multipart. |
| `POST` | `/api/reset` | Xóa lịch sử chat hiện tại. |
| `GET` | `/api/stats` | Lấy thống kê sản phẩm, danh mục và session. |
| `GET` | `/api/sessions` | Danh sách session gần đây. |
| `POST` | `/api/sessions` | Tạo session mới. |
| `GET` | `/api/sessions/{session_id}` | Lấy tin nhắn của session. |
| `DELETE` | `/api/sessions/{session_id}` | Xóa session. |

Ví dụ gọi chat API:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Gợi ý nến thơm làm quà sinh nhật dưới 500k\"}"
```

Payload mẫu:

```json
{
  "message": "Gợi ý nến thơm làm quà sinh nhật dưới 500k",
  "image": null,
  "session_id": null
}
```

Response mẫu:

```json
{
  "answer": "...",
  "results": [
    {
      "name": "Tên sản phẩm",
      "price": "350.000đ",
      "url": "https://carpediem.vn/...",
      "image": "https://...",
      "score": 0.82,
      "categories": ["Nến thơm"]
    }
  ],
  "session_id": "..."
}
```

### Admin API

Admin API yêu cầu đăng nhập bằng mật khẩu `ADMIN_PASSWORD`. Sau khi login, client nhận token và gửi trong header `Authorization: Bearer <token>`.

| Method | Endpoint | Mô tả |
| --- | --- | --- |
| `POST` | `/api/admin/login` | Đăng nhập admin và nhận token. |
| `GET` | `/api/admin/status` | Lấy trạng thái các pipeline. |
| `POST` | `/api/admin/crawl` | Crawl danh sách sản phẩm. |
| `POST` | `/api/admin/crawl-details` | Crawl chi tiết sản phẩm. |
| `POST` | `/api/admin/chunk` | Chia dữ liệu sản phẩm thành chunks. |
| `POST` | `/api/admin/embed` | Tạo FAISS embeddings. |
| `POST` | `/api/admin/run-full-pipeline` | Chạy pipeline crawl -> details -> chunk -> embed. |
| `GET` | `/api/admin/products` | Lấy danh sách sản phẩm từ Neo4j. |
| `DELETE` | `/api/admin/products/{product_name}` | Xóa sản phẩm khỏi Neo4j. |
| `GET` | `/api/admin/sessions` | Lấy danh sách session. |
| `DELETE` | `/api/admin/sessions/{session_id}` | Xóa session. |
| `GET` | `/api/admin/stats` | Lấy thống kê dữ liệu cho admin dashboard. |

Ví dụ đăng nhập admin:

```bash
curl -X POST http://localhost:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"your_admin_password\"}"
```

Ví dụ chạy full pipeline:

```bash
curl -X POST http://localhost:8000/api/admin/run-full-pipeline \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d "{\"total_pages\": 7, \"batch_size\": 10}"
```

## Admin Dashboard

Admin dashboard có tại:

```text
http://localhost:8000/admin
```

Các chức năng chính:

- Đăng nhập bằng `ADMIN_PASSWORD`.
- Theo dõi trạng thái pipeline.
- Kích hoạt crawl, crawl details, chunking, embedding hoặc full pipeline.
- Xem thống kê dữ liệu cache, chunks, embeddings và Neo4j.
- Quản lý danh sách sản phẩm trong Neo4j.
- Xem và xóa session hội thoại.

## Dữ Liệu Và Lưu Trữ

| Thành phần | Vị trí | Mô tả |
| --- | --- | --- |
| Product cache | `data/cache/product_details.json` | Dữ liệu sản phẩm đã crawl. |
| Chunks | `data/chunks/*.json` | Sản phẩm được chia batch để xử lý embedding. |
| FAISS index | `data/embeddings/products.index` | Vector index phục vụ semantic search. |
| Embedding metadata | `data/embeddings/products_metadata.json` | Metadata gắn với từng vector. |
| Chat memory | `data/carpediem_chat.db` | SQLite database lưu session và messages. |
| Graph database | Neo4j | Lưu product graph, categories, collections, entities và similarity edges. |

## Troubleshooting

### Thiếu `OPENAI_API_KEY`

Thông báo thường gặp:

```text
Thiếu OPENAI_API_KEY trong file .env
```

Cách xử lý: kiểm tra file `.env` tại root và đảm bảo `OPENAI_API_KEY` đã được khai báo đúng.

### Không kết nối được Neo4j

Kiểm tra các biến sau trong `.env`:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

Đảm bảo Neo4j đang chạy và tài khoản có quyền đọc/ghi database.

### Thiếu FAISS index hoặc metadata

Nếu gặp lỗi khi khởi tạo `GraphRAG`, kiểm tra các file:

```text
data/embeddings/products.index
data/embeddings/products_metadata.json
```

Nếu file chưa tồn tại, chạy:

```bash
python processing/chunking.py
python processing/embedding.py
```

### Chatbot không trả về sản phẩm phù hợp

Kiểm tra các bước sau:

- `data/cache/product_details.json` có dữ liệu sản phẩm hợp lệ.
- Embeddings đã được tạo lại sau khi dữ liệu sản phẩm thay đổi.
- Neo4j graph đã được build bằng `python src/graph_builder.py`.
- Câu hỏi người dùng có đủ thông tin về sản phẩm, dịp, ngân sách hoặc danh mục.

### Lỗi tải model Sentence Transformers

Lần chạy đầu tiên cần tải model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Kiểm tra kết nối Internet hoặc cấu hình cache model nếu môi trường bị giới hạn mạng.

## Đóng Góp

Quy trình đề xuất khi phát triển:

1. Tạo branch mới từ branch chính.
2. Cài đặt dependencies và cấu hình `.env` local.
3. Thực hiện thay đổi nhỏ, rõ ràng và có kiểm thử thủ công qua API/CLI/UI liên quan.
4. Không commit `.env`, virtual environment, `__pycache__` hoặc dữ liệu nhạy cảm.
5. Mô tả rõ thay đổi, cách kiểm thử và rủi ro còn lại trong pull request.

## Ghi Chú Bảo Mật

- Không public `OPENAI_API_KEY`, `NEO4J_PASSWORD` hoặc `ADMIN_PASSWORD`.
- Admin token hiện được lưu trong memory của process và hết hạn sau 24 giờ.
- CORS hiện đang cho phép tất cả origin để thuận tiện phát triển. Khi triển khai production, nên giới hạn `allow_origins` về domain chính thức.