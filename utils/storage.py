"""MinIO (S3-compatible) storage integration for Vizier.

All binary assets are stored in MinIO, never in Postgres (anti-drift #7).
Uses the minio-py client configured from environment variables.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from minio import Minio  # type: ignore[import-untyped]  # minio has no type stubs
from minio.error import S3Error  # type: ignore[import-untyped]

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

BUCKET_NAME = "vizier-assets"


def get_minio_client() -> Any:
    """Create a MinIO client from environment variables.

    Returns a Minio instance. Typed as Any because minio lacks type stubs.
    """
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )


def _resolve_client(client: Any) -> Any:
    """Return the provided client or create a new one."""
    if client is None:
        return get_minio_client()
    return client


def ensure_bucket(client: Any = None) -> None:
    """Create the vizier-assets bucket if it doesn't exist."""
    client = _resolve_client(client)
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        logger.info("Created bucket: %s", BUCKET_NAME)


def upload_bytes(
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    client: Any = None,
) -> str:
    """Upload raw bytes to MinIO.

    Args:
        object_name: The key/path in the bucket (e.g. "posters/abc-123.png").
        data: Raw bytes to upload.
        content_type: MIME type of the object.
        client: Optional pre-configured Minio client.

    Returns:
        The storage path in format "bucket/object_name".
    """
    client = _resolve_client(client)
    ensure_bucket(client)

    client.put_object(
        BUCKET_NAME,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    logger.info("Uploaded %s (%d bytes)", object_name, len(data))
    return f"{BUCKET_NAME}/{object_name}"


def upload_file(
    object_name: str,
    file_path: Path | str,
    content_type: str = "application/octet-stream",
    client: Any = None,
) -> str:
    """Upload a local file to MinIO.

    Returns:
        The storage path in format "bucket/object_name".
    """
    client = _resolve_client(client)
    ensure_bucket(client)

    client.fput_object(
        BUCKET_NAME,
        object_name,
        str(file_path),
        content_type=content_type,
    )
    logger.info("Uploaded file %s as %s", file_path, object_name)
    return f"{BUCKET_NAME}/{object_name}"


def download_bytes(
    object_name: str,
    client: Any = None,
) -> bytes:
    """Download an object from MinIO as bytes.

    Raises:
        S3Error: If the object does not exist.
    """
    client = _resolve_client(client)

    response = client.get_object(BUCKET_NAME, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_object(
    object_name: str,
    client: Any = None,
) -> None:
    """Delete an object from MinIO."""
    client = _resolve_client(client)
    client.remove_object(BUCKET_NAME, object_name)
    logger.info("Deleted %s", object_name)


def object_exists(
    object_name: str,
    client: Any = None,
) -> bool:
    """Check if an object exists in MinIO."""
    client = _resolve_client(client)
    try:
        client.stat_object(BUCKET_NAME, object_name)
        return True
    except S3Error:
        return False


# ---------------------------------------------------------------------------
# fal.ai URL upload (for Kontext image_url parameter)
# ---------------------------------------------------------------------------

import fal_client  # type: ignore[import-untyped]


def upload_to_fal(
    data: bytes,
    content_type: str = "image/jpeg",
) -> str:
    """Upload image bytes to fal.ai storage and return a public URL.

    fal.ai's Kontext model requires a publicly accessible URL for
    ``image_url``. Local paths and localhost MinIO URLs are not
    reachable from fal.ai servers. This function uploads to fal.ai's
    own CDN and returns the hosted URL.

    Args:
        data: Raw image bytes.
        content_type: MIME type (default ``image/jpeg``).

    Returns:
        Publicly accessible fal.ai-hosted URL.
    """
    url: str = fal_client.upload(data, content_type=content_type)
    logger.info("Uploaded %d bytes to fal.ai: %s", len(data), url[:80])
    return url
