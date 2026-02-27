from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas import (
    AssetKind,
    AssetRecord,
    AssetSourceType,
    AssetStatus,
    GenerateImagesRequest,
    GenerateVideosRequest,
    ImagePromptScript,
    IdentityMode,
    IdentityStatus,
    LogLevel,
    MasterScript,
    PromptInputForm,
    PromptItem,
    ProductBrief,
    PlanShot,
    ProgressStep,
    ProjectPlan,
    ProjectLog,
    ProjectProgress,
    ProjectRecord,
    ProjectStatus,
    QualityLevel,
    QualityReport,
    RenderResponse,
    RenderRecord,
    RenderRequest,
    ReviewAction,
    ReviewDecision,
    ReviewRequest,
    ScenarioType,
    ScriptOption,
    SelectScriptRequest,
    ShotApprovalStatus,
    ShotPlan,
    ShotStage,
    StoryboardStatus,
    TaskRunStatus,
    ToolType,
    VideoPromptScript,
    VisualInsight,
)
from app.services.assembly_service import AssemblyService
from app.services.compliance_service import ComplianceService
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
    ) -> None:
        self._store = store
        self._script_service = script_service
        self._compliance = compliance_service
        self._sora = sora_service
        self._reference_image = reference_image_service
        self._assembly = assembly_service
        self._storage_root = storage_root
        self._storyboard_tasks: dict[str, asyncio.Task[None]] = {}
        self._render_tasks: dict[str, asyncio.Task[None]] = {}
        self._image_tasks: dict[str, asyncio.Task[None]] = {}

    async def create_project(
        self,
        image_bytes: bytes,
        image_mime: str,
        image_suffix: str,
        brief: ProductBrief,
        image_public_url: str | None,
        tool_type: ToolType = ToolType.intro_video_multi_script,
        prompt_inputs: PromptInputForm | None = None,
        scenario_type: ScenarioType = ScenarioType.product_video,
        template_name: str = "general",
        quality_level: QualityLevel = QualityLevel.standard,
        batch_group_id: str | None = None,
        reference_images: list[dict[str, Any]] | None = None,
        reference_image_public_urls: list[str] | None = None,
        identity_required: bool = False,
        camera_inputs: dict[str, Any] | None = None,
    ) -> ProjectRecord:
        project_id = str(uuid4())
        image_path = self._write_image(project_id, image_bytes, image_suffix)

        now = utc_now()
        project = ProjectRecord(
            project_id=project_id,
            tool_type=tool_type,
            status=ProjectStatus.draft,
            task_status=TaskRunStatus.queued,
            created_at=now,
            updated_at=now,
            image_path=str(image_path),
            source_image_b64=base64.b64encode(image_bytes).decode("utf-8"),
            image_public_url=image_public_url,
            brief=brief,
            scenario_type=scenario_type,
            template_name=template_name,
            quality_level=quality_level,
            prompt_inputs=prompt_inputs
            or self._script_service.default_prompt_inputs(tool_type=tool_type, template_name=template_name),
            batch_group_id=batch_group_id,
            identity_required=identity_required,
            identity_mode=IdentityMode.none,
            identity_status=IdentityStatus.pending if identity_required else IdentityStatus.confirmed,
            camera_inputs=dict(camera_inputs or {}),
        )
        self._store.add_project(project)
        input_asset = AssetRecord(
            asset_id=str(uuid4()),
            project_id=project_id,
            tool_type=tool_type,
            kind=AssetKind.input,
            source_type=AssetSourceType.uploaded,
            status=AssetStatus.ready,
            created_at=now,
            updated_at=now,
            local_path=str(image_path),
            image_url=image_public_url,
            tags=["input", tool_type.value],
            metadata={"mime": image_mime, "suffix": image_suffix},
        )
        self._store.add_asset(input_asset)
        self._store.update_project(
            project_id,
            lambda p: setattr(p, "asset_ids", [*p.asset_ids, input_asset.asset_id]),
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
            ref_asset = AssetRecord(
                asset_id=str(uuid4()),
                project_id=project_id,
                tool_type=tool_type,
                kind=AssetKind.input,
                source_type=AssetSourceType.uploaded,
                status=AssetStatus.ready,
                created_at=now,
                updated_at=now,
                local_path=str(ref_path),
                image_url=None,
                tags=["input", "reference", ref_role, tool_type.value],
                metadata={"mime": ref_mime, "suffix": ref_suffix, "role": ref_role},
            )
            self._store.add_asset(ref_asset)
            if ref_role == "identity":
                self._store.update_project(
                    project_id,
                    lambda p, aid=ref_asset.asset_id: (
                        setattr(p, "asset_ids", [*p.asset_ids, aid]),
                        setattr(p, "identity_asset_id", aid),
                        setattr(p, "identity_mode", IdentityMode.uploaded),
                        setattr(p, "identity_status", IdentityStatus.confirmed),
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
            },
        )
        self._store.update_project(project_id, lambda p: setattr(p, "task_status", TaskRunStatus.running))
        if tool_type == ToolType.intro_video_multi_script:
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
        else:
            insight = VisualInsight(
                summary="任务已创建。请进入 Step2 触发AI方案设计，再执行生成。",
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

        return self._get_project_or_raise(project_id)

    async def create_batch_projects(
        self,
        items: list[dict[str, Any]],
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
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
            generated_plan = await self._script_service.generate_project_plan(
                image_bytes=image_bytes,
                image_mime=self._get_project_image_mime(project),
                brief=project.brief,
                scenario_type=project.scenario_type,
                template_name=project.template_name,
                quality_level=project.quality_level,
                tool_type=project.tool_type,
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

    async def generate_project_plan(self, project_id: str, force: bool = False) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        self._ensure_project_not_failed(project=project, action="generate_project_plan")
        if project.project_plan and not force:
            return project
        image_bytes = self._get_project_image_bytes(project)
        plan = await self._script_service.generate_project_plan(
            image_bytes=image_bytes,
            image_mime=self._get_project_image_mime(project),
            brief=project.brief,
            scenario_type=project.scenario_type,
            template_name=project.template_name,
            quality_level=project.quality_level,
            tool_type=project.tool_type,
            strict_json=True,
        )
        self._store.update_project(project_id, lambda p: setattr(p, "project_plan", plan))
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="plan.completed",
            message="项目方案生成完成",
            details={"shot_count": len(plan.shots), "force": force},
        )
        return self._get_project_or_raise(project_id)

    def update_project_plan(self, project_id: str, project_plan: ProjectPlan) -> ProjectRecord:
        project = self._get_project_or_raise(project_id)
        if project_plan.scenario_type != project.scenario_type:
            raise ValueError("project plan scenario_type does not match project scenario_type")
        self._store.update_project(
            project_id,
            lambda p: (
                setattr(p, "project_plan", project_plan),
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
            details={"shot_count": len(project_plan.shots)},
        )
        return self._get_project_or_raise(project_id)

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
        expanded_prompts: list[PromptItem] = []
        for item in prompt_pack.image_prompt_pack:
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
        reference_urls, reference_paths = self._collect_reference_inputs(project)

        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="images.start",
            message="开始生成图片素材",
            details={
                "prompt_count": len(prompt_pack.image_prompt_pack),
                "candidates_per_prompt": candidates_per_prompt,
                "total_tasks": total_prompts,
                "image_aspect_ratio": request.image_aspect_ratio,
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

        def _materialize_image_result(
            shot_id: str,
            ref: Any,
        ) -> tuple[AssetRecord, QualityReport]:
            base_shot_id, variant_index = self._split_variant_shot_id(shot_id)
            status = AssetStatus.ready if (ref.image_url or ref.local_path) else AssetStatus.failed
            asset = AssetRecord(
                asset_id=str(uuid4()),
                project_id=project_id,
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
                    "image_aspect_ratio": request.image_aspect_ratio,
                    "image_resolution": request.image_resolution,
                    "image_output_format": request.image_output_format,
                },
            )
            score = 0.82 if status == AssetStatus.ready else 0.35
            report = QualityReport(
                quality_id=str(uuid4()),
                project_id=project_id,
                asset_id=asset.asset_id,
                score=score,
                clarity_score=score,
                consistency_score=score if ref.source == "generated" else max(0.5, score - 0.2),
                compliance_score=0.95 if status == AssetStatus.ready else 0.4,
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
                level=LogLevel.info,
                stage="images.shot.progress",
                message="单镜头图片已就绪",
                details={
                    "shot_id": shot_id,
                    "done": done_count,
                    "total": total_prompts,
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
                image_aspect_ratio=request.image_aspect_ratio,
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
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="images.completed",
            message="图片素材生成完成",
            details={
                "generated": sum(1 for item in assets if item.status == AssetStatus.ready),
                "failed": sum(1 for item in assets if item.status == AssetStatus.failed),
                "candidates_per_prompt": candidates_per_prompt,
            },
        )
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
            item for item in project_assets if item.source_type == AssetSourceType.generated
        ]
        reviewed_count = sum(1 for item in generated_assets if item.status == AssetStatus.reviewed)
        all_reviewed = bool(generated_assets) and reviewed_count >= len(generated_assets)
        next_task_status = TaskRunStatus.done if all_reviewed else TaskRunStatus.reviewing
        next_status = ProjectStatus.completed if all_reviewed else (
            ProjectStatus.rendering
            if self._get_project_or_raise(project_id).status == ProjectStatus.rendering
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
        return self._get_project_or_raise(project_id), decision

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
        reviewed_assets = sum(1 for item in assets if item.status == AssetStatus.reviewed)
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
                        label="多角度生成",
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
                        done_criteria="目标角度素材全部生成完成",
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
                completion_criteria = "多角度素材全部生成完成，且人工审核全部通过后才算完成"
            else:
                with_identity_step = project.tool_type == ToolType.model_retouch and project.identity_required
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
                target_assets = max(planned_assets, generated_assets, 1)
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
                        label="图像生成",
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
                        done_criteria="目标素材全部生成完成",
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
                )
                progress_profile = "image_weighted"
                completion_criteria = "目标素材全部生成完成，且人工审核全部通过后才算完成"

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
            if not script_selected:
                return "先在 Step2 选择一套主拍摄脚本，再继续生成分镜。"
            if not plan_ready:
                return "先点击“生成/刷新AI方案”，确认镜头规划。"
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
            if not plan_ready:
                return "先点击“生成/刷新AI方案”，让AI输出图像执行计划。"
            if not prompts_ready:
                return "先点击“编译提示词”，确认每张图的生成提示词。"
            if project.identity_required and project.identity_status != IdentityStatus.confirmed:
                return "请先在 Step3 完成替换身份确认，再执行批量精修。"
            if generated_assets == 0:
                return "点击“开始批量生图”，生成第一批候选素材。"
            if reviewed_assets < generated_assets:
                return f"Step5 可直接查看生成结果（已标记 {reviewed_assets}/{generated_assets}）。"
            return "当前素材已生成完成，可继续创建新任务或重试低分素材。"

        if tool == ToolType.multi_angle_camera:
            if not plan_ready:
                return "先在 Step2 调整机位参数并更新方案。"
            if generated_assets == 0:
                return "点击“开始生成”，按当前机位批量生成多角度素材。"
            if reviewed_assets < generated_assets:
                return f"Step4 可直接查看生成结果（已标记 {reviewed_assets}/{generated_assets}）。"
            return "多角度素材已完成，可继续创建新任务。"

        if tool == ToolType.product_image_suite:
            if not plan_ready:
                return "先点击“生成/刷新AI方案”，让AI输出图像执行计划。"
            if not prompts_ready:
                return "先点击“编译提示词”，确认每张图的生成提示词。"
            if generated_assets == 0:
                return "点击“开始批量生图”，生成第一批候选素材。"
            if reviewed_assets < generated_assets:
                return f"Step4 可直接查看生成结果（已标记 {reviewed_assets}/{generated_assets}）。"
            return "当前素材已生成完成，可继续创建新任务或重试低分素材。"

        if tool == ToolType.quick_video_15s:
            if not plan_ready:
                return "先生成AI方案，确保15秒节奏和分镜结构清晰。"
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
        focal_mm = str(camera_inputs.get("focal_mm") or "50")
        distance = str(camera_inputs.get("distance") or "medium")
        presets = self._multi_angle_presets(camera_inputs)
        shots: list[PlanShot] = []
        for idx, preset in enumerate(presets, start=1):
            yaw = int(preset.get("yaw", 0))
            pitch = int(preset.get("pitch", 0))
            label = str(preset.get("label") or f"angle-{idx}")
            stage = ShotStage.feature if idx < len(presets) else ShotStage.proof
            image_prompt = (
                f"{project.brief.product_name}，{label}，yaw {yaw}°，pitch {pitch}°，"
                f"{focal_mm}mm，distance {distance}，AI摄影棚质感，主体比例稳定，材质连续，不要文字logo水印"
            )
            shots.append(
                PlanShot(
                    shot_id=f"angle-{idx}",
                    title=label,
                    intent="输出可用于电商详情页的多角度产品图",
                    duration_sec=4,
                    stage=stage,
                    image_prompt=image_prompt,
                    video_prompt=self._script_service._sanitize_video_prompt(
                        f"{project.brief.product_name} {label} 动态预览，保持相机参数一致，不要文字logo水印"
                    ),
                )
            )
        return ProjectPlan(
            scenario_type=ScenarioType.multi_angle_camera,
            template_name=project.template_name,
            channels=project.brief.channels,
            summary=f"{project.brief.product_name} 多角度拍摄方案",
            planner_notes=["source:camera-inputs", f"preset_count:{len(shots)}"],
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

    async def generate_identity_candidate(
        self,
        project_id: str,
        regenerate: bool = False,
    ) -> tuple[ProjectRecord, AssetRecord]:
        project = self._get_project_or_raise(project_id)
        if project.tool_type != ToolType.model_retouch:
            raise ValueError("identity candidate only supported for model_retouch tool")
        if not project.identity_required:
            raise ValueError("当前任务未开启替换模特流程")
        if project.identity_mode == IdentityMode.uploaded and not regenerate:
            if project.identity_asset_id:
                asset = self._store.get_asset(project.identity_asset_id)
                if asset:
                    return project, asset
        image_path = self._resolve_project_image_path(project)
        reference_urls, reference_paths = self._collect_reference_inputs(project)
        prompt = self._script_service._cleanup_prompt_text(
            f"{project.brief.product_name}替换模特身份锚点图，半身正面，表情自然，皮肤质感真实，"
            "光线均匀，保持写实摄影棚风格，不要文字logo水印。"
            f"{project.brief.creative_direction or ''}"
        )
        refs = await self._reference_image.generate_images_from_prompts(
            image_path=image_path,
            image_public_url=project.image_public_url,
            prompts=[PromptItem(shot_id="identity-candidate", prompt=prompt)],
            image_aspect_ratio="3:4",
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
            tool_type=project.tool_type,
            kind=AssetKind.input,
            source_type=AssetSourceType.generated,
            status=status,
            created_at=utc_now(),
            updated_at=utc_now(),
            image_url=result.image_url,
            local_path=result.local_path,
            prompt=prompt,
            tags=["input", "reference", "identity", "generated", project.tool_type.value],
            metadata={"role": "identity_candidate", "source": result.source},
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
            details={"asset_id": asset.asset_id, "status": status.value},
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
                setattr(p, "identity_mode", identity_mode),
                setattr(p, "identity_status", IdentityStatus.confirmed),
                setattr(p, "identity_required", True),
                setattr(p, "error_message", None),
            ),
        )
        self._log(
            project_id=project_id,
            level=LogLevel.info,
            stage="identity.candidate.confirmed",
            message="替换模特身份图已确认",
            details={"asset_id": target_asset_id, "identity_mode": identity_mode.value},
        )
        return self._get_project_or_raise(project_id), self._store.get_asset(target_asset_id) or asset

    async def generate_for_project(
        self,
        project_id: str,
        *,
        stage: str = "auto",
        variants_per_shot: int = 2,
        candidates_per_prompt: int = 1,
        async_mode: bool = False,
        image_aspect_ratio: str = "1:1",
        image_resolution: str = "1K",
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
        self._store.update_project(project_id, lambda p: setattr(p, "task_status", TaskRunStatus.running))

        if tool in {ToolType.product_image_suite, ToolType.model_retouch, ToolType.multi_angle_camera}:
            if tool == ToolType.model_retouch and project.identity_required and project.identity_status != IdentityStatus.confirmed:
                raise ValueError("请先在身份确认步骤确认替换模特图，再执行批量精修。")
            if tool == ToolType.multi_angle_camera and not project.project_plan:
                await self.generate_multi_angle_plan(project_id=project_id, force=False)
            project_row, assets, reports = await self.generate_images_for_project(
                project_id=project_id,
                request=GenerateImagesRequest(
                    regenerate=normalized_stage == "regenerate",
                    async_mode=async_mode,
                    candidates_per_prompt=max(1, candidates_per_prompt),
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
        return self._store.get_project(project_id)

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

    def get_dashboard_kpi(self) -> dict[str, int]:
        projects = self._store.list_projects(limit=10000)
        assets = self._store.list_assets_global(limit=100000)
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
        urls: list[str] = []
        paths: list[Path] = []
        main_image_path = Path(project.image_path).resolve()
        for asset in self._store.list_assets(project.project_id):
            if asset.kind != AssetKind.input:
                continue
            tags = {item.lower() for item in asset.tags}
            if "reference" not in tags:
                continue
            if asset.image_url:
                urls.append(asset.image_url)
                continue
            if asset.local_path:
                candidate = Path(asset.local_path)
                if candidate.is_file():
                    try:
                        if candidate.resolve() != main_image_path:
                            paths.append(candidate)
                    except Exception:
                        paths.append(candidate)
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
