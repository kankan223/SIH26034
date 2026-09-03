"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    POSTGRES_DB: str = "legal_metrology"
    POSTGRES_USER: str = "app_user"
    POSTGRES_PASSWORD: str = "changeme"
    DATABASE_URL: str = "postgresql+asyncpg://app_user:changeme@postgres:5432/legal_metrology"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Object storage (MinIO)
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "changeme"
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_BUCKET_IMAGES: str = "lm-images"
    S3_BUCKET_EVIDENCE: str = "lm-evidence"
    S3_BUCKET_REPORTS: str = "lm-reports"

    # Auth
    JWT_SECRET_KEY: str = "changeme-generate-a-real-32-byte-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # App
    ENVIRONMENT: str = "development"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"

    # ML/CV model paths
    YOLO_MODEL_PATH: str = "/models/package_label_detector.onnx"
    PRODUCT_CLASSIFIER_PATH: str = "/models/product_classifier.joblib"
    PADDLEOCR_LANG: str = "en,hi"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
