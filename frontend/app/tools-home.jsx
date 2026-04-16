"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";

import { apiFetch, cx, formatDate, formatProgressLabel } from "./app-utils";
import { localPathToMedia, resolveAssetImageSrc } from "./media-utils";
import { resolveTaskRisk, resolveTaskWorkspacePath, stageLabel, taskNextActionHint, TASK_RISK_LABEL } from "./workspace-flow";
import { HIDDEN_WEB_TOOL_SLUGS, STATUS_LABEL, TOOL_BY_TYPE, TOOLS, VISIBLE_TOOL_LIST, toolIconName } from "./tool-config";
import { applyImageFallback, fallbackImageForToolType, HOT_SELLING_TRACKS, SALES_PACKAGES, SHOWCASE_TABS, SHOWCASE_FALLBACK_IMAGES, STUDIO_SHOWCASE_CASES } from "./ui-config";
import { Icon } from "./shared-ui";
import { shouldShowDeliveryProgress } from "./task-page-helpers";

export function ToolsHome({ navigate }) {
  const [kpi, setKpi] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [showcaseAssets, setShowcaseAssets] = useState([]);
  const [activeShowcaseTab, setActiveShowcaseTab] = useState("all");
  const [remixingAssetId, setRemixingAssetId] = useState("");
  const [status, setStatus] = useState({ text: "加载中...", type: "" });

  const load = useCallback(async () => {
    setStatus({ text: "加载看板数据...", type: "" });
    try {
      const [kpiRes, tasksRes] = await Promise.all([
        apiFetch("/api/v1/tools/kpi"),
        apiFetch("/api/v1/projects?limit=8"),
      ]);
      const assetsRes = await apiFetch("/api/v1/showcase/assets?limit=120");
      setKpi(kpiRes);
      setTasks(tasksRes);
      setShowcaseAssets(
        assetsRes.filter((item) => String(item?.kind || "").toLowerCase() === "generated_image")
      );
      setStatus({ text: "看板已更新", type: "success" });
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const showcaseCards = useMemo(() => {
    const grouped = {};
    for (const item of showcaseAssets) {
      if (!grouped[item.tool_type]) grouped[item.tool_type] = [];
      grouped[item.tool_type].push(item);
    }

    return STUDIO_SHOWCASE_CASES.filter((preset) => !HIDDEN_WEB_TOOL_SLUGS.has(preset.toolSlug)).map((preset, idx) => {
      const tool = TOOLS[preset.toolSlug];
      const pool = grouped[tool.toolType] || [];
      const asset = pool.length ? pool[idx % pool.length] : null;
      const fallbackImageUrl = SHOWCASE_FALLBACK_IMAGES[preset.caseId] || "";
      return {
        ...preset,
        tool,
        imageUrl: (asset ? resolveAssetImageSrc(asset) : "") || fallbackImageUrl,
        fallbackImageUrl,
        projectId: asset?.project_id || "",
        assetId: asset?.asset_id || "",
      };
    });
  }, [showcaseAssets]);

  const filteredShowcaseCards = useMemo(() => {
    if (activeShowcaseTab === "all") return showcaseCards;
    return showcaseCards.filter((item) => item.category === activeShowcaseTab);
  }, [showcaseCards, activeShowcaseTab]);
  const sortedTasks = useMemo(
    () => [...tasks].sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()),
    [tasks],
  );
  const visibleTasks = useMemo(() => sortedTasks.slice(0, 5), [sortedTasks]);
  const continueTask = visibleTasks[0] || null;
  const continueTool = continueTask ? TOOL_BY_TYPE[continueTask.tool_type] : null;
  const imageTools = useMemo(() => VISIBLE_TOOL_LIST.filter((tool) => tool.category === "image"), []);
  const videoTools = useMemo(() => VISIBLE_TOOL_LIST.filter((tool) => tool.category === "video"), []);
  const secondaryKpis = useMemo(() => ([
    { label: "项目总数", value: kpi?.total_projects ?? 0 },
    { label: "上传素材", value: kpi?.uploaded_assets ?? 0 },
    { label: "生成素材", value: kpi?.generated_assets ?? 0 },
    { label: "失败任务", value: kpi?.failed_projects ?? 0 },
  ]), [kpi]);

  const featuredShowcaseCard = filteredShowcaseCards.length ? filteredShowcaseCards[0] : null;
  const secondaryShowcaseCards = filteredShowcaseCards.slice(1, 5);
  const visiblePackages = SALES_PACKAGES.slice(0, 2);

  const remixFromShowcase = async (card) => {
    if (!card?.assetId || !card?.tool?.slug) {
      navigate(`/app/tools/${card?.tool?.slug || "product-image"}/tasks`);
      return;
    }
    setRemixingAssetId(card.assetId);
    setStatus({ text: "正在创建同款任务...", type: "" });
    try {
      const data = await apiFetch("/api/v1/showcase/remix", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: card.assetId }),
      });
      const projectId = data?.project?.project_id || "";
      if (!projectId) throw new Error("创建同款任务失败，请重试。");
      setStatus({ text: "同款任务已创建，正在进入工作台。", type: "success" });
      navigate(`/app/tools/${card.tool.slug}/projects/${projectId}`);
    } catch (error) {
      setStatus({ text: String(error?.message || "同款创建失败，请稍后重试。"), type: "error" });
      navigate(`/app/tools/${card.tool.slug}/tasks`);
    } finally {
      setRemixingAssetId("");
    }
  };

  return (
    <div className="content-stack">
      <section className="card home-hero-card studio-home-hero-card">
        <div className="hero-banner hero-banner-luxe">
          <div className="hero-copy">
            <div className="hero-kicker"><Icon name="spark" size={14} />AI摄影棚 · 商业资产工作台</div>
            <h1 className="title-row"><Icon name="spark" size={20} />选择工具，开始出图</h1>
            <p className="card-subtitle">商品棚拍、模特精修、多角度展示、讲解视频、15 秒短片统一放在一套工作流里，先出可编辑草稿，再确认进入下一步。</p>
            <div className="toolbar hero-cta-row" style={{ marginTop: 10 }} data-cta-scope="tools-home.hero">
              <button type="button" className="btn-primary" onClick={() => navigate("/app/tools/product-image/tasks")}>立即开始棚拍</button>
              <button type="button" className="btn-secondary" onClick={() => navigate("/app/assets")}>进入资产中台</button>
            </div>
            <div className="hero-metric-strip">
              <div className="hero-metric-card">
                <span>当前进行中</span>
                <strong>{kpi?.running_projects ?? 0}</strong>
              </div>
              <div className="hero-metric-card">
                <span>今日完成</span>
                <strong>{kpi?.done_projects ?? 0}</strong>
              </div>
              <div className="hero-metric-card">
                <span>已分享样片</span>
                <strong>{kpi?.showcase_assets ?? 0}</strong>
              </div>
            </div>
          </div>
          <div className="hero-stageboard">
            <div className="hero-stageboard-head">
              <span className="badge"><Icon name="gallery" size={12} />摄影棚样片墙</span>
              <span className="badge"><Icon name="cube" size={12} />可复用模板</span>
              <span className="badge"><Icon name="wand" size={12} />批量出图出片</span>
            </div>
            <div className="hero-stageboard-grid">
              <article className="hero-stage-tile hero-stage-tile-main">
                <img src="/static/showcase/main-1.jpg" alt="品牌主图样片" />
                <div className="hero-stage-caption">品牌主图套图</div>
              </article>
              <article className="hero-stage-tile">
                <img src="/static/showcase/model-1.jpg" alt="模特精修样片" />
                <div className="hero-stage-caption">模特精修</div>
              </article>
              <article className="hero-stage-tile">
                <img src="/static/showcase/scene-1.jpg" alt="场景故事样片" />
                <div className="hero-stage-caption">场景叙事</div>
              </article>
            </div>
          </div>
        </div>
        <div className="home-hero-foot">
          <div className="home-hero-foot-meta">
            {secondaryKpis.map((item) => (
              <span key={item.label} className="kpi-chip">{item.label}：{item.value}</span>
            ))}
          </div>
          <div className={cx("status-banner", status.type)}>{status.text}</div>
        </div>
      </section>

      <section className="card studio-home-section-card">
        <div className="studio-section-head">
          <div>
            <div className="studio-section-kicker">优先处理</div>
            <h2 className="title-row"><Icon name="task" size={18} />当前最紧急的任务</h2>
          </div>
          <button type="button" className="btn-secondary" onClick={() => navigate("/app/assets")}>打开资产中台</button>
        </div>
        {!continueTask ? (
          <div className="empty-state premium-empty" style={{ marginTop: 10 }}>
            <div className="title-row"><Icon name="task" size={16} />当前没有待继续任务</div>
            <p className="muted">从商品棚拍或视频工坊创建任务后，这里会优先显示最值得继续推进的那一条。</p>
          </div>
        ) : (
          <article className="studio-urgent-card">
            <div className="studio-urgent-meta">
              <span className="badge">{continueTool?.title || continueTask.tool_type}</span>
              <span className="badge">{stageLabel(continueTask.current_stage, continueTool?.slug)}</span>
              <span className="badge">{STATUS_LABEL[continueTask.status] || continueTask.status}</span>
            </div>
            <h3>{continueTask.product_name || "未命名任务"}</h3>
            <p className="muted">下一步：{continueTask.next_action || taskNextActionHint(continueTask) || "回到工作台继续处理"}</p>
            {shouldShowDeliveryProgress(continueTask, continueTool?.slug) ? (
              <div className="studio-urgent-progress">
                <span className="badge">已选 {continueTask.selected_final_count}/{continueTask.required_final_count}</span>
                <span className="badge">候选 {continueTask.candidate_total}</span>
              </div>
            ) : null}
            <div className="toolbar" style={{ marginTop: 10 }}>
              <button type="button" className="btn-primary" onClick={() => navigate(resolveTaskWorkspacePath(continueTask, TOOL_BY_TYPE))}>回到工作台</button>
            </div>
          </article>
        )}
      </section>

      <section className="card studio-home-section-card">
        <div className="ops-banner">
          <div>
            <div className="studio-section-kicker">样片广场</div>
            <h2 className="title-row" style={{ marginBottom: 6 }}><Icon name="gallery" size={18} />可复用的商业样片</h2>
            <p className="muted">这里只展示主动分享的样片，用来复拍、复剪和做运营封面。原始素材和项目仍保留在私有工作区。</p>
          </div>
          <button type="button" className="btn-secondary" onClick={() => navigate("/app/assets")}>查看我的素材库</button>
        </div>
        <div className="toolbar" style={{ marginTop: 10 }}>
          {SHOWCASE_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={cx("btn-secondary", activeShowcaseTab === tab.key && "active")}
              onClick={() => setActiveShowcaseTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {!featuredShowcaseCard ? (
          <div className="empty-state premium-empty" style={{ marginTop: 10 }}>
            <div className="title-row"><Icon name="gallery" size={16} />暂未生成样片</div>
            <p className="muted">先去任一工具创建并筛选结果，再在“选片分享”步骤推送到样片墙。</p>
            <div className="toolbar" style={{ marginTop: 8 }} data-cta-scope="tools-home.showcase-empty">
              <button type="button" className="btn-primary" onClick={() => navigate("/app/tools/product-image/tasks")}>去创建任务</button>
            </div>
          </div>
        ) : (
          <div className="showcase-stage" style={{ marginTop: 10 }}>
            <article className="featured-showcase">
              <div className="featured-showcase-media">
                {featuredShowcaseCard.imageUrl ? (
                  <img
                    src={featuredShowcaseCard.imageUrl}
                    alt={featuredShowcaseCard.title}
                    onError={(event) => applyImageFallback(event, featuredShowcaseCard.fallbackImageUrl)}
                  />
                ) : (
                  <div className="showcase-placeholder">
                    <span>{featuredShowcaseCard.badge}</span>
                    <strong>{featuredShowcaseCard.title}</strong>
                  </div>
                )}
              </div>
              <div className="featured-showcase-meta">
                <span className="badge">{featuredShowcaseCard.badge}</span>
                <h3>{featuredShowcaseCard.title}</h3>
                <p className="muted">{featuredShowcaseCard.subtitle}</p>
                <div className="muted">{featuredShowcaseCard.packageTier} · {featuredShowcaseCard.packagePrice}</div>
                <div className="toolbar" style={{ marginTop: 10 }}>
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={Boolean(featuredShowcaseCard.assetId) && remixingAssetId === featuredShowcaseCard.assetId}
                    onClick={() => remixFromShowcase(featuredShowcaseCard)}
                  >
                    {Boolean(featuredShowcaseCard.assetId) && remixingAssetId === featuredShowcaseCard.assetId ? "创建中..." : "立即拍同款"}
                  </button>
                  {featuredShowcaseCard.projectId && (
                    <button type="button" className="btn-secondary" onClick={() => navigate(`/app/tools/${featuredShowcaseCard.tool.slug}/projects/${featuredShowcaseCard.projectId}`)}>查看案例</button>
                  )}
                </div>
              </div>
            </article>
            <div className="showcase-grid showcase-grid-secondary">
              {secondaryShowcaseCards.map((item) => (
                <article key={item.caseId} className="showcase-card">
                  {item.imageUrl ? (
                    <img
                      src={item.imageUrl}
                      alt={item.title}
                      onError={(event) => applyImageFallback(event, item.fallbackImageUrl)}
                    />
                  ) : (
                    <div className="showcase-placeholder">
                      <span>{item.badge}</span>
                      <strong>{item.title}</strong>
                    </div>
                  )}
                  <div className="showcase-meta">
                    <div>
                      <div><strong>{item.title}</strong></div>
                      <div className="muted">{item.subtitle}</div>
                    </div>
                    <div className="toolbar">
                      <button
                        type="button"
                        className="btn-secondary"
                        disabled={Boolean(item.assetId) && remixingAssetId === item.assetId}
                        onClick={() => remixFromShowcase(item)}
                      >
                        {Boolean(item.assetId) && remixingAssetId === item.assetId ? "创建中..." : "拍同款"}
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="card studio-home-section-card">
        <div className="studio-section-head">
          <div>
            <div className="studio-section-kicker">图片工具</div>
            <h2 className="title-row"><Icon name="gallery" size={18} />先产出图片，再进入筛选与交付</h2>
          </div>
        </div>
        <div className="tool-grid studio-tool-grid">
          {imageTools.map((tool) => (
            <article key={tool.slug} className="tool-card tool-card-featured studio-tool-card">
              <div className="tool-card-kicker">图片工作流</div>
              <h3 className="title-row"><Icon name={toolIconName(tool)} size={16} />{tool.title}</h3>
              <p className="muted">{tool.subtitle}</p>
              <div className="tool-card-meta">
                <span className="badge">{tool.steps.length} 步流程</span>
                <span className="badge">先生成后确认</span>
              </div>
              <div className="studio-tool-steps">
                {tool.steps.map((step, idx) => (
                  <span key={step} className="studio-tool-step">{idx + 1}. {step}</span>
                ))}
              </div>
              <button type="button" className="btn-primary" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>进入任务中心</button>
            </article>
          ))}
        </div>
      </section>

      <section className="card studio-home-section-card">
        <div className="studio-section-head">
          <div>
            <div className="studio-section-kicker">视频工具</div>
            <h2 className="title-row"><Icon name="video" size={18} />讲解视频和转化短片共用一套视频编排</h2>
          </div>
        </div>
        <div className="tool-grid studio-tool-grid">
          {videoTools.map((tool) => (
            <article key={tool.slug} className="tool-card tool-card-featured studio-tool-card">
              <div className="tool-card-kicker">视频工作流</div>
              <h3 className="title-row"><Icon name={toolIconName(tool)} size={16} />{tool.title}</h3>
              <p className="muted">{tool.subtitle}</p>
              <div className="tool-card-meta">
                <span className="badge">{tool.steps.length} 步流程</span>
                <span className="badge">脚本与分镜前置</span>
              </div>
              <div className="studio-tool-steps">
                {tool.steps.map((step, idx) => (
                  <span key={step} className="studio-tool-step">{idx + 1}. {step}</span>
                ))}
              </div>
              <button type="button" className="btn-primary" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>进入任务中心</button>
            </article>
          ))}
        </div>
      </section>

      <section className="card studio-home-section-card">
        <h2 className="title-row"><Icon name="cube" size={18} />套图商品包（可运营）</h2>
        <div className="package-stage">
          <div className="package-strip">
            {visiblePackages.filter((pack) => !HIDDEN_WEB_TOOL_SLUGS.has(TOOLS[pack.toolSlug]?.slug || "")).map((pack) => (
              <article key={pack.packId} className="tool-card package-card">
                <h3 className="title-row"><Icon name="spark" size={16} />{pack.title}</h3>
                <p className="muted">{pack.includes}</p>
                <div className="toolbar" style={{ marginTop: 8 }}>
                  <span className="badge">{pack.pricing}</span>
                  <span className="badge">{pack.delivery}</span>
                </div>
                <div className="toolbar" style={{ marginTop: 10 }}>
                  <button type="button" className="btn-primary" onClick={() => navigate(`/app/tools/${TOOLS[pack.toolSlug].slug}/tasks`)}>立即开单</button>
                  <button type="button" className="btn-secondary" onClick={() => navigate("/app/assets")}>二次编辑</button>
                </div>
              </article>
            ))}
          </div>
          <aside className="hot-sales-panel">
            <h3 className="title-row"><Icon name="task" size={16} />近期热销</h3>
            <div className="hot-sales-list">
              {HOT_SELLING_TRACKS.filter((item) => !HIDDEN_WEB_TOOL_SLUGS.has(item.ctaTool)).map((item, idx) => (
                <article key={item.id} className="hot-sales-item">
                  <div className="title-row">
                    <span className="badge">TOP {idx + 1}</span>
                    <strong>{item.title}</strong>
                  </div>
                  <div className="muted">{item.reason}</div>
                  <div className="toolbar" style={{ marginTop: 8 }}>
                    <button type="button" className="btn-secondary" onClick={() => navigate(`/app/tools/${item.ctaTool}/tasks`)}>
                      查看工坊
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </aside>
        </div>
        {SALES_PACKAGES.length > visiblePackages.length ? (
          <div className="toolbar" style={{ marginTop: 10, justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => navigate("/app/tools/product-image/tasks")}>查看更多套餐</button>
          </div>
        ) : null}
      </section>

      <section className="card studio-home-section-card">
        <div className="ops-banner" style={{ marginBottom: 8 }}>
          <div>
            <div className="studio-section-kicker">任务流</div>
            <h2 className="title-row" style={{ marginBottom: 6 }}><Icon name="task" size={18} />最近的任务推进</h2>
            <p className="muted">仅显示最近 5 条任务，聚焦当前最需要跟进的项目。</p>
          </div>
          <span className="badge">共 {tasks.length} 条</span>
        </div>
        {!tasks.length ? (
          <div className="empty-state premium-empty">
            <div className="title-row"><Icon name="task" size={16} />暂无任务</div>
            <p className="muted">从左侧选择任一工坊创建任务，系统会把进度实时同步到看板。</p>
            <div className="toolbar" style={{ marginTop: 8 }} data-cta-scope="tools-home.tasks-empty">
              <button type="button" className="btn-primary" onClick={() => navigate("/app/tools/product-image/tasks")}>创建首个任务</button>
              <button type="button" className="btn-secondary" onClick={() => navigate("/app/tools/intro-video/tasks")}>去视频工坊</button>
            </div>
          </div>
        ) : (
          <div className="asset-task-grid home-ops-grid">
            {visibleTasks.map((task) => {
              const tool = TOOL_BY_TYPE[task.tool_type];
              const taskPath = resolveTaskWorkspacePath(task, TOOL_BY_TYPE);
              const risk = resolveTaskRisk(task);
              return (
                <article key={task.project_id} className="asset-task-card home-ops-card">
                  <div className="asset-task-cover asset-task-cover-fallback">
                    <Icon name={toolIconName(tool)} size={22} />
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
                      <div className="asset-task-progress-bar" style={{ width: `${Math.max(0, Math.min(Number(task.progress_percent || 0), 100))}%` }} />
                    </div>
                    <div className="asset-task-meta-row">
                      <span className="badge">{formatProgressLabel(task.progress_label)}</span>
                      <span className="muted">{formatDate(task.updated_at)}</span>
                    </div>
                    <div className="asset-task-next">
                      <span>下一步</span>
                      <strong>{taskNextActionHint(task)}</strong>
                    </div>
                    <div className="toolbar asset-task-actions" style={{ marginTop: 8 }}>
                      <button type="button" className="btn-secondary" onClick={() => navigate(taskPath)}>打开任务</button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
        {tasks.length > visibleTasks.length ? (
          <div className="toolbar" style={{ marginTop: 10, justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => navigate("/app/tools/product-image/tasks")}>查看完整任务中心</button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
