from functools import lru_cache
import os

from app.config import get_settings
from app.services.assembly_service import AssemblyService
from app.services.compliance_service import ComplianceService
from app.services.pipeline_service import PipelineService
from app.services.reference_image_service import ReferenceImageService
from app.services.sora_service import KieSoraService
from app.services.volc_service import VolcScriptService
from app.store import InMemoryStore


@lru_cache
def get_store() -> InMemoryStore:
    settings = get_settings()
    backend = (settings.store_backend or "auto").strip().lower()
    if backend == "auto":
        if settings.redis_url:
            backend = "redis"
        elif os.getenv("VERCEL") and all(
            [
                settings.oss_access_key,
                settings.oss_secret_key,
                settings.oss_bucket,
                settings.oss_endpoint,
            ]
        ):
            backend = "oss"
        else:
            backend = "local"

    if backend == "redis":
        if not settings.redis_url:
            raise RuntimeError("MVP_STORE_BACKEND=redis requires MVP_REDIS_URL or KV_URL")
        return InMemoryStore(
            redis_url=settings.redis_url,
            redis_state_key=settings.redis_state_key,
            async_persist=False,
        )
    if backend == "oss":
        if not all(
            [
                settings.oss_access_key,
                settings.oss_secret_key,
                settings.oss_bucket,
                settings.oss_endpoint,
            ]
        ):
            raise RuntimeError(
                "MVP_STORE_BACKEND=oss requires OSS credentials (MVP_OSS_* or OSS_*)."
            )
        root_prefix = str(settings.oss_root_prefix or "").strip().strip("/")
        state_key = f"{root_prefix}/state/store.json" if root_prefix else "state/store.json"
        return InMemoryStore(
            oss_access_key=settings.oss_access_key,
            oss_secret_key=settings.oss_secret_key,
            oss_bucket=settings.oss_bucket,
            oss_endpoint=settings.oss_endpoint,
            oss_state_key=state_key,
            async_persist=True,
        )

    return InMemoryStore(
        persist_path=settings.storage_root / "state" / "store.json",
        async_persist=settings.store_async_persist,
    )


@lru_cache
def get_pipeline_service() -> PipelineService:
    settings = get_settings()
    return PipelineService(
        store=get_store(),
        script_service=VolcScriptService(settings),
        compliance_service=ComplianceService(),
        sora_service=KieSoraService(settings),
        reference_image_service=ReferenceImageService(settings),
        assembly_service=AssemblyService(settings),
        storage_root=settings.storage_root,
        settings=settings,
    )
