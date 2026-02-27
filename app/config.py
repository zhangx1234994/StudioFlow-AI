import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "photo2video-mvp"
    api_prefix: str = "/api/v1"

    volc_api_key: str | None = None
    volc_base_url: str = "https://ark.cn-beijing.volces.com/api/v3/responses"
    volc_model: str = "doubao-seed-2-0-pro-260215"

    kie_api_key: str | None = None
    kie_jobs_base_url: str = "https://api.kie.ai/api/v1/jobs"
    kie_market_base_url: str = "https://api.kie.ai"
    kie_upload_base_url: str = "https://kieai.redpandaai.co"
    kie_callback_url: str | None = None
    kie_video_model: str = "sora-2-image-to-video"
    kie_image_model: str = "nano-banana-pro"
    kie_image_resolution: str = "1K"
    kie_image_output_format: str = "png"
    storyboard_concurrency: int = 2

    ref_image_enabled: bool = False
    ref_image_api_key: str | None = None
    ref_image_base_url: str | None = None
    ref_image_model: str = "seedream"

    storage_root: Path = Path("data")
    store_backend: str = "auto"
    redis_url: str | None = None
    redis_state_key: str = "photo2video:state"
    allow_background_tasks: bool = True
    auth_enabled: bool = True
    admin_username: str = "admin"
    admin_password: str = "admin123"
    auth_secret: str = "photo2video-dev-secret"
    auth_session_hours: int = 24
    use_mock_providers: bool = True
    log_level: str = "INFO"
    log_to_file: bool = True
    local_assembly_enabled: bool = False
    poll_interval_seconds: float = 5.0
    poll_max_attempts: int = 180
    video_task_concurrency: int = 20
    vl_overall_timeout_seconds: float = 45.0

    model_config = SettingsConfigDict(
        env_prefix="MVP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.redis_url:
        settings.redis_url = (
            os.getenv("KV_URL")
            or os.getenv("UPSTASH_REDIS_URL")
            or os.getenv("REDIS_URL")
        )

    if os.getenv("VERCEL"):
        if settings.storage_root == Path("data"):
            settings.storage_root = Path("/tmp/photo2video-data")
        if "MVP_ALLOW_BACKGROUND_TASKS" not in os.environ:
            settings.allow_background_tasks = False

    settings.storage_root.mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "uploads").mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "renders").mkdir(parents=True, exist_ok=True)
    return settings
