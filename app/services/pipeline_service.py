from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import logging
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from app.schemas import (
    AccountStatus,
    AssetKind,
    AssetRecord,
    AssetSourceType,
    AssetStatus,
    BackgroundPolicy,
    BatchStats,
    BatchRole,
    BillingSummary,
    GenerateImagesRequest,
    GenerateVideosRequest,
    ImagePromptScript,
    IdentityMode,
    IdentityStatus,
    LedgerKind,
    LogLevel,
    MasterScript,
    PromptInputForm,
    PromptItem,
    PromptVersionMetric,
    PromptVersionMetricsResponse,
    PointsLedgerEntry,
    ProductBrief,
    PlanShot,
    ProgressStep,
    ProjectPlan,
    ProjectLog,
    ProjectProgress,
    ProjectRecord,
    ProjectStatus,
    QualityLevel,
    QualitySummaryItem,
    QualitySummaryResponse,
    QualityReport,
    RechargeOrder,
    RechargeStatus,
    RenderResponse,
    RenderRecord,
    RenderRequest,
    ReviewAction,
    ReviewDecision,
    ReviewRequest,
    ScenarioType,
    SetConfig,
    ScriptOption,
    SelectScriptRequest,
    ShowcaseRemixResponse,
    ShotApprovalStatus,
    ShotPlan,
    ShotStage,
    StoryboardStatus,
    TaskRunStatus,
    ToolType,
    UserRecord,
    UserRole,
    VideoPromptScript,
    VisualInsight,
    WorkflowMode,
    RetouchStrength,
)
from app.config import Settings
from app.services.assembly_service import AssemblyService
from app.services.compliance_service import ComplianceService
from app.services.oss_service import OssService
import httpx
from app.services.reference_image_service import ReferenceImageService
from app.services.sora_service import KieSoraService
from app.services.volc_service import VolcScriptService
from app.store import InMemoryStore, utc_now

logger = logging.getLogger(__name__)
_BATCH_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAEAQH/2fY9WQAAAABJRU5ErkJggg=="
)

TOOL_SCENARIO_MAP: dict[ToolType, ScenarioType] = {
    ToolType.intro_video_multi_script: ScenarioType.product_video,
    ToolType.product_image_suite: ScenarioType.product_image_suite,
    ToolType.model_retouch: ScenarioType.model_retouch,
    ToolType.quick_video_15s: ScenarioType.product_video,
    ToolType.multi_angle_camera: ScenarioType.multi_angle_camera,
}

IDENTITY_LIGHTING_PRESETS: dict[str, str] = {
    "softbox_clean": "双柔光箱45度布光，皮肤层次干净，阴影克制",
    "window_natural": "侧窗自然光，保留真实肌理与柔和过渡",
    "rim_fashion": "主光+轮廓光分离主体，强调时尚立体感",
}
IDENTITY_FRAMING_PRESETS: dict[str, str] = {
    "headshot": "近景头像，突出五官与皮肤细节",
    "half_body": "半身构图，兼顾表情、姿态与服装",
    "full_body": "全身构图，强调身形比例与动作流线",
}
IDENTITY_ANGLE_PRESETS: dict[str, str] = {
    "front": "正面平视",
    "left_45": "左前45度",
    "right_45": "右前45度",
    "back": "背面站姿",
    "slight_low": "轻微仰拍",
}

SHOWCASE_SHARE_TAG = "showcase_shared"
SHARE_REWARD_POINTS = 2
SHARE_REWARD_PER_PROJECT_LIMIT = 5
SHARE_REWARD_DAILY_LIMIT = 50
IMAGE_GENERATION_COST_PER_ASSET = 1
VIDEO_GENERATION_COST_PER_VARIANT = 10


class PipelineService:
    def __init__(
        self,
        store: InMemoryStore,
        script_service: VolcScriptService,
        compliance_service: ComplianceService,
        sora_service: KieSoraService,
        reference_image_service: ReferenceImageService,
        assembly_service: AssemblyService,
        storage_root: Path,
        settings: Settings | None = None,
    ) -> None:
        self._store = store
        self._script_service = script_service
        self._compliance = compliance_service
        self._sora = sora_service
        self._reference_image = reference_image_service
        self._assembly = assembly_service
        self._storage_root = storage_root
        self._oss = OssService(settings or script_service._settings)
        self._plan_tasks: dict[str, asyncio.Task[None]] = {}
        self._storyboard_tasks: dict[str, asyncio.Task[None]] = {}
        self._render_tasks: dict[str, asyncio.Task[None]] = {}
        self._image_tasks: dict[str, asyncio.Task[None]] = {}
        self._ensure_default_users(settings or script_service._settings)

    def _password_hash(self, raw_password: str) -> str:
        payload = f"{raw_password}|{self._script_service._settings.auth_secret}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _ensure_default_users(self, settings: Settings) -> None:
        admin_username = (settings.admin_username or "admin").strip() or "admin"
        if self._store.get_user(admin_username):
            return
        now = utc_now()
        admin = UserRecord(
            username=admin_username,
            email=(settings.admin_email or "admin@studioflow.local").strip().lower(),
            display_name="系统管理员",
            workspace_id="default_workspace",
            role=UserRole.admin,
            account_status=AccountStatus.active,
            is_active=True,
            points_balance=100000,
            created_at=now,
            updated_at=now,
        )
        self._store.add_user(admin)
        self._store.set_user_password_hash(admin_username, self._password_hash(settings.admin_password or "admin123"))
        self._store.add_project_log(
            project_id="system",
            level=LogLevel.info,
            stage="user.bootstrap",
            message="初始化默认管理员账户",
            details={"username": admin_username},
        )
        self._store.add_points_ledger(
            PointsLedgerEntry(
                ledger_id=str(uuid4()),
                username=admin_username,
                delta=admin.points_balance,
                balance_after=admin.points_balance,
                kind=LedgerKind.manual_adjust,
                note="系统初始化额度",
                created_at=now,
            )
        )

    def authenticate_local_user(self, username_or_email: str, password: str) -> UserRecord | None:
        user = self.find_user_by_login(username_or_email)
        if not user or not user.is_active:
            return None
        if user.account_status in {AccountStatus.suspended, AccountStatus.frozen}:
            return None
        stored_hash = self._store.get_user_password_hash(user.username)
        if not stored_hash:
            # Backward compatibility: bootstrap legacy admin from env password.
            if user.username == self._script_service._settings.admin_username and password == self._script_service._settings.admin_password:
                stored_hash = self._password_hash(password)
                self._store.set_user_password_hash(user.username, stored_hash)
        if stored_hash != self._password_hash(password):
            return None
        self._store.update_user(
            user.username,
            lambda u: setattr(u, "last_login_at", utc_now()),
        )
        return self._store.get_user(user.username)

    def find_user_by_login(self, username_or_email: str) -> UserRecord | None:
        login_value = (username_or_email or "").strip().lower()
        if not login_value:
            return None
        users = self._store.list_users()
        return next(
            (
                item
                for item in users
                if item.username.lower() == login_value or item.email.lower() == login_value
            ),
            None,
        )

    def get_user(self, username: str) -> UserRecord | None:
        return self._store.get_user((username or "").strip())

    def list_users(self) -> list[UserRecord]:
        return self._store.list_users()

    def create_user(
        self,
        *,
        username: str,
        password: str,
        email: str | None,
        display_name: str | None,
        workspace_id: str | None,
        role: UserRole,
        account_status: AccountStatus,
        is_active: bool,
        initial_points: int,
    ) -> UserRecord:
        normalized_username = (username or "").strip().lower()
        if not normalized_username:
            raise ValueError("username is required")
        if not normalized_username.replace("_", "").isalnum():
            raise ValueError("username can only contain letters, digits, and underscores")
        if self._store.get_user(normalized_username):
            raise ValueError("username already exists")
        normalized_email = (email or f"{normalized_username}@studioflow.local").strip().lower()
        if "@" not in normalized_email:
            raise ValueError("email is invalid")
        if any((row.email or "").strip().lower() == normalized_email for row in self._store.list_users()):
            raise ValueError("email already exists")
        normalized_workspace = (workspace_id or "default_workspace").strip().lower() or "default_workspace"
        now = utc_now()
        user = UserRecord(
            username=normalized_username,
            email=normalized_email,
            display_name=(display_name or normalized_username).strip(),
            workspace_id=normalized_workspace,
            role=role,
            account_status=account_status,
            is_active=is_active,
            points_balance=max(0, int(initial_points or 0)),
            created_at=now,
            updated_at=now,
        )
        self._store.add_user(user)
        self._store.set_user_password_hash(normalized_username, self._password_hash(password))
        if user.points_balance > 0:
            self._store.add_points_ledger(
                PointsLedgerEntry(
                    ledger_id=str(uuid4()),
                    username=user.username,
                    delta=user.points_balance,
                    balance_after=user.points_balance,
                    kind=LedgerKind.manual_adjust,
                    note="创建用户初始积分",
                    created_at=now,
                )
            )
        return user

    def register_user(
        self,
        *,
        username: str,
        password: str,
        email: str,
        display_name: str | None = None,
    ) -> UserRecord:
        return self.create_user(
            username=username,
            password=password,
            email=email,
            display_name=display_name,
            workspace_id="default_workspace",
            role=UserRole.member,
            account_status=AccountStatus.trial,
            is_active=True,
            initial_points=60,
        )

    def update_user(
        self,
        *,
        username: str,
        display_name: str | None = None,
        workspace_id: str | None = None,
        role: UserRole | None = None,
        account_status: AccountStatus | None = None,
        is_active: bool | None = None,
        password: str | None = None,
    ) -> UserRecord:
        normalized_username = (username or "").strip().lower()
        if not self._store.get_user(normalized_username):
            raise KeyError("user not found")
        self._store.update_user(
            normalized_username,
            lambda user: (
                setattr(user, "display_name", display_name.strip() if display_name is not None else user.display_name),
                setattr(
                    user,
                    "workspace_id",
                    (workspace_id or "").strip().lower() if workspace_id is not None and workspace_id.strip() else user.workspace_id,
                ),
                setattr(user, "role", role if role is not None else user.role),
                setattr(user, "account_status", account_status if account_status is not None else user.account_status),
                setattr(user, "is_active", bool(is_active) if is_active is not None else user.is_active),
            ),
        )
        if password:
            self._store.set_user_password_hash(normalized_username, self._password_hash(password))
        updated = self._store.get_user(normalized_username)
        if not updated:
            raise KeyError("user not found")
        return updated

    def _apply_points_delta(
        self,
        *,
        username: str,
        delta: int,
        kind: LedgerKind,
        note: str | None = None,
        project_id: str | None = None,
        asset_id: str | None = None,
        allow_negative_balance: bool = False,
    ) -> PointsLedgerEntry:
        user = self._store.get_user(username)
        if not user:
            raise KeyError("user not found")
        old_balance = int(user.points_balance or 0)
        new_balance = old_balance + int(delta)
        if not allow_negative_balance and new_balance < 0:
            raise ValueError("积分不足，请先充值。")
        self._store.update_user(
            username,
            lambda u: setattr(u, "points_balance", max(new_balance, 0)),
        )
        entry = PointsLedgerEntry(
            ledger_id=str(uuid4()),
            username=username,
            delta=int(delta),
            balance_after=max(new_balance, 0),
            kind=kind,
            note=note,
            project_id=project_id,
            asset_id=asset_id,
            created_at=utc_now(),
        )
        self._store.add_points_ledger(entry)
        return entry

    def list_points_ledger(self, username: str, limit: int = 100) -> list[PointsLedgerEntry]:
        return self._store.list_points_ledger(username=username, limit=limit)

    def get_billing_summary(self, username: str) -> BillingSummary:
        user = self._store.get_user(username)
        if not user:
            raise KeyError("user not found")
        today = utc_now().astimezone(timezone.utc).date()
        ledger = self._store.list_points_ledger(username=username, limit=1000)
        today_income = sum(item.delta for item in ledger if item.delta > 0 and item.created_at.date() == today)
        today_cost = -sum(item.delta for item in ledger if item.delta < 0 and item.created_at.date() == today)
        pending_recharge_count = len(
            [item for item in self._store.list_recharge_orders(username=username, limit=1000) if item.status == RechargeStatus.pending]
        )
        return BillingSummary(
            username=user.username,
            balance=int(user.points_balance or 0),
            today_income=today_income,
            today_cost=today_cost,
            pending_recharge_count=pending_recharge_count,
        )

    def create_recharge_order(
        self,
        *,
        username: str,
        points: int,
        amount_cny: float,
        channel: str,
        note: str | None = None,
    ) -> RechargeOrder:
        user = self._store.get_user(username)
        if not user:
            raise KeyError("user not found")
        now = utc_now()
        order = RechargeOrder(
            order_id=str(uuid4()),
            username=username,
            points=max(1, int(points)),
            amount_cny=float(amount_cny),
            channel=(channel or "manual").strip() or "manual",
            status=RechargeStatus.pending,
            created_at=now,
            updated_at=now,
            note=note,
        )
        self._store.add_recharge_order(order)
        return order

    def confirm_recharge_order(self, *, order_id: str, operator: str) -> RechargeOrder:
        order = self._store.get_recharge_order(order_id)
        if not order:
            raise KeyError("order not found")
        if order.status != RechargeStatus.pending:
            return order
        now = utc_now()
        self._store.update_recharge_order(
            order_id,
            lambda row: (
                setattr(row, "status", RechargeStatus.paid),
                setattr(row, "paid_at", now),
                setattr(row, "operator", operator),
            ),
        )
        self._apply_points_delta(
            username=order.username,
            delta=int(order.points),
            kind=LedgerKind.recharge,
            note=f"充值到账（订单 {order.order_id[:8]}）",
        )
        updated = self._store.get_recharge_order(order_id)
        if not updated:
            raise KeyError("order not found")
        return updated

    def list_recharge_orders(self, *, username: str | None = None, limit: int = 100) -> list[RechargeOrder]:
        return self._store.list_recharge_orders(username=username, limit=limit)

    def adjust_points(
        self,
        *,
        username: str,
        delta: int,
        note: str | None = None,
    ) -> PointsLedgerEntry:
        return self._apply_points_delta(
            username=username,
            delta=delta,
            kind=LedgerKind.manual_adjust,
            note=note or "管理员手动调整",
        )

    def _pad_product_image_plan(
        self,
        project: ProjectRecord,
        plan: ProjectPlan,
    ) -> ProjectPlan:
        if project.tool_type != ToolType.product_image_suite:
            return plan
        if not project.set_config:
            return plan
        target = int(project.set_config.target_final_count or 0)
        if target <= 0:
            return plan
        shots = list(plan.shots)
        if len(shots) >= target:
            return plan
        existing_ids = {shot.shot_id for shot in shots}
        stage_cycle = [ShotStage.hook, ShotStage.feature, ShotStage.proof, ShotStage.cta]
        delivery_map = {
            ShotStage.hook: "主图",
            ShotStage.feature: "场景图",
            ShotStage.proof: "细节图",
            ShotStage.cta: "对比图",
        }
        base_prompt = (
            f"{project.brief.product_name}，补充展示画面，高细节、真实质感、画面干净，不要文字、logo、水印。"
        )
        for idx in range(len(shots) + 1, target + 1):
            stage = stage_cycle[(idx - 1) % len(stage_cycle)]
            shot_id = f"shot-{idx}"
            if shot_id in existing_ids:
                shot_id = f"shot-{idx}-{uuid4().hex[:4]}"
            existing_ids.add(shot_id)
            shots.append(
                PlanShot(
                    shot_id=shot_id,
                    title=f"镜头{idx}",
                    intent="补充展示卖点与质感",
                    duration_sec=4,
                    stage=stage,
                    image_prompt=base_prompt,
                    video_prompt=base_prompt,
                    delivery_purpose=delivery_map.get(stage, "场景图"),
                )
            )
        return plan.model_copy(update={"shots": shots})

    def _planner_execution_hints(self, project: ProjectRecord) -> dict[str, int | None]:
        if project.tool_type != ToolType.product_image_suite or not project.set_config:
            return {
                "expected_shot_count": None,
                "takes_per_shot": None,
                "target_candidate_assets": None,
            }
        expected = max(3, min(30, int(project.set_config.target_final_count or 0)))
        takes = max(1, min(4, int(project.set_config.takes_per_shot or 1)))
        return {
            "expected_shot_count": expected,
            "takes_per_shot": takes,
            "target_candidate_assets": expected * takes,
        }

    def _default_delivery_purpose(self, scenario_type: ScenarioType, stage: ShotStage) -> str:
        if scenario_type == ScenarioType.product_image_suite:
            mapping = {
                ShotStage.hook: "主图",
                ShotStage.feature: "场景图",
                ShotStage.proof: "细节图",
                ShotStage.cta: "对比图",
            }
            return mapping.get(stage, "场景图")
        if scenario_type == ScenarioType.model_retouch:
            return "单图精修交付"
        if scenario_type == ScenarioType.multi_angle_camera:
            return "角度展示图"
        return "视频关键帧"

    def _normalize_project_plan_delivery_purpose(
        self,
        scenario_type: ScenarioType,
        plan: ProjectPlan,
    ) -> ProjectPlan:
        normalized_shots: list[PlanShot] = []
        changed = False
        for shot in plan.shots:
            normalized = (shot.delivery_purpose or "").strip()
            if not normalized:
                normalized = self._default_delivery_purpose(scenario_type=scenario_type, stage=shot.stage)
            if normalized != (shot.delivery_purpose or ""):
                changed = True
                normalized_shots.append(shot.model_copy(update={"delivery_purpose": normalized}))
            else:
                normalized_shots.append(shot)
        if not changed:
            return plan
        return plan.model_copy(update={"shots": normalized_shots})

    def _build_marketing_copy(
        self,
        *,
        product_name: str,
        purpose: str,
        intent: str,
        title: str,
    ) -> str:
        core = (intent or title or product_name or "核心卖点").strip()
        normalized_purpose = (purpose or "").strip()
        if "主图" in normalized_purpose:
            return f"主图主打：{core}，第一眼突出{product_name}的核心价值。"
        if "场景" in normalized_purpose:
            return f"场景表达：{core}，强调真实使用中的体验感与代入感。"
        if "细节" in normalized_purpose:
            return f"细节卖点：{core}，放大材质与做工优势，提升信任感。"
        if "对比" in normalized_purpose:
            return f"决策对比：{core}，帮助用户快速理解差异并做选择。"
        if "角度" in normalized_purpose:
            return f"角度展示：{core}，补全{product_name}的立体信息。"
        if "精修" in normalized_purpose:
            return f"精修目标：{core}，在保持一致性的前提下提升成片质感。"
        return f"卖点说明：{core}"

    def _resolve_owner_username(self, project: ProjectRecord) -> str:
        owner = (project.owner_username or "").strip().lower()
        if owner:
            return owner
        return (self._script_service._settings.admin_username or "admin").strip().lower()

    def _resolve_workspace_id_for_user(self, username: str | None) -> str:
        normalized = (username or "").strip().lower()
        if normalized:
            user = self._store.get_user(normalized)
            if user and (user.workspace_id or "").strip():
                return user.workspace_id.strip().lower()
        return "default_workspace"

    def _ensure_sufficient_points(self, *, username: str, required: int, reason: str) -> None:
        if required <= 0:
            return
        user = self._store.get_user(username)
        if not user:
            return
        if int(user.points_balance or 0) < required:
            raise ValueError(f"积分不足，{reason}需要 {required} 积分，请先充值。")

    def _charge_generation_points(
        self,
        *,
        username: str,
        cost_points: int,
        project_id: str,
        note: str,
    ) -> None:
        if cost_points <= 0:
            return
        self._apply_points_delta(
            username=username,
            delta=-cost_points,
            kind=LedgerKind.consume_generation,
            note=note,
            project_id=project_id,
        )

    def _asset_is_showcase_shared(self, asset: AssetRecord) -> bool:
        metadata = asset.metadata or {}
        if bool(metadata.get("showcase_shared")):
            return True
        return any(tag.lower() == SHOWCASE_SHARE_TAG for tag in asset.tags)

    def _asset_reward_points(self, asset: AssetRecord) -> int:
        try:
            return max(0, int((asset.metadata or {}).get("share_reward_points") or 0))
        except Exception:
            return 0

    def _asset_reward_awarded_at(self, asset: AssetRecord) -> datetime | None:
        raw = str((asset.metadata or {}).get("share_reward_awarded_at") or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _total_share_points(self) -> int:
        return sum(self._asset_reward_points(item) for item in self._store.list_assets_global(limit=200000))

    def _daily_reward_points_issued(self, now: datetime) -> int:
        today = now.astimezone(timezone.utc).date()
        total = 0
        for asset in self._store.list_assets_global(limit=200000):
            awarded_at = self._asset_reward_awarded_at(asset)
            if not awarded_at or awarded_at.date() != today:
                continue
            total += self._asset_reward_points(asset)
        return total

    def _project_rewarded_share_count(self, project_id: str) -> int:
        return sum(
            1
            for item in self._store.list_assets(project_id=project_id)
            if self._asset_reward_points(item) > 0
        )

    @property
    def oss(self) -> OssService:
        return self._oss

    def _enqueue_oss_upload(
        self,
        *,
        asset_id: str,
        project_id: str,
        local_path: Path,
        object_key: str,
        content_type: str | None,
        update_project_image: bool,
    ) -> None:
        if not self._oss.enabled:
            return

        async def _runner() -> None:
            try:
                public_url = await self._oss.upload_file(
                    local_path=local_path,
                    object_key=object_key,
                    content_type=content_type,
                )
                self._store.update_asset(asset_id, lambda asset: setattr(asset, "image_url", public_url))
                if update_project_image:
                    self._store.update_project(
                        project_id,
                        lambda p: setattr(p, "image_public_url", public_url),
                    )
            except Exception as exc:  # pragma: no cover - network instability
                logger.warning("Upload asset to OSS failed: %s", exc)

        asyncio.create_task(_runner())

    async def _run_intro_bootstrap(
        self,
        *,
        project_id: str,
        image_bytes: bytes,
        image_mime: str,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
        tool_type: ToolType,
    ) -> None:
        try:
            project_plan = await self._script_service.generate_project_plan(
                image_bytes=image_bytes,
                image_mime=image_mime,
                brief=brief,
                scenario_type=scenario_type,
                template_name=template_name,
                quality_level=quality_level,
                tool_type=tool_type,
                strict_json=True,
            )
            self._store.update_project(project_id, lambda p: setattr(p, "project_plan", project_plan))
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="plan.completed",
                message="AI设计师方案生成完成",
                details={"shot_count": len(project_plan.shots)},
            )
        except Exception as exc:
            self._log(
                project_id=project_id,
                level=LogLevel.warning,
                stage="plan.pending",
                message="AI方案暂未就绪，可在工作台重试",
                details={"error": str(exc)},
            )

        try:
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="vl.start",
                message="开始视觉理解与脚本生成",
            )
            safe_brief = brief.model_copy(
                update={"desired_duration_sec": max(30, brief.desired_duration_sec)}
            )
            insight, scripts = await self._script_service.analyze_and_plan(
                image_bytes=image_bytes,
                image_mime=image_mime,
                brief=safe_brief,
            )
            sanitized = [self._compliance.sanitize_script(script) for script in scripts]
            fallback_used = any("回退" in risk for risk in (insight.risks or []))
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "insight", insight),
                    setattr(p, "script_options", sanitized),
                    setattr(p, "status", ProjectStatus.scripted),
                    setattr(p, "task_status", TaskRunStatus.queued),
                    setattr(p, "error_message", None),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.warning if fallback_used else LogLevel.info,
                stage="vl.completed",
                message="脚本生成完成",
                details={
                    "script_count": len(self._get_project_or_raise(project_id).script_options),
                    "fallback_used": fallback_used,
                },
            )
        except Exception as exc:  # pragma: no cover - defensive status handling
            error_message = str(exc)
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "status", ProjectStatus.failed),
                    setattr(p, "task_status", TaskRunStatus.failed),
                    setattr(p, "error_message", error_message),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.error,
                stage="vl.failed",
                message="脚本生成失败",
                details={"error": error_message},
            )

    def _enqueue_intro_bootstrap(
        self,
        *,
        project_id: str,
        image_bytes: bytes,
        image_mime: str,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
        tool_type: ToolType,
    ) -> None:
        async def _runner() -> None:
            await self._run_intro_bootstrap(
                project_id=project_id,
                image_bytes=image_bytes,
                image_mime=image_mime,
                brief=brief,
                scenario_type=scenario_type,
                template_name=template_name,
                quality_level=quality_level,
                tool_type=tool_type,
            )

        asyncio.create_task(_runner())

    async def create_project(
        self,
        image_bytes: bytes,
        image_mime: str,
        image_suffix: str,
        brief: ProductBrief,
        image_public_url: str | None,
        owner_username: str | None = None,
        tool_type: ToolType = ToolType.intro_video_multi_script,
        prompt_inputs: PromptInputForm | None = None,
        scenario_type: ScenarioType = ScenarioType.product_video,
        template_name: str = "general",
        quality_level: QualityLevel = QualityLevel.standard,
        batch_group_id: str | None = None,
        batch_role: BatchRole = BatchRole.member,
        reference_images: list[dict[str, Any]] | None = None,
        reference_image_public_urls: list[str] | None = None,
        identity_image_public_url: str | None = None,
        identity_required: bool = False,
        background_policy: BackgroundPolicy = BackgroundPolicy.keep_original,
        output_aspect_ratio: str = "original",
        retouch_strength: RetouchStrength = RetouchStrength.light,
        camera_inputs: dict[str, Any] | None = None,
        set_config: SetConfig | None = None,
        workflow_mode: WorkflowMode | None = None,
        project_id: str | None = None,
    ) -> ProjectRecord:
        project_id = project_id or str(uuid4())
        if self._store.get_project(project_id):
            raise ValueError("Project id already exists")
        image_path = self._storage_root / "uploads" / f"{project_id}{image_suffix or '.png'}"
        if image_bytes:
            image_path = self._write_image(project_id, image_bytes, image_suffix)
        resolved_image_public_url = image_public_url
        source_object_key: str | None = None
        if not resolved_image_public_url and self._oss.enabled:
            source_object_key = self._oss.object_key("inputs", project_id, f"source{image_suffix or '.png'}")

        now = utc_now()
        resolved_workflow_mode = workflow_mode or WorkflowMode.default
        if tool_type == ToolType.product_image_suite and resolved_workflow_mode == WorkflowMode.default:
            resolved_workflow_mode = WorkflowMode.product_set
        if tool_type == ToolType.model_retouch and resolved_workflow_mode == WorkflowMode.default:
            resolved_workflow_mode = WorkflowMode.retouch_per_image
        resolved_set_config = set_config
        if tool_type == ToolType.product_image_suite and resolved_set_config is None:
            resolved_set_config = SetConfig()
        resolved_owner_username = (
            (owner_username or "").strip().lower()
            or (self._script_service._settings.admin_username or "admin").strip().lower()
        )
        resolved_workspace_id = self._resolve_workspace_id_for_user(resolved_owner_username)
        project = ProjectRecord(
            project_id=project_id,
            owner_username=resolved_owner_username,
            workspace_id=resolved_workspace_id,
            tool_type=tool_type,
            status=ProjectStatus.draft,
            task_status=TaskRunStatus.queued,
            created_at=now,
            updated_at=now,
            image_path=str(image_path),
            source_image_b64=base64.b64encode(image_bytes).decode("utf-8") if image_bytes else None,
            image_public_url=resolved_image_public_url,
            brief=brief,
            scenario_type=scenario_type,
            template_name=template_name,
            quality_level=quality_level,
            prompt_inputs=prompt_inputs
            or self._script_service.default_prompt_inputs(tool_type=tool_type, template_name=template_name),
            batch_group_id=batch_group_id,
            batch_role=batch_role,
            workflow_mode=resolved_workflow_mode,
            identity_required=identity_required,
            identity_mode=IdentityMode.none,
            identity_status=IdentityStatus.pending if identity_required else IdentityStatus.confirmed,
            background_policy=background_policy,
            output_aspect_ratio=output_aspect_ratio if output_aspect_ratio else "original",
            retouch_strength=retouch_strength,
            camera_inputs=dict(camera_inputs or {}),
            set_config=resolved_set_config,
        )
        self._store.add_project(project)
        input_asset = AssetRecord(
            asset_id=str(uuid4()),
            project_id=project_id,
            workspace_id=resolved_workspace_id,
            tool_type=tool_type,
            kind=AssetKind.input,
            source_type=AssetSourceType.uploaded,
            status=AssetStatus.ready,
            created_at=now,
            updated_at=now,
            local_path=str(image_path) if image_bytes else None,
            image_url=resolved_image_public_url,
            tags=["input", tool_type.value],
            metadata={"mime": image_mime, "suffix": image_suffix},
        )
        self._store.add_asset(input_asset)
        self._store.update_project(
            project_id,
            lambda p: setattr(p, "asset_ids", [*p.asset_ids, input_asset.asset_id]),
        )
        if source_object_key and self._oss.enabled:
            self._enqueue_oss_upload(
                asset_id=input_asset.asset_id,
                project_id=project_id,
                local_path=image_path,
                object_key=source_object_key,
                content_type=image_mime,
                update_project_image=True,
            )

        uploaded_refs = reference_images or []
        public_ref_urls = reference_image_public_urls or []
        for idx, ref in enumerate(uploaded_refs, start=1):
            ref_bytes = ref.get("image_bytes")
            if not isinstance(ref_bytes, (bytes, bytearray)):
                continue
            ref_suffix = str(ref.get("image_suffix") or ".png")
            ref_mime = str(ref.get("image_mime") or "image/png")
            ref_role = str(ref.get("role") or f"reference_{idx}").strip() or f"reference_{idx}"
            ref_path = self._write_image(f"{project_id}_ref_{idx}", bytes(ref_bytes), ref_suffix)
            ref_public_url: str | None = None
            ref_object_key: str | None = None
            if self._oss.enabled:
                ref_object_key = self._oss.object_key("inputs", project_id, "references", f"{ref_role}_{idx}{ref_suffix}")
            ref_asset = AssetRecord(
                asset_id=str(uuid4()),
                project_id=project_id,
                workspace_id=resolved_workspace_id,
                tool_type=tool_type,
                kind=AssetKind.input,
                source_type=AssetSourceType.uploaded,
                status=AssetStatus.ready,
                created_at=now,
                updated_at=now,
                local_path=str(ref_path),
                image_url=ref_public_url,
                tags=["input", "reference", ref_role, tool_type.value],
                metadata={"mime": ref_mime, "suffix": ref_suffix, "role": ref_role},
            )
            self._store.add_asset(ref_asset)
            if ref_object_key and self._oss.enabled:
                self._enqueue_oss_upload(
                    asset_id=ref_asset.asset_id,
                    project_id=project_id,
                    local_path=ref_path,
                    object_key=ref_object_key,
                    content_type=ref_mime,
                    update_project_image=False,
                )
            if ref_role == "identity":
                self._store.update_project(
                    project_id,
                    lambda p, aid=ref_asset.asset_id: (
                        setattr(p, "asset_ids", [*p.asset_ids, aid]),
                        setattr(p, "identity_asset_id", aid),
                        setattr(p, "identity_mode", IdentityMode.uploaded),
                        setattr(p, "identity_status", IdentityStatus.pending),
                        setattr(p, "identity_required", True),
                    ),
                )
            else:
                self._store.update_project(
                    project_id,
                    lambda p, aid=ref_asset.asset_id: setattr(p, "asset_ids", [*p.asset_ids, aid]),
                )

        for idx, ref_url in enumerate(public_ref_urls, start=1):
            value = str(ref_url or "").strip()
            if not value:
                continue
            ref_asset = AssetRecord(
                asset_id=str(uuid4()),
                project_id=project_id,
                workspace_id=resolved_workspace_id,
                tool_type=tool_type,
                kind=AssetKind.input,
                source_type=AssetSourceType.uploaded,
                status=AssetStatus.ready,
                created_at=now,
                updated_at=now,
                local_path=None,
                image_url=value,
                tags=["input", "reference", f"public_{idx}", tool_type.value],
                metadata={"source": "public_url", "role": f"public_{idx}"},
            )
            self._store.add_asset(ref_asset)
            self._store.update_project(
                project_id,
                lambda p, aid=ref_asset.asset_id: setattr(p, "asset_ids", [*p.asset_ids, aid]),
            )
        if identity_image_public_url:
            identity_asset = AssetRecord(
                asset_id=str(uuid4()),
                project_id=project_id,
                workspace_id=resolved_workspace_id,
                tool_type=tool_type,
                kind=AssetKind.input,
                source_type=AssetSourceType.uploaded,
                status=AssetStatus.ready,
                created_at=now,
                updated_at=now,
                local_path=None,
                image_url=identity_image_public_url,
                tags=["input", "reference", "identity", tool_type.value],
                metadata={"source": "public_url", "role": "identity"},
            )
            self._store.add_asset(identity_asset)
            self._store.update_project(
                project_id,
                lambda p, aid=identity_asset.asset_id: (
                    setattr(p, "asset_ids", [*p.asset_ids, aid]),
                    setattr(p, "identity_asset_id", aid),
                    setattr(p, "identity_mode", IdentityMode.uploaded),
                    setattr(p, "identity_status", IdentityStatus.pending),
                    setattr(p, "identity_required", True),
                ),
            )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="create.start",
            message="收到创建项目请求",
            details={
                "product_name": brief.product_name,
                "scenario_type": scenario_type.value,
                "template_name": template_name,
                "image_path": str(image_path),
                "reference_count": len(uploaded_refs) + len(public_ref_urls),
                "workflow_mode": resolved_workflow_mode.value,
                "set_config": resolved_set_config.model_dump() if resolved_set_config else None,
            },
        )
        self._store.update_project(project_id, lambda p: setattr(p, "task_status", TaskRunStatus.running))
        if tool_type == ToolType.intro_video_multi_script:
            settings = getattr(self._script_service, "_settings", None)
            run_inline = bool(settings and (settings.use_mock_providers or not settings.allow_background_tasks))
            if run_inline:
                await self._run_intro_bootstrap(
                    project_id=project_id,
                    image_bytes=image_bytes,
                    image_mime=image_mime,
                    brief=brief,
                    scenario_type=scenario_type,
                    template_name=template_name,
                    quality_level=quality_level,
                    tool_type=tool_type,
                )
            else:
                self._enqueue_intro_bootstrap(
                    project_id=project_id,
                    image_bytes=image_bytes,
                    image_mime=image_mime,
                    brief=brief,
                    scenario_type=scenario_type,
                    template_name=template_name,
                    quality_level=quality_level,
                    tool_type=tool_type,
                )
        else:
            insight = VisualInsight(
                summary="任务已创建。请进入 Step2 生成拍摄方案，再执行试拍。",
                visible_points=brief.key_features[:6],
                risks=[],
            )
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "insight", insight),
                    setattr(p, "status", ProjectStatus.scripted),
                    setattr(p, "task_status", TaskRunStatus.queued),
                    setattr(p, "error_message", None),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="tool.ready",
                message="任务创建完成，等待执行工具专属流程",
                details={"tool_type": tool_type.value},
            )

        if batch_group_id:
            self._sync_batch_stats(batch_group_id)
        return self._store.get_project(project_id) or project

    async def create_batch_projects(
        self,
        items: list[dict[str, Any]],
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
        owner_username: str | None = None,
        tool_type: ToolType = ToolType.intro_video_multi_script,
    ) -> list[ProjectRecord]:
        batch_group_id = str(uuid4())
        projects: list[ProjectRecord] = []
        for item in items:
            product_name = str(item.get("product_name") or "").strip()
            image_public_url = str(item.get("image_public_url") or "").strip() or None
            if not product_name:
                continue
            brief = ProductBrief(
                product_name=product_name,
                target_audience=str(item.get("target_audience") or "注重体验和性价比的人群"),
                platform=str(item.get("platform") or "douyin"),
                key_features=[str(v) for v in item.get("key_features", []) if str(v).strip()],
                desired_duration_sec=int(item.get("desired_duration_sec") or 15),
                channels=[str(v) for v in item.get("channels", []) if str(v).strip()] or ["douyin"],
            )
            project = await self.create_project(
                image_bytes=_BATCH_PLACEHOLDER_PNG,
                image_mime="image/png",
                image_suffix=".png",
                brief=brief,
                image_public_url=image_public_url,
                owner_username=owner_username,
                tool_type=tool_type,
                scenario_type=scenario_type,
                template_name=template_name,
                quality_level=quality_level,
                batch_group_id=batch_group_id,
            )
            projects.append(project)
        return projects

    def select_script(self, project_id: str, request: SelectScriptRequest) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="script.select.start",
            message="开始选择脚本",
            details={"script_id": request.script_id, "edit_count": len(request.edits)},
        )
        script = next(
            (item for item in project.script_options if item.script_id == request.script_id),
            None,
        )
        if not script:
            self._log(
                project_id=project_id,
                level=LogLevel.error,
                stage="script.select.failed",
                message="脚本不存在",
                details={"script_id": request.script_id},
            )
            raise ValueError(f"script_id {request.script_id} not found")

        selected = script.model_copy(deep=True)
        edit_map = {item.shot_id: item for item in request.edits}
        for shot in selected.shots:
            edit = edit_map.get(shot.shot_id)
            if not edit:
                continue
            if edit.narration:
                shot.narration = edit.narration
            if edit.on_screen_text:
                shot.on_screen_text = edit.on_screen_text
            if edit.visual_prompt:
                shot.visual_prompt = edit.visual_prompt
            if edit.reference_image_prompt:
                shot.reference_image_prompt = edit.reference_image_prompt
            if edit.motion_direction:
                shot.motion_direction = edit.motion_direction
            if edit.voiceover_direction:
                shot.voiceover_direction = edit.voiceover_direction
            if edit.duration_sec:
                shot.duration_sec = edit.duration_sec

        selected.total_duration_sec = sum(item.duration_sec for item in selected.shots)
        selected = self._compliance.sanitize_script(selected)
        master_script = self._script_to_master(selected)
        shot_approvals = {
            shot.shot_id: ShotApprovalStatus.pending for shot in master_script.shots
        }

        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "selected_script", selected),
                setattr(p, "master_script", master_script),
                setattr(p, "image_prompt_script", None),
                setattr(p, "video_prompt_script", None),
                setattr(p, "shot_approvals", shot_approvals),
                setattr(p, "status", ProjectStatus.scripted),
                setattr(p, "storyboard_status", StoryboardStatus.not_started),
                setattr(p, "storyboard_references", {}),
                setattr(p, "storyboard_error_message", None),
                setattr(p, "render_id", None),
                setattr(p, "error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="script.select.completed",
            message="脚本选择完成",
            details={"script_id": selected.script_id, "duration_sec": selected.total_duration_sec},
        )
        return self._get_project_or_raise(project_id)

    def update_master_script(self, project_id: str, master_script: MasterScript) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        if not project.selected_script:
            raise ValueError("Please select a script before editing master script.")

        sanitized = self._compliance.sanitize_script(self._master_to_script(master_script))
        approved_script = self._script_to_master(sanitized)
        shot_approvals = {
            shot.shot_id: ShotApprovalStatus.pending for shot in approved_script.shots
        }

        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "master_script", approved_script),
                setattr(p, "selected_script", sanitized),
                setattr(p, "image_prompt_script", None),
                setattr(p, "video_prompt_script", None),
                setattr(p, "shot_approvals", shot_approvals),
                setattr(p, "status", ProjectStatus.scripted),
                setattr(p, "storyboard_status", StoryboardStatus.not_started),
                setattr(p, "storyboard_references", {}),
                setattr(p, "storyboard_error_message", None),
                setattr(p, "render_id", None),
                setattr(p, "error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="master_script.updated",
            message="主拍摄脚本已更新",
            details={"shot_count": len(approved_script.shots)},
        )
        return self._get_project_or_raise(project_id)

    async def derive_prompts(self, project_id: str, force: bool = False) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="derive_prompts")
        if project.prompt_pack and not force:
            return project

        if not project.project_plan:
            image_bytes = self._get_project_image_bytes(project)
            planner_hints = self._planner_execution_hints(project)
            generated_plan = await self._script_service.generate_project_plan(
                image_bytes=image_bytes,
                image_mime=self._get_project_image_mime(project),
                brief=project.brief,
                scenario_type=project.scenario_type,
                template_name=project.template_name,
                quality_level=project.quality_level,
                tool_type=project.tool_type,
                expected_shot_count=planner_hints["expected_shot_count"],
                takes_per_shot=planner_hints["takes_per_shot"],
                target_candidate_assets=planner_hints["target_candidate_assets"],
                strict_json=True,
            )
            self._store.update_project(project_id, lambda p: setattr(p, "project_plan", generated_plan))
            project = self._get_project_or_raise(project_id)

        prompt_pack = self._script_service.compile_prompt_pack(
            plan=project.project_plan,
            brief=project.brief,
            quality_level=project.quality_level,
            tool_type=project.tool_type,
        )
        image_script = ImagePromptScript(
            script_id=f"{project.project_id}-image",
            shots=[
                {"shot_id": item.shot_id, "prompt": item.prompt}
                for item in prompt_pack.image_prompt_pack
            ],
        )
        video_script = VideoPromptScript(
            script_id=f"{project.project_id}-video",
            shots=[
                {"shot_id": item.shot_id, "prompt": item.prompt}
                for item in prompt_pack.video_prompt_pack
            ],
        )

        refined_script = project.selected_script
        if project.master_script:
            baseline_script = self._master_to_script(project.master_script)
            refined_script, image_script_refined, video_script_refined = (
                await self._script_service.derive_prompt_scripts(
                    brief=project.brief,
                    insight=project.insight,
                    master_script=baseline_script,
                )
            )
            refined_script = self._compliance.sanitize_script(refined_script)
            image_script = ImagePromptScript.model_validate(image_script_refined.model_dump(mode="json"))
            video_script = VideoPromptScript.model_validate(video_script_refined.model_dump(mode="json"))

        shot_approvals = dict(project.shot_approvals)
        if refined_script:
            for shot in refined_script.shots:
                shot_approvals.setdefault(shot.shot_id, ShotApprovalStatus.pending)

        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "prompt_pack", prompt_pack),
                setattr(p, "project_plan", project.project_plan),
                setattr(p, "selected_script", refined_script),
                setattr(p, "image_prompt_script", image_script),
                setattr(p, "video_prompt_script", video_script),
                setattr(p, "shot_approvals", shot_approvals),
                setattr(p, "status", ProjectStatus.scripted),
                setattr(p, "storyboard_status", StoryboardStatus.not_started),
                setattr(p, "storyboard_references", {}),
                setattr(p, "storyboard_error_message", None),
                setattr(p, "render_id", None),
                setattr(p, "error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="prompts.derived",
            message="已从主脚本派生生图与生视频提示词",
            details={
                "shot_count": len(project.project_plan.shots if project.project_plan else []),
                "force": force,
            },
        )
        return self._get_project_or_raise(project_id)

    async def generate_project_plan(
        self,
        project_id: str,
        force: bool = False,
        async_mode: bool = False,
    ) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="generate_project_plan")
        if project.project_plan and not force:
            padded = self._pad_product_image_plan(project=project, plan=project.project_plan)
            if len(padded.shots) != len(project.project_plan.shots):
                self._store.update_project(project_id, lambda p: setattr(p, "project_plan", padded))
                self._log(
                    project_id=project_id,
                    level=LogLevel.info,
                    stage="plan.padded",
                    message="项目方案镜头数已自动补齐",
                    details={"shot_count": len(padded.shots)},
                )
                return self._get_project_or_raise(project_id)
            return project
        if async_mode:
            if self._is_plan_task_running(project_id):
                return self._get_project_or_raise(project_id)
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "status", ProjectStatus.scripted if p.project_plan else ProjectStatus.draft),
                    setattr(p, "task_status", TaskRunStatus.running),
                    setattr(p, "error_message", None),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="plan.start",
                message="AI方案生成已提交，正在后台执行",
                details={"force": force},
            )
            task = asyncio.create_task(self.generate_project_plan(project_id=project_id, force=force, async_mode=False))
            self._track_background_task(self._plan_tasks, project_id, task)
            return self._get_project_or_raise(project_id)
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "task_status", TaskRunStatus.running),
                setattr(p, "error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="plan.start",
            message="开始生成AI方案",
            details={"force": force},
        )
        image_bytes = self._get_project_image_bytes(project)
        planner_hints = self._planner_execution_hints(project)
        try:
            plan = await self._script_service.generate_project_plan(
                image_bytes=image_bytes,
                image_mime=self._get_project_image_mime(project),
                brief=project.brief,
                scenario_type=project.scenario_type,
                template_name=project.template_name,
                quality_level=project.quality_level,
                tool_type=project.tool_type,
                expected_shot_count=planner_hints["expected_shot_count"],
                takes_per_shot=planner_hints["takes_per_shot"],
                target_candidate_assets=planner_hints["target_candidate_assets"],
                strict_json=True,
            )
            plan = self._pad_product_image_plan(project=project, plan=plan)
            plan = self._normalize_project_plan_delivery_purpose(
                scenario_type=project.scenario_type,
                plan=plan,
            )
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "project_plan", plan),
                    setattr(p, "status", ProjectStatus.scripted),
                    setattr(p, "task_status", TaskRunStatus.queued),
                    setattr(p, "error_message", None),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="plan.completed",
                message="项目方案生成完成",
                details={"shot_count": len(plan.shots), "force": force},
            )
        except Exception as exc:
            error_message = str(exc)
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "task_status", TaskRunStatus.failed),
                    setattr(p, "error_message", error_message),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.error,
                stage="plan.failed",
                message="项目方案生成失败",
                details={"error": error_message},
            )
            raise
        return self._get_project_or_raise(project_id)

    def update_project_plan(self, project_id: str, project_plan: ProjectPlan) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        if project_plan.scenario_type != project.scenario_type:
            raise ValueError("project plan scenario_type does not match project scenario_type")
        normalized_plan = self._normalize_project_plan_delivery_purpose(
            scenario_type=project.scenario_type,
            plan=project_plan,
        )
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "project_plan", normalized_plan),
                setattr(p, "prompt_pack", None),
                setattr(p, "image_prompt_script", None),
                setattr(p, "video_prompt_script", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="plan.updated",
            message="项目方案已人工更新",
            details={"shot_count": len(normalized_plan.shots)},
        )
        return self._get_project_or_raise(project_id)

    def _resolve_model_retouch_aspect_ratio(self, project: ProjectRecord, fallback: str) -> str:
        configured = str(project.output_aspect_ratio or "original").strip().lower()
        if configured == "original":
            return "auto"
        allowed = {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"}
        if configured in allowed:
            return configured
        return fallback

    def _apply_model_retouch_prompt_guardrails(self, project: ProjectRecord, prompt: str) -> str:
        blocks: list[str] = [
            "Core rule: keep original camera angle, framing, pose, body proportion, and original outfit silhouette.",
            "Identity rule: use identity anchor for face, hairline, body proportion, and skin tone only; do not copy anchor background, scene lighting setup, or anchor clothing.",
            "Outfit rule: keep garment category, coverage, color family, fabric behavior, and silhouette from the source image; never borrow top, bottom, or accessories from identity anchor.",
            "No extra people, no extra limbs, no aggressive crop, no shot-scale change.",
        ]
        if project.background_policy == BackgroundPolicy.keep_original:
            blocks.append("Background rule: keep original background and perspective exactly.")
        else:
            blocks.append("Background rule: background can be adjusted slightly, but perspective and scene logic must stay realistic.")
        strength_rules = {
            RetouchStrength.light: "Retouch strength: light. Only clean skin texture, micro-lighting, and detail polish.",
            RetouchStrength.medium: "Retouch strength: medium. Improve lighting and texture while preserving identity and scene.",
            RetouchStrength.heavy: "Retouch strength: heavy. Creative polish allowed, but identity and pose must remain consistent.",
        }
        blocks.append(strength_rules.get(project.retouch_strength, strength_rules[RetouchStrength.light]))
        merged = f"{prompt.strip()} {' '.join(blocks)}".strip()
        return self._script_service._cleanup_prompt_text(merged)

    async def generate_images_for_project(
        self,
        project_id: str,
        request: GenerateImagesRequest,
    ) -> tuple[ProjectRecord, list[AssetRecord], list[QualityReport]]:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="generate_images")
        if request.async_mode:
            if self._is_image_task_running(project_id):
                return (
                    self._get_project_or_raise(project_id),
                    self._store.list_assets(project_id=project_id),
                    self._store.list_quality_reports(project_id=project_id),
                )
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "status", ProjectStatus.scripted),
                    setattr(p, "storyboard_status", StoryboardStatus.generating),
                    setattr(p, "storyboard_error_message", None),
                    setattr(p, "error_message", None),
                ),
            )
            background_request = request.model_copy(update={"async_mode": False})
            task = asyncio.create_task(
                self.generate_images_for_project(
                    project_id=project_id,
                    request=background_request,
                )
            )
            self._track_background_task(self._image_tasks, project_id, task)
            return (
                self._get_project_or_raise(project_id),
                self._store.list_assets(project_id=project_id),
                self._store.list_quality_reports(project_id=project_id),
            )
        if project.scenario_type not in {
            ScenarioType.product_image_suite,
            ScenarioType.model_retouch,
            ScenarioType.multi_angle_camera,
            ScenarioType.product_video,
        }:
            raise ValueError("Unsupported scenario for image generation.")
        if not project.prompt_pack or request.regenerate:
            await self.derive_prompts(project_id=project_id, force=request.regenerate)
            project = self._get_project_or_raise(project_id)
        prompt_pack = project.prompt_pack
        if not prompt_pack or not prompt_pack.image_prompt_pack:
            raise ValueError("Image prompt pack is empty.")
        candidates_per_prompt = max(1, request.candidates_per_prompt)
        prompt_items = list(prompt_pack.image_prompt_pack)
        effective_image_aspect_ratio = request.image_aspect_ratio
        if project.tool_type == ToolType.model_retouch and prompt_items:
            # 模特精修按“单图单结果”执行：方案用于约束，不按多个修正项重复出图。
            prompt_items = [prompt_items[0]]
            prompt_items = [
                PromptItem(
                    shot_id=item.shot_id,
                    prompt=self._apply_model_retouch_prompt_guardrails(project=project, prompt=item.prompt),
                )
                for item in prompt_items
            ]
            effective_image_aspect_ratio = self._resolve_model_retouch_aspect_ratio(
                project=project,
                fallback=request.image_aspect_ratio,
            )
        expanded_prompts: list[PromptItem] = []
        for item in prompt_items:
            for candidate_index in range(candidates_per_prompt):
                expanded_shot_id = (
                    f"{item.shot_id}__v{candidate_index + 1}"
                    if candidates_per_prompt > 1
                    else item.shot_id
                )
                expanded_prompts.append(
                    PromptItem(
                        shot_id=expanded_shot_id,
                        prompt=item.prompt,
                    )
                )
        total_prompts = len(expanded_prompts)
        owner_username = self._resolve_owner_username(project)
        planned_cost_points = total_prompts * IMAGE_GENERATION_COST_PER_ASSET
        self._ensure_sufficient_points(
            username=owner_username,
            required=planned_cost_points,
            reason=f"图片生成（{total_prompts} 张）",
        )
        reference_urls, reference_paths = self._collect_reference_inputs(project)

        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="images.start",
            message="开始生成图片素材",
            details={
                "prompt_count": len(prompt_pack.image_prompt_pack),
                "effective_prompt_count": len(prompt_items),
                "candidates_per_prompt": candidates_per_prompt,
                "total_tasks": total_prompts,
                "image_aspect_ratio": effective_image_aspect_ratio,
                "image_resolution": request.image_resolution,
                "image_output_format": request.image_output_format,
                "reference_images": len(reference_urls) + len(reference_paths),
            },
        )
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "storyboard_references", {}),
                setattr(p, "storyboard_status", StoryboardStatus.generating),
                setattr(p, "task_status", TaskRunStatus.running),
                setattr(p, "storyboard_error_message", None),
                setattr(p, "error_message", None),
            ),
        )

        assets: list[AssetRecord] = []
        reports: list[QualityReport] = []
        shot_lookup = {
            shot.shot_id: shot
            for shot in (project.project_plan.shots if project.project_plan else [])
        }

        def _materialize_image_result(
            shot_id: str,
            ref: Any,
        ) -> tuple[AssetRecord, QualityReport]:
            base_shot_id, variant_index = self._split_variant_shot_id(shot_id)
            plan_shot = shot_lookup.get(base_shot_id)
            source = getattr(ref, "source", None)
            generated_success = bool(ref.image_url) and source == "generated"
            mock_placeholder = (
                self._script_service._settings.use_mock_providers
                and source == "original"
                and bool(ref.image_url or ref.local_path)
            )
            render_success = generated_success or mock_placeholder
            status = AssetStatus.ready if render_success else AssetStatus.failed
            asset = AssetRecord(
                asset_id=str(uuid4()),
                project_id=project_id,
                workspace_id=project.workspace_id,
                tool_type=project.tool_type,
                kind=AssetKind.generated_image,
                source_type=AssetSourceType.generated,
                status=status,
                created_at=utc_now(),
                updated_at=utc_now(),
                image_url=ref.image_url,
                local_path=ref.local_path,
                prompt=ref.prompt,
                tags=[
                    project.tool_type.value,
                    "generated",
                    "image",
                    base_shot_id,
                    f"v{variant_index}",
                ],
                metadata={
                    "shot_id": base_shot_id,
                    "variant_index": variant_index,
                    "source": ref.source,
                    "shot_title": plan_shot.title if plan_shot else "",
                    "shot_intent": plan_shot.intent if plan_shot else "",
                    "delivery_purpose": plan_shot.delivery_purpose if plan_shot else "",
                    "intent_summary": (
                        f"{plan_shot.title}：{plan_shot.intent}" if plan_shot else ""
                    ),
                    "marketing_copy": (
                        self._build_marketing_copy(
                            product_name=project.brief.product_name,
                            purpose=plan_shot.delivery_purpose if plan_shot else "",
                            intent=plan_shot.intent if plan_shot else "",
                            title=plan_shot.title if plan_shot else "",
                        )
                        if plan_shot
                        else ""
                    ),
                    "image_aspect_ratio": effective_image_aspect_ratio,
                    "image_resolution": request.image_resolution,
                    "image_output_format": request.image_output_format,
                    "fallback_used": not generated_success,
                    "mock_placeholder": mock_placeholder,
                },
            )
            score = 0.82 if generated_success else (0.72 if mock_placeholder else 0.35)
            report = QualityReport(
                quality_id=str(uuid4()),
                project_id=project_id,
                asset_id=asset.asset_id,
                score=score,
                clarity_score=score,
                consistency_score=score if render_success else max(0.5, score - 0.2),
                compliance_score=0.95 if render_success else 0.4,
                passed=score >= 0.7,
                issues=[] if score >= 0.7 else ["清晰度或一致性不足"],
                suggestions=[] if score >= 0.7 else ["建议重生该镜头并调整提示词"],
                created_at=utc_now(),
            )
            return asset, report

        emitted_shot_ids: set[str] = set()
        emitted_lock = asyncio.Lock()

        async def _on_item_done(shot_id: str, reference: Any) -> None:
            done_count = 0
            async with emitted_lock:
                if shot_id in emitted_shot_ids:
                    return
                emitted_shot_ids.add(shot_id)
                asset, report = _materialize_image_result(shot_id=shot_id, ref=reference)
                self._store.add_asset(asset)
                self._store.add_quality_report(report)
                assets.append(asset)
                reports.append(report)
                self._store.update_project(
                    project_id,
                    lambda p: (
                        setattr(p, "asset_ids", list(dict.fromkeys([*p.asset_ids, asset.asset_id]))),
                        setattr(
                            p,
                            "quality_report_ids",
                            list(dict.fromkeys([*p.quality_report_ids, report.quality_id])),
                        ),
                        setattr(
                            p,
                            "storyboard_references",
                            {
                                **dict(p.storyboard_references),
                                shot_id: reference,
                            },
                        ),
                        setattr(p, "storyboard_status", StoryboardStatus.generating),
                        setattr(p, "task_status", TaskRunStatus.running),
                        setattr(p, "storyboard_error_message", None),
                    ),
                )
                done_count = len(emitted_shot_ids)
            self._log(
                project_id=project_id,
                level=LogLevel.info if asset.status == AssetStatus.ready else LogLevel.warning,
                stage="images.shot.progress",
                message="单镜头图片已就绪" if asset.status == AssetStatus.ready else "单镜头生成失败，已标记可重试",
                details={
                    "shot_id": shot_id,
                    "done": done_count,
                    "total": total_prompts,
                    "source": reference.source,
                },
            )

        def _append_new_ids(existing_ids: list[str], new_ids: list[str]) -> list[str]:
            if not new_ids:
                return existing_ids
            return list(dict.fromkeys([*existing_ids, *new_ids]))

        def _merge_references(
            existing_refs: dict[str, Any],
            new_refs: dict[str, Any],
        ) -> dict[str, Any]:
            merged = dict(existing_refs)
            merged.update(new_refs)
            return merged

        references: dict[str, Any] = {}
        generation_failed = False
        try:
            references = await self._reference_image.generate_images_from_prompts(
                image_path=self._resolve_project_image_path(project),
                image_public_url=project.image_public_url,
                prompts=expanded_prompts,
                image_aspect_ratio=effective_image_aspect_ratio,
                image_resolution=request.image_resolution,
                image_output_format=request.image_output_format,
                reference_image_urls=reference_urls,
                reference_image_paths=reference_paths,
                on_item_done=_on_item_done,
            )
        except Exception:
            generation_failed = True
            raise
        finally:
            if generation_failed:
                self._store.update_project(
                    project_id,
                    lambda p: (
                        setattr(p, "storyboard_status", StoryboardStatus.failed),
                        setattr(p, "task_status", TaskRunStatus.failed),
                        setattr(p, "error_message", "图片生成失败，请查看日志后重试"),
                    ),
                )
                self._log(
                    project_id=project_id,
                    level=LogLevel.error,
                    stage="images.failed",
                    message="图片素材生成失败",
                    details={"total_tasks": total_prompts},
                )
                if project.batch_group_id:
                    self._sync_batch_stats(project.batch_group_id)

        late_assets: list[AssetRecord] = []
        late_reports: list[QualityReport] = []
        for shot_id, ref in references.items():
            if shot_id in emitted_shot_ids:
                continue
            asset, report = _materialize_image_result(shot_id=shot_id, ref=ref)
            self._store.add_asset(asset)
            self._store.add_quality_report(report)
            assets.append(asset)
            reports.append(report)
            late_assets.append(asset)
            late_reports.append(report)
            emitted_shot_ids.add(shot_id)

        prompt_by_shot_id = {item.shot_id: item.prompt for item in expanded_prompts}
        expected_shot_ids = [item.shot_id for item in expanded_prompts]
        missing_shot_ids = [shot_id for shot_id in expected_shot_ids if shot_id not in emitted_shot_ids]
        for shot_id in missing_shot_ids:
            fallback_ref = SimpleNamespace(
                source="missing",
                image_url=None,
                local_path=None,
                prompt=prompt_by_shot_id.get(shot_id) or "",
            )
            asset, report = _materialize_image_result(shot_id=shot_id, ref=fallback_ref)
            metadata = dict(asset.metadata or {})
            metadata["failure_reason"] = "provider_missing_result"
            asset = asset.model_copy(update={"metadata": metadata})
            self._store.add_asset(asset)
            self._store.add_quality_report(report)
            assets.append(asset)
            reports.append(report)
            late_assets.append(asset)
            late_reports.append(report)
            emitted_shot_ids.add(shot_id)
            self._log(
                project_id=project_id,
                level=LogLevel.warning,
                stage="images.shot.missing",
                message="镜头结果超时，已标记为失败可重试",
                details={"shot_id": shot_id},
            )

        successful_count = sum(1 for item in assets if item.status == AssetStatus.ready)
        failed_count = sum(1 for item in assets if item.status == AssetStatus.failed)
        if successful_count == 0:
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "asset_ids", _append_new_ids(p.asset_ids, [a.asset_id for a in late_assets])),
                    setattr(
                        p,
                        "quality_report_ids",
                        _append_new_ids(p.quality_report_ids, [r.quality_id for r in late_reports]),
                    ),
                    setattr(p, "storyboard_references", _merge_references(p.storyboard_references, references)),
                    setattr(p, "storyboard_status", StoryboardStatus.failed),
                    setattr(p, "task_status", TaskRunStatus.failed),
                    setattr(
                        p,
                        "error_message",
                        f"图片生成失败（0/{total_prompts} 成功），请检查模型连通性后重试",
                    ),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.error,
                stage="images.failed",
                message="图片素材生成失败",
                details={
                    "generated": successful_count,
                    "failed": failed_count,
                    "total": total_prompts,
                    "reason": "all_fallback_or_failed",
                },
            )
        else:
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "asset_ids", _append_new_ids(p.asset_ids, [a.asset_id for a in late_assets])),
                    setattr(
                        p,
                        "quality_report_ids",
                        _append_new_ids(p.quality_report_ids, [r.quality_id for r in late_reports]),
                    ),
                    setattr(p, "storyboard_references", _merge_references(p.storyboard_references, references)),
                    setattr(p, "storyboard_status", StoryboardStatus.ready),
                    setattr(p, "task_status", TaskRunStatus.reviewing),
                    setattr(
                        p,
                        "storyboard_error_message",
                        (
                            f"部分镜头生成失败（{failed_count}/{total_prompts}），可重试失败镜头"
                            if failed_count > 0
                            else None
                        ),
                    ),
                    setattr(p, "error_message", None),
                ),
            )
        self._log(
            project_id=project_id,
            level=LogLevel.warning if failed_count > 0 else LogLevel.info,
            stage="images.completed",
            message="图片素材生成完成" if successful_count > 0 else "图片素材生成失败",
            details={
                "generated": successful_count,
                "failed": failed_count,
                "candidates_per_prompt": candidates_per_prompt,
                "cost_points_plan": planned_cost_points,
            },
        )
        actual_cost_points = successful_count * IMAGE_GENERATION_COST_PER_ASSET
        if actual_cost_points > 0:
            self._charge_generation_points(
                username=owner_username,
                cost_points=actual_cost_points,
                project_id=project_id,
                note=f"图片生成扣费（{successful_count} 张）",
            )
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="images.points.charged",
                message="图片生成积分扣费完成",
                details={
                    "successful_assets": successful_count,
                    "charged_points": actual_cost_points,
                },
            )
        if project.batch_group_id:
            self._sync_batch_stats(project.batch_group_id)
        return self._get_project_or_raise(project_id), assets, reports

    async def generate_videos_for_project(
        self,
        project_id: str,
        request: GenerateVideosRequest,
    ) -> RenderResponse:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="generate_videos")
        if project.scenario_type != ScenarioType.product_video:
            raise ValueError("generate-videos only supports product_video scenario.")

        if not project.project_plan:
            await self.generate_project_plan(project_id=project_id, force=False)
            project = self._get_project_or_raise(project_id)
        if not project.prompt_pack:
            await self.derive_prompts(project_id=project_id, force=False)
            project = self._get_project_or_raise(project_id)

        if not project.selected_script:
            script = self._project_plan_to_script(project)
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "selected_script", script),
                    setattr(p, "master_script", self._script_to_master(script)),
                    setattr(
                        p,
                        "shot_approvals",
                        {shot.shot_id: ShotApprovalStatus.approved for shot in script.shots},
                    ),
                ),
            )
            project = self._get_project_or_raise(project_id)

        if not project.storyboard_references:
            await self.generate_images_for_project(
                project_id=project_id,
                request=GenerateImagesRequest(
                    regenerate=False,
                    async_mode=False,
                    candidates_per_prompt=1,
                    image_aspect_ratio="9:16" if request.video_aspect_ratio == "portrait" else "16:9",
                    image_resolution="1K",
                    image_output_format="png",
                ),
            )
            project = self._get_project_or_raise(project_id)

        if project.storyboard_status != StoryboardStatus.confirmed:
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(
                        p,
                        "shot_approvals",
                        {shot.shot_id: ShotApprovalStatus.approved for shot in p.selected_script.shots},
                    ),
                    setattr(p, "storyboard_status", StoryboardStatus.confirmed),
                ),
            )

        render_request = RenderRequest(
            variants_per_shot=request.variants_per_shot,
            preferred_variants={},
            async_mode=request.async_mode,
            video_aspect_ratio=request.video_aspect_ratio,
            video_n_frames=request.video_n_frames,
            video_size=request.video_size,
            video_remove_watermark=request.video_remove_watermark,
            video_upload_method=request.video_upload_method,
        )
        if request.async_mode:
            project_row, render_row = self.start_render_project(project_id=project_id, request=render_request)
            return RenderResponse(project=project_row, render=render_row)
        project_row, render_row = await self.render_project(project_id=project_id, request=render_request)
        self._materialize_video_assets(project_id=project_id, render=render_row)
        return RenderResponse(project=project_row, render=render_row)

    def review_asset(self, project_id: str, request: ReviewRequest) -> tuple[ProjectRecord, ReviewDecision]:
        self._get_project_or_raise(project_id)
        asset = self._store.get_asset(request.asset_id)
        if not asset or asset.project_id != project_id:
            raise ValueError("asset_id not found in project")
        if asset.source_type != AssetSourceType.generated or asset.kind not in {
            AssetKind.generated_image,
            AssetKind.generated_video,
        }:
            raise ValueError("only generated image/video assets can be reviewed")

        if request.action == ReviewAction.approve:
            new_status = AssetStatus.reviewed
        elif request.action == ReviewAction.reject:
            new_status = AssetStatus.rejected
        else:
            new_status = AssetStatus.pending

        self._store.update_asset(request.asset_id, lambda a: setattr(a, "status", new_status))
        decision = ReviewDecision(
            decision_id=str(uuid4()),
            project_id=project_id,
            asset_id=request.asset_id,
            action=request.action,
            reason=request.reason,
            reviewer="human",
            created_at=utc_now(),
        )
        self._store.add_review_decision(decision)
        self._store.update_project(
            project_id,
            lambda p: setattr(p, "review_decision_ids", [*p.review_decision_ids, decision.decision_id]),
        )
        project_assets = self._store.list_assets(project_id=project_id)
        generated_assets = [
            item
            for item in project_assets
            if item.source_type == AssetSourceType.generated
            and item.kind in {AssetKind.generated_image, AssetKind.generated_video}
        ]
        project = self._get_project_or_raise(project_id)
        reviewed_count = sum(1 for item in generated_assets if item.status == AssetStatus.reviewed)
        if project.tool_type == ToolType.product_image_suite and project.set_config:
            all_reviewed = reviewed_count >= project.set_config.target_final_count
        else:
            all_reviewed = bool(generated_assets) and reviewed_count >= len(generated_assets)
        next_task_status = TaskRunStatus.done if all_reviewed else TaskRunStatus.reviewing
        next_status = ProjectStatus.completed if all_reviewed else (
            ProjectStatus.rendering
            if project.status == ProjectStatus.rendering
            else ProjectStatus.scripted
        )
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "task_status", next_task_status),
                setattr(p, "status", next_status),
                setattr(p, "error_message", None if all_reviewed else p.error_message),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="review.updated",
            message="人工审核状态已更新",
            details={"asset_id": request.asset_id, "action": request.action.value},
        )
        if project.batch_group_id:
            self._sync_batch_stats(project.batch_group_id)
        return self._get_project_or_raise(project_id), decision

    def share_asset_to_showcase(
        self,
        project_id: str,
        asset_id: str,
        shared: bool = True,
    ) -> tuple[ProjectRecord, AssetRecord, int, int]:
        self._get_project_or_raise(project_id)
        asset = self._store.get_asset(asset_id)
        if not asset or asset.project_id != project_id:
            raise ValueError("asset_id not found in project")
        if asset.source_type != AssetSourceType.generated or asset.kind != AssetKind.generated_image:
            raise ValueError("only generated image assets can be shared")
        if asset.status != AssetStatus.reviewed:
            raise ValueError("only reviewed assets can be shared")

        metadata = dict(asset.metadata or {})
        tags = list(asset.tags or [])
        now = utc_now()
        awarded_points = 0
        already_shared = self._asset_is_showcase_shared(asset)

        if shared:
            if not already_shared:
                reward_points = self._asset_reward_points(asset)
                if reward_points <= 0:
                    daily_issued = self._daily_reward_points_issued(now)
                    project_rewarded = self._project_rewarded_share_count(project_id)
                    if (
                        project_rewarded < SHARE_REWARD_PER_PROJECT_LIMIT
                        and daily_issued < SHARE_REWARD_DAILY_LIMIT
                    ):
                        awarded_points = min(
                            SHARE_REWARD_POINTS,
                            max(0, SHARE_REWARD_DAILY_LIMIT - daily_issued),
                        )
                        if awarded_points > 0:
                            metadata["share_reward_points"] = awarded_points
                            metadata["share_reward_awarded_at"] = now.isoformat()
                metadata["showcase_shared"] = True
                metadata["showcase_shared_at"] = now.isoformat()
                if not any(tag.lower() == SHOWCASE_SHARE_TAG for tag in tags):
                    tags.append(SHOWCASE_SHARE_TAG)
            else:
                metadata["showcase_shared"] = True
                if not metadata.get("showcase_shared_at"):
                    metadata["showcase_shared_at"] = now.isoformat()
        else:
            metadata["showcase_shared"] = False
            metadata.pop("showcase_shared_at", None)
            tags = [tag for tag in tags if tag.lower() != SHOWCASE_SHARE_TAG]

        updated_asset = self._store.update_asset(
            asset_id,
            lambda a: (
                setattr(a, "metadata", metadata),
                setattr(a, "tags", tags),
            ),
        )
        if shared and awarded_points > 0:
            owner_username = self._resolve_owner_username(self._get_project_or_raise(project_id))
            self._apply_points_delta(
                username=owner_username,
                delta=awarded_points,
                kind=LedgerKind.share_reward,
                note=f"样片分享奖励（{asset_id[:8]}）",
                project_id=project_id,
                asset_id=asset_id,
            )
        total_points = self._total_share_points()
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="showcase.share.updated",
            message="样片分享状态已更新",
            details={
                "asset_id": asset_id,
                "shared": shared,
                "awarded_points": awarded_points,
                "total_points": total_points,
            },
        )
        return self._get_project_or_raise(project_id), updated_asset, awarded_points, total_points

    async def export_project_image_archive(
        self,
        *,
        project_id: str,
        scope: str = "generated",
    ) -> tuple[str, bytes]:
        project = self._get_project_or_raise(project_id)
        normalized_scope = (scope or "generated").strip().lower()
        if normalized_scope not in {"generated", "approved", "shared"}:
            raise ValueError("scope must be one of: generated, approved, shared")

        assets = self._store.list_assets(project_id=project_id)
        image_assets = [
            item
            for item in assets
            if item.source_type == AssetSourceType.generated and item.kind == AssetKind.generated_image
        ]
        if normalized_scope == "approved":
            image_assets = [item for item in image_assets if item.status == AssetStatus.reviewed]
        elif normalized_scope == "shared":
            image_assets = [item for item in image_assets if self._asset_is_showcase_shared(item)]
        else:
            image_assets = [
                item
                for item in image_assets
                if item.status in {AssetStatus.ready, AssetStatus.reviewed, AssetStatus.rejected}
            ]
        if not image_assets:
            raise ValueError("no downloadable images in current scope")

        zip_buffer = io.BytesIO()
        written = 0
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            fetch_tasks = [self._read_asset_image_bytes(asset=asset, client=client) for asset in image_assets]
            fetched = await asyncio.gather(*fetch_tasks)
            with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                for idx, (asset, image_bytes) in enumerate(zip(image_assets, fetched), start=1):
                    if not image_bytes:
                        continue
                    filename = self._build_archive_item_name(asset=asset, index=idx)
                    archive.writestr(filename, image_bytes)
                    written += 1
        if written == 0:
            raise ValueError("no downloadable images resolved")

        project_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", project.brief.product_name or "project").strip("-") or "project"
        archive_name = f"{project_name}-{normalized_scope}-{written}.zip"
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="assets.archive.generated",
            message="项目图片打包下载已生成",
            details={"scope": normalized_scope, "asset_count": written},
        )
        return archive_name, zip_buffer.getvalue()

    async def export_model_retouch_batch_archive(
        self,
        *,
        batch_group_id: str,
        scope: str = "approved",
    ) -> tuple[str, bytes]:
        normalized_scope = str(scope or "approved").strip().lower() or "approved"
        if normalized_scope not in {"generated", "approved", "shared"}:
            raise ValueError("scope must be one of: generated, approved, shared")

        projects = [
            item
            for item in self.list_projects_by_tool(tool_type=ToolType.model_retouch, limit=10000)
            if item.batch_group_id == batch_group_id
        ]
        if not projects:
            raise KeyError("batch not found")

        archive_rows: list[tuple[ProjectRecord, AssetRecord]] = []
        for project in projects:
            assets = self._store.list_assets(project_id=project.project_id)
            image_assets = [
                item
                for item in assets
                if item.source_type == AssetSourceType.generated and item.kind == AssetKind.generated_image
            ]
            if normalized_scope == "approved":
                image_assets = [item for item in image_assets if item.status == AssetStatus.reviewed]
            elif normalized_scope == "shared":
                image_assets = [item for item in image_assets if self._asset_is_showcase_shared(item)]
            else:
                image_assets = [
                    item
                    for item in image_assets
                    if item.status in {AssetStatus.ready, AssetStatus.reviewed, AssetStatus.rejected}
                ]
            archive_rows.extend((project, item) for item in image_assets)

        if not archive_rows:
            raise ValueError("no downloadable images in current scope")

        zip_buffer = io.BytesIO()
        written = 0
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            fetch_tasks = [self._read_asset_image_bytes(asset=asset, client=client) for _, asset in archive_rows]
            fetched = await asyncio.gather(*fetch_tasks)
            with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                for idx, ((project, asset), image_bytes) in enumerate(zip(archive_rows, fetched), start=1):
                    if not image_bytes:
                        continue
                    filename = self._build_batch_archive_item_name(project=project, asset=asset, index=idx)
                    archive.writestr(filename, image_bytes)
                    written += 1
        if written == 0:
            raise ValueError("no downloadable images resolved")

        first_project = projects[0]
        project_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", first_project.brief.product_name or "model-retouch").strip("-") or "model-retouch"
        archive_name = f"{project_name}-batch-{normalized_scope}-{written}.zip"
        self._log(
            project_id=first_project.project_id,
            level=LogLevel.info,
            stage="assets.archive.generated",
            message="模特批次图片打包下载已生成",
            details={"scope": normalized_scope, "asset_count": written, "batch_group_id": batch_group_id},
        )
        return archive_name, zip_buffer.getvalue()

    def _build_batch_archive_item_name(
        self,
        *,
        project: ProjectRecord,
        asset: AssetRecord,
        index: int,
    ) -> str:
        project_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5_-]+", "-", project.brief.product_name or project.project_id[:8]).strip("-") or project.project_id[:8]
        return f"{project_name}/{self._build_archive_item_name(asset=asset, index=index)}"

    async def _read_asset_image_bytes(
        self,
        *,
        asset: AssetRecord,
        client: httpx.AsyncClient,
    ) -> bytes | None:
        local_path = (asset.local_path or "").strip()
        if local_path:
            local_candidate = Path(local_path)
            if not local_candidate.is_absolute():
                candidates = [
                    self._storage_root / local_candidate,
                    self._storage_root.parent / local_candidate,
                ]
                local_candidate = next((item for item in candidates if item.exists()), local_candidate)
            if local_candidate.exists() and local_candidate.is_file():
                try:
                    return local_candidate.read_bytes()
                except Exception as exc:
                    logger.warning("Read local asset failed: %s", exc)

        image_url = (asset.image_url or "").strip()
        if image_url:
            try:
                response = await client.get(image_url)
                response.raise_for_status()
                return response.content
            except Exception as exc:
                logger.warning("Fetch remote asset failed: %s", exc)
        return None

    def _build_archive_item_name(self, *, asset: AssetRecord, index: int) -> str:
        metadata = asset.metadata or {}
        shot_id = str(metadata.get("shot_id") or f"shot-{index}").strip()
        shot_title = str(metadata.get("shot_title") or "").strip()
        shot_title = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5_-]+", "-", shot_title).strip("-")
        ext = ".png"
        path_hint = ""
        if asset.image_url:
            path_hint = urlparse(asset.image_url).path
        elif asset.local_path:
            path_hint = str(asset.local_path)
        suffix = Path(path_hint).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            ext = suffix
        if shot_title:
            return f"{index:03d}-{shot_id}-{shot_title}{ext}"
        return f"{index:03d}-{shot_id}{ext}"

    async def generate_storyboard(
        self,
        project_id: str,
        regenerate: bool = False,
    ) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="generate_storyboard")
        self._ensure_storyboard_generation_allowed(project_id=project_id, regenerate=regenerate)
        if self._is_storyboard_task_running(project_id):
            raise ValueError("Storyboard generation is already running.")
        self._mark_storyboard_generating(project_id=project_id, regenerate=regenerate)
        await self._run_storyboard_generation(project_id=project_id)
        return self._get_project_or_raise(project_id)

    def start_storyboard_generation(
        self,
        project_id: str,
        regenerate: bool = False,
    ) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="start_storyboard_generation")
        self._ensure_storyboard_generation_allowed(project_id=project_id, regenerate=regenerate)
        if self._is_storyboard_task_running(project_id):
            return self._get_project_or_raise(project_id)
        self._mark_storyboard_generating(project_id=project_id, regenerate=regenerate)
        task = asyncio.create_task(self._run_storyboard_generation(project_id=project_id))
        self._track_background_task(self._storyboard_tasks, project_id, task)
        return self._get_project_or_raise(project_id)

    async def regenerate_storyboard_shot(
        self,
        project_id: str,
        shot_id: str,
    ) -> ProjectRecord:
        self._validate_storyboard_shot(project_id=project_id, shot_id=shot_id)
        if self._is_storyboard_task_running(project_id):
            raise ValueError("Storyboard generation is already running.")
        self._mark_storyboard_shot_generating(project_id=project_id, shot_id=shot_id)
        await self._run_storyboard_shot_regeneration(project_id=project_id, shot_id=shot_id)
        return self._get_project_or_raise(project_id)

    def start_storyboard_shot_regeneration(
        self,
        project_id: str,
        shot_id: str,
    ) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="regenerate_storyboard_shot")
        self._validate_storyboard_shot(project_id=project_id, shot_id=shot_id)
        if self._is_storyboard_task_running(project_id):
            return self._get_project_or_raise(project_id)
        self._mark_storyboard_shot_generating(project_id=project_id, shot_id=shot_id)
        task = asyncio.create_task(
            self._run_storyboard_shot_regeneration(project_id=project_id, shot_id=shot_id)
        )
        self._track_background_task(self._storyboard_tasks, project_id, task)
        return self._get_project_or_raise(project_id)

    def approve_storyboard_shot(
        self,
        project_id: str,
        shot_id: str,
        status: ShotApprovalStatus,
    ) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        if not project.selected_script:
            raise ValueError("Please select a script before approving storyboard shots.")

        shot_ids = {shot.shot_id for shot in project.selected_script.shots}
        if shot_id not in shot_ids:
            raise ValueError(f"shot_id {shot_id} not found in selected script")

        if not project.storyboard_references:
            raise ValueError("Please generate storyboard before approving shots.")

        if status == ShotApprovalStatus.regenerating:
            next_storyboard_status = StoryboardStatus.generating
        else:
            next_storyboard_status = project.storyboard_status

        approvals = dict(project.shot_approvals)
        approvals[shot_id] = status

        total = len(shot_ids)
        approved_count = sum(1 for item in approvals.values() if item == ShotApprovalStatus.approved)
        refs_ready = len(project.storyboard_references) >= total
        if refs_ready and approved_count == total:
            next_storyboard_status = StoryboardStatus.confirmed
        elif next_storyboard_status == StoryboardStatus.confirmed:
            next_storyboard_status = StoryboardStatus.ready

        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "shot_approvals", approvals),
                setattr(p, "storyboard_status", next_storyboard_status),
                setattr(p, "storyboard_error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="storyboard.shot.approval",
            message="已更新镜头确认状态",
            details={
                "shot_id": shot_id,
                "status": status.value,
                "approved": approved_count,
                "total": total,
            },
        )
        return self._get_project_or_raise(project_id)

    def confirm_storyboard(self, project_id: str) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        if not project.selected_script:
            raise ValueError("Please select a script before confirming storyboard.")
        if project.storyboard_status == StoryboardStatus.generating:
            raise ValueError("Storyboard is still generating, please wait.")
        if not project.storyboard_references:
            raise ValueError("Please generate storyboard before confirming.")

        approvals = self._normalized_shot_approvals(project)
        total = len(project.selected_script.shots)
        approved_count = sum(1 for item in approvals.values() if item == ShotApprovalStatus.approved)
        if approved_count < total:
            raise ValueError(f"Please approve all storyboard shots before rendering ({approved_count}/{total}).")

        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "shot_approvals", approvals),
                setattr(p, "storyboard_status", StoryboardStatus.confirmed),
                setattr(p, "storyboard_error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="storyboard.confirmed",
            message="分镜已确认，可进入视频生成",
            details={"count": len(project.storyboard_references)},
        )
        return self._get_project_or_raise(project_id)

    async def render_project(
        self,
        project_id: str,
        request: RenderRequest,
    ) -> tuple[ProjectRecord, RenderRecord]:
        if self._is_render_task_running(project_id):
            raise ValueError("Render task is already running.")
        project, render = self._prepare_render(project_id=project_id, request=request)
        await self._run_render_pipeline(project_id=project_id, render_id=render.render_id, request=request)
        final_render = self.get_render(render.render_id)
        if not final_render:
            raise KeyError(f"render_id {render.render_id} not found")
        return self._get_project_or_raise(project_id), final_render

    def start_render_project(
        self,
        project_id: str,
        request: RenderRequest,
    ) -> tuple[ProjectRecord, RenderRecord]:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="start_render_project")
        if self._is_render_task_running(project_id):
            project = self._get_project_or_raise(project_id)
            if not project.render_id:
                raise ValueError("Render task is already running.")
            current = self.get_render(project.render_id)
            if not current:
                raise ValueError("Render task is already running.")
            return project, current

        project, render = self._prepare_render(project_id=project_id, request=request)
        task = asyncio.create_task(
            self._run_render_pipeline(
                project_id=project_id,
                render_id=render.render_id,
                request=request,
            )
        )
        self._track_background_task(self._render_tasks, project_id, task)
        return project, render

    def _prepare_render(
        self,
        project_id: str,
        request: RenderRequest,
    ) -> tuple[ProjectRecord, RenderRecord]:
        project = self._get_project_or_raise(project_id)
        if not project.selected_script:
            raise ValueError("Please select a script before rendering.")
        if project.storyboard_status != StoryboardStatus.confirmed:
            raise ValueError("Please approve all storyboard shots before rendering.")
        if not project.storyboard_references:
            raise ValueError("Storyboard references are missing.")

        approvals = self._normalized_shot_approvals(project)
        total_shots = len(project.selected_script.shots)
        approved_count = sum(1 for item in approvals.values() if item == ShotApprovalStatus.approved)
        if approved_count < total_shots:
            raise ValueError(f"Please approve all storyboard shots before rendering ({approved_count}/{total_shots}).")

        render_id = str(uuid4())
        now = utc_now()
        total_variants = len(project.selected_script.shots) * request.variants_per_shot
        owner_username = self._resolve_owner_username(project)
        planned_cost_points = total_variants * VIDEO_GENERATION_COST_PER_VARIANT
        self._ensure_sufficient_points(
            username=owner_username,
            required=planned_cost_points,
            reason=f"视频生成（{total_variants} 条候选）",
        )
        render = RenderRecord(
            render_id=render_id,
            project_id=project_id,
            status=ProjectStatus.rendering,
            created_at=now,
            updated_at=now,
            total_variants=total_variants,
            completed_variants=0,
            failed_variants=0,
            running_variants=total_variants,
        )
        self._store.add_render(render)
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="render.start",
            message="开始渲染任务",
            details={
                "render_id": render_id,
                "variants_per_shot": request.variants_per_shot,
                "total_variants": total_variants,
                "cost_points_plan": planned_cost_points,
                "video_aspect_ratio": request.video_aspect_ratio,
                "video_n_frames": request.video_n_frames,
                "video_size": request.video_size,
            },
            render_id=render_id,
        )
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "status", ProjectStatus.rendering),
                setattr(p, "task_status", TaskRunStatus.running),
                setattr(p, "render_id", render_id),
                setattr(p, "error_message", None),
            ),
        )
        return self._get_project_or_raise(project_id), render

    async def _run_render_pipeline(
        self,
        project_id: str,
        render_id: str,
        request: RenderRequest,
    ) -> None:
        project = self._get_project_or_raise(project_id)
        try:
            references = project.storyboard_references
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="render.references.ready",
                message="参考图准备完成",
                details={"count": len(references)},
                render_id=render_id,
            )

            async def _on_variant_done(clip: Any, progress: dict[str, int]) -> None:
                def _apply_variant_progress(record: RenderRecord) -> None:
                    variants = {key: list(value) for key, value in record.variants.items()}
                    existing = [
                        item
                        for item in variants.get(clip.shot_id, [])
                        if item.variant_index != clip.variant_index
                    ]
                    existing.append(clip)
                    existing.sort(key=lambda item: item.variant_index)
                    variants[clip.shot_id] = existing
                    record.variants = variants
                    record.total_variants = progress.get("total", record.total_variants)
                    record.completed_variants = progress.get("done", record.completed_variants)
                    record.failed_variants = progress.get("failed", record.failed_variants)
                    record.running_variants = progress.get("running", record.running_variants)

                self._store.update_render(render_id, _apply_variant_progress)
                self._log(
                    project_id=project_id,
                    level=LogLevel.info,
                    stage="render.variant.progress",
                    message="视频候选进度更新",
                    details={
                        "shot_id": getattr(clip, "shot_id", ""),
                        "variant_index": getattr(clip, "variant_index", 0),
                        "done": progress.get("done", 0),
                        "total": progress.get("total", 0),
                        "failed": progress.get("failed", 0),
                    },
                    render_id=render_id,
                )

            variants, image_public_url = await self._sora.generate_variants(
                project_id=project_id,
                image_path=self._resolve_project_image_path(project),
                image_public_url=project.image_public_url,
                shots=project.selected_script.shots,
                variants_per_shot=request.variants_per_shot,
                references=references,
                video_aspect_ratio=request.video_aspect_ratio,
                video_n_frames=request.video_n_frames,
                video_size=request.video_size,
                video_remove_watermark=request.video_remove_watermark,
                video_upload_method=request.video_upload_method,
                on_variant_done=_on_variant_done,
            )
            total_variants = sum(len(items) for items in variants.values())
            live_task_variants = sum(1 for items in variants.values() for clip in items if clip.task_id)
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="render.variants.ready",
                message="视频候选生成完成",
                details={
                    "total_variants": total_variants,
                    "live_task_variants": live_task_variants,
                    "fallback_to_mock": live_task_variants == 0,
                },
                render_id=render_id,
            )

            chosen = self._assembly.choose_variants(
                script=project.selected_script,
                variants=variants,
                preferred=request.preferred_variants,
            )
            output_video_path, subtitle_path, assembly_note = self._assembly.assemble_video(
                project_id=project_id,
                chosen=chosen,
                script=project.selected_script,
            )

            self._store.update_render(
                render_id,
                lambda r: (
                    setattr(r, "variants", variants),
                    setattr(r, "references", references),
                    setattr(r, "chosen_variants", chosen),
                    setattr(r, "status", ProjectStatus.completed),
                    setattr(r, "completed_variants", total_variants),
                    setattr(r, "running_variants", 0),
                    setattr(
                        r,
                        "output_video_path",
                        str(output_video_path) if output_video_path else None,
                    ),
                    setattr(r, "subtitle_path", str(subtitle_path)),
                    setattr(
                        r,
                        "manifest_path",
                        str((self._storage_root / "renders" / project_id / "render_manifest.json")),
                    ),
                    setattr(r, "assembly_note", assembly_note),
                    setattr(r, "error_message", None),
                ),
            )

            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "status", ProjectStatus.scripted),
                    setattr(p, "task_status", TaskRunStatus.reviewing),
                    setattr(p, "image_public_url", image_public_url),
                    setattr(p, "error_message", None),
                ),
            )
            completed_variants = sum(
                1
                for rows in variants.values()
                for clip in rows
                if bool(getattr(clip, "video_url", None) or getattr(clip, "local_path", None))
            )
            actual_cost_points = completed_variants * VIDEO_GENERATION_COST_PER_VARIANT
            if actual_cost_points > 0:
                owner_username = self._resolve_owner_username(project)
                self._charge_generation_points(
                    username=owner_username,
                    cost_points=actual_cost_points,
                    project_id=project_id,
                    note=f"视频生成扣费（{completed_variants} 条候选）",
                )
                self._log(
                    project_id=project_id,
                    level=LogLevel.info,
                    stage="render.points.charged",
                    message="视频生成积分扣费完成",
                    details={
                        "completed_variants": completed_variants,
                        "charged_points": actual_cost_points,
                    },
                    render_id=render_id,
                )
            current_render = self.get_render(render_id)
            if current_render:
                self._materialize_video_assets(project_id=project_id, render=current_render)
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="render.completed",
                message="渲染完成",
                details={
                    "has_final_video": bool(output_video_path),
                    "subtitle_path": str(subtitle_path),
                    "local_assembly_enabled": self._assembly.local_assembly_enabled,
                },
                render_id=render_id,
            )
        except Exception as exc:
            error_message = str(exc)
            self._store.update_render(
                render_id,
                lambda r: (
                    setattr(r, "status", ProjectStatus.failed),
                    setattr(r, "running_variants", 0),
                    setattr(r, "error_message", error_message),
                ),
            )
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "status", ProjectStatus.failed),
                    setattr(p, "task_status", TaskRunStatus.failed),
                    setattr(p, "error_message", error_message),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.error,
                stage="render.failed",
                message="渲染失败",
                details={"error": error_message},
                render_id=render_id,
            )
            raise

    def _ensure_storyboard_generation_allowed(self, project_id: str, regenerate: bool) -> None:
        project = self._get_project_or_raise(project_id)
        if not project.master_script and not project.selected_script:
            raise ValueError("Please select a script before generating storyboard.")
        if (
            project.storyboard_status == StoryboardStatus.confirmed
            and project.storyboard_references
            and not regenerate
        ):
            raise ValueError("Storyboard already confirmed. Use regenerate to rebuild it.")

    def _validate_storyboard_shot(self, project_id: str, shot_id: str) -> None:
        project = self._get_project_or_raise(project_id)
        script = project.selected_script
        if not script:
            raise ValueError("Please select a script before regenerating storyboard shot.")
        shot_ids = {shot.shot_id for shot in script.shots}
        if shot_id not in shot_ids:
            raise ValueError(f"shot_id {shot_id} not found in selected script")

    def _mark_storyboard_generating(self, project_id: str, regenerate: bool) -> None:
        project = self._get_project_or_raise(project_id)
        approvals = self._normalized_shot_approvals(project)
        if regenerate:
            approvals = {key: ShotApprovalStatus.pending for key in approvals}

        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "status", ProjectStatus.scripted),
                setattr(p, "storyboard_status", StoryboardStatus.generating),
                setattr(p, "storyboard_error_message", None),
                setattr(p, "shot_approvals", approvals),
                setattr(p, "render_id", None),
                setattr(p, "error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="storyboard.start",
            message="开始生成分镜图片",
            details={"regenerate": regenerate},
        )

    def _mark_storyboard_shot_generating(self, project_id: str, shot_id: str) -> None:
        project = self._get_project_or_raise(project_id)
        approvals = self._normalized_shot_approvals(project)
        approvals[shot_id] = ShotApprovalStatus.regenerating

        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "status", ProjectStatus.scripted),
                setattr(p, "storyboard_status", StoryboardStatus.generating),
                setattr(p, "storyboard_error_message", None),
                setattr(p, "shot_approvals", approvals),
                setattr(p, "render_id", None),
                setattr(p, "error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="storyboard.shot.start",
            message="开始重生成单镜头分镜图",
            details={"shot_id": shot_id},
        )

    async def _run_storyboard_generation(self, project_id: str) -> None:
        project = await self._prepare_generation_script(project_id)
        try:
            script = project.selected_script
            if not script:
                raise ValueError("Please select a script before generation.")
            total_shots = len(script.shots)

            async def _on_shot_done(shot_id: str, reference: Any) -> None:
                updated = self._store.update_project(
                    project_id,
                    lambda p: (
                        setattr(
                            p,
                            "storyboard_references",
                            {
                                **dict(p.storyboard_references),
                                shot_id: reference,
                            },
                        ),
                        setattr(p, "storyboard_status", StoryboardStatus.generating),
                        setattr(p, "storyboard_error_message", None),
                    ),
                )
                done_count = len(updated.storyboard_references)
                self._log(
                    project_id=project_id,
                    level=LogLevel.info,
                    stage="storyboard.shot.progress",
                    message="单镜头分镜图已就绪",
                    details={
                        "shot_id": shot_id,
                        "done": done_count,
                        "total": total_shots,
                        "source": getattr(reference, "source", "unknown"),
                    },
                )

            references = await self._reference_image.generate_storyboard(
                project_id=project_id,
                image_path=self._resolve_project_image_path(project),
                image_public_url=project.image_public_url,
                script=script,
                on_shot_done=_on_shot_done,
            )
            generated_count = sum(1 for item in references.values() if item.source == "generated")
            approvals = self._normalized_shot_approvals(project)
            for shot_id in references:
                if approvals.get(shot_id) == ShotApprovalStatus.regenerating:
                    approvals[shot_id] = ShotApprovalStatus.pending
                approvals.setdefault(shot_id, ShotApprovalStatus.pending)

            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "storyboard_references", references),
                    setattr(p, "shot_approvals", approvals),
                    setattr(p, "storyboard_status", StoryboardStatus.ready),
                    setattr(p, "storyboard_error_message", None),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="storyboard.completed",
                message="分镜图片生成完成",
                details={
                    "total": len(references),
                    "generated": generated_count,
                    "fallback_original": len(references) - generated_count,
                },
            )
        except Exception as exc:
            error_message = str(exc)
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "storyboard_status", StoryboardStatus.failed),
                    setattr(p, "storyboard_error_message", error_message),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.error,
                stage="storyboard.failed",
                message="分镜图片生成失败",
                details={"error": error_message},
            )
            raise

    async def _run_storyboard_shot_regeneration(self, project_id: str, shot_id: str) -> None:
        project = await self._prepare_generation_script(project_id)
        if not project.selected_script:
            raise ValueError("Please select a script before regenerating storyboard shot.")
        shot = next((item for item in project.selected_script.shots if item.shot_id == shot_id), None)
        if not shot:
            raise ValueError(f"shot_id {shot_id} not found in selected script")
        try:
            reference = await self._reference_image.generate_storyboard_shot(
                image_path=self._resolve_project_image_path(project),
                image_public_url=project.image_public_url,
                shot=shot,
            )
            existing = dict(project.storyboard_references)
            existing[shot_id] = reference
            approvals = self._normalized_shot_approvals(project)
            approvals[shot_id] = ShotApprovalStatus.pending
            generated_count = sum(1 for item in existing.values() if item.source == "generated")
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "storyboard_references", existing),
                    setattr(p, "shot_approvals", approvals),
                    setattr(p, "storyboard_status", StoryboardStatus.ready),
                    setattr(p, "storyboard_error_message", None),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="storyboard.shot.completed",
                message="单镜头分镜图重生成完成",
                details={
                    "shot_id": shot_id,
                    "source": reference.source,
                    "generated_total": generated_count,
                },
            )
        except Exception as exc:
            error_message = str(exc)
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "storyboard_status", StoryboardStatus.failed),
                    setattr(p, "storyboard_error_message", error_message),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.error,
                stage="storyboard.shot.failed",
                message="单镜头分镜图重生成失败",
                details={"shot_id": shot_id, "error": error_message},
            )
            raise

    async def _prepare_generation_script(self, project_id: str) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        if not project.selected_script:
            if project.master_script:
                self._store.update_project(
                    project_id,
                    lambda p: setattr(p, "selected_script", self._master_to_script(project.master_script)),
                )
            else:
                raise ValueError("Please select a script before generation.")
        project = self._get_project_or_raise(project_id)
        if self._script_has_generation_fields(project.selected_script):
            return project

        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="vl.shot_plan.start",
            message="开始用AI细化分镜与视频生成参数",
            details={"script_id": project.selected_script.script_id},
        )
        refined = await self._script_service.refine_script_for_generation(
            brief=project.brief,
            insight=project.insight,
            script=project.selected_script,
        )
        image_script, video_script = self._build_derived_scripts(refined)
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "selected_script", refined),
                setattr(p, "image_prompt_script", image_script),
                setattr(p, "video_prompt_script", video_script),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="vl.shot_plan.completed",
            message="AI细化完成，已更新镜头参数",
            details={"shot_count": len(refined.shots)},
        )
        return self._get_project_or_raise(project_id)

    def _script_has_generation_fields(self, script: ScriptOption | None) -> bool:
        if not script:
            return False
        for shot in script.shots:
            if not getattr(shot, "reference_image_prompt", None):
                return False
            if not getattr(shot, "visual_prompt", None):
                return False
            if not getattr(shot, "motion_direction", None):
                return False
            if not getattr(shot, "voiceover_direction", None):
                return False
        return True

    def _normalized_shot_approvals(self, project: ProjectRecord) -> dict[str, ShotApprovalStatus]:
        approvals = dict(project.shot_approvals)
        script = project.selected_script
        if not script:
            return approvals
        for shot in script.shots:
            approvals.setdefault(shot.shot_id, ShotApprovalStatus.pending)
        return approvals

    def get_project_progress(self, project_id: str) -> ProjectProgress:
        project = self._get_project_or_raise(project_id)
        render = self.get_render(project.render_id) if project.render_id else None
        plan_ready = project.project_plan is not None
        prompts_ready = project.prompt_pack is not None
        assets = self._store.list_assets(project_id)
        generated_assets = sum(
            1
            for item in assets
            if item.kind in {AssetKind.generated_image, AssetKind.generated_video}
            and item.status in {AssetStatus.ready, AssetStatus.reviewed}
        )
        candidate_total = sum(
            1
            for item in assets
            if item.kind == AssetKind.generated_image
            and item.source_type == AssetSourceType.generated
            and item.status in {AssetStatus.ready, AssetStatus.reviewed, AssetStatus.rejected, AssetStatus.failed}
        )
        reviewed_assets = sum(
            1
            for item in assets
            if item.kind in {AssetKind.generated_image, AssetKind.generated_video}
            and item.source_type == AssetSourceType.generated
            and item.status == AssetStatus.reviewed
        )
        required_final_count = (
            project.set_config.target_final_count
            if project.tool_type == ToolType.product_image_suite and project.set_config
            else 0
        )
        selected_final_count = reviewed_assets
        script_selected = bool(project.master_script or project.selected_script)
        storyboard_total = len(project.selected_script.shots) if project.selected_script else 0
        if storyboard_total == 0 and project.project_plan:
            storyboard_total = len(project.project_plan.shots)
        storyboard_done = len(project.storyboard_references)
        approvals = self._normalized_shot_approvals(project)
        approved = sum(1 for item in approvals.values() if item == ShotApprovalStatus.approved)

        render_total = render.total_variants if render else 0
        render_done = render.completed_variants if render else 0
        render_failed = render.failed_variants if render else 0
        render_running = render.running_variants if render else 0
        batch_done = project.batch_stats.done_images if project.batch_stats else 0
        batch_failed = project.batch_stats.failed_images if project.batch_stats else 0
        failed_stage = self._detect_failed_stage(project=project, render=render)

        if project.scenario_type == ScenarioType.product_video:
            step_weights = {
                "master_script": 15,
                "plan": 15,
                "prompt": 10,
                "storyboard": 20,
                "render": 30,
                "review": 10,
            }
            storyboard_target = max(storyboard_total, 1)
            render_target = max(render_total, 1)
            review_target = max(generated_assets, 1)
            steps = [
                ProgressStep(
                    step_id="master_script",
                    label="主脚本",
                    status=self._resolve_step_status("completed" if script_selected else "pending", "master_script", failed_stage),
                    completed=1 if script_selected else 0,
                    total=1,
                    weight=step_weights["master_script"],
                    entry_criteria="项目创建成功",
                    done_criteria="已确认并落地一套主拍摄脚本",
                    error_code=self._step_error_code("master_script", failed_stage),
                ),
                ProgressStep(
                    step_id="plan",
                    label="AI方案",
                    status=self._resolve_step_status("completed" if plan_ready else "pending", "plan", failed_stage),
                    completed=1 if plan_ready else 0,
                    total=1,
                    weight=step_weights["plan"],
                    entry_criteria="主脚本已选定",
                    done_criteria="VL返回结构化镜头方案并通过schema校验",
                    error_code=self._step_error_code("plan", failed_stage),
                ),
                ProgressStep(
                    step_id="prompt",
                    label="提示词编译",
                    status=self._resolve_step_status("completed" if prompts_ready else "pending", "prompt", failed_stage),
                    completed=1 if prompts_ready else 0,
                    total=1,
                    weight=step_weights["prompt"],
                    entry_criteria="AI方案可用",
                    done_criteria="生图/生视频提示词包生成完成",
                    error_code=self._step_error_code("prompt", failed_stage),
                ),
                ProgressStep(
                    step_id="storyboard",
                    label="关键帧/分镜",
                    status=self._resolve_step_status(self._map_storyboard_status(project.storyboard_status), "storyboard", failed_stage),
                    completed=min(approved, storyboard_target),
                    total=storyboard_target,
                    weight=step_weights["storyboard"],
                    entry_criteria="提示词包已生成",
                    done_criteria="全部镜头已通过分镜确认",
                    error_code=self._step_error_code("storyboard", failed_stage),
                ),
                ProgressStep(
                    step_id="render",
                    label="15秒视频生成",
                    status=self._resolve_step_status(
                        "failed"
                        if render and render.status == ProjectStatus.failed
                        else "completed"
                        if render and render.status == ProjectStatus.completed
                        else "in_progress"
                        if render and render.status == ProjectStatus.rendering
                        else "pending",
                        "render",
                        failed_stage,
                    ),
                    completed=min(render_done, render_target),
                    total=render_target,
                    weight=step_weights["render"],
                    entry_criteria="分镜全部通过",
                    done_criteria="候选视频全部生成完成",
                    error_code=self._step_error_code("render", failed_stage),
                ),
                ProgressStep(
                    step_id="review",
                    label="人工确认",
                    status=self._resolve_step_status(
                        "completed" if generated_assets > 0 and reviewed_assets >= generated_assets else "in_progress" if reviewed_assets > 0 else "pending",
                        "review",
                        failed_stage,
                    ),
                    completed=min(reviewed_assets, review_target),
                    total=review_target,
                    weight=step_weights["review"],
                    entry_criteria="生成结果可用",
                    done_criteria="全部候选片段人工审核通过",
                    error_code=self._step_error_code("review", failed_stage),
                ),
            ]
            progress_profile = "video_weighted"
            completion_criteria = "全部候选视频生成完成，且人工审核全部通过后才算完成"
        else:
            if project.tool_type == ToolType.multi_angle_camera:
                step_weights = {
                    "plan": 35,
                    "generate": 45,
                    "review": 20,
                }
                if project.tool_type == ToolType.model_retouch:
                    planned_assets = 1 if project.project_plan and project.project_plan.shots else 0
                else:
                    planned_assets = len(project.project_plan.shots) if project.project_plan else 0
                target_assets = max(planned_assets, generated_assets, 1)
                steps = [
                    ProgressStep(
                        step_id="plan",
                        label="机位方案",
                        status=self._resolve_step_status("completed" if plan_ready else "pending", "plan", failed_stage),
                        completed=1 if plan_ready else 0,
                        total=1,
                        weight=step_weights["plan"],
                        entry_criteria="项目创建成功",
                        done_criteria="机位参数已保存并生成角度方案",
                        error_code=self._step_error_code("plan", failed_stage),
                    ),
                    ProgressStep(
                        step_id="generate",
                        label="生成当前角度",
                        status=self._resolve_step_status(
                            "completed"
                            if generated_assets >= target_assets
                            else "in_progress"
                            if generated_assets > 0
                            else "pending",
                            "generate",
                            failed_stage,
                        ),
                        completed=min(generated_assets, target_assets),
                        total=target_assets,
                        weight=step_weights["generate"],
                        entry_criteria="机位方案已确认",
                        done_criteria="当前机位素材生成完成，可继续切角度追加生成",
                        error_code=self._step_error_code("generate", failed_stage),
                    ),
                    ProgressStep(
                        step_id="review",
                        label="人工确认",
                        status=self._resolve_step_status(
                            "completed" if reviewed_assets >= target_assets else "in_progress" if reviewed_assets > 0 else "pending",
                            "review",
                            failed_stage,
                        ),
                        completed=min(reviewed_assets, target_assets),
                        total=target_assets,
                        weight=step_weights["review"],
                        entry_criteria="已有可审核生成素材",
                        done_criteria="目标素材人工审核全部通过",
                        error_code=self._step_error_code("review", failed_stage),
                    ),
                ]
                progress_profile = "image_weighted"
                completion_criteria = "每次生成一张当前机位图，人工审核通过后可继续切角度追加"
            else:
                with_identity_step = project.tool_type == ToolType.model_retouch and project.identity_required
                is_product_set = (
                    project.tool_type == ToolType.product_image_suite
                    and project.workflow_mode == WorkflowMode.product_set
                    and project.set_config is not None
                )
                if with_identity_step:
                    step_weights = {
                        "plan": 20,
                        "prompt": 10,
                        "identity": 20,
                        "generate": 35,
                        "review": 15,
                    }
                else:
                    step_weights = {
                        "plan": 20,
                        "prompt": 10,
                        "generate": 50,
                        "review": 20,
                    }
                planned_assets = len(project.project_plan.shots) if project.project_plan else 0
                required_candidates = (
                    project.set_config.required_min_candidates if is_product_set and project.set_config else 0
                )
                target_assets = max(planned_assets, generated_assets, required_candidates, 1)
                review_target = (
                    project.set_config.target_final_count if is_product_set and project.set_config else target_assets
                )
                identity_completed = (
                    not with_identity_step or project.identity_status == IdentityStatus.confirmed
                )
                identity_status = (
                    "completed"
                    if identity_completed
                    else "in_progress"
                    if project.identity_asset_id
                    else "pending"
                )
                steps = [
                    ProgressStep(
                        step_id="plan",
                        label="AI方案",
                        status=self._resolve_step_status("completed" if plan_ready else "pending", "plan", failed_stage),
                        completed=1 if plan_ready else 0,
                        total=1,
                        weight=step_weights["plan"],
                        entry_criteria="项目创建成功",
                        done_criteria="VL返回结构化图像执行方案",
                        error_code=self._step_error_code("plan", failed_stage),
                    ),
                    ProgressStep(
                        step_id="prompt",
                        label="提示词编译",
                        status=self._resolve_step_status("completed" if prompts_ready else "pending", "prompt", failed_stage),
                        completed=1 if prompts_ready else 0,
                        total=1,
                        weight=step_weights["prompt"],
                        entry_criteria="AI方案可用",
                        done_criteria="生图提示词包生成完成",
                        error_code=self._step_error_code("prompt", failed_stage),
                    ),
                ]
                if with_identity_step:
                    steps.append(
                        ProgressStep(
                            step_id="identity",
                            label="身份确认",
                            status=self._resolve_step_status(identity_status, "identity", failed_stage),
                            completed=1 if identity_completed else 0,
                            total=1,
                            weight=step_weights["identity"],
                            entry_criteria="提示词包已生成",
                            done_criteria="替换模特身份图已确认并锁定",
                            error_code=self._step_error_code("identity", failed_stage),
                        )
                    )
                steps.extend(
                    [
                        ProgressStep(
                        step_id="generate",
                        label="开始试拍" if is_product_set else "图像生成",
                        status=self._resolve_step_status(
                            "completed"
                            if generated_assets >= target_assets
                            else "in_progress"
                            if generated_assets > 0
                            else "pending",
                            "generate",
                            failed_stage,
                        ),
                        completed=min(generated_assets, target_assets),
                        total=target_assets,
                        weight=step_weights["generate"],
                        entry_criteria="提示词包已生成" if not with_identity_step else "身份图已确认",
                        done_criteria=(
                            "达到试拍候选数量，可进入选片定稿"
                            if is_product_set
                            else "目标素材全部生成完成"
                        ),
                        error_code=self._step_error_code("generate", failed_stage),
                    ),
                    ProgressStep(
                        step_id="review",
                        label="选片定稿" if is_product_set else "人工确认",
                        status=self._resolve_step_status(
                            "completed"
                            if reviewed_assets >= review_target
                            else "in_progress"
                            if reviewed_assets > 0
                            else "pending",
                            "review",
                            failed_stage,
                        ),
                        completed=min(reviewed_assets, review_target),
                        total=review_target,
                        weight=step_weights["review"],
                        entry_criteria="已有可审核生成素材",
                        done_criteria=(
                            "已达到目标成片数，可提交交付"
                            if is_product_set
                            else "目标素材人工审核全部通过"
                        ),
                        error_code=self._step_error_code("review", failed_stage),
                    ),
                    ]
                )
                progress_profile = "image_weighted"
                completion_criteria = (
                    "先完成试拍候选，再达到目标成片数后才算完成"
                    if is_product_set
                    else "目标素材全部生成完成，且人工审核全部通过后才算完成"
                )

        progress_percent_weighted = self._compute_weighted_percent(steps)
        current_stage = next((step.step_id for step in steps if step.status != "completed"), "completed")
        if failed_stage:
            current_stage = "failed"
        elif progress_percent_weighted >= 100:
            current_stage = "completed"
        next_action = self._build_next_action_hint(
            project=project,
            current_stage=current_stage,
            plan_ready=plan_ready,
            prompts_ready=prompts_ready,
            script_selected=script_selected,
            storyboard_done=storyboard_done,
            storyboard_total=storyboard_total,
            reviewed_assets=reviewed_assets,
            generated_assets=generated_assets,
        )

        return ProjectProgress(
            project_id=project.project_id,
            status=project.status,
            task_status=self._effective_task_status(project),
            storyboard_status=project.storyboard_status,
            current_stage=current_stage,
            next_action=next_action,
            steps=steps,
            plan_ready=plan_ready,
            prompts_ready=prompts_ready,
            generated_assets=generated_assets,
            reviewed_assets=reviewed_assets,
            storyboard_done=storyboard_done,
            storyboard_total=storyboard_total,
            approved_shots=approved,
            total_shots=storyboard_total,
            render_completed=render_done,
            render_total=render_total,
            render_failed=render_failed,
            render_running=render_running,
            selected_final_count=selected_final_count,
            required_final_count=required_final_count,
            candidate_total=candidate_total,
            batch_done=batch_done,
            batch_failed=batch_failed,
            progress_percent_weighted=progress_percent_weighted,
            progress_profile=progress_profile,
            step_weights=step_weights,
            completion_criteria=completion_criteria,
            updated_at=project.updated_at,
            render_id=project.render_id,
        )

    def _compute_weighted_percent(self, steps: list[ProgressStep]) -> int:
        total_weight = sum(max(step.weight, 0) for step in steps)
        if total_weight <= 0:
            return 0
        score = 0.0
        for step in steps:
            denominator = max(step.total, 1)
            ratio = min(max(step.completed / denominator, 0.0), 1.0)
            score += ratio * max(step.weight, 0)
        return max(0, min(100, int(round((score / total_weight) * 100))))

    def _resolve_step_status(self, base_status: str, step_id: str, failed_stage: str | None) -> str:
        if failed_stage and failed_stage == step_id:
            return "failed"
        return base_status

    def _step_error_code(self, step_id: str, failed_stage: str | None) -> str | None:
        if failed_stage != step_id:
            return None
        mapping = {
            "plan": "PLAN_FAILED",
            "prompt": "PROMPT_COMPILE_FAILED",
            "identity": "IDENTITY_CONFIRM_FAILED",
            "generate": "IMAGE_GENERATION_FAILED",
            "storyboard": "STORYBOARD_FAILED",
            "render": "VIDEO_RENDER_FAILED",
            "review": "REVIEW_GATE_BLOCKED",
            "master_script": "MASTER_SCRIPT_FAILED",
        }
        return mapping.get(step_id, "PROJECT_FAILED")

    def _detect_failed_stage(self, project: ProjectRecord, render: RenderRecord | None) -> str | None:
        if render and render.status == ProjectStatus.failed:
            return "render"
        if project.storyboard_status == StoryboardStatus.failed:
            return "storyboard" if project.scenario_type == ScenarioType.product_video else "generate"
        if project.status != ProjectStatus.failed and project.task_status != TaskRunStatus.failed:
            return None
        if not project.project_plan:
            return "plan"
        if not project.prompt_pack:
            return "prompt"
        if project.scenario_type == ScenarioType.product_video:
            if project.storyboard_status in {StoryboardStatus.not_started, StoryboardStatus.generating, StoryboardStatus.ready}:
                return "storyboard"
            return "render"
        if project.tool_type == ToolType.multi_angle_camera:
            if not project.project_plan:
                return "plan"
            return "generate"
        return "generate"

    def _build_next_action_hint(
        self,
        project: ProjectRecord,
        current_stage: str,
        plan_ready: bool,
        prompts_ready: bool,
        script_selected: bool,
        storyboard_done: int,
        storyboard_total: int,
        reviewed_assets: int,
        generated_assets: int,
    ) -> str:
        if project.status == ProjectStatus.failed:
            return f"当前流程失败，请先查看日志并重试失败步骤：{project.error_message or '未知错误'}"

        tool = project.tool_type
        if tool == ToolType.intro_video_multi_script:
            if not plan_ready and self._is_plan_task_running(project.project_id):
                return "AI方案生成中，请稍候自动刷新。"
            if not script_selected:
                if not plan_ready:
                    return "先点击“生成AI方案”，获取脚本方案后在 Step2 选择主脚本。"
                return "先在 Step2 选择一套主脚本，再继续生成分镜。"
            if not plan_ready:
                return "先点击“生成AI方案”，确认镜头规划。"
            if not prompts_ready:
                return "先点击“编译提示词”，生成生图/生视频执行提示词。"
            if storyboard_total and storyboard_done < storyboard_total:
                return f"请继续生成并确认分镜（{storyboard_done}/{storyboard_total}）。"
            if project.storyboard_status != StoryboardStatus.confirmed:
                return "请先完成全部分镜通过，再进入视频生成。"
            if project.render_id and project.status == ProjectStatus.rendering:
                return "视频生成进行中，可在当前页查看进度并等待候选结果。"
            if project.render_id and generated_assets > 0 and reviewed_assets < generated_assets:
                return f"请在 Step4 完成人工选片（{reviewed_assets}/{generated_assets}）。"
            return "可以开始生成视频候选并进入人工选片。"

        if tool == ToolType.model_retouch:
            if not plan_ready and self._is_plan_task_running(project.project_id):
                return "精修方案生成中，请稍候自动刷新。"
            if not plan_ready:
                return "先点击“生成精修方案”，输出批次精修约束。"
            if not prompts_ready:
                return "先点击“编译提示词”，确认单图精修指令。"
            if project.identity_required and project.identity_status != IdentityStatus.confirmed:
                return "请先在 Step3 完成替换身份确认，再执行批量精修。"
            if generated_assets == 0:
                return "点击“开始精修”，按单图任务生成第一批候选。"
            if reviewed_assets < generated_assets:
                return f"Step5 可继续逐图定稿（已通过 {reviewed_assets}/{generated_assets}）。"
            return "批次精修已完成，可继续创建新批次或重试低分素材。"

        if tool == ToolType.multi_angle_camera:
            if not plan_ready and self._is_plan_task_running(project.project_id):
                return "机位方案生成中，请稍候自动刷新。"
            if not plan_ready:
                return "先在 Step2 调整机位参数并更新方案。"
            if generated_assets == 0:
                return "点击“开始生成”，按当前机位先生成1张角度图。"
            if reviewed_assets < generated_assets:
                return f"Step4 可直接查看生成结果（已标记 {reviewed_assets}/{generated_assets}）。"
            return "当前角度已完成，可切换机位继续生成下一张。"

        if tool == ToolType.product_image_suite:
            if not plan_ready and self._is_plan_task_running(project.project_id):
                return "拍摄方案生成中，请稍候自动刷新。"
            if not plan_ready:
                return "先点击“生成拍摄方案”，确认组图镜头与表达意义。"
            if not prompts_ready:
                return "先点击“编译提示词”，生成每个镜头的试拍提示词。"
            if project.set_config and project.project_plan:
                plan_count = len(project.project_plan.shots)
                if plan_count * project.set_config.takes_per_shot < project.set_config.target_final_count:
                    return (
                        "当前试拍数量不足覆盖目标成片，请提高每方案试拍数或下调目标成片数。"
                    )
            if generated_assets == 0:
                return "点击“开始试拍”，先产出候选图再进入选片定稿。"
            required_final = project.set_config.target_final_count if project.set_config else generated_assets
            if reviewed_assets < required_final:
                return (
                    f"Step4 继续选片定稿（已选 {reviewed_assets}/{required_final}，"
                    f"候选 {generated_assets} 张）。"
                )
            return "已达到目标成片数，可提交交付或继续试拍补充备选。"

        if tool == ToolType.quick_video_15s:
            if not plan_ready and self._is_plan_task_running(project.project_id):
                return "AI方案生成中，请稍候自动刷新。"
            if not plan_ready:
                return "先点击“生成AI方案”，确保15秒节奏和分镜结构清晰。"
            if not prompts_ready:
                return "先编译提示词，再一键生成视频候选。"
            if project.status == ProjectStatus.rendering:
                return "视频候选生成中，建议等待并按日志查看进度。"
            if project.render_id and generated_assets > 0 and reviewed_assets < generated_assets:
                return f"候选视频已生成，请进行人工选片（{reviewed_assets}/{generated_assets}）。"
            if project.render_id and project.status == ProjectStatus.completed:
                return "候选视频已审核完成。"
            return "可以点击“一键生成候选”开始视频生成。"

        if current_stage == "completed":
            return "流程已完成，可在任务中心查看结果或创建新任务。"
        return "按左侧步骤顺序执行：方案设计 → 生成执行 → 人工确认。"

    def tool_to_scenario(self, tool_type: ToolType) -> ScenarioType:
        return TOOL_SCENARIO_MAP.get(tool_type, ScenarioType.product_video)

    def list_tool_templates(self, tool_type: ToolType) -> list[dict[str, Any]]:
        return self._script_service.list_tool_templates(tool_type=tool_type)

    def get_template_defaults(self, tool_type: ToolType, template_name: str) -> dict[str, Any]:
        return self._script_service.get_template_defaults(tool_type=tool_type, template_name=template_name)

    def update_prompt_inputs(self, project_id: str, prompt_inputs: PromptInputForm) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        existing_constraints = [
            item.strip()
            for item in project.brief.compliance_blocklist
            if item and item.strip()
        ]
        merged_constraints = [
            *dict.fromkeys([*existing_constraints, *[item.strip() for item in prompt_inputs.constraints if item.strip()]])
        ]
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "prompt_inputs", prompt_inputs),
                setattr(
                    p,
                    "brief",
                    p.brief.model_copy(
                        update={
                            "tone": prompt_inputs.style or p.brief.tone,
                            "evidence_points": [prompt_inputs.shot_focus] if prompt_inputs.shot_focus else p.brief.evidence_points,
                            "compliance_blocklist": merged_constraints,
                        }
                    ),
                ),
                setattr(p, "prompt_pack", None),
                setattr(p, "project_plan", None),
                setattr(p, "status", ProjectStatus.draft),
                setattr(p, "task_status", TaskRunStatus.queued),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="prompt_inputs.updated",
            message="提示词表单已更新",
            details={"constraint_count": len(merged_constraints)},
        )
        return self._get_project_or_raise(project_id)

    def update_camera_inputs(self, project_id: str, camera_inputs: dict[str, Any]) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        if project.tool_type != ToolType.multi_angle_camera:
            raise ValueError("camera inputs only supported for multi_angle_camera tool")
        normalized = dict(camera_inputs or {})
        presets = normalized.get("presets")
        if not isinstance(presets, list):
            presets = []
        sanitized_presets: list[dict[str, Any]] = []
        for idx, item in enumerate(presets[:24], start=1):
            if not isinstance(item, dict):
                continue
            yaw = int(item.get("yaw", 0))
            pitch = int(item.get("pitch", 0))
            sanitized_presets.append(
                {
                    "label": str(item.get("label") or f"angle-{idx}"),
                    "yaw": max(-180, min(180, yaw)),
                    "pitch": max(-45, min(45, pitch)),
                }
            )
        normalized["presets"] = sanitized_presets
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "camera_inputs", normalized),
                setattr(p, "project_plan", None),
                setattr(p, "prompt_pack", None),
                setattr(p, "status", ProjectStatus.draft),
                setattr(p, "task_status", TaskRunStatus.queued),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="camera.inputs.updated",
            message="多角度相机参数已更新",
            details={"preset_count": len(sanitized_presets)},
        )
        return self._get_project_or_raise(project_id)

    def _multi_angle_presets(self, camera_inputs: dict[str, Any]) -> list[dict[str, Any]]:
        presets = camera_inputs.get("presets")
        if isinstance(presets, list) and presets:
            output: list[dict[str, Any]] = []
            for idx, item in enumerate(presets[:24], start=1):
                if not isinstance(item, dict):
                    continue
                output.append(
                    {
                        "label": str(item.get("label") or f"angle-{idx}"),
                        "yaw": max(-180, min(180, int(item.get("yaw", 0)))),
                        "pitch": max(-45, min(45, int(item.get("pitch", 0)))),
                    }
                )
            if output:
                return output
        base_yaw = max(-180, min(180, int(camera_inputs.get("yaw", 0))))
        base_pitch = max(-45, min(45, int(camera_inputs.get("pitch", 0))))
        return [
            {"label": "主视角", "yaw": base_yaw, "pitch": base_pitch},
            {"label": "左前45", "yaw": max(-180, base_yaw - 45), "pitch": base_pitch},
            {"label": "右前45", "yaw": min(180, base_yaw + 45), "pitch": base_pitch},
            {"label": "俯视角", "yaw": base_yaw, "pitch": max(-45, base_pitch - 25)},
        ]

    def _build_multi_angle_plan(self, project: ProjectRecord) -> ProjectPlan:
        camera_inputs = dict(project.camera_inputs or {})
        yaw = max(-180, min(180, int(camera_inputs.get("yaw", 0))))
        pitch = max(-45, min(45, int(camera_inputs.get("pitch", 0))))
        focal_mm = str(camera_inputs.get("focal_mm") or "50")
        distance = str(camera_inputs.get("distance") or "medium")
        distance_desc = {
            "near": "近距拍摄，突出细节与材质",
            "medium": "中距拍摄，兼顾主体与结构",
            "far": "远距拍摄，完整展示轮廓比例",
        }.get(distance, "中距拍摄，兼顾主体与结构")
        angle_label = (
            "正面平视"
            if yaw == 0 and pitch == 0
            else f"yaw {yaw}° / pitch {pitch}°"
        )
        image_prompt = (
            f"{project.brief.product_name}，单张多角度产品摄影，机位 {angle_label}，焦段 {focal_mm}mm，"
            f"拍摄距离 {distance}；相机指令: 绕主体水平旋转到 yaw {yaw}°，垂直俯仰到 pitch {pitch}°；"
            f"景别: 中近景；构图: 主体稳定居中并保留边缘轮廓；"
            f"光线: 摄影棚柔光主光+轻轮廓光；要求: 透视真实、几何比例稳定、材质纹理清晰、"
            "与原图品牌元素一致，不要文字水印，不要额外道具。"
            f" {distance_desc}"
        )
        shots = [
            PlanShot(
                shot_id="angle-current",
                title=f"当前机位 · {angle_label}",
                intent="按当前机位输出1张可直接用于详情页的角度图",
                duration_sec=4,
                stage=ShotStage.feature,
                image_prompt=image_prompt,
                video_prompt=self._script_service._sanitize_video_prompt(
                    f"{project.brief.product_name} 当前机位动态预览，机位 {angle_label}，保持主体尺度稳定。"
                ),
                delivery_purpose="角度展示图",
            )
        ]
        return ProjectPlan(
            scenario_type=ScenarioType.multi_angle_camera,
            template_name=project.template_name,
            channels=project.brief.channels,
            summary=f"{project.brief.product_name} 当前机位拍摄方案",
            planner_notes=["source:camera-inputs", "single-shot:true"],
            shots=shots,
        )

    async def generate_multi_angle_plan(self, project_id: str, force: bool = False) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        if project.tool_type != ToolType.multi_angle_camera:
            raise ValueError("multi-angle plan only supported for multi_angle_camera tool")
        if project.project_plan and not force:
            return project
        plan = self._build_multi_angle_plan(project)
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "project_plan", plan),
                setattr(p, "status", ProjectStatus.scripted),
                setattr(p, "task_status", TaskRunStatus.queued),
                setattr(p, "error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="multi_angle.plan.completed",
            message="多角度拍摄方案生成完成",
            details={"shot_count": len(plan.shots)},
        )
        return self._get_project_or_raise(project_id)

    def _normalize_identity_design(self, design_inputs: dict[str, Any] | None) -> dict[str, Any]:
        payload = dict(design_inputs or {})
        identity_source = str(payload.get("identity_source") or "use_uploaded").strip()
        if identity_source not in {"use_uploaded", "beautify_uploaded", "generate_new"}:
            identity_source = "use_uploaded"
        lighting_preset = str(payload.get("lighting_preset") or "softbox_clean").strip()
        if lighting_preset not in IDENTITY_LIGHTING_PRESETS:
            lighting_preset = "softbox_clean"
        framing_preset = str(payload.get("framing_preset") or "full_body").strip()
        if framing_preset not in IDENTITY_FRAMING_PRESETS:
            framing_preset = "full_body"
        angle_preset = str(payload.get("angle_preset") or "front").strip()
        if angle_preset not in IDENTITY_ANGLE_PRESETS:
            angle_preset = "front"
        requirements = str(payload.get("identity_requirements") or "").strip()
        preserve_pose = bool(payload.get("preserve_pose", True))
        return {
            "identity_source": identity_source,
            "lighting_preset": lighting_preset,
            "framing_preset": framing_preset,
            "angle_preset": angle_preset,
            "identity_requirements": requirements[:300],
            "preserve_pose": preserve_pose,
        }

    def _is_active_identity_asset(self, asset: AssetRecord) -> bool:
        return not bool((asset.metadata or {}).get("removed"))

    def _list_identity_assets(
        self,
        project_id: str,
        *,
        source_type: AssetSourceType | None = None,
    ) -> list[AssetRecord]:
        rows: list[AssetRecord] = []
        for asset in self._store.list_assets(project_id):
            if asset.kind != AssetKind.input:
                continue
            tags = {item.lower() for item in asset.tags}
            if "identity" not in tags:
                continue
            if source_type and asset.source_type != source_type:
                continue
            if not self._is_active_identity_asset(asset):
                continue
            rows.append(asset)
        rows.sort(key=lambda item: item.created_at)
        return rows

    def _latest_uploaded_identity_asset(self, project_id: str) -> AssetRecord | None:
        rows = self._list_identity_assets(project_id, source_type=AssetSourceType.uploaded)
        if not rows:
            return None
        return rows[-1]

    def _build_identity_prompt(self, project: ProjectRecord, design: dict[str, Any]) -> str:
        source_mode = design["identity_source"]
        lighting_text = IDENTITY_LIGHTING_PRESETS[design["lighting_preset"]]
        framing_text = IDENTITY_FRAMING_PRESETS[design["framing_preset"]]
        angle_text = IDENTITY_ANGLE_PRESETS[design["angle_preset"]]
        requirements = design["identity_requirements"]
        preserve_pose = bool(design["preserve_pose"])
        if source_mode == "beautify_uploaded":
            role_instruction = "基于上传模特做全身标准照式美化并生成身份锚点，不改变五官骨相、发型轮廓与体型比例。"
        elif source_mode == "generate_new":
            role_instruction = "根据需求生成新的全身标准照式模特身份锚点，气质自然高级，避免夸张AI脸。服装使用纯色贴身基础款，不携带风格化服饰信息。"
        else:
            role_instruction = "直接使用当前上传的全身标准照式模特作为身份锚点。"
        pose_instruction = (
            "保持原图姿态、肢体走向和服装版型。"
            if preserve_pose
            else "允许在自然范围内微调姿态，但保持服装版型稳定。"
        )
        requirement_line = requirements or "无额外需求，按电商人像大片标准执行。"
        return self._script_service._cleanup_prompt_text(
            f"{project.brief.product_name} 模特身份锚点生成。{role_instruction}"
            f"镜头: {framing_text}；角度: {angle_text}；布光: {lighting_text}；输出应为一张三视图定妆照：同一画面内同时展示正面、侧面、背面，全身完整，不裁掉腿部和脚部；"
            f"{pose_instruction} 要求: 肤质真实、面部结构自然、发丝清晰。若为新生成锚点，服装必须为中性基础款，不提供后续替换服装参考。"
            f"用户需求: {requirement_line} 保持写实摄影棚风格，不要文字logo水印，不要多人物。"
            f"{project.brief.creative_direction or ''}"
        )

    def _identity_prompt_pack(self, project: ProjectRecord, design: dict[str, Any]) -> list[PromptItem]:
        return [PromptItem(shot_id="identity-candidate", prompt=self._build_identity_prompt(project, design))]

    async def generate_identity_candidate(
        self,
        project_id: str,
        regenerate: bool = False,
        design_inputs: dict[str, Any] | None = None,
    ) -> tuple[ProjectRecord, AssetRecord]:
        project = self._get_project_or_raise(project_id)
        if project.tool_type != ToolType.model_retouch:
            raise ValueError("identity candidate only supported for model_retouch tool")
        design = self._normalize_identity_design(design_inputs)
        source_mode = design["identity_source"]
        uploaded_identity_asset = self._latest_uploaded_identity_asset(project.project_id)
        if source_mode == "use_uploaded":
            if not uploaded_identity_asset:
                raise ValueError("当前没有可用模特图，请先上传替换模特图。")
            target_asset_id = uploaded_identity_asset.asset_id
            self._store.update_project(
                project_id,
                lambda p, aid=target_asset_id: (
                    setattr(p, "identity_asset_id", aid),
                    setattr(p, "identity_anchor_asset_id", aid),
                    setattr(p, "identity_mode", IdentityMode.uploaded),
                    setattr(p, "identity_status", IdentityStatus.pending),
                    setattr(p, "identity_required", True),
                    setattr(p, "error_message", None),
                ),
            )
            self._log(
                project_id=project_id,
                level=LogLevel.info,
                stage="identity.candidate.use_uploaded",
                message="已选用当前上传模特作为身份锚点候选",
                details={"asset_id": target_asset_id},
            )
            return self._get_project_or_raise(project_id), uploaded_identity_asset
        if source_mode == "beautify_uploaded" and not uploaded_identity_asset:
            raise ValueError("未上传模特图，无法执行“精修模特图”，请先上传或改用“生成新模特”。")
        source_image_path = self._resolve_project_image_path(project)
        source_image_public_url = project.image_public_url
        reference_project = project
        if source_mode == "beautify_uploaded" and uploaded_identity_asset:
            reference_project = project.model_copy(
                update={
                    "identity_asset_id": uploaded_identity_asset.asset_id,
                    "identity_anchor_asset_id": uploaded_identity_asset.asset_id,
                }
            )
            if uploaded_identity_asset.local_path:
                candidate_path = Path(uploaded_identity_asset.local_path)
                if candidate_path.is_file():
                    source_image_path = candidate_path
            if uploaded_identity_asset.image_url:
                source_image_public_url = uploaded_identity_asset.image_url
        reference_urls, reference_paths = self._collect_reference_inputs(reference_project)
        prompts = self._identity_prompt_pack(project=project, design=design)
        framing_aspect_map = {
            "headshot": "1:1",
            "half_body": "3:4",
            "full_body": "2:3",
        }
        identity_aspect_ratio = framing_aspect_map.get(str(design.get("framing_preset") or "full_body"), "2:3")
        refs = await self._reference_image.generate_images_from_prompts(
            image_path=source_image_path,
            image_public_url=source_image_public_url,
            prompts=prompts,
            image_aspect_ratio=identity_aspect_ratio,
            image_resolution="1K",
            image_output_format="png",
            reference_image_urls=reference_urls,
            reference_image_paths=reference_paths,
        )
        result = refs.get("identity-candidate")
        if not result:
            raise ValueError("身份候选图生成失败")
        status = AssetStatus.ready if (result.image_url or result.local_path) else AssetStatus.failed
        asset = AssetRecord(
            asset_id=str(uuid4()),
            project_id=project_id,
            workspace_id=project.workspace_id,
            tool_type=project.tool_type,
            kind=AssetKind.input,
            source_type=AssetSourceType.generated,
            status=status,
            created_at=utc_now(),
            updated_at=utc_now(),
            image_url=result.image_url,
            local_path=result.local_path,
            prompt=prompts[0].prompt,
            tags=["input", "reference", "identity", "generated", project.tool_type.value],
            metadata={
                "role": "identity_candidate",
                "source": result.source,
                "identity_source": design["identity_source"],
                "lighting_preset": design["lighting_preset"],
                "framing_preset": design["framing_preset"],
                "angle_preset": design["angle_preset"],
                "identity_layout": "triptych_front_side_back",
                "image_aspect_ratio": identity_aspect_ratio,
                "identity_requirements": design["identity_requirements"],
                "preserve_pose": bool(design["preserve_pose"]),
            },
        )
        self._store.add_asset(asset)
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "asset_ids", [*p.asset_ids, asset.asset_id]),
                setattr(p, "identity_asset_id", asset.asset_id),
                setattr(p, "identity_mode", IdentityMode.generated),
                setattr(p, "identity_status", IdentityStatus.pending),
                setattr(p, "identity_required", True),
                setattr(p, "error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info if status == AssetStatus.ready else LogLevel.warning,
            stage="identity.candidate.generated",
            message="替换模特身份候选图已生成",
            details={
                "asset_id": asset.asset_id,
                "status": status.value,
                "identity_source": design["identity_source"],
                "lighting_preset": design["lighting_preset"],
                "framing_preset": design["framing_preset"],
                "angle_preset": design["angle_preset"],
                "identity_layout": "triptych_front_side_back",
            },
        )
        return self._get_project_or_raise(project_id), asset

    def confirm_identity_candidate(
        self,
        project_id: str,
        asset_id: str | None = None,
    ) -> tuple[ProjectRecord, AssetRecord]:
        project = self._get_project_or_raise(project_id)
        if project.tool_type != ToolType.model_retouch:
            raise ValueError("identity confirm only supported for model_retouch tool")
        target_asset_id = asset_id or project.identity_asset_id
        if not target_asset_id:
            raise ValueError("没有可确认的替换模特图")
        asset = self._store.get_asset(target_asset_id)
        if not asset or asset.project_id != project_id:
            raise ValueError("identity asset not found in project")
        tags = {item.lower() for item in asset.tags}
        if "identity" not in tags:
            raise ValueError("asset is not an identity candidate")
        self._store.update_asset(target_asset_id, lambda a: setattr(a, "status", AssetStatus.reviewed))
        identity_mode = IdentityMode.uploaded if asset.source_type == AssetSourceType.uploaded else IdentityMode.generated
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "identity_asset_id", target_asset_id),
                setattr(p, "identity_anchor_asset_id", target_asset_id),
                setattr(p, "identity_mode", identity_mode),
                setattr(p, "identity_status", IdentityStatus.confirmed),
                setattr(p, "identity_required", True),
                setattr(p, "error_message", None),
            ),
        )
        project = self._get_project_or_raise(project_id)
        if project.batch_group_id:
            self._propagate_batch_identity(
                batch_group_id=project.batch_group_id,
                anchor_asset_id=target_asset_id,
                identity_mode=identity_mode,
                exclude_project_id=project.project_id,
            )
            self._sync_batch_stats(project.batch_group_id)
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="identity.candidate.confirmed",
            message="替换模特身份图已确认",
            details={"asset_id": target_asset_id, "identity_mode": identity_mode.value},
        )
        return self._get_project_or_raise(project_id), self._store.get_asset(target_asset_id) or asset

    def _list_batch_projects(self, batch_group_id: str) -> list[ProjectRecord]:
        rows = [
            item
            for item in self._store.list_projects(limit=200000)
            if item.batch_group_id == batch_group_id and item.tool_type == ToolType.model_retouch
        ]
        rows.sort(
            key=lambda item: (
                0 if item.batch_role == BatchRole.controller else 1,
                item.created_at,
                item.project_id,
            )
        )
        return rows

    def _resolve_batch_controller(self, batch_group_id: str) -> ProjectRecord:
        rows = self._list_batch_projects(batch_group_id)
        if not rows:
            raise KeyError(f"batch_group_id {batch_group_id} not found")
        return rows[0]

    def _propagate_batch_identity(
        self,
        *,
        batch_group_id: str,
        anchor_asset_id: str,
        identity_mode: IdentityMode,
        exclude_project_id: str | None = None,
    ) -> None:
        for item in self._list_batch_projects(batch_group_id):
            if exclude_project_id and item.project_id == exclude_project_id:
                continue
            self._store.update_project(
                item.project_id,
                lambda p: (
                    setattr(p, "identity_asset_id", anchor_asset_id),
                    setattr(p, "identity_anchor_asset_id", anchor_asset_id),
                    setattr(p, "identity_mode", identity_mode),
                    setattr(p, "identity_status", IdentityStatus.confirmed),
                    setattr(p, "identity_required", True),
                    setattr(p, "error_message", None),
                ),
            )

    def get_model_retouch_batch(self, batch_group_id: str) -> dict[str, Any]:
        rows = self._list_batch_projects(batch_group_id)
        if not rows:
            raise KeyError(f"batch_group_id {batch_group_id} not found")
        controller = rows[0]
        effective_statuses = [self._effective_task_status(item) for item in rows]
        done_images = sum(1 for status in effective_statuses if status in {TaskRunStatus.done, TaskRunStatus.reviewing})
        failed_images = sum(1 for status in effective_statuses if status == TaskRunStatus.failed)
        running_images = sum(1 for status in effective_statuses if status == TaskRunStatus.running)
        queued_images = max(0, len(rows) - done_images - failed_images - running_images)
        identity_status = (
            IdentityStatus.confirmed
            if all(item.identity_status == IdentityStatus.confirmed for item in rows)
            else IdentityStatus.pending
        )
        anchor_asset_id = controller.identity_anchor_asset_id or controller.identity_asset_id
        return {
            "batch_group_id": batch_group_id,
            "controller_project_id": controller.project_id,
            "total_images": len(rows),
            "done_images": done_images,
            "failed_images": failed_images,
            "running_images": running_images,
            "queued_images": queued_images,
            "identity_status": identity_status,
            "identity_anchor_asset_id": anchor_asset_id,
            "projects": rows,
        }

    async def generate_model_retouch_batch_identity_candidate(
        self,
        *,
        batch_group_id: str,
        design_inputs: dict[str, Any] | None = None,
        regenerate: bool = False,
    ) -> tuple[dict[str, Any], AssetRecord]:
        controller = self._resolve_batch_controller(batch_group_id)
        design = self._normalize_identity_design(design_inputs)
        project, asset = await self.generate_identity_candidate(
            project_id=controller.project_id,
            regenerate=regenerate,
            design_inputs=design,
        )
        for item in self._list_batch_projects(batch_group_id):
            if item.project_id == project.project_id:
                continue
            self._store.update_project(
                item.project_id,
                lambda p, aid=asset.asset_id, mode=project.identity_mode: (
                    setattr(p, "identity_asset_id", aid),
                    setattr(p, "identity_anchor_asset_id", aid),
                    setattr(p, "identity_mode", mode),
                    setattr(p, "identity_status", IdentityStatus.pending),
                    setattr(p, "identity_required", True),
                ),
            )
        self._sync_batch_stats(batch_group_id)
        return self.get_model_retouch_batch(batch_group_id), asset

    def confirm_model_retouch_batch_identity(
        self,
        *,
        batch_group_id: str,
        asset_id: str,
    ) -> tuple[dict[str, Any], AssetRecord]:
        controller = self._resolve_batch_controller(batch_group_id)
        asset = self._store.get_asset(asset_id)
        if not asset:
            raise ValueError("identity asset not found")
        if asset.project_id != controller.project_id:
            raise ValueError("identity asset must belong to controller project")
        tags = {item.lower() for item in asset.tags}
        if "identity" not in tags:
            raise ValueError("asset is not an identity candidate")
        self._store.update_asset(asset_id, lambda row: setattr(row, "status", AssetStatus.reviewed))
        identity_mode = IdentityMode.uploaded if asset.source_type == AssetSourceType.uploaded else IdentityMode.generated
        self._propagate_batch_identity(
            batch_group_id=batch_group_id,
            anchor_asset_id=asset_id,
            identity_mode=identity_mode,
        )
        self._sync_batch_stats(batch_group_id)
        self._log(
            project_id=controller.project_id,
            level=LogLevel.info,
            stage="identity.batch.confirmed",
            message="批次身份锚点已确认并同步",
            details={"batch_group_id": batch_group_id, "asset_id": asset_id},
        )
        return self.get_model_retouch_batch(batch_group_id), self._store.get_asset(asset_id) or asset

    def upload_model_retouch_batch_identity(
        self,
        *,
        batch_group_id: str,
        image_public_url: str,
        image_mime: str = "image/png",
        image_suffix: str = ".png",
    ) -> tuple[dict[str, Any], AssetRecord]:
        controller = self._resolve_batch_controller(batch_group_id)
        now = utc_now()
        asset = AssetRecord(
            asset_id=str(uuid4()),
            project_id=controller.project_id,
            workspace_id=controller.workspace_id,
            tool_type=ToolType.model_retouch,
            kind=AssetKind.input,
            source_type=AssetSourceType.uploaded,
            status=AssetStatus.ready,
            created_at=now,
            updated_at=now,
            image_url=image_public_url,
            local_path=None,
            tags=["input", "reference", "identity", ToolType.model_retouch.value],
            metadata={"source": "public_url", "role": "identity", "mime": image_mime, "suffix": image_suffix},
        )
        self._store.add_asset(asset)
        self._store.update_project(
            controller.project_id,
            lambda p, aid=asset.asset_id: (
                setattr(p, "asset_ids", list(dict.fromkeys([*p.asset_ids, aid]))),
                setattr(p, "identity_asset_id", aid),
                setattr(p, "identity_anchor_asset_id", aid),
                setattr(p, "identity_mode", IdentityMode.uploaded),
                setattr(p, "identity_status", IdentityStatus.pending),
                setattr(p, "identity_required", True),
                setattr(p, "error_message", None),
            ),
        )
        self._propagate_batch_identity(
            batch_group_id=batch_group_id,
            anchor_asset_id=asset.asset_id,
            identity_mode=IdentityMode.uploaded,
            exclude_project_id=controller.project_id,
        )
        for item in self._list_batch_projects(batch_group_id):
            if item.project_id == controller.project_id:
                continue
            self._store.update_project(
                item.project_id,
                lambda p: setattr(p, "identity_status", IdentityStatus.pending),
            )
        self._sync_batch_stats(batch_group_id)
        self._log(
            project_id=controller.project_id,
            level=LogLevel.info,
            stage="identity.batch.uploaded",
            message="批次替换模特图已更新",
            details={"batch_group_id": batch_group_id, "asset_id": asset.asset_id},
        )
        return self.get_model_retouch_batch(batch_group_id), asset

    def clear_model_retouch_batch_uploaded_identity(
        self,
        *,
        batch_group_id: str,
        asset_id: str | None = None,
    ) -> tuple[dict[str, Any], AssetRecord]:
        controller = self._resolve_batch_controller(batch_group_id)
        uploaded_assets = self._list_identity_assets(controller.project_id, source_type=AssetSourceType.uploaded)
        target_asset: AssetRecord | None = None
        normalized_asset_id = (asset_id or "").strip()
        if normalized_asset_id:
            target_asset = next((item for item in uploaded_assets if item.asset_id == normalized_asset_id), None)
            if not target_asset:
                raise ValueError("uploaded identity asset not found")
        elif uploaded_assets:
            target_asset = uploaded_assets[-1]
        if not target_asset:
            raise ValueError("当前没有可移除的上传模特图")

        def _mark_removed(asset: AssetRecord) -> None:
            current_metadata = dict(asset.metadata or {})
            current_metadata["removed"] = True
            current_metadata["removed_reason"] = "user_cleared_upload"
            current_metadata["removed_at"] = utc_now().isoformat()
            asset.metadata = current_metadata
            asset.tags = [tag for tag in asset.tags if tag.lower() not in {"identity", "reference"}]

        self._store.update_asset(target_asset.asset_id, _mark_removed)

        for item in self._list_batch_projects(batch_group_id):
            self._store.update_project(
                item.project_id,
                lambda p, aid=target_asset.asset_id: (
                    setattr(p, "asset_ids", [row for row in p.asset_ids if row != aid]),
                    setattr(p, "identity_anchor_asset_id", None if p.identity_anchor_asset_id == aid else p.identity_anchor_asset_id),
                    setattr(p, "identity_asset_id", p.identity_anchor_asset_id if p.identity_asset_id == aid else p.identity_asset_id),
                    setattr(p, "identity_mode", IdentityMode.none if not (p.identity_anchor_asset_id or p.identity_asset_id) else p.identity_mode),
                    setattr(p, "identity_status", IdentityStatus.pending if p.identity_anchor_asset_id is None else p.identity_status),
                    setattr(p, "error_message", None),
                ),
            )
        self._sync_batch_stats(batch_group_id)
        self._log(
            project_id=controller.project_id,
            level=LogLevel.info,
            stage="identity.batch.uploaded.cleared",
            message="批次上传模特图已移除",
            details={"batch_group_id": batch_group_id, "asset_id": target_asset.asset_id},
        )
        refreshed = self._store.get_asset(target_asset.asset_id) or target_asset
        return self.get_model_retouch_batch(batch_group_id), refreshed

    async def generate_model_retouch_batch(
        self,
        *,
        batch_group_id: str,
        project_ids: list[str] | None = None,
        output_aspect_ratio: str = "original",
        image_resolution: str | None = None,
        image_output_format: str = "png",
    ) -> dict[str, Any]:
        rows = self._list_batch_projects(batch_group_id)
        if not rows:
            raise KeyError(f"batch_group_id {batch_group_id} not found")
        target = rows
        if project_ids:
            selected = set(project_ids)
            target = [item for item in rows if item.project_id in selected]
            if not target:
                raise ValueError("project_ids not found in batch")
        normalized_output_aspect_ratio = str(output_aspect_ratio or "original").strip().lower()
        allowed_output_aspect_ratio = {
            "original",
            "1:1",
            "2:3",
            "3:2",
            "3:4",
            "4:3",
            "4:5",
            "5:4",
            "9:16",
            "16:9",
            "21:9",
        }
        if normalized_output_aspect_ratio not in allowed_output_aspect_ratio:
            normalized_output_aspect_ratio = "original"
        for item in target:
            self._store.update_project(
                item.project_id,
                lambda p, ratio=normalized_output_aspect_ratio: setattr(p, "output_aspect_ratio", ratio),
            )

        async def _run_one(item: ProjectRecord) -> None:
            await self.generate_for_project(
                project_id=item.project_id,
                stage="auto",
                async_mode=False,
                candidates_per_prompt=1,
                image_aspect_ratio="auto",
                image_resolution=image_resolution,
                image_output_format=image_output_format,
            )

        semaphore = asyncio.Semaphore(6)

        async def _guard(item: ProjectRecord) -> None:
            async with semaphore:
                await _run_one(item)

        results = await asyncio.gather(*[_guard(item) for item in target], return_exceptions=True)
        failed = sum(1 for item in results if isinstance(item, Exception))
        if failed:
            logger.warning("model retouch batch generate finished with %s failures in batch %s", failed, batch_group_id)
        self._sync_batch_stats(batch_group_id)
        return self.get_model_retouch_batch(batch_group_id)

    async def retry_model_retouch_batch(
        self,
        *,
        batch_group_id: str,
        project_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        rows = self._list_batch_projects(batch_group_id)
        if not rows:
            raise KeyError(f"batch_group_id {batch_group_id} not found")
        target = rows
        if project_ids:
            selected = set(project_ids)
            target = [item for item in rows if item.project_id in selected]
            if not target:
                raise ValueError("project_ids not found in batch")
        else:
            target = [item for item in rows if self._effective_task_status(item) == TaskRunStatus.failed]
        if not target:
            return self.get_model_retouch_batch(batch_group_id)
        for item in target:
            await self.retry_project(project_id=item.project_id, stage="generate", async_mode=False)
        self._sync_batch_stats(batch_group_id)
        return self.get_model_retouch_batch(batch_group_id)

    async def generate_for_project(
        self,
        project_id: str,
        *,
        stage: str = "auto",
        variants_per_shot: int = 2,
        candidates_per_prompt: int = 1,
        async_mode: bool = False,
        image_aspect_ratio: str = "1:1",
        image_resolution: str | None = None,
        image_output_format: str = "png",
        video_aspect_ratio: str = "portrait",
        video_n_frames: str = "10",
        video_size: str = "standard",
        video_remove_watermark: bool = True,
        video_upload_method: str = "s3",
    ) -> dict[str, Any]:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="generate_for_project")
        tool = project.tool_type
        normalized_stage = stage.strip().lower() if stage else "auto"

        if tool in {ToolType.product_image_suite, ToolType.model_retouch, ToolType.multi_angle_camera}:
            if tool == ToolType.model_retouch and project.identity_required and project.identity_status != IdentityStatus.confirmed:
                raise ValueError("请先在身份确认步骤确认替换模特图，再执行批量精修。")
            if tool == ToolType.multi_angle_camera:
                await self.generate_multi_angle_plan(project_id=project_id, force=True)
                project = self._get_project_or_raise(project_id)
            effective_candidates = max(1, candidates_per_prompt)
            if tool == ToolType.multi_angle_camera:
                # 多角度工坊每次只生成当前机位的单张图，避免用户误解为批量任务。
                effective_candidates = 1
            if tool == ToolType.product_image_suite and project.set_config:
                effective_candidates = max(effective_candidates, project.set_config.takes_per_shot)
                if not project.project_plan:
                    await self.generate_project_plan(project_id=project_id, force=False)
                    project = self._get_project_or_raise(project_id)
                planned_shots = len(project.project_plan.shots) if project.project_plan else 0
                if (
                    planned_shots > 0
                    and planned_shots * effective_candidates < project.set_config.target_final_count
                ):
                    raise ValueError(
                        "试拍数量不足，请提高“每方案试拍数”或降低“目标成片数”。"
                    )
            project_row, assets, reports = await self.generate_images_for_project(
                project_id=project_id,
                request=GenerateImagesRequest(
                    regenerate=normalized_stage == "regenerate",
                    async_mode=async_mode,
                    candidates_per_prompt=effective_candidates,
                    image_aspect_ratio=image_aspect_ratio,
                    image_resolution=image_resolution,
                    image_output_format=image_output_format,
                ),
            )
            ready_generated_assets = [
                item
                for item in assets
                if item.source_type == AssetSourceType.generated
                and item.kind == AssetKind.generated_image
                and item.status in {AssetStatus.ready, AssetStatus.reviewed}
            ]
            self._store.update_project(
                project_id,
                lambda p: setattr(
                    p,
                    "task_status",
                    TaskRunStatus.running
                    if async_mode
                    else TaskRunStatus.reviewing
                    if ready_generated_assets
                    else TaskRunStatus.failed,
                ),
            )
            if project_row.batch_group_id:
                self._sync_batch_stats(project_row.batch_group_id)
            return {"project": project_row, "assets": assets, "quality_reports": reports}

        if tool == ToolType.quick_video_15s:
            if not project.project_plan:
                await self.generate_project_plan(project_id=project_id, force=False)
            if not project.prompt_pack:
                await self.derive_prompts(project_id=project_id, force=False)
            project = self._get_project_or_raise(project_id)
            if not project.selected_script:
                script = self._project_plan_to_script(project)
                self._store.update_project(
                    project_id,
                    lambda p: (
                        setattr(p, "selected_script", script),
                        setattr(p, "master_script", self._script_to_master(script)),
                        setattr(
                            p,
                            "shot_approvals",
                            {shot.shot_id: ShotApprovalStatus.pending for shot in script.shots},
                        ),
                    ),
                )
                project = self._get_project_or_raise(project_id)
            if project.storyboard_status != StoryboardStatus.confirmed:
                await self.generate_storyboard(project_id=project_id, regenerate=normalized_stage == "regenerate")
                project = self._get_project_or_raise(project_id)
                if project.selected_script:
                    for shot in project.selected_script.shots:
                        self.approve_storyboard_shot(
                            project_id=project_id,
                            shot_id=shot.shot_id,
                            status=ShotApprovalStatus.approved,
                        )
                    self.confirm_storyboard(project_id=project_id)
            render_response = await self.generate_videos_for_project(
                project_id=project_id,
                request=GenerateVideosRequest(
                    variants_per_shot=max(1, variants_per_shot),
                    async_mode=async_mode,
                    video_aspect_ratio=video_aspect_ratio,
                    video_n_frames=video_n_frames,
                    video_size=video_size,
                    video_remove_watermark=video_remove_watermark,
                    video_upload_method=video_upload_method,
                ),
            )
            render_status = render_response.render.status
            if render_status == ProjectStatus.completed:
                next_task_status = TaskRunStatus.reviewing
            elif render_status == ProjectStatus.failed:
                next_task_status = TaskRunStatus.failed
            else:
                next_task_status = TaskRunStatus.running
            self._store.update_project(
                project_id,
                lambda p: setattr(
                    p,
                    "task_status",
                    next_task_status,
                ),
            )
            return {
                "project": render_response.project,
                "render": render_response.render,
            }

        # intro video flow keeps the gate: first storyboard, then render.
        if not project.selected_script:
            if not project.script_options:
                raise ValueError("AI脚本尚未生成，请稍后重试。")
            raise ValueError("请先在工作台选择并确认一套主拍摄脚本。")

        if normalized_stage in {"storyboard", "auto"} and project.storyboard_status != StoryboardStatus.confirmed:
            project_row = await self.generate_storyboard(
                project_id=project_id,
                regenerate=normalized_stage == "regenerate",
            )
            self._store.update_project(project_id, lambda p: setattr(p, "task_status", TaskRunStatus.reviewing))
            return {"project": project_row}

        if project.storyboard_status != StoryboardStatus.confirmed:
            raise ValueError("请先完成分镜确认，再生成视频。")

        render_response = await self.generate_videos_for_project(
            project_id=project_id,
            request=GenerateVideosRequest(
                variants_per_shot=max(1, variants_per_shot),
                async_mode=async_mode,
                video_aspect_ratio=video_aspect_ratio,
                video_n_frames=video_n_frames,
                video_size=video_size,
                video_remove_watermark=video_remove_watermark,
                video_upload_method=video_upload_method,
            ),
        )
        render_status = render_response.render.status
        if render_status == ProjectStatus.completed:
            next_task_status = TaskRunStatus.reviewing
        elif render_status == ProjectStatus.failed:
            next_task_status = TaskRunStatus.failed
        else:
            next_task_status = TaskRunStatus.running
        self._store.update_project(
            project_id,
            lambda p: setattr(
                p,
                "task_status",
                next_task_status,
            ),
        )
        return {"project": render_response.project, "render": render_response.render}

    def _map_storyboard_status(self, status: StoryboardStatus) -> str:
        if status == StoryboardStatus.failed:
            return "failed"
        if status == StoryboardStatus.confirmed:
            return "completed"
        if status == StoryboardStatus.ready:
            return "in_progress"
        if status == StoryboardStatus.generating:
            return "in_progress"
        return "pending"

    def _ensure_project_not_failed(self, project: ProjectRecord, action: str) -> None:
        render = self.get_render(project.render_id) if project.render_id else None
        failed_stage = self._detect_failed_stage(project=project, render=render)
        if failed_stage:
            raise ValueError(
                f"当前项目处于失败状态（stage={failed_stage}），请先调用 retry 接口后再执行 {action}。"
            )

    async def retry_project(
        self,
        project_id: str,
        *,
        stage: str | None = None,
        async_mode: bool = False,
    ) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        render = self.get_render(project.render_id) if project.render_id else None
        failed_stage = self._detect_failed_stage(project=project, render=render)
        if not failed_stage:
            raise ValueError("当前项目不处于可重试的失败状态。")

        target_stage = (stage or failed_stage).strip().lower()
        allowed = {"plan", "prompt", "generate"}
        if project.scenario_type == ScenarioType.product_video:
            allowed.update({"storyboard", "render"})
        if target_stage not in allowed:
            raise ValueError(f"retry stage 不合法: {target_stage}")

        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "status", ProjectStatus.scripted if p.project_plan else ProjectStatus.draft),
                setattr(p, "task_status", TaskRunStatus.queued),
                setattr(p, "error_message", None),
                setattr(p, "storyboard_error_message", None),
                setattr(p, "render_id", None if failed_stage == "render" else p.render_id),
            ),
        )

        if target_stage == "plan":
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "project_plan", None),
                    setattr(p, "prompt_pack", None),
                    setattr(p, "image_prompt_script", None),
                    setattr(p, "video_prompt_script", None),
                    setattr(p, "storyboard_status", StoryboardStatus.not_started),
                    setattr(p, "storyboard_references", {}),
                    setattr(p, "render_id", None),
                ),
            )
            await self.generate_project_plan(project_id=project_id, force=True)
        elif target_stage == "prompt":
            self._store.update_project(
                project_id,
                lambda p: (
                    setattr(p, "prompt_pack", None),
                    setattr(p, "image_prompt_script", None),
                    setattr(p, "video_prompt_script", None),
                ),
            )
            await self.derive_prompts(project_id=project_id, force=True)
        elif target_stage == "generate":
            await self.generate_images_for_project(
                project_id=project_id,
                request=GenerateImagesRequest(
                    regenerate=True,
                    async_mode=async_mode,
                    candidates_per_prompt=1,
                    image_aspect_ratio="1:1",
                    image_resolution="1K",
                    image_output_format="png",
                ),
            )
        elif target_stage == "storyboard":
            if async_mode:
                self.start_storyboard_generation(project_id=project_id, regenerate=True)
            else:
                await self.generate_storyboard(project_id=project_id, regenerate=True)
        elif target_stage == "render":
            await self.generate_videos_for_project(
                project_id=project_id,
                request=GenerateVideosRequest(
                    variants_per_shot=2,
                    async_mode=async_mode,
                ),
            )

        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="retry.completed",
            message="失败阶段已重试",
            details={"retry_stage": target_stage, "async_mode": async_mode},
        )
        project = self._get_project_or_raise(project_id)
        if project.batch_group_id:
            self._sync_batch_stats(project.batch_group_id)
        return self._get_project_or_raise(project_id)

    def _effective_task_status(self, project: ProjectRecord) -> TaskRunStatus:
        if project.status == ProjectStatus.failed:
            return TaskRunStatus.failed
        if project.status == ProjectStatus.completed:
            return TaskRunStatus.done
        if project.status == ProjectStatus.rendering:
            return TaskRunStatus.running
        return project.task_status

    def _script_to_master(self, script: ScriptOption) -> MasterScript:
        return MasterScript.model_validate(script.model_dump(mode="json"))

    def _master_to_script(self, script: MasterScript) -> ScriptOption:
        return ScriptOption.model_validate(script.model_dump(mode="json"))

    def _build_derived_scripts(
        self,
        script: ScriptOption,
    ) -> tuple[ImagePromptScript, VideoPromptScript]:
        image_script = ImagePromptScript(
            script_id=script.script_id,
            shots=[
                {
                    "shot_id": shot.shot_id,
                    "prompt": shot.reference_image_prompt or shot.visual_prompt,
                }
                for shot in script.shots
            ],
        )
        video_script = VideoPromptScript(
            script_id=script.script_id,
            shots=[
                {
                    "shot_id": shot.shot_id,
                    "prompt": shot.visual_prompt,
                }
                for shot in script.shots
            ],
        )
        return image_script, video_script

    def _split_variant_shot_id(self, shot_id: str) -> tuple[str, int]:
        marker = "__v"
        if marker not in shot_id:
            return shot_id, 1
        base, suffix = shot_id.rsplit(marker, 1)
        try:
            index = int(suffix)
        except ValueError:
            index = 1
        return base or shot_id, max(1, index)

    def _is_storyboard_task_running(self, project_id: str) -> bool:
        task = self._storyboard_tasks.get(project_id)
        return bool(task and not task.done())

    def _is_render_task_running(self, project_id: str) -> bool:
        task = self._render_tasks.get(project_id)
        return bool(task and not task.done())

    def _is_image_task_running(self, project_id: str) -> bool:
        task = self._image_tasks.get(project_id)
        return bool(task and not task.done())

    def _is_plan_task_running(self, project_id: str) -> bool:
        task = self._plan_tasks.get(project_id)
        return bool(task and not task.done())

    def _track_background_task(
        self,
        tasks: dict[str, asyncio.Task[None]],
        key: str,
        task: asyncio.Task[None],
    ) -> None:
        tasks[key] = task

        def _cleanup(done: asyncio.Task[None]) -> None:
            tasks.pop(key, None)
            try:
                done.result()
            except Exception as exc:  # pragma: no cover - defensive logging for detached tasks
                logger.warning("Background task %s failed: %s", key, exc)

        task.add_done_callback(_cleanup)

    def get_project(self, project_id: str) -> ProjectRecord | None:
        project = self._store.get_project(project_id)
        if not project or not project.project_plan:
            return project
        normalized_plan = self._normalize_project_plan_delivery_purpose(
            scenario_type=project.scenario_type,
            plan=project.project_plan,
        )
        if normalized_plan != project.project_plan:
            self._store.update_project(
                project_id,
                lambda p: setattr(p, "project_plan", normalized_plan),
            )
            project = self._store.get_project(project_id)
        return project

    def get_render(self, render_id: str) -> RenderRecord | None:
        return self._store.get_render(render_id)

    def get_asset(self, asset_id: str) -> AssetRecord | None:
        return self._store.get_asset(asset_id)

    def list_assets(self, project_id: str) -> list[AssetRecord]:
        return self._store.list_assets(project_id=project_id)

    def list_quality_reports(self, project_id: str) -> list[QualityReport]:
        return self._store.list_quality_reports(project_id=project_id)

    def list_review_decisions(self, project_id: str) -> list[ReviewDecision]:
        return self._store.list_review_decisions(project_id=project_id)

    def list_projects(self, limit: int = 20, query: str | None = None) -> list[ProjectRecord]:
        return self._store.list_projects(limit=limit, query=query)

    def list_projects_by_tool(
        self,
        tool_type: ToolType,
        limit: int = 20,
        query: str | None = None,
    ) -> list[ProjectRecord]:
        rows = self._store.list_projects(limit=max(limit * 5, limit), query=query)
        filtered = [item for item in rows if item.tool_type == tool_type]
        return filtered[:limit]

    def list_assets_global(
        self,
        *,
        source_type: str | None = None,
        tool_type: str | None = None,
        project_id: str | None = None,
        keyword: str | None = None,
        tag: str | None = None,
        limit: int = 200,
    ) -> list[AssetRecord]:
        return self._store.list_assets_global(
            source_type=source_type,
            tool_type=tool_type,
            project_id=project_id,
            keyword=keyword,
            tag=tag,
            limit=limit,
        )

    def list_showcase_assets(
        self,
        *,
        tool_type: ToolType | None = None,
        limit: int = 200,
    ) -> list[AssetRecord]:
        items = self._store.list_assets_global(tag=SHOWCASE_SHARE_TAG, limit=max(limit * 4, limit))
        rows = [item for item in items if item.kind == AssetKind.generated_image and self._asset_is_showcase_shared(item)]
        if tool_type is not None:
            rows = [item for item in rows if item.tool_type == tool_type]
        rows.sort(
            key=lambda item: (
                str((item.metadata or {}).get("showcase_shared_at") or item.updated_at.isoformat()),
                item.updated_at.isoformat(),
            ),
            reverse=True,
        )
        return rows[:limit]

    async def create_project_from_showcase_asset(
        self,
        *,
        owner_username: str,
        asset_id: str,
        product_name: str | None = None,
        template_name: str | None = None,
    ) -> ShowcaseRemixResponse:
        source_asset = self._store.get_asset(asset_id)
        if not source_asset:
            raise ValueError("showcase asset not found")
        if source_asset.kind != AssetKind.generated_image:
            raise ValueError("showcase remix only supports image assets")
        if not self._asset_is_showcase_shared(source_asset):
            raise ValueError("asset is not published in showcase")

        source_project = self._store.get_project(source_asset.project_id)
        if not source_project:
            raise ValueError("source project not found")
        brief = source_project.brief.model_copy(deep=True)
        if product_name and product_name.strip():
            brief.product_name = product_name.strip()[:80]
        else:
            brief.product_name = f"{brief.product_name}-同款"

        image_bytes = b""
        image_public_url = source_asset.image_url
        image_suffix = ".png"
        image_mime = "image/png"
        if source_asset.local_path:
            path = Path(source_asset.local_path)
            if path.is_file():
                image_bytes = path.read_bytes()
                image_suffix = path.suffix or ".png"
        if not image_bytes and source_asset.image_url:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                resp = client.get(source_asset.image_url)
                resp.raise_for_status()
                image_bytes = resp.content
            if source_asset.image_url.lower().endswith(".jpg") or source_asset.image_url.lower().endswith(".jpeg"):
                image_suffix = ".jpg"
                image_mime = "image/jpeg"

        created = await self.create_project(
            image_bytes=image_bytes,
            image_mime=image_mime,
            image_suffix=image_suffix,
            brief=brief,
            image_public_url=image_public_url if not image_bytes else None,
            owner_username=owner_username,
            tool_type=source_project.tool_type,
            scenario_type=source_project.scenario_type,
            template_name=(template_name or source_project.template_name or "general").strip() or "general",
            quality_level=source_project.quality_level,
            prompt_inputs=source_project.prompt_inputs,
        )
        self._store.update_project(
            created.project_id,
            lambda p: (
                setattr(
                    p,
                    "camera_inputs",
                    {
                        **dict(p.camera_inputs or {}),
                        "source_showcase_asset_id": source_asset.asset_id,
                        "source_showcase_project_id": source_project.project_id,
                    },
                )
            ),
        )
        self._log(
            project_id=created.project_id,
            level=LogLevel.info,
            stage="showcase.remix.created",
            message="已根据样片创建同款项目",
            details={
                "source_asset_id": source_asset.asset_id,
                "source_project_id": source_project.project_id,
                "owner_username": owner_username,
            },
        )
        return ShowcaseRemixResponse(
            source_asset_id=source_asset.asset_id,
            source_project_id=source_project.project_id,
            project=self._get_project_or_raise(created.project_id),
        )

    def get_quality_summary(
        self,
        *,
        days: int = 7,
        tool_type: ToolType | None = None,
    ) -> QualitySummaryResponse:
        now = utc_now()
        horizon = now.timestamp() - max(1, int(days)) * 24 * 3600
        reports = self._store.list_quality_reports_global(limit=200000)
        grouped: dict[ToolType, list[QualityReport]] = {}
        issue_counter: dict[ToolType, dict[str, int]] = {}
        for report in reports:
            if report.created_at.timestamp() < horizon:
                continue
            project = self._store.get_project(report.project_id)
            if not project:
                continue
            if tool_type is not None and project.tool_type != tool_type:
                continue
            grouped.setdefault(project.tool_type, []).append(report)
            issue_counter.setdefault(project.tool_type, {})
            for issue in report.issues:
                key = str(issue or "").strip()
                if not key:
                    continue
                issue_counter[project.tool_type][key] = issue_counter[project.tool_type].get(key, 0) + 1

        items: list[QualitySummaryItem] = []
        total_reports = 0
        total_passed = 0
        for tt, rows in grouped.items():
            total = len(rows)
            passed = sum(1 for item in rows if item.passed)
            total_reports += total
            total_passed += passed
            top_issues = sorted(
                issue_counter.get(tt, {}).items(),
                key=lambda it: it[1],
                reverse=True,
            )[:3]
            items.append(
                QualitySummaryItem(
                    tool_type=tt,
                    total_reports=total,
                    passed_reports=passed,
                    pass_rate=(passed / total) if total else 0.0,
                    avg_score=(sum(item.score for item in rows) / total) if total else 0.0,
                    avg_clarity=(sum(item.clarity_score for item in rows) / total) if total else 0.0,
                    avg_consistency=(sum(item.consistency_score for item in rows) / total) if total else 0.0,
                    avg_compliance=(sum(item.compliance_score for item in rows) / total) if total else 0.0,
                    top_issues=[f"{name} ({count})" for name, count in top_issues],
                )
            )
        items.sort(key=lambda item: item.pass_rate, reverse=True)
        return QualitySummaryResponse(
            days=max(1, int(days)),
            total_reports=total_reports,
            overall_pass_rate=(total_passed / total_reports) if total_reports else 0.0,
            items=items,
        )

    def get_prompt_version_metrics(
        self,
        *,
        days: int = 7,
        tool_type: ToolType | None = None,
    ) -> PromptVersionMetricsResponse:
        now = utc_now()
        horizon = now.timestamp() - max(1, int(days)) * 24 * 3600
        projects = self._store.list_projects(limit=200000)
        quality_by_project: dict[str, list[QualityReport]] = {}
        for report in self._store.list_quality_reports_global(limit=200000):
            quality_by_project.setdefault(report.project_id, []).append(report)

        grouped: dict[tuple[ToolType, str], dict[str, Any]] = {}
        for project in projects:
            if project.updated_at.timestamp() < horizon:
                continue
            if tool_type is not None and project.tool_type != tool_type:
                continue
            if not project.prompt_pack:
                continue
            version = str(
                (project.prompt_pack.guardrail_report or {}).get("planner_prompt_version")
                or f"prompt_pack_v{project.prompt_pack.version}"
            )
            key = (project.tool_type, version)
            row = grouped.setdefault(
                key,
                {
                    "project_count": 0,
                    "generated_assets": 0,
                    "passed_reports": 0,
                    "total_reports": 0,
                    "score_sum": 0.0,
                    "last_used_at": project.updated_at,
                },
            )
            row["project_count"] += 1
            row["last_used_at"] = max(row["last_used_at"], project.updated_at)
            reports = quality_by_project.get(project.project_id, [])
            for report in reports:
                row["total_reports"] += 1
                row["score_sum"] += float(report.score or 0.0)
                if report.passed:
                    row["passed_reports"] += 1
            assets = self._store.list_assets(project.project_id)
            row["generated_assets"] += sum(
                1
                for item in assets
                if item.source_type == AssetSourceType.generated
                and item.kind in {AssetKind.generated_image, AssetKind.generated_video}
            )

        items: list[PromptVersionMetric] = []
        for (tt, version), row in grouped.items():
            total_reports = int(row["total_reports"])
            items.append(
                PromptVersionMetric(
                    tool_type=tt,
                    prompt_version=version,
                    project_count=int(row["project_count"]),
                    generated_assets=int(row["generated_assets"]),
                    pass_rate=(float(row["passed_reports"]) / total_reports) if total_reports else 0.0,
                    avg_score=(float(row["score_sum"]) / total_reports) if total_reports else 0.0,
                    last_used_at=row["last_used_at"],
                )
            )
        items.sort(key=lambda item: item.last_used_at or utc_now(), reverse=True)
        return PromptVersionMetricsResponse(days=max(1, int(days)), items=items)

    def get_dashboard_kpi(self) -> dict[str, int]:
        projects = self._store.list_projects(limit=10000)
        assets = self._store.list_assets_global(limit=100000)
        showcase_assets = sum(1 for item in assets if self._asset_is_showcase_shared(item))
        share_points_earned = sum(self._asset_reward_points(item) for item in assets)
        return {
            "total_projects": len(projects),
            "running_projects": sum(
                1
                for item in projects
                if self._effective_task_status(item) in {TaskRunStatus.running, TaskRunStatus.queued}
            ),
            "failed_projects": sum(
                1 for item in projects if self._effective_task_status(item) == TaskRunStatus.failed
            ),
            "done_projects": sum(
                1 for item in projects if self._effective_task_status(item) == TaskRunStatus.done
            ),
            "total_assets": len(assets),
            "uploaded_assets": sum(1 for item in assets if item.source_type == AssetSourceType.uploaded),
            "generated_assets": sum(1 for item in assets if item.source_type == AssetSourceType.generated),
            "showcase_assets": showcase_assets,
            "share_points_earned": share_points_earned,
        }

    def get_project_logs(self, project_id: str, limit: int = 200) -> list[ProjectLog]:
        project = self._store.get_project(project_id)
        if not project:
            raise KeyError(f"project_id {project_id} not found")
        return self._store.list_project_logs(project_id, limit=limit)

    def _write_image(self, project_id: str, image_bytes: bytes, image_suffix: str) -> Path:
        suffix = image_suffix.lower() if image_suffix else ".png"
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        target = self._storage_root / "uploads" / f"{project_id}{suffix}"
        target.write_bytes(image_bytes)
        return target

    def _get_project_image_mime(self, project: ProjectRecord) -> str:
        assets = self._store.list_assets(project.project_id)
        for asset in assets:
            if asset.kind != AssetKind.input:
                continue
            mime = asset.metadata.get("mime")
            if isinstance(mime, str) and mime:
                return mime
        return "image/png"

    def _get_project_image_bytes(self, project: ProjectRecord) -> bytes:
        image_path = Path(project.image_path)
        if image_path.is_file():
            return image_path.read_bytes()
        if project.source_image_b64:
            try:
                return base64.b64decode(project.source_image_b64)
            except Exception as exc:  # pragma: no cover - defensive decode path
                raise ValueError("project source image data is invalid") from exc
        if project.image_public_url:
            try:
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    response = client.get(project.image_public_url)
                    response.raise_for_status()
                    payload = response.content
                suffix = image_path.suffix if image_path.suffix else ".png"
                target = self._storage_root / "uploads" / f"{project.project_id}{suffix}"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                try:
                    self._store.update_project(
                        project.project_id,
                        lambda p: setattr(p, "source_image_b64", base64.b64encode(payload).decode("utf-8")),
                    )
                except Exception:
                    pass
                return payload
            except Exception as exc:  # pragma: no cover - network instability
                raise ValueError("project source image is missing") from exc
        raise ValueError("project source image is missing")

    def _resolve_project_image_path(self, project: ProjectRecord) -> Path:
        image_path = Path(project.image_path)
        if image_path.is_file():
            return image_path
        image_bytes = self._get_project_image_bytes(project)
        suffix = image_path.suffix if image_path.suffix else ".png"
        target = self._storage_root / "uploads" / f"{project.project_id}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(image_bytes)
        return target

    def _collect_reference_inputs(self, project: ProjectRecord) -> tuple[list[str], list[Path]]:
        identity_urls: list[str] = []
        identity_paths: list[Path] = []
        other_urls: list[str] = []
        other_paths: list[Path] = []
        main_image_path = Path(project.image_path).resolve()
        expected_identity_asset_id = project.identity_anchor_asset_id or project.identity_asset_id
        identity_asset_attached = False
        for asset in self._store.list_assets(project.project_id):
            if asset.kind != AssetKind.input:
                continue
            tags = {item.lower() for item in asset.tags}
            if not self._is_active_identity_asset(asset) and "identity" in tags:
                continue
            if "reference" not in tags:
                continue
            is_identity_asset = bool(expected_identity_asset_id and asset.asset_id == expected_identity_asset_id)
            if (
                project.tool_type == ToolType.model_retouch
                and "identity" in tags
                and expected_identity_asset_id
                and asset.asset_id != expected_identity_asset_id
            ):
                # 模特精修仅使用当前锚点身份图，避免多个身份候选混入参考导致结果漂移。
                continue
            if is_identity_asset:
                identity_asset_attached = True
            prefer_identity_group = project.tool_type == ToolType.model_retouch and is_identity_asset
            target_urls = identity_urls if prefer_identity_group else other_urls
            target_paths = identity_paths if prefer_identity_group else other_paths
            if asset.image_url:
                target_urls.append(asset.image_url)
                continue
            if asset.local_path:
                candidate = Path(asset.local_path)
                if candidate.is_file():
                    try:
                        if candidate.resolve() != main_image_path:
                            target_paths.append(candidate)
                    except Exception:
                        target_paths.append(candidate)
        if expected_identity_asset_id and not identity_asset_attached:
            anchor_asset = self._store.get_asset(expected_identity_asset_id)
            if anchor_asset and self._is_active_identity_asset(anchor_asset):
                if anchor_asset.image_url:
                    identity_urls.append(anchor_asset.image_url)
                elif anchor_asset.local_path:
                    anchor_path = Path(anchor_asset.local_path)
                    if anchor_path.is_file():
                        identity_paths.append(anchor_path)

        urls = [*identity_urls, *other_urls]
        paths = [*identity_paths, *other_paths]
        # keep order stable while removing duplicates
        unique_urls: list[str] = []
        seen_urls: set[str] = set()
        for item in urls:
            if item in seen_urls:
                continue
            seen_urls.add(item)
            unique_urls.append(item)

        unique_paths: list[Path] = []
        seen_paths: set[str] = set()
        for item in paths:
            value = str(item)
            if value in seen_paths:
                continue
            seen_paths.add(value)
            unique_paths.append(item)
        return unique_urls[:7], unique_paths[:7]

    def _compute_batch_stats(self, batch_group_id: str) -> BatchStats:
        projects = [
            item
            for item in self._store.list_projects(limit=10000)
            if item.batch_group_id == batch_group_id
        ]
        done_images = sum(
            1 for item in projects if self._effective_task_status(item) == TaskRunStatus.done
        )
        failed_images = sum(
            1 for item in projects if self._effective_task_status(item) == TaskRunStatus.failed
        )
        total_images = len(projects)
        queued_images = max(0, total_images - done_images - failed_images)
        return BatchStats(
            total_images=total_images,
            done_images=done_images,
            failed_images=failed_images,
            queued_images=queued_images,
        )

    def _sync_batch_stats(self, batch_group_id: str) -> None:
        stats = self._compute_batch_stats(batch_group_id)
        for item in self._store.list_projects(limit=10000):
            if item.batch_group_id != batch_group_id:
                continue
            self._store.update_project(
                item.project_id,
                lambda p, batch_stats=stats: setattr(p, "batch_stats", batch_stats),
            )

    def _get_project_or_raise(self, project_id: str) -> ProjectRecord:
        project = self._store.get_project(project_id)
        if not project:
            raise KeyError(f"project_id {project_id} not found")
        return project

    def _project_plan_to_script(self, project: ProjectRecord) -> ScriptOption:
        if not project.project_plan or not project.project_plan.shots:
            raise ValueError("project plan is missing for video generation")
        shots: list[ShotPlan] = []
        for idx, shot in enumerate(project.project_plan.shots):
            shots.append(
                ShotPlan(
                    shot_id=shot.shot_id or f"shot-{idx + 1}",
                    stage=shot.stage,
                    duration_sec=max(3, min(8, shot.duration_sec)),
                    visual_prompt=shot.video_prompt,
                    reference_image_prompt=shot.image_prompt,
                    motion_direction="镜头平稳推进，动作自然",
                    voiceover_direction="语速中等，语气真实克制",
                    narration=shot.intent,
                    on_screen_text="",
                )
            )
        total_duration = sum(item.duration_sec for item in shots)
        return ScriptOption(
            script_id=f"plan-script-{project.project_id}",
            title=f"{project.brief.product_name} 15秒视频方案",
            format_type="场景演示",
            strategy_note="先吸引再演示再收束，保持真实质感",
            compliance_note="禁止绝对化词汇与画面文字",
            total_duration_sec=max(15, min(50, total_duration)),
            shots=shots,
        )

    def _materialize_video_assets(self, project_id: str, render: RenderRecord) -> None:
        now = utc_now()
        project = self._get_project_or_raise(project_id)
        assets: list[AssetRecord] = []
        for shot_id, clips in render.variants.items():
            for clip in clips:
                url = clip.video_url
                local_path = clip.local_path
                status = AssetStatus.ready if (url or local_path) else AssetStatus.failed
                asset = AssetRecord(
                    asset_id=str(uuid4()),
                    project_id=project_id,
                    workspace_id=project.workspace_id,
                    tool_type=project.tool_type,
                    kind=AssetKind.generated_video,
                    source_type=AssetSourceType.generated,
                    status=status,
                    created_at=now,
                    updated_at=now,
                    video_url=url,
                    local_path=local_path,
                    prompt=None,
                    tags=[project.tool_type.value, "generated", "video", shot_id],
                    metadata={"shot_id": shot_id, "variant_index": clip.variant_index},
                )
                self._store.add_asset(asset)
                assets.append(asset)
                quality_score = 0.8 if status == AssetStatus.ready else 0.35
                report = QualityReport(
                    quality_id=str(uuid4()),
                    project_id=project_id,
                    asset_id=asset.asset_id,
                    score=quality_score,
                    clarity_score=quality_score,
                    consistency_score=quality_score,
                    compliance_score=0.95 if status == AssetStatus.ready else 0.4,
                    passed=quality_score >= 0.7,
                    issues=[] if quality_score >= 0.7 else ["视频片段不可用或超时失败"],
                    suggestions=[] if quality_score >= 0.7 else ["建议重试该镜头候选"],
                    created_at=now,
                )
                self._store.add_quality_report(report)
                self._store.update_project(
                    project_id,
                    lambda p: (
                        setattr(p, "asset_ids", [*p.asset_ids, asset.asset_id]),
                        setattr(p, "quality_report_ids", [*p.quality_report_ids, report.quality_id]),
                    ),
                )

    def _log(
        self,
        project_id: str,
        level: LogLevel,
        stage: str,
        message: str,
        details: dict[str, Any] | None = None,
        render_id: str | None = None,
    ) -> None:
        self._store.add_project_log(
            project_id=project_id,
            level=level,
            stage=stage,
            message=message,
            details=details,
            render_id=render_id,
        )
        plain = f"[{project_id}] {stage} - {message}"
        if level == LogLevel.error:
            logger.error(plain, extra={"details": details or {}, "render_id": render_id})
        elif level == LogLevel.warning:
            logger.warning(plain, extra={"details": details or {}, "render_id": render_id})
        else:
            logger.info(plain, extra={"details": details or {}, "render_id": render_id})
