from datetime import datetime, timezone

from app.schemas import (
    ProductBrief,
    ProjectRecord,
    ProjectStatus,
    ScenarioType,
    TaskRunStatus,
    ToolType,
)
from app.store import InMemoryStore


def _build_project(project_id: str) -> ProjectRecord:
    now = datetime.now(timezone.utc)
    return ProjectRecord(
        project_id=project_id,
        tool_type=ToolType.multi_angle_camera,
        scenario_type=ScenarioType.multi_angle_camera,
        status=ProjectStatus.draft,
        task_status=TaskRunStatus.queued,
        created_at=now,
        updated_at=now,
        image_path="data/uploads/demo.png",
        source_image_b64="",
        image_public_url=None,
        brief=ProductBrief(
            product_name="test",
            target_audience="test",
            platform="douyin",
            key_features=["a"],
            cta_text="go",
            desired_duration_sec=15,
            tone="neutral",
        ),
    )


def test_get_project_triggers_remote_sync_on_cache_miss(monkeypatch):
    store = InMemoryStore()
    store._redis_client = object()
    project = _build_project("p1")

    def fake_load():
        store._projects = {project.project_id: project}

    monkeypatch.setattr(store, "_load_from_persistence", fake_load)
    assert store.get_project("p1") is not None


def test_update_project_triggers_remote_sync_on_cache_miss(monkeypatch):
    store = InMemoryStore()
    store._redis_client = object()
    project = _build_project("p2")

    def fake_load():
        store._projects = {project.project_id: project}

    monkeypatch.setattr(store, "_load_from_persistence", fake_load)
    updated = store.update_project("p2", lambda p: setattr(p, "status", ProjectStatus.rendering))
    assert updated.status == ProjectStatus.rendering
