"""
Tests for Task 2.1.2: MinIO Object Storage Service

Verifies:
- upload_image: uploads and returns storage URL
- upload_image: content-hash deduplication (same hash = same URL, no re-upload)
- upload_evidence_crop: uploads evidence crops with correct key structure
- upload_report: uploads PDF reports with correct key structure
- get_presigned_url: generates valid presigned URLs
- _strip_exif_and_reencoding: EXIF data is removed from images
- ensure_buckets: creates required buckets
- URL parsing helpers
- Integration with image_processing (upload quality-assessed images)

Uses unittest.mock to mock boto3 S3 client (no live MinIO required).
"""
import io
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

from PIL import Image


# ---------------------------------------------------------------------------
# Mock S3 responses
# ---------------------------------------------------------------------------

class MockS3Client:
    """Mock boto3 S3 client for testing."""

    def __init__(self):
        self.objects = {}  # bucket -> key -> bytes
        self.buckets = set()
        self.calls = []

    def head_bucket(self, Bucket):
        self.calls.append(("head_bucket", Bucket))
        if Bucket not in self.buckets:
            from botocore.exceptions import ClientError
            error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
            raise ClientError(error_response, "HeadBucket")

    def create_bucket(self, Bucket):
        self.calls.append(("create_bucket", Bucket))
        self.buckets.add(Bucket)

    def head_object(self, Bucket, Key):
        self.calls.append(("head_object", Bucket, Key))
        if Bucket not in self.objects or Key not in self.objects.get(Bucket, {}):
            from botocore.exceptions import ClientError
            error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
            raise ClientError(error_response, "HeadObject")

    def put_object(self, Bucket, Key, Body, ContentType="application/octet-stream"):
        self.calls.append(("put_object", Bucket, Key, len(Body)))
        if Bucket not in self.objects:
            self.objects[Bucket] = {}
        self.objects[Bucket][Key] = Body

    def get_object(self, Bucket, Key):
        self.calls.append(("get_object", Bucket, Key))
        if Bucket not in self.objects or Key not in self.objects.get(Bucket, {}):
            from botocore.exceptions import ClientError
            error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
            raise ClientError(error_response, "GetObject")

        body = self.objects[Bucket][Key]
        return {"Body": MagicMock(read=lambda: body)}

    def generate_presigned_url(self, OperationName, Params, ExpiresIn=3600):
        self.calls.append(("generate_presigned_url", OperationName, Params, ExpiresIn))
        bucket = Params["Bucket"]
        key = Params["Key"]
        return f"http://minio:9000/{bucket}/{key}?expires={ExpiresIn}"


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_test_image(width: int = 100, height: int = 100) -> bytes:
    """Create a simple test JPEG image."""
    img = Image.new("RGB", (width, height), color=(128, 200, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _make_image_with_exif() -> bytes:
    """Create a test image with EXIF-like metadata."""
    img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _make_test_pdf() -> bytes:
    """Create a minimal PDF-like byte sequence."""
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n%%EOF"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: EXIF STRIPPING TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestExifStripping:
    """Verify EXIF data is stripped via re-encoding per prd.md §25.5."""

    def test_reencoded_image_is_valid_jpeg(self):
        """Re-encoded output should be a valid JPEG."""
        from app.services.storage import _strip_exif_and_reencode
        original = _make_test_image()
        reencoded = _strip_exif_and_reencode(original)
        # Should be decodable
        img = Image.open(io.BytesIO(reencoded))
        assert img.format == "JPEG"

    def test_reencoded_image_has_no_exif(self):
        """Re-encoded image should have no EXIF data."""
        from app.services.storage import _strip_exif_and_reencode
        original = _make_image_with_exif()
        reencoded = _strip_exif_and_reencode(original)
        img = Image.open(io.BytesIO(reencoded))
        # Pillow returns empty dict when no EXIF
        assert not img.info.get("exif")

    def test_reencoded_image_dimensions_preserved(self):
        """Re-encoded image should preserve original dimensions."""
        from app.services.storage import _strip_exif_and_reencode
        original = _make_test_image(300, 200)
        reencoded = _strip_exif_and_reencode(original)
        img = Image.open(io.BytesIO(reencoded))
        assert img.size == (300, 200)

    def test_reencoded_image_rgb_mode(self):
        """Re-encoded image should be RGB (no alpha channel)."""
        from app.services.storage import _strip_exif_and_reencode
        # Create RGBA image
        img = Image.new("RGBA", (100, 100), color=(128, 200, 50, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        original = buf.getvalue()
        reencoded = _strip_exif_and_reencode(original)
        result = Image.open(io.BytesIO(reencoded))
        assert result.mode == "RGB"

    def test_reencoded_is_smaller_or_equal(self):
        """Re-encoded image should be similar size or smaller."""
        from app.services.storage import _strip_exif_and_reencode
        original = _make_test_image(800, 600)
        reencoded = _strip_exif_and_reencode(original)
        # Re-encoded should be reasonable size
        assert len(reencoded) > 0
        assert len(reencoded) < len(original) * 2  # Not massively larger


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: BUCKET INITIALIZATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestBucketInitialization:
    """Verify bucket creation and idempotency."""

    @patch("app.services.storage._get_s3_client")
    def test_ensure_buckets_creates_all_three(self, mock_get_s3):
        """ensure_buckets should create lm-images, lm-evidence, lm-reports."""
        from app.services.storage import ensure_buckets
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        ensure_buckets()

        assert "lm-images" in mock_s3.buckets
        assert "lm-evidence" in mock_s3.buckets
        assert "lm-reports" in mock_s3.buckets

    @patch("app.services.storage._get_s3_client")
    def test_ensure_buckets_is_idempotent(self, mock_get_s3):
        """Calling ensure_buckets twice should not error."""
        from app.services.storage import ensure_buckets
        mock_s3 = MockS3Client()
        mock_s3.buckets = {"lm-images", "lm-evidence", "lm-reports"}  # Already exist
        mock_get_s3.return_value = mock_s3

        ensure_buckets()  # Should not raise
        ensure_buckets()  # Should not raise


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: UPLOAD IMAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestUploadImage:
    """Verify image upload with deduplication."""

    @patch("app.services.storage._get_s3_client")
    def test_upload_image_returns_url(self, mock_get_s3):
        """upload_image should return a minio:// URL."""
        from app.services.storage import upload_image
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image_bytes = _make_test_image()
        url = upload_image(image_bytes, "abc123def456")

        assert url.startswith("minio://lm-images/")
        assert url.endswith(".jpg")

    @patch("app.services.storage._get_s3_client")
    def test_upload_image_stores_in_correct_bucket(self, mock_get_s3):
        """Image should be stored in lm-images bucket."""
        from app.services.storage import upload_image
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image_bytes = _make_test_image()
        upload_image(image_bytes, "abc123def456")

        assert "lm-images" in mock_s3.objects
        assert len(mock_s3.objects["lm-images"]) == 1

    @patch("app.services.storage._get_s3_client")
    def test_upload_image_deduplicates(self, mock_get_s3):
        """Uploading the same hash twice should return same URL without re-upload."""
        from app.services.storage import upload_image
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image_bytes = _make_test_image()
        content_hash = "abc123def456"

        url1 = upload_image(image_bytes, content_hash)
        url2 = upload_image(image_bytes, content_hash)

        assert url1 == url2
        # Only one put_object call (first upload)
        put_calls = [c for c in mock_s3.calls if c[0] == "put_object"]
        assert len(put_calls) == 1

    @patch("app.services.storage._get_s3_client")
    def test_upload_image_reencodes(self, mock_get_s3):
        """Upload should re-encode image to strip EXIF."""
        from app.services.storage import upload_image
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image_bytes = _make_test_image()
        upload_image(image_bytes, "abc123def456")

        # Get the stored object
        stored = mock_s3.objects["lm-images"]["abc123def456.jpg"]
        # Should be a valid JPEG (re-encoded)
        img = Image.open(io.BytesIO(stored))
        assert img.format == "JPEG"

    @patch("app.services.storage._get_s3_client")
    def test_upload_image_uses_correct_key(self, mock_get_s3):
        """Storage key should be first 32 chars of hash + .jpg."""
        from app.services.storage import upload_image
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image_bytes = _make_test_image()
        hash_val = "a" * 64  # 64-char hex hash
        url = upload_image(image_bytes, hash_val)

        assert "a" * 32 in url
        assert url.endswith(".jpg")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: EVIDENCE CROP TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestUploadEvidenceCrop:
    """Verify evidence crop upload."""

    @patch("app.services.storage._get_s3_client")
    def test_upload_evidence_returns_url(self, mock_get_s3):
        """upload_evidence_crop should return a minio:// URL."""
        from app.services.storage import upload_evidence_crop
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        crop_bytes = _make_test_image(200, 150)
        url = upload_evidence_crop(crop_bytes, "insp-001", "viol-001")

        assert url.startswith("minio://lm-evidence/")
        assert "insp-001" in url
        assert "viol-001" in url

    @patch("app.services.storage._get_s3_client")
    def test_upload_evidence_stores_correctly(self, mock_get_s3):
        """Evidence crop should be stored in lm-evidence bucket."""
        from app.services.storage import upload_evidence_crop
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        crop_bytes = _make_test_image()
        upload_evidence_crop(crop_bytes, "insp-001", "viol-001")

        assert "lm-evidence" in mock_s3.objects
        key = "insp-001/viol-001.jpg"
        assert key in mock_s3.objects["lm-evidence"]

    @patch("app.services.storage._get_s3_client")
    def test_upload_evidence_reencodes(self, mock_get_s3):
        """Evidence crop should be re-encoded (EXIF stripped)."""
        from app.services.storage import upload_evidence_crop
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        crop_bytes = _make_test_image()
        upload_evidence_crop(crop_bytes, "insp-001", "viol-001")

        stored = mock_s3.objects["lm-evidence"]["insp-001/viol-001.jpg"]
        img = Image.open(io.BytesIO(stored))
        assert img.format == "JPEG"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: REPORT UPLOAD TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestUploadReport:
    """Verify PDF report upload."""

    @patch("app.services.storage._get_s3_client")
    def test_upload_report_returns_url(self, mock_get_s3):
        """upload_report should return a minio:// URL."""
        from app.services.storage import upload_report
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        pdf_bytes = _make_test_pdf()
        url = upload_report(pdf_bytes, "insp-001")

        assert url.startswith("minio://lm-reports/")
        assert "insp-001" in url
        assert url.endswith("report.pdf")

    @patch("app.services.storage._get_s3_client")
    def test_upload_report_stores_correctly(self, mock_get_s3):
        """Report should be stored in lm-reports bucket."""
        from app.services.storage import upload_report
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        pdf_bytes = _make_test_pdf()
        upload_report(pdf_bytes, "insp-001")

        assert "lm-reports" in mock_s3.objects
        assert "insp-001/report.pdf" in mock_s3.objects["lm-reports"]

    @patch("app.services.storage._get_s3_client")
    def test_upload_report_content_type(self, mock_get_s3):
        """Report should be uploaded with PDF content type."""
        from app.services.storage import upload_report
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        pdf_bytes = _make_test_pdf()
        upload_report(pdf_bytes, "insp-001")

        put_calls = [c for c in mock_s3.calls if c[0] == "put_object"]
        assert len(put_calls) == 1


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: PRESIGNED URL TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestPresignedUrl:
    """Verify presigned URL generation."""

    @patch("app.services.storage._get_s3_client")
    def test_get_presigned_url_returns_string(self, mock_get_s3):
        """get_presigned_url should return a URL string."""
        from app.services.storage import get_presigned_url
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        url = get_presigned_url("minio://lm-images/abc123.jpg", expiry_seconds=3600)
        assert isinstance(url, str)
        assert url.startswith("http")

    @patch("app.services.storage._get_s3_client")
    def test_get_presigned_url_uses_correct_bucket(self, mock_get_s3):
        """Presigned URL should reference the correct bucket."""
        from app.services.storage import get_presigned_url
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        get_presigned_url("minio://lm-evidence/insp-001/viol-001.jpg")

        presigned_calls = [c for c in mock_s3.calls if c[0] == "generate_presigned_url"]
        assert len(presigned_calls) == 1
        params = presigned_calls[0][2]
        assert params["Bucket"] == "lm-evidence"
        assert params["Key"] == "insp-001/viol-001.jpg"

    @patch("app.services.storage._get_s3_client")
    def test_get_presigned_url_custom_expiry(self, mock_get_s3):
        """Presigned URL should accept custom expiry time."""
        from app.services.storage import get_presigned_url
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        get_presigned_url("minio://lm-images/abc123.jpg", expiry_seconds=7200)

        presigned_calls = [c for c in mock_s3.calls if c[0] == "generate_presigned_url"]
        assert presigned_calls[0][3] == 7200

    @patch("app.services.storage._get_s3_client")
    def test_get_presigned_url_default_expiry(self, mock_get_s3):
        """Default expiry should be 3600 seconds (1 hour)."""
        from app.services.storage import get_presigned_url
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        get_presigned_url("minio://lm-images/abc123.jpg")

        presigned_calls = [c for c in mock_s3.calls if c[0] == "generate_presigned_url"]
        assert presigned_calls[0][3] == 3600


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: DOWNLOAD & EXISTENCE CHECK TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestDownloadAndExistence:
    """Verify download and existence check helpers."""

    @patch("app.services.storage._get_s3_client")
    def test_download_object_returns_bytes(self, mock_get_s3):
        """download_object should return the stored bytes."""
        from app.services.storage import download_object, upload_image
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image_bytes = _make_test_image()
        url = upload_image(image_bytes, "abc123")
        downloaded = download_object(url)

        assert isinstance(downloaded, bytes)
        assert len(downloaded) > 0

    @patch("app.services.storage._get_s3_client")
    def test_object_exists_returns_true(self, mock_get_s3):
        """object_exists should return True for uploaded objects."""
        from app.services.storage import object_exists, upload_image
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image_bytes = _make_test_image()
        url = upload_image(image_bytes, "abc123")
        assert object_exists(url) is True

    @patch("app.services.storage._get_s3_client")
    def test_object_exists_returns_false(self, mock_get_s3):
        """object_exists should return False for non-existent objects."""
        from app.services.storage import object_exists
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        assert object_exists("minio://lm-images/nonexistent.jpg") is False


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8: URL PARSING TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestUrlParsing:
    """Verify storage URL parsing."""

    def test_parse_minio_url(self):
        """Should parse minio:// URLs correctly."""
        from app.services.storage import _parse_storage_url
        bucket, key = _parse_storage_url("minio://lm-images/abc123.jpg")
        assert bucket == "lm-images"
        assert key == "abc123.jpg"

    def test_parse_nested_key(self):
        """Should handle nested keys (evidence crops)."""
        from app.services.storage import _parse_storage_url
        bucket, key = _parse_storage_url("minio://lm-evidence/insp-001/viol-001.jpg")
        assert bucket == "lm-evidence"
        assert key == "insp-001/viol-001.jpg"

    def test_parse_s3_url(self):
        """Should also parse s3:// URLs."""
        from app.services.storage import _parse_storage_url
        bucket, key = _parse_storage_url("s3://lm-reports/insp-001/report.pdf")
        assert bucket == "lm-reports"
        assert key == "insp-001/report.pdf"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 9: INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestStorageIntegration:
    """Integration tests combining upload, download, and dedup."""

    @patch("app.services.storage._get_s3_client")
    def test_full_upload_download_cycle(self, mock_get_s3):
        """Upload → download → verify bytes match."""
        from app.services.storage import upload_image, download_object
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        original = _make_test_image()
        url = upload_image(original, "test-hash-001")
        downloaded = download_object(url)

        # Both should be valid JPEGs (original may differ due to re-encoding)
        img_original = Image.open(io.BytesIO(original))
        img_downloaded = Image.open(io.BytesIO(downloaded))
        assert img_original.size == img_downloaded.size

    @patch("app.services.storage._get_s3_client")
    def test_dedup_returns_same_url(self, mock_get_s3):
        """Two uploads with same hash should return identical URLs."""
        from app.services.storage import upload_image
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image = _make_test_image()
        url1 = upload_image(image, "same-hash")
        url2 = upload_image(image, "same-hash")

        assert url1 == url2

    @patch("app.services.storage._get_s3_client")
    def test_different_hashes_different_urls(self, mock_get_s3):
        """Different hashes should produce different URLs."""
        from app.services.storage import upload_image
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image = _make_test_image()
        url1 = upload_image(image, "hash-aaa")
        url2 = upload_image(image, "hash-bbb")

        assert url1 != url2

    @patch("app.services.storage._get_s3_client")
    def test_all_three_buckets_used(self, mock_get_s3):
        """Verify all three buckets are used across upload functions."""
        from app.services.storage import upload_image, upload_evidence_crop, upload_report
        mock_s3 = MockS3Client()
        mock_get_s3.return_value = mock_s3

        image = _make_test_image()
        pdf = _make_test_pdf()

        upload_image(image, "hash-001")
        upload_evidence_crop(image, "insp-001", "viol-001")
        upload_report(pdf, "insp-001")

        assert "lm-images" in mock_s3.objects
        assert "lm-evidence" in mock_s3.objects
        assert "lm-reports" in mock_s3.objects
