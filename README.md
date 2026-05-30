# Carpediem Chatbot

Đây là dự án xây dựng Chatbot - Trợ lý AI cho thương hiệu chuyên về mùi hương Carpediem, hỗ trợ tư vấn nến thơm, tinh dầu, đá thơm khuếch hương và giftset. Dự án kết hợp FastAPI, OpenAI API, Neo4j, Qdrant và Sentence Transformers để xây dựng hệ thống chatbot có khả năng tìm kiếm sản phẩm theo ngữ nghĩa, gợi ý theo dịp/ngân sách, phân tích ảnh và lưu lịch sử hội thoại.

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
- Tìm kiếm sản phẩm bằng Graph RAG kết hợp Qdrant vector search và Neo4j graph filtering.
- Gợi ý sản phẩm theo dịp như sinh nhật, Valentine, 8/3, 20/10, cưới hỏi, tân gia, Giáng sinh và Tết.
- Gợi ý theo ngân sách, danh mục và nội dung mô tả sản phẩm.
- Phân tích ảnh sản phẩm hoặc không gian để đề xuất sản phẩm phù hợp.
- Lưu lịch sử hội thoại theo session bằng SQLite.
- Web chat UI tĩnh phục vụ qua FastAPI.
- Admin dashboard để theo dõi dữ liệu, session và kích hoạt pipeline xử lý dữ liệu.
- Streamlit interface cho trải nghiệm demo độc lập.
- CLI demo cho kiểm thử nhanh trong terminal.
- CrossEncoder reranking để sắp xếp kết quả tìm kiếm chính xác hơn.
- Fallback 4 tầng: hybrid → Neo4j text → dense-only → SQLite keyword.
- Nhận biết câu hỏi follow-up (đó, này, nó, sản phẩm đó) dựa vào ngữ cảnh hội thoại.
- Ragas evaluation để đánh giá chất lượng phản hồi tự động.

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
        |-- Crawl collections
        |-- Crawl collections details
        |-- Merge product details and collections details
        |-- Chunk data
        |-- Generate embeddings
        |-- Build Neo4j graph

Data Layer
  |-- data/cache/product_details.json
  |-- data/cache/collection_details.json
  |-- data/cache/merged_collection_products.json
  |-- data/chunks/*.json
  |-- data/embeddings/backup
  |-- data/carpediem_chat.db
  |-- data/carpediem_products.db
  |-- Neo4j graph database
```

Luồng xử lý chat chính:

1. Người dùng gửi tin nhắn hoặc ảnh.
2. `ChatBot` phân loại intent thành `product_search`, `general_qa` hoặc `image_analysis`.
3. Với câu hỏi sản phẩm, hệ thống tìm kiếm bằng Qdrant, lọc/enrich bằng Neo4j và lấy context sản phẩm liên quan.
4. OpenAI model sinh câu trả lời dựa trên prompt, lịch sử hội thoại và kết quả truy xuất.
5. Tin nhắn được lưu vào SQLite để hỗ trợ hội thoại nhiều lượt.

## Công Nghệ Sử Dụng

- Python 3.10+
- FastAPI và Uvicorn cho HTTP API.
- OpenAI Python SDK cho mô hình hội thoại và xử lý ảnh.
- Neo4j cho graph database sản phẩm, danh mục, collection, entity và quan hệ tương đồng.
- Qdrant cho vector similarity search.
- Sentence Transformers với model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` để tạo embedding đa ngôn ngữ.
- SQLite cho lưu session và lịch sử chat.
- Streamlit cho giao diện demo.
- BeautifulSoup và Requests cho crawler.
- HTML, CSS, JS để xây dựng giao diện cho hệ thống.

## Cấu Trúc Thư Mục

```text
carpediem-mini-project/
├── api/                                # FastAPI app, models, auth, admin routes, pipeline API
│   ├── app.py                          # Entry point FastAPI (routes: chat, upload, reset, stats, sessions)
│   ├── admin_routes.py                 # API quản trị và pipeline (run-full-pipeline, status)
│   ├── auth.py                         # Xác thực admin bằng ADMIN_PASSWORD
│   ├── models.py                       # Pydantic schemas cho request/response
│   └── pipeline.py                     # Chạy crawl/chunk/embedding bất đồng bộ trong background thread
├── crawl/                              # Crawler dữ liệu sản phẩm Carpediem từ carpediem.vn
│   ├── crawl_collections.py            # Crawl danh sách bộ sưu tập (tên + link)
│   ├── crawl_collection_details.py     # Crawl chi tiết sản phẩm trong từng bộ sưu tập
│   ├── static_crawling.py              # Crawl danh sách sản phẩm (tên + link)
│   ├── static_crawling_details.py      # Crawl chi tiết sản phẩm (giá, mô tả, ảnh)
│   └── product_db.py                   # Tạo và truy vấn SQLite product database
├── data/                               # Dữ liệu cache, chunks, embeddings và SQLite DB
│   ├── cache/                          # JSON crawl output (merged_collection_products.json, ...)
│   ├── chunks/                         # Chunk files từ processing/chunking.py
│   ├── embeddings/                     # Sparse vocab + product metadata
│   ├── carpediem_products.db           # SQLite sản phẩm (products, collections, giftsets)
│   └── carpediem_chat.db               # SQLite chat sessions và messages
├── interface/                          # Streamlit UI (trải nghiệm demo độc lập)
│   ├── app.py                          # Chat UI với image upload, suggestion buttons
│   └── assets/                         # Hình ảnh và tài nguyên
├── processing/                         # Chunking và embedding pipeline
│   ├── chunking.py                     # Chunk merged JSON thành các segments nhỏ
│   └── embedding.py                    # Embed chunks và upsert lên Qdrant
├── scripts/                            # Script tiện ích
│   ├── demo_cli.py                     # CLI demo cho kiểm thử nhanh trong terminal
│   ├── giftset_products.py             # Xử lý dữ liệu giftset
│   ├── merge_collection_product_details.py  # Gộp collection + product details vào merged JSON
│   ├── merge_images_to_collections.py  # Gộp ảnh vào collections
│   └── upload_images_to_minio.py       # Upload ảnh sản phẩm lên MinIO
├── src/                                # Core chatbot engine
│   ├── chatbot.py                      # ChatBot orchestrator: intent classification, retrieval routing, LLM prompting
│   ├── graph_rag.py                    # GraphRAG hybrid retrieval: dense + sparse + Neo4j + reranker
│   ├── graph_builder.py                # Xây dựng Neo4j graph từ merged JSON
│   ├── vector_store.py                 # Qdrant client cho dense và sparse vector search
│   ├── reranker.py                     # CrossEncoder reranker (BAAI/bge-reranker-v2-m3)
│   ├── memory_store.py                 # SQLite chat session/message persistence
│   ├── storage.py                      # MinIO image storage với presigned URLs
│   └── log_utils.py                    # Pipeline logging utility
├── static/                             # Web chat UI và admin UI tĩnh (phục vụ qua FastAPI)
│   ├── index.html                      # Chat giao diện chính
│   ├── style.css                       # Stylesheet
│   ├── app.js                          # Chat logic JavaScript
│   ├── admin.html                      # Admin dashboard
│   ├── admin.js                        # Admin logic JavaScript
│   ├── admin.css                       # Admin stylesheet
│   ├── img/                            # Hình ảnh UI
│   └── favicon.ico                     # Favicon
├── rag_eval/                           # RAG Evaluation với Ragas framework
│   └── rag_eval/
│       ├── evals.py                    # Định nghĩa dataset, metric, experiment
│       ├── pyproject.toml              # Dependencies (ragas, neo4j, qdrant-client, ...)
│       ├── evals/
│       │   ├── datasets/               # CSV test datasets (tự sinh từ evals.py)
│       │   └── experiments/            # Kết quả đánh giá pass/fail
│       └── .venv/                      # Virtual environment
├── .env                                # Biến môi trường (API keys, backend URIs)
├── requirements.txt                    # Python dependencies
├── AGENTS.md                           # Hướng dẫn cho AI agents
└── README.md                           # Tài liệu dự án
```

## Yêu Cầu Hệ Thống

- Python 3.9 trở lên.
- Neo4j đang chạy và có thể truy cập từ máy local hoặc server (cấu hình qua NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD).
- OpenAI API key hợp lệ (hoặc OpenRouter API key nếu dùng model third-party).
- Kết nối Internet để tải model Sentence Transformers (paraphrase-multilingual-MiniLM-L12-v2) và CrossEncoder (BAAI/bge-reranker-v2-m3) trong lần chạy đầu tiên.
- Qdrant đang chạy (optional: nếu không có, hệ thống tự fallback xuống Neo4j text search và SQLite).
- MinIO đang chạy (optional: nếu không có, ảnh sản phẩm trả về URL gốc thay vì presigned URL).
- Dung lượng đủ cho dữ liệu embeddings (~200MB), model cache (~2GB) và SQLite databases.
- Port 7687 (Neo4j), 6333 (Qdrant) và 30031 (MinIO) cần được mở nếu chạy các dịch vụ trên server từ xa.

## Cài Đặt
### 1. Clone repository
```bash
git clone <repository-url>
cd carpediem-chatbot
```
### 2. Tạo virtual environment
```bash
python -m venv venv
```
Kích hoạt trên macOS/Linux:
```bash
source venv/bin/activate
```
Kích hoạt trên Windows PowerShell:
```powershell
.\venv\Scripts\Activate.ps1
```
### 3. Cài đặt dependencies
```bash
pip install -r requirements.txt
```
### 4. Cấu hình môi trường
Tạo file `.env` từ mẫu:
```bash
cp .env.example .env
```

NEO4J_URI=
NEO4J_USER=
NEO4J_PASSWORD=

OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=

ADMIN_PASSWORD=

MINIO_ENDPOINT=
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_BUCKET=
MINIO_USE_SSL=

QDRANT_URL=
QDRANT_COLLECTION=

Các biến bắt buộc:
| Biến | Mô tả | Ví dụ |
|------|-------|-------|
| `OPENAI_API_KEY` | API key cho LLM | `sk-...` |
| `NEO4J_URI` | URI kết nối Neo4j | `neo4j://localhost:7687` |
| `NEO4J_USER` | Username Neo4j | `neo4j` |
| `NEO4J_PASSWORD` | Password Neo4j | |
Các biến tùy chọn:
| Biến | Mô tả | Mặc định |
|------|-------|----------|
| `OPENAI_BASE_URL` | Base URL cho OpenAI-compatible API | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Model name | `gpt-4o-mini` |
| `QDRANT_URL` | Qdrant endpoint | `http://localhost:6333` |
| `MINIO_ENDPOINT` | MinIO endpoint (nếu có) | - |

Không commit file `.env` vì file này chứa thông tin nhạy cảm.

### 5. Khởi động các dịch vụ backend
**Neo4j** (bắt buộc):
```bash
# Docker
docker run -d --name neo4j -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/<password> neo4j:5
```
**Qdrant** (tùy chọn — nếu thiếu, hệ thống tự fallback):
```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
```
### 6. Xây dựng dữ liệu
Chạy pipeline để crawl, chunk và index dữ liệu sản phẩm Carpediem:
```bash
# 1. Crawl dữ liệu sản phẩm
python crawl/static_crawling.py
python crawl/static_crawling_details.py
python scripts/merge_collection_product_details.py
# 2. Chunk và embedding
python processing/chunking.py
python processing/embedding.py
# 3. Xây dựng Neo4j graph
python src/graph_builder.py
```
### 7. Chạy ứng dụng
**FastAPI server** (web chat + admin API):
```bash
uvicorn api.app:app --reload
```
Truy cập: http://localhost:8000 (chat UI) / http://localhost:8000/admin (admin)
**Streamlit UI** (demo độc lập):
```bash
streamlit run interface/app.py
```
### 8. Chạy đánh giá (optional)
```bash
cd rag_eval/rag_eval
uv sync
uv run python evals.py
```

## Chuẩn Bị Dữ Liệu

Dự án cần các dữ liệu sau để chatbot truy xuất sản phẩm:

- `data/cache/merged_collection_products.json`: dữ liệu sản phẩm đã crawl.
- `data/chunks/*.json`: dữ liệu sản phẩm đã chia chunk.
- Neo4j graph chứa node `Product`, `Category`, `Collection`, `Entity` và relationship liên quan.

Nếu dữ liệu đã có sẵn trong thư mục `data/`, bạn có thể bỏ qua bước crawl/chunk/embedding và chỉ cần đảm bảo Neo4j đã được build.

Chạy từng bước pipeline bằng Python:

```bash
python crawl/static_crawling.py
python crawl/static_crawling_details.py
python scripts/upload_images_to_minio.py
python crawl/crawl_collections.py
python crawl/crawl_collection_details.py
python scripts/merge_collection_product_details.py
python scripts/merge_images_to_collections.py
python processing/chunking.py
python processing/embedding.py
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
| `GET`  | `/api/admin/status` | Lấy trạng thái các pipeline. |
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
| `POST` | `/api/admin/images/upload` | Upload ảnh sản phẩm lên MinIO. |
| `GET` | `/api/admin/images/url` | Lấy presigned URL của ảnh từ MinIO. |
| `DELETE` | `/api/admin/images/{key}` | Xóa ảnh khỏi MinIO. |

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