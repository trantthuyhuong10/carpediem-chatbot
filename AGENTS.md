# AGENTS

## Repo reality check
- `README.md` includes outdated paths in some sections; trust executable entrypoints in `api/`, `src/`, `processing/`, `crawl/`, and `scripts/`.
- This repo has no lint/typecheck/test config (`pytest.ini`, `pyproject.toml`, CI workflows, Makefile not present). Do not invent verification commands.

## Runtime entrypoints
- FastAPI app: `uvicorn api.app:app --reload`
- Streamlit app: `streamlit run interface/app.py`
- CLI demo: `python scripts/demo_cli.py`

## Required environment and services
- Required for startup: `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (used by `ChatBot`/`GraphRAG`).
- Admin auth uses `ADMIN_PASSWORD` from env (`api/auth.py`).
- Qdrant is optional at runtime: if unavailable, vector search is skipped and chatbot falls back to SQLite product DB search.
- MinIO is optional at runtime: if unavailable, image URLs are not rewritten to presigned links.
- Code has internal-network defaults for Qdrant/MinIO (`172.16.4.205...`); override with env vars in local/dev environments.

## Data and persistence locations
- Chat sessions/messages SQLite: `data/carpediem_chat.db` (`src/memory_store.py`).
- Product SQLite: `data/carpediem_products.db` (`crawl/product_db.py`).
- Vector sparse vocab: `data/embeddings/sparse_vocab.json`.
- Chunking input is `data/cache/merged_collection_products.json` (not `product_details.json`).

## Correct pipeline order (important)
- If rebuilding retrieval data from crawl output, run in this order:
  1) `python crawl/static_crawling.py`
  2) `python crawl/static_crawling_details.py`
  3) `python scripts/merge_collection_product_details.py`
  4) `python processing/chunking.py`
  5) `python processing/embedding.py`
  6) `python src/graph_builder.py`
- Reason: `processing/chunking.py` reads merged collection+product detail JSON, not raw crawl details.

## API/admin behavior quirks
- Admin pipeline endpoints run async in background threads (`api/pipeline.py`); check progress via `GET /api/admin/status`.
- `/api/admin/run-full-pipeline` runs crawl -> crawl-details -> chunk -> embed only; Neo4j graph build is separate (`python src/graph_builder.py`).

## Working conventions for agents
- Keep edits scoped; this repo contains checked-in runtime artifacts (`data/*.db`, `data/embeddings/*`, `__pycache__`, `node_modules/`). Avoid modifying generated/runtime data unless task explicitly asks.
- Do not trust README command names blindly when they conflict with files on disk; verify paths/scripts before changing docs or code.
