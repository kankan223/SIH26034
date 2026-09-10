"""
Shared pytest fixtures for backend tests.

Session-scoped fixtures are used for expensive one-time setup
(model training, heavy imports) so every test function doesn't
pay the same cost.
"""
from __future__ import annotations

import pytest

from app.services.classification import retrain_model, _get_model, MODEL_PATH
import os


@pytest.fixture(scope="session")
def trained_classifier():
    """Ensure the classification model is trained once per session.

    Returns the loaded Pipeline so artifact checks can inspect it
    without re-training.
    """
    pipeline = retrain_model()
    return pipeline


@pytest.fixture(scope="session")
def loaded_classifier_pipeline():
    """Return the already-loaded in-memory pipeline (or train if absent).

    Uses _get_model() so the fixture respects the module's global cache.
    """
    return _get_model()
