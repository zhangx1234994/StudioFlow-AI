import os

from fastapi.testclient import TestClient

os.environ["MVP_USE_MOCK_PROVIDERS"] = "true"
os.environ["MVP_AUTH_ENABLED"] = "false"

from app.main import app


def test_app_tools_page_serves_frontend() -> None:
    client = TestClient(app)
    response = client.get("/app/tools")
    assert response.status_code == 200
    assert "AI摄影棚" in response.text


def test_legacy_entry_routes_redirect_to_app() -> None:
    client = TestClient(app)

    assert client.get("/", follow_redirects=False).headers["location"] == "/app/tools"
    assert client.get("/login", follow_redirects=False).headers["location"] == "/app/login"
    assert client.get("/tools", follow_redirects=False).headers["location"] == "/app/tools"
    assert client.get("/assets", follow_redirects=False).headers["location"] == "/app/assets"
    assert client.get("/tasks", follow_redirects=False).headers["location"] == "/app/tools"


def test_legacy_tool_routes_redirect_to_new_slug_routes() -> None:
    client = TestClient(app)

    intro_task = client.get("/tools/intro_video_multi_script/tasks", follow_redirects=False)
    assert intro_task.status_code == 302
    assert intro_task.headers["location"] == "/app/tools/intro-video/tasks"

    image_project = client.get("/tools/product_image_suite/projects/demo", follow_redirects=False)
    assert image_project.status_code == 302
    assert image_project.headers["location"] == "/app/tools/product-image/projects/demo"

    retouch_project = client.get("/tools/model_retouch/projects/demo", follow_redirects=False)
    assert retouch_project.status_code == 302
    assert retouch_project.headers["location"] == "/app/tools/model-retouch/projects/demo"

    quick_project = client.get("/tools/quick_video_15s/projects/demo", follow_redirects=False)
    assert quick_project.status_code == 302
    assert quick_project.headers["location"] == "/app/tools/quick-video-15s/projects/demo"

    multi_project = client.get("/tools/multi_angle_camera/projects/demo", follow_redirects=False)
    assert multi_project.status_code == 302
    assert multi_project.headers["location"] == "/app/tools/multi-angle-camera/projects/demo"


def test_ui_meta_and_nav_context_endpoints() -> None:
    client = TestClient(app)

    meta_resp = client.get("/api/v1/ui/tool-meta")
    assert meta_resp.status_code == 200
    payload = meta_resp.json()
    assert isinstance(payload, list)
    assert len(payload) == 5
    assert any(item["slug"] == "multi-angle-camera" for item in payload)

    nav_resp = client.get("/api/v1/ui/nav-context")
    assert nav_resp.status_code == 200
    nav_payload = nav_resp.json()
    assert nav_payload["breadcrumbs"] == ["首页", "工具箱"]
