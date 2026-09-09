"""Computer vision detection service per prd.md §10.2 and FR-004/FR-005.

Fine-tuned YOLOv8n package and label region detection:
- detect_package(): locates package boundary in frame (FR-004)
- detect_label(): locates label/principal-display-panel within package (FR-005)
- Confidence threshold ≥0.5 per prd.md §10.4
- Fallback: full-image OCR when no package detected (manual_crop_used flag)
- CPU inference <300ms per prd.md §10.2

The runtime model is a YOLOv8n fine-tuned on labeled package photos
(training pipeline: ml/training/), exported to ONNX and installed at
ml/models/package_label_detector.onnx with classes {0: package, 1: label}.
When the model file is absent, falls back to contour-based detection
for development/testing purposes.
"""

import ast
import io
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants per prd.md §10.4
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence for valid detection
NMS_IOU_THRESHOLD = 0.45   # Non-max suppression IoU threshold
MIN_PACKAGE_AREA_RATIO = 0.02  # Minimum package area as fraction of image
MIN_LABEL_AREA_RATIO = 0.005   # Minimum label area as fraction of package


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BBox:
    """Bounding box with confidence score."""
    x1: int  # Top-left x
    y1: int  # Top-left y
    x2: int  # Bottom-right x
    y2: int  # Bottom-right y
    confidence: float  # Detection confidence [0, 1]
    class_name: str = ""  # "package" or "label"

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    def to_dict(self) -> dict:
        return {
            "x1": self.x1, "y1": self.y1,
            "x2": self.x2, "y2": self.y2,
            "confidence": round(self.confidence, 3),
            "class_name": self.class_name,
            "width": self.width, "height": self.height,
        }


@dataclass
class DetectionResult:
    """Result of package/label detection."""
    bboxes: list[BBox] = field(default_factory=list)
    manual_crop_used: bool = False
    detection_time_ms: float = 0.0
    image_width: int = 0
    image_height: int = 0
    model_used: str = "none"

    @property
    def detected(self) -> bool:
        """True if at least one valid detection was made."""
        return len(self.bboxes) > 0

    @property
    def primary_bbox(self) -> Optional[BBox]:
        """Return the highest-confidence detection."""
        if not self.bboxes:
            return None
        return max(self.bboxes, key=lambda b: b.confidence)


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_onnx_session = None
_onnx_names: dict[int, str] = {}
_onnx_imgsz: int = 416
_ultra_model = None


def _candidate_model_paths() -> list[Path]:
    """Model lookup order: configured path first, then code-relative default.

    The code-relative path mirrors the product classifier (ml/models/) so the
    model is found both on the host (backend/ml/models/) and in containers
    where backend/ is bind-mounted at /app.
    """
    paths: list[Path] = []
    configured = getattr(settings, "YOLO_MODEL_PATH", None)
    if configured:
        paths.append(Path(configured))
    backend_root = Path(__file__).resolve().parents[2]  # app/services -> app -> backend
    paths.append(backend_root / "ml" / "models" / "package_label_detector.onnx")
    return paths


def _parse_onnx_names(session) -> dict[int, str]:
    """Extract class names from Ultralytics ONNX metadata (falls back to defaults)."""
    try:
        for meta in session.get_modelmeta().custom_metadata_map.items():
            if meta[0] == "names":
                return {int(k): v for k, v in ast.literal_eval(meta[1]).items()}
    except Exception as e:  # pragma: no cover - metadata should always exist
        logger.warning(f"Could not parse ONNX class metadata: {e}")
    return {0: "package", 1: "label"}


def _load_yolo_model():
    """Load the fine-tuned package/label detector.

    Tries, in order:
    1. ONNX detector via onnxruntime (production path; ml/models/...onnx)
    2. Ultralytics checkpoint (development; e.g. fine-tuned best.pt)
    3. Returns None if neither available (contour fallback mode)
    """
    global _onnx_session, _onnx_names, _onnx_imgsz, _ultra_model

    if _onnx_session is not None or _ultra_model is not None:
        return _onnx_session or _ultra_model

    # 1. Fine-tuned ONNX model via onnxruntime
    for model_path in _candidate_model_paths():
        if not model_path.is_file():
            continue
        try:
            import onnxruntime as ort

            _onnx_session = ort.InferenceSession(
                str(model_path), providers=["CPUExecutionProvider"]
            )
            _onnx_names = _parse_onnx_names(_onnx_session)
            # Input shape is (1, 3, H, W); use H as the inference imgsz
            input_shape = _onnx_session.get_inputs()[0].shape
            _onnx_imgsz = int(input_shape[2]) if isinstance(input_shape[2], int) else 416
            logger.info(
                f"Loaded fine-tuned YOLO detector from {model_path} "
                f"(classes={_onnx_names}, imgsz={_onnx_imgsz})"
            )
            return _onnx_session
        except Exception as e:
            logger.warning(f"Failed to load ONNX detector {model_path}: {e}")

    # 2. Ultralytics (development fallback: pretrained or fine-tuned .pt)
    try:
        from ultralytics import YOLO

        _ultra_model = YOLO("yolov8n.pt")
        logger.info("Loaded Ultralytics YOLOv8n (no fine-tuned ONNX found)")
        return _ultra_model
    except Exception as e:
        logger.warning(f"Failed to load Ultralytics YOLO: {e}")

    # No model available — use fallback
    logger.info("No YOLO model available, using contour-based fallback")
    return None


# ---------------------------------------------------------------------------
# Non-Max Suppression
# ---------------------------------------------------------------------------

def _non_max_suppression(bboxes: list[BBox], iou_threshold: float = NMS_IOU_THRESHOLD) -> list[BBox]:
    """Apply Non-Max Suppression to remove overlapping detections.

    Args:
        bboxes: List of detected bounding boxes.
        iou_threshold: IoU threshold for suppression (default 0.45).

    Returns:
        Filtered list of bounding boxes.
    """
    if not bboxes:
        return []

    # Sort by confidence (highest first)
    sorted_bboxes = sorted(bboxes, key=lambda b: b.confidence, reverse=True)
    keep = []

    for bbox in sorted_bboxes:
        # Check IoU against all kept boxes
        is_duplicate = False
        for kept in keep:
            iou = _compute_iou(bbox, kept)
            if iou > iou_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            keep.append(bbox)

    return keep


def _compute_iou(a: BBox, b: BBox) -> float:
    """Compute Intersection over Union between two bounding boxes."""
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = a.area + b.area - intersection

    return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Contour-based fallback detection
# ---------------------------------------------------------------------------

def _detect_by_contours(image: np.ndarray, target: str = "package") -> list[BBox]:
    """Fallback detection using contour analysis when YOLO is unavailable.

    Finds large rectangular contours that could represent packages or labels.
    This is a development/testing fallback — not production-quality.

    Args:
        image: BGR image as numpy array.
        target: "package" or "label".

    Returns:
        List of detected bounding boxes.
    """
    height, width = image.shape[:2]
    image_area = height * width

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # Dilate to connect nearby edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bboxes = []
    min_area = MIN_PACKAGE_AREA_RATIO if target == "package" else MIN_LABEL_AREA_RATIO

    for contour in contours:
        area = cv2.contourArea(contour)
        area_ratio = area / image_area

        if area_ratio < min_area:
            continue

        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)

        # Filter by aspect ratio (packages are roughly rectangular)
        aspect = w / h if h > 0 else 0
        if target == "package" and (aspect < 0.2 or aspect > 5.0):
            continue

        # Confidence based on area ratio and rectangularity
        rect_area = w * h
        rectangularity = area / rect_area if rect_area > 0 else 0
        confidence = min(0.95, rectangularity * 0.8 + area_ratio * 5)

        # Clamp to image bounds
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(width, x + w)
        y2 = min(height, y + h)

        bboxes.append(BBox(
            x1=x1, y1=y1, x2=x2, y2=y2,
            confidence=round(confidence, 3),
            class_name=target,
        ))

    return bboxes


# ---------------------------------------------------------------------------
# YOLO-based detection
# ---------------------------------------------------------------------------

def _letterbox(image: np.ndarray, size: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize with preserved aspect ratio, padding to a square input.

    Returns (letterboxed image, scale factor, (pad_x, pad_y)) so outputs can
    be mapped back to original image coordinates.
    """
    h, w = image.shape[:2]
    scale = min(size / w, size / h)
    new_w, new_h = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return canvas, scale, (pad_x, pad_y)


def _detect_by_onnx(image: np.ndarray, session, target: str = "package") -> list[BBox]:
    """Detect using the fine-tuned ONNX detector via onnxruntime.

    Replicates the Ultralytics detection post-processing: letterbox
    preprocessing, (1, 4+nc, N) output decoding, confidence filtering,
    and class-aware NMS.

    Args:
        image: BGR image as numpy array.
        session: Loaded onnxruntime InferenceSession.
        target: "package" or "label".

    Returns:
        List of detected bounding boxes with confidence ≥ threshold.
    """
    height, width = image.shape[:2]
    size = _onnx_imgsz

    letterboxed, scale, (pad_x, pad_y) = _letterbox(image, size)
    blob = letterboxed[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    blob = np.ascontiguousarray(blob[None])  # (1, 3, size, size)

    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: blob})
    preds = np.asarray(outputs[0])
    if preds.ndim == 3:
        preds = preds[0]
    if preds.shape[0] < preds.shape[1]:  # (4+nc, N) -> (N, 4+nc)
        preds = preds.T

    boxes_xywh = preds[:, :4]
    scores_all = preds[:, 4:]
    class_ids = scores_all.argmax(axis=1)
    confidences = scores_all.max(axis=1)

    names = _onnx_names or {0: "package", 1: "label"}
    wanted = {cid for cid, name in names.items() if name == target}

    # Pre-filter by confidence and target class before NMS
    candidates: list[BBox] = []
    for i in np.where(confidences >= CONFIDENCE_THRESHOLD)[0]:
        if wanted and int(class_ids[i]) not in wanted:
            continue
        cx, cy, bw, bh = boxes_xywh[i]
        # Map letterbox coordinates back to original image coordinates
        x1 = (cx - bw / 2 - pad_x) / scale
        y1 = (cy - bh / 2 - pad_y) / scale
        x2 = (cx + bw / 2 - pad_x) / scale
        y2 = (cy + bh / 2 - pad_y) / scale
        x1 = max(0, min(int(x1), width - 1))
        y1 = max(0, min(int(y1), height - 1))
        x2 = max(x1 + 1, min(int(x2), width))
        y2 = max(y1 + 1, min(int(y2), height))
        candidates.append(BBox(
            x1=x1, y1=y1, x2=x2, y2=y2,
            confidence=round(float(confidences[i]), 3),
            class_name=target,
        ))

    return _non_max_suppression(candidates)


def _detect_by_yolo(image: np.ndarray, model, target: str = "package") -> list[BBox]:
    """Detect using the YOLO model (onnxruntime session or Ultralytics YOLO).

    Args:
        image: BGR image as numpy array.
        model: Loaded model (onnxruntime InferenceSession or Ultralytics YOLO).
        target: "package" or "label".

    Returns:
        List of detected bounding boxes with confidence ≥ threshold.
    """
    if hasattr(model, "run"):  # onnxruntime InferenceSession
        return _detect_by_onnx(image, model, target)

    height, width = image.shape[:2]

    # Run inference at reduced resolution — imgsz=320 keeps CPU latency
    # well under the 300ms target per prd.md §10.2 while retaining
    # package-scale detection accuracy.
    results = model(image, imgsz=320, verbose=False)

    bboxes = []
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue

        names = getattr(result, "names", None) or {}
        for box in boxes:
            conf = float(box.conf[0])
            if conf < CONFIDENCE_THRESHOLD:
                continue

            # Filter to the target class when the model knows our classes
            cls_id = int(box.cls[0]) if box.cls is not None and len(box.cls) else -1
            class_name = names.get(cls_id, "")
            if class_name and class_name != target:
                continue

            # Get bounding box coordinates
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Clamp to image bounds
            x1 = max(0, min(x1, width - 1))
            y1 = max(0, min(y1, height - 1))
            x2 = max(x1 + 1, min(x2, width))
            y2 = max(y1 + 1, min(y2, height))

            bboxes.append(BBox(
                x1=x1, y1=y1, x2=x2, y2=y2,
                confidence=round(conf, 3),
                class_name=target,
            ))

    return bboxes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_package(image_bytes: bytes) -> DetectionResult:
    """Detect package boundary in an image per prd.md §10.2 and FR-004.

    Uses YOLOv8n if available, otherwise falls back to contour-based detection.
    If no package is detected, manual_crop_used is flagged.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, etc.)

    Returns:
        DetectionResult with bounding boxes and metadata.

    Raises:
        ValueError: If image cannot be decoded.
    """
    start = time.time()

    # Validate input
    if not image_bytes:
        raise ValueError("Cannot decode image — empty bytes")

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Cannot decode image — invalid or corrupted file")

    height, width = image.shape[:2]

    # Try the fine-tuned detector first
    model = _load_yolo_model()
    if model is None:
        model_used = "contour_fallback"
    elif _onnx_session is not None:
        model_used = "yolo_v8n_finetuned"
    else:
        model_used = "yolo_v8n"

    if model is not None:
        bboxes = _detect_by_yolo(image, model, target="package")
    else:
        bboxes = _detect_by_contours(image, target="package")

    # Apply NMS
    bboxes = _non_max_suppression(bboxes)

    # Filter by confidence threshold
    bboxes = [b for b in bboxes if b.confidence >= CONFIDENCE_THRESHOLD]

    # If no package detected, flag for manual crop
    manual_crop_used = len(bboxes) == 0

    if manual_crop_used:
        logger.info("No package detected — manual crop required")
        # Per FR-004: full-image fallback so the pipeline can continue —
        # applies regardless of whether a model is loaded (real YOLO may
        # legitimately find nothing on a given frame).
        bboxes = [BBox(
            x1=0, y1=0, x2=width, y2=height,
            confidence=0.3,  # Low confidence for fallback
            class_name="package",
        )]

    elapsed_ms = (time.time() - start) * 1000

    return DetectionResult(
        bboxes=bboxes,
        manual_crop_used=manual_crop_used,
        detection_time_ms=round(elapsed_ms, 2),
        image_width=width,
        image_height=height,
        model_used=model_used,
    )


def detect_label(
    image_bytes: bytes,
    package_bbox: Optional[BBox] = None,
) -> DetectionResult:
    """Detect label/principal-display-panel within package region per FR-005.

    Per prd.md §10.2: MVP fallback treats the full package crop as the
    label region and relies on text-detection density to sub-segment.

    Args:
        image_bytes: Raw image bytes.
        package_bbox: Optional package bounding box to constrain search.
            If None, searches the full image.

    Returns:
        DetectionResult with label bounding boxes.
    """
    start = time.time()

    # Validate input
    if not image_bytes:
        raise ValueError("Cannot decode image — empty bytes")

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Cannot decode image — invalid or corrupted file")

    height, width = image.shape[:2]
    model_used = "contour_fallback"

    if package_bbox is None:
        package_bbox = BBox(x1=0, y1=0, x2=width, y2=height, confidence=1.0)

    # Try the fine-tuned detector. The model is trained on full package
    # photos, so inference runs on the complete frame — a tight package crop
    # starves it of context and suppresses detections. Results are then
    # clipped to the package region when one is provided.
    model = _load_yolo_model()
    if model is not None:
        model_used = "yolo_v8n_finetuned" if _onnx_session is not None else "yolo_v8n"
        bboxes = _detect_by_yolo(image, model, target="label")
        clipped: list[BBox] = []
        for b in bboxes:
            x1 = max(b.x1, package_bbox.x1)
            y1 = max(b.y1, package_bbox.y1)
            x2 = min(b.x2, package_bbox.x2)
            y2 = min(b.y2, package_bbox.y2)
            if x2 > x1 and y2 > y1:
                clipped.append(BBox(
                    x1=x1, y1=y1, x2=x2, y2=y2,
                    confidence=b.confidence,
                    class_name="label",
                ))
        bboxes = clipped
    else:
        # Fallback: use full package region as label (MVP per FR-005)
        bboxes = [BBox(
            x1=package_bbox.x1,
            y1=package_bbox.y1,
            x2=package_bbox.x2,
            y2=package_bbox.y2,
            confidence=0.4,  # Low confidence for fallback
            class_name="label",
        )]

    # Apply NMS
    bboxes = _non_max_suppression(bboxes)

    # Per FR-005: MVP fallback treats the full package crop as the label
    # region when nothing is detected, so the pipeline can continue.
    if not bboxes:
        bboxes = [BBox(
            x1=package_bbox.x1,
            y1=package_bbox.y1,
            x2=package_bbox.x2,
            y2=package_bbox.y2,
            confidence=0.4,  # Low confidence for fallback
            class_name="label",
        )]

    elapsed_ms = (time.time() - start) * 1000

    return DetectionResult(
        bboxes=bboxes,
        manual_crop_used=False,
        detection_time_ms=round(elapsed_ms, 2),
        image_width=width,
        image_height=height,
        model_used=model_used,
    )


def crop_image(image_bytes: bytes, bbox: BBox) -> bytes:
    """Crop an image to the given bounding box.

    Args:
        image_bytes: Raw image bytes.
        bbox: Bounding box to crop to.

    Returns:
        Cropped image as JPEG bytes.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Cannot decode image")

    crop = image[bbox.y1:bbox.y2, bbox.x1:bbox.x2]
    _, buffer = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buffer.tobytes()
