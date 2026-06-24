from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Rental Housing Matching System"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    debug: bool = True

    database_url: str = Field(
        default="postgresql+asyncpg://rental:rental@localhost:5432/rental_housing",
        validation_alias="DATABASE_URL",
    )
    alembic_database_url: str = Field(
        default="postgresql+psycopg://rental:rental@localhost:5432/rental_housing",
        validation_alias="ALEMBIC_DATABASE_URL",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    auth_secret_key: str = Field(
        default="dev-only-change-me",
        validation_alias="AUTH_SECRET_KEY",
    )
    auth_algorithm: str = Field(default="HS256", validation_alias="AUTH_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=60,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        validation_alias="REFRESH_TOKEN_EXPIRE_DAYS",
    )

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:5173"],
        validation_alias="CORS_ORIGINS",
    )

    openai_api_key: str = Field(
        default="",
        validation_alias="OPENAI_API_KEY",
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias="OPENAI_EMBEDDING_MODEL",
    )
    openai_chat_model: str = Field(
        default="gpt-4o",
        validation_alias="OPENAI_CHAT_MODEL",
    )

    amap_web_key: str = Field(
        default="",
        validation_alias="AMAP_WEB_KEY",
    )
    amap_geocode_url: str = Field(
        default="https://restapi.amap.com/v3/geocode/geo",
        validation_alias="AMAP_GEOCODE_URL",
    )
    amap_geocode_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="AMAP_GEOCODE_TIMEOUT_SECONDS",
    )
    amap_around_url: str = Field(
        default="https://restapi.amap.com/v5/place/around",
        validation_alias="AMAP_AROUND_URL",
    )
    amap_nearby_radius_meters: int = Field(
        default=2000,
        validation_alias="AMAP_NEARBY_RADIUS_METERS",
    )
    amap_nearby_page_size: int = Field(
        default=5,
        validation_alias="AMAP_NEARBY_PAGE_SIZE",
    )

    upload_dir: str = Field(default="./uploads", validation_alias="UPLOAD_DIR")
    max_upload_size: int = Field(default=5 * 1024 * 1024, validation_alias="MAX_UPLOAD_SIZE")
    allowed_image_types: list[str] = Field(
        default=["image/jpeg", "image/png", "image/webp"],
        validation_alias="ALLOWED_IMAGE_TYPES",
    )
    max_images_per_property: int = Field(default=10, validation_alias="MAX_IMAGES_PER_PROPERTY")

    # WeChat Mini Program
    wechat_appid: str = Field(
        default="",
        validation_alias="WECHAT_APPID",
    )
    wechat_secret: str = Field(
        default="",
        validation_alias="WECHAT_SECRET",
    )
    wechat_token_url: str = Field(
        default="https://api.weixin.qq.com/cgi-bin/token",
        validation_alias="WECHAT_TOKEN_URL",
    )

    # SMS (Alibaba Cloud SMS)
    sms_provider: str = Field(default="aliyun", validation_alias="SMS_PROVIDER")
    sms_access_key_id: str = Field(default="", validation_alias="SMS_ACCESS_KEY_ID")
    sms_access_key_secret: str = Field(default="", validation_alias="SMS_ACCESS_KEY_SECRET")
    sms_sign_name: str = Field(default="", validation_alias="SMS_SIGN_NAME")
    sms_template_code: str = Field(default="", validation_alias="SMS_TEMPLATE_CODE")
    sms_endpoint: str = Field(
        default="dysmsapi.aliyuncs.com",
        validation_alias="SMS_ENDPOINT",
    )

    # Email (SMTP)
    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str = Field(default="", validation_alias="SMTP_USER")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from_name: str = Field(
        default="Rental Housing",
        validation_alias="SMTP_FROM_NAME",
    )
    smtp_from_email: str = Field(default="", validation_alias="SMTP_FROM_EMAIL")
    smtp_use_tls: bool = Field(
        default=True,
        validation_alias="SMTP_USE_TLS",
    )

    # Rate limiting
    rate_limit_requests: int = Field(
        default=100,
        validation_alias="RATE_LIMIT_REQUESTS",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        validation_alias="RATE_LIMIT_WINDOW_SECONDS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
