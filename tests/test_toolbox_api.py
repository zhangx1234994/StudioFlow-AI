import base64
import os

from fastapi.testclient import TestClient

os.environ["MVP_USE_MOCK_PROVIDERS"] = "true"

from app.main import app

PNG_20X20 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAKUlEQVR4nGP8z0A+YKJAL8Oo"
    "ZhIBE6kakMGoZhIBE6kakMGoZhIBRZoBIpwBJy3phGMAAAAASUVORK5CYII="
)


def test_tool_specific_tasks_and_global_assets() -> None:
    client = TestClient(app)

    templates_resp = client.get("/api/v1/tools/product_image_suite/templates")
    assert templates_resp.status_code == 200
    templates = templates_resp.json()
    assert templates
    assert any(item["template_name"] == "general" for item in templates)
    assert templates[0]["default_form"]

    create_resp = client.post(
        "/api/v1/projects",
        data={
            "tool_type": "product_image_suite",
            "scenario_type": "product_image_suite",
            "product_name": "工具箱-图像任务",
            "scene_style": "简洁棚拍",
            "scene_goals": "主图精修,场景图",
        },
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project = create_resp.json()["project"]
    project_id = project["project_id"]
    assert project["status"] == "scripted"
    assert project["task_status"] == "queued"

    progress_resp = client.get(f"/api/v1/projects/{project_id}/progress")
    assert progress_resp.status_code == 200
    assert progress_resp.json()["next_action"]

    prompt_resp = client.patch(
        f"/api/v1/projects/{project_id}/prompt-inputs",
        json={
            "prompt_inputs": {
                "goal": "提高点击率",
                "style": "真实产品质感",
                "constraints": ["禁止绝对化词汇"],
                "shot_focus": "主图突出材质，场景图突出使用场景",
            }
        },
    )
    assert prompt_resp.status_code == 200

    generate_resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={
            "stage": "auto",
            "async_mode": False,
            "candidates_per_prompt": 2,
            "image_aspect_ratio": "1:1",
            "image_resolution": "1K",
            "image_output_format": "png",
        },
    )
    assert generate_resp.status_code == 200
    assert generate_resp.json()["ok"] is True
    generated_assets = generate_resp.json()["assets"]
    assert len(generated_assets) >= 2
    assert all(item["metadata"]["image_aspect_ratio"] == "1:1" for item in generated_assets)

    tool_tasks_resp = client.get("/api/v1/tools/product_image_suite/tasks?limit=20")
    assert tool_tasks_resp.status_code == 200
    task_items = tool_tasks_resp.json()
    assert any(item["project_id"] == project_id for item in task_items)

    kpi_resp = client.get("/api/v1/tools/kpi")
    assert kpi_resp.status_code == 200
    assert kpi_resp.json()["total_projects"] >= 1

    assets_resp = client.get("/api/v1/assets?tool_type=product_image_suite&limit=200")
    assert assets_resp.status_code == 200
    assets = assets_resp.json()
    assert any(item["project_id"] == project_id for item in assets)
    assert any(item["source_type"] == "uploaded" for item in assets if item["project_id"] == project_id)


def test_intro_generate_requires_script_selection() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/projects",
        data={
            "tool_type": "intro_video_multi_script",
            "product_name": "工具箱-脚本门禁",
        },
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["project"]["project_id"]

    generate_resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"stage": "auto", "variants_per_shot": 1, "async_mode": False},
    )
    assert generate_resp.status_code == 400
    assert "选择并确认一套主拍摄脚本" in generate_resp.json()["detail"]


def test_model_retouch_batch_identity_and_generate() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/tools/model_retouch/batch-create",
        data={
            "product_name": "模特精修批次",
            "identity_replace": "true",
        },
        files=[
            ("images", ("a.png", PNG_20X20, "image/png")),
            ("images", ("b.png", PNG_20X20, "image/png")),
        ],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] == 2
    assert payload["batch_group_id"]

    tasks_resp = client.get("/api/v1/tools/model_retouch/tasks?limit=20")
    assert tasks_resp.status_code == 200
    tasks = tasks_resp.json()
    assert any(item["batch_group_id"] == payload["batch_group_id"] for item in tasks)

    project_id = payload["project_ids"][0]
    progress_resp = client.get(f"/api/v1/projects/{project_id}/progress")
    assert progress_resp.status_code == 200
    steps = progress_resp.json()["steps"]
    assert any(step["step_id"] == "identity" for step in steps)

    identity_generate = client.post(f"/api/v1/projects/{project_id}/identity/generate-candidate", json={"force": False})
    assert identity_generate.status_code == 200
    identity_asset = identity_generate.json().get("asset")
    assert identity_asset

    identity_confirm = client.post(
        f"/api/v1/projects/{project_id}/identity/confirm",
        json={"asset_id": identity_asset["asset_id"]},
    )
    assert identity_confirm.status_code == 200
    assert identity_confirm.json()["project"]["identity_status"] == "confirmed"

    generate_resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={
            "stage": "auto",
            "async_mode": False,
            "candidates_per_prompt": 1,
            "image_aspect_ratio": "1:1",
            "image_resolution": "1K",
            "image_output_format": "png",
        },
    )
    assert generate_resp.status_code == 200
    assert generate_resp.json()["ok"] is True
    assert generate_resp.json()["assets"]


def test_multi_angle_camera_plan_and_generate() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/projects",
        data={
            "tool_type": "multi_angle_camera",
            "scenario_type": "multi_angle_camera",
            "product_name": "多角度耳机",
            "camera_yaw": "10",
            "camera_pitch": "-5",
            "camera_distance": "medium",
            "camera_focal_mm": "50",
            "camera_aspect_ratio": "1:1",
        },
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["project"]["project_id"]

    camera_resp = client.patch(
        f"/api/v1/projects/{project_id}/multi-angle/camera-inputs",
        json={
            "yaw": 0,
            "pitch": 0,
            "distance": "medium",
            "focal_mm": "50",
            "aspect_ratio": "1:1",
            "presets": [
                {"label": "主视角", "yaw": 0, "pitch": 0},
                {"label": "左前45", "yaw": -45, "pitch": 0},
            ],
        },
    )
    assert camera_resp.status_code == 200

    plan_resp = client.post(f"/api/v1/projects/{project_id}/multi-angle/plan", json={"force": True})
    assert plan_resp.status_code == 200
    assert len(plan_resp.json()["project_plan"]["shots"]) >= 2

    derive_resp = client.post(f"/api/v1/projects/{project_id}/derive-prompts", json={"force": True})
    assert derive_resp.status_code == 200

    generate_resp = client.post(
        f"/api/v1/projects/{project_id}/multi-angle/generate",
        json={
            "stage": "auto",
            "async_mode": False,
            "candidates_per_prompt": 1,
            "image_aspect_ratio": "1:1",
            "image_resolution": "1K",
            "image_output_format": "png",
        },
    )
    assert generate_resp.status_code == 200
    assert generate_resp.json()["assets"]
    assert all(item["metadata"]["image_aspect_ratio"] == "1:1" for item in generate_resp.json()["assets"])

    tool_tasks_resp = client.get("/api/v1/tools/multi_angle_camera/tasks?limit=20")
    assert tool_tasks_resp.status_code == 200
    assert any(item["project_id"] == project_id for item in tool_tasks_resp.json())
