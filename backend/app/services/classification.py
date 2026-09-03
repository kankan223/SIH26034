"""Product category classifier per prd.md §13 and FR-009.

TF-IDF + GradientBoosting baseline classifier:
- classify_product(): assigns product to category taxonomy
- Categories per prd.md §13.1 (Food & Beverage, Personal Care, etc.)
- Confidence threshold ≥0.6 per prd.md §10.4
- Below threshold → routes to manual category selection
- Model saved as .joblib artifact per tech-stack.md §7
- Inference <50ms per prd.md §10.2
"""

import os
import logging
import time
from dataclasses import dataclass
from typing import Optional

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category taxonomy per prd.md §13.1
# ---------------------------------------------------------------------------

CATEGORIES = {
    "food_beverage_packaged_food": "Food & Beverage > Packaged Food",
    "food_beverage_beverages": "Food & Beverage > Beverages",
    "food_beverage_edible_oils": "Food & Beverage > Edible Oils & Fats",
    "personal_care_cosmetics": "Personal Care & Cosmetics > Cosmetics",
    "personal_care_toiletries": "Personal Care & Cosmetics > Toiletries",
    "household_cleaning": "Household > Cleaning Products",
    "household_home_care": "Household > Home Care",
    "health_pharma_otc": "Health & Pharma > OTC/Medical Device",
    "industrial_bulk": "Industrial/Bulk",
    "other_uncategorized": "Other/Uncategorized",
}

# Flat list for dropdown per §13.1
CATEGORY_LIST = list(CATEGORIES.values())

# Confidence threshold per prd.md §10.4
CONFIDENCE_THRESHOLD = 0.6

# Model paths
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ml", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "product_classifier.joblib")


# ---------------------------------------------------------------------------
# Training data (seeded product names per §13.1 categories)
# ---------------------------------------------------------------------------

TRAINING_DATA = [
    # Food & Beverage > Packaged Food
    ("Britannia Good Day Biscuits", "food_beverage_packaged_food"),
    ("Parle-G Biscuits", "food_beverage_packaged_food"),
    ("Haldiram Aloo Bhujia", "food_beverage_packaged_food"),
    ("Kellogg's Corn Flakes", "food_beverage_packaged_food"),
    ("Maggi Noodles 2-Minute", "food_beverage_packaged_food"),
    ("Lay's Potato Chips Salted", "food_beverage_packaged_food"),
    ("Cadbury Dairy Milk Chocolate", "food_beverage_packaged_food"),
    ("Nestle Munch Chocolate Bar", "food_beverage_packaged_food"),
    ("Balaji Wafers", "food_beverage_packaged_food"),
    ("Bikaji Soan Papdi", "food_beverage_packaged_food"),
    ("Britannia Marie Gold Biscuit", "food_beverage_packaged_food"),
    ("Monaco Biscuit Pack", "food_beverage_packaged_food"),
    ("Kurkure Masala Munch", "food_beverage_packaged_food"),
    ("Uncle Chipps Spicy Treat", "food_beverage_packaged_food"),
    ("Oreo Biscuits Original", "food_beverage_packaged_food"),

    # Food & Beverage > Beverages
    ("Bisleri Packaged Drinking Water", "food_beverage_beverages"),
    ("Coca-Cola Soft Drink", "food_beverage_beverages"),
    ("Pepsi Carbonated Beverage", "food_beverage_beverages"),
    ("Frooti Mango Drink", "food_beverage_beverages"),
    ("Real Fruit Juice Mixed Fruit", "food_beverage_beverages"),
    ("Tropicana Orange Juice", "food_beverage_beverages"),
    ("Minute Maid Pulpy Orange", "food_beverage_beverages"),
    ("Kinley Packaged Water", "food_beverage_beverages"),
    ("Aquafina Drinking Water", "food_beverage_beverages"),
    ("Thums Up Cola", "food_beverage_beverages"),
    ("Sprite Lemon Drink", "food_beverage_beverages"),
    ("Maaza Mango Drink", "food_beverage_beverages"),
    ("Paper Boat Aamras", "food_beverage_beverages"),
    ("Sting Energy Drink", "food_beverage_beverages"),
    ("Red Bull Energy Drink", "food_beverage_beverages"),

    # Food & Beverage > Edible Oils & Fats
    ("Fortune Sunlite Refined Oil", "food_beverage_edible_oils"),
    ("Saffola Gold Edible Oil", "food_beverage_edible_oils"),
    ("Soyabean Refined Oil", "food_beverage_edible_oils"),
    ("Mustard Oil Kachchi Ghani", "food_beverage_edible_oils"),
    ("Groundnut Oil Filtered", "food_beverage_edible_oils"),
    ("Dalda Vanaspati", "food_beverage_edible_oils"),
    ("Oleic Sunflower Oil", "food_beverage_edible_oils"),
    ("Coconut Oil Parachute", "food_beverage_edible_oils"),
    ("Refined Palm Oil", "food_beverage_edible_oils"),
    ("Rice Bran Oil Health", "food_beverage_edible_oils"),

    # Personal Care & Cosmetics > Cosmetics
    ("Lakme Absolute Foundation", "personal_care_cosmetics"),
    ("Maybelline Lipstick", "personal_care_cosmetics"),
    ("L'Oreal Paris Serum", "personal_care_cosmetics"),
    ("MAC Lip Gloss", "personal_care_cosmetics"),
    ("Revlon Nail Polish", "personal_care_cosmetics"),
    ("Himalaya Kajal", "personal_care_cosmetics"),
    ("Faces Canada Compact", "personal_care_cosmetics"),
    ("Blue Heaven Mascara", "personal_care_cosmetics"),

    # Personal Care & Cosmetics > Toiletries
    ("Colgate Toothpaste MaxFresh", "personal_care_toiletries"),
    ("Lifebuoy Soap Antibacterial", "personal_care_toiletries"),
    ("Pantene Shampoo Anti-Dandruff", "personal_care_toiletries"),
    ("Dove Beauty Soap", "personal_care_toiletries"),
    ("Head & Shoulders Shampoo", "personal_care_toiletries"),
    ("Close-Up Toothpaste", "personal_care_toiletries"),
    ("Lux Soap Floral", "personal_care_toiletries"),
    ("Nirma Washing Powder", "personal_care_toiletries"),
    ("Surf Excel Detergent", "personal_care_toiletries"),
    ("Vim Dishwash Liquid", "personal_care_toiletries"),
    ("Dettol Handwash", "personal_care_toiletries"),
    ("Sensodyne Toothpaste", "personal_care_toiletries"),
    ("Garnier Shampoo", "personal_care_toiletries"),
    ("Revlon Shampoo", "personal_care_toiletries"),
    ("Clinic Plus Shampoo", "personal_care_toiletries"),

    # Household > Cleaning Products
    ("Harpic Toilet Cleaner", "household_cleaning"),
    ("Lizol Floor Cleaner", "household_cleaning"),
    ("Clorox Bleach", "household_cleaning"),
    ("Domex Toilet Cleaner", "household_cleaning"),
    ("Phenyl Disinfectant", "household_cleaning"),
    ("Bio Bathroom Cleaner", "household_cleaning"),
    ("Colin Glass Cleaner", "household_cleaning"),
    ("Easy Off Oven Cleaner", "household_cleaning"),

    # Household > Home Care
    ("Odonil Air Freshener", "household_home_care"),
    ("Max Air Freshener", "household_home_care"),
    ("Good Knight Mosquito Repellent", "household_home_care"),
    ("All Out Liquid Vaporizer", "household_home_care"),
    ("Raid Insect Killer", "household_home_care"),
    ("Hit Spray Insecticide", "household_home_care"),
    ("Mortein Coil", "household_home_care"),
    ("Baygon Spray", "household_home_care"),

    # Health & Pharma > OTC
    ("Crocin Pain Relief Tablet", "health_pharma_otc"),
    ("Vicks Vaporub", "health_pharma_otc"),
    ("Dolo 650 Tablet", "health_pharma_otc"),
    ("Band-Aid Plaster", "health_pharma_otc"),
    ("Digene Antacid Gel", "health_pharma_otc"),
    ("Gelusil MPS Antacid", "health_pharma_otc"),
    ("Eno Fruit Salt", "health_pharma_otc"),
    ("Strepsils Lozenges", "health_pharma_otc"),
    ("Cough Syrup Alex", "health_pharma_otc"),
    ("Becosules Capsule", "health_pharma_otc"),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """Result of product category classification."""
    category: str  # Full category path (e.g., "Food & Beverage > Packaged Food")
    category_key: str  # Short key (e.g., "food_beverage_packaged_food")
    confidence: float  # [0, 1]
    is_confident: bool  # True if confidence ≥ threshold
    needs_manual_selection: bool  # True if below threshold

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "category_key": self.category_key,
            "confidence": round(self.confidence, 3),
            "is_confident": self.is_confident,
            "needs_manual_selection": self.needs_manual_selection,
        }


# ---------------------------------------------------------------------------
# Model loading and training
# ---------------------------------------------------------------------------

_model_pipeline = None
_vectorizer = None
_classifier = None


def _build_training_data() -> tuple[list[str], list[str]]:
    """Build training data from seeded product names."""
    texts = [text for text, _ in TRAINING_DATA]
    labels = [label for _, label in TRAINING_DATA]
    return texts, labels


def _train_model() -> Pipeline:
    """Train the TF-IDF + GradientBoosting classifier.

    Returns:
        Trained sklearn Pipeline.
    """
    texts, labels = _build_training_data()

    # Build pipeline per prd.md §10.2 and tech-stack.md §7
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb",  # Character n-grams (good for product names)
            ngram_range=(2, 4),  # 2-4 character n-grams
            max_features=5000,
            sublinear_tf=True,
        )),
        ("classifier", GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
        )),
    ])

    # Train on all data (MVP baseline)
    pipeline.fit(texts, labels)

    logger.info(f"Trained classifier on {len(texts)} samples, {len(set(labels))} classes")
    return pipeline


def _save_model(pipeline: Pipeline) -> str:
    """Save trained model to disk.

    Returns:
        Path to saved model.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")
    return MODEL_PATH


def _load_model() -> Optional[Pipeline]:
    """Load trained model from disk.

    Returns:
        Loaded Pipeline or None if not found.
    """
    if os.path.exists(MODEL_PATH):
        try:
            pipeline = joblib.load(MODEL_PATH)
            logger.info(f"Model loaded from {MODEL_PATH}")
            return pipeline
        except Exception as e:
            logger.warning(f"Failed to load model: {e}")
    return None


def _get_model() -> Pipeline:
    """Get or create the model pipeline.

    Tries to load from disk first, then trains a new model.
    """
    global _model_pipeline

    if _model_pipeline is not None:
        return _model_pipeline

    # Try loading from disk
    _model_pipeline = _load_model()
    if _model_pipeline is not None:
        return _model_pipeline

    # Train new model
    _model_pipeline = _train_model()
    _save_model(_model_pipeline)
    return _model_pipeline


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_product(
    product_name: str,
    extracted_text: str = "",
) -> ClassificationResult:
    """Classify a product into a category per prd.md §13 and FR-009.

    Uses TF-IDF + GradientBoosting baseline per prd.md §10.2.

    Args:
        product_name: Product name from OCR extraction.
        extracted_text: Additional extracted text for context.

    Returns:
        ClassificationResult with category, confidence, and flags.
    """
    start = time.time()

    # Combine input text
    combined_text = f"{product_name} {extracted_text}".strip()

    if not combined_text:
        return ClassificationResult(
            category=CATEGORIES["other_uncategorized"],
            category_key="other_uncategorized",
            confidence=0.0,
            is_confident=False,
            needs_manual_selection=True,
        )

    # Get model
    model = _get_model()

    # Predict
    try:
        prediction = model.predict([combined_text])[0]
        probabilities = model.predict_proba([combined_text])[0]
        confidence = float(max(probabilities))
    except Exception as e:
        logger.warning(f"Classification failed: {e}")
        return ClassificationResult(
            category=CATEGORIES["other_uncategorized"],
            category_key="other_uncategorized",
            confidence=0.0,
            is_confident=False,
            needs_manual_selection=True,
        )

    # Apply confidence threshold per prd.md §10.4
    is_confident = confidence >= CONFIDENCE_THRESHOLD
    needs_manual = not is_confident

    elapsed_ms = (time.time() - start) * 1000
    logger.debug(f"Classification: {prediction} ({confidence:.3f}) in {elapsed_ms:.1f}ms")

    return ClassificationResult(
        category=CATEGORIES.get(prediction, CATEGORIES["other_uncategorized"]),
        category_key=prediction,
        confidence=confidence,
        is_confident=is_confident,
        needs_manual_selection=needs_manual,
    )


def get_category_list() -> list[str]:
    """Get the list of all categories for manual selection dropdown.

    Per prd.md §13.1: 15-entry dropdown (simplified to 10 categories).

    Returns:
        List of category display names.
    """
    return CATEGORY_LIST


def retrain_model() -> Pipeline:
    """Retrain the model (for development/testing).

    Returns:
        Newly trained Pipeline.
    """
    global _model_pipeline
    _model_pipeline = _train_model()
    _save_model(_model_pipeline)
    return _model_pipeline
