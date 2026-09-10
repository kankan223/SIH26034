"""
Shared pytest fixtures for heavy ML/CV/OCR imports.

These fixtures exist to avoid paying the one-time import/init cost of
PaddleOCR (~6s) and cv_detection (~0.6s + model load) on every test
that touches the CV/OCR stack. Session-scoped fixtures pay once; the
tests then reuse the already-imported modules / already-loaded models.

See: prd.md §10 (CV pipeline), prd.md §11 (OCR), tech-stack.md §6.
"""
from __future__ import annotations

import pytest

import time


@pytest.fixture(scope="session")
def trained_classifier():
    """Ensure the classification model is trained once per session.

    Returns the loaded Pipeline so artifact checks can inspect it
    without re-training. This is the same fixture added in the prior
    perf-optimization session (backend test-suite speedup).
    """
    from app.services.classification import retrain_model

    return retrain_model()


@pytest.fixture(scope="session")
def ocr_service_module():
    """Import and initialize app.services.ocr_service once per session.

    PaddleOCR import + model init is expensive (~6s cold); this fixture
    pays it once so every OCR test reuses the same initialized instance.
    Returns the module so tests can call extract_text / extract_text_simple
    and access ocr_service.PaddleOCR if needed.
    """
    import cv2

    from app.services import ocr_service

    # Force model init at fixture setup (one-time). Subsequent calls to
    # extract_text / extract_text_simple will reuse _ocr_instance.
    _ = ocr_service._load_ocr()

    return ocr_service


@pytest.fixture(scope="session")
def ocr_engine(ocr_service_module):
    """Return the already-initialized PaddleOCR engine (or None on init failure).

    Tests that only need the engine — not the wrapper functions — can use
    this directly. Falls back gracefully if OCR init failed in this env.
    """
    return ocr_service_module._load_ocr()


@pytest.fixture(scope="session")
def cv_detection_module():
    """Import app.services.cv_detection once per session and warm the ONNX session.

    cv_detection import is ~0.6s (cv2 + onnxruntime). The first real detect()
    call also loads the ONNX model (~0.14s). This fixture imports the module
    and runs a cheap single detect on a tiny blank image so the model is loaded
    before any per-test detect() call.
    """
    from app.services import cv_detection as cvd

    # Warm the model + ONNX session with a tiny blank image.
    import io
    from PIL import Image

    _warm_blob = np.zeros((240, 320, 3), dtype="uint8")
    _buf = io.BytesIO()
    Image.fromarray(_warm_blob).save(_buf, format="PNG")
    _png = _buf.getvalue()
    try:
        cvd.detect_package(_png)
    except Exception:
        # Model may be absent in some test envs; that's OK — detect() will
        # still function (contour fallback / graceful degradation).
        pass

    return cvd


@pytest.fixture(scope="session")
def cv_detection(cv_detection_module):
    """Convenience alias for cv_detection_module.

    Keeps test code readable: cv_detection is the module, with detect_package,
    detect_label, BBox, DetectionResult, etc. already imported.
    """
    return cv_detection_module


# Hoist numpy at module level so the cv_detection warm fixture can reuse
# the same imported module (avoids a second cv2 import in the fixture body).
import numpy as np  # noqa: E402
