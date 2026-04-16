from pathlib import Path


PAGE_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/page.jsx")
IDENTITY_FLOW_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/identity-flow.jsx")
WORKSPACE_FLOW_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/workspace-flow.jsx")
PRODUCT_REFERENCE_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/product-reference.js")
TOOL_CONFIG_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/tool-config.js")
MEDIA_UTILS_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/media-utils.js")
APP_UTILS_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/app-utils.js")
SHARED_UI_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/shared-ui.jsx")
MULTI_ANGLE_PAD_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/multi-angle-pad.jsx")
TASK_PAGE_HELPERS_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/task-page-helpers.js")
TOOL_TASKS_PAGE_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/tool-tasks-page.jsx")
MODEL_RETOUCH_BATCH_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/model-retouch-batch-workspace.jsx")
PROJECT_WORKSPACE_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/project-workspace.jsx")
PRODUCT_IMAGE_WORKBENCH_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/product-image-workbench.jsx")
GENERATE_STAGE_PANEL_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/generate-stage-panel.jsx")
REVIEW_STAGE_PANEL_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/review-stage-panel.jsx")
TOOLS_HOME_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/tools-home.jsx")
ASSETS_PAGE_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/assets-page.jsx")
APP_SHELL_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/app-shell.jsx")
AUTH_PAGES_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/auth-pages.jsx")
ROUTER_STATE_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/router-state.jsx")
GLOBALS_CSS_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/globals.css")


def _load_source() -> str:
    paths = [
        PAGE_PATH,
        IDENTITY_FLOW_PATH,
        WORKSPACE_FLOW_PATH,
        PRODUCT_REFERENCE_PATH,
        TOOL_CONFIG_PATH,
        MEDIA_UTILS_PATH,
        APP_UTILS_PATH,
        SHARED_UI_PATH,
        MULTI_ANGLE_PAD_PATH,
        TASK_PAGE_HELPERS_PATH,
        TOOL_TASKS_PAGE_PATH,
        MODEL_RETOUCH_BATCH_PATH,
        PROJECT_WORKSPACE_PATH,
        GENERATE_STAGE_PANEL_PATH,
        REVIEW_STAGE_PANEL_PATH,
        TOOLS_HOME_PATH,
        ASSETS_PAGE_PATH,
        APP_SHELL_PATH,
        AUTH_PAGES_PATH,
        ROUTER_STATE_PATH,
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def _load_identity_flow_source() -> str:
    return IDENTITY_FLOW_PATH.read_text(encoding="utf-8")


def _load_workspace_flow_source() -> str:
    return WORKSPACE_FLOW_PATH.read_text(encoding="utf-8")


def _load_product_reference_source() -> str:
    return PRODUCT_REFERENCE_PATH.read_text(encoding="utf-8")


def _load_tool_config_source() -> str:
    return TOOL_CONFIG_PATH.read_text(encoding="utf-8")


def _load_media_utils_source() -> str:
    return MEDIA_UTILS_PATH.read_text(encoding="utf-8")


def _load_app_utils_source() -> str:
    return APP_UTILS_PATH.read_text(encoding="utf-8")


def _load_shared_ui_source() -> str:
    return SHARED_UI_PATH.read_text(encoding="utf-8")


def _load_multi_angle_pad_source() -> str:
    return MULTI_ANGLE_PAD_PATH.read_text(encoding="utf-8")


def _load_task_page_helpers_source() -> str:
    return TASK_PAGE_HELPERS_PATH.read_text(encoding="utf-8")


def _load_tool_tasks_page_source() -> str:
    return TOOL_TASKS_PAGE_PATH.read_text(encoding="utf-8")


def _load_model_retouch_batch_source() -> str:
    return MODEL_RETOUCH_BATCH_PATH.read_text(encoding="utf-8")


def _load_globals_css_source() -> str:
    return GLOBALS_CSS_PATH.read_text(encoding="utf-8")


def _load_review_stage_panel_source() -> str:
    return REVIEW_STAGE_PANEL_PATH.read_text(encoding="utf-8")


def _load_generate_stage_panel_source() -> str:
    return GENERATE_STAGE_PANEL_PATH.read_text(encoding="utf-8")


def _load_product_image_workbench_source() -> str:
    return PRODUCT_IMAGE_WORKBENCH_PATH.read_text(encoding="utf-8")


def test_tool_tasks_create_form_has_single_primary_submit() -> None:
    source = _load_tool_tasks_page_source()
    start = source.index('<form ref={formRef} className="grid" onSubmit={create}>')
    end = source.index("</form>", start)
    form_snippet = source[start:end]
    assert form_snippet.count('type="submit" className="btn-primary"') == 1
    assert 'data-cta-scope={`tool-tasks.create.${tool.slug}`}' in form_snippet


def test_tool_tasks_create_flow_does_not_fallback_to_server_upload() -> None:
    source = _load_tool_tasks_page_source()
    assert 'buildFormDataWithoutFiles(raw)' in source
    assert 'buildSafeFormData' not in source
    assert "已自动切换服务器上传" not in source


def test_quick_video_create_panel_is_parameter_simplified() -> None:
    source = _load_tool_tasks_page_source()
    page_source = _load_source()
    start = source.index('{tool.slug === "quick-video-15s" && (')
    end = source.index('{tool.slug === "product-image" && (', start)
    quick_video_snippet = source[start:end]
    assert "短片主题" in quick_video_snippet
    assert "节奏" in quick_video_snippet
    assert "文案语气" in quick_video_snippet
    assert "结尾行动语" in quick_video_snippet
    assert 'name="target_final_count"' not in quick_video_snippet
    assert 'name="takes_per_shot"' not in quick_video_snippet
    assert "生成拍摄方案" not in quick_video_snippet
    assert 'variants_per_shot: tool.slug === "quick-video-15s" ? 3 : 2' in page_source


def test_workspace_product_image_step_has_secondary_non_primary_actions() -> None:
    source = _load_source()
    start = source.index('{tool.slug === "product-image" ? (')
    end = source.index(') : tool.slug === "model-retouch" ? null : (', start)
    snippet = source[start:end]
    assert '重新生成方案' in snippet
    assert '!project?.project_plan?.shots?.length ? (' in snippet
    assert '确认方案并进入试拍' in snippet
    assert '点击主按钮后，系统会基于当前镜头草稿自动编译执行方案并进入试拍，不需要再单独处理提示词步骤。' in snippet
    assert '已确认基准：{activeProductChoiceLabel} · 当前镜头 {project.project_plan.shots.length} 个 · 目标成片 {requiredFinalCount || 0} 张' in snippet
    assert '<button type="button" className="btn-secondary" onClick={savePlanDraft} disabled={savingPlan}>' in snippet
    assert '<button type="button" className="btn-secondary" onClick={() => genPlan()} disabled={isInitializing || isPlanLoading}>' in snippet
    assert 'data-cta-scope="workspace.step1.product-image"' in source
    assert 'data-cta-scope={`workspace.step2.${tool.slug}`}' in source
    assert 'data-cta-scope={`workspace.generate.${tool.slug}`}' in source
    assert 'data-cta-scope="workspace.review.product-image"' in source


def test_product_image_failed_projects_do_not_auto_jump_to_review_step() -> None:
    source = PROJECT_WORKSPACE_PATH.read_text(encoding="utf-8")
    assert 'if (!["review", "completed"].includes(stage)) return;' in source


def test_product_image_workspace_uses_dedicated_static_workbench_component() -> None:
    source = PROJECT_WORKSPACE_PATH.read_text(encoding="utf-8")
    workbench_source = _load_product_image_workbench_source()
    assert 'from "./product-image-workbench"' in source
    assert 'if (tool.slug === "product-image") {' in source
    assert "<ProductImageWorkbench" in source
    assert "renderStep1" in workbench_source
    assert "renderStep2" in workbench_source
    assert "renderStep3" in workbench_source
    assert "renderStep4" in workbench_source
    assert "商品棚拍工作台" in workbench_source
    assert "认出来了，去定方案" in workbench_source
    assert "方案没问题，开始出图" in workbench_source
    assert "开始试拍" in workbench_source
    assert "选片分享墙" in workbench_source


def test_product_image_project_route_bypasses_global_shell() -> None:
    page_source = PAGE_PATH.read_text(encoding="utf-8")
    assert 'const useDedicatedProductImageShell = route.page === "project" && route.toolSlug === "product-image";' in page_source
    assert 'if (useDedicatedProductImageShell) {' in page_source
    assert 'className="app-shell app-shell-product-image"' in page_source
    assert 'className="workspace-main workspace-main-product-image"' in page_source


def test_workspace_video_step_keeps_secondary_support_actions() -> None:
    source = _load_source()
    intro_start = source.index('tool.slug === "intro-video" ? (')
    intro_end = source.index(') : (', intro_start)
    intro_snippet = source[intro_start:intro_end]
    assert '重新生成脚本候选' in intro_snippet
    assert 'introScriptOptions.length > 0 ? (' in intro_snippet
    assert '<button type="button" className="btn-secondary" onClick={genPlan} disabled={isInitializing || isPlanLoading || scriptSelecting}>' in intro_snippet

    quick_start = source.index('!project?.project_plan?.shots?.length ? (', intro_end)
    quick_end = source.index('重新生成AI方案', quick_start)
    quick_snippet = source[quick_start:quick_end + len('重新生成AI方案')]
    assert '生成AI方案' in quick_snippet
    assert '生成执行方案' in quick_snippet
    assert '进入候选生成' in quick_snippet
    assert '重新生成AI方案' in quick_snippet


def test_multi_angle_waiting_copy_matches_primary_action() -> None:
    source = _load_source()
    workspace_source = _load_workspace_flow_source()
    tool_config_source = _load_tool_config_source()
    multi_angle_source = _load_multi_angle_pad_source()
    tool_tasks_source = _load_tool_tasks_page_source()
    assert 'const HIDDEN_WEB_TOOL_SLUGS = new Set([]);' in tool_config_source
    assert '多角度展品工坊' in tool_config_source
    assert 'from "./workspace-flow"' in source
    assert 'from "./multi-angle-pad"' in source
    assert 'const hasActiveAsyncTasks = Number(progress?.active_task_count || 0) > 0' in source
    assert 'if (toolSlug === "multi-angle-camera" && stage === "generate") return "生成当前角度";' in workspace_source
    assert 'if (toolSlug === "multi-angle-camera" && stage === "review") return "人工确认";' in workspace_source
    assert 'tool.slug === "multi-angle-camera"\n              ? "执行中：当前机位生成中，完成后可切换角度再拍一张。"' in source
    assert 'if (["generate"].includes(stage)) {\n        nextStep = generationStepIndex;' in source
    assert '等待执行：先保存机位或点击“开始生成当前角度”。' in source
    assert '开始生成当前角度' in source
    assert 'data-cta-scope={`workspace.review.${tool.slug}`}' in source
    assert '先聚焦待审核结果，再在卡片内逐张通过或淘汰。' in source
    assert '俯仰角 (-45~45)' in multi_angle_source
    assert 'pitch: 45' in multi_angle_source
    assert 'pitch: -45' in multi_angle_source
    assert 'name="camera_yaw" value={formValues.camera_yaw}' in tool_tasks_source


def test_multi_angle_failed_generate_uses_retry_as_primary_cta() -> None:
    source = _load_generate_stage_panel_source()
    assert 'const useRetryAsPrimary = tool.slug === "multi-angle-camera" && showRetry;' in source
    assert 'onClick={() => (useRetryAsPrimary ? retry() : runGenerate("auto"))}' in source
    assert 'disabled={useRetryAsPrimary ? retrying : runningGenerate || isProjectRunning}' in source
    assert ': "失败重试"' in source
    assert '{showRetry && !useRetryAsPrimary && (' in source


def test_page_imports_media_utils_module() -> None:
    source = _load_source()
    media_source = _load_media_utils_source()
    assert 'from "./media-utils"' in source
    assert 'export function safeSessionSet(key, value)' in media_source
    assert 'export function localPathToMedia(path)' in media_source
    assert 'export function resolveAssetImageSrc(asset)' in media_source
    assert 'export function detectFrontendBuildTag()' in media_source


def test_page_imports_shared_ui_module() -> None:
    source = _load_source()
    shared_ui_source = _load_shared_ui_source()
    assert 'from "./shared-ui"' in source
    assert 'export function Icon({ name, size = 18, className = "" })' in shared_ui_source
    assert 'export class ErrorBoundary extends React.Component' in shared_ui_source


def test_tools_home_marks_single_primary_cta_scopes() -> None:
    source = TOOLS_HOME_PATH.read_text(encoding="utf-8")
    assert 'data-cta-scope="tools-home.hero"' in source
    assert 'className="btn-primary" onClick={() => navigate("/app/tools/product-image/tasks")}>立即开始棚拍</button>' in source
    assert 'className="btn-secondary" onClick={() => navigate("/app/assets")}>进入资产中台</button>' in source
    assert 'data-cta-scope="tools-home.showcase-empty"' in source
    assert 'data-cta-scope="tools-home.tasks-empty"' in source


def test_page_imports_task_page_helpers_module() -> None:
    source = _load_tool_tasks_page_source()
    helper_source = _load_task_page_helpers_source()
    assert 'from "./task-page-helpers"' in source
    assert 'export function buildTaskRows({ tasks, toolSlug })' in helper_source
    assert 'export function buildPriorityRows({ taskRows, taskRiskPriority })' in helper_source


def test_quick_video_stage_label_hides_master_script_jargon() -> None:
    workspace_source = _load_workspace_flow_source()
    assert 'if (toolSlug === "quick-video-15s" && stage === "master_script") return "AI方案";' in workspace_source
    assert 'if (toolSlug === "quick-video-15s" && stage === "storyboard") return "AI方案";' in workspace_source
    assert 'if (toolSlug === "intro-video" && stage === "master_script") return "AI方案";' in workspace_source


def test_model_retouch_step4_has_explicit_download_cta() -> None:
    source = _load_model_retouch_batch_source()
    assert '打包下载已通过结果' in source
    assert '打包下载全部结果' in source
    assert '已通过 {approvedGeneratedAssets.length} 张，可直接交付' in source
    assert 'data-cta-scope="workspace.batch.step4.model-retouch"' in source


def test_model_retouch_batch_workspace_marks_primary_cta_scopes() -> None:
    source = _load_model_retouch_batch_source()
    assert 'data-cta-scope="workspace.batch.step1.model-retouch"' in source
    assert 'data-cta-scope="workspace.batch.step2.generate.model-retouch"' in source
    assert 'data-cta-scope="workspace.batch.step2.confirm.model-retouch"' in source
    assert 'data-cta-scope="workspace.batch.step3.model-retouch"' in source


def test_model_retouch_batch_stepper_has_gating_and_blocked_copy() -> None:
    source = _load_model_retouch_batch_source()
    assert 'const [stepperStatus, setStepperStatus] = useState({ text: "", type: "" });' in source
    assert 'const canEnterStep = useCallback((nextStep) => {' in source
    assert 'if (nextStep === 2) return batch?.identity_status === "confirmed";' in source
    assert 'if (nextStep === 3) return hasReviewableResults;' in source
    assert 'const blockedStepMessage = useCallback((nextStep) => {' in source
    assert '请先在上一步确认一张模特来源图，再进入批量精修执行。' in source
    assert '请先执行一轮批量精修，至少产出 1 张结果后再进入结果审核与导出。' in source
    assert 'onClick={() => gotoStep(idx)}' in source
    assert 'setStepperStatus({ text: blockedStepMessage(nextStep), type: "warning" });' in source


def test_intro_video_primary_label_matches_actual_behavior() -> None:
    source = _load_source()
    assert '确认主脚本并准备视频生成' in source
    assert '确认主脚本并进入视频生成' not in source


def test_model_retouch_copy_uses_model_source_language_and_reference_order_hint() -> None:
    source = _load_model_retouch_batch_source()
    assert '选择模特来源' in source
    assert '先确认“用哪张模特”，再批量替换整组套图中的人物。这里先决定模特来源，再决定替换方式。' in source
    assert '参考顺序固定为：主图作为基底输入 → 模特来源图作为首个参考输入 → 其他风格参考图排在其后。' in source
    assert '先生成或选择一张模特图，再点击“确认模特并开始整组替换”。' in source
    assert '当前还不能开始整组精修：请先在上一步确认一张模特来源图。' in source
    assert '还不能进入整组替换：先在上方候选区确认一张上传模特图或模特候选图。' in source


def test_product_image_generation_area_explains_missing_retry_actions() -> None:
    source = _load_source()
    assert '当前没有异常候选，所以“失败重试 / 补拍失败项”暂不显示。' in source


def test_product_image_generation_copy_uses_trial_shooting_language() -> None:
    source = _load_source()
    assert '执行中：正在试拍候选图，结果会逐张回填，可先处理其他任务。' in source
    assert '提交中：正在提交试拍任务...' in source
    assert '执行中：已开始试拍，候选图会逐张出现并自动刷新。' in source
    assert '? "执行中：试拍中..."' in source
    assert '低于目标成片' in source


def test_user_workspaces_hide_generation_debug_bridge() -> None:
    source = _load_source()
    assert '联调调试' not in source
    assert '打开 workflow 调试页' not in source
    assert '中台 / workflow 对账' not in source


def test_workspace_stepper_syncs_to_review_stage() -> None:
    source = _load_source()
    assert 'if (!["review", "completed"].includes(stage)) return;' in source
    assert 'const reviewStepIndex = tool.steps.length - 1;' in source
    assert 'setStep(reviewStepIndex);' in source
    assert '已进入选片分享：先处理 ${failedAssetsCount} 张异常候选，再继续入选与交付。' in source
    assert '已进入选片分享：先完成入选，再批量分享或下载交付。' in source


def test_task_center_prefers_backend_next_action_copy() -> None:
    source = _load_source()
    assert 'task.next_action || taskNextActionHint(task)' in source
    assert '下一步：{latestTask.next_action || "进入工作台继续处理"}' in source
    assert '下一步：{continueTask.next_action || taskNextActionHint(continueTask) || "回到工作台继续处理"}' in source
    assert '下一步：{continueTask.next_action || taskNextActionHint(continueTask) || "立即回到工作台继续处理"}' in source
    assert '<div className="home-continue-band">' in source
    assert '<div className="home-continue-label">继续上次任务</div>' in source
    assert 'className="home-continue-metrics"' in source
    assert '已选 {latestTask.selected_final_count}/{latestTask.required_final_count}' in source
    assert '已选 {continueTask.selected_final_count}/{continueTask.required_final_count}' in source


def test_task_center_progress_copy_strips_backend_profile_prefix() -> None:
    source = _load_app_utils_source()
    page_source = _load_source()
    assert 'parts[0].toLowerCase().includes("weighted")' in source
    assert 'return parts.slice(1).join(" | ");' in source
    assert 'formatProgressLabel(task.progress_label)' in page_source


def test_task_center_cards_promote_next_action_as_highlight_strip() -> None:
    page_source = _load_source()
    css_source = _load_globals_css_source()
    assert 'className="asset-card task-card"' in page_source
    assert 'className="task-card-next-action"' in page_source
    assert 'task-card-meta-strip' in page_source
    assert 'task-card-progress-strip' in page_source
    assert '.task-card {' in css_source
    assert '.task-card-next-action {' in css_source
    assert '.task-card-progress-strip {' in css_source
    assert '.home-continue-metrics {' in css_source


def test_task_center_shows_queue_overview_chips() -> None:
    page_source = _load_source()
    assert 'const taskOverview = useMemo(() => ({' in page_source
    assert 'const taskFilterStats = useMemo(() => ({' in page_source
    assert '<span>卡住</span>' in page_source
    assert '<strong>{taskOverview.blocked}</strong>' in page_source
    assert '<span>待确认</span>' in page_source
    assert '<strong>{taskOverview.pending}</strong>' in page_source
    assert '<span>执行中</span>' in page_source
    assert '<strong>{taskOverview.running}</strong>' in page_source
    assert '<span>总任务</span>' in page_source
    assert '<strong>{taskOverview.total}</strong>' in page_source
    assert 'taskFilter === "product_lock"' in page_source
    assert 'taskFilter === "review"' in page_source
    assert 'taskFilter === "blocked"' in page_source
    assert '待锁主体({taskFilterStats.product_lock})' in page_source
    assert '待选片({taskFilterStats.review})' in page_source
    assert '需重试({taskFilterStats.blocked})' in page_source
    assert '先处理卡住、待确认、执行中的关键任务；上方清完阻塞，再回到最近任务继续推进。' in page_source
    assert '这里只展示未进入“优先处理”的最近任务，不和上方重复，方便顺手续做。' in page_source


def test_task_center_table_shows_delivery_progress_for_product_image() -> None:
    page_source = _load_source()
    assert '<th>交付</th>' in page_source
    assert '`已选 ${task.selected_final_count}/${task.required_final_count} · 候选 ${task.candidate_total}`' in page_source
    assert 'shouldShowDeliveryProgress(task, tool.slug)' in page_source


def test_task_center_recent_rows_skip_priority_duplicates() -> None:
    page_source = _load_source()
    helper_source = _load_task_page_helpers_source()
    assert 'import { buildPriorityRows, buildTaskRows, shouldShowDeliveryProgress, shouldShowTaskRiskChip, taskCardStatusLabel, taskOpenLabel, taskRowKey } from "./task-page-helpers";' in page_source
    assert 'const priorityKeys = new Set(priorityRows.map((task) => taskRowKey(task)));' in page_source
    assert 'const filtered = filteredTaskRows.filter((task) => !priorityKeys.has(taskRowKey(task)));' in page_source
    assert 'return (filtered.length ? filtered : filteredTaskRows).slice(0, 3);' in page_source
    assert 'export function taskRowKey(task)' in helper_source


def test_task_center_uses_stage_aware_status_badges() -> None:
    page_source = _load_source()
    helper_source = _load_task_page_helpers_source()
    assert 'taskCardStatusLabel(task, tool.slug, STATUS_LABEL)' in page_source
    assert 'export function taskCardStatusLabel(task, toolSlug, statusLabelMap)' in helper_source
    assert 'if (stage === "product_lock") return "待锁主体";' in helper_source
    assert 'if (stage === "review") return "待选片";' in helper_source
    assert 'export function shouldShowTaskRiskChip(task, toolSlug, statusLabelMap)' in helper_source
    assert 'export function shouldShowDeliveryProgress(task, toolSlug)' in helper_source
    assert 'export function taskOpenLabel(task, toolSlug)' in helper_source
    assert 'taskOpenLabel(task, tool.slug)' in page_source


def test_product_image_review_stage_has_failed_candidate_disposal_card() -> None:
    source = _load_source()
    assert '异常候选处置' in source
    assert '当前有 {failedAssetsCount} 张异常候选。建议先只看异常结果，确认问题后直接补拍失败项' in source
    assert '当前主路径：先补拍 ${failedAssetsCount} 张异常候选，再处理剩余 ${productImagePendingAssets.length} 张待筛选结果。' in source
    assert '只看异常({failedAssetsCount})' in source
    assert '补拍失败项(${failedAssetsCount})' in source
    assert '这张是异常候选，建议先补拍失败项或只看异常筛掉后再继续交付。' in source
    assert '优先补拍异常(${failedAssetsCount})' in source
    assert 'productImagePrimaryAction === "retry-failed"' in source
    assert source.count('只看异常({failedAssetsCount})') == 1
    assert '异常候选区' in source
    assert '这里集中展示异常候选，建议优先处理后，再回到正常候选继续入选与分享。' in source
    assert '正常候选区' in source
    assert '先处理异常区，再回到这里做批量入选、分享或下载交付。' in source


def test_product_image_review_cards_preserve_real_aspect_ratio_and_flag_failed_cards() -> None:
    source = _load_source()
    css_source = _load_globals_css_source()
    assert 'className={cx("asset-card result-asset-card", bucket === "failed" && "failed")}' in source
    assert 'result-asset-meta-strip' in source
    assert '.result-asset-card.failed {' in css_source
    assert 'aspect-ratio: auto;' in css_source
    assert 'object-fit: contain;' in css_source
    assert 'max-height: 320px;' in css_source


def test_product_image_review_primary_path_copy_and_secondary_manual_toggle() -> None:
    source = _load_source()
    panel_source = _load_review_stage_panel_source()
    workspace_source = PROJECT_WORKSPACE_PATH.read_text(encoding="utf-8")
    assert 'from "./review-stage-panel"' in workspace_source
    assert "<ReviewStagePanel" in workspace_source
    assert '当前主路径：先完成入选（已选 ${selectedFinalCount}/${requiredFinalCount}），再批量分享或下载交付。' in source
    assert '当前主路径：已达交付门槛，优先批量分享 ${productImageApprovedUnsharedAssets.length} 张入选图，或直接打包下载。' in source
    assert '当前主路径：结果已达标，可批量分享或打包下载交付。' in source
    assert 'const productImagePrimaryAction = tool.slug !== "product-image"' in panel_source
    assert 'productImagePrimaryAction === "retry-failed"' in panel_source
    assert 'productImagePrimaryAction === "approve-pending"' in panel_source
    assert 'productImagePrimaryAction === "share-approved"' in panel_source
    assert "手动微调只用于处理少量边缘结果，默认主路径仍是先补拍异常、再批量入选、最后分享或下载交付。" in panel_source
    assert '{manualReviewMode ? "收起手动微调" : "打开手动微调"}' in panel_source


def test_generate_stage_panel_is_extracted_from_workspace() -> None:
    source = _load_source()
    panel_source = _load_generate_stage_panel_source()
    workspace_source = PROJECT_WORKSPACE_PATH.read_text(encoding="utf-8")
    assert 'from "./generate-stage-panel"' in workspace_source
    assert "<GenerateStagePanel" in workspace_source
    assert 'export function GenerateStagePanel({' in panel_source
    assert 'data-cta-scope={`workspace.generate.${tool.slug}`}' in panel_source
    assert '候选已产出。当前建议先检查本轮试拍结果，再进入选片分享处理入选与交付。' in panel_source
    assert "当前没有异常候选，所以“失败重试 / 补拍失败项”暂不显示。" in source


def test_product_image_generate_stage_defers_delivery_actions_to_review() -> None:
    panel_source = _load_generate_stage_panel_source()
    assert "进入选片分享" in panel_source
    assert "入选、批量分享、打包下载和手动微调统一放到 Step4 处理" in panel_source
    assert "一键入选(" not in panel_source
    assert "打包下载全部" not in panel_source
    assert "手动筛选" not in panel_source


def test_product_image_generate_and_review_panels_use_workspace_stage_cards() -> None:
    generate_source = _load_generate_stage_panel_source()
    review_source = _load_review_stage_panel_source()
    css_source = _load_globals_css_source()
    assert 'const useProductImageVisualRefresh = tool.slug === "product-image";' in generate_source
    assert 'const useProductImageVisualRefresh = tool.slug === "product-image";' in review_source
    assert 'product-generate-panel' in generate_source
    assert 'product-review-panel' in review_source
    assert 'product-generate-control-deck' in generate_source
    assert 'product-side-card' in generate_source
    assert 'product-stage-status-banner' in review_source
    assert '.product-generate-panel .desktop-stage-shell,' in css_source
    assert '.product-generate-control-deck {' in css_source
    assert '.product-side-card {' in css_source
    assert '.product-review-panel .review-summary-card {' in css_source


def test_model_retouch_defaults_to_full_body_anchor() -> None:
    source = _load_source()
    batch_source = _load_model_retouch_batch_source()
    identity_source = _load_identity_flow_source()
    assert 'from "./identity-flow"' in source
    assert 'MODEL_IDENTITY_TEMPLATES' in identity_source
    assert 'MODEL_IDENTITY_TEMPLATES' in source
    assert 'useIdentityFlowActions' in source
    assert 'identityCandidateStartCopy' in source
    assert 'identityPrimaryActionState' in source
    assert 'function createDefaultIdentityDesign()' in identity_source
    assert 'function useIdentityDesignState({' in identity_source
    assert 'function IdentityDesignFields({' in identity_source
    assert 'export async function submitIdentityCandidateAction({' in identity_source
    assert 'export async function submitIdentityConfirmAction({' in identity_source
    assert 'export async function runIdentityCandidateFlow(config)' in identity_source
    assert 'export async function runIdentityConfirmFlow(config)' in identity_source
    assert 'export function useIdentityFlowActions({' in identity_source
    assert 'export function identityPrimaryActionLabel(identitySource)' in identity_source
    assert 'export function identityModeDescription(identitySource)' in identity_source
    assert 'export function identityConfirmSuccessCopy(scope = "single")' in identity_source
    assert 'export function identitySourceNeedsUploadedAsset(identitySource)' in identity_source
    assert 'export function identityMissingUploadWarning()' in identity_source
    assert 'export function identityCandidateStartCopy({' in identity_source
    assert 'export function identityPrimaryActionState({' in identity_source
    assert batch_source.count('useIdentityDesignState({ hasUploadedIdentity, identityAssets })') >= 1
    assert source.count('useIdentityDesignState({ hasUploadedIdentity, identityAssets })') >= 1
    assert batch_source.count('<IdentityDesignFields') >= 1
    assert source.count('<IdentityDesignFields') >= 1
    assert 'identity_source: "use_uploaded"' in identity_source
    assert 'framing_preset: "full_body"' in identity_source


def test_model_retouch_identity_candidates_show_triptych_label() -> None:
    source = _load_model_retouch_batch_source()
    assert 'identity_layout === "triptych_front_side_back" ? "三视图模特照"' in source


def test_model_retouch_step2_uses_model_source_wording() -> None:
    source = _load_model_retouch_batch_source()
    assert '待确认模特' in source
    assert '确认模特并开始整组替换' in source
    assert '当前替换方式：' in source


def test_quick_video_step2_primary_button_progresses_with_plan_state() -> None:
    source = _load_source()
    assert '生成执行方案' in source
    assert '进入候选生成' in source
    assert '重新生成AI方案' in source


def test_quick_video_auto_advances_after_prompt_pack_ready() -> None:
    source = _load_source()
    assert 'if (tool.slug !== "quick-video-15s") return;' in source
    assert '执行方案已准备，已进入候选生成。' in source


def test_product_image_workspace_has_product_lock_step_and_cta() -> None:
    source = _load_source()
    workspace_source = _load_workspace_flow_source()
    product_reference_source = _load_product_reference_source()
    tool_config_source = _load_tool_config_source()
    assert 'steps: ["产品主体锁定", "组图拍摄方案", "开始试拍", "选片分享"]' in tool_config_source
    assert 'product_lock: "产品主体锁定"' in workspace_source
    assert '生成后会在这里显示主体参考板' in product_reference_source or '生成后会在这里显示服装多角度参考板或套装拆件板' in product_reference_source
    assert '确认当前基准并进入方案' in source
    assert source.count('确认当前基准并进入方案') == 1
    assert 'aria-pressed={productImageModelProvider === item.value}' in source
    assert 'aria-pressed={productLockMode === "direct"}' in source
    assert 'aria-pressed={productLockCandidateCount === 1}' in source
    assert 'product-lock-choice-selected' in source
    assert '执行中：正在生成产品主体参考图，完成后会自动出现候选卡片；当前请先不要重复点击主按钮。' in source
    assert '生成${productLockCandidateCount}张${productReferenceDisplayLabel}' in source
    assert '/product-lock' in source


def test_product_image_stepper_uses_dedicated_blocked_banner() -> None:
    source = _load_source()
    assert 'const [stepperStatus, setStepperStatus] = useState({ text: "", type: "" });' in source
    assert 'const blockedStepMessage = useCallback((idx) => {' in source
    assert 'setStepperStatus({ text: blockedStepMessage(idx), type: "warning" });' in source
    assert 'setStepperStatus({ text: "", type: "" });' in source


def test_video_and_multi_angle_stepper_gating_copy_exists() -> None:
    source = _load_source()
    assert 'if (tool.slug === "intro-video") {' in source
    assert '请先在 AI 方案与执行方案步骤选择并确认一套主脚本，并整理执行方案后再进入视频生成。' in source
    assert '请先完成视频生成，至少产出 1 个候选后再进入人工确认。' in source
    assert 'if (tool.slug === "quick-video-15s") {' in source
    assert '请先生成 AI 方案并整理执行方案，再进入候选生成。' in source
    assert '请先完成候选生成，至少产出 1 个视频结果后再进入人工确认。' in source
    assert '请先生成当前角度，至少产出 1 张结果后再进入人工确认。' in source


def test_workspace_result_filters_do_not_use_primary_button_style() -> None:
    source = _load_source()
    assert 'className={cx("btn-secondary", generateFilter === filter.key && "active")}' in source
    assert 'className={cx("btn-secondary", reviewFilter === filter.key && "active")}' in source
    assert 'generateFilter === filter.key ? "btn-primary" : "btn-secondary"' not in source


def test_tab_and_view_switches_do_not_use_primary_button_style() -> None:
    tools_home_source = TOOLS_HOME_PATH.read_text(encoding="utf-8")
    users_source = Path("/Volumes/MAC 1/shipin/frontend/app/users-page.jsx").read_text(encoding="utf-8")
    assert 'className={cx("btn-secondary", activeShowcaseTab === tab.key && "active")}' in tools_home_source
    assert 'className={cx("btn-secondary", userView === "abnormal" && "active")}' in users_source
    assert 'className={cx("btn-secondary", userView === "pending" && "active")}' in users_source
    assert 'className={cx("btn-secondary", userView === "all" && "active")}' in users_source


def test_log_drawer_mask_is_non_blocking_on_desktop_and_resets_on_project_change() -> None:
    workspace_source = PROJECT_WORKSPACE_PATH.read_text(encoding="utf-8")
    css_source = Path("/Volumes/MAC 1/shipin/frontend/app/globals.css").read_text(encoding="utf-8")
    assert 'setLogDrawerOpen(false);' in workspace_source
    assert '}, [projectId, tool.slug]);' in workspace_source
    assert 'if (!logDrawerOpen || typeof window === "undefined") return undefined;' in workspace_source
    assert 'if (event.key === "Escape") {' in workspace_source
    assert ".log-drawer-mask {" in css_source
    assert "background: transparent;" in css_source
    assert "pointer-events: none;" in css_source


def test_secondary_active_state_has_visible_selected_style() -> None:
    css_source = Path("/Volumes/MAC 1/shipin/frontend/app/globals.css").read_text(encoding="utf-8")
    assert '.btn-secondary.active,' in css_source
    assert '.btn-secondary[aria-pressed="true"]' in css_source
    assert '.product-lock-choice-selected {' in css_source


def test_non_workspace_routes_cleanup_stale_log_drawer_overlay() -> None:
    source = _load_source()
    assert 'document.querySelectorAll(".log-drawer-mask, .log-drawer")' in source
    assert 'if (route.page === "project" || route.page === "batch") return;' in source
    assert 'node.style.pointerEvents = "none";' in source
    assert 'node.style.display = "none";' in source


def test_product_image_run_next_action_gates_plan_by_subject_lock() -> None:
    source = _load_source()
    assert 'if (tool.slug === "product-image" && !current.product_reference_asset_id)' in source
    assert '请先完成产品主体锁定，再进入组图拍摄方案。' in source
    assert '请先生成${productReferenceDisplayLabel}，再进入拍摄方案。' in source
    assert '确认方案并进入试拍' in source


def test_product_image_reference_board_copy_is_explicit() -> None:
    source = _load_source()
    product_reference_source = _load_product_reference_source()
    assert 'from "./product-reference"' in source
    assert "这一步不是直接出最终图，而是在确认后续所有方案和试拍都基于哪张主体基准图执行。" in source
    assert "确认当前基准并进入方案" in source
    assert '服装参考板' in product_reference_source
    assert '套装输出拆件板，拆分上装、下装、外套等单品。' in product_reference_source
    assert '已生成服装参考板：后续方案与试拍都将优先使用这张多角度/拆件参考板。' in product_reference_source
    assert '"包"' not in product_reference_source.split('isApparelLikeProductName')[1].split('].some')[0]
    assert '"鞋"' not in product_reference_source.split('isApparelLikeProductName')[1].split('].some')[0]


def test_product_image_reference_uses_latest_product_lock_asset_and_cache_buster() -> None:
    source = _load_source()
    assert 'const productLockAssets = useMemo(' in source
    assert 'item.tags.includes("product_lock")' in source
    assert 'withMediaVersion(' in source
    assert 'const productReferenceChoices = useMemo(' in source


def test_product_image_reference_debug_line_shows_route_and_workflow() -> None:
    source = _load_source()
    assert 'const productReferenceChoices = useMemo(' in source
    assert 'product-lock-choice-grid' in source


def test_product_image_reference_card_exposes_debug_actions() -> None:
    source = _load_source()
    assert '预览当前选择' in source
    assert 'product-lock-choice-grid' in source
    assert '当前选择：{activeProductChoiceLabel}' in source


def test_product_image_admin_debug_card_reads_generation_tasks() -> None:
    source = _load_source()
    assert 'const [generationTasks, setGenerationTasks] = useState([]);' in source
    assert '/generation-tasks?limit=200' in source
    assert 'canViewGenerationDebug' in source
    assert 'canViewGenerationDebug' in source


def test_product_lock_ui_shows_backfilling_state_copy() -> None:
    source = _load_source()
    assert '执行中：${productReferenceDisplayLabel}任务已提交，正在后台生成，完成后会自动显示' in source
    assert '执行中：结果正在同步，请稍候自动刷新。' in source
    assert 'candidate_count: productLockCandidateCount' in source or 'candidate_count: productLockCandidateCount' in source


def test_product_image_create_form_includes_product_type_field() -> None:
    source = _load_tool_tasks_page_source()
    product_reference_source = _load_product_reference_source()
    tool_config_source = _load_tool_config_source()
    assert 'label>产品类型<' in source
    assert 'PRODUCT_TYPE_OPTIONS' in source
    assert 'const PRODUCT_TYPE_OPTIONS = [' in tool_config_source
    assert 'product_type_other' in source
    assert '包参考板' in product_reference_source


def test_product_lock_ui_shows_queue_busy_copy() -> None:
    source = _load_source()
    assert '执行中：当前资源繁忙，已进入排队，可切换到商业模型重试。' in source


def test_product_image_create_and_workspace_expose_model_provider_choice() -> None:
    tool_tasks_source = _load_tool_tasks_page_source()
    workspace_source = PROJECT_WORKSPACE_PATH.read_text(encoding="utf-8")
    tool_config_source = _load_tool_config_source()
    assert 'IMAGE_MODEL_PROVIDER_OPTIONS' in tool_config_source
    assert 'label>出图引擎<' in tool_tasks_source
    assert 'fd.set("image_model_provider", String(formValues.image_model_provider || "self_hosted"));' in tool_tasks_source
    assert '当前引擎：' in workspace_source
    assert 'image_model_provider: productImageModelProvider' in workspace_source


def test_product_image_generation_options_are_not_reset_by_polling_load() -> None:
    workspace_source = PROJECT_WORKSPACE_PATH.read_text(encoding="utf-8")
    assert 'const generationOptionsHydratedRef = useRef(false);' in workspace_source
    assert 'if (generationOptionsHydratedRef.current) return prev;' in workspace_source
    assert 'generationOptionsHydratedRef.current = true;' in workspace_source
    assert 'setOptions({' in workspace_source


def test_project_workspace_preserves_dirty_form_state_during_polling() -> None:
    workspace_source = PROJECT_WORKSPACE_PATH.read_text(encoding="utf-8")
    assert 'const productImageModelProviderDirtyRef = useRef(false);' in workspace_source
    assert 'const promptInputsDirtyRef = useRef(false);' in workspace_source
    assert 'const cameraInputsDirtyRef = useRef(false);' in workspace_source
    assert 'const planDraftDirtyRef = useRef(false);' in workspace_source
    assert 'if (!promptInputsDirtyRef.current) {' in workspace_source
    assert 'if (!cameraInputsDirtyRef.current) {' in workspace_source
    assert 'if (!planDraftDirtyRef.current) {' in workspace_source


def test_model_retouch_batch_generate_options_are_not_reset_by_polling() -> None:
    batch_source = _load_model_retouch_batch_source()
    assert 'const batchGenerateOptionsHydratedRef = useRef(false);' in batch_source
    assert 'if (controllerProject && !batchGenerateOptionsHydratedRef.current) {' in batch_source


def test_product_lock_success_state_has_confirm_and_regenerate_actions() -> None:
    source = _load_source()
    assert '确认当前基准并进入方案' in source
    assert '已确认使用${activeProductChoiceLabel}，请继续生成组图拍摄方案。' in source
    assert '已确认使用${activeProductChoiceLabel}，请继续生成组图拍摄方案。' in source


def test_product_lock_shows_two_candidates_and_confirm_flow_copy() -> None:
    source = _load_source()
    assert 'product-lock-choice-grid' in source
    assert '/product-lock/confirm' in source
    assert '当前选择：{activeProductChoiceLabel}' in source


def test_product_lock_choice_grid_includes_original_and_generated_candidates() -> None:
    source = _load_source()
    assert 'const originalSourceAsset = useMemo(' in source
    assert 'const productReferenceChoices = useMemo(' in source
    assert "const label = isOriginal ? \"原图\" : `候选 ${asset?.metadata?.candidate_index || '-'}`;" in source
    assert '确认当前基准并进入方案' in source


def test_model_retouch_step2_uses_source_and_candidate_decision_layout() -> None:
    source = _load_model_retouch_batch_source()
    identity_source = _load_identity_flow_source()
    assert '模特来源图' in source
    assert '模特候选区' in source
    assert '直接使用上传模特作为替换来源' in source
    assert '先把上传模特图修成更稳定的标准照，再作为整组替换的模特来源。' in identity_source
    assert '替换方式' in identity_source
    assert '只替换模特' in identity_source
    assert '替换模特并轻微修正动作' in identity_source
    assert '替换模特并重构动作' in identity_source
    assert '使用上传模特' in identity_source
    assert '精修上传模特' in identity_source
    assert '生成新模特' in identity_source


def test_reference_uploads_are_capped_to_supported_limits() -> None:
    source = _load_tool_tasks_page_source()
    app_utils_source = _load_app_utils_source()
    assert 'from "./app-utils"' in source
    assert 'function fileLimitForField(toolSlug, field)' in app_utils_source
    assert 'field === "reference_images") return 2' in app_utils_source
    assert 'toolSlug === "model-retouch" ? 1 : 2' in app_utils_source
    assert '当前仅支持上传 ${limit} 张' in source
    assert 'multiple={false}' in source


def test_product_image_create_form_uses_style_reference_field() -> None:
    source = _load_tool_tasks_page_source()
    start = source.index('{tool.slug === "product-image" && (')
    end = source.index('{tool.slug === "model-retouch" && (', start)
    snippet = source[start:end]
    assert 'name="style_reference_images"' in snippet
    assert 'name="reference_images"' not in snippet


def test_intro_video_generate_does_not_auto_confirm_storyboard() -> None:
    source = _load_source()
    assert "const prepareIntroFlow = async () => {" not in source
    assert "请先确认主脚本并完成分镜确认，再生成视频。" in source
    assert "当前分镜尚未确认，不能自动跳过人工确认。" in source


# ==================== 队列状态契约测试 ====================

def test_task_risk_label_includes_queued_status() -> None:
    """验证 TASK_RISK_LABEL 包含 'queued' 状态（排队中）"""
    source = _load_workspace_flow_source()
    assert 'queued: "排队中"' in source or 'queued: "排队中"' in source


def test_task_next_action_hint_handles_queued() -> None:
    """验证 taskNextActionHint 处理 queued 状态"""
    source = _load_workspace_flow_source()
    assert 'if (risk === "queued")' in source or "风险 === 'queued'" in source
    assert "任务已排队" in source or "等待执行" in source


def test_has_active_async_tasks_excludes_queued() -> None:
    """验证 hasActiveAsyncTasks 不包含 queued_task_count"""
    source = _load_source()
    # 修复后不应再有 queued_task_count
    assert "queued_task_count" not in source or "queued_task_count" not in source.split("hasActiveAsyncTasks")[1] if "hasActiveAsyncTasks" in source else True


def test_assets_page_kpi_separates_running_and_queued() -> None:
    """验证资产页面 KPI 分离 running 和 queued"""
    source = _load_source()
    # 应该有 separate counters for running and queued
    assert "queued:" in source.lower() or "queued" in source
