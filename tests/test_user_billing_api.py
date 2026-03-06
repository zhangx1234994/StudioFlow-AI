from uuid import uuid4
import base64

from fastapi.testclient import TestClient

from app.main import app, settings
from app.deps import get_pipeline_service
from app.schemas import ShotReference

PNG_20X20 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAKUlEQVR4nGP8z0A+YKJAL8Oo"
    "ZhIBE6kakMGoZhIBE6kakMGoZhIBRZoBIpwBJy3phGMAAAAASUVORK5CYII="
)


def test_user_management_and_billing_endpoints() -> None:
    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    prev_recharge_enabled = settings.billing_recharge_enabled
    settings.auth_enabled = False
    settings.auth_provider = "local"
    settings.billing_recharge_enabled = False
    try:
        client = TestClient(app)
        username = f"member_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/v1/users",
            json={
                "username": username,
                "password": "member123",
                "email": f"{username}@studioflow.local",
                "display_name": "测试成员",
                "role": "member",
                "is_active": True,
                "initial_points": 20,
            },
        )
        assert create_resp.status_code == 200
        assert create_resp.json()["username"] == username

        list_resp = client.get("/api/v1/users")
        assert list_resp.status_code == 200
        assert any(item["username"] == username for item in list_resp.json()["items"])

        patch_resp = client.patch(
            f"/api/v1/users/{username}",
            json={"display_name": "测试成员-更新", "role": "operator"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["display_name"] == "测试成员-更新"
        assert patch_resp.json()["role"] == "operator"

        summary_resp = client.get("/api/v1/billing/me")
        assert summary_resp.status_code == 200
        assert "balance" in summary_resp.json()

        recharge_resp = client.post(
            "/api/v1/billing/recharge",
            json={"points": 50, "amount_cny": 5.0, "channel": "manual"},
        )
        assert recharge_resp.status_code == 503

        confirm_resp = client.post(
            "/api/v1/billing/recharge/confirm",
            json={"order_id": "mock-order-id"},
        )
        assert confirm_resp.status_code == 503

        adjust_resp = client.post(
            "/api/v1/billing/adjust",
            json={"username": username, "delta": 15, "note": "测试补贴"},
        )
        assert adjust_resp.status_code == 200
        assert adjust_resp.json()["delta"] == 15
    finally:
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider
        settings.billing_recharge_enabled = prev_recharge_enabled


def test_local_login_uses_user_store_credentials() -> None:
    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    settings.auth_enabled = False
    settings.auth_provider = "local"
    try:
        client = TestClient(app)
        username = f"login_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/v1/users",
            json={
                "username": username,
                "password": "login123",
                "email": f"{username}@studioflow.local",
                "display_name": "登录测试",
                "role": "member",
                "is_active": True,
                "initial_points": 0,
            },
        )
        assert create_resp.status_code == 200
    finally:
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider

    settings.auth_enabled = True
    settings.auth_provider = "local"
    try:
        client = TestClient(app)
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": "login123"},
        )
        assert login_resp.status_code == 200
        me_resp = client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["authenticated"] is True
        assert me_resp.json()["username"] == username
    finally:
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider


def test_member_project_permission_isolation() -> None:
    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    settings.auth_enabled = False
    settings.auth_provider = "local"
    user_a = f"membera_{uuid4().hex[:8]}"
    user_b = f"memberb_{uuid4().hex[:8]}"
    try:
        admin_client = TestClient(app)
        for username in (user_a, user_b):
            resp = admin_client.post(
                "/api/v1/users",
                json={
                    "username": username,
                    "password": "member123",
                    "email": f"{username}@studioflow.local",
                    "display_name": username,
                    "role": "member",
                    "is_active": True,
                    "initial_points": 100,
                },
            )
            assert resp.status_code == 200
    finally:
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider

    settings.auth_enabled = True
    settings.auth_provider = "local"
    try:
        client_a = TestClient(app)
        login_a = client_a.post("/api/v1/auth/login", data={"username": user_a, "password": "member123"})
        assert login_a.status_code == 200
        create_a = client_a.post(
            "/api/v1/projects",
            data={"product_name": "权限隔离A", "tool_type": "product_image_suite"},
            files={"image": ("a.png", PNG_20X20, "image/png")},
        )
        assert create_a.status_code == 200
        project_id = create_a.json()["project"]["project_id"]

        client_b = TestClient(app)
        login_b = client_b.post("/api/v1/auth/login", data={"username": user_b, "password": "member123"})
        assert login_b.status_code == 200
        get_resp = client_b.get(f"/api/v1/projects/{project_id}")
        assert get_resp.status_code == 403

        list_resp = client_b.get("/api/v1/projects?limit=100")
        assert list_resp.status_code == 200
        assert all(row["project_id"] != project_id for row in list_resp.json())
    finally:
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider


def test_billing_charges_only_successful_generated_images() -> None:
    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    settings.auth_enabled = False
    settings.auth_provider = "local"
    username = f"billing_{uuid4().hex[:8]}"
    try:
        admin_client = TestClient(app)
        create_resp = admin_client.post(
            "/api/v1/users",
            json={
                "username": username,
                "password": "member123",
                "email": f"{username}@studioflow.local",
                "display_name": "扣费测试",
                "role": "member",
                "is_active": True,
                "initial_points": 10,
            },
        )
        assert create_resp.status_code == 200
    finally:
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider

    settings.auth_enabled = True
    settings.auth_provider = "local"
    service = get_pipeline_service()
    original_generate = service._reference_image.generate_images_from_prompts

    async def fake_generate_images_from_prompts(*, prompts, on_item_done=None, **_kwargs):
        result = {}
        for index, item in enumerate(prompts):
            ref = ShotReference(
                shot_id=item.shot_id,
                source="generated" if index < 2 else "provider_missing_result",
                image_url=f"https://example.com/{item.shot_id}.png" if index < 2 else None,
                local_path=None,
                prompt=item.prompt,
            )
            result[item.shot_id] = ref
            if on_item_done is not None:
                maybe = on_item_done(item.shot_id, ref)
                if hasattr(maybe, '__await__'):
                    await maybe
        return result

    try:
        service._reference_image.generate_images_from_prompts = fake_generate_images_from_prompts
        client = TestClient(app)
        login_resp = client.post('/api/v1/auth/login', data={'username': username, 'password': 'member123'})
        assert login_resp.status_code == 200

        before_summary = client.get('/api/v1/billing/me')
        assert before_summary.status_code == 200
        assert before_summary.json()['balance'] == 10

        create_resp = client.post(
            '/api/v1/projects',
            data={
                'product_name': '扣费仅按成功产物',
                'tool_type': 'product_image_suite',
                'target_final_count': 4,
                'takes_per_shot': 1,
            },
            files={'image': ('billing.png', PNG_20X20, 'image/png')},
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()['project']['project_id']

        plan_resp = client.post(f'/api/v1/projects/{project_id}/plan', json={'force': True, 'async_mode': False})
        assert plan_resp.status_code == 200

        generate_resp = client.post(
            f'/api/v1/projects/{project_id}/generate-images',
            json={'regenerate': False, 'async_mode': False, 'candidates_per_prompt': 1},
        )
        assert generate_resp.status_code == 200
        payload = generate_resp.json()
        assets = payload['assets']
        success_assets = [item for item in assets if item['status'] == 'ready']
        failed_assets = [item for item in assets if item['status'] == 'failed']
        assert len(success_assets) == 2
        assert len(failed_assets) == 2

        after_summary = client.get('/api/v1/billing/me')
        assert after_summary.status_code == 200
        assert after_summary.json()['balance'] == 8

        ledger_resp = client.get('/api/v1/billing/ledger?limit=20')
        assert ledger_resp.status_code == 200
        generation_entries = [
            item for item in ledger_resp.json()['items']
            if item['kind'] == 'consume_generation' and item.get('project_id') == project_id
        ]
        assert generation_entries
        assert generation_entries[0]['delta'] == -2
    finally:
        service._reference_image.generate_images_from_prompts = original_generate
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider
