"""Enums used across the database models."""

import enum


class Role(str, enum.Enum):
    """User roles per prd.md §8.5 FR-030."""
    INSPECTOR = "inspector"
    SENIOR_OFFICER = "senior_officer"
    ADMIN = "admin"


class InspectionStatus(str, enum.Enum):
    """Inspection workflow status."""
    DRAFT = "draft"
    ANALYZING = "analyzing"
    REVIEW = "review"
    REVIEWED = "reviewed"
    REPORTED = "reported"


class OverallStatus(str, enum.Enum):
    """Overall compliance verdict per prd.md §17.1."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Verdict(str, enum.Enum):
    """Per-rule verdict per prd.md §17.1."""
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"
    NOT_APPLICABLE = "not_applicable"


class Severity(str, enum.Enum):
    """Violation severity levels."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class Source(str, enum.Enum):
    """Inspection source type."""
    PHYSICAL = "physical"
    ECOMMERCE = "ecommerce"
