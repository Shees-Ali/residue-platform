"""Photo storage behind an interface: Cloud Storage in production, in-memory locally and in tests.

The client uploads straight to the signed URL, then tells the API the object path. The API only
accepts paths under `jobs/{job_id}/{kind}/`, so a photo can't be attached to the wrong job.
"""
import os
import uuid
from datetime import timedelta
from typing import Protocol

PHOTO_KINDS = ("pickup", "delivery", "weighbridge")


def photo_prefix(job_id: str, kind: str) -> str:
    return f"jobs/{job_id}/{kind}/"


def new_photo_path(job_id: str, kind: str) -> str:
    return f"{photo_prefix(job_id, kind)}{uuid.uuid4().hex}.jpg"


class Storage(Protocol):
    async def signed_upload_url(self, path: str, content_type: str) -> str: ...

    async def read(self, path: str) -> bytes: ...


class FakeStorage:
    """No bucket configured: hands out a dev URL and serves whatever a test stored."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    async def signed_upload_url(self, path: str, content_type: str) -> str:
        return f"http://localhost:8000/dev-upload/{path}"

    async def read(self, path: str) -> bytes:
        if path not in self.blobs:
            raise FileNotFoundError(path)
        return self.blobs[path]


class GcsStorage:
    def __init__(self, bucket: str) -> None:
        from google.cloud import storage  # lazy: only needed when STORAGE_BUCKET is set

        self._bucket = storage.Client().bucket(bucket)

    async def signed_upload_url(self, path: str, content_type: str) -> str:
        blob = self._bucket.blob(path)
        return blob.generate_signed_url(
            version="v4", method="PUT", expiration=timedelta(minutes=15), content_type=content_type
        )

    async def read(self, path: str) -> bytes:
        return self._bucket.blob(path).download_as_bytes()


_storage: Storage | None = None


def get_storage() -> Storage:
    """FastAPI dependency. A real bucket only when STORAGE_BUCKET is set."""
    global _storage
    if _storage is None:
        bucket = os.getenv("STORAGE_BUCKET")
        _storage = GcsStorage(bucket) if bucket else FakeStorage()
    return _storage
