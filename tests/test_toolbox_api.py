import base64
import os

from fastapi.testclient import TestClient

os.environ["MVP_USE_MOCK_PROVIDERS"] = "true"

from app.main import app
from app.schemas import ShotReference

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
            "target_final_count": "9",
            "takes_per_shot": "3",
            "shot_plan_mode": "meaning_first",
            "workflow_mode": "product_set",
        },
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project = create_resp.json()["project"]
    project_id = project["project_id"]
    assert project["status"] == "scripted"
    assert project["task_status"] == "queued"
    assert project["workflow_mode"] == "product_set"
    assert project["set_config"]["target_final_count"] == 9
    assert project["set_config"]["takes_per_shot"] == 3

    progress_resp = client.get(f"/api/v1/projects/{project_id}/progress")
    assert progress_resp.status_code == 200
    progress_payload = progress_resp.json()
    assert progress_payload["next_action"]
    assert progress_payload["required_final_count"] == 9

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
    assert all(item["metadata"].get("delivery_purpose") for item in generated_assets)
    assert all(item["metadata"].get("marketing_copy") for item in generated_assets)

    first_asset_id = generated_assets[0]["asset_id"]
    approve_resp = client.post(
        f"/api/v1/projects/{project_id}/review",
        json={"asset_id": first_asset_id, "action": "approve"},
    )
    assert approve_resp.status_code == 200

    share_resp = client.post(
        f"/api/v1/projects/{project_id}/share",
        json={"asset_id": first_asset_id, "shared": True},
    )
    assert share_resp.status_code == 200
    share_payload = share_resp.json()
    assert share_payload["asset"]["metadata"]["showcase_shared"] is True
    assert share_payload["asset"]["metadata"].get("share_reward_points", 0) >= 0

    tool_tasks_resp = client.get("/api/v1/tools/product_image_suite/tasks?limit=20")
    assert tool_tasks_resp.status_code == 200
    task_items = tool_tasks_resp.json()
    assert any(item["project_id"] == project_id for item in task_items)

    kpi_resp = client.get("/api/v1/tools/kpi")
    assert kpi_resp.status_code == 200
    assert kpi_resp.json()["total_projects"] >= 1
    assert "showcase_assets" in kpi_resp.json()
    assert "share_points_earned" in kpi_resp.json()

    assets_resp = client.get("/api/v1/assets?tool_type=product_image_suite&limit=200")
    assert assets_resp.status_code == 200
    assets = assets_resp.json()
    assert any(item["project_id"] == project_id for item in assets)
    assert any(item["source_type"] == "uploaded" for item in assets if item["project_id"] == project_id)
    shared_assets_resp = client.get("/api/v1/assets?tag=showcase_shared&limit=200")
    assert shared_assets_resp.status_code == 200
    assert any(item["asset_id"] == first_asset_id for item in shared_assets_resp.json())


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
            "background_policy": "keep_original",
            "output_aspect_ratio": "original",
            "retouch_strength": "light",
        },
        files=[
            ("images", ("a.png", PNG_20X20, "image/png")),
            ("images", ("b.png", PNG_20X20, "image/png")),
            ("identity_image", ("identity.png", PNG_20X20, "image/png")),
        ],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] == 2
    assert payload["total_images"] == 2
    assert payload["queued_images"] == 2
    assert payload["batch_group_id"]
    assert payload["controller_project_id"]

    tasks_resp = client.get("/api/v1/tools/model_retouch/tasks?limit=20")
    assert tasks_resp.status_code == 200
    tasks = tasks_resp.json()
    assert any(item["batch_group_id"] == payload["batch_group_id"] for item in tasks)

    batch_id = payload["batch_group_id"]
    controller_project_id = payload["controller_project_id"]
    summary_resp = client.get(f"/api/v1/tools/model_retouch/batches/{batch_id}")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["identity_status"] == "pending"
    assert summary["total_images"] == 2

    identity_generate = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/identity/generate-candidate",
        json={
            "force": False,
            "identity_source": "generate_new",
            "lighting_preset": "rim_fashion",
            "framing_preset": "half_body",
            "angle_preset": "left_45",
            "identity_requirements": "需要时尚大片风格但保持真实人像质感",
        },
    )
    assert identity_generate.status_code == 200
    controller_assets = client.get(f"/api/v1/projects/{controller_project_id}/assets")
    assert controller_assets.status_code == 200
    identity_candidates = [
        item
        for item in controller_assets.json()
        if "identity" in [tag.lower() for tag in item.get("tags", [])]
    ]
    assert identity_candidates
    identity_asset = identity_candidates[-1]

    identity_confirm = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/identity/confirm",
        json={"asset_id": identity_asset["asset_id"]},
    )
    assert identity_confirm.status_code == 200
    assert identity_confirm.json()["identity_status"] == "confirmed"

    generate_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/generate",
        json={
            "async_mode": False,
            "image_resolution": "1K",
            "image_output_format": "png",
        },
    )
    assert generate_resp.status_code == 200
    final_summary = generate_resp.json()
    assert final_summary["batch_group_id"] == batch_id
    assert final_summary["identity_status"] == "confirmed"
    assert len(final_summary["projects"]) == 2

    for project_row in final_summary["projects"]:
        project_id = project_row["project_id"]
        assets_resp = client.get(f"/api/v1/projects/{project_id}/assets")
        assert assets_resp.status_code == 200
        generated_assets = [
            item
            for item in assets_resp.json()
            if item["source_type"] == "generated" and item["kind"] == "generated_image"
        ]
        assert generated_assets
        assert all(item["metadata"]["image_aspect_ratio"] == "auto" for item in generated_assets)
        project_resp = client.get(f"/api/v1/projects/{project_id}")
        assert project_resp.status_code == 200
        assert project_resp.json()["identity_status"] == "confirmed"
        approve_resp = client.post(
            f"/api/v1/projects/{project_id}/review",
            json={"asset_id": generated_assets[0]["asset_id"], "action": "approve"},
        )
        assert approve_resp.status_code == 200

    batch_download_resp = client.get(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/download-images?scope=approved"
    )
    assert batch_download_resp.status_code == 200
    assert batch_download_resp.headers["content-type"] == "application/zip"
    assert "attachment; filename=" in batch_download_resp.headers["content-disposition"]
    assert batch_download_resp.content


def test_model_retouch_batch_identity_upload_and_use_uploaded_mode() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/tools/model_retouch/batch-create",
        data={
            "product_name": "模特替换上传模式",
            "identity_replace": "true",
        },
        files=[
            ("images", ("source.png", PNG_20X20, "image/png")),
            ("identity_image", ("identity.png", PNG_20X20, "image/png")),
        ],
    )
    assert create_resp.status_code == 200
    payload = create_resp.json()
    batch_id = payload["batch_group_id"]
    controller_project_id = payload["controller_project_id"]

    replace_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/identity/upload",
        json={
            "image_public_url": "https://example.com/identity-replaced.png",
            "image_mime": "image/png",
        },
    )
    assert replace_resp.status_code == 200
    assert replace_resp.json()["identity_status"] == "pending"

    assets_resp = client.get(f"/api/v1/projects/{controller_project_id}/assets")
    assert assets_resp.status_code == 200
    uploaded_identity_assets = [
        item
        for item in assets_resp.json()
        if item["source_type"] == "uploaded"
        and "identity" in [tag.lower() for tag in item.get("tags", [])]
        and item.get("image_url") == "https://example.com/identity-replaced.png"
    ]
    assert uploaded_identity_assets
    uploaded_asset_id = uploaded_identity_assets[-1]["asset_id"]

    generated_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/identity/generate-candidate",
        json={"identity_source": "generate_new"},
    )
    assert generated_resp.status_code == 200
    controller_row = next(
        item
        for item in generated_resp.json().get("projects", [])
        if item.get("project_id") == controller_project_id
    )
    assert controller_row.get("identity_asset_id") != uploaded_asset_id

    use_uploaded_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/identity/generate-candidate",
        json={"identity_source": "use_uploaded"},
    )
    assert use_uploaded_resp.status_code == 200
    assert use_uploaded_resp.json()["identity_anchor_asset_id"] == uploaded_asset_id
    assert use_uploaded_resp.json()["identity_status"] == "pending"

    confirm_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/identity/confirm",
        json={"asset_id": uploaded_asset_id},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["identity_status"] == "confirmed"


def test_model_retouch_batch_identity_clear_uploaded() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/tools/model_retouch/batch-create",
        data={
            "product_name": "模特上传移除测试",
            "identity_replace": "true",
        },
        files=[
            ("images", ("source.png", PNG_20X20, "image/png")),
            ("identity_image", ("identity.png", PNG_20X20, "image/png")),
        ],
    )
    assert create_resp.status_code == 200
    payload = create_resp.json()
    batch_id = payload["batch_group_id"]
    controller_project_id = payload["controller_project_id"]

    clear_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/identity/clear-uploaded",
        json={},
    )
    assert clear_resp.status_code == 200
    summary = clear_resp.json()
    assert summary["identity_status"] == "pending"
    assert summary["identity_anchor_asset_id"] is None

    assets_resp = client.get(f"/api/v1/projects/{controller_project_id}/assets")
    assert assets_resp.status_code == 200
    uploaded_identity_assets = [
        item
        for item in assets_resp.json()
        if item["source_type"] == "uploaded" and "identity" in [tag.lower() for tag in item.get("tags", [])]
    ]
    assert not uploaded_identity_assets
    assert any(item.get("metadata", {}).get("removed") for item in assets_resp.json())

    use_uploaded_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/identity/generate-candidate",
        json={"identity_source": "use_uploaded"},
    )
    assert use_uploaded_resp.status_code == 400


def test_model_retouch_batch_generate_allows_ratio_selection() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/tools/model_retouch/batch-create",
        data={
            "product_name": "模特批次比例测试",
            "identity_replace": "true",
        },
        files=[
            ("images", ("source-a.png", PNG_20X20, "image/png")),
            ("images", ("source-b.png", PNG_20X20, "image/png")),
            ("identity_image", ("identity.png", PNG_20X20, "image/png")),
        ],
    )
    assert create_resp.status_code == 200
    payload = create_resp.json()
    batch_id = payload["batch_group_id"]
    controller_project_id = payload["controller_project_id"]

    controller_assets = client.get(f"/api/v1/projects/{controller_project_id}/assets")
    assert controller_assets.status_code == 200
    identity_assets = [
        item
        for item in controller_assets.json()
        if "identity" in [tag.lower() for tag in item.get("tags", [])]
    ]
    assert identity_assets
    confirm_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/identity/confirm",
        json={"asset_id": identity_assets[-1]["asset_id"]},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["identity_status"] == "confirmed"

    generate_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{batch_id}/generate",
        json={
            "async_mode": False,
            "output_aspect_ratio": "4:5",
            "image_resolution": "1K",
            "image_output_format": "png",
        },
    )
    assert generate_resp.status_code == 200

    for project_row in generate_resp.json()["projects"]:
        pid = project_row["project_id"]
        project_resp = client.get(f"/api/v1/projects/{pid}")
        assert project_resp.status_code == 200
        assert project_resp.json()["output_aspect_ratio"] == "4:5"
        assets_resp = client.get(f"/api/v1/projects/{pid}/assets")
        assert assets_resp.status_code == 200
        generated_assets = [
            item
            for item in assets_resp.json()
            if item["source_type"] == "generated" and item["kind"] == "generated_image"
        ]
        assert generated_assets
        assert all(item["metadata"]["image_aspect_ratio"] == "4:5" for item in generated_assets)


def test_generate_images_accepts_original_ratio_without_resolution() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/projects",
        data={
            "tool_type": "product_image_suite",
            "scenario_type": "product_image_suite",
            "product_name": "原图比例不传分辨率",
        },
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["project"]["project_id"]

    generate_resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={
            "stage": "auto",
            "async_mode": False,
            "candidates_per_prompt": 1,
            "image_aspect_ratio": "auto",
            "image_output_format": "png",
        },
    )
    assert generate_resp.status_code == 200
    assets = generate_resp.json()["assets"]
    assert assets
    assert all(item["metadata"]["image_aspect_ratio"] == "auto" for item in assets)


def test_product_image_generate_blocks_when_candidates_below_target() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/projects",
        data={
            "tool_type": "product_image_suite",
            "scenario_type": "product_image_suite",
            "product_name": "候选不足测试",
            "target_final_count": "30",
            "takes_per_shot": "1",
            "workflow_mode": "product_set",
        },
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["project"]["project_id"]

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
    project_resp = client.get(f"/api/v1/projects/{project_id}")
    assert project_resp.status_code == 200
    assert project_resp.json()["task_status"] in {"queued", "running", "reviewing", "succeeded", "done", "completed"}
    progress_resp = client.get(f"/api/v1/projects/{project_id}/progress")
    assert progress_resp.status_code == 200
    assert progress_resp.json()["task_status"] in {"queued", "running", "reviewing", "succeeded", "done", "completed"}


def test_review_rejects_non_generated_delivery_asset() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/projects",
        data={
            "tool_type": "model_retouch",
            "scenario_type": "model_retouch",
            "product_name": "审核门禁测试",
            "identity_replace": "true",
        },
        files={"image": ("demo.png", PNG_20X20, "image/png")},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["project"]["project_id"]

    identity_generate = client.post(
        f"/api/v1/projects/{project_id}/identity/generate-candidate",
        json={"force": False, "identity_source": "generate_new"},
    )
    assert identity_generate.status_code == 200
    identity_asset = identity_generate.json()["asset"]

    review_resp = client.post(
        f"/api/v1/projects/{project_id}/review",
        json={"asset_id": identity_asset["asset_id"], "action": "approve"},
    )
    assert review_resp.status_code == 400
    assert "only generated image/video assets can be reviewed" in review_resp.json()["detail"]


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
    assert len(plan_resp.json()["project_plan"]["shots"]) == 1

    derive_resp = client.post(f"/api/v1/projects/{project_id}/derive-prompts", json={"force": True})
    assert derive_resp.status_code == 200

    generate_resp = client.post(
        f"/api/v1/projects/{project_id}/multi-angle/generate",
        json={
            "stage": "auto",
            "async_mode": False,
            "candidates_per_prompt": 4,
            "image_aspect_ratio": "1:1",
            "image_resolution": "1K",
            "image_output_format": "png",
        },
    )
    assert generate_resp.status_code == 200
    assert len(generate_resp.json()["assets"]) == 1
    assert all(item["metadata"]["image_aspect_ratio"] == "1:1" for item in generate_resp.json()["assets"])

    tool_tasks_resp = client.get("/api/v1/tools/multi_angle_camera/tasks?limit=20")
    assert tool_tasks_resp.status_code == 200
    assert any(item["project_id"] == project_id for item in tool_tasks_resp.json())


def test_model_retouch_reference_order_prefers_identity_after_source_image() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/tools/model_retouch/batch-create",
        data={
            "product_name": "参考顺序测试",
            "identity_replace": "true",
        },
        files=[
            ("images", ("source.png", PNG_20X20, "image/png")),
            ("style_reference_images", ("style.png", PNG_20X20, "image/png")),
            ("identity_image", ("identity.png", PNG_20X20, "image/png")),
        ],
    )
    assert create_resp.status_code == 200
    payload = create_resp.json()
    project_id = payload["controller_project_id"]

    assets_resp = client.get(f"/api/v1/projects/{project_id}/assets")
    assert assets_resp.status_code == 200
    identity_asset = next(
        item for item in assets_resp.json()
        if item["source_type"] == "uploaded" and "identity" in [tag.lower() for tag in item.get("tags", [])]
    )

    identity_confirm = client.post(
        f"/api/v1/tools/model_retouch/batches/{payload['batch_group_id']}/identity/confirm",
        json={"asset_id": identity_asset["asset_id"]},
    )
    assert identity_confirm.status_code == 200

    from app.deps import get_pipeline_service

    service = get_pipeline_service()
    project = service.get_project(project_id)
    assert project is not None
    urls, paths = service._collect_reference_inputs(project)
    combined = [*urls, *[str(item) for item in paths]]
    assert len(combined) >= 2
    stored_identity_asset = service._store.get_asset(project.identity_anchor_asset_id or project.identity_asset_id)
    assert stored_identity_asset is not None
    expected_identity_ref = stored_identity_asset.image_url or stored_identity_asset.local_path
    assert combined[0] == expected_identity_ref


def test_model_retouch_beautify_uploaded_uses_uploaded_identity_as_base() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/tools/model_retouch/batch-create",
        data={
            "product_name": "模特图精修基底测试",
            "identity_replace": "true",
        },
        files=[
            ("images", ("source.png", PNG_20X20, "image/png")),
            ("identity_image", ("identity.png", PNG_20X20, "image/png")),
        ],
    )
    assert create_resp.status_code == 200
    payload = create_resp.json()
    project_id = payload["controller_project_id"]

    from app.deps import get_pipeline_service

    service = get_pipeline_service()
    original_generate = service._reference_image.generate_images_from_prompts
    captured = {}

    async def fake_generate_images_from_prompts(*, image_path, image_public_url, prompts, **kwargs):
        captured["image_path"] = str(image_path)
        captured["image_public_url"] = image_public_url
        return {
            prompts[0].shot_id: ShotReference(
                shot_id=prompts[0].shot_id,
                source="generated",
                image_url="https://example.com/identity-candidate.png",
                local_path=None,
                prompt=prompts[0].prompt,
            )
        }

    service._reference_image.generate_images_from_prompts = fake_generate_images_from_prompts
    try:
        generate_resp = client.post(
            f"/api/v1/tools/model_retouch/batches/{payload['batch_group_id']}/identity/generate-candidate",
            json={"identity_source": "beautify_uploaded", "force": False},
        )
        assert generate_resp.status_code == 200
    finally:
        service._reference_image.generate_images_from_prompts = original_generate

    assets_resp = client.get(f"/api/v1/projects/{project_id}/assets")
    assert assets_resp.status_code == 200
    identity_asset = next(
        item for item in assets_resp.json()
        if item["source_type"] == "uploaded" and "identity" in [tag.lower() for tag in item.get("tags", [])]
    )
    assert captured["image_public_url"] == identity_asset["image_url"]


def test_model_retouch_default_identity_design_uses_full_body() -> None:
    from app.deps import get_pipeline_service

    service = get_pipeline_service()
    design = service._normalize_identity_design({})
    assert design["framing_preset"] == "full_body"


def test_model_retouch_generated_identity_candidate_uses_triptych_layout() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/tools/model_retouch/batch-create",
        data={"product_name": "锚点包测试", "identity_replace": "true"},
        files=[("images", ("source.png", PNG_20X20, "image/png"))],
    )
    assert create_resp.status_code == 200
    payload = create_resp.json()
    project_id = payload["controller_project_id"]

    generate_resp = client.post(
        f"/api/v1/tools/model_retouch/batches/{payload['batch_group_id']}/identity/generate-candidate",
        json={"identity_source": "generate_new", "framing_preset": "full_body", "force": False},
    )
    assert generate_resp.status_code == 200

    assets_resp = client.get(f"/api/v1/projects/{project_id}/assets")
    assert assets_resp.status_code == 200
    generated_identity_assets = [
        item for item in assets_resp.json()
        if item["source_type"] == "generated" and "identity" in [tag.lower() for tag in item.get("tags", [])]
    ]
    assert generated_identity_assets
    layout_values = {str((item.get("metadata") or {}).get("identity_layout") or "") for item in generated_identity_assets}
    assert "triptych_front_side_back" in layout_values


def test_model_retouch_guardrails_forbid_anchor_outfit_transfer() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/tools/model_retouch/batch-create",
        data={"product_name": "服装约束测试", "identity_replace": "true"},
        files=[("images", ("source.png", PNG_20X20, "image/png"))],
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["controller_project_id"]

    from app.deps import get_pipeline_service

    service = get_pipeline_service()
    project = service.get_project(project_id)
    assert project is not None
    guarded = service._apply_model_retouch_prompt_guardrails(project, 'replace model in source image')
    assert 'anchor clothing' in guarded
    assert 'keep garment category' in guarded
    assert 'never borrow top, bottom, or accessories from identity anchor' in guarded


def test_model_retouch_generated_identity_prompt_uses_neutral_basewear() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/tools/model_retouch/batch-create",
        data={"product_name": "锚点服装测试", "identity_replace": "true"},
        files=[("images", ("source.png", PNG_20X20, "image/png"))],
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["controller_project_id"]

    from app.deps import get_pipeline_service

    service = get_pipeline_service()
    project = service.get_project(project_id)
    assert project is not None
    prompt = service._build_identity_prompt(project, service._normalize_identity_design({'identity_source': 'generate_new'}))
    assert '纯色贴身基础款' in prompt
    assert '不提供后续替换服装参考' in prompt
