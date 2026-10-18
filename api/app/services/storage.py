"""Photo storage behind an interface: Cloud Storage in production, disk locally, memory in tests.

The client uploads straight to the signed URL, then tells the API the object path. The API only
accepts paths under `jobs/{job_id}/{kind}/`, so a photo can't be attached to the wrong job, and it
checks the file really is there (and not too big) before it records a pickup, delivery or grade.
"""
import os
import re
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Protocol

PHOTO_KINDS = ("pickup", "delivery", "weighbridge")
PHOTO_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
PHOTO_MAX_BYTES = 5 * 1024 * 1024
PHOTO_PATH = re.compile(
    r"^jobs/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/"
    r"(pickup|delivery|weighbridge)/[0-9a-f]{32}\.(jpg|png|webp)$"
)
_MEDIA = {ext: media for media, ext in PHOTO_TYPES.items()}


def photo_prefix(job_id: str, kind: str) -> str:
    return f"jobs/{job_id}/{kind}/"


def new_photo_path(job_id: str, kind: str, content_type: str = "image/jpeg") -> str:
    return f"{photo_prefix(job_id, kind)}{uuid.uuid4().hex}.{PHOTO_TYPES[content_type]}"


def media_type(path: str) -> str:
    return _MEDIA.get(path.rsplit(".", 1)[-1], "application/octet-stream")


class Storage(Protocol):
    async def signed_upload_url(self, path: str, content_type: str) -> str: ...

    async def read_url(self, path: str) -> str: ...

    async def read(self, path: str) -> bytes: ...

    async def size(self, path: str) -> int | None:
        """Bytes stored at `path`, or None when nothing was uploaded there."""
        ...


class FakeStorage:
    """In memory, for tests: serves whatever a test stored."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    async def signed_upload_url(self, path: str, content_type: str) -> str:
        return f"/api/dev-upload/{path}"

    async def read_url(self, path: str) -> str:
        return f"/api/dev-upload/{path}"

    async def read(self, path: str) -> bytes:
        if path not in self.blobs:
            raise FileNotFoundError(path)
        return self.blobs[path]

    async def size(self, path: str) -> int | None:
        return len(self.blobs[path]) if path in self.blobs else None

    async def put(self, path: str, data: bytes) -> None:
        self.blobs[path] = data


class DiskStorage:
    """Local development without a bucket: files live under api/.dev_uploads (gitignored).

    The browser PUTs to /api/dev-upload/{path} (see routers/devupload.py) and reads from the same
    address, so pickup and delivery photos really upload and show up on screen.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2] / ".dev_uploads"

    def _file(self, path: str) -> Path:
        if not PHOTO_PATH.match(path):
            raise FileNotFoundError(path)
        return self.root / path

    async def signed_upload_url(self, path: str, content_type: str) -> str:
        return f"/api/dev-upload/{path}"

    async def read_url(self, path: str) -> str:
        return f"/api/dev-upload/{path}"

    async def read(self, path: str) -> bytes:
        return self._file(path).read_bytes()

    async def size(self, path: str) -> int | None:
        try:
            file = self._file(path)
        except FileNotFoundError:
            return None
        return file.stat().st_size if file.is_file() else None

    async def put(self, path: str, data: bytes) -> None:
        file = self._file(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)


class GcsStorage:
    def __init__(self, bucket: str) -> None:
        from google.cloud import storage  # lazy: only needed when STORAGE_BUCKET is set

        self._bucket = storage.Client().bucket(bucket)

    def _signer(self) -> dict:
        """On Cloud Run the credentials have no private key: sign through the IAM API with the
        service account's own token (needs roles/iam.serviceAccountTokenCreator on itself)."""
        import google.auth
        from google.auth.transport.requests import Request

        creds, _ = google.auth.default()
        if not getattr(creds, "service_account_email", None) or hasattr(creds, "sign_bytes"):
            return {}  # a key file or user credentials sign locally
        creds.refresh(Request())
        return {"service_account_email": creds.service_account_email, "access_token": creds.token}

    async def signed_upload_url(self, path: str, content_type: str) -> str:
        blob = self._bucket.blob(path)
        return blob.generate_signed_url(
            version="v4", method="PUT", expiration=timedelta(minutes=15),
            content_type=content_type, **self._signer(),
        )

    async def read_url(self, path: str) -> str:
        return self._bucket.blob(path).generate_signed_url(
            version="v4", method="GET", expiration=timedelta(minutes=30), **self._signer()
        )

    async def read(self, path: str) -> bytes:
        return self._bucket.blob(path).download_as_bytes()

    async def size(self, path: str) -> int | None:
        blob = self._bucket.get_blob(path)
        return int(blob.size) if blob is not None and blob.size is not None else None


_storage: Storage | None = None


def get_storage() -> Storage:
    """FastAPI dependency. A real bucket when STORAGE_BUCKET is set, local disk otherwise."""
    global _storage
    if _storage is None:
        bucket = os.getenv("STORAGE_BUCKET")
        _storage = GcsStorage(bucket) if bucket else DiskStorage()
    return _storage


def dev_uploads_enabled(storage: Storage) -> bool:
    """The dev upload route only exists for local storage, and never on Cloud Run."""
    return isinstance(storage, DiskStorage | FakeStorage) and not os.getenv("K_SERVICE")
