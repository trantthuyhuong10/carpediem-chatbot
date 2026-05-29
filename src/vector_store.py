import os
import numpy as np
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

load_dotenv()

VECTOR_SIZE = 384


class VectorStore:
    def __init__(self):
        url = os.getenv("QDRANT_URL", "http://172.16.4.205:6333")
        self.collection_name = os.getenv("QDRANT_COLLECTION", "carpediem_details")
        self._available = True

        try:
            self.client = QdrantClient(url=url, timeout=30)
            self.client.get_collections()
            self._ensure_collection()
            print(f"[Qdrant] Connected to {url}/{self.collection_name}")
        except Exception as e:
            print(f"[Qdrant] Connection failed: {e}")
            print("[Qdrant] Vector search will be unavailable")
            self._available = False
            self.client = None

    @property
    def available(self):
        return self._available

    def _ensure_collection(self):
        try:
            collections = self.client.get_collections().collections
            names = [c.name for c in collections]
            if self.collection_name not in names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=VECTOR_SIZE,
                        distance=models.Distance.COSINE,
                    ),
                )
                print(f"[Qdrant] Created collection: {self.collection_name}")
        except UnexpectedResponse as e:
            if "already exists" in str(e):
                pass
            else:
                raise

    def upsert(self, vectors, payloads):
        if not self.available:
            return
        points = []
        for i, (vec, payload) in enumerate(zip(vectors, payloads)):
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            points.append(models.PointStruct(id=i, vector=vec.tolist(), payload=payload))
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        print(f"[Qdrant] Upserted {len(points)} points")

    def search(self, query_vector, top_k=5):
        if not self.available:
            return []
        norm = np.linalg.norm(query_vector)
        if norm > 0:
            query_vector = query_vector / norm
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector.tolist(),
            limit=top_k * 2,
            with_payload=True,
        )
        output = []
        for r in results.points:
            p = dict(r.payload)
            p["score"] = float(r.score)
            output.append(p)
        return output

    def get_all_points(self):
        if not self.available:
            return [], [], []
        offset = None
        ids, vectors, payloads = [], [], []
        while True:
            results, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            for r in results:
                ids.append(r.id)
                vectors.append(np.array(r.vector))
                payloads.append(dict(r.payload))
            if offset is None or offset == "":
                break
        return ids, vectors, payloads

    def delete_collection(self):
        if not self.available:
            return
        try:
            self.client.delete_collection(self.collection_name)
            print(f"[Qdrant] Deleted collection: {self.collection_name}")
        except Exception:
            pass

    def count(self):
        if not self.available:
            return 0
        return self.client.count(self.collection_name).count
