"""Pydantic schemas for rule management API.

Per prd.md §12.2: rule schema structure with applies_when, validation, severity.
Per prd.md §12.6: legal_reference required before publish.
"""

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────

class RuleCreateRequest(BaseModel):
    """Request to create a new rule.

    Attributes:
        rule_key: Unique machine-readable key (e.g., "mrp_format").
        title: Human-readable rule title.
        description: Optional longer description of the rule.
        product_categories: List of categories this rule applies to.
        package_type: Optional specific package type (e.g., "plastic_bottle").
        severity: Default severity level (critical|major|minor).
    """
    rule_key: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    product_categories: list[str] = Field(default_factory=list)
    package_type: Optional[str] = None
    severity: str = "major"  # critical | major | minor


class RuleVersionCreateRequest(BaseModel):
    """Request to create a new version of a rule.

    Per prd.md §12.2: content contains applies_when, validation, severity.
    Per prd.md §12.6: legal_reference is required and must be non-empty.

    Attributes:
        content: The rule content dict (applies_when, validation, severity, etc.).
        legal_reference: Legal citation (e.g., "Legal Metrology Act §18").
            MUST be non-empty before publish.
        effective_date: Date from which this version becomes active.
        end_date: Optional end date (for deprecating versions).
    """
    content: dict[str, Any] = Field(
        default_factory=dict,
        description="Rule content: applies_when, validation, severity per prd.md §12.2"
    )
    legal_reference: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Legal citation required per prd.md §12.6"
    )
    effective_date: date
    end_date: Optional[date] = None


class RuleVersionPublishRequest(BaseModel):
    """Request to publish a rule version.

    Per prd.md §12.6: publishing makes the version effective.
    The version's legal_reference must already be set (validated on version creation).

    Attributes:
        published_by: User ID of the admin publishing the version.
    """
    published_by: str = Field(..., min_length=1)


# ── Response schemas ──────────────────────────────────────────────────────────

class RuleListResponse(BaseModel):
    """List of rules (summary)."""

    class RuleSummary(BaseModel):
        """Summary of a single rule."""
        id: str
        rule_key: str
        title: str
        version: int
        latest_version_id: str
        effective_date: date
        product_categories: list[str]
        severity: str

    rules: list[RuleSummary]


class RuleDetailResponse(BaseModel):
    """Full rule detail with versions."""

    class VersionInfo(BaseModel):
        """A single rule version."""
        id: str
        version: int
        content: dict[str, Any]
        legal_reference: str
        effective_date: date
        end_date: Optional[date] = None
        published_by: Optional[str] = None
        published_at: Optional[date] = None
        is_published: bool

    id: str
    rule_key: str
    title: str
    description: Optional[str] = None
    versions: list[VersionInfo]
    current_version_id: Optional[str] = None
    current_effective_date: Optional[date] = None


class RuleVersionResponse(BaseModel):
    """Response for rule version operations."""

    class VersionCreated(BaseModel):
        id: str
        version: int
        content: dict[str, Any]
        legal_reference: str
        effective_date: date
        message: str

    version: VersionCreated


class RulePublishResponse(BaseModel):
    """Response for rule publish operation."""

    class PublishedVersion(BaseModel):
        id: str
        version: int
        effective_date: date
        published_at: date
        published_by: str

    version: PublishedVersion
    message: str


# ── Query params ──────────────────────────────────────────────────────────────

class RuleListQueryParams(BaseModel):
    """Query parameters for listing rules."""

    category: Optional[str] = None
    effective_after: Optional[date] = None
    effective_before: Optional[date] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
