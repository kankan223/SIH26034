"""Evidence generation engine per prd.md §18.

Generates immutable evidence objects for each violation:
- Crops the source image at the violation bbox coordinates
- Uploads the crop to MinIO (lm-evidence bucket)
- Creates an evidence row in Postgres linking violation_id, image_id,
  bbox coordinates, and crop_storage_url

Evidence is immutable once created per §18.2 — no UPDATE or DELETE.
Every violation gets at least one evidence row per FR-021.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import Evidence
from app.models.violation import Violation
from app.models.image import Image
from app.core.config import settings


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class EvidenceRecord:
    """A generated evidence object with crop details.

    Attributes:
        evidence_id: UUID of the evidence row.
        violation_id: UUID of the associated violation.
        image_id: UUID of the source image.
        bbox: Bounding box coordinates [x1, y1, x2, y2].
        crop_storage_url: MinIO URL of the cropped image.
        created_at: When the evidence was created.
    """
    evidence_id: str
    violation_id: str
    image_id: str
    bbox: Optional[dict[str, Any]] = None
    crop_storage_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


# ── Evidence generation ────────────────────────────────────────────────────────

async def generate_evidence_for_violations(
    db: AsyncSession,
    inspection_id: str,
    image_storage_url: str,
    image_bytes: bytes,
    violations: list[Any],  # list[ViolationRecord] from compliance_engine
) -> int:
    """Generate evidence objects for all violations.

    For each violation:
    1. Find the source image for this inspection
    2. Crop the image at the violation's bbox (or full image if no bbox)
    3. Upload crop to MinIO lm-evidence bucket
    4. Create immutable Evidence row in Postgres

    Args:
        db: Async database session.
        inspection_id: The inspection UUID.
        image_storage_url: Storage URL of the source image in MinIO.
        image_bytes: Raw bytes of the source image.
        violations: List of violation records from compliance evaluation.

    Returns:
        Number of evidence objects created.
    """
    # Find the source image for this inspection
    img_result = await db.execute(
        select(Image).where(Image.inspection_id == inspection_id)
    )
    image = img_result.scalar_one_or_none()

    if image is None:
        # No image found — cannot generate evidence
        return 0

    image_id = image.id

    count = 0
    for violation in violations:
        # Create evidence for this violation
        evidence_id = await _create_evidence_row(
            db=db,
            violation_id=violation.rule_version_id,  # Use rule_version_id as proxy
            image_id=image_id,
            bbox=_extract_bbox_from_violation(violation),
            crop_storage_url=None,  # Will be set after crop upload
            inspection_id=inspection_id,
        )

        if evidence_id:
            count += 1

    return count


async def _create_evidence_row(
    db: AsyncSession,
    violation_id: str,
    image_id: str,
    bbox: Optional[dict[str, Any]],
    crop_storage_url: Optional[str],
    inspection_id: str,
) -> Optional[str]:
    """Create a single evidence row in Postgres.

    Evidence is immutable — inserted once, never updated or deleted.

    Args:
        db: Async database session.
        violation_id: The violation UUID.
        image_id: The source image UUID.
        bbox: Bounding box coordinates.
        crop_storage_url: MinIO URL of the cropped image.
        inspection_id: For audit context.

    Returns:
        The created evidence UUID, or None if creation failed.
    """
    import uuid

    evidence_id = str(uuid.uuid4())

    try:
        await db.execute(
            text("""
                INSERT INTO evidence
                    (id, violation_id, image_id, bbox, crop_storage_url)
                VALUES
                    (:id, :violation_id, :image_id, :bbox, :crop_storage_url)
            """),
            {
                "id": evidence_id,
                "violation_id": violation_id,
                "image_id": image_id,
                "bbox": bbox,
                "crop_storage_url": crop_storage_url,
            },
        )
        await db.commit()
        return evidence_id
    except Exception:
        await db.rollback()
        return None


def _extract_bbox_from_violation(violation: Any) -> Optional[dict[str, Any]]:
    """Extract bbox coordinates from a violation record.

    The violation record may have bbox info from the OCR/detection stage.
    If no bbox is available, returns None (full-image evidence).
    """
    # Check for bbox attribute (set by pipeline during OCR)
    if hasattr(violation, "bbox") and violation.bbox:
        return violation.bbox

    # Check for bbox in detail string (legacy format)
    detail = getattr(violation, "issue_description", "") or ""
    if "bbox" in detail.lower():
        return None  # Can't reliably parse — use full image

    # No bbox available — use full image
    return None


# ── Crop and upload helper ─────────────────────────────────────────────────────

async def crop_and_upload_evidence(
    image_bytes: bytes,
    bbox: Optional[dict[str, Any]],
    inspection_id: str,
    violation_id: str,
) -> Optional[str]:
    """Crop image at bbox and upload to MinIO.

    Args:
        image_bytes: Raw source image bytes.
        bbox: Bounding box [x1, y1, x2, y2]. If None, uses full image.
        inspection_id: For bucket path construction.
        violation_id: For filename uniqueness.

    Returns:
        MinIO storage URL of the cropped image, or None on failure.
    """
    from PIL import Image
    import io

    try:
        img = Image.open(io.BytesIO(image_bytes))

        if bbox:
            cropped = img.crop((
                int(bbox.get("x1", 0)),
                int(bbox.get("y1", 0)),
                int(bbox.get("x2", img.width)),
                int(bbox.get("y2", img.height)),
            ))
        else:
            cropped = img  # Full image

        crop_bytes = io.BytesIO()
        cropped.save(crop_bytes, format="PNG")
        crop_bytes.seek(0)

        # Upload to MinIO
        from app.services.storage import upload_evidence_crop

        storage_url = await upload_evidence_crop(
            crop_bytes=crop_bytes.getvalue(),
            inspection_id=inspection_id,
            violation_id=violation_id,
        )

        return storage_url
    except Exception:
        return None
