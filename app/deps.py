from functools import lru_cache

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
        backend = "redis" if settings.redis_url else "local"

    if backend == "redis":
        if not settings.redis_url:
            raise RuntimeError("MVP_STORE_BACKEND=redis requires MVP_REDIS_URL or KV_URL")
        return InMemoryStore(
            redis_url=settings.redis_url,
            redis_state_key=settings.redis_state_key,
        )

    return InMemoryStore(persist_path=settings.storage_root / "state" / "store.json")


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
