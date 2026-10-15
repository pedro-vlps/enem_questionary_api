"""Application settings and configuration management using environment variables."""

import json
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env")

    APP_ENV: str

    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    OPENAI_API_KEY: str = ""
    QUESTION_GENERATION_ENABLED: bool = False
    OPENAI_TEXT_MODEL: str = "gpt-5.4-mini"
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"
    OPENAI_IMAGE_SIZE: str = "1024x1024"
    OPENAI_IMAGE_QUALITY: str = "low"
    OPENAI_IMAGE_OUTPUT_FORMAT: str = "png"
    QUESTION_ASSETS_ENABLE_IMAGE_GENERATION: bool
    FERNET_KEY: str
    JWT_SECRET_KEY: str
    ALGORITHM: str
    JWT_EXPIRATION_MINUTES: int
    RESTRICT_STRIPE_AUTH_KEY: str
    PUBLIC_STRIPE_AUTH_KEY: str
    SECRET_STRIPE_AUTH_KEY: str
    WEBHOOK_STRIPE_SECRECT_KEY: str
    DEFAULT_PRICE_ID: str
    PAYMENT_CURRENCY: str
    CHECKOUT_REDIRECT_URL: str

    PASSWORD_RESET_TOKEN_EXPIRATION_MINUTES: int
    PASSWORD_RESET_INCLUDE_TOKEN_IN_RESPONSE: bool
    PASSWORD_RESET_URL: str

    SMTP_ENABLED: bool
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USE_TLS: bool
    SMTP_USE_SSL: bool
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str
    SMTP_FROM_NAME: str

    S3_ENABLED: bool = False
    S3_BUCKET: str | None = None
    S3_REGION: str | None = None
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_PUBLIC_BASE_URL: str | None = None
    S3_KEY_PREFIX: str = "question-assets"

    FRONTEND_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "https://enemquestionaryfront-production.up.railway.app"]

    @field_validator("FRONTEND_ORIGINS", mode="before")
    @classmethod
    def parse_frontend_origins(cls, value: Any) -> list[str]:
        """Support either a list or a comma-separated string of allowed origins."""
        if isinstance(value, str):
            if value.strip().startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def database_url(self):
        """Build the database URL from individual components."""
        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()  # type: ignore[call-arg]
