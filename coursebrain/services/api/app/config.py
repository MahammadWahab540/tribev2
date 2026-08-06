import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "CourseBrain QA"
    DEBUG: bool = True
    VERSION: str = "0.1.0"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/coursebrain"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    STORAGE_PATH: str = "./storage"
    MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024 * 1024  # 2GB

    # Feature flags
    ENABLE_TRIBE: bool = False
    ENABLE_LLM: bool = False
    ENABLE_OCR: bool = False
    MOCK_ANALYSIS: bool = False

    # Analysis limits
    TASK_TIME_LIMIT_SECONDS: int = 3600
    MAX_VIDEO_DURATION_SECONDS: int = 1800
    VIDEO_SAMPLE_INTERVAL: float = 5.0
    TRANSCRIPT_WINDOW_SIZE: int = 30

    # TribeV2
    TRIBE_CACHE_FOLDER: str = "./cache"
    TRIBE_MODEL_NAME: str = "facebook/tribev2"
    TRIBE_DEVICE: str = "auto"  # auto, cuda, cpu

    # LLM
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: Optional[str] = None  # For OpenAI-compatible APIs

    # Analysis thresholds
    MIN_PASSIVE_STRETCH: int = 45  # seconds
    HIGH_SPEECH_RATE_WPM: int = 180
    LOW_SPEECH_RATE_WPM: int = 100

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
