from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class MediaUploadError(ValueError):
    pass


class MediaContentTypeError(MediaUploadError):
    pass


class MediaTooLargeError(MediaUploadError):
    pass


def get_media_root() -> Path:
    configured = os.getenv("MEDIA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / "media" / "uploads").resolve()


def get_recipes_upload_dir() -> Path:
    directory = get_media_root() / "recipes"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def to_public_media_url(filename: str) -> str:
    return f"/media/recipes/{filename}"


def _safe_suffix_for_content_type(content_type: str | None) -> str:
    if not content_type:
        raise MediaContentTypeError("Unsupported image type")
    suffix = ALLOWED_IMAGE_CONTENT_TYPES.get(content_type.lower())
    if not suffix:
        raise MediaContentTypeError("Unsupported image type")
    return suffix


def save_uploaded_recipe_image(file: UploadFile) -> str:
    suffix = _safe_suffix_for_content_type(file.content_type)
    content = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise MediaTooLargeError("Image is too large")

    filename = f"{uuid4().hex}{suffix}"
    destination = get_recipes_upload_dir() / filename
    destination.write_bytes(content)
    return to_public_media_url(filename)


def maybe_delete_media_file(url: str | None) -> None:
    if not url:
        return
    prefix = "/media/recipes/"
    if not url.startswith(prefix):
        return

    filename = url.removeprefix(prefix)
    if not filename:
        return

    candidate = get_recipes_upload_dir() / filename
    try:
        candidate.relative_to(get_recipes_upload_dir())
    except ValueError:
        return

    if candidate.exists() and candidate.is_file():
        candidate.unlink(missing_ok=True)
