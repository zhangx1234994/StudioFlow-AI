from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    draft = "draft"
    scripted = "scripted"
    rendering = "rendering"
    completed = "completed"
    failed = "failed"


class StoryboardStatus(str, Enum):
    not_started = "not_started"
    generating = "generating"
    ready = "ready"
    confirmed = "confirmed"
    failed = "failed"


class LogLevel(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


class ScenarioType(str, Enum):
    product_image_suite = "product_image_suite"
    model_retouch = "model_retouch"
    multi_angle_camera = "multi_angle_camera"
    product_video = "product_video"


class ToolType(str, Enum):
    intro_video_multi_script = "intro_video_multi_script"
    product_image_suite = "product_image_suite"
    model_retouch = "model_retouch"
    quick_video_15s = "quick_video_15s"
    multi_angle_camera = "multi_angle_camera"


class QualityLevel(str, Enum):
    economy = "economy"
    standard = "standard"
    premium = "premium"


class ShotStage(str, Enum):
    hook = "hook"
    feature = "feature"
    proof = "proof"
    cta = "cta"


class PresenterMode(str, Enum):
    none = "none"
    no_face = "no_face"
    face = "face"


class PresenterSource(str, Enum):
    virtual = "virtual"
    uploaded = "uploaded"


class GoalType(str, Enum):
    conversion = "conversion"
    awareness = "awareness"
    seeding = "seeding"
    review = "review"


class ShotApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    regenerating = "regenerating"


class IdentityMode(str, Enum):
    none = "none"
    uploaded = "uploaded"
    generated = "generated"


class IdentityStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"


class AssetKind(str, Enum):
    input = "input"
    plan_keyframe = "plan_keyframe"
    generated_image = "generated_image"
    generated_video = "generated_video"
    selected_output = "selected_output"


class AssetStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"
    reviewed = "reviewed"
    rejected = "rejected"


class AssetSourceType(str, Enum):
    uploaded = "uploaded"
    generated = "generated"


class TaskRunStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    reviewing = "reviewing"
    done = "done"


class ReviewAction(str, Enum):
    approve = "approve"
    reject = "reject"
    regenerate = "regenerate"


class PromptInputForm(BaseModel):
    goal: str = Field(default="提升转化", max_length=160)
    style: str = Field(default="真实质感，轻商业感", max_length=160)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    shot_focus: str = Field(default="开场钩子、核心卖点、证据收束", max_length=240)


class ProductBrief(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=80)
    target_audience: str = Field(default="注重体验和性价比的人群", max_length=200)
    platform: str = Field(default="douyin", max_length=40)
    price_band: str = Field(default="未填写", max_length=80)
    key_features: list[str] = Field(default_factory=list, max_length=8)
    cta_text: str = Field(default="点击了解详情", max_length=60)
    desired_duration_sec: int = Field(default=40, ge=15, le=50)
    tone: str = Field(default="真实、克制、有钩子", max_length=80)
    content_template: str = Field(default="talking_head", max_length=40)
    presenter_mode: PresenterMode = PresenterMode.none
    presenter_source: PresenterSource = PresenterSource.virtual
    presenter_image_url: str | None = None
    goal_type: GoalType = GoalType.conversion
    evidence_points: list[str] = Field(default_factory=list, max_length=12)
    compliance_blocklist: list[str] = Field(default_factory=list, max_length=20)
    channels: list[str] = Field(default_factory=lambda: ["douyin"], max_length=6)
    creative_direction: str = Field(default="", max_length=300)


class BatchItem(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=80)
    image_public_url: str | None = None
    target_audience: str = Field(default="注重体验和性价比的人群", max_length=200)
    platform: str = Field(default="douyin", max_length=40)
    key_features: list[str] = Field(default_factory=list, max_length=8)
    desired_duration_sec: int = Field(default=15, ge=15, le=50)


class VisualInsight(BaseModel):
    summary: str
    visible_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class PlanShot(BaseModel):
    shot_id: str
    title: str
    intent: str
    duration_sec: int = Field(default=5, ge=3, le=8)
    stage: ShotStage = ShotStage.feature
    image_prompt: str
    video_prompt: str
    retouch_prompt: str | None = None
    retouch_goal: str | None = None
    identity_lock_rules: list[str] = Field(default_factory=list)
    local_edit_instructions: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)


class ProjectPlan(BaseModel):
    scenario_type: ScenarioType
    template_name: str = "general"
    channels: list[str] = Field(default_factory=lambda: ["douyin"])
    summary: str
    planner_notes: list[str] = Field(default_factory=list)
    shots: list[PlanShot] = Field(default_factory=list)


class PromptItem(BaseModel):
    shot_id: str
    prompt: str


class PromptPack(BaseModel):
    planner_prompt: str
    image_prompt_pack: list[PromptItem] = Field(default_factory=list)
    video_prompt_pack: list[PromptItem] = Field(default_factory=list)
    guardrail_report: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class ShotPlan(BaseModel):
    shot_id: str
    stage: ShotStage
    duration_sec: int = Field(ge=3, le=8)
    visual_prompt: str
    reference_image_prompt: str | None = None
    motion_direction: str | None = None
    voiceover_direction: str | None = None
    narration: str
    on_screen_text: str


class ScriptOption(BaseModel):
    script_id: str
    title: str
    format_type: str = Field(default="口播讲解", max_length=20)
    strategy_note: str
    compliance_note: str
    total_duration_sec: int = Field(ge=15, le=50)
    shots: list[ShotPlan] = Field(min_length=3, max_length=10)


class MasterScript(BaseModel):
    script_id: str
    title: str
    format_type: str = Field(default="口播讲解", max_length=20)
    strategy_note: str
    compliance_note: str
    total_duration_sec: int = Field(ge=15, le=50)
    shots: list[ShotPlan] = Field(min_length=3, max_length=10)


class ImagePromptShot(BaseModel):
    shot_id: str
    prompt: str


class VideoPromptShot(BaseModel):
    shot_id: str
    prompt: str


class ImagePromptScript(BaseModel):
    script_id: str
    shots: list[ImagePromptShot] = Field(default_factory=list)


class VideoPromptScript(BaseModel):
    script_id: str
    shots: list[VideoPromptShot] = Field(default_factory=list)


class ShotReference(BaseModel):
    shot_id: str
    source: str
    image_url: str | None = None
    local_path: str | None = None
    prompt: str | None = None


class ClipVariant(BaseModel):
    shot_id: str
    variant_index: int
    score: float
    task_id: str | None = None
    video_url: str | None = None
    local_path: str | None = None


class AssetRecord(BaseModel):
    asset_id: str
    project_id: str
    tool_type: ToolType = ToolType.intro_video_multi_script
    kind: AssetKind
    source_type: AssetSourceType = AssetSourceType.generated
    status: AssetStatus
    created_at: datetime
    updated_at: datetime
    image_url: str | None = None
    video_url: str | None = None
    local_path: str | None = None
    source_asset_id: str | None = None
    prompt: str | None = None
    version: int = 1
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QualityReport(BaseModel):
    quality_id: str
    project_id: str
    asset_id: str | None = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    clarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    consistency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    compliance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    passed: bool = False
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    created_at: datetime


class ReviewDecision(BaseModel):
    decision_id: str
    project_id: str
    asset_id: str
    action: ReviewAction
    reason: str | None = None
    reviewer: str = "human"
    created_at: datetime


class ProjectRecord(BaseModel):
    project_id: str
    tool_type: ToolType = ToolType.intro_video_multi_script
    status: ProjectStatus
    task_status: TaskRunStatus = TaskRunStatus.queued
    created_at: datetime
    updated_at: datetime
    image_path: str
    source_image_b64: str | None = None
    image_public_url: str | None = None
    brief: ProductBrief
    scenario_type: ScenarioType = ScenarioType.product_video
    template_name: str = "general"
    quality_level: QualityLevel = QualityLevel.standard
    prompt_inputs: PromptInputForm = Field(default_factory=PromptInputForm)
    batch_group_id: str | None = None
    identity_required: bool = False
    identity_mode: IdentityMode = IdentityMode.none
    identity_status: IdentityStatus = IdentityStatus.pending
    identity_asset_id: str | None = None
    camera_inputs: dict[str, Any] = Field(default_factory=dict)
    insight: VisualInsight | None = None
    project_plan: ProjectPlan | None = None
    prompt_pack: PromptPack | None = None
    script_options: list[ScriptOption] = Field(default_factory=list)
    selected_script: ScriptOption | None = None
    master_script: MasterScript | None = None
    image_prompt_script: ImagePromptScript | None = None
    video_prompt_script: VideoPromptScript | None = None
    shot_approvals: dict[str, ShotApprovalStatus] = Field(default_factory=dict)
    storyboard_status: StoryboardStatus = StoryboardStatus.not_started
    storyboard_references: dict[str, ShotReference] = Field(default_factory=dict)
    storyboard_error_message: str | None = None
    render_id: str | None = None
    asset_ids: list[str] = Field(default_factory=list)
    quality_report_ids: list[str] = Field(default_factory=list)
    review_decision_ids: list[str] = Field(default_factory=list)
    error_message: str | None = None


class ProjectTaskItem(BaseModel):
    project_id: str
    tool_type: ToolType
    product_name: str
    scenario_type: ScenarioType
    template_name: str
    status: ProjectStatus
    storyboard_status: StoryboardStatus
    current_stage: str
    progress_percent: int = Field(default=0, ge=0, le=100)
    progress_label: str = ""
    batch_group_id: str | None = None
    render_id: str | None = None
    updated_at: datetime


class ProjectLog(BaseModel):
    event_id: str
    project_id: str
    timestamp: datetime
    level: LogLevel
    stage: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    render_id: str | None = None


class TaskRun(BaseModel):
    run_id: str
    project_id: str
    tool_type: ToolType
    stage: str
    status: TaskRunStatus
    created_at: datetime
    updated_at: datetime
    message: str | None = None


class ShotEdit(BaseModel):
    shot_id: str
    narration: str | None = None
    on_screen_text: str | None = None
    visual_prompt: str | None = None
    reference_image_prompt: str | None = None
    motion_direction: str | None = None
    voiceover_direction: str | None = None
    duration_sec: int | None = Field(default=None, ge=3, le=8)


class SelectScriptRequest(BaseModel):
    script_id: str
    edits: list[ShotEdit] = Field(default_factory=list)


class UpdateMasterScriptRequest(BaseModel):
    master_script: MasterScript


class DerivePromptsRequest(BaseModel):
    force: bool = False


class UpdatePromptInputsRequest(BaseModel):
    prompt_inputs: PromptInputForm


class GeneratePlanRequest(BaseModel):
    force: bool = False


class RetryProjectRequest(BaseModel):
    stage: str | None = None
    async_mode: bool = False


class IdentityActionRequest(BaseModel):
    asset_id: str | None = None


class IdentityActionResponse(BaseModel):
    project: ProjectRecord
    asset: AssetRecord | None = None


class CameraAngleInput(BaseModel):
    label: str | None = None
    yaw: int = Field(default=0, ge=-180, le=180)
    pitch: int = Field(default=0, ge=-45, le=45)


class CameraInputsRequest(BaseModel):
    yaw: int = Field(default=0, ge=-180, le=180)
    pitch: int = Field(default=0, ge=-45, le=45)
    distance: Literal["near", "medium", "far"] = "medium"
    focal_mm: Literal["35", "50", "85"] = "50"
    aspect_ratio: Literal["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9"] = "1:1"
    presets: list[CameraAngleInput] = Field(default_factory=list, max_length=24)


class UpdatePlanRequest(BaseModel):
    project_plan: ProjectPlan


class ApproveStoryboardShotRequest(BaseModel):
    shot_id: str
    status: ShotApprovalStatus


class GenerateStoryboardRequest(BaseModel):
    regenerate: bool = False
    async_mode: bool = False


class RegenerateStoryboardShotRequest(BaseModel):
    shot_id: str
    async_mode: bool = False


class GenerateImagesRequest(BaseModel):
    regenerate: bool = False
    async_mode: bool = False
    candidates_per_prompt: int = Field(default=1, ge=1, le=4)
    image_aspect_ratio: Literal[
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
        "auto",
    ] = "1:1"
    image_resolution: Literal["1K", "2K", "4K"] = "1K"
    image_output_format: Literal["png", "jpg"] = "png"


class GenerateVideosRequest(BaseModel):
    variants_per_shot: int = Field(default=2, ge=1, le=4)
    async_mode: bool = False
    with_voiceover: bool = False
    video_aspect_ratio: Literal["portrait", "landscape"] = "portrait"
    video_n_frames: Literal["10", "15"] = "10"
    video_size: Literal["standard", "high"] = "standard"
    video_remove_watermark: bool = True
    video_upload_method: Literal["s3", "oss"] = "s3"


class GenerateRequest(BaseModel):
    stage: str = Field(default="auto", max_length=40)
    variants_per_shot: int = Field(default=2, ge=1, le=4)
    candidates_per_prompt: int = Field(default=1, ge=1, le=4)
    async_mode: bool = False
    image_aspect_ratio: Literal[
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
        "auto",
    ] = "1:1"
    image_resolution: Literal["1K", "2K", "4K"] = "1K"
    image_output_format: Literal["png", "jpg"] = "png"
    video_aspect_ratio: Literal["portrait", "landscape"] = "portrait"
    video_n_frames: Literal["10", "15"] = "10"
    video_size: Literal["standard", "high"] = "standard"
    video_remove_watermark: bool = True
    video_upload_method: Literal["s3", "oss"] = "s3"


class ReviewRequest(BaseModel):
    asset_id: str
    action: ReviewAction
    reason: str | None = None


class RenderRequest(BaseModel):
    variants_per_shot: int = Field(default=2, ge=1, le=4)
    preferred_variants: dict[str, int] = Field(default_factory=dict)
    async_mode: bool = False
    video_aspect_ratio: Literal["portrait", "landscape"] = "portrait"
    video_n_frames: Literal["10", "15"] = "10"
    video_size: Literal["standard", "high"] = "standard"
    video_remove_watermark: bool = True
    video_upload_method: Literal["s3", "oss"] = "s3"


class RenderRecord(BaseModel):
    render_id: str
    project_id: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    total_variants: int = 0
    completed_variants: int = 0
    failed_variants: int = 0
    running_variants: int = 0
    variants: dict[str, list[ClipVariant]] = Field(default_factory=dict)
    references: dict[str, ShotReference] = Field(default_factory=dict)
    chosen_variants: dict[str, ClipVariant] = Field(default_factory=dict)
    output_video_path: str | None = None
    subtitle_path: str | None = None
    manifest_path: str | None = None
    assembly_note: str | None = None
    error_message: str | None = None


class ProgressStep(BaseModel):
    step_id: str
    label: str
    status: str
    completed: int = 0
    total: int = 0
    weight: int = 0
    entry_criteria: str = ""
    done_criteria: str = ""
    error_code: str | None = None


class ToolTemplateOption(BaseModel):
    tool_type: ToolType
    template_name: str
    display_name: str
    description: str
    planner_focus: list[str] = Field(default_factory=list)
    default_form: dict[str, Any] = Field(default_factory=dict)


class ProjectProgress(BaseModel):
    project_id: str
    status: ProjectStatus
    task_status: TaskRunStatus = TaskRunStatus.queued
    storyboard_status: StoryboardStatus
    current_stage: str
    next_action: str = ""
    steps: list[ProgressStep]
    plan_ready: bool = False
    prompts_ready: bool = False
    generated_assets: int = 0
    reviewed_assets: int = 0
    storyboard_done: int = 0
    storyboard_total: int = 0
    approved_shots: int = 0
    total_shots: int = 0
    render_completed: int = 0
    render_total: int = 0
    render_failed: int = 0
    render_running: int = 0
    progress_percent_weighted: int = Field(default=0, ge=0, le=100)
    progress_profile: Literal["image_weighted", "video_weighted"] = "image_weighted"
    step_weights: dict[str, int] = Field(default_factory=dict)
    completion_criteria: str = ""
    updated_at: datetime
    render_id: str | None = None


class CreateProjectResponse(BaseModel):
    project: ProjectRecord


class BatchCreateProjectResponse(BaseModel):
    projects: list[ProjectRecord]


class BatchCreateModelRetouchResponse(BaseModel):
    batch_group_id: str
    project_ids: list[str] = Field(default_factory=list)
    created_count: int = 0
    projects: list[ProjectRecord] = Field(default_factory=list)


class RenderResponse(BaseModel):
    project: ProjectRecord
    render: RenderRecord


class GenerateAssetsResponse(BaseModel):
    project: ProjectRecord
    assets: list[AssetRecord]
    quality_reports: list[QualityReport]


class ReviewResponse(BaseModel):
    project: ProjectRecord
    decision: ReviewDecision


class DashboardKpi(BaseModel):
    total_projects: int = 0
    running_projects: int = 0
    failed_projects: int = 0
    done_projects: int = 0
    total_assets: int = 0
    uploaded_assets: int = 0
    generated_assets: int = 0


class BatchCreateRequest(BaseModel):
    tool_type: ToolType = ToolType.intro_video_multi_script
    scenario_type: ScenarioType
    template_name: str = "general"
    quality_level: QualityLevel = QualityLevel.standard
    channels: list[str] = Field(default_factory=lambda: ["douyin"])
    items: list[BatchItem] = Field(min_length=1, max_length=100)
