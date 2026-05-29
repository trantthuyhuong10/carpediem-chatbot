import os
import uuid
import requests
from io import BytesIO
from urllib.parse import urlparse
from dotenv import load_dotenv
from minio import Minio
from minio.error import S3Error
from datetime import timedelta

load_dotenv()


class MinioStorage:
    def __init__(self):
        endpoint = os.getenv("MINIO_ENDPOINT", "172.16.4.205:30032")
        access_key = os.getenv("MINIO_ACCESS_KEY", "admin2")
        secret_key = os.getenv("MINIO_SECRET_KEY", "12345678")
        self.bucket = os.getenv("MINIO_BUCKET", "carpediem-images")
        use_ssl = os.getenv("MINIO_USE_SSL", "false").lower() == "true"
        self._available = True

        try:
            self.client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=use_ssl,
            )
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                print(f"[MinIO] Created bucket: {self.bucket}")
            print(f"[MinIO] Connected to {endpoint}/{self.bucket}")
        except Exception as e:
            print(f"[MinIO] Connection failed: {e}")
            print("[MinIO] Images will use original URLs as fallback")
            self._available = False
            self.client = None

    @property
    def available(self):
        return self._available

    def upload_from_bytes(self, key, data, content_type="image/webp"):
        if not self.available:
            return None
        self.client.put_object(
            self.bucket, key, BytesIO(data), len(data), content_type=content_type
        )
        return key

    def upload_from_url(self, key, url):
        if not self.available:
            return None
        try:
            resp = requests.get(url, timeout=10, stream=True)
            resp.raise_for_status()
            ct = resp.headers.get("Content-Type", "image/webp")
            data = resp.content
            return self.upload_from_bytes(key, data, ct)
        except Exception as e:
            print(f"[MinIO] Failed to upload from URL {url}: {e}")
            return None

    def get_presigned_url(self, key, expires=3600):
        if not self.available or not key:
            return key
        try:
            return self.client.get_presigned_url(
                "GET", self.bucket, key, expires=timedelta(seconds=expires)
            )
        except Exception as e:
            print(f"[MinIO] Failed to get presigned URL for {key}: {e}")
            return key

    def delete(self, key):
        if not self.available or not key:
            return
        try:
            self.client.remove_object(self.bucket, key)
        except Exception as e:
            print(f"[MinIO] Failed to delete {key}: {e}")

    @staticmethod
    def is_minio_key(key):
        if not key:
            return False
        return not key.startswith(("http://", "https://", "data:", "blob:"))

    def resolve(self, key_or_url, expires=3600):
        if self.is_minio_key(key_or_url):
            return self.get_presigned_url(key_or_url, expires)
        return key_or_url

    @staticmethod
    def extract_slug(url):
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]
        if "products" in parts:
            idx = parts.index("products")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return parts[-1] if parts else "unknown"

    def product_image_key(self, product_url, index=0, suffix=None):
        slug = self.extract_slug(product_url)
        name = f"main.webp"
        if index > 0:
            name = f"gallery-{index}.webp"
        elif suffix:
            name = f"{suffix}.webp"
        return f"products/{slug}/{name}"

    def upload_image_key(self, prefix="uploads/chat"):
        return f"{prefix}/{uuid.uuid4().hex}.webp"
