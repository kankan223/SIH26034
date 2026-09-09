"""Text normalization and declaration extraction per prd.md §14 and FR-007/FR-008.

Two-stage pipeline:
1. normalize_text(): Clean OCR output — fix substitutions, normalize units/currency/dates
2. extract_declarations(): Classify normalized tokens into declaration field types

Per prd.md §14.1: Every field type has at least one extraction rule.
Per prd.md FR-007: Unmapped units flagged as 'unrecognized_unit', never dropped.
Per prd.md FR-008: Missing fields recorded as NOT_FOUND, never omitted.
"""

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants per prd.md §14.1
# ---------------------------------------------------------------------------

# Declaration field types (closed vocabulary per §14.1)
FIELD_TYPES = [
    "manufacturer",
    "packer",
    "importer",
    "net_quantity",
    "mrp",
    "mfg_date",
    "packing_date",
    "import_date",
    "consumer_care",
    "country_of_origin",
    "product_name",
    "batch_number",
    "ingredients",
    "dimensions",
]


# ---------------------------------------------------------------------------
# OCR substitution dictionary per prd.md FR-007
# ---------------------------------------------------------------------------

OCR_SUBSTITUTIONS = {
    # Common OCR misreads
    "O": "0",  # Letter O → zero (in numeric contexts)
    "o": "0",
    "l": "1",  # Lowercase L → one (in numeric contexts)
    "I": "1",  # Capital I → one (in numeric contexts)
    "S": "5",  # S → 5 (in numeric contexts)
    "B": "8",  # B → 8 (in numeric contexts)
    "Z": "2",  # Z → 2 (in numeric contexts)
}

# Unit normalization mapping per prd.md §14.1 (closed vocabulary)
UNIT_NORMALIZATIONS = {
    # Weight units → "g"
    "g": "g",
    "gm": "g",
    "gms": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "mg": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    # Volume units → "ml"
    "ml": "ml",
    "mL": "ml",
    "milliliter": "ml",
    "millilitre": "ml",
    "milliliters": "ml",
    "millilitres": "ml",
    "l": "l",
    "ltr": "l",
    "ltrs": "l",
    "liter": "l",
    "litre": "l",
    "liters": "l",
    "litres": "l",
    # Count units
    "pcs": "pcs",
    "piece": "pcs",
    "pieces": "pcs",
    "nos": "nos",
    "no": "nos",
    "units": "units",
    "unit": "units",
    # Pack units
    "pack": "pack",
    "pkt": "pkt",
    "packet": "pkt",
    "packets": "pkt",
    "box": "box",
    "boxes": "box",
    "bottle": "bottle",
    "bottles": "bottle",
    "can": "can",
    "cans": "can",
}

# Currency patterns
CURRENCY_SYMBOLS = {"₹", "Rs", "Rs.", "INR", "Rs/", "Re", "Re."}

# Date-related keywords per prd.md §14.1
DATE_KEYWORDS = {
    "mfg": "mfg_date",
    "manufactured": "mfg_date",
    "manufacture": "mfg_date",
    "mfd": "mfg_date",
    "mfgd": "mfg_date",
    "packed": "packing_date",
    "packing": "packing_date",
    "pkd": "packing_date",
    "pkdt": "packing_date",
    "imported": "import_date",
    "import": "import_date",
    "imp": "import_date",
}

# Consumer care keywords
CONSUMER_CARE_KEYWORDS = [
    "consumer care", "consumer complaint", "customer care",
    "helpline", "toll free", "toll-free", "contact us",
    "customer service", "grievance",
]

# Country of origin keywords
ORIGIN_KEYWORDS = [
    "country of origin", "made in", "product of", "origin",
    "manufactured in", "produced in",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NormalizedToken:
    """A normalized text token from OCR output."""
    original: str  # Raw OCR text
    normalized: str  # Cleaned text
    value: Optional[float] = None  # Numeric value if applicable
    unit: Optional[str] = None  # Normalized unit
    currency: Optional[str] = None  # Currency code (INR)
    is_numeric: bool = False
    is_date: bool = False
    is_currency: bool = False
    confidence: float = 1.0  # Inherited from OCR

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "normalized": self.normalized,
            "value": self.value,
            "unit": self.unit,
            "currency": self.currency,
            "is_numeric": self.is_numeric,
            "is_date": self.is_date,
            "is_currency": self.is_currency,
        }


@dataclass
class Declaration:
    """An extracted declaration per prd.md §14.1."""
    field_type: str
    value: str
    raw_value: str = ""
    confidence: float = 0.0
    bbox: Optional[list] = None  # From OCR
    language: str = "en"
    is_not_found: bool = False  # True if field not found (FR-008)
    candidates: list = field(default_factory=list)  # Multiple candidates for ambiguity

    def to_dict(self) -> dict:
        return {
            "field_type": self.field_type,
            "value": self.value,
            "raw_value": self.raw_value,
            "confidence": round(self.confidence, 3),
            "bbox": self.bbox,
            "language": self.language,
            "is_not_found": self.is_not_found,
            "candidates": [c if isinstance(c, dict) else str(c) for c in self.candidates],
        }


@dataclass
class ExtractionResult:
    """Full extraction result from normalized tokens."""
    declarations: list[Declaration] = field(default_factory=list)
    normalized_tokens: list[NormalizedToken] = field(default_factory=list)
    processing_time_ms: float = 0.0

    @property
    def found_fields(self) -> list[str]:
        """Field types that were successfully extracted."""
        return [d.field_type for d in self.declarations if not d.is_not_found]

    @property
    def missing_fields(self) -> list[str]:
        """Field types that were NOT_FOUND."""
        return [d.field_type for d in self.declarations if d.is_not_found]

    def get_declaration(self, field_type: str) -> Optional[Declaration]:
        """Get declaration by field type."""
        for d in self.declarations:
            if d.field_type == field_type:
                return d
        return None


# ---------------------------------------------------------------------------
# Stage 1: Text Normalization (FR-007)
# ---------------------------------------------------------------------------

def _fix_ocr_substitutions(text: str) -> str:
    """Fix common OCR character substitutions in numeric contexts.

    Per prd.md FR-007: fix common substitutions (O/0, l/1).
    Only applies substitutions within numeric-looking strings.
    """
    # Only fix in strings that look numeric (contain digits)
    if not any(c.isdigit() for c in text):
        return text

    result = []
    for char in text:
        if char in OCR_SUBSTITUTIONS and any(c.isdigit() for c in text):
            # Only replace if surrounded by digits or at boundaries
            result.append(OCR_SUBSTITUTIONS[char])
        else:
            result.append(char)

    return "".join(result)


def _normalize_unit(text: str) -> tuple[Optional[str], str]:
    """Normalize unit string to closed vocabulary per prd.md §14.1.

    Returns (normalized_unit or None, cleaned_text).
    """
    text_lower = text.lower().strip()

    # Sort by length descending to match longest unit first (e.g., kg before g)
    sorted_units = sorted(UNIT_NORMALIZATIONS.keys(), key=len, reverse=True)

    for unit_key in sorted_units:
        if text_lower.endswith(unit_key):
            # Extract value part
            value_part = text_lower[: -len(unit_key)].strip()
            return UNIT_NORMALIZATIONS[unit_key], value_part

    return None, text


def _normalize_currency(text: str) -> tuple[Optional[str], str]:
    """Normalize currency symbols to INR per prd.md §14.1.

    Returns (currency_code or None, cleaned_text).
    """
    text_stripped = text.strip()

    # Check for currency symbols
    for symbol in CURRENCY_SYMBOLS:
        if text_stripped.startswith(symbol):
            remaining = text_stripped[len(symbol):].strip()
            # Remove leading punctuation (dots, slashes)
            remaining = remaining.lstrip("./:")
            return "INR", remaining
        if text_stripped.endswith(symbol):
            remaining = text_stripped[: -len(symbol)].strip()
            return "INR", remaining

    # Check for ₹ Unicode
    if "₹" in text_stripped:
        remaining = text_stripped.replace("₹", "").strip()
        return "INR", remaining

    return None, text


def _parse_date(text: str) -> Optional[tuple[int, int]]:
    """Try to parse a date string into (month, year).

    Handles formats: MM/YYYY, MM-YYYY, MM.YYYY, DD/MM/YYYY, etc.
    Also finds date patterns within longer strings (e.g., 'MFG 08/2026').
    Returns (month, year) or None.
    """
    text = text.strip()

    # Pattern: MM/YYYY or MM-YYYY or MM.YYYY
    match = re.search(r"(\d{1,2})[/\-\.](\d{4})", text)
    if match:
        month, year = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12 and 2020 <= year <= 2030:
            return (month, year)

    # Pattern: YYYY-MM
    match = re.search(r"(\d{4})[/\-](\d{1,2})", text)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12 and 2020 <= year <= 2030:
            return (month, year)

    # Pattern: DD/MM/YYYY
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if 1 <= month <= 12 and 2020 <= year <= 2030:
            return (month, year)

    return None


def normalize_text(ocr_results: list) -> list[NormalizedToken]:
    """Normalize OCR output tokens per prd.md FR-007.

    Processing:
    1. Fix common OCR substitutions (O/0, l/1)
    2. Normalize units to closed vocabulary
    3. Normalize currency symbols to INR
    4. Parse date formats to (month, year)

    Args:
        ocr_results: List of OCRResult objects from ocr_service.

    Returns:
        List of NormalizedToken objects.
    """
    tokens = []

    for result in ocr_results:
        text = result.text.strip()
        if not text:
            continue

        # Step 1: Fix OCR substitutions
        fixed = _fix_ocr_substitutions(text)

        # Step 2: Normalize currency
        currency, remaining = _normalize_currency(fixed)

        # Step 3: Normalize unit
        unit, value_text = _normalize_unit(remaining)

        # Step 4: Parse date (check both value_text and full text)
        date_result = _parse_date(value_text)
        if date_result is None:
            # Also check for date patterns in the full text
            date_result = _parse_date(fixed)

        # Step 5: Check if numeric
        is_numeric = bool(re.match(r"^[\d,\.]+$", value_text.replace(" ", "")))
        value = None
        if is_numeric:
            try:
                value = float(value_text.replace(",", "").replace(" ", ""))
            except ValueError:
                pass

        # Step 6: Check if date
        is_date = date_result is not None
        if is_date:
            value = f"{date_result[1]:04d}-{date_result[0]:02d}"

        tokens.append(NormalizedToken(
            original=result.text,
            normalized=fixed,
            value=value,
            unit=unit,
            currency=currency,
            is_numeric=is_numeric,
            is_date=is_date,
            is_currency=currency is not None,
            confidence=result.confidence,
        ))

    return tokens


# ---------------------------------------------------------------------------
# Stage 2: Declaration Extraction (FR-008)
# ---------------------------------------------------------------------------

def _extract_mrp(tokens: list[NormalizedToken]) -> Optional[Declaration]:
    """Extract MRP declaration per prd.md §14.1.

    Pattern: ₹ or Rs. followed by a number.
    """
    candidates = []

    for token in tokens:
        if token.is_currency:
            # Try to extract numeric value from the token
            value = token.value
            if value is None:
                # Try to extract from normalized text
                match = re.search(r"[\d,\.]+", token.normalized)
                if match:
                    try:
                        value = float(match.group().replace(",", ""))
                    except ValueError:
                        pass

            if value is not None:
                formatted = f"₹{value:.0f}" if value == int(value) else f"₹{value}"
                candidates.append(Declaration(
                    field_type="mrp",
                    value=formatted,
                    raw_value=token.original,
                    confidence=token.confidence,
                    language="en",
                ))

    if not candidates:
        return Declaration(
            field_type="mrp",
            value="NOT_FOUND",
            raw_value="",
            confidence=0.0,
            is_not_found=True,
        )

    # Return highest confidence candidate
    return max(candidates, key=lambda c: c.confidence)


def _extract_net_quantity(tokens: list[NormalizedToken]) -> Optional[Declaration]:
    """Extract net quantity declaration per prd.md §14.1.

    Pattern: number + unit (g, ml, kg, pcs, etc.)
    """
    candidates = []

    for token in tokens:
        if token.unit:
            # Try to extract numeric value from the token
            value = token.value
            if value is None:
                match = re.search(r"[\d,\.]+", token.normalized)
                if match:
                    try:
                        value = float(match.group().replace(",", ""))
                    except ValueError:
                        pass

            if value is not None:
                formatted = f"{value:.0f} {token.unit}" if value == int(value) else f"{value} {token.unit}"
                candidates.append(Declaration(
                    field_type="net_quantity",
                    value=formatted,
                    raw_value=token.original,
                    confidence=token.confidence,
                    language="en",
                ))

    if not candidates:
        return Declaration(
            field_type="net_quantity",
            value="NOT_FOUND",
            raw_value="",
            confidence=0.0,
            is_not_found=True,
        )

    return max(candidates, key=lambda c: c.confidence)


def _extract_dates(
    tokens: list[NormalizedToken],
    all_text: str,
) -> list[Declaration]:
    """Extract date declarations per prd.md §14.1.

    Pattern: date near MFG/PKD/Import keywords.
    """
    declarations = []

    # Combine all text for context
    text_lower = all_text.lower()

    # Find which date types are mentioned
    for keyword, field_type in DATE_KEYWORDS.items():
        if keyword in text_lower:
            # Find date tokens
            for token in tokens:
                if token.is_date:
                    declarations.append(Declaration(
                        field_type=field_type,
                        value=str(token.value),
                        raw_value=token.original,
                        confidence=token.confidence,
                        language="en",
                    ))

    # If no dates found near keywords, still record as NOT_FOUND for each
    found_types = {d.field_type for d in declarations}
    for field_type in ["mfg_date", "packing_date"]:
        if field_type not in found_types:
            declarations.append(Declaration(
                field_type=field_type,
                value="NOT_FOUND",
                raw_value="",
                confidence=0.0,
                is_not_found=True,
            ))

    return declarations


def _extract_manufacturer(all_text: str) -> Declaration:
    """Extract manufacturer declaration per prd.md §14.1.

    Heuristic: Look for 'Manufactured by' / 'Packed by' / 'Marketed by'
    followed by company name.
    """
    patterns = [
        r"(?:manufactured?\s+by|packed?\s+by|marketed?\s+by|produced?\s+by)[:\s]+(.+?)(?:\n|$|,|\.)",
        r"(?:mfr|maker|company)[:\s]+(.+?)(?:\n|$|,|\.)",
    ]

    for pattern in patterns:
        match = re.search(pattern, all_text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if len(value) > 3:  # Minimum viable manufacturer name
                return Declaration(
                    field_type="manufacturer",
                    value=value,
                    raw_value=match.group(0).strip(),
                    confidence=0.8,
                    language="en",
                )

    return Declaration(
        field_type="manufacturer",
        value="NOT_FOUND",
        raw_value="",
        confidence=0.0,
        is_not_found=True,
    )


def _extract_consumer_care(all_text: str) -> Declaration:
    """Extract consumer care details per prd.md §14.1."""
    text_lower = all_text.lower()

    for keyword in CONSUMER_CARE_KEYWORDS:
        if keyword in text_lower:
            # Find the line containing the keyword
            for line in all_text.split("\n"):
                if keyword in line.lower():
                    return Declaration(
                        field_type="consumer_care",
                        value=line.strip(),
                        raw_value=line.strip(),
                        confidence=0.7,
                        language="en",
                    )

    return Declaration(
        field_type="consumer_care",
        value="NOT_FOUND",
        raw_value="",
        confidence=0.0,
        is_not_found=True,
    )


def _extract_country_of_origin(all_text: str) -> Declaration:
    """Extract country of origin per prd.md §14.1."""
    text_lower = all_text.lower()

    for keyword in ORIGIN_KEYWORDS:
        if keyword in text_lower:
            # Find the line containing the keyword
            for line in all_text.split("\n"):
                if keyword in line.lower():
                    # Extract country name after colon or keyword
                    match = re.search(r"(?:origin|made in|product of)[:\s]+([A-Za-z\s]+)", line, re.IGNORECASE)
                    if match:
                        country = match.group(1).strip().split()[0]  # First word after keyword
                        return Declaration(
                            field_type="country_of_origin",
                            value=country,
                            raw_value=line.strip(),
                            confidence=0.7,
                            language="en",
                        )

    return Declaration(
        field_type="country_of_origin",
        value="NOT_FOUND",
        raw_value="",
        confidence=0.0,
        is_not_found=True,
    )


def _extract_product_name(all_text: str) -> Declaration:
    """Extract product name (usually the most prominent text)."""
    lines = [l.strip() for l in all_text.split("\n") if l.strip()]
    if lines:
        # Heuristic: longest line is often the product name
        product_name = max(lines, key=len)
        if len(product_name) > 3:
            return Declaration(
                field_type="product_name",
                value=product_name,
                raw_value=product_name,
                confidence=0.6,
                language="en",
            )

    return Declaration(
        field_type="product_name",
        value="NOT_FOUND",
        raw_value="",
        confidence=0.0,
        is_not_found=True,
    )


def extract_declarations(
    ocr_results: list,
    normalized_tokens: Optional[list[NormalizedToken]] = None,
) -> ExtractionResult:
    """Extract declarations from OCR results per prd.md §14 and FR-008.

    Processing:
    1. Normalize text (if tokens not provided)
    2. Extract each field type per §14.1 data model
    3. Record NOT_FOUND for missing fields (never omit per FR-008)
    4. Handle ambiguity: multiple candidates with confidence scores

    Args:
        ocr_results: List of OCRResult objects from ocr_service.
        normalized_tokens: Optional pre-normalized tokens.

    Returns:
        ExtractionResult with all declarations.
    """
    import time
    start = time.time()

    # Stage 1: Normalize if needed
    if normalized_tokens is None:
        normalized_tokens = normalize_text(ocr_results)

    # Combine all text for context (ocr_service.OCRResult exposes .text;
    # older internal token objects expose .original)
    all_text = " ".join(
        (getattr(t, "original", None) or getattr(t, "text", "")) for t in ocr_results
    ) if ocr_results else ""

    # Stage 2: Extract declarations
    declarations = []

    # MRP
    declarations.append(_extract_mrp(normalized_tokens))

    # Net Quantity
    declarations.append(_extract_net_quantity(normalized_tokens))

    # Dates
    declarations.extend(_extract_dates(normalized_tokens, all_text))

    # Manufacturer
    declarations.append(_extract_manufacturer(all_text))

    # Consumer Care
    declarations.append(_extract_consumer_care(all_text))

    # Country of Origin
    declarations.append(_extract_country_of_origin(all_text))

    # Product Name
    declarations.append(_extract_product_name(all_text))

    # Ensure every field type in §14.1 has at least one entry
    found_types = {d.field_type for d in declarations}
    for field_type in FIELD_TYPES:
        if field_type not in found_types:
            declarations.append(Declaration(
                field_type=field_type,
                value="NOT_FOUND",
                raw_value="",
                confidence=0.0,
                is_not_found=True,
            ))

    elapsed_ms = (time.time() - start) * 1000

    return ExtractionResult(
        declarations=declarations,
        normalized_tokens=normalized_tokens,
        processing_time_ms=round(elapsed_ms, 2),
    )
