"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiFetch, buildFormDataWithoutFiles, createClientProjectId, cx, fileLimitForField, formatDate, formatProgressLabel, selectedFileSummary, uploadToOss } from "./app-utils";
import { safeCreateObjectURL, safeSessionGet, safeSessionRemove, safeSessionSet } from "./media-utils";
import { resolveTaskRisk, resolveTaskWorkspacePath, stageLabel, taskNextActionHint, TASK_RISK_LABEL } from "./workspace-flow";
import { resolveProductReferenceLabel } from "./product-reference";
import { IMAGE_MODEL_PROVIDER_OPTIONS, PRODUCT_TYPE_OPTIONS, STATUS_LABEL, TASK_RISK_PRIORITY, TOOL_BY_TYPE, toolIconName } from "./tool-config";
import { QUICK_VIDEO_CTA_OPTIONS, QUICK_VIDEO_CTA_TEXT_BY_STYLE, QUICK_VIDEO_NARRATION_OPTIONS, QUICK_VIDEO_PACE_OPTIONS, QUICK_VIDEO_THEME_FEATURES, QUICK_VIDEO_THEME_OPTIONS, QUICK_VIDEO_TONE_BY_STYLE } from "./ui-config";
import { Icon } from "./shared-ui";
import { buildDefaultFormValues, createOutcomePreview, createToolScene } from "./tool-create-config";
import { buildPriorityRows, buildTaskRows, shouldShowDeliveryProgress, shouldShowTaskRiskChip, taskCardStatusLabel, taskOpenLabel, taskRowKey } from "./task-page-helpers";

export function ToolTasksPage({ tool, navigate }) {
  const [templates, setTemplates] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [query, setQuery] = useState("");
  const [taskFilter, setTaskFilter] = useState("all");
  const [status, setStatus] = useState({ text: "准备中...", type: "" });
  const [createStatus, setCreateStatus] = useState({ text: "填写信息后创建。", type: "" });
  const [creating, setCreating] = useState(false);
  const mountedRef = useRef(true);
  const requestTokenRef = useRef(0);
  const [formValues, setFormValues] = useState(buildDefaultFormValues(tool.slug));
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [previewSrc, setPreviewSrc] = useState("");
  const [highlightBatch, setHighlightBatch] = useState("");
  const [lastCreatedProjectId, setLastCreatedProjectId] = useState("");
  const [lastCreatedBatchId, setLastCreatedBatchId] = useState("");
  const formRef = useRef(null);
  const createTimerRef = useRef(null);
  const [fileInputVersion, setFileInputVersion] = useState({
    image: 0,
    images: 0,
    reference_images: 0,
    style_reference_images: 0,
    identity_image: 0,
  });
  const fileInputIds = useMemo(
    () => ({
      image: `file-image-${fileInputVersion.image}`,
      images: `file-images-${fileInputVersion.images}`,
      reference_images: `file-reference-${fileInputVersion.reference_images}`,
      style_reference_images: `file-style-${fileInputVersion.style_reference_images}`,
      identity_image: `file-identity-${fileInputVersion.identity_image}`,
    }),
    [fileInputVersion]
  );
  const [selectedFiles, setSelectedFiles] = useState({
    image: [],
    images: [],
    reference_images: [],
    style_reference_images: [],
    identity_image: [],
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    const cached = safeSessionGet(`highlight_batch_${tool.slug}`);
    if (cached) {
      setHighlightBatch(cached);
      safeSessionRemove(`highlight_batch_${tool.slug}`);
    }
  }, [tool.slug]);

  const onFileChange = useCallback((field, event) => {
    const limit = fileLimitForField(tool.slug, field);
    const files = Array.from(event.target.files || []);
    const acceptedFiles = limit ? files.slice(0, limit) : files;
    if (limit && files.length > limit) {
      setCreateStatus({ text: `提示：当前仅支持上传 ${limit} 张${field === "style_reference_images" || field === "reference_images" ? "参考图" : "图片"}，已自动保留前 ${limit} 张。`, type: "warning" });
    }
    const names = acceptedFiles.map((file) => file.name);
    setSelectedFiles((prev) => ({ ...prev, [field]: names }));
    if (field === "image") {
      if (acceptedFiles[0]) {
        setPreviewSrc(safeCreateObjectURL(acceptedFiles[0]));
      } else {
        setPreviewSrc("");
      }
    }
    if (event.target) {
      const dt = new DataTransfer();
      acceptedFiles.forEach((file) => dt.items.add(file));
      event.target.files = dt.files;
    }
  }, [tool.slug]);

  const clearFiles = useCallback((field) => {
    setSelectedFiles((prev) => ({ ...prev, [field]: [] }));
    setFileInputVersion((prev) => ({ ...prev, [field]: prev[field] + 1 }));
    if (field === "image") setPreviewSrc("");
  }, []);

  const loadData = useCallback(async () => {
    setStatus({ text: "加载模板和任务...", type: "" });
    try {
      const [templatesRes, tasksRes] = await Promise.all([
        apiFetch(`/api/v1/tools/${tool.toolType}/templates`),
        apiFetch(`/api/v1/tools/${tool.toolType}/tasks?limit=40${query.trim() ? `&query=${encodeURIComponent(query.trim())}` : ""}`),
      ]);
      if (!mountedRef.current) return;
      setTemplates(templatesRes);
      setTasks(tasksRes);
      if (templatesRes.length) {
        setFormValues((prev) => ({ ...prev, template_name: templatesRes[0].template_name }));
      }
      setStatus({ text: tasksRes.length ? `任务已加载（${tasksRes.length}）` : "暂无任务", type: "success" });
    } catch (error) {
      if (!mountedRef.current) return;
      setStatus({ text: error.message, type: "error" });
    }
  }, [tool.toolType, query]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);
  useEffect(() => {
    requestTokenRef.current += 1;
    setFormValues(buildDefaultFormValues(tool.slug));
    setCreateStatus({ text: "填写信息后创建。", type: "" });
    setCreating(false);
    setAdvancedOpen(false);
    setPreviewSrc("");
    setLastCreatedProjectId("");
    setLastCreatedBatchId("");
    setSelectedFiles({
      image: [],
      images: [],
      reference_images: [],
      style_reference_images: [],
      identity_image: [],
    });
    setFileInputVersion((prev) => ({
      image: prev.image + 1,
      images: prev.images + 1,
      reference_images: prev.reference_images + 1,
      style_reference_images: prev.style_reference_images + 1,
      identity_image: prev.identity_image + 1,
    }));
    setHighlightBatch("");
    setQuery("");
  }, [tool.slug, buildDefaultFormValues]);

  const latestTask = useMemo(
    () => [...tasks].sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime())[0] || null,
    [tasks],
  );
  const latestTaskPath = latestTask ? resolveTaskWorkspacePath(latestTask, TOOL_BY_TYPE) : "";
  const taskRows = useMemo(() => buildTaskRows({ tasks, toolSlug: tool.slug }), [tasks, tool.slug]);
  const filteredTaskRows = useMemo(() => {
    if (taskFilter === "all") return taskRows;
    return taskRows.filter((task) => {
      const stage = String(task.current_stage || "").toLowerCase();
      const risk = resolveTaskRisk(task);
      if (taskFilter === "product_lock") return stage === "product_lock";
      if (taskFilter === "review") return stage === "review";
      if (taskFilter === "blocked") return risk === "blocked";
      return true;
    });
  }, [taskFilter, taskRows]);
  const priorityRows = useMemo(
    () => buildPriorityRows({ taskRows: filteredTaskRows, taskRiskPriority: TASK_RISK_PRIORITY }),
    [filteredTaskRows],
  );
  const taskOverview = useMemo(() => ({
    blocked: taskRows.filter((task) => resolveTaskRisk(task) === "blocked").length,
    pending: taskRows.filter((task) => resolveTaskRisk(task) === "pending").length,
    running: taskRows.filter((task) => resolveTaskRisk(task) === "running").length,
    total: taskRows.length,
  }), [taskRows]);
  const taskFilterStats = useMemo(() => ({
    product_lock: taskRows.filter((task) => String(task.current_stage || "").toLowerCase() === "product_lock").length,
    review: taskRows.filter((task) => String(task.current_stage || "").toLowerCase() === "review").length,
    blocked: taskRows.filter((task) => resolveTaskRisk(task) === "blocked").length,
  }), [taskRows]);
  const recentRows = useMemo(() => {
    const priorityKeys = new Set(priorityRows.map((task) => taskRowKey(task)));
    const filtered = filteredTaskRows.filter((task) => !priorityKeys.has(taskRowKey(task)));
    return (filtered.length ? filtered : filteredTaskRows).slice(0, 3);
  }, [priorityRows, filteredTaskRows]);
  const createScene = useMemo(() => createToolScene(tool.slug), [tool.slug]);
  const outcomePreview = useMemo(
    () => createOutcomePreview({ slug: tool.slug, formValues, selectedFiles, tasks }),
    [tool.slug, formValues, selectedFiles, tasks]
  );

  const create = async (event) => {
    event.preventDefault();
    const raw = new FormData(formRef.current);
    const requestToken = requestTokenRef.current + 1;
    requestTokenRef.current = requestToken;
    const optimisticProjectId = tool.slug === "model-retouch" ? "" : createClientProjectId();
    setCreating(true);
    setCreateStatus({ text: "提交中：自动优化图片并提交任务...", type: "" });
    if (createTimerRef.current) clearTimeout(createTimerRef.current);
    createTimerRef.current = setTimeout(() => {
      if (!mountedRef.current || requestToken !== requestTokenRef.current) return;
      setCreateStatus({ text: "提交中：提交时间较长，仍在处理中，请耐心等待…", type: "warning" });
    }, 8000);
    try {
      const getSuffix = (name) => {
        const idx = String(name || "").lastIndexOf(".");
        return idx >= 0 ? String(name).slice(idx) : ".png";
      };
      const uploadProjectId = optimisticProjectId || createClientProjectId();
      let uploadedMain = null;
      let uploadedRefs = [];
      let uploadedStyleRefs = [];
      let uploadedIdentity = null;
      let uploadedBatch = [];
      if (tool.slug === "model-retouch") {
        const batchFiles = raw.getAll("images").filter((item) => item instanceof File && item.size > 0);
        if (batchFiles.length) {
          setCreateStatus({ text: "提交中：正在上传主素材（直传OSS）...", type: "" });
          uploadedBatch = [];
          let done = 0;
          for (const file of batchFiles) {
            const result = await uploadToOss({ file, projectId: uploadProjectId, role: "source" });
            uploadedBatch.push(result.public_url);
            done += 1;
            setCreateStatus({ text: `执行中：主素材已上传 ${done}/${batchFiles.length}`, type: "" });
          }
        }
        const styleFiles = raw
          .getAll("style_reference_images")
          .filter((item) => item instanceof File && item.size > 0)
          .slice(0, fileLimitForField(tool.slug, "style_reference_images") || undefined);
        if (styleFiles.length) {
          let done = 0;
          for (const file of styleFiles) {
            const result = await uploadToOss({ file, projectId: uploadProjectId, role: "style_reference" });
            uploadedStyleRefs.push(result.public_url);
            done += 1;
            setCreateStatus({ text: `执行中：风格参考已上传 ${done}/${styleFiles.length}`, type: "" });
          }
        }
        const identityFile = raw.get("identity_image");
        if (identityFile instanceof File && identityFile.size > 0) {
          setCreateStatus({ text: "提交中：上传替换模特图...", type: "" });
          const result = await uploadToOss({ file: identityFile, projectId: uploadProjectId, role: "identity" });
          uploadedIdentity = result.public_url;
        }
      } else {
        const mainFile = raw.get("image");
        if (mainFile instanceof File && mainFile.size > 0) {
          setCreateStatus({ text: "提交中：上传主图中（直传OSS）...", type: "" });
          const result = await uploadToOss({ file: mainFile, projectId: uploadProjectId, role: "source" });
          uploadedMain = { url: result.public_url, mime: mainFile.type || "image/png", suffix: getSuffix(mainFile.name) };
        }
        const refFiles = raw.getAll("reference_images").filter((item) => item instanceof File && item.size > 0);
        if (refFiles.length) {
          let done = 0;
          for (const file of refFiles) {
            const result = await uploadToOss({ file, projectId: uploadProjectId, role: "reference" });
            uploadedRefs.push(result.public_url);
            done += 1;
            setCreateStatus({ text: `执行中：参考图已上传 ${done}/${refFiles.length}`, type: "" });
          }
        }
        const styleFiles = raw
          .getAll("style_reference_images")
          .filter((item) => item instanceof File && item.size > 0)
          .slice(0, fileLimitForField(tool.slug, "style_reference_images") || undefined);
        if (styleFiles.length) {
          let done = 0;
          for (const file of styleFiles) {
            const result = await uploadToOss({ file, projectId: uploadProjectId, role: "style_reference" });
            uploadedStyleRefs.push(result.public_url);
            done += 1;
            setCreateStatus({ text: `执行中：风格参考已上传 ${done}/${styleFiles.length}`, type: "" });
          }
        }
      }

      const fd = buildFormDataWithoutFiles(raw);
      if (uploadedMain?.url) {
        fd.set("image_public_url", uploadedMain.url);
        fd.set("image_mime", uploadedMain.mime);
        fd.set("image_suffix", uploadedMain.suffix);
      }
      if (uploadedRefs.length) {
        fd.set("reference_image_public_urls", uploadedRefs.join(","));
      }
      if (uploadedStyleRefs.length) {
        fd.set("style_reference_image_public_urls", uploadedStyleRefs.join(","));
      }
      if (uploadedIdentity) {
        fd.set("identity_image_public_url", uploadedIdentity);
      }
      if (uploadedBatch.length) {
        fd.set("image_public_urls", uploadedBatch.join(","));
      }
      if (tool.slug === "model-retouch") {
        fd.set("retouch_scope", "per_image");
        fd.set("workflow_mode", "retouch_per_image");
        const result = await apiFetch("/api/v1/tools/model_retouch/batch-create", { method: "POST", body: fd });
        if (!mountedRef.current || requestToken !== requestTokenRef.current) return;
        setHighlightBatch(result.batch_group_id || "");
        if (typeof window !== "undefined" && result.batch_group_id) {
          safeSessionSet(`highlight_batch_${tool.slug}`, result.batch_group_id);
        }
        setCreateStatus({
          text: `成功：批次创建完成，共 ${result.created_count} 张，进入批量工作台。`,
          type: "success",
        });
        const batchGroupId = result.batch_group_id || "";
        const firstProjectId = result.controller_project_id
          || (Array.isArray(result.project_ids) ? result.project_ids[0] : "")
          || (Array.isArray(result.projects) ? result.projects[0]?.project_id : "");
        setLastCreatedBatchId(batchGroupId);
        if (firstProjectId) setLastCreatedProjectId(firstProjectId);
        if (batchGroupId) {
          navigate(`/app/tools/${tool.slug}/batches/${batchGroupId}`);
          if (typeof window !== "undefined") {
            setTimeout(() => {
              if (window.location.pathname.includes("/tasks")) {
                window.location.assign(`/app/tools/${tool.slug}/batches/${batchGroupId}`);
              }
            }, 200);
          }
          return;
        }
        await loadData();
      } else {
        fd.set("tool_type", tool.toolType);
        fd.set("scenario_type", tool.scenarioType);
        if (tool.slug === "quick-video-15s") {
          const quickTheme = String(formValues.quick_video_theme || "product_highlight").trim() || "product_highlight";
          const quickPace = String(formValues.quick_video_pace || "fast").trim() || "fast";
          const quickNarration = String(formValues.quick_video_narration_style || "direct").trim() || "direct";
          const quickCta = String(formValues.quick_video_cta_style || "soft_sell").trim() || "soft_sell";
          const toneValue = QUICK_VIDEO_TONE_BY_STYLE[quickNarration] || QUICK_VIDEO_TONE_BY_STYLE.direct;
          const ctaText = QUICK_VIDEO_CTA_TEXT_BY_STYLE[quickCta] || QUICK_VIDEO_CTA_TEXT_BY_STYLE.soft_sell;
          const featureValue = QUICK_VIDEO_THEME_FEATURES[quickTheme] || QUICK_VIDEO_THEME_FEATURES.product_highlight;
          const paceHint = quickPace === "fast" ? "快节奏强钩子" : quickPace === "balanced" ? "中速节奏稳转化" : "舒缓节奏重叙事";

          fd.set("desired_duration_sec", "15");
          fd.set("tone", toneValue);
          fd.set("cta_text", ctaText);
          fd.set("key_features", featureValue);
          fd.set("scene_style", `15秒短片/${quickTheme}`);
          fd.set("scene_goals", `节奏:${paceHint},时长:15秒,输出:3个候选`);
          fd.set("creative_direction", `${String(formValues.creative_direction || "").trim()}；节奏偏好:${paceHint}`.replace(/^；/, ""));
          fd.set("target_final_count", "3");
          fd.set("takes_per_shot", "1");
        }
        if (tool.slug === "product-image") {
          fd.set("target_final_count", String(Math.max(3, Math.min(30, Number(formValues.target_final_count || 9)))));
          fd.set("takes_per_shot", String(Math.max(1, Math.min(4, Number(formValues.takes_per_shot || 3)))));
          fd.set("shot_plan_mode", "meaning_first");
          fd.set("workflow_mode", "product_set");
          fd.set("image_model_provider", String(formValues.image_model_provider || "self_hosted"));
          const resolvedProductType = formValues.product_type === "other"
            ? String(formValues.product_type_other || "").trim()
            : String(formValues.product_type || "").trim();
          fd.set("product_type", resolvedProductType);
        }
        if (optimisticProjectId) {
          fd.set("project_id", optimisticProjectId);
        }
        const result = await apiFetch("/api/v1/projects", { method: "POST", body: fd });
        const projectId = result?.project?.project_id;
        if (!projectId) throw new Error("创建成功但未返回项目ID");
        if (!mountedRef.current || requestToken !== requestTokenRef.current) return;
        if (tool.slug === "multi-angle-camera") {
          setCreateStatus({
            text: `成功：创建成功，进入工作台后先设置机位，再生成当前角度（项目 ${projectId}）`,
            type: "success",
          });
        } else {
          setCreateStatus({
            text: `成功：创建成功，进入项目 ${projectId}`,
            type: "success",
          });
        }
        navigate(`/app/tools/${tool.slug}/projects/${projectId}`);
      }
    } catch (error) {
      if (!mountedRef.current || requestToken !== requestTokenRef.current) return;
      setCreateStatus({ text: `失败：${error.message}`, type: "error" });
    } finally {
      if (createTimerRef.current) clearTimeout(createTimerRef.current);
      if (mountedRef.current && requestToken === requestTokenRef.current) {
        setCreating(false);
      }
    }
  };

  return (
    <div className="content-stack">
      <section className={cx("card", "create-tool-card", `create-tool-card--${tool.slug}`)}>
        <div className="create-tool-hero">
          <div className="create-tool-copy">
            <div className="create-tool-kicker"><Icon name={toolIconName(tool)} size={13} />{createScene.eyebrow}</div>
            <h1 className="title-row"><Icon name={toolIconName(tool)} size={20} />{tool.title}</h1>
            <p className="card-subtitle">{tool.subtitle}</p>
            <strong className="create-tool-title">{createScene.title}</strong>
            <p className="muted">{createScene.description}</p>
            <div className="toolbar create-tool-bullets">
              {createScene.bullets.map((item) => (
                <span key={item} className="badge">{item}</span>
              ))}
            </div>
          </div>
          <div className="create-tool-stageboard">
            <article className="create-tool-stage-main">
              <img src={createScene.imageMain} alt={`${tool.title}样片`} />
            </article>
            <article className="create-tool-stage-side">
              <img src={createScene.imageSide} alt={`${tool.title}场景样片`} />
            </article>
          </div>
        </div>
        <div className="ops-banner create-tool-outcome" style={{ marginTop: 8 }}>
          <div>
            <h3 className="title-row" style={{ marginBottom: 4 }}><Icon name="spark" size={15} />本次产出预期</h3>
            <p className="muted">{outcomePreview.summary}</p>
          </div>
          <div className="toolbar">
            {outcomePreview.chips.map((item) => (
              <span key={item} className="badge">{item}</span>
            ))}
          </div>
        </div>
        {latestTask ? (
          <div className="home-continue-band">
            <div>
              <div className="home-continue-label">继续上次任务</div>
              <strong>{latestTask.product_name || "未命名任务"}</strong>
              <span> · {stageLabel(latestTask.current_stage, tool.slug)}</span>
              {shouldShowDeliveryProgress(latestTask, tool.slug) ? (
                <div className="home-continue-metrics">
                  <span className="badge">已选 {latestTask.selected_final_count}/{latestTask.required_final_count}</span>
                  <span className="badge">候选 {latestTask.candidate_total}</span>
                </div>
              ) : null}
              <div className="muted" style={{ marginTop: 4 }}>下一步：{latestTask.next_action || "进入工作台继续处理"}</div>
            </div>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => navigate(latestTaskPath)}
            >
              继续上次任务
            </button>
          </div>
        ) : null}
        <form ref={formRef} className="grid" onSubmit={create}>
          <div className="field"><label>{tool.slug === "model-retouch" ? "批次名" : "产品名"} *</label><input name="product_name" required value={formValues.product_name} onChange={(event) => setFormValues((prev) => ({ ...prev, product_name: event.target.value }))} /></div>
          {tool.slug === "model-retouch" ? (
            <>
              <div className="field">
                <label>A. 主素材组图（必填）*</label>
                <div className="muted">上传几张就会创建几个精修任务（1 图 = 1 任务）。</div>
                <div className="file-picker">
                  <input
                    key={`images-${fileInputVersion.images}`}
                    id={fileInputIds.images}
                    className="file-input-hidden"
                    name="images"
                    type="file"
                    accept="image/*"
                    multiple
                    required
                    onChange={(event) => onFileChange("images", event)}
                  />
                  <label className="btn-secondary" htmlFor={fileInputIds.images}>选择多张</label>
                  <span className="muted">{selectedFileSummary(selectedFiles.images)}</span>
                  {selectedFiles.images.length > 0 && <button type="button" className="btn-ghost" onClick={() => clearFiles("images")}>撤回已选</button>}
                </div>
              </div>
              <div className="field">
                <label>B. 风格参考图（最多 1 张）</label>
                <div className="file-picker">
                  <input
                    key={`style-reference-images-${fileInputVersion.style_reference_images}`}
                    id={fileInputIds.style_reference_images}
                    className="file-input-hidden"
                    name="style_reference_images"
                    type="file"
                    accept="image/*"
                    multiple={false}
                    onChange={(event) => onFileChange("style_reference_images", event)}
                  />
                  <label className="btn-secondary" htmlFor={fileInputIds.style_reference_images}>选择参考图</label>
                  <span className="muted">{selectedFileSummary(selectedFiles.style_reference_images)}</span>
                  {selectedFiles.style_reference_images.length > 0 && <button type="button" className="btn-ghost" onClick={() => clearFiles("style_reference_images")}>撤回已选</button>}
                </div>
              </div>
              <div className="field">
                <label>C. 替换模特源图</label>
                <div className="muted">开启后将先确认模特锚点，再进入整组替换精修。</div>
                <div className="file-picker">
                  <input
                    key={`identity-image-${fileInputVersion.identity_image}`}
                    id={fileInputIds.identity_image}
                    className="file-input-hidden"
                    name="identity_image"
                    type="file"
                    accept="image/*"
                    onChange={(event) => onFileChange("identity_image", event)}
                  />
                  <label className="btn-secondary" htmlFor={fileInputIds.identity_image}>选择文件</label>
                  <span className="muted">{selectedFileSummary(selectedFiles.identity_image)}</span>
                  {selectedFiles.identity_image.length > 0 && <button type="button" className="btn-ghost" onClick={() => clearFiles("identity_image")}>撤回已选</button>}
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="field">
                <label>主图 *</label>
                <div className="file-picker">
                  <input
                    key={`image-${fileInputVersion.image}`}
                    id={fileInputIds.image}
                    className="file-input-hidden"
                    name="image"
                    type="file"
                    accept="image/*"
                    required
                    onChange={(event) => onFileChange("image", event)}
                  />
                  <label className="btn-secondary" htmlFor={fileInputIds.image}>选择文件</label>
                  <span className="muted">{selectedFileSummary(selectedFiles.image)}</span>
                  {selectedFiles.image.length > 0 && <button type="button" className="btn-ghost" onClick={() => clearFiles("image")}>撤回已选</button>}
                </div>
              </div>
              {tool.slug === "product-image" && (
                <div className="field">
                  <label>风格参考图（最多 2 张）</label>
                  <div className="file-picker">
                    <input
                      key={`${tool.slug}-style-reference-${fileInputVersion.style_reference_images}`}
                      id={fileInputIds.style_reference_images}
                      className="file-input-hidden"
                      name="style_reference_images"
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={(event) => onFileChange("style_reference_images", event)}
                    />
                    <label className="btn-secondary" htmlFor={fileInputIds.style_reference_images}>选择参考图</label>
                    <span className="muted">
                      {selectedFileSummary(selectedFiles.style_reference_images)}
                    </span>
                    {selectedFiles.style_reference_images.length > 0 && (
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={() => clearFiles("style_reference_images")}
                      >
                        撤回已选
                      </button>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
          {tool.slug !== "quick-video-15s" ? (
            <div className="field"><label>模板</label><select name="template_name" value={formValues.template_name} onChange={(event) => setFormValues((prev) => ({ ...prev, template_name: event.target.value }))}>{templates.map((item) => <option key={item.template_name} value={item.template_name}>{item.display_name}</option>)}</select></div>
          ) : (
            <input name="template_name" type="hidden" value={formValues.template_name} readOnly />
          )}
          {tool.slug !== "multi-angle-camera" ? (
            <div className="field"><label>平台</label><input name="platform" value={formValues.platform} onChange={(event) => setFormValues((prev) => ({ ...prev, platform: event.target.value }))} /></div>
          ) : (
            <input name="platform" type="hidden" value={formValues.platform} readOnly />
          )}

          {tool.slug === "intro-video" && (
            <div className="field"><label>时长（秒）</label><input name="desired_duration_sec" type="number" min={15} max={50} value={formValues.desired_duration_sec} onChange={(event) => setFormValues((prev) => ({ ...prev, desired_duration_sec: Number(event.target.value || 15) }))} /></div>
          )}

          {tool.slug === "quick-video-15s" && (
            <>
              <div className="field"><label>时长（秒）</label><input value="15（固定）" disabled readOnly /></div>
              <div className="field">
                <label>短片主题</label>
                <select
                  value={formValues.quick_video_theme}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, quick_video_theme: event.target.value }))}
                >
                  {QUICK_VIDEO_THEME_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </div>
              <div className="field">
                <label>节奏</label>
                <select
                  value={formValues.quick_video_pace}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, quick_video_pace: event.target.value }))}
                >
                  {QUICK_VIDEO_PACE_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </div>
              <div className="field">
                <label>文案语气</label>
                <select
                  value={formValues.quick_video_narration_style}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, quick_video_narration_style: event.target.value }))}
                >
                  {QUICK_VIDEO_NARRATION_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </div>
              <div className="field">
                <label>结尾行动语</label>
                <select
                  value={formValues.quick_video_cta_style}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, quick_video_cta_style: event.target.value }))}
                >
                  {QUICK_VIDEO_CTA_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </div>
            </>
          )}

          {tool.slug === "product-image" && (
            <>
              <div className="field">
                <label>出图引擎</label>
                <select
                  name="image_model_provider"
                  value={formValues.image_model_provider}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, image_model_provider: event.target.value }))}
                >
                  {IMAGE_MODEL_PROVIDER_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
                <div className="muted">
                  {(IMAGE_MODEL_PROVIDER_OPTIONS.find((item) => item.value === formValues.image_model_provider) || IMAGE_MODEL_PROVIDER_OPTIONS[0]).hint}
                </div>
              </div>
              <div className="field"><label>产品类型</label><select name="product_type" value={formValues.product_type} onChange={(event) => setFormValues((prev) => ({ ...prev, product_type: event.target.value }))}><option value="">让系统判断（默认）</option>{PRODUCT_TYPE_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><div className="muted">优先按你选择的产品类型生成参考板，避免包误走服装逻辑。</div></div>
              {formValues.product_type === "other" && <div className="field"><label>补充产品类型</label><input name="product_type_other" value={formValues.product_type_other} onChange={(event) => setFormValues((prev) => ({ ...prev, product_type_other: event.target.value }))} placeholder="例如：行李箱 / 杯子 / 台灯" /></div>}
              <div className="field"><label>场景风格</label><input name="scene_style" value={formValues.scene_style} onChange={(event) => setFormValues((prev) => ({ ...prev, scene_style: event.target.value }))} /></div>
              <div className="field"><label>出图目标（逗号）</label><input name="scene_goals" value={formValues.scene_goals} onChange={(event) => setFormValues((prev) => ({ ...prev, scene_goals: event.target.value }))} /></div>
              <div className="field">
                <label>目标成片数 *</label>
                <input
                  name="target_final_count"
                  type="number"
                  min={3}
                  max={30}
                  value={formValues.target_final_count}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, target_final_count: Number(event.target.value || 9) }))}
                />
                <div className="muted">最终要交付的图片张数。</div>
              </div>
              <div className="field">
                <label>每方案试拍数 *</label>
                <input
                  name="takes_per_shot"
                  type="number"
                  min={1}
                  max={4}
                  value={formValues.takes_per_shot}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, takes_per_shot: Number(event.target.value || 3) }))}
                />
                <div className="muted">每个镜头生成几张候选图，像摄影师连拍供你选片。</div>
              </div>
            </>
          )}

          {tool.slug === "model-retouch" && (
            <>
              <div className="field"><label>精修目标（逗号）</label><input name="retouch_targets" value={formValues.retouch_targets} onChange={(event) => setFormValues((prev) => ({ ...prev, retouch_targets: event.target.value }))} /></div>
              <div className="field"><label>保真要求</label><input name="fidelity_requirement" value={formValues.fidelity_requirement} onChange={(event) => setFormValues((prev) => ({ ...prev, fidelity_requirement: event.target.value }))} /></div>
              <div className="field"><label><input name="identity_replace" type="checkbox" value="true" checked={formValues.identity_replace} onChange={(event) => setFormValues((prev) => ({ ...prev, identity_replace: event.target.checked }))} /> 开启替换模特流程</label></div>
              <div className="field">
                <label>默认背景策略</label>
                <select
                  name="background_policy"
                  value={formValues.background_policy}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, background_policy: event.target.value }))}
                >
                  <option value="keep_original">保留原背景（默认）</option>
                  <option value="regenerate">允许重构背景</option>
                </select>
              </div>
              <div className="field">
                <label>输出比例</label>
                <select
                  name="output_aspect_ratio"
                  value={formValues.output_aspect_ratio}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, output_aspect_ratio: event.target.value }))}
                >
                  <option value="original">原图比例（默认）</option>
                  <option value="1:1">1:1</option>
                  <option value="4:5">4:5</option>
                  <option value="3:4">3:4</option>
                  <option value="9:16">9:16</option>
                  <option value="16:9">16:9</option>
                </select>
              </div>
              <div className="field">
                <label>精修强度</label>
                <select
                  name="retouch_strength"
                  value={formValues.retouch_strength}
                  onChange={(event) => setFormValues((prev) => ({ ...prev, retouch_strength: event.target.value }))}
                >
                  <option value="light">轻度保真（默认）</option>
                  <option value="medium">中度优化</option>
                  <option value="heavy">重度创意</option>
                </select>
              </div>
            </>
          )}

          {tool.slug !== "multi-angle-camera" && tool.slug !== "quick-video-15s" ? (
            <details className="details" open={advancedOpen} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)} style={{ gridColumn: "1 / -1" }}>
              <summary>高级设置（可选）</summary>
              <div className="grid" style={{ marginTop: 10 }}>
                <div className="field"><label>关键卖点（逗号）</label><input name="key_features" value={formValues.key_features} onChange={(event) => setFormValues((prev) => ({ ...prev, key_features: event.target.value }))} /></div>
                <div className="field"><label>受众</label><input name="target_audience" value={formValues.target_audience} onChange={(event) => setFormValues((prev) => ({ ...prev, target_audience: event.target.value }))} /></div>
                <div className="field"><label>语气</label><input name="tone" value={formValues.tone} onChange={(event) => setFormValues((prev) => ({ ...prev, tone: event.target.value }))} /></div>
                <div className="field"><label>证据点（逗号）</label><input name="evidence_points" value={formValues.evidence_points} onChange={(event) => setFormValues((prev) => ({ ...prev, evidence_points: event.target.value }))} /></div>
                <div className="field"><label>渠道（逗号）</label><input name="channels" value={formValues.channels} onChange={(event) => setFormValues((prev) => ({ ...prev, channels: event.target.value }))} /></div>
                <div className="field"><label>合规屏蔽词（逗号）</label><input name="compliance_blocklist" value={formValues.compliance_blocklist} onChange={(event) => setFormValues((prev) => ({ ...prev, compliance_blocklist: event.target.value }))} /></div>
                <div className="field" style={{ gridColumn: "1 / -1" }}><label>创意指令</label><textarea name="creative_direction" value={formValues.creative_direction} onChange={(event) => setFormValues((prev) => ({ ...prev, creative_direction: event.target.value }))} /></div>
              </div>
            </details>
          ) : tool.slug === "quick-video-15s" ? (
            <details className="details" open={advancedOpen} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)} style={{ gridColumn: "1 / -1" }}>
              <summary>高级设置（可选）</summary>
              <div className="grid" style={{ marginTop: 10 }}>
                <div className="field" style={{ gridColumn: "1 / -1" }}>
                  <label>补充创意约束</label>
                  <textarea
                    name="creative_direction"
                    value={formValues.creative_direction}
                    onChange={(event) => setFormValues((prev) => ({ ...prev, creative_direction: event.target.value }))}
                    placeholder="例如：镜头切换更快，结尾突出优惠信息。"
                  />
                </div>
              </div>
            </details>
          ) : (
            <>
              <input name="key_features" type="hidden" value={formValues.key_features} readOnly />
              <input name="target_audience" type="hidden" value={formValues.target_audience} readOnly />
              <input name="tone" type="hidden" value={formValues.tone} readOnly />
              <input name="evidence_points" type="hidden" value={formValues.evidence_points} readOnly />
              <input name="channels" type="hidden" value={formValues.channels} readOnly />
              <input name="compliance_blocklist" type="hidden" value={formValues.compliance_blocklist} readOnly />
              <input name="creative_direction" type="hidden" value={formValues.creative_direction} readOnly />
            </>
          )}

          {tool.slug === "multi-angle-camera" && (
            <>
              <input type="hidden" name="camera_yaw" value={formValues.camera_yaw} readOnly />
              <input type="hidden" name="camera_pitch" value={formValues.camera_pitch} readOnly />
              <input type="hidden" name="camera_distance" value={formValues.camera_distance} readOnly />
              <input type="hidden" name="camera_focal_mm" value={formValues.camera_focal_mm} readOnly />
              <input type="hidden" name="camera_aspect_ratio" value={formValues.camera_aspect_ratio} readOnly />
            </>
          )}

          <div style={{ gridColumn: "1 / -1" }} className="toolbar" data-cta-scope={`tool-tasks.create.${tool.slug}`}>
            <button type="submit" className="btn-primary" disabled={creating}>{creating ? "提交中：正在创建..." : tool.slug === "model-retouch" ? "创建批次并进入工作台" : tool.slug === "multi-angle-camera" ? "创建并进入机位台" : "创建并进入工作台"}</button>
            {tool.slug === "multi-angle-camera" && (
              <span className="muted">进入工作台后先调机位，再生成当前角度单张图。</span>
            )}
          </div>
        </form>
        <div className={cx("status-banner", createStatus.type)}>{createStatus.text}</div>
        {tool.slug === "model-retouch" && (lastCreatedBatchId || lastCreatedProjectId) && (
          <div className="toolbar" style={{ marginTop: 8 }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => navigate(
                lastCreatedBatchId
                  ? `/app/tools/${tool.slug}/batches/${lastCreatedBatchId}`
                  : `/app/tools/${tool.slug}/projects/${lastCreatedProjectId}`
              )}
            >
              进入刚创建批次
            </button>
          </div>
        )}
      </section>

      <section className="card task-center-hero-card">
        <div className="task-center-hero">
          <div className="task-center-hero-copy">
            <div className="studio-section-kicker">任务中心</div>
            <h2 className="title-row"><Icon name="task" size={18} />先处理阻塞，再继续最近任务</h2>
            <p className="muted">这页只负责两件事：创建新任务，以及把当前最值得处理的任务提到最前面。先清阻塞，再回到最近任务推进。</p>
          </div>
          <div className="task-center-hero-kpis">
            <div className="task-center-hero-kpi">
              <span>卡住</span>
              <strong>{taskOverview.blocked}</strong>
            </div>
            <div className="task-center-hero-kpi">
              <span>待确认</span>
              <strong>{taskOverview.pending}</strong>
            </div>
            <div className="task-center-hero-kpi">
              <span>执行中</span>
              <strong>{taskOverview.running}</strong>
            </div>
            <div className="task-center-hero-kpi">
              <span>总任务</span>
              <strong>{taskOverview.total}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="card task-center-card">
        <div className="ops-banner task-center-head">
          <div>
            <h2 className="title-row" style={{ marginBottom: 4 }}><Icon name="task" size={16} />任务优先队列</h2>
            <p className="muted">默认优先显示卡住/待确认/执行中任务，再显示最近 3 条任务。</p>
          </div>
          <div className="toolbar task-center-tools">
            <input placeholder="关键词搜索" value={query} onChange={(event) => setQuery(event.target.value)} style={{ width: 220 }} />
            <button type="button" className="btn-secondary" onClick={loadData}>搜索</button>
            <button type="button" className="btn-secondary" onClick={loadData}>刷新</button>
          </div>
        </div>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        {!filteredTaskRows.length ? (
          <div className="empty-state" style={{ marginTop: 10 }}>暂无任务</div>
        ) : (
          <>
            {tool.slug === "product-image" ? (
              <div className="toolbar task-center-filters task-center-filter-strip" style={{ marginTop: 10 }}>
                <button type="button" className={cx("btn-secondary", taskFilter === "all" && "active")} onClick={() => setTaskFilter("all")}>全部</button>
                <button type="button" className={cx("btn-secondary", taskFilter === "product_lock" && "active")} onClick={() => setTaskFilter("product_lock")}>待锁主体({taskFilterStats.product_lock})</button>
                <button type="button" className={cx("btn-secondary", taskFilter === "review" && "active")} onClick={() => setTaskFilter("review")}>待选片({taskFilterStats.review})</button>
                <button type="button" className={cx("btn-secondary", taskFilter === "blocked" && "active")} onClick={() => setTaskFilter("blocked")}>需重试({taskFilterStats.blocked})</button>
              </div>
            ) : null}
            <div className="tool-grid task-center-columns" style={{ marginTop: 10 }}>
              <article className="tool-card task-center-bucket">
                <h3 className="title-row"><Icon name="spark" size={15} />优先处理（最多 6 条）</h3>
                <p className="muted" style={{ marginTop: 6 }}>先处理卡住、待确认、执行中的关键任务；上方清完阻塞，再回到最近任务继续推进。</p>
                {!priorityRows.length ? (
                  <p className="muted">当前没有卡住、待确认或执行中的任务。</p>
                ) : (
                  <div className="asset-grid">
                    {priorityRows.map((task) => (
                      (() => {
                        const showRiskChip = shouldShowTaskRiskChip(task, tool.slug, STATUS_LABEL);
                        const showDeliveryProgress = shouldShowDeliveryProgress(task, tool.slug);
                        return (
                      <article
                        key={`priority-${task.batch_group_id || task.project_id}`}
                        className="asset-card task-card"
                        style={highlightBatch && task.batch_group_id === highlightBatch ? { background: "#fff8e8" } : undefined}
                      >
                        <div><strong>{task.batch_group_id ? `批次：${task.batch_group_id}` : task.product_name}</strong></div>
                        {task._batch_total ? <div className="muted">任务数：{task._batch_total}</div> : null}
                        <div className="task-card-meta-strip">
                          <span className="badge">{stageLabel(task.current_stage, tool.slug)}</span>
                          {showRiskChip ? <span className={cx("badge", task._risk === "blocked" && "warning")}>{TASK_RISK_LABEL[task._risk] || "普通"}</span> : null}
                          <span className="badge">{taskCardStatusLabel(task, tool.slug, STATUS_LABEL)}</span>
                        </div>
                        {showDeliveryProgress ? (
                          <div className="task-card-progress-strip">
                            已选 {task.selected_final_count}/{task.required_final_count} · 候选 {task.candidate_total}
                          </div>
                        ) : null}
                        <div className="muted">进度：{task.progress_percent}% · 更新于 {formatDate(task.updated_at)}</div>
                        <div className="toolbar task-card-action-row" style={{ marginTop: 8 }}>
                          <button type="button" className="btn-secondary" onClick={() => navigate(resolveTaskWorkspacePath(task, TOOL_BY_TYPE))}>{taskOpenLabel(task, tool.slug)}</button>
                        </div>
                        <div className="task-card-next-action">下一步：{task.next_action || taskNextActionHint(task)}</div>
                      </article>
                        );
                      })()
                    ))}
                  </div>
                )}
              </article>
              <article className="tool-card task-center-bucket">
                <h3 className="title-row"><Icon name="gallery" size={15} />最近 3 条</h3>
                <p className="muted" style={{ marginTop: 6 }}>这里只展示未进入“优先处理”的最近任务，不和上方重复，方便顺手续做。</p>
                <div className="asset-grid">
                  {recentRows.map((task) => (
                    (() => {
                      const risk = resolveTaskRisk(task);
                      const showRiskChip = shouldShowTaskRiskChip(task, tool.slug, STATUS_LABEL);
                      const showDeliveryProgress = shouldShowDeliveryProgress(task, tool.slug);
                      return (
                    <article
                      key={`recent-${task.batch_group_id || task.project_id}`}
                      className="asset-card task-card"
                      style={highlightBatch && task.batch_group_id === highlightBatch ? { background: "#fff8e8" } : undefined}
                    >
                      <div><strong>{task.batch_group_id ? `批次：${task.batch_group_id}` : task.product_name}</strong></div>
                      <div className="task-card-meta-strip">
                        <span className="badge">{stageLabel(task.current_stage, tool.slug)}</span>
                        {showRiskChip ? <span className={cx("badge", risk === "blocked" && "warning")}>{TASK_RISK_LABEL[risk] || "普通"}</span> : null}
                        <span className="badge">{taskCardStatusLabel(task, tool.slug, STATUS_LABEL)}</span>
                      </div>
                      {showDeliveryProgress ? (
                        <div className="task-card-progress-strip">
                          已选 {task.selected_final_count}/{task.required_final_count} · 候选 {task.candidate_total}
                        </div>
                      ) : null}
                      <div className="muted">进度：{task.progress_percent}% · 更新于 {formatDate(task.updated_at)}</div>
                      <div className="toolbar task-card-action-row" style={{ marginTop: 8 }}>
                        <button type="button" className="btn-secondary" onClick={() => navigate(resolveTaskWorkspacePath(task, TOOL_BY_TYPE))}>{taskOpenLabel(task, tool.slug)}</button>
                      </div>
                      <div className="task-card-next-action">下一步：{task.next_action || taskNextActionHint(task)}</div>
                    </article>
                      );
                    })()
                  ))}
                </div>
              </article>
            </div>

            <details className="details task-center-details" style={{ marginTop: 10 }}>
              <summary><span className="title-row"><Icon name="task" size={15} />查看全部任务（{filteredTaskRows.length}）</span></summary>
              {tool.slug === "model-retouch" ? (
                <div className="retouch-wall" style={{ marginTop: 8 }}>
                  {filteredTaskRows.map((task) => (
                    <article
                      key={task.batch_group_id || task.project_id}
                      className="asset-card"
                      style={highlightBatch && task.batch_group_id === highlightBatch ? { background: "#fff8e8" } : undefined}
                    >
                      <div><strong>{task.batch_group_id ? `批次：${task.batch_group_id}` : task.product_name}</strong></div>
                      {task._batch_total ? <div className="muted">任务数：{task._batch_total}</div> : null}
                      <div className="muted">阶段：{stageLabel(task.current_stage, tool.slug)}</div>
                      {shouldShowDeliveryProgress(task, tool.slug) ? (
                        <div className="task-card-progress-strip">
                          已选 {task.selected_final_count}/{task.required_final_count} · 候选 {task.candidate_total}
                        </div>
                      ) : null}
                      <div className="muted">进度：{task.progress_percent}% · {formatProgressLabel(task.progress_label)}</div>
                      <div className="toolbar" style={{ marginTop: 8 }}>
                        <span className="badge">{taskCardStatusLabel(task, tool.slug, STATUS_LABEL)}</span>
                        <button type="button" className="btn-secondary" onClick={() => navigate(resolveTaskWorkspacePath(task, TOOL_BY_TYPE))}>
                          {taskOpenLabel(task, tool.slug)}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="table-wrap" style={{ marginTop: 8 }}>
                  <table className="table">
                    <thead><tr><th>任务</th><th>阶段</th><th>交付</th><th>进度</th><th>风险</th><th>下一步</th><th>状态</th><th>更新时间</th><th>操作</th></tr></thead>
                    <tbody>
                      {filteredTaskRows.map((task) => {
                        const risk = resolveTaskRisk(task);
                        return (
                          <tr key={task.project_id} style={highlightBatch && task.batch_group_id === highlightBatch ? { background: "#fff8e8" } : undefined}>
                            <td><strong>{task.product_name}</strong>{task.batch_group_id && <div className="muted">批次：{task.batch_group_id}</div>}</td>
                            <td>{stageLabel(task.current_stage, tool.slug)}</td>
                            <td className="muted">
                              {tool.slug === "product-image" && task.required_final_count > 0
                                ? `已选 ${task.selected_final_count}/${task.required_final_count} · 候选 ${task.candidate_total}`
                                : "-"}
                            </td>
                            <td>{task.progress_percent}%<div className="muted">{formatProgressLabel(task.progress_label)}</div></td>
                            <td><span className={cx("badge", risk === "blocked" && "warning")}>{TASK_RISK_LABEL[risk] || "普通"}</span></td>
                            <td className="muted">{task.next_action || taskNextActionHint(task)}</td>
                            <td><span className="badge">{taskCardStatusLabel(task, tool.slug, STATUS_LABEL)}</span></td>
                            <td>{formatDate(task.updated_at)}</td>
                            <td><button type="button" className="btn-secondary" onClick={() => navigate(resolveTaskWorkspacePath(task, TOOL_BY_TYPE))}>{taskOpenLabel(task, tool.slug)}</button></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </details>
          </>
        )}
      </section>
    </div>
  );
}
