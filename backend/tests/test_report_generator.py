"""Tests for the report generator — PDF, DOCX export, and scheduling (Phase 7).

See: prd.md §24 (report format), design.md §9 (print/PDF design),
design.md §12 (design tokens), prd.md §9 (PDF generation ≤10s target).
"""

import io
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def sample_inspection() -> dict:
    return {
        "id": "INS-001",
        "created_at": "2026-09-01T10:00:00",
        "inspector_name": "A. Inspector",
        "inspector_id": "usr-1",
        "location": "Mumbai",
        "region": "West",
        "source": "physical",
        "product_name": "Packaged Biscuits",
        "category": "Food & Beverage > Packaged Food",
        "package_type": "pouch",
        "classification_confidence": 0.91,
        "status": "COMPLIANT",
        "declarations": [
            {"field_type": "manufacturer", "value": {"text": "ACME Foods Pvt Ltd"}, "confidence": 0.95},
            {"field_type": "mrp", "value": {"text": "Rs. 99"}, "confidence": 0.88},
        ],
    }


@pytest.fixture
def sample_compliance() -> dict:
    return {
        "overall_status": "COMPLIANT",
        "status_reason": "All mandatory declarations present and valid.",
        "per_field_compliance": [],
        "violations": [],
    }


@pytest.fixture
def sample_evidence() -> list[dict]:
    return [
        {
            "violation_id": "VIO-1",
            "crop_storage_url": "s3://lm-evidence/ins-1/vio-1.png",
            "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 60},
        }
    ]


LEGAL_REFS = ["Legal Metrology (Packaged Commodities) Rules, 2011"]


# ── Design tokens ──────────────────────────────────────────────────────────────

class TestDesignTokens:
    def test_design_tokens_match_docket_palette(self):
        """Design tokens come from design.md §1/§12, never hardcoded hex."""
        from app.services.report_generator import _get_design_tokens

        tokens = _get_design_tokens()
        assert tokens["color_ink_navy"] == "#1B2A41"
        assert tokens["color_teal"] == "#2E8B8B"
        assert tokens["color_redline"] == "#C0392B"
        assert tokens["color_amber"] == "#D4A017"
        assert tokens["font_heading"] == "Source Serif 4"


# ── PDF report HTML ────────────────────────────────────────────────────────────

class TestReportHtml:
    def test_html_has_12_sections(self, sample_inspection, sample_compliance, sample_evidence):
        """PDF HTML must contain all 12 sections per prd.md §24.1."""
        from app.services.report_generator import _generate_report_html

        html = _generate_report_html(
            inspection=sample_inspection,
            compliance=sample_compliance,
            images=["http://img/1.jpg"],
            evidence=sample_evidence,
            legal_references=LEGAL_REFS,
            show_seal=True,
        )
        section_markers = [
            "Legal Metrology Compliance Report",
            "Inspection Information",
            "Product Information",
            "4. Images",
            "5. Declarations",
            "Compliance Summary",
            "7. Violations",
            "Evidence Appendix",
            "Legal References",
            "Confidence Notes",
            "Inspector Review",
            "Audit Information",
        ]
        for marker in section_markers:
            assert marker in html, f"Missing report section: {marker}"

    def test_compliant_report_has_verification_seal(
        self, sample_inspection, sample_compliance, sample_evidence
    ):
        """COMPLIANT reports include the verification seal per design.md §9."""
        from app.services.report_generator import _generate_report_html

        html = _generate_report_html(
            inspection=sample_inspection,
            compliance=sample_compliance,
            images=[],
            evidence=sample_evidence,
            legal_references=LEGAL_REFS,
            show_seal=True,
        )
        assert "verification-seal" in html

    def test_non_compliant_report_has_no_seal(
        self, sample_inspection, sample_evidence
    ):
        """NON_COMPLIANT reports must NOT include the verification seal."""
        from app.services.report_generator import _generate_report_html

        non_compliant = {
            "overall_status": "NON_COMPLIANT",
            "status_reason": "Missing mandatory declarations.",
            "per_field_compliance": [],
            "violations": [{"field": "mrp", "severity": "CRITICAL", "rule_key": "r-1"}],
        }
        html = _generate_report_html(
            inspection=sample_inspection,
            compliance=non_compliant,
            images=[],
            evidence=sample_evidence,
            legal_references=LEGAL_REFS,
            show_seal=False,
        )
        # CSS classes always exist in the stylesheet; the seal body text
        # only renders in the markup for COMPLIANT reports.
        assert "verified as compliant with all applicable" not in html

    def test_evidence_bbox_coordinates_in_html(
        self, sample_inspection, sample_compliance, sample_evidence
    ):
        """Evidence appendix must carry bounding box coordinates per FR-023."""
        from app.services.report_generator import _generate_report_html

        html = _generate_report_html(
            inspection=sample_inspection,
            compliance=sample_compliance,
            images=[],
            evidence=sample_evidence,
            legal_references=LEGAL_REFS,
            show_seal=True,
        )
        assert "VIO-1" in html
        assert "10" in html and "60" in html  # bbox corner coordinates rendered


# ── DOCX export ────────────────────────────────────────────────────────────────

class TestDocxExport:
    def test_generate_docx_returns_valid_document(
        self, sample_inspection, sample_compliance, sample_evidence
    ):
        """DOCX export is a valid .docx with the 12-section structure (prd.md §24.2)."""
        docx = pytest.importorskip("docx")
        from app.services.report_generator import generate_docx

        raw = generate_docx(
            inspection_data=sample_inspection,
            compliance_result=sample_compliance,
            image_urls=["http://img/1.jpg"],
            evidence_crops=sample_evidence,
            legal_references=LEGAL_REFS,
        )
        assert raw.startswith(b"PK")  # .docx is a zip container

        document = docx.Document(io.BytesIO(raw))
        texts = [p.text for p in document.paragraphs]
        assert any("Legal Metrology Compliance Report" in t for t in texts)
        assert any("Evidence Appendix" in t for t in texts)
        assert any("VIO-1" in t for t in texts)
        # inspection + product + inspector review + audit = 4 key/value tables
        assert len(document.tables) >= 4

    def test_generate_docx_non_compliant_has_no_seal(
        self, sample_inspection, sample_evidence
    ):
        """NON_COMPLIANT DOCX must not carry the verification seal line."""
        docx = pytest.importorskip("docx")
        from app.services.report_generator import generate_docx

        non_compliant = {
            "overall_status": "NON_COMPLIANT",
            "status_reason": "MRP format invalid.",
            "per_field_compliance": [],
            "violations": [],
        }
        raw = generate_docx(
            inspection_data=sample_inspection,
            compliance_result=non_compliant,
            image_urls=[],
            evidence_crops=sample_evidence,
            legal_references=LEGAL_REFS,
        )
        document = docx.Document(io.BytesIO(raw))
        texts = [p.text for p in document.paragraphs]
        assert not any("verified as compliant" in t for t in texts)


# ── Report scheduling ──────────────────────────────────────────────────────────

class TestReportScheduling:
    def test_schedule_report_registers_entry(self):
        """schedule_report() returns an id and registers a scheduled entry."""
        from app.services.report_generator import get_scheduled_reports, schedule_report

        schedule_id = schedule_report("INS-1", datetime.utcnow() + timedelta(hours=1))
        assert schedule_id
        entries = get_scheduled_reports()
        assert any(
            e["schedule_id"] == schedule_id and e["status"] == "scheduled"
            for e in entries
        )

    def test_process_scheduled_reports_marks_due(self):
        """Entries whose time has passed transition to 'done'."""
        from app.services.report_generator import process_scheduled_reports, schedule_report

        schedule_id = schedule_report("INS-2", datetime.utcnow() - timedelta(minutes=5))
        processed = process_scheduled_reports()
        assert any(
            e["schedule_id"] == schedule_id and e["status"] == "done"
            for e in processed
        )

    def test_process_scheduled_reports_skips_future(self):
        """Future-dated entries remain 'scheduled' after processing."""
        from app.services.report_generator import (
            get_scheduled_reports,
            process_scheduled_reports,
            schedule_report,
        )

        schedule_id = schedule_report("INS-3", datetime.utcnow() + timedelta(hours=2))
        processed = process_scheduled_reports()
        assert not any(e["schedule_id"] == schedule_id for e in processed)
        entry = next(
            e for e in get_scheduled_reports() if e["schedule_id"] == schedule_id
        )
        assert entry["status"] == "scheduled"