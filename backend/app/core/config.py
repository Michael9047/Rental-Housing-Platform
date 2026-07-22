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
    openai_base_url: str = Field(
        default="",
        validation_alias="OPENAI_BASE_URL",
    )
    # DeepSeek LLM（用于 AI 搜房：自然语言解析 + 房源摘要生成）
    deepseek_api_key: str = Field(
        default="",
        validation_alias="DEEPSEEK_API_KEY",
    )
    deepseek_chat_model: str = Field(
        default="deepseek-chat",
        validation_alias="DEEPSEEK_CHAT_MODEL",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias="DEEPSEEK_BASE_URL",
    )

    # 智谱 AI（Embedding，OpenAI 兼容接口）—— 优先于 OpenAI 使用
    zhipu_api_key: str = Field(
        default="",
        validation_alias="ZHIPU_API_KEY",
    )
    zhipu_embedding_model: str = Field(
        default="embedding-3",
        validation_alias="ZHIPU_EMBEDDING_MODEL",
    )
    zhipu_base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4",
        validation_alias="ZHIPU_BASE_URL",
    )
    # 与 pgvector 列维度（Property.embedding，1536）对齐，embedding-3 支持自定义输出维度
    embedding_dimensions: int = Field(
        default=1536,
        validation_alias="EMBEDDING_DIMENSIONS",
    )

    # ========== 高德地图（中国大陆主引擎） ==========
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
    amap_js_key: str = Field(
        default="",
        validation_alias="AMAP_JS_KEY",
    )
    # 高德路线规划 API（步行/骑行/驾车/公交，四种通勤模式）
    amap_direction_walking_url: str = Field(
        default="https://restapi.amap.com/v3/direction/walking",
        validation_alias="AMAP_DIRECTION_WALKING_URL",
    )
    amap_direction_bicycling_url: str = Field(
        default="https://restapi.amap.com/v4/direction/bicycling",
        validation_alias="AMAP_DIRECTION_BICYCLING_URL",
    )
    amap_direction_driving_url: str = Field(
        default="https://restapi.amap.com/v3/direction/driving",
        validation_alias="AMAP_DIRECTION_DRIVING_URL",
    )
    amap_direction_transit_url: str = Field(
        default="https://restapi.amap.com/v4/direction/transit/integrated",
        validation_alias="AMAP_DIRECTION_TRANSIT_URL",
    )
    amap_direction_timeout_seconds: float = Field(
        default=8.0,
        validation_alias="AMAP_DIRECTION_TIMEOUT_SECONDS",
    )

    # ========== Google Maps（海外主引擎） ==========
    gm_api_key: str = Field(
        default="",
        validation_alias="GM_API_KEY",
    )
    gm_geocode_url: str = Field(
        default="https://maps.googleapis.com/maps/api/geocode/json",
        validation_alias="GM_GEOCODE_URL",
    )
    gm_nearby_url: str = Field(
        default="https://maps.googleapis.com/maps/api/place/nearbysearch/json",
        validation_alias="GM_NEARBY_URL",
    )
    gm_geocode_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="GM_GEOCODE_TIMEOUT_SECONDS",
    )
    gm_nearby_radius_meters: int = Field(
        default=2000,
        validation_alias="GM_NEARBY_RADIUS_METERS",
    )
    # Google Distance Matrix API（批量通勤时间计算）
    gm_distance_matrix_url: str = Field(
        default="https://maps.googleapis.com/maps/api/distancematrix/json",
        validation_alias="GM_DISTANCE_MATRIX_URL",
    )
    gm_direction_timeout_seconds: float = Field(
        default=8.0,
        validation_alias="GM_DIRECTION_TIMEOUT_SECONDS",
    )
    # Google Directions API（获取路线 polyline + steps，Distance Matrix 不返回这些）
    gm_directions_url: str = Field(
        default="https://maps.googleapis.com/maps/api/directions/json",
        validation_alias="GM_DIRECTIONS_URL",
    )

    # ========== OSM / Nominatim（全球备用引擎） ==========
    nominatim_url: str = Field(
        default="https://nominatim.openstreetmap.org",
        validation_alias="NOMINATIM_URL",
    )
    nominatim_timeout_seconds: float = Field(
        default=15.0,
        validation_alias="NOMINATIM_TIMEOUT_SECONDS",
    )

    # ========== OpenRouteService（OSM 全球路线引擎）==========
    ors_api_key: str = Field(
        default="",
        validation_alias="ORS_API_KEY",
    )
    ors_directions_url: str = Field(
        default="https://api.openrouteservice.org/v2/directions",
        validation_alias="ORS_DIRECTIONS_URL",
    )
    ors_timeout_seconds: float = Field(
        default=8.0,
        validation_alias="ORS_TIMEOUT_SECONDS",
    )

    upload_dir: str = Field(default="./uploads", validation_alias="UPLOAD_DIR")
    private_object_dir: str = Field(default="./private_objects", validation_alias="PRIVATE_OBJECT_DIR")
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

    # SMS 验证码 (Alibaba Cloud 号码认证 dypnsapi)
    sms_provider: str = Field(default="aliyun", validation_alias="SMS_PROVIDER")
    sms_access_key_id: str = Field(default="", validation_alias="SMS_ACCESS_KEY_ID")
    sms_access_key_secret: str = Field(default="", validation_alias="SMS_ACCESS_KEY_SECRET")
    sms_sign_name: str = Field(default="", validation_alias="SMS_SIGN_NAME")
    sms_template_code: str = Field(default="", validation_alias="SMS_TEMPLATE_CODE")
    sms_scheme_name: str = Field(default="", validation_alias="SMS_SCHEME_NAME")
    sms_endpoint: str = Field(
        default="dypnsapi.aliyuncs.com",
        validation_alias="SMS_ENDPOINT",
    )

    # SMS 通知 (Alibaba Cloud 短信服务 dysmsapi)
    sms_notify_access_key_id: str = Field(
        default="", validation_alias="SMS_NOTIFY_ACCESS_KEY_ID",
    )
    sms_notify_access_key_secret: str = Field(
        default="", validation_alias="SMS_NOTIFY_ACCESS_KEY_SECRET",
    )
    sms_notify_sign_name: str = Field(
        default="", validation_alias="SMS_NOTIFY_SIGN_NAME",
    )
    sms_notify_endpoint: str = Field(
        default="dysmsapi.aliyuncs.com",
        validation_alias="SMS_NOTIFY_ENDPOINT",
    )
    # 通知类型 → 模板CODE 的映射，JSON 字符串格式：
    # {"booking_created":"SMS_xxx","payment_received":"SMS_yyy",...}
    sms_notify_template_map: str = Field(
        default="{}", validation_alias="SMS_NOTIFY_TEMPLATE_MAP",
    )

    # Email (SMTP) — deprecated，DirectMail 稳定后移除
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
    email_delivery_mode: str = Field(default="mailpit", validation_alias="EMAIL_DELIVERY_MODE")
    support_email: str = Field(default="support@localhost", validation_alias="SUPPORT_EMAIL")

    # Email (Alibaba Cloud DirectMail) — 主引擎，支持附件
    dm_access_key_id: str = Field(default="", validation_alias="DM_ACCESS_KEY_ID")
    dm_access_key_secret: str = Field(default="", validation_alias="DM_ACCESS_KEY_SECRET")
    dm_account_name: str = Field(
        default="",
        validation_alias="DM_ACCOUNT_NAME",
    )
    dm_from_alias: str = Field(
        default="Rental Housing",
        validation_alias="DM_FROM_ALIAS",
    )
    dm_region_id: str = Field(
        default="cn-hangzhou",
        validation_alias="DM_REGION_ID",
    )
    dm_endpoint: str = Field(
        default="dm.aliyuncs.com",
        validation_alias="DM_ENDPOINT",
    )
    dm_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="DM_TIMEOUT_SECONDS",
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

    # Frontend
    frontend_url: str = Field(
        default="http://localhost:5173",
        validation_alias="FRONTEND_URL",
    )
    payment_provider: str = Field(default="mock_hosted", validation_alias="PAYMENT_PROVIDER")
    payment_mock_webhook_secret: str = Field(default="local-test-only-change-me", validation_alias="PAYMENT_MOCK_WEBHOOK_SECRET")
    payment_mock_merchant_account: str = Field(default="mock_test_account", validation_alias="PAYMENT_MOCK_MERCHANT_ACCOUNT")
    payments_live_enabled: bool = Field(default=False, validation_alias="PAYMENTS_LIVE_ENABLED")
    wechat_pay_merchant_id: str = Field(default="", validation_alias="WECHAT_PAY_MERCHANT_ID")
    wechat_pay_app_id: str = Field(default="", validation_alias="WECHAT_PAY_APP_ID")
    wechat_pay_api_v3_key: str = Field(default="", validation_alias="WECHAT_PAY_API_V3_KEY")
    wechat_pay_cert_serial_no: str = Field(default="", validation_alias="WECHAT_PAY_CERT_SERIAL_NO")
    wechat_pay_private_key_path: str = Field(default="", validation_alias="WECHAT_PAY_PRIVATE_KEY_PATH")
    wechat_pay_notify_url: str = Field(default="", validation_alias="WECHAT_PAY_NOTIFY_URL")
    alipay_app_id: str = Field(default="", validation_alias="ALIPAY_APP_ID")
    alipay_private_key_path: str = Field(default="", validation_alias="ALIPAY_PRIVATE_KEY_PATH")
    alipay_public_key_path: str = Field(default="", validation_alias="ALIPAY_PUBLIC_KEY_PATH")
    alipay_notify_url: str = Field(default="", validation_alias="ALIPAY_NOTIFY_URL")
    alipay_return_url: str = Field(default="", validation_alias="ALIPAY_RETURN_URL")
    card_provider: str = Field(default="", validation_alias="CARD_PROVIDER")
    card_secret_key: str = Field(default="", validation_alias="CARD_SECRET_KEY")
    card_publishable_key: str = Field(default="", validation_alias="CARD_PUBLISHABLE_KEY")
    card_webhook_secret: str = Field(default="", validation_alias="CARD_WEBHOOK_SECRET")
    card_success_url: str = Field(default="", validation_alias="CARD_SUCCESS_URL")
    card_cancel_url: str = Field(default="", validation_alias="CARD_CANCEL_URL")
    contract_expiring_soon_days: int = Field(default=30, validation_alias="CONTRACT_EXPIRING_SOON_DAYS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
