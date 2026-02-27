import base64
import os
import time

from fastapi.testclient import TestClient

os.environ["MVP_USE_MOCK_PROVIDERS"] = "true"

from app.main import app


PNG_20X20 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAKUlEQVR4nGP8z0A+YKJAL8Oo"
    "ZhIBE6kakMGoZhIBE6kakMGoZhIBRZoBIpwBJy3phGMAAAAASUVORK5CYII="
)
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAEAQH/"
    "2fY9WQAAAABJRU5ErkJggg=="
)


def test_reject_too_small_image() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/projects",
        data={"product_name": "便携榨汁杯"},
        files={"image": ("tiny.png", PNG_1X1, "image/png")},
    )

    assert response.status_code == 422
    assert "Minimum supported size" in response.json()["detail"]


def test_project_logs_not_found() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/projects/not-found/logs")
    assert response.status_code == 404


def test_list_projects_for_task_manager() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/projects",
        data={"product_name": "任务列表样例"},
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200

    list_resp = client.get("/api/v1/projects?limit=20")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert isinstance(items, list)
    assert any(item["product_name"] == "任务列表样例" for item in items)

    bad_limit_resp = client.get("/api/v1/projects?limit=0")
    assert bad_limit_resp.status_code == 422


def test_media_endpoint_limits_to_public_assets() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/projects",
        data={"product_name": "媒体目录测试"},
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    image_path = create_resp.json()["project"]["image_path"]
    image_name = image_path.replace("\\", "/").split("/")[-1]

    public_resp = client.get(f"/media/uploads/{image_name}")
    assert public_resp.status_code == 200

    private_resp = client.get("/media/state/store.json")
    assert private_resp.status_code == 404


def test_mvp_flow() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/projects",
        data={
            "product_name": "便携榨汁杯",
            "key_features": "便携,好清洗,出汁快",
            "desired_duration_sec": 36,
        },
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200

    project = create_resp.json()["project"]
    assert len(project["script_options"]) == 3
    format_types = [item.get("format_type") for item in project["script_options"]]
    assert all(format_types)
    assert len(set(format_types)) >= 2

    logs_resp = client.get(f"/api/v1/projects/{project['project_id']}/logs")
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert any(item["stage"] == "create.start" for item in logs)

    select_resp = client.post(
        f"/api/v1/projects/{project['project_id']}/select-script",
        json={"script_id": project["script_options"][0]["script_id"], "edits": []},
    )
    assert select_resp.status_code == 200

    derive_resp = client.post(
        f"/api/v1/projects/{project['project_id']}/derive-prompts",
        json={},
    )
    assert derive_resp.status_code == 200

    render_before_storyboard = client.post(
        f"/api/v1/projects/{project['project_id']}/render",
        json={"variants_per_shot": 1, "preferred_variants": {}},
    )
    assert render_before_storyboard.status_code == 400
    assert "approve all storyboard shots" in render_before_storyboard.json()["detail"]

    storyboard_resp = client.post(
        f"/api/v1/projects/{project['project_id']}/storyboard/generate",
        json={},
    )
    assert storyboard_resp.status_code == 200
    assert storyboard_resp.json()["storyboard_status"] in {"ready", "failed", "confirmed"}

    project_after_storyboard = client.get(f"/api/v1/projects/{project['project_id']}").json()
    for shot in project_after_storyboard["selected_script"]["shots"]:
        approve_resp = client.post(
            f"/api/v1/projects/{project['project_id']}/storyboard/approve-shot",
            json={"shot_id": shot["shot_id"], "status": "approved"},
        )
        assert approve_resp.status_code == 200

    regen_shot_resp = client.post(
        f"/api/v1/projects/{project['project_id']}/storyboard/regenerate-shot",
        json={"shot_id": "shot-1"},
    )
    assert regen_shot_resp.status_code == 200
    assert regen_shot_resp.json()["storyboard_status"] in {"ready", "failed", "confirmed"}

    reapprove_resp = client.post(
        f"/api/v1/projects/{project['project_id']}/storyboard/approve-shot",
        json={"shot_id": "shot-1", "status": "approved"},
    )
    assert reapprove_resp.status_code == 200

    confirm_resp = client.post(
        f"/api/v1/projects/{project['project_id']}/storyboard/confirm",
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["storyboard_status"] == "confirmed"

    render_resp = client.post(
        f"/api/v1/projects/{project['project_id']}/render",
        json={"variants_per_shot": 1, "preferred_variants": {}},
    )
    assert render_resp.status_code == 200

    body = render_resp.json()
    assert body["project"]["status"] in {"scripted", "failed"}
    assert body["render"]["status"] in {"completed", "failed"}
    if body["render"]["status"] == "completed":
        assets_resp = client.get(f"/api/v1/projects/{project['project_id']}/assets")
        assert assets_resp.status_code == 200
        generated_assets = [
            item
            for item in assets_resp.json()
            if item.get("source_type") == "generated"
        ]
        assert generated_assets
        for asset in generated_assets:
            review_resp = client.post(
                f"/api/v1/projects/{project['project_id']}/review",
                json={"asset_id": asset["asset_id"], "action": "approve"},
            )
            assert review_resp.status_code == 200
        final_project = client.get(f"/api/v1/projects/{project['project_id']}")
        assert final_project.status_code == 200
        assert final_project.json()["status"] == "completed"

    logs_resp = client.get(f"/api/v1/projects/{project['project_id']}/logs")
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert any(item["stage"] == "script.select.completed" for item in logs)
    assert any(item["stage"] == "storyboard.shot.approval" for item in logs)


def test_update_master_script_resets_status_after_render() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/projects",
        data={"product_name": "状态重置样例"},
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project = create_resp.json()["project"]
    project_id = project["project_id"]

    select_resp = client.post(
        f"/api/v1/projects/{project_id}/select-script",
        json={"script_id": project["script_options"][0]["script_id"], "edits": []},
    )
    assert select_resp.status_code == 200

    storyboard_resp = client.post(
        f"/api/v1/projects/{project_id}/storyboard/generate",
        json={},
    )
    assert storyboard_resp.status_code == 200

    project_after_storyboard = client.get(f"/api/v1/projects/{project_id}").json()
    for shot in project_after_storyboard["selected_script"]["shots"]:
        approve_resp = client.post(
            f"/api/v1/projects/{project_id}/storyboard/approve-shot",
            json={"shot_id": shot["shot_id"], "status": "approved"},
        )
        assert approve_resp.status_code == 200

    confirm_resp = client.post(f"/api/v1/projects/{project_id}/storyboard/confirm")
    assert confirm_resp.status_code == 200

    render_resp = client.post(
        f"/api/v1/projects/{project_id}/render",
        json={"variants_per_shot": 1, "preferred_variants": {}},
    )
    assert render_resp.status_code == 200

    assets_resp = client.get(f"/api/v1/projects/{project_id}/assets")
    assert assets_resp.status_code == 200
    generated_assets = [item for item in assets_resp.json() if item.get("source_type") == "generated"]
    assert generated_assets
    for asset in generated_assets:
        review_resp = client.post(
            f"/api/v1/projects/{project_id}/review",
            json={"asset_id": asset["asset_id"], "action": "approve"},
        )
        assert review_resp.status_code == 200

    before_update = client.get(f"/api/v1/projects/{project_id}")
    assert before_update.status_code == 200
    assert before_update.json()["status"] == "completed"

    master_script = before_update.json()["master_script"]
    master_script["shots"][0]["narration"] = "重新编辑主脚本后应回退到脚本阶段。"
    master_script["total_duration_sec"] = sum(shot["duration_sec"] for shot in master_script["shots"])
    update_resp = client.patch(
        f"/api/v1/projects/{project_id}/master-script",
        json={"master_script": master_script},
    )
    assert update_resp.status_code == 200
    updated_project = update_resp.json()
    assert updated_project["status"] == "scripted"
    assert updated_project["storyboard_status"] == "not_started"
    assert updated_project["render_id"] is None


def test_mvp_async_flow() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/projects",
        data={"product_name": "旅行电热杯"},
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project = create_resp.json()["project"]
    project_id = project["project_id"]

    select_resp = client.post(
        f"/api/v1/projects/{project_id}/select-script",
        json={"script_id": project["script_options"][0]["script_id"], "edits": []},
    )
    assert select_resp.status_code == 200

    derive_resp = client.post(
        f"/api/v1/projects/{project_id}/derive-prompts",
        json={"force": True},
    )
    assert derive_resp.status_code == 200

    storyboard_start = client.post(
        f"/api/v1/projects/{project_id}/storyboard/generate",
        json={"async_mode": True},
    )
    assert storyboard_start.status_code == 200
    assert storyboard_start.json()["storyboard_status"] in {"generating", "ready", "confirmed"}

    storyboard_status = storyboard_start.json()["storyboard_status"]
    for _ in range(40):
        if storyboard_status in {"ready", "confirmed", "failed"}:
            break
        time.sleep(0.05)
        poll = client.get(f"/api/v1/projects/{project_id}")
        assert poll.status_code == 200
        storyboard_status = poll.json()["storyboard_status"]
    assert storyboard_status in {"ready", "confirmed"}

    project_row = client.get(f"/api/v1/projects/{project_id}")
    assert project_row.status_code == 200
    for shot in project_row.json()["selected_script"]["shots"]:
        approve_resp = client.post(
            f"/api/v1/projects/{project_id}/storyboard/approve-shot",
            json={"shot_id": shot["shot_id"], "status": "approved"},
        )
        assert approve_resp.status_code == 200

    confirm_resp = client.post(f"/api/v1/projects/{project_id}/storyboard/confirm")
    assert confirm_resp.status_code == 200

    render_start = client.post(
        f"/api/v1/projects/{project_id}/render",
        json={"variants_per_shot": 1, "preferred_variants": {}, "async_mode": True},
    )
    assert render_start.status_code == 200
    render_id = render_start.json()["render"]["render_id"]

    render_status = render_start.json()["render"]["status"]
    for _ in range(80):
        if render_status in {"completed", "failed"}:
            break
        time.sleep(0.05)
        poll = client.get(f"/api/v1/renders/{render_id}")
        assert poll.status_code == 200
        render_status = poll.json()["status"]
    assert render_status == "completed"


def test_project_progress_endpoint() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/projects",
        data={"product_name": "进度接口样例"},
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["project"]["project_id"]

    progress_resp = client.get(f"/api/v1/projects/{project_id}/progress")
    assert progress_resp.status_code == 200
    payload = progress_resp.json()
    assert payload["project_id"] == project_id
    assert "steps" in payload
    assert any(step["step_id"] == "master_script" for step in payload["steps"])
    assert "progress_percent_weighted" in payload
    assert "progress_profile" in payload
    assert "step_weights" in payload
    assert "completion_criteria" in payload


def test_retry_endpoint_requires_failed_state() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/projects",
        data={"product_name": "重试接口样例"},
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["project"]["project_id"]

    retry_resp = client.post(f"/api/v1/projects/{project_id}/retry", json={})
    assert retry_resp.status_code == 400
    assert "不处于可重试的失败状态" in retry_resp.json()["detail"]


def test_productized_endpoints_smoke() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/projects",
        data={
            "product_name": "产品化接口样例",
            "scenario_type": "product_video",
            "desired_duration_sec": 15,
        },
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["project"]["project_id"]

    plan_resp = client.post(f"/api/v1/projects/{project_id}/plan", json={"force": True})
    assert plan_resp.status_code == 200
    assert plan_resp.json()["project_plan"] is not None

    derive_resp = client.post(f"/api/v1/projects/{project_id}/derive-prompts", json={"force": True})
    assert derive_resp.status_code == 200
    assert derive_resp.json()["prompt_pack"] is not None

    images_resp = client.post(
        f"/api/v1/projects/{project_id}/generate-images",
        json={"regenerate": False, "async_mode": False, "candidates_per_prompt": 1},
    )
    assert images_resp.status_code == 200
    assets_payload = images_resp.json()["assets"]
    assert assets_payload

    list_assets_resp = client.get(f"/api/v1/projects/{project_id}/assets")
    assert list_assets_resp.status_code == 200
    assert list_assets_resp.json()

    first_asset_id = assets_payload[0]["asset_id"]
    get_asset_resp = client.get(f"/api/v1/assets/{first_asset_id}")
    assert get_asset_resp.status_code == 200
    assert get_asset_resp.json()["asset_id"] == first_asset_id

    review_resp = client.post(
        f"/api/v1/projects/{project_id}/review",
        json={"asset_id": first_asset_id, "action": "approve"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["decision"]["action"] == "approve"

    videos_resp = client.post(
        f"/api/v1/projects/{project_id}/generate-videos",
        json={"variants_per_shot": 1, "async_mode": True},
    )
    assert videos_resp.status_code == 200
    assert videos_resp.json()["render"]["render_id"]


def test_batch_create_endpoint() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/v1/projects/batch",
        json={
            "scenario_type": "product_image_suite",
            "template_name": "general",
            "quality_level": "standard",
            "items": [
                {"product_name": "批量A", "platform": "douyin", "desired_duration_sec": 15},
                {"product_name": "批量B", "platform": "tiktok", "desired_duration_sec": 15},
            ],
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["projects"]) == 2
    assert all(item["batch_group_id"] for item in payload["projects"])
