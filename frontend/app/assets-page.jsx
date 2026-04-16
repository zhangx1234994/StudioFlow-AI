"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiFetch, assetReviewBucket, candidateCaption, cx, ecommerceCaption, formatDate, formatProgressLabel } from "./app-utils";
import { localPathToMedia, resolveAssetImageSrc } from "./media-utils";
import { resolveTaskWorkspacePath, resolveTaskRisk, stageLabel, taskNextActionHint, TASK_RISK_LABEL } from "./workspace-flow";
import { ASSET_KIND_LABEL, assetKindLabel, assetSourceLabel, assetStatusLabel, TOOL_BY_TYPE, HIDDEN_WEB_TOOL_SLUGS, STATUS_LABEL, VISIBLE_TOOL_LIST, toolIconName } from "./tool-config";
import { applyImageFallback, fallbackImageForToolType } from "./ui-config";
import { Icon } from "./shared-ui";
import { shouldShowDeliveryProgress } from "./task-page-helpers";

export function AssetsPage({ navigate }) {
  const [assets, setAssets] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [showcaseAssets, setShowcaseAssets] = useState([]);
  const [activeTab, setActiveTab] = useState("tasks");
  const [status, setStatus] = useState({ text: "准备加载资产中台...", type: "" });
  const [remixingAssetId, setRemixingAssetId] = useState("");
  const formRef = useRef(null);

  const queryAll = useCallback(async () => {
    const fd = new FormData(formRef.current);
    const params = new URLSearchParams();
    ["source_type", "tool_type", "project_id", "tag", "keyword", "limit"].forEach((key) => {
      const value = String(fd.get(key) || "").trim();
      if (value) params.set(key, value);
    });
    if (!params.get("limit")) params.set("limit", "120");
    setStatus({ text: "正在同步资产、任务与样片...", type: "" });
    try {
      const [assetRows, taskRows, showcaseRows] = await Promise.all([
        apiFetch(`/api/v1/assets?${params.toString()}`),
        apiFetch("/api/v1/projects?limit=80"),
        apiFetch("/api/v1/showcase/assets?limit=120"),
      ]);
      setAssets(Array.isArray(assetRows) ? assetRows : []);
      setTasks(Array.isArray(taskRows) ? taskRows : []);
      setShowcaseAssets((Array.isArray(showcaseRows) ? showcaseRows : []).filter((item) => String(item?.kind || "").toLowerCase() === "generated_image"));
      setStatus({
        text: `同步完成：素材 ${assetRows.length} ｜任务 ${taskRows.length} ｜样片 ${showcaseRows.length}`,
        type: "success",
      });
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    }
  }, []);

  useEffect(() => { queryAll(); }, [queryAll]);

  const assetCoverByProject = useMemo(() => {
    const map = {};
    for (const item of assets) {
      if (map[item.project_id]) continue;
      const imageUrl = item.image_url || localPathToMedia(item.local_path);
      if (imageUrl) map[item.project_id] = imageUrl;
    }
    return map;
  }, [assets]);

  const hubKpis = useMemo(() => {
    // 区分"执行中"和"排队中"
    const running = tasks.filter((item) => item.status === "running" || item.status === "rendering").length;
    const queued = tasks.filter((item) => item.status === "queued").length;
    const completed = tasks.filter((item) => item.status === "done" || item.status === "completed").length;
    const approvedAssets = assets.filter((item) => item.status === "reviewed" || item.status === "approved").length;
    return {
      running,
      queued,
      completed,
      assets: assets.length,
      showcase: showcaseAssets.length,
      approvedAssets,
    };
  }, [tasks, assets, showcaseAssets]);

  const latestTasks = useMemo(() => (
    [...tasks].filter((item) => !HIDDEN_WEB_TOOL_SLUGS.has(TOOL_BY_TYPE[item.tool_type]?.slug || "")).sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()).slice(0, 18)
  ), [tasks]);
  const continueTask = latestTasks[0] || null;
  const continueTool = continueTask ? TOOL_BY_TYPE[continueTask.tool_type] : null;

  const latestAssets = useMemo(() => (
    [...assets].filter((item) => !HIDDEN_WEB_TOOL_SLUGS.has(TOOL_BY_TYPE[item.tool_type]?.slug || "")).sort((a, b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime()).slice(0, 24)
  ), [assets]);

  const latestShowcase = useMemo(() => (
    [...showcaseAssets].filter((item) => !HIDDEN_WEB_TOOL_SLUGS.has(TOOL_BY_TYPE[item.tool_type]?.slug || "")).sort((a, b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime()).slice(0, 18)
  ), [showcaseAssets]);
  const assetHeroLead = latestShowcase[0] || null;
  const assetHeroSecondary = latestShowcase.slice(1, 3);
  const assetHeroLeadSrc = assetHeroLead
    ? assetHeroLead.image_url || assetHeroLead?.metadata?.preview_image_url || fallbackImageForToolType(assetHeroLead.tool_type)
    : "";

  const remixFromShowcase = async (assetId) => {
    if (!assetId) return;
    setRemixingAssetId(assetId);
    setStatus({ text: "正在创建同款任务...", type: "" });
    try {
      const data = await apiFetch("/api/v1/showcase/remix", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: assetId }),
      });
      const projectId = data?.project?.project_id || "";
      const tool = TOOL_BY_TYPE[data?.project?.tool_type];
      if (!projectId || !tool) throw new Error("同款任务创建失败，请重试。");
      setStatus({ text: "同款任务已创建，正在进入工作台。", type: "success" });
      navigate(`/app/tools/${tool.slug}/projects/${projectId}`);
    } catch (error) {
      setStatus({ text: String(error?.message || "同款创建失败"), type: "error" });
    } finally {
      setRemixingAssetId("");
    }
  };

  return (
    <div className="content-stack">
      <section className="card hub-hero-card asset-hub-hero-card page-hero-card">
        <div className="asset-hub-hero asset-hub-hero-luxe">
          <div className="asset-hub-copy">
            <div className="asset-hub-kicker"><Icon name="assets" size={14} />资产控制台</div>
            <h1 className="title-row"><Icon name="assets" size={20} />资产操作台</h1>
            <p className="card-subtitle">把任务、素材、样片放到同一张运营画布里，优先处理当前最该推进的内容，再把优质结果推向样片墙和复用模板。</p>
            <div className="toolbar asset-hub-cta-row">
              <button type="button" className="btn-primary" onClick={() => setActiveTab("tasks")}>进入任务流</button>
              <button type="button" className="btn-secondary" onClick={() => setActiveTab("library")}>查看素材库</button>
              <button type="button" className="btn-secondary" onClick={() => setActiveTab("showcase")}>运营样片墙</button>
            </div>
            <div className="asset-hub-kpis">
              <div className="asset-hub-kpi"><span>执行中</span><strong>{hubKpis.running}</strong></div>
              {hubKpis.queued > 0 && <div className="asset-hub-kpi"><span>排队中</span><strong>{hubKpis.queued}</strong></div>}
              <div className="asset-hub-kpi"><span>已完成</span><strong>{hubKpis.completed}</strong></div>
              <div className="asset-hub-kpi"><span>素材总量</span><strong>{hubKpis.assets}</strong></div>
              <div className="asset-hub-kpi"><span>已分享样片</span><strong>{hubKpis.showcase}</strong></div>
            </div>
          </div>
          <div className="asset-hub-stageboard">
            <div className="asset-hub-stageboard-head">
              <span className="badge"><Icon name="gallery" size={12} />样片中心</span>
              <span className="badge"><Icon name="task" size={12} />任务优先级</span>
            </div>
            <div className="asset-hub-stageboard-grid">
              <article className="asset-hub-stage-main">
                {assetHeroLeadSrc ? (
                  <img
                    src={assetHeroLeadSrc}
                    alt="样片主视觉"
                    onError={(event) => applyImageFallback(event, fallbackImageForToolType(assetHeroLead.tool_type))}
                  />
                ) : (
                  <div className="showcase-placeholder"><strong>等待样片沉淀</strong></div>
                )}
                <div className="asset-hub-stage-caption">最新可运营样片</div>
              </article>
              <div className="asset-hub-stage-side">
                {assetHeroSecondary.map((asset, idx) => (
                  <article key={asset.asset_id || idx} className="asset-hub-stage-tile">
                    {(asset.image_url || asset?.metadata?.preview_image_url || fallbackImageForToolType(asset.tool_type)) ? (
                      <img
                        src={asset.image_url || asset?.metadata?.preview_image_url || fallbackImageForToolType(asset.tool_type)}
                        alt="样片缩略图"
                        onError={(event) => applyImageFallback(event, fallbackImageForToolType(asset.tool_type))}
                      />
                    ) : (
                      <div className="showcase-placeholder"><strong>等待样片</strong></div>
                    )}
                    <div className="asset-hub-stage-caption">{ASSET_KIND_LABEL[asset.kind] || "样片结果"}</div>
                  </article>
                ))}
                {assetHeroSecondary.length === 0 ? (
                  <article className="asset-hub-stage-tile asset-hub-stage-empty">
                    <strong>还没有更多样片</strong>
                    <span>创建任务并主动分享后，这里会成为你的运营封面区。</span>
                  </article>
                ) : null}
              </div>
            </div>
          </div>
        </div>
        {continueTask ? (
          <div className="home-continue-band asset-hub-continue-band">
            <div>
              <div className="home-continue-label">继续当前重点任务</div>
              <strong>{continueTask.product_name || "未命名任务"}</strong>
              <span> · {continueTool?.title || continueTask.tool_type} · {stageLabel(continueTask.current_stage, continueTool?.slug)}</span>
              {shouldShowDeliveryProgress(continueTask, continueTool?.slug) ? (
                <div className="home-continue-metrics">
                  <span className="badge">已选 {continueTask.selected_final_count}/{continueTask.required_final_count}</span>
                  <span className="badge">候选 {continueTask.candidate_total}</span>
                </div>
              ) : null}
              <div className="muted" style={{ marginTop: 4 }}>下一步：{continueTask.next_action || taskNextActionHint(continueTask) || "立即回到工作台继续处理"}</div>
            </div>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => navigate(resolveTaskWorkspacePath(continueTask, TOOL_BY_TYPE))}
            >
              立即继续
            </button>
          </div>
        ) : null}
        <div className={cx("status-banner", status.type)}>{status.text}</div>
      </section>

      <section className="card asset-hub-card page-content-card">
        <div className="asset-hub-head page-tab-head">
          <div className="asset-hub-tabs">
            <button type="button" className={cx("asset-hub-tab", activeTab === "tasks" && "active")} onClick={() => setActiveTab("tasks")}>任务中心 · {tasks.length}</button>
            <button type="button" className={cx("asset-hub-tab", activeTab === "library" && "active")} onClick={() => setActiveTab("library")}>素材中心 · {assets.length}</button>
            <button type="button" className={cx("asset-hub-tab", activeTab === "showcase" && "active")} onClick={() => setActiveTab("showcase")}>样片中心 · {showcaseAssets.length}</button>
          </div>
          <div className="toolbar">
            <button type="button" className="btn-secondary" onClick={queryAll}>刷新中心</button>
            <button type="button" className="btn-ghost" onClick={() => navigate("/app/tools")}>返回工具箱</button>
          </div>
        </div>

        {activeTab === "tasks" ? (
          <section className="asset-hub-priority">
            <div className="asset-hub-priority-copy">
              <div className="studio-section-kicker">当前优先</div>
              <h2 className="title-row"><Icon name="task" size={16} />先处理最值得推进的任务</h2>
              <p className="muted">资产中台不是素材仓库首页，而是任务、素材、样片三条线的交汇口。先继续当前重点任务，再决定是否进入素材和样片视图。</p>
            </div>
            {continueTask ? (
              <article className="asset-hub-priority-card">
                <div className="asset-hub-priority-meta">
                  <span className="badge">{continueTool?.title || continueTask.tool_type}</span>
                  <span className="badge">{stageLabel(continueTask.current_stage, continueTool?.slug)}</span>
                </div>
                <strong>{continueTask.product_name || "未命名任务"}</strong>
                <p className="muted">下一步：{continueTask.next_action || taskNextActionHint(continueTask) || "立即回到工作台继续处理"}</p>
                <div className="toolbar" style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => navigate(resolveTaskWorkspacePath(continueTask, TOOL_BY_TYPE))}
                  >
                    立即继续
                  </button>
                </div>
              </article>
            ) : (
              <article className="asset-hub-priority-card asset-hub-priority-empty">
                <strong>当前没有待继续任务</strong>
                <p className="muted">先从工具箱创建任务，任务进展会自动汇聚到这里。</p>
              </article>
            )}
          </section>
        ) : null}

        <details className="details low-priority-card" style={{ marginTop: 10 }}>
          <summary><span className="title-row"><Icon name="task" size={14} />高级筛选（可选）</span></summary>
          <form ref={formRef} className="grid" style={{ marginTop: 10 }}>
            <div className="field"><label>来源</label><select name="source_type" defaultValue=""><option value="">全部</option><option value="uploaded">用户上传</option><option value="generated">AI生成</option></select></div>
            <div className="field"><label>工具</label><select name="tool_type" defaultValue=""><option value="">全部</option>{VISIBLE_TOOL_LIST.map((tool) => <option key={tool.toolType} value={tool.toolType}>{tool.title}</option>)}</select></div>
            <div className="field"><label>任务编号</label><input name="project_id" /></div>
            <div className="field"><label>标签</label><input name="tag" /></div>
            <div className="field"><label>关键词</label><input name="keyword" /></div>
            <div className="field"><label>返回数量</label><input name="limit" type="number" defaultValue="120" min="1" max="1000" /></div>
          </form>
        </details>

        {activeTab === "tasks" ? (
          !latestTasks.length ? (
            <div className="empty-state premium-empty" style={{ marginTop: 10 }}>
              <div className="title-row"><Icon name="task" size={16} />暂无任务</div>
              <p className="muted">先创建任务，任务进展会自动聚合在这里。</p>
              <div className="toolbar"><button type="button" className="btn-primary" onClick={() => navigate("/app/tools/product-image/tasks")}>去创建任务</button></div>
            </div>
          ) : (
            <div className="asset-task-grid" style={{ marginTop: 10 }}>
              {latestTasks.map((task) => {
                const tool = TOOL_BY_TYPE[task.tool_type];
                const cover = assetCoverByProject[task.project_id] || "";
                const goPath = tool?.slug === "model-retouch" && task.batch_group_id
                  ? `/app/tools/model-retouch/batches/${task.batch_group_id}`
                  : `/app/tools/${tool?.slug || "product-image"}/projects/${task.project_id}`;
                const progress = Number(task.progress_percent || 0);
                const risk = resolveTaskRisk(task);
                return (
                  <article key={task.project_id} className="asset-task-card">
                    <div className="asset-task-cover">
                      {cover ? (
                        <img
                          src={cover}
                          alt={task.product_name || task.project_id}
                          onError={(event) => applyImageFallback(event, fallbackImageForToolType(task.tool_type))}
                        />
                      ) : <div className="asset-task-cover-fallback"><Icon name={toolIconName(tool)} size={18} /></div>}
                    </div>
                    <div className="asset-task-body">
                      <div className="asset-task-header">
                        <div>
                          <div className="asset-task-kicker">{tool?.title || task.tool_type}</div>
                          <div className="title-row"><strong>{task.product_name || "未命名任务"}</strong></div>
                        </div>
                        <span className={cx("badge", risk === "blocked" && "warning")}>{TASK_RISK_LABEL[risk] || "普通"}</span>
                      </div>
                      <div className="muted">{stageLabel(task.current_stage, tool?.slug)} · {STATUS_LABEL[task.status] || task.status}</div>
                      <div className="asset-task-progress">
                        <div className="asset-task-progress-bar" style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }} />
                      </div>
                      <div className="asset-task-meta-row">
                        <span className="badge">{formatProgressLabel(task.progress_label)}</span>
                        <span className="muted">{formatDate(task.updated_at)}</span>
                      </div>
                      <div className="asset-task-next">
                        <span>下一步</span>
                        <strong>{task.next_action || taskNextActionHint(task)}</strong>
                      </div>
                      <div className="toolbar asset-task-actions" style={{ marginTop: 8 }}>
                        <button type="button" className="btn-secondary" onClick={() => navigate(goPath)}>进入工作台</button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )
        ) : null}

        {activeTab === "library" ? (
          !latestAssets.length ? (
            <div className="empty-state premium-empty" style={{ marginTop: 10 }}>
              <div className="title-row"><Icon name="assets" size={16} />暂无素材</div>
              <p className="muted">你上传或生成的素材会在这里持续累积。</p>
            </div>
          ) : (
            <div className="asset-grid" style={{ marginTop: 10 }}>
              {latestAssets.map((asset) => {
                const imageUrl = resolveAssetImageSrc(asset);
                const videoUrl = asset.video_url || localPathToMedia(asset.local_path);
                const tool = TOOL_BY_TYPE[asset.tool_type];
                return (
                  <article key={asset.asset_id} className="asset-card result-asset-card library-asset-card">
                    {imageUrl ? (
                      <img
                        src={imageUrl}
                        alt="asset"
                        onError={(event) => applyImageFallback(event, fallbackImageForToolType(asset.tool_type))}
                      />
                    ) : videoUrl ? <video src={videoUrl} controls preload="metadata" /> : <div className="empty-state">无预览</div>}
                    <div className="result-asset-body">
                      <div className="result-asset-head">
                        <span className="badge">{assetSourceLabel(asset.source_type)}</span>
                        <span className="badge">{assetKindLabel(asset.kind)}</span>
                        {asset.status === "reviewed" || asset.status === "approved" ? <span className="badge">精选</span> : null}
                      </div>
                      <div className="asset-task-kicker">{tool?.title || asset.tool_type}</div>
                      <div className="result-asset-copy muted">任务编号：{asset.project_id}</div>
                      <div className="muted result-asset-note">处理状态：{assetStatusLabel(asset.status)}</div>
                      {tool ? <button type="button" className="btn-secondary" style={{ marginTop: 8 }} onClick={() => navigate(`/app/tools/${tool.slug}/projects/${asset.project_id}`)}>打开项目</button> : null}
                    </div>
                  </article>
                );
              })}
            </div>
          )
        ) : null}

        {activeTab === "showcase" ? (
          !latestShowcase.length ? (
            <div className="empty-state premium-empty" style={{ marginTop: 10 }}>
              <div className="title-row"><Icon name="gallery" size={16} />暂无样片</div>
              <p className="muted">你在选片分享阶段推送到首页的图片会出现在这里。</p>
            </div>
          ) : (
            <div className="showcase-grid" style={{ marginTop: 10 }}>
              {latestShowcase.map((asset) => {
                const imageUrl = localPathToMedia(asset.local_path) || asset.image_url || "";
                return (
                  <article key={asset.asset_id} className="showcase-card showcase-card-rich">
                    {imageUrl ? (
                      <img
                        src={imageUrl}
                        alt="showcase"
                        onError={(event) => applyImageFallback(event, fallbackImageForToolType(asset.tool_type))}
                      />
                    ) : <div className="showcase-placeholder"><strong>暂无预览</strong></div>}
                    <div className="showcase-meta">
                      <div>
                        <div className="tool-card-kicker">{TOOL_BY_TYPE[asset.tool_type]?.title || asset.tool_type}</div>
                        <div><strong>{asset.project_id?.slice(0, 8) || "样片任务"}</strong></div>
                        <div className="muted">{formatDate(asset.updated_at || asset.created_at)}</div>
                      </div>
                      <div className="toolbar">
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={remixingAssetId === asset.asset_id}
                          onClick={() => remixFromShowcase(asset.asset_id)}
                        >
                          {remixingAssetId === asset.asset_id ? "创建中..." : "拍同款"}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )
        ) : null}
      </section>
    </div>
  );
}
