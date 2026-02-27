from pathlib import Path

from app.schemas import ProductBrief, ProjectRecord, ProjectStatus
from app.store import InMemoryStore, utc_now


def test_store_persists_to_json(tmp_path: Path) -> None:
    persist_path = tmp_path / "state" / "store.json"
    store = InMemoryStore(persist_path=persist_path)

    now = utc_now()
    project = ProjectRecord(
        project_id="project-1",
        status=ProjectStatus.draft,
        created_at=now,
        updated_at=now,
        image_path="data/uploads/project-1.png",
        brief=ProductBrief(product_name="测试产品"),
    )
    store.add_project(project)
    store.add_project_log(
        project_id="project-1",
        level="info",
        stage="test",
        message="persist",
    )

    reloaded = InMemoryStore(persist_path=persist_path)
    loaded_project = reloaded.get_project("project-1")

    assert loaded_project is not None
    assert loaded_project.brief.product_name == "测试产品"
    assert persist_path.exists()
    assert len(reloaded.list_project_logs("project-1")) == 1
