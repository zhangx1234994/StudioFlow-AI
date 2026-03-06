from pathlib import Path


PAGE_PATH = Path("/Volumes/MAC 1/shipin/frontend/app/page.jsx")


def _load_source() -> str:
    return PAGE_PATH.read_text(encoding="utf-8")


def test_tool_tasks_create_form_has_single_primary_submit() -> None:
    source = _load_source()
    start = source.index('<form ref={formRef} className="grid" onSubmit={create}>')
    end = source.index("</form>", start)
    form_snippet = source[start:end]
    assert form_snippet.count('type="submit" className="btn-primary"') == 1


def test_quick_video_create_panel_is_parameter_simplified() -> None:
    source = _load_source()
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


def test_workspace_product_image_step_has_secondary_non_primary_actions() -> None:
    source = _load_source()
    start = source.index('{tool.slug === "product-image" ? (')
    end = source.index(') : tool.slug === "model-retouch" ? null : (', start)
    snippet = source[start:end]
    assert '重新生成方案' in snippet
    assert '!project?.project_plan?.shots?.length ? (' in snippet
    assert '确认方案并进入试拍' in snippet
    assert '<button type="button" className="btn-secondary" onClick={() => genPlan()} disabled={isInitializing || isPlanLoading}>' in snippet


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
    assert '等待执行：先保存机位或点击“开始生成当前角度”。' in source
    assert '开始生成当前角度' in source


def test_model_retouch_step4_has_explicit_download_cta() -> None:
    source = _load_source()
    assert '打包下载已通过结果' in source
    assert '打包下载全部结果' in source
    assert '已通过 {approvedGeneratedAssets.length} 张，可直接交付' in source


def test_intro_video_primary_label_matches_actual_behavior() -> None:
    source = _load_source()
    assert '确认主脚本并准备视频生成' in source
    assert '确认主脚本并进入视频生成' not in source


def test_model_retouch_copy_uses_anchor_language_and_reference_order_hint() -> None:
    source = _load_source()
    assert '模特锚点确认台' in source
    assert '确认一张可复用的模特锚点图，再批量替换整组套图中的模特' in source
    assert '参考顺序固定为：主图作为基底输入 → 模特锚点作为首个参考输入 → 其他风格参考图排在其后。' in source


def test_model_retouch_defaults_to_full_body_anchor() -> None:
    source = _load_source()
    assert 'framing_preset: "full_body"' in source


def test_model_retouch_identity_candidates_show_triptych_label() -> None:
    source = _load_source()
    assert 'identity_layout === "triptych_front_side_back" ? "三视图定妆照"' in source


def test_model_retouch_triptych_uses_anchor_wording() -> None:
    source = _load_source()
    assert '待确认锚点' in source
    assert '确认该锚点' in source


def test_quick_video_step2_primary_button_progresses_with_plan_state() -> None:
    source = _load_source()
    assert '生成执行方案' in source
    assert '进入候选生成' in source
    assert '重新生成AI方案' in source


def test_quick_video_auto_advances_after_prompt_pack_ready() -> None:
    source = _load_source()
    assert 'if (tool.slug !== "quick-video-15s") return;' in source
    assert '执行方案已准备，已进入候选生成。' in source
