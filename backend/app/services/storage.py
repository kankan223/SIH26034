"""Object storage service per tech-stack.md §8 and prd.md §25.5.

MinIO/S3-compatible client for:
- Raw image upload with content-hash deduplication (FR-001)
- Evidence crop storage
- Report PDF storage
- Presigned URL generation for time-limited access
- Server-side image re-encoding to strip EXIF/embedded payloads (prd.md §25.5)
- Bucket initialization on startup

Uses boto3 S3-compatible API against self-hosted MinIO.
"""

import io
import logging
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

# Bucket names from environment
BUCKET_IMAGES = settings.S3_BUCKET_IMAGES
BUCKET_EVIDENCE = settings.S3_BUCKET_EVIDENCE
BUCKET_REPORTS = settings.S3_BUCKET_REPORTS

ALL_BUCKETS = [BUCKET_IMAGES, BUCKET_EVIDENCE, BUCKET_REPORTS]


# ---------------------------------------------------------------------------
# S3 client factory
# ---------------------------------------------------------------------------

def _get_s3_client():
    """Create a boto3 S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
        region_name="us-east-1",
    )


# ---------------------------------------------------------------------------
# Bucket initialization
# ---------------------------------------------------------------------------

def ensure_buckets():
    """Create required buckets if they don't exist.

    Called on app startup to guarantee buckets are available.
    Idempotent: safe to call multiple times.
    """
    s3 = _get_s3_client()
    for bucket_name in ALL_BUCKETS:
        try:
            s3.head_bucket(Bucket=bucket_name)
            logger.debug(f"Bucket '{bucket_name}' already exists")
        except ClientError:
            try:
                s3.create_bucket(Bucket=bucket_name)
                logger.info(f"Created bucket '{bucket_name}'")
            except ClientError as e:
                logger.error(f"Failed to create bucket '{bucket_name}': {e}")
                raise


# ---------------------------------------------------------------------------
# EXIF stripping via re-encoding
# ---------------------------------------------------------------------------

def _strip_exif_and_reencode(image_bytes: bytes) -> bytes:
    """Re-encode image to strip EXIF data and embedded payloads.

    Per prd.md §25.5: server-side image re-encoding strips EXIF metadata
    and any embedded payloads on ingest.

    Opens the image with Pillow (which discards EXIF by default when saving)
    and re-encodes as JPEG with quality 92.

    Args:
        image_bytes: Raw image bytes (any format Pillow supports).

    Returns:
        Re-encoded JPEG bytes with EXIF stripped.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGB if necessary (handles RGBA, palette, etc.)
    if img.mode != "RGB":
        img = img.convert("RGB")

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Storage URL helpers
# ---------------------------------------------------------------------------

def _parse_storage_url(storage_url: str) -> tuple[str, str]:
    """Parse a storage URL into (bucket, key).

    Supports formats:
    - minio://bucket/key
    - s3://bucket/key
    """
    parsed = urlparse(storage_url)
    bucket = parsed.hostname or parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


# ---------------------------------------------------------------------------
# Upload functions
# ---------------------------------------------------------------------------

def upload_image(file_bytes: bytes, content_hash: str) -> str:
    """Upload an image to object storage with content-hash deduplication.

    Per FR-001: duplicate uploads are detected via content hash and linked
    to the existing storage URL (no duplicate storage).

    Per prd.md §25.5: images are re-encoded to strip EXIF data.

    Args:
        file_bytes: Raw image bytes.
        content_hash: SHA-256 content hash for deduplication.

    Returns:
        Storage URL in format: minio://lm-images/{content_hash[:32]}.jpg
    """
    s3 = _get_s3_client()
    key = f"{content_hash[:32]}.jpg"

    # Check if already uploaded (deduplication)
    try:
        s3.head_object(Bucket=BUCKET_IMAGES, Key=key)
        logger.info(f"Image deduplicated: {content_hash[:16]}... already exists")
        return f"minio://{BUCKET_IMAGES}/{key}"
    except ClientError:
        pass  # Not found — proceed with upload

    # Re-encode to strip EXIF per prd.md §25.5
    reencoded = _strip_exif_and_reencode(file_bytes)

    s3.put_object(
        Bucket=BUCKET_IMAGES,
        Key=key,
        Body=reencoded,
        ContentType="image/jpeg",
    )
    logger.info(f"Uploaded image: {key} ({len(reencoded)} bytes)")
    return f"minio://{BUCKET_IMAGES}/{key}"


def upload_evidence_crop(
    crop_bytes: bytes,
    inspection_id: str,
    violation_id: str,
) -> str:
    """Upload an evidence crop image to object storage.

    Evidence crops are bounding-box crops from violation images,
    stored separately for evidence cards per design.md §7.3.

    Args:
        crop_bytes: Cropped image bytes.
        inspection_id: UUID of the parent inspection.
        violation_id: UUID of the violation.

    Returns:
        Storage URL: minio://lm-evidence/{inspection_id}/{violation_id}.jpg
    """
    s3 = _get_s3_client()
    key = f"{inspection_id}/{violation_id}.jpg"

    # Re-encode to strip EXIF
    reencoded = _strip_exif_and_reencode(crop_bytes)

    s3.put_object(
        Bucket=BUCKET_EVIDENCE,
        Key=key,
        Body=reencoded,
        ContentType="image/jpeg",
    )
    logger.info(f"Uploaded evidence crop: {key} ({len(reencoded)} bytes)")
    return f"minio://{BUCKET_EVIDENCE}/{key}"


def upload_report(pdf_bytes: bytes, inspection_id: str) -> str:
    """Upload a generated PDF report to object storage.

    Reports are generated by WeasyPrint per prd.md §24 and stored
    for retrieval by inspectors.

    Args:
        pdf_bytes: PDF document bytes.
        inspection_id: UUID of the inspection.

    Returns:
        Storage URL: minio://lm-reports/{inspection_id}/report.pdf
    """
    s3 = _get_s3_client()
    key = f"{inspection_id}/report.pdf"

    s3.put_object(
        Bucket=BUCKET_REPORTS,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )
    logger.info(f"Uploaded report: {key} ({len(pdf_bytes)} bytes)")
    return f"minio://{BUCKET_REPORTS}/{key}"


# ---------------------------------------------------------------------------
# Presigned URL generation
# ---------------------------------------------------------------------------

def get_presigned_url(storage_url: str, expiry_seconds: int = 3600) -> str:
    """Generate a presigned URL for time-limited access to a stored object.

    Per prd.md §25.1: presigned URLs for time-limited access.

    Args:
        storage_url: Internal storage URL (minio://bucket/key).
        expiry_seconds: URL validity duration (default: 1 hour).

    Returns:
        Presigned URL string.
    """
    s3 = _get_s3_client()
    bucket, key = _parse_storage_url(storage_url)

    presigned = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry_seconds,
    )
    return presigned


# ---------------------------------------------------------------------------
# Download / verification helper
# ---------------------------------------------------------------------------

def download_object(storage_url: str) -> bytes:
    """Download an object from storage by its URL.

    Args:
        storage_url: Internal storage URL (minio://bucket/key).

    Returns:
        Object bytes.
    """
    s3 = _get_s3_client()
    bucket, key = _parse_storage_url(storage_url)

    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def object_exists(storage_url: str) -> bool:
    """Check if an object exists in storage.

    Args:
        storage_url: Internal storage URL (minio://bucket/key).

    Returns:
        True if the object exists.
    """
    s3 = _get_s3_client()
    bucket, key = _parse_storage_url(storage_url)

    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False
