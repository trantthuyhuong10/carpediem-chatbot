# GraphRAG - Carpediem Product Recommendation

## Kiến trúc

```
graph_builder.py  →  Xây graph: nodes + relationships (BELONGS_TO, PART_OF, HAS_ENTITY, SIMILAR_TO)
graph_rag.py      →  Retrieval: FAISS vector + Neo4j graph filter/enrich
```

## Cách dùng

```bash
# Build graph (xoá cũ, tạo mới toàn bộ)
python src/graph_builder.py

# Interactive retrieval
python src/graph_rag.py

# So sánh vector-only vs GraphRAG
python scripts/demo_graph_rag.py
```

```python
from src.graph_rag import GraphRAG
rag = GraphRAG()

rag.query("nến thơm hương trầm dưới 500k")          # hybrid search
rag.recommend_by_occasion("sinh nhật")               # occasion
rag.recommend_by_budget("dưới 300k")                 # budget
rag.find_similar_products("Nến thơm Hoài An")        # similar products
rag.get_stats()                                      # graph stats
rag.close()
```

## Graph Schema

| Label | Count |
|---|---|
| Product | 51 |
| Category | 5 |
| Entity | 13 |

| Relationship | Count |
|---|---|
| BELONGS_TO | 51 |
| PART_OF | 51 |
| HAS_ENTITY | 178 |
| SIMILAR_TO | 228 |

## Pipeline

```
1. Crawl → data/cache/product_details.json
2. Chunk → data/chunks/
3. Embed → data/embeddings/
4. Build graph → python src/graph_builder.py
5. Query → python src/graph_rag.py
```
