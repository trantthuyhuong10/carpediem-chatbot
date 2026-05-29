import os
import json
import re
import numpy as np
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

load_dotenv()

VECTOR_SIZE = 384
SPARSE_VOCAB_PATH = "data/embeddings/sparse_vocab.json"


class VectorStore:
    def __init__(self):
        url = os.getenv("QDRANT_URL", "http://172.16.4.205:6333")
        self.collection_name = os.getenv("QDRANT_COLLECTION", "carpediem_details")
        self._available = True
        self.vocab = {}
        self.vocab_size = 0

        try:
            self.client = QdrantClient(url=url, timeout=30)
            self.client.get_collections()
            self._ensure_collection()
            print(f"[Qdrant] Connected to {url}/{self.collection_name}")
            self._load_vocab()
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
                    vectors_config={
                        "dense": models.VectorParams(
                            size=VECTOR_SIZE,
                            distance=models.Distance.COSINE,
                        ),
                    },
                    sparse_vectors_config={
                        "sparse": models.SparseVectorParams(
                            modifier=models.Modifier.IDF,
                        ),
                    },
                )
                print(f"[Qdrant] Created collection: {self.collection_name} (dense + sparse)")
        except UnexpectedResponse as e:
            if "already exists" in str(e):
                pass
            else:
                raise

    def _load_vocab(self):
        if os.path.exists(SPARSE_VOCAB_PATH):
            with open(SPARSE_VOCAB_PATH, "r", encoding="utf-8") as f:
                self.vocab = json.load(f)
            self.vocab_size = len(self.vocab)
            print(f"[Qdrant] Loaded sparse vocab: {self.vocab_size} terms")

    def _save_vocab(self):
        os.makedirs(os.path.dirname(SPARSE_VOCAB_PATH), exist_ok=True)
        with open(SPARSE_VOCAB_PATH, "w", encoding="utf-8") as f:
            json.dump(self.vocab, f, ensure_ascii=False)

    def set_vocab(self, vocab):
        self.vocab = vocab
        self.vocab_size = len(vocab)
        self._save_vocab()

    @staticmethod
    def _tokenize(text):
        return re.findall(
            r'[a-zàáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợ'
            r'ùúủũụưứừửữựỳýỷỹỵ0-9]+',
            text.lower()
        )

    @staticmethod
    def _build_vocabulary(texts):
        vocab = {}
        for text in texts:
            tokens = VectorStore._tokenize(text)
            for token in tokens:
                if token not in vocab:
                    vocab[token] = len(vocab)
        return vocab

    def _text_to_sparse(self, text):
        tokens = self._tokenize(text)
        freq = {}
        for token in tokens:
            tid = self.vocab.get(token)
            if tid is not None:
                freq[tid] = freq.get(tid, 0) + 1
        if not freq:
            return models.SparseVector(indices=[0], values=[0.0])
        indices = sorted(freq.keys())
        values = [float(freq[i]) for i in indices]
        return models.SparseVector(indices=indices, values=values)

    def upsert(self, vectors, payloads, sparse_vectors=None):
        if not self.available:
            return
        points = []
        for i, (vec, payload) in enumerate(zip(vectors, payloads)):
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            point_vec = {"dense": vec.tolist()}
            if sparse_vectors is not None and i < len(sparse_vectors):
                point_vec["sparse"] = sparse_vectors[i]
            points.append(models.PointStruct(id=i, vector=point_vec, payload=payload))
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        print(f"[Qdrant] Upserted {len(points)} points (dense + sparse)")

    def search(self, query_vector, top_k=5):
        if not self.available:
            return []
        norm = np.linalg.norm(query_vector)
        if norm > 0:
            query_vector = query_vector / norm
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector.tolist(),
            using="dense",
            limit=top_k,
            with_payload=True,
        )
        output = []
        for r in results.points:
            p = dict(r.payload)
            p["score"] = float(r.score)
            output.append(p)
        return output

    def sparse_search(self, query_text, top_k=5):
        if not self.available or not self.vocab:
            return []
        sparse = self._text_to_sparse(query_text)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=sparse,
            using="sparse",
            limit=top_k,
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
                vec = r.vector
                if isinstance(vec, dict) and "dense" in vec:
                    vectors.append(np.array(vec["dense"]))
                else:
                    vectors.append(np.array(vec))
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
        if os.path.exists(SPARSE_VOCAB_PATH):
            os.remove(SPARSE_VOCAB_PATH)

    def count(self):
        if not self.available:
            return 0
        return self.client.count(self.collection_name).count
