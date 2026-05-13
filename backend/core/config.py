"""
Application configuration via environment variables.
Uses pydantic-settings for type-safe config management.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ArgentNorth"
    APP_ENV: str = "production"
    SECRET_KEY: str
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Database
    DATABASE_PROVIDER: str = "postgresql"
    DATABASE_URL: str
    DATABASE_CONNECT_TIMEOUT_SECONDS: int = 30

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str = "loanlens-documents"
    AWS_S3_ENDPOINT_URL: str = ""
    AWS_KMS_ENDPOINT_URL: str = ""
    AWS_KMS_KEY_ID: str = ""
    AWS_S3_FORCE_PATH_STYLE: bool = False

    # AI — Google Gemini
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "models/gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # Document Processing
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    CHROMA_DB_PATH: str = "./chroma_data"
    OCR_PROVIDER_MODE: str = "hybrid"
    GOOGLE_DOCUMENT_AI_PROJECT_ID: str = ""
    GOOGLE_DOCUMENT_AI_LOCATION: str = ""
    GOOGLE_DOCUMENT_AI_PROCESSOR_ID: str = ""
    OCR_RENDER_DPI: int = 300
    OCR_MIN_TEXT_LENGTH: int = 50
    OCR_MIN_ACCEPTABLE_CONFIDENCE: float = 0.60
    ANALYSIS_LOCAL_FALLBACK_MIN_TEXT_LENGTH: int = 50
    OCR_MAX_CONCURRENCY: int = 4
    OCR_TESSERACT_LANGS: str = "eng+hin"
    ANALYSIS_JOBS_PATH: str = "./analysis_jobs"
    ANALYSIS_JOB_POLL_SECONDS: int = 2
    ANALYSIS_JOB_MAX_ATTEMPTS: int = 1

    # Clerk Auth
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = "https://api.clerk.com/v1/jwks"
    CLERK_JWT_AUDIENCE: str = ""
    CLERK_JWT_ISSUER: str = ""
    CLERK_JWT_LEEWAY_SECONDS: int = 60
    CODEX_E2E_AUTH_BYPASS: bool = False

    # File uploads
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: list[str] = ["application/pdf", "image/png", "image/jpeg"]
    LOCAL_STORAGE_ENCRYPTION_KEY: str = ""

    # Data retention
    RETENTION_CASE_DAYS: int = 180
    RETENTION_DOCUMENT_DAYS: int = 180
    RETENTION_AUDIT_LOG_DAYS: int = 365
    RETENTION_BATCH_SIZE: int = 100

    # Prisma (used by schema.prisma, not directly by Python)
    PRISMA_SCHEMA_PATH: str = "./schema.prisma"
    PRISMA_AUTO_GENERATE_CLIENT: bool = True
    DIRECT_URL: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",  # Ignore unknown env vars
    }

    @property
    def MIN_TEXT_LENGTH_FOR_OCR(self) -> int:
        """Backward-compatible alias for older code paths/tests."""
        return self.OCR_MIN_TEXT_LENGTH


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — reads .env once."""
    return Settings()
