from __future__ import annotations

import base64
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, settings

PNG_20X20 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAKUlEQVR4nGP8z0A+YKJAL8Oo"
    "ZhIBE6kakMGoZhIBE6kakMGoZhIBRZoBIpwBJy3phGMAAAAASUVORK5CYII="
)


def test_showcase_remix_and_metrics_endpoints() -> None:
    prev_auth_enabled = settings.auth_enabled
    prev_auth_provider = settings.auth_provider
    prev_mock_mode = settings.use_mock_providers
    settings.auth_enabled = False
    settings.auth_provider = "local"
    settings.use_mock_providers = True
    try:
        client = TestClient(app)
        create_resp = client.post(
            "/api/v1/projects",
            data={"product_name": f"样片测试-{uuid4().hex[:6]}", "tool_type": "product_image_suite"},
            files={"image": ("source.png", PNG_20X20, "image/png")},
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["project"]["project_id"]

        generate_resp = client.post(
            f"/api/v1/projects/{project_id}/generate-images",
            json={"candidates_per_prompt": 1, "async_mode": False},
        )
        assert generate_resp.status_code == 200
        assets = generate_resp.json()["assets"]
        generated = next((item for item in assets if item.get("kind") == "generated_image"), None)
        assert generated is not None
        asset_id = generated["asset_id"]

        review_resp = client.post(
            f"/api/v1/projects/{project_id}/review",
            json={"asset_id": asset_id, "action": "approve"},
        )
        assert review_resp.status_code == 200

        share_resp = client.post(
            f"/api/v1/projects/{project_id}/share",
            json={"asset_id": asset_id, "shared": True},
        )
        assert share_resp.status_code == 200
        assert share_resp.json()["asset"]["metadata"]["showcase_shared"] is True

        showcase_resp = client.get("/api/v1/showcase/assets?limit=20")
        assert showcase_resp.status_code == 200
        assert any(item["asset_id"] == asset_id for item in showcase_resp.json())

        remix_resp = client.post("/api/v1/showcase/remix", json={"asset_id": asset_id})
        assert remix_resp.status_code == 200
        remix_project = remix_resp.json()["project"]
        assert remix_project["project_id"]
        assert remix_project["camera_inputs"]["source_showcase_asset_id"] == asset_id

        quality_summary = client.get("/api/v1/quality/summary?days=7")
        assert quality_summary.status_code == 200
        assert quality_summary.json()["total_reports"] >= 1

        prompt_metrics = client.get("/api/v1/prompts/metrics?days=7")
        assert prompt_metrics.status_code == 200
        assert isinstance(prompt_metrics.json()["items"], list)
    finally:
        settings.auth_enabled = prev_auth_enabled
        settings.auth_provider = prev_auth_provider
        settings.use_mock_providers = prev_mock_mode
