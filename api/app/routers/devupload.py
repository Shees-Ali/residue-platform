"""Local stand-in for a signed Cloud Storage URL: upload and read photos through the API.

Exists only with local storage and never on Cloud Run. The path is unguessable, so reading is open
(an <img> tag cannot send a token); writing needs a signed-in person and checks type and size.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.auth.firebase import AuthUser, current_user
from app.services.storage import (
    PHOTO_MAX_BYTES,
    PHOTO_PATH,
    PHOTO_TYPES,
    Storage,
    dev_uploads_enabled,
    get_storage,
    media_type,
)
from app.validation import FieldErrors

router = APIRouter(prefix="/api/dev-upload", tags=["dev"])


def _local(storage: Storage, path: str) -> None:
    if not dev_uploads_enabled(storage):
        raise HTTPException(404, "Not found")
    if not PHOTO_PATH.match(path):
        raise HTTPException(404, "Unknown photo path")


@router.put("/{path:path}", status_code=204)
async def put_photo(
    path: str,
    request: Request,
    user: AuthUser = Depends(current_user),
    storage: Storage = Depends(get_storage),
):
    _local(storage, path)
    kind = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if kind not in PHOTO_TYPES or media_type(path) != kind:
        raise FieldErrors(
            [("photo", "Add a photo (JPEG, PNG or WebP, up to 5 MB)")], code="photo_type"
        )
    data = await request.body()
    if not data:
        raise FieldErrors([("photo", "The photo file is empty")], code="empty_photo")
    if len(data) > PHOTO_MAX_BYTES:
        raise FieldErrors([("photo", "Photo must be 5 MB or smaller")], code="photo_too_big")
    await storage.put(path, data)  # type: ignore[attr-defined]


@router.get("/{path:path}")
async def get_photo(path: str, storage: Storage = Depends(get_storage)):
    _local(storage, path)
    try:
        data = await storage.read(path)
    except FileNotFoundError:
        raise HTTPException(404, "Unknown photo") from None
    return Response(
        data,
        media_type=media_type(path),
        headers={"Cache-Control": "private, max-age=3600"},
    )
