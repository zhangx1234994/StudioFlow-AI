# UI Interaction Contract (v1)

## Purpose
Define a single interaction model for all tool workspaces so users always know current step, system status, and next action.

## Unified State Machine
- `idle`: No active operation; current step is actionable.
- `submitting`: User just clicked a primary action; request in-flight; primary actions locked.
- `running`: Background generation in progress; progress/logs update continuously.
- `review`: Outputs available and awaiting manual review.
- `done`: Required outputs reviewed or accepted.
- `failed`: Operation failed with actionable reason and retry path.
- `blocked`: User attempted to jump to a step with unmet prerequisites.

## Core Interaction Rules
1. Each step has exactly one primary CTA.
2. Primary CTA must show feedback in <=200ms (`已提交...`).
3. While `submitting` or `running`, all conflicting actions are disabled.
4. Step navigation enforces prerequisites; blocked navigation redirects to prerequisite step with reason.
5. Progress feedback is persistent and cannot regress to `等待执行` until state exits `running`.
6. Every failure state includes: reason, retry action, and suggested next step.
7. Workspace step navigation must use a top horizontal stepper (`流程进度`) to maximize primary work area; no local left-side step panel is allowed.
8. Stepper must remain clickable for direct step switching and expose clear active/completed visual states.
9. Core sections must use icon + short title composition; avoid text-only dense blocks for first-screen information.
10. Visual style must convey premium quality: unified typography, atmospheric background layers, elevated cards, and clear interaction hierarchy.
11. Home showcase must prioritize operations: one featured hero case + secondary case grid + direct CTA, not a flat card wall only.
12. Workspace step content must use a panel header (`STEP kicker + title + icon`) and a compact meta strip (stage/progress/status/next action) for quick orientation.
13. Generation and review steps must expose dashboard-style summaries (`generation control deck` + `review summary cards`) before asset walls.
14. Asset walls must include visible status filters (`全部/已通过/待筛选/异常`) so users can narrow large candidate sets without losing context.
15. Runtime logs are secondary information: default collapsed and opened via side drawer; logs must never occupy primary operation space.
16. Home operations area must include both package modules and a hot-selling signal block to support commercial conversion decisions.
17. `queued` is waiting state, not running state: UI must not show “生成中” unless the backend reports `running` or the current action was explicitly submitted in this session.
18. Long-running plan generation must have timeout fallback (default 120s): unlock primary CTA and surface retry guidance.
19. Product-image plan generation must support progressive completion: when shot count is high, backend returns outline first and fills per-shot prompts in parallel to avoid long blank waiting.
20. Model retouch must use batch workspace route (`/app/tools/model-retouch/batches/{batch_group_id}`) as the primary entry after create; no stop on standalone “批次精修要求” page.
21. Model retouch identity is always `pending` before explicit confirmation (including uploaded identity image); Step2 primary CTA stays at top and exposes idle/loading/success/error.
22. Model retouch Step3 is batch execution view: all task cards visible, one-click batch run, per-card progressive backfill, and retry only failed items.
23. Model retouch Step2 must expose exactly three identity actions: `使用上传模特图 / 精修模特图 / 生成新模特图`; each click must have visible feedback and disabled reason.
24. Model retouch Step2 must support replacing uploaded identity image in-place (same page), and replacement keeps `pending` until user explicitly confirms anchor.
25. Image tools must expose aspect ratio selection with default `原图（默认）`; backend request should use `image_aspect_ratio=auto` when default is selected.
26. Model retouch Step2 must show an anchor overview panel (`当前锚点总览`), so users can always see which image is currently confirmed.
27. When aspect ratio is `原图（默认）`, resolution selector must be disabled and UI must explain “原图比例模式下不传分辨率”.
28. Topbar must expose a visible frontend build tag (`前端版本`) for cache diagnosis; user can verify refresh state without opening devtools.
29. Product-image flow after generation should prioritize batch outcomes: default action path is `进入选片分享 -> 一键入选 -> 批量分享/打包下载`; single-image review actions are secondary (manual mode).
30. Model retouch Step2 must carry over create-page uploads in-page (主素材缩略图 + 上传模特图预览), so users do not lose context after create.
31. Model retouch Step2 uploaded identity panel must support in-place replace and remove (`X`) without leaving the page; remove returns identity state to `pending` until a new anchor is confirmed.
32. Auth login page must follow brand-first visual layout (`品牌海报区 + 登录区`), with at least one photography preview image and clear primary CTA (`登录`) + secondary CTA (`注册`).
33. Topbar must be compact-first: quick search + compact chips + small action buttons; avoid oversized CTA-like controls in global navigation.
34. Topbar labels must use product language (e.g., `账号正常/主工作区/积分`) and must not expose developer-oriented field wording.
35. Home first screen should prioritize low cognitive load: core KPI cards first, secondary metrics in compact chips, and avoid dense equal-weight blocks.
36. Model retouch Step2 identity flow should use mode switching (`使用上传/精修上传/生成新模特`) with one primary action button per current mode.
37. Asset center must be a unified operation canvas (`任务中心 + 素材中心 + 样片中心`) with tab switching; task flow is primary and should be first-class, not hidden across separate pages.
38. Asset center visual style should be stage-like (dark premium container + focused cards + restrained controls), avoiding back-office table-first appearance.

## Step Gating Rules
- `overview`: Always accessible.
- `plan`: Always accessible.
- `generate`: Requires `plan_ready && prompts_ready`.
- `review`: Requires at least one generated asset.
- Intro video extras:
  - Render requires selected script.
  - If storyboard exists and not confirmed, user is guided to approve/confirm storyboard first.

## Required UI Feedback Blocks
- Global status bar: project-level stage + task status + next action.
- Flow guide bar: "where you are / what is happening / where to click next".
- Step status bar: step-local execution status.
- Timeline logs: latest events for trust and recovery.

## Edge Cases to Handle
- Repeated clicks on primary CTA.
- Refresh during long-running tasks.
- Partial completion (some assets succeed, some fail).
- Task timeout or provider error.
- User edits prompts after plan generated (must mark downstream stale if needed).

## Acceptance Criteria
- No primary action has silent click behavior.
- No blocked step is entered without explanation.
- Running operations preserve visible progress language.
- Refresh restores correct step and actionable state.
