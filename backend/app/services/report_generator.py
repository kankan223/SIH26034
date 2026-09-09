"""Report generator per prd.md §24.

Generates PDF reports from finalized inspections using WeasyPrint + Jinja2.
Report structure (12 sections per §24.1):
1. Cover page
2. Inspection Info
3. Product Info
4. Images
5. Declarations
6. Compliance Summary
7. Violations
8. Evidence Appendix
9. Legal References
10. Confidence Notes
11. Inspector Review
12. Audit Info

PDF generation target: ≤10s per prd.md §9.
COMPLIANT reports include verification seal per design.md §9.
NON_COMPLIANT reports do NOT include verification seal.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from weasyprint import HTML

from app.core.config import settings


# ── Report data classes ────────────────────────────────────────────────────────

@dataclass
class ReportResult:
    """Result of report generation.

    Attributes:
        report_id: UUID of the report row.
        pdf_storage_url: MinIO URL of the generated PDF.
        inspection_id: The inspection this report covers.
        json_export_url: MinIO URL of the JSON export (or None).
        generated_at: When the report was generated.
        generation_time_ms: Time taken to generate the PDF.
    """
    report_id: str
    pdf_storage_url: str
    inspection_id: str
    json_export_url: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.utcnow)
    generation_time_ms: float = 0.0


# ── Template environment ───────────────────────────────────────────────────────

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=True,
)


def _get_template(name: str):
    """Load a Jinja2 template by name."""
    return _jinja_env.get_template(name)


# ── Report generation ──────────────────────────────────────────────────────────

def generate_report(
    inspection_data: dict[str, Any],
    compliance_result: dict[str, Any],
    image_urls: list[str],
    evidence_crops: list[dict[str, Any]],
    legal_references: list[str],
    output_dir: Optional[str] = None,
) -> ReportResult:
    """Generate a PDF report for a finalized inspection.

    Args:
        inspection_data: Dict with inspection info (id, inspector, date, location, etc.).
        compliance_result: Dict with overall_status, status_reason, per_field_compliance, violations.
        image_urls: List of MinIO URLs for source images.
        evidence_crops: List of dicts with violation_id, bbox, crop_storage_url.
        legal_references: List of legal citation strings.
        output_dir: Directory to save PDF (default: tmp).

    Returns:
        ReportResult with storage URLs and timing.
    """
    import time
    import uuid
    import json
    import os

    start = time.time()

    # ── Render PDF via WeasyPrint ────────────────────────────────────

    # Use the report.html template when present; otherwise fall back to
    # the inline 12-section HTML generator so report generation still
    # works without a templates directory on disk.
    is_compliant = compliance_result.get("overall_status") == "COMPLIANT"
    try:
        template = _get_template("report.html")
        html_content = template.render(
            inspection=inspection_data,
            compliance=compliance_result,
            images=image_urls,
            evidence=evidence_crops,
            legal_references=legal_references,
            show_seal=is_compliant,
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            design_tokens=_get_design_tokens(),
        )
    except TemplateNotFound:
        html_content = _generate_report_html(
            inspection=inspection_data,
            compliance=compliance_result,
            images=image_urls,
            evidence=evidence_crops,
            legal_references=legal_references,
            show_seal=is_compliant,
        )

    # Generate PDF
    pdf_bytes = HTML(string=html_content).write_pdf()

    # ── Save PDF to MinIO ─────────────────────────────────────────────────────

    report_id = str(uuid.uuid4())
    pdf_filename = f"{report_id}.pdf"

    # Upload PDF to MinIO lm-reports bucket
    from app.services.storage import upload_report

    pdf_storage_url = upload_report(pdf_bytes, inspection_data["id"])

    # ── Generate JSON export ──────────────────────────────────────────────────

    export_data = {
        "report_id": report_id,
        "inspection_id": inspection_data["id"],
        "generated_at": datetime.utcnow().isoformat(),
        "compliance_status": compliance_result.get("overall_status"),
        "declarations": inspection_data.get("declarations", []),
        "violations": compliance_result.get("violations", []),
        "legal_references": legal_references,
    }

    json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")

    # Upload JSON to MinIO
    json_storage_url = upload_report(json_bytes, inspection_data["id"], filename=f"{report_id}.json")

    generation_time_ms = (time.time() - start) * 1000

    return ReportResult(
        report_id=report_id,
        pdf_storage_url=pdf_storage_url,
        json_export_url=json_storage_url,
        inspection_id=inspection_data["id"],
        generated_at=datetime.utcnow(),
        generation_time_ms=generation_time_ms,
    )


# ── DOCX export ────────────────────────────────────────────────────────────────

def _add_key_value_table(doc: Any, pairs: dict[str, Any]) -> None:
    """Append a two-column key/value table to the DOCX document."""
    table = doc.add_table(rows=0, cols=2)
    table.style = "Light Grid Accent 1"
    for key, value in pairs.items():
        row = table.add_row().cells
        row[0].text = key
        row[1].text = str(value)


def generate_docx(
    inspection_data: dict[str, Any],
    compliance_result: dict[str, Any],
    image_urls: list[str],
    evidence_crops: list[dict[str, Any]],
    legal_references: list[str],
) -> bytes:
    """Generate an editable DOCX report per prd.md §24.2.

    Mirrors the 12-section PDF structure so officers can annotate and
    re-export the report. Returns the .docx document as bytes (uploaded
    alongside the PDF to MinIO). Evidence crops are referenced by
    violation ID + bounding box; thumbnails are embedded in the PDF.

    Requires python-docx (tech-stack.md §5); raises ImportError if missing.
    """
    from docx import Document as DocxDocument
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    import io

    tokens = _get_design_tokens()

    def _rgb(hex_color: str) -> RGBColor:
        hex_color = hex_color.lstrip("#")
        return RGBColor(
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )

    doc = DocxDocument()

    # Base styles per design.md §12 (typography tokens)
    normal = doc.styles["Normal"]
    normal.font.name = tokens["font_body"]
    normal.font.size = Pt(10)

    # 1. Cover
    title = doc.add_heading("Docket — Legal Metrology Compliance Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = doc.add_paragraph("Ministry of Consumer Affairs, Food & Public Distribution")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Inspection Reference: {inspection_data.get('id', 'N/A')}")
    doc.add_paragraph(f"Classification: {compliance_result.get('overall_status', 'N/A')}")
    doc.add_page_break()

    # 2. Inspection info
    doc.add_heading("2. Inspection Information", level=1)
    _add_key_value_table(doc, {
        "Inspection ID": inspection_data.get("id", "N/A"),
        "Inspector": inspection_data.get("inspector_name", "N/A"),
        "Date": inspection_data.get("created_at", "N/A"),
        "Location": inspection_data.get("location", "N/A"),
        "Region": inspection_data.get("region", "N/A"),
        "Source": inspection_data.get("source", "N/A"),
    })

    # 3. Product info
    doc.add_heading("3. Product Information", level=1)
    _add_key_value_table(doc, {
        "Product Name": inspection_data.get("product_name", "N/A"),
        "Category": inspection_data.get("category", "N/A"),
        "Package Type": inspection_data.get("package_type", "N/A"),
        "Classifier Confidence": inspection_data.get("classification_confidence", "N/A"),
    })

    # 4. Images (referenced; binary embedding happens in the PDF)
    doc.add_heading("4. Images", level=1)
    if image_urls:
        for url in image_urls:
            doc.add_paragraph(url, style="List Bullet")
    else:
        doc.add_paragraph("No source images recorded.")

    # 5. Declarations
    doc.add_heading("5. Declarations", level=1)
    declarations = inspection_data.get("declarations", [])
    if declarations:
        table = doc.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        for i, header in enumerate(["Field", "Detected Value", "Confidence", "Status"]):
            table.rows[0].cells[i].text = header
        for decl in declarations:
            value = decl.get("value", {})
            text = value.get("text", "NOT_FOUND") if isinstance(value, dict) else str(value)
            status = "PASS" if decl.get("confidence", 0) >= 0.5 else "LOW_CONF"
            row = table.add_row().cells
            row[0].text = decl.get("field_type", "unknown")
            row[1].text = str(text)
            row[2].text = f"{decl.get('confidence', 0):.2f}"
            row[3].text = status
    else:
        doc.add_paragraph("No declarations recorded.")

    # 6. Compliance summary
    doc.add_heading("6. Compliance Summary", level=1)
    status = compliance_result.get("overall_status", "UNKNOWN")
    status_par = doc.add_paragraph(f"Overall Status: {status}")
    status_par.runs[0].bold = True
    doc.add_paragraph(compliance_result.get("status_reason", ""))

    # 7. Violations
    doc.add_heading("7. Violations", level=1)
    violations = compliance_result.get("violations", [])
    if violations:
        table = doc.add_table(rows=1, cols=5)
        table.style = "Light Grid Accent 1"
        for i, header in enumerate(["#", "Field", "Severity", "Issue", "Rule Reference"]):
            table.rows[0].cells[i].text = header
        for i, v in enumerate(violations, 1):
            row = table.add_row().cells
            row[0].text = str(i)
            row[1].text = v.get("field", "N/A")
            row[2].text = v.get("severity", "minor").upper()
            row[3].text = v.get("issue_description", "N/A")
            row[4].text = v.get("rule_key", "N/A")
    else:
        doc.add_paragraph("No violations detected.")

    # 8. Evidence appendix (violation id + bbox coordinates)
    doc.add_heading("8. Evidence Appendix", level=1)
    if evidence_crops:
        for ev in evidence_crops:
            bbox = ev.get("bbox", {})
            par = doc.add_paragraph(style="List Bullet")
            par.add_run(f"Violation ID: {ev.get('violation_id', 'N/A')}  ")
            par.add_run(
                f"bbox: ({bbox.get('x1', 0)}, {bbox.get('y1', 0)})–"
                f"({bbox.get('x2', 0)}, {bbox.get('y2', 0)})"
            )
            if ev.get("crop_storage_url"):
                doc.add_paragraph(ev["crop_storage_url"])
    else:
        doc.add_paragraph("No evidence crops generated.")

    # 9. Legal references
    doc.add_heading("9. Legal References", level=1)
    for ref in legal_references:
        doc.add_paragraph(ref, style="List Bullet")

    # 10. Confidence notes
    doc.add_heading("10. Confidence Notes", level=1)
    low_conf = [d for d in declarations if d.get("confidence", 1) < 0.5]
    if low_conf:
        for d in low_conf:
            doc.add_paragraph(
                f"{d.get('field_type', 'unknown')}: confidence {d.get('confidence', 0):.2f}",
                style="List Bullet",
            )
    else:
        doc.add_paragraph("All fields extracted with sufficient confidence.")

    # 11. Inspector review
    doc.add_heading("11. Inspector Review", level=1)
    _add_key_value_table(doc, {
        "Inspector ID": inspection_data.get("inspector_id", "N/A"),
        "Review Status": inspection_data.get("status", "N/A"),
    })

    # 12. Audit info
    doc.add_heading("12. Audit Information", level=1)
    _add_key_value_table(doc, {
        "Report Type": "DOCX export (editable)",
        "Generated At": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "System": "Docket SIH26034 v1.0",
    })

    # Verification seal only for COMPLIANT per design.md §9
    if compliance_result.get("overall_status") == "COMPLIANT":
        seal = doc.add_paragraph()
        run = seal.add_run(
            "✓ This inspection has been verified as compliant with all applicable "
            "Legal Metrology rules."
        )
        run.bold = True
        run.font.color.rgb = _rgb(tokens["color_teal"])

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _get_design_tokens() -> dict[str, str]:
    """Get design tokens for use in PDF template.

    Returns a dict of color/font tokens that match design.md §12.
    These are used in the WeasyPrint CSS to maintain brand consistency.
    """
    return {
        "color_ink_navy": "#1B2A41",
        "color_paper_cream": "#F8F5F0",
        "color_teal": "#2E8B8B",
        "color_redline": "#C0392B",
        "color_amber": "#D4A017",
        "color_border": "#C8C0B6",
        "font_heading": "Source Serif 4",
        "font_body": "IBM Plex Sans",
        "font_mono": "IBM Plex Mono",
    }


# ── HTML template generator (inline, since we can't rely on external files) ───

def _generate_report_html(
    inspection: dict[str, Any],
    compliance: dict[str, Any],
    images: list[str],
    evidence: list[dict[str, Any]],
    legal_references: list[str],
    show_seal: bool,
) -> str:
    """Generate the full HTML report inline (fallback if template file missing).

    This generates the complete 12-section report HTML.
    """
    tokens = _get_design_tokens()

    sections_html = ""

    # Section 1: Cover
    sections_html += f"""
    <div class="section cover">
        <div class="cover-header">
            <h1 class="cover-title">Docket</h1>
            <p class="cover-subtitle">Legal Metrology Compliance Report</p>
        </div>
        <div class="cover-body">
            <p class="cover-label">Inspection Reference</p>
            <p class="cover-value">{inspection.get('id', 'N/A')}</p>
            <p class="cover-label">Date of Inspection</p>
            <p class="cover-value">{inspection.get('created_at', 'N/A')}</p>
            <p class="cover-label">Classification</p>
            <p class="cover-value">{compliance.get('overall_status', 'N/A')}</p>
        </div>
        <div class="cover-footer">
            <p>Generated by Docket SIH26034</p>
            <p>Ministry of Consumer Affairs, Food & Public Distribution</p>
        </div>
    </div>
    """

    # Section 2: Inspection Info
    sections_html += f"""
    <div class="section">
        <h2>2. Inspection Information</h2>
        <table class="info-table">
            <tr><th>Inspection ID</th><td>{inspection.get('id', 'N/A')}</td></tr>
            <tr><th>Inspector</th><td>{inspection.get('inspector_name', 'N/A')}</td></tr>
            <tr><th>Date</th><td>{inspection.get('created_at', 'N/A')}</td></tr>
            <tr><th>Location</th><td>{inspection.get('location', 'N/A')}</td></tr>
            <tr><th>Region</th><td>{inspection.get('region', 'N/A')}</td></tr>
            <tr><th>Source</th><td>{inspection.get('source', 'N/A')}</td></tr>
        </table>
    </div>
    """

    # Section 3: Product Info
    sections_html += f"""
    <div class="section">
        <h2>3. Product Information</h2>
        <table class="info-table">
            <tr><th>Product Name</th><td>{inspection.get('product_name', 'N/A')}</td></tr>
            <tr><th>Category</th><td>{inspection.get('category', 'N/A')}</td></tr>
            <tr><th>Package Type</th><td>{inspection.get('package_type', 'N/A')}</td></tr>
            <tr><th>Classifier Confidence</th><td>{inspection.get('classification_confidence', 'N/A')}</td></tr>
        </table>
    </div>
    """

    # Section 4: Images
    sections_html += '<div class="section"><h2>4. Images</h2>'
    for img_url in images:
        sections_html += f'<div class="image-container"><img src="{img_url}" alt="Inspection image" /></div>'
    sections_html += '</div>'

    # Section 5: Declarations
    declarations = inspection.get("declarations", [])
    sections_html += '<div class="section"><h2>5. Declarations</h2><table class="declarations-table">'
    sections_html += '<tr><th>Field</th><th>Detected Value</th><th>Confidence</th><th>Status</th></tr>'
    for decl in declarations:
        field_type = decl.get("field_type", "unknown")
        value = decl.get("value", {})
        text = value.get("text", "NOT_FOUND") if isinstance(value, dict) else str(value)
        confidence = decl.get("confidence", 0)
        status = "PASS" if confidence >= 0.5 else "LOW_CONF"
        status_class = "status-pass" if status == "PASS" else "status-warn"
        sections_html += f'<tr><td>{field_type}</td><td>{text}</td><td>{confidence:.2f}</td><td class="{status_class}">{status}</td></tr>'
    sections_html += '</table></div>'

    # Section 6: Compliance Summary
    status = compliance.get("overall_status", "UNKNOWN")
    reason = compliance.get("status_reason", "")
    status_color = {
        "COMPLIANT": tokens["color_teal"],
        "NON_COMPLIANT": tokens["color_redline"],
        "PARTIALLY_COMPLIANT": tokens["color_amber"],
        "NEEDS_HUMAN_REVIEW": tokens["color_amber"],
        "INSUFFICIENT_EVIDENCE": tokens["color_redline"],
    }.get(status, tokens["color_ink_navy"])

    sections_html += f"""
    <div class="section">
        <h2>6. Compliance Summary</h2>
        <div class="compliance-status" style="border-left-color: {status_color}">
            <span class="status-badge" style="background-color: {status_color}">{status}</span>
            <p class="status-reason">{reason}</p>
        </div>
    </div>
    """

    # Section 7: Violations
    violations = compliance.get("violations", [])
    if violations:
        sections_html += '<div class="section"><h2>7. Violations</h2><table class="violations-table">'
        sections_html += '<tr><th>#</th><th>Field</th><th>Severity</th><th>Issue</th><th>Rule Reference</th></tr>'
        for i, v in enumerate(violations, 1):
            sev = v.get("severity", "minor").upper()
            sev_color = {
                "CRITICAL": tokens["color_redline"],
                "MAJOR": tokens["color_amber"],
                "MINOR": tokens["color_border"],
            }.get(sev, tokens["color_border"])
            sections_html += f'<tr><td>{i}</td><td>{v.get("field", "N/A")}</td><td style="color:{sev_color};font-weight:bold">{sev}</td><td>{v.get("issue_description", "N/A")}</td><td>{v.get("rule_key", "N/A")}</td></tr>'
        sections_html += '</table></div>'
    else:
        sections_html += '<div class="section"><h2>7. Violations</h2><p class="no-violations">No violations detected.</p></div>'

    # Section 8: Evidence Appendix
    if evidence:
        sections_html += '<div class="section"><h2>8. Evidence Appendix</h2>'
        for ev in evidence:
            crop_url = ev.get("crop_storage_url", "")
            bbox = ev.get("bbox", {})
            sections_html += f'<div class="evidence-item"><div class="evidence-image"><img src="{crop_url}" alt="Evidence crop" /><span class="bbox-overlay">bbox: ({bbox.get("x1",0)},{bbox.get("y1",0)})-({bbox.get("x2",0)},{bbox.get("y2",0)})</span></div><p class="evidence-id">Violation ID: {ev.get("violation_id", "N/A")}</p></div>'
        sections_html += '</div>'
    else:
        sections_html += '<div class="section"><h2>8. Evidence Appendix</h2><p>No evidence crops generated.</p></div>'

    # Section 9: Legal References
    if legal_references:
        sections_html += '<div class="section"><h2>9. Legal References</h2><ul>'
        for ref in legal_references:
            sections_html += f'<li>{ref}</li>'
        sections_html += '</ul></div>'
    else:
        sections_html += '<div class="section"><h2>9. Legal References</h2><p>No legal references applicable.</p></div>'

    # Section 10: Confidence Notes
    low_conf_fields = [f for f in declarations if f.get("confidence", 1) < 0.5]
    if low_conf_fields:
        sections_html += '<div class="section"><h2>10. Confidence Notes</h2><p>The following fields have low confidence and may require human review:</p><ul>'
        for f in low_conf_fields:
            sections_html += f'<li>{f.get("field_type", "unknown")}: confidence {f.get("confidence", 0):.2f}</li>'
        sections_html += '</ul></div>'
    else:
        sections_html += '<div class="section"><h2>10. Confidence Notes</h2><p>All fields extracted with sufficient confidence.</p></div>'

    # Section 11: Inspector Review
    sections_html += f"""
    <div class="section">
        <h2>11. Inspector Review</h2>
        <table class="info-table">
            <tr><th>Inspector ID</th><td>{inspection.get('inspector_id', 'N/A')}</td></tr>
            <tr><th>Review Status</th><td>{inspection.get('status', 'N/A')}</td></tr>
            <tr><th>Review Date</th><td>{inspection.get('created_at', 'N/A')}</td></tr>
        </table>
    </div>
    """

    # Section 12: Audit Info
    sections_html += f"""
    <div class="section">
        <h2>12. Audit Information</h2>
        <table class="info-table">
            <tr><th>Report ID</th><td>{uuid.uuid4()}</td></tr>
            <tr><th>Generated At</th><td>{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</td></tr>
            <tr><th>System</th><td>Docket SIH26034 v1.0</td></tr>
            <tr><th>Generation Time</th><td>~N/A (report generated via generate_report())</td></tr>
        </table>
    </div>
    """

    # Verification seal (only for COMPLIANT)
    seal_html = ""
    if show_seal:
        seal_html = f"""
        <div class="verification-seal">
            <div class="seal-circle">✓</div>
            <p class="seal-text">This inspection has been verified as compliant with all applicable Legal Metrology rules.</p>
            <p class="seal-date">Verified: {datetime.utcnow().strftime("%Y-%m-%d")}</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Compliance Report — {inspection.get('id', 'N/A')}</title>
    <style>
        @page {{ size: A4; margin: 2cm; }}
        @page :first {{ margin: 0; }}

        body {{
            font-family: "{tokens['font_body']}", sans-serif;
            color: {tokens['color_ink_navy']};
            line-height: 1.6;
            margin: 0;
            padding: 0;
        }}

        .section {{
            margin-bottom: 2em;
            page-break-inside: avoid;
        }}

        h2 {{
            font-family: "{tokens['font_heading']}", serif;
            font-size: 1.3em;
            color: {tokens['color_ink_navy']};
            border-bottom: 1px solid {tokens['color_border']};
            padding-bottom: 0.3em;
            margin-top: 0;
        }}

        h1 {{
            font-family: "{tokens['font_heading']}", serif;
            font-size: 2em;
            color: {tokens['color_ink_navy']};
        }}

        .cover {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background: {tokens['color_paper_cream']};
            text-align: center;
            page-break-after: always;
        }}

        .cover-title {{
            font-size: 3em;
            margin-bottom: 0.2em;
        }}

        .cover-subtitle {{
            font-size: 1.2em;
            color: {tokens['color_border']};
            margin-bottom: 2em;
        }}

        .cover-label {{
            font-size: 0.8em;
            color: {tokens['color_border']};
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }}

        .cover-value {{
            font-size: 1.2em;
            margin: 0.3em 0;
        }}

        .cover-footer {{
            position: absolute;
            bottom: 2cm;
            font-size: 0.8em;
            color: {tokens['color_border']};
        }}

        .info-table, .declarations-table, .violations-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 0.5em;
        }}

        .info-table th, .info-table td,
        .declarations-table th, .declarations-table td,
        .violations-table th, .violations-table td {{
            padding: 0.4em 0.6em;
            text-align: left;
            border-bottom: 1px solid {tokens['color_border']};
        }}

        .info-table th, .declarations-table th, .violations-table th {{
            font-weight: bold;
            width: 30%;
            color: {tokens['color_ink_navy']};
        }}

        .status-pass {{ color: {tokens['color_teal']}; }}
        .status-warn {{ color: {tokens['color_amber']}; }}

        .compliance-status {{
            border-left: 4px solid;
            padding-left: 1em;
            margin: 1em 0;
        }}

        .status-badge {{
            display: inline-block;
            padding: 0.3em 0.8em;
            color: white;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 0.9em;
        }}

        .status-reason {{
            margin-top: 0.5em;
            color: {tokens['color_ink_navy']};
        }}

        .no-violations {{
            color: {tokens['color_teal']};
            font-style: italic;
        }}

        .severity-critical {{ color: {tokens['color_redline']}; font-weight: bold; }}
        .severity-major {{ color: {tokens['color_amber']}; font-weight: bold; }}
        .severity-minor {{ color: {tokens['color_border']}; }}

        .image-container {{
            margin: 1em 0;
            text-align: center;
        }}

        .image-container img {{
            max-width: 100%;
            max-height: 400px;
            border: 1px solid {tokens['color_border']};
        }}

        .evidence-item {{
            margin: 1em 0;
            padding: 0.5em;
            border: 1px solid {tokens['color_border']};
        }}

        .evidence-image {{
            text-align: center;
        }}

        .evidence-image img {{
            max-width: 200px;
            max-height: 150px;
        }}

        .bbox-overlay {{
            font-family: "{tokens['font_mono']}", monospace;
            font-size: 0.7em;
            color: {tokens['color_border']};
            display: block;
            margin-top: 0.3em;
        }}

        .evidence-id {{
            font-family: "{tokens['font_mono']}", monospace;
            font-size: 0.8em;
            text-align: center;
            color: {tokens['color_ink_navy']};
        }}

        .verification-seal {{
            margin-top: 3em;
            padding: 2em;
            border: 2px solid {tokens['color_teal']};
            text-align: center;
            page-break-inside: avoid;
        }}

        .seal-circle {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: {tokens['color_teal']};
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5em;
            font-weight: bold;
            margin: 0 auto 1em;
        }}

        .seal-text {{
            font-family: "{tokens['font_heading']}", serif;
            font-size: 1.1em;
            color: {tokens['color_ink_navy']};
            margin-bottom: 0.5em;
        }}

        .seal-date {{
            font-size: 0.8em;
            color: {tokens['color_border']};
        }}
    </style>
</head>
<body>
{sections_html}
{seal_html}
</body>
</html>"""


# ── Report scheduling ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

SCHEDULED_REPORTS: list[dict[str, Any]] = []


def schedule_report(inspection_id: str, scheduled_time: datetime) -> str:
    """Queue a report for asynchronous batch generation.

    Registers the inspection in the scheduler with status 'scheduled'.
    A worker calls process_scheduled_reports() periodically, then runs
    generate_report_from_pipeline() for each due entry.
    """
    schedule_id = str(uuid.uuid4())
    SCHEDULED_REPORTS.append({
        "schedule_id": schedule_id,
        "inspection_id": inspection_id,
        "scheduled_time": scheduled_time.isoformat(),
        "status": "scheduled",
    })
    return schedule_id


def get_scheduled_reports() -> list[dict[str, Any]]:
    """Return a snapshot of the scheduled-reports queue."""
    return list(SCHEDULED_REPORTS)


def process_scheduled_reports(now: Optional[datetime] = None) -> list[dict[str, Any]]:
    """Mark due scheduled reports as ready for batch generation.

    Transitions entries from 'scheduled' to 'done' once their
    scheduled_time has passed, recording processed_at. The actual PDF/DOCX
    generation is performed by the calling worker via
    generate_report_from_pipeline() for each processed entry.
    """
    now = now or datetime.utcnow()
    processed: list[dict[str, Any]] = []
    for entry in SCHEDULED_REPORTS:
        if entry["status"] != "scheduled":
            continue
        scheduled_at = datetime.fromisoformat(entry["scheduled_time"])
        if scheduled_at <= now:
            entry["status"] = "done"
            entry["processed_at"] = now.isoformat()
            processed.append(entry)
    return processed


# ── Convenience: generate from pipeline result ─────────────────────────────────

def generate_report_from_pipeline(
    pipeline_result: Any,
    inspection_extra: dict[str, Any],
) -> ReportResult:
    """Generate a report from a PipelineResult object.

    Convenience function that maps pipeline output to report inputs.

    Args:
        pipeline_result: PipelineResult from run_analysis_pipeline().
        inspection_extra: Additional inspection metadata (inspector_name, etc.).

    Returns:
        ReportResult with PDF and JSON storage URLs.
    """
    inspection_data = {
        "id": pipeline_result.inspection_id,
        "created_at": pipeline_result.pipeline_completed_at.isoformat(),
        "inspector_name": inspection_extra.get("inspector_name", "N/A"),
        "location": inspection_extra.get("location", "N/A"),
        "region": inspection_extra.get("region", "N/A"),
        "source": inspection_extra.get("source", "physical"),
        "product_name": inspection_extra.get("product_name", "N/A"),
        "category": pipeline_result.classification.category,
        "package_type": inspection_extra.get("package_type", "N/A"),
        "classification_confidence": pipeline_result.classification.confidence,
        "declarations": [
            {
                "field_type": d.field_type,
                "value": d.value,
                "confidence": d.confidence,
            }
            for d in pipeline_result.extraction.declarations
        ],
        "status": "pending",
    }

    compliance_data = {
        "overall_status": pipeline_result.compliance.overall_status.value,
        "status_reason": pipeline_result.compliance.status_reason,
        "per_field_compliance": [
            {
                "field_type": fc.field_type,
                "status": fc.status,
                "rule_version_id": fc.rule_version_id,
                "confidence": fc.confidence,
                "detail": fc.detail,
            }
            for fc in pipeline_result.compliance.per_field_compliance
        ],
        "violations": [
            {
                "field": v.field,
                "severity": v.severity.value,
                "rule_version_id": v.rule_version_id,
                "rule_key": v.rule_key,
                "issue_description": v.issue_description,
                "detected_value": v.detected_value,
                "expected_condition": v.expected_condition,
            }
            for v in pipeline_result.compliance.violations
        ],
    }

    # Get image URLs from pipeline result
    image_urls = []
    if hasattr(pipeline_result, 'images') and pipeline_result.images:
        for img in pipeline_result.images:
            if hasattr(img, 'storage_url') and img.storage_url:
                image_urls.append(img.storage_url)

    # Get evidence crops from pipeline result
    evidence_crops = []
    if hasattr(pipeline_result, 'evidence') and pipeline_result.evidence:
        for ev in pipeline_result.evidence:
            evidence_crops.append({
                "violation_id": ev.violation_id if hasattr(ev, 'violation_id') else "N/A",
                "crop_storage_url": ev.crop_storage_url if hasattr(ev, 'crop_storage_url') else "",
                "bbox": {
                    "x1": ev.bbox.x1 if hasattr(ev, 'bbox') and hasattr(ev.bbox, 'x1') else 0,
                    "y1": ev.bbox.y1 if hasattr(ev, 'bbox') and hasattr(ev.bbox, 'y1') else 0,
                    "x2": ev.bbox.x2 if hasattr(ev, 'bbox') and hasattr(ev.bbox, 'x2') else 0,
                    "y2": ev.bbox.y2 if hasattr(ev, 'bbox') and hasattr(ev.bbox, 'y2') else 0,
                },
            })

    legal_refs = ["Legal Metrology (Packaged Commodities) Rules, 2011"]

    return generate_report(
        inspection_data=inspection_data,
        compliance_result=compliance_data,
        image_urls=image_urls,
        evidence_crops=evidence_crops,
        legal_references=legal_refs,
    )
