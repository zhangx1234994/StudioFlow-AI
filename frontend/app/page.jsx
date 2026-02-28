"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const TOOLS = {
  "intro-video": {
    slug: "intro-video",
    toolType: "intro_video_multi_script",
    scenarioType: "product_video",
    title: "转化讲解视频工坊",
    subtitle: "AI先生成3套脚本，确认后再分镜与视频候选。",
    category: "video",
    steps: ["需求与素材", "AI方案与提示词", "视频生成", "人工确认"],
  },
  "product-image": {
    slug: "product-image",
    toolType: "product_image_suite",
    scenarioType: "product_image_suite",
    title: "商品棚拍出图工坊",
    subtitle: "AI规划主图/场景/细节并批量生成。",
    category: "image",
    steps: ["需求与素材", "AI方案与提示词", "批量生图", "人工确认"],
  },
  "model-retouch": {
    slug: "model-retouch",
    toolType: "model_retouch",
    scenarioType: "model_retouch",
    title: "模特人像精修工坊",
    subtitle: "组图按每张=1任务拆分，支持身份锚点。",
    category: "image",
    steps: ["需求与素材", "AI方案与提示词", "身份确认", "批量精修", "人工确认"],
  },
  "quick-video-15s": {
    slug: "quick-video-15s",
    toolType: "quick_video_15s",
    scenarioType: "product_video",
    title: "15秒场景短片工坊",
    subtitle: "AI规划15秒节奏并默认生成3个候选。",
    category: "video",
    steps: ["需求与素材", "AI方案与提示词", "一键生成候选", "人工确认"],
  },
  "multi-angle-camera": {
    slug: "multi-angle-camera",
    toolType: "multi_angle_camera",
    scenarioType: "multi_angle_camera",
    title: "多角度展品工坊",
    subtitle: "3D机位控制 + 实时预览，批量生成多角度图。",
    category: "image",
    steps: ["素材与目标", "机位控制", "批量生成", "人工确认"],
  },
};

const TOOL_LIST = Object.values(TOOLS);
const TOOL_BY_TYPE = Object.fromEntries(TOOL_LIST.map((tool) => [tool.toolType, tool]));
const SHOWCASE_TABS = [
  { key: "all", label: "全部样片" },
  { key: "main", label: "主图套图" },
  { key: "scene", label: "场景套图" },
  { key: "model", label: "模特精修" },
  { key: "angle", label: "多角度图" },
];

const STUDIO_SHOWCASE_CASES = [
  {
    caseId: "main-1",
    category: "main",
    title: "高点击主图四宫格",
    subtitle: "白底主图 / 功能拆解 / 细节特写 / 对比图",
    toolSlug: "product-image",
    badge: "主图",
    packageTier: "基础套图包",
    packagePrice: "¥199 / 套",
  },
  {
    caseId: "main-2",
    category: "main",
    title: "品牌感主图套图",
    subtitle: "统一色调与材质光泽，适配站内主图位",
    toolSlug: "product-image",
    badge: "主图",
    packageTier: "品牌套图包",
    packagePrice: "¥399 / 套",
  },
  {
    caseId: "scene-1",
    category: "scene",
    title: "生活场景种草组图",
    subtitle: "真实使用情境 + 人物动作 + 轻商业布光",
    toolSlug: "product-image",
    badge: "场景",
    packageTier: "场景套图包",
    packagePrice: "¥499 / 套",
  },
  {
    caseId: "scene-2",
    category: "scene",
    title: "电商详情页故事组图",
    subtitle: "痛点引入、解决方案、结果展示三段式",
    toolSlug: "product-image",
    badge: "场景",
    packageTier: "故事套图包",
    packagePrice: "¥699 / 套",
  },
  {
    caseId: "model-1",
    category: "model",
    title: "模特人像精修样片",
    subtitle: "动作自然、肤质统一、身份一致性锁定",
    toolSlug: "model-retouch",
    badge: "模特",
    packageTier: "人像精修包",
    packagePrice: "¥299 / 套",
  },
  {
    caseId: "angle-1",
    category: "angle",
    title: "8角度产品展示图",
    subtitle: "正侧后+俯仰视角，商品细节完整覆盖",
    toolSlug: "multi-angle-camera",
    badge: "角度",
    packageTier: "多角度包",
    packagePrice: "¥259 / 套",
  },
];

const SALES_PACKAGES = [
  {
    packId: "starter",
    title: "上新快拍包",
    pricing: "¥199 / SKU",
    delivery: "24小时交付",
    includes: "主图4 + 细节2 + 场景2",
    toolSlug: "product-image",
  },
  {
    packId: "growth",
    title: "增长场景包",
    pricing: "¥599 / SKU",
    delivery: "48小时交付",
    includes: "主图4 + 场景8 + 卖点对比4",
    toolSlug: "product-image",
  },
  {
    packId: "portrait",
    title: "模特精修包",
    pricing: "¥399 / 10张",
    delivery: "24小时交付",
    includes: "动作修正 + 面部精修 + 身份一致",
    toolSlug: "model-retouch",
  },
];

const STATUS_LABEL = {
  queued: "排队中",
  running: "执行中",
  reviewing: "待审核",
  done: "已完成",
  failed: "失败",
};

const STAGE_LABEL = {
  master_script: "主脚本",
  plan: "AI方案",
  prompt: "提示词编译",
  identity: "身份确认",
  storyboard: "分镜",
  generate: "素材生成",
  render: "视频生成",
  review: "人工确认",
  completed: "已完成",
  failed: "失败",
};

function cx(...items) {
  return items.filter(Boolean).join(" ");
}

function parseCsv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

async function apiFetch(url, options = {}) {
  const resp = await fetch(url, { credentials: "include", ...options });
  const payload = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(payload?.detail || payload?.msg || `请求失败 (${resp.status})`);
  return payload;
}

function formatDate(value) {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString();
}

function selectedFileSummary(files) {
  if (!files?.length) return "未选择文件";
  if (files.length === 1) return files[0];
  return `${files[0]} 等 ${files.length} 个文件`;
}

function localPathToMedia(path) {
  if (!path) return "";
  const normalized = String(path).replaceAll("\\", "/");
  if (normalized.startsWith("data/")) return `/media/${normalized.slice(5)}`;
  const idx = normalized.indexOf("/data/");
  if (idx >= 0) return `/media/${normalized.slice(idx + 6)}`;
  return "";
}

function parseRoute(pathname) {
  const normalized = (pathname.startsWith("/app") ? pathname.slice(4) : pathname).replace(/\/+$/, "") || "/";
  const parts = normalized.split("/").filter(Boolean);
  if (!parts.length) return { page: "tools" };
  if (parts[0] === "login") return { page: "login" };
  if (parts[0] === "assets") return { page: "assets" };
  if (parts[0] === "tools" && parts.length === 1) return { page: "tools" };
  if (parts[0] === "tools" && parts.length === 3 && parts[2] === "tasks") {
    return { page: "tasks", toolSlug: parts[1] };
  }
  if (parts[0] === "tools" && parts.length >= 4 && parts[2] === "projects") {
    return { page: "project", toolSlug: parts[1], projectId: decodeURIComponent(parts[3]) };
  }
  return { page: "tools" };
}

function breadcrumbs(route, projectName = "") {
  if (route.page === "login") return ["登录"];
  if (route.page === "tools") return ["首页", "工具箱"];
  if (route.page === "assets") return ["首页", "我的素材库"];
  const tool = TOOLS[route.toolSlug];
  if (route.page === "tasks") return ["首页", tool?.title || "工具", "任务中心"];
  if (route.page === "project") {
    return ["首页", tool?.title || "工具", "任务中心", projectName || route.projectId || "项目"];
  }
  return ["首页"];
}

function useRouterState() {
  const [pathname, setPathname] = useState(() => {
    if (typeof window === "undefined") return "/app/login";
    return window.location.pathname || "/app/login";
  });

  useEffect(() => {
    setPathname(window.location.pathname);
    const onPop = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((target) => {
    const url = target.startsWith("/app") ? target : `/app${target.startsWith("/") ? target : `/${target}`}`;
    window.history.pushState({}, "", url);
    setPathname(url);
  }, []);

  return { pathname, route: parseRoute(pathname), navigate };
}

function LoginPage({ navigate }) {
  const [status, setStatus] = useState({ text: "请输入账号密码", type: "" });
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setLoading(true);
    setStatus({ text: "登录中...", type: "" });
    try {
      await apiFetch("/api/v1/auth/login", { method: "POST", body: formData });
      setStatus({ text: "登录成功，正在跳转...", type: "success" });
      navigate("/app/tools");
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-main" style={{ maxWidth: 520, paddingTop: 80 }}>
      <section className="card">
        <h1>登录 AI摄影棚</h1>
        <p className="card-subtitle">默认账号：admin / admin123</p>
        <form className="grid" onSubmit={submit}>
          <div className="field"><label>用户名</label><input name="username" defaultValue="admin" required /></div>
          <div className="field"><label>密码</label><input name="password" type="password" defaultValue="admin123" required /></div>
          <button type="submit" className="btn-primary" disabled={loading}>{loading ? "登录中..." : "登录"}</button>
        </form>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
      </section>
    </div>
  );
}

function TopBar({ route, auth, navigate, onLogout }) {
  const [keyword, setKeyword] = useState("");

  const jump = async () => {
    if (!keyword.trim()) return;
    try {
      const rows = await apiFetch(`/api/v1/projects?limit=1&query=${encodeURIComponent(keyword.trim())}`);
      if (!rows.length) return;
      const tool = TOOL_BY_TYPE[rows[0].tool_type];
      if (!tool) return;
      navigate(`/app/tools/${tool.slug}/projects/${rows[0].project_id}`);
      setKeyword("");
    } catch (_) {
      // no-op
    }
  };

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <a className="brand" href="/app/tools" onClick={(event) => { event.preventDefault(); navigate("/app/tools"); }}>AI摄影棚</a>
        <nav className="nav-links">
          <a className={cx("nav-link", ["tools", "tasks", "project"].includes(route.page) && "active")} href="/app/tools" onClick={(event) => { event.preventDefault(); navigate("/app/tools"); }}>工具箱</a>
          <a className={cx("nav-link", route.page === "assets" && "active")} href="/app/assets" onClick={(event) => { event.preventDefault(); navigate("/app/assets"); }}>我的素材库</a>
        </nav>
        <div className="topbar-right">
          <input className="quick-jump" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索项目ID/名称" onKeyDown={(event) => event.key === "Enter" && jump()} />
          <button type="button" className="btn-secondary" onClick={jump}>跳转</button>
          <span className="muted">{auth.username ? `当前用户：${auth.username}` : "已登录"}</span>
          <button type="button" className="btn-ghost" onClick={() => navigate("/app/tools")}>返回首页</button>
          <button type="button" className="btn-ghost" onClick={onLogout}>退出</button>
        </div>
      </div>
    </header>
  );
}

function AppSidebar({ route, navigate }) {
  const activeTool = route.toolSlug || "";
  return (
    <aside className="app-sidebar">
      <div className="sidebar-card">
        <h3>工具箱</h3>
        <div className="sidebar-links">
          <button
            type="button"
            className={cx("sidebar-link", route.page === "tools" && "active")}
            onClick={() => navigate("/app/tools")}
          >
            总览首页
          </button>
          <button
            type="button"
            className={cx("sidebar-link", route.page === "assets" && "active")}
            onClick={() => navigate("/app/assets")}
          >
            我的素材库
          </button>
        </div>
      </div>

      <div className="sidebar-card">
        <h4>图片工具</h4>
        <div className="sidebar-links">
          {TOOL_LIST.filter((item) => item.category === "image").map((item) => (
            <button
              key={item.slug}
              type="button"
              className={cx("sidebar-link", activeTool === item.slug && "active")}
              onClick={() => navigate(`/app/tools/${item.slug}/tasks`)}
            >
              {item.title}
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar-card">
        <h4>视频工具</h4>
        <div className="sidebar-links">
          {TOOL_LIST.filter((item) => item.category === "video").map((item) => (
            <button
              key={item.slug}
              type="button"
              className={cx("sidebar-link", activeTool === item.slug && "active")}
              onClick={() => navigate(`/app/tools/${item.slug}/tasks`)}
            >
              {item.title}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}

function ToolsHome({ navigate }) {
  const [kpi, setKpi] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [showcaseAssets, setShowcaseAssets] = useState([]);
  const [activeShowcaseTab, setActiveShowcaseTab] = useState("all");
  const [status, setStatus] = useState({ text: "加载中...", type: "" });

  const load = useCallback(async () => {
    setStatus({ text: "加载看板数据...", type: "" });
    try {
      const [kpiRes, tasksRes] = await Promise.all([
        apiFetch("/api/v1/tools/kpi"),
        apiFetch("/api/v1/projects?limit=8"),
      ]);
      const assetsRes = await apiFetch("/api/v1/assets?source_type=generated&limit=48");
      setKpi(kpiRes);
      setTasks(tasksRes);
      setShowcaseAssets(assetsRes.filter((item) => item.kind === "image"));
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

    return STUDIO_SHOWCASE_CASES.map((preset, idx) => {
      const tool = TOOLS[preset.toolSlug];
      const pool = grouped[tool.toolType] || [];
      const asset = pool.length ? pool[idx % pool.length] : null;
      return {
        ...preset,
        tool,
        imageUrl: asset ? asset.image_url || localPathToMedia(asset.local_path) : "",
        projectId: asset?.project_id || "",
      };
    });
  }, [showcaseAssets]);

  const filteredShowcaseCards = useMemo(() => {
    if (activeShowcaseTab === "all") return showcaseCards;
    return showcaseCards.filter((item) => item.category === activeShowcaseTab);
  }, [showcaseCards, activeShowcaseTab]);

  return (
    <div className="content-stack">
      <section className="card">
        <div className="hero-banner">
          <div>
            <h1>AI摄影棚</h1>
            <p className="card-subtitle">电商公司的在线摄影棚：先选样片，再拍同款，再做精修与批量复用。</p>
            <div className="toolbar" style={{ marginTop: 10 }}>
              <button type="button" className="btn-primary" onClick={() => navigate("/app/tools/product-image/tasks")}>立即开拍</button>
              <button type="button" className="btn-secondary" onClick={() => navigate("/app/tools/intro-video/tasks")}>制作视频</button>
            </div>
          </div>
          <div className="hero-tags">
            <span className="badge">摄影棚样片墙</span>
            <span className="badge">可复用模板</span>
            <span className="badge">批量出图出片</span>
          </div>
        </div>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        <div className="kpi-grid" style={{ marginTop: 10 }}>
          {[
            ["项目总数", kpi?.total_projects ?? 0],
            ["进行中", kpi?.running_projects ?? 0],
            ["已完成", kpi?.done_projects ?? 0],
            ["失败", kpi?.failed_projects ?? 0],
            ["素材总数", kpi?.total_assets ?? 0],
            ["上传素材", kpi?.uploaded_assets ?? 0],
            ["生成素材", kpi?.generated_assets ?? 0],
          ].map(([label, value]) => (
            <div key={label} className="kpi-item"><div className="label">{label}</div><div className="value">{value}</div></div>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="ops-banner">
          <div>
            <h2 style={{ marginBottom: 6 }}>摄影棚样片墙</h2>
            <p className="muted">公开展示风格样片，用户可直接“拍同款”。你的原始素材与项目仍在“我的素材库”私有保存。</p>
          </div>
          <button type="button" className="btn-secondary" onClick={() => navigate("/app/assets")}>查看我的素材库</button>
        </div>
        <div className="toolbar" style={{ marginTop: 10 }}>
          {SHOWCASE_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={cx(activeShowcaseTab === tab.key ? "btn-primary" : "btn-secondary")}
              onClick={() => setActiveShowcaseTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="showcase-grid" style={{ marginTop: 10 }}>
          {filteredShowcaseCards.map((item) => (
            <article key={item.caseId} className="showcase-card">
              {item.imageUrl ? (
                <img src={item.imageUrl} alt={item.title} />
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
                  <div className="muted">{item.packageTier} · {item.packagePrice}</div>
                </div>
                <div className="toolbar">
                  <button type="button" className="btn-primary" onClick={() => navigate(`/app/tools/${item.tool.slug}/tasks`)}>拍同款</button>
                  {item.projectId && (
                    <button type="button" className="btn-secondary" onClick={() => navigate(`/app/tools/${item.tool.slug}/projects/${item.projectId}`)}>看案例</button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>图片类工具</h2>
        <div className="tool-grid">
          {TOOL_LIST.filter((tool) => tool.category === "image").map((tool) => (
            <article key={tool.slug} className="tool-card">
              <h3>{tool.title}</h3>
              <p className="muted">{tool.subtitle}</p>
              <button type="button" className="btn-primary" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>进入任务中心</button>
            </article>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>视频类工具</h2>
        <div className="tool-grid">
          {TOOL_LIST.filter((tool) => tool.category === "video").map((tool) => (
            <article key={tool.slug} className="tool-card">
              <h3>{tool.title}</h3>
              <p className="muted">{tool.subtitle}</p>
              <button type="button" className="btn-primary" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>进入任务中心</button>
            </article>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>套图商品包（可运营）</h2>
        <div className="tool-grid">
          {SALES_PACKAGES.map((pack) => (
            <article key={pack.packId} className="tool-card">
              <h3>{pack.title}</h3>
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
      </section>

      <section className="card">
        <h2>我的任务看板</h2>
        {!tasks.length ? (
          <div className="empty-state">暂无任务</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>任务</th><th>工具</th><th>阶段</th><th>进度</th><th>状态</th><th>更新时间</th><th>操作</th></tr></thead>
              <tbody>
                {tasks.map((task) => {
                  const tool = TOOL_BY_TYPE[task.tool_type];
                  return (
                    <tr key={task.project_id}>
                      <td>{task.product_name}</td>
                      <td>{tool?.title || task.tool_type}</td>
                      <td>{STAGE_LABEL[task.current_stage] || task.current_stage}</td>
                      <td>{task.progress_percent}%<div className="muted">{task.progress_label || "-"}</div></td>
                      <td><span className="badge">{STATUS_LABEL[task.status] || task.status}</span></td>
                      <td>{formatDate(task.updated_at)}</td>
                      <td><button type="button" className="btn-secondary" onClick={() => navigate(`/app/tools/${tool?.slug || "intro-video"}/projects/${task.project_id}`)}>打开</button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function AssetsPage({ navigate }) {
  const [assets, setAssets] = useState([]);
  const [status, setStatus] = useState({ text: "准备查询", type: "" });
  const formRef = useRef(null);

  const queryAssets = useCallback(async () => {
    const fd = new FormData(formRef.current);
    const params = new URLSearchParams();
    ["source_type", "tool_type", "project_id", "tag", "keyword", "limit"].forEach((key) => {
      const value = String(fd.get(key) || "").trim();
      if (value) params.set(key, value);
    });
    if (!params.get("limit")) params.set("limit", "100");
    setStatus({ text: "查询中...", type: "" });
    try {
      const rows = await apiFetch(`/api/v1/assets?${params.toString()}`);
      setAssets(rows);
      setStatus({ text: `共 ${rows.length} 条素材`, type: "success" });
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    }
  }, []);

  useEffect(() => { queryAssets(); }, [queryAssets]);

  return (
    <div className="content-stack">
      <section className="card">
        <h1>我的素材库</h1>
        <p className="card-subtitle">仅你可见：上传与生成素材统一检索，支持跨工具复用。</p>
        <form ref={formRef} className="grid">
          <div className="field"><label>来源</label><select name="source_type" defaultValue=""><option value="">全部</option><option value="uploaded">uploaded</option><option value="generated">generated</option></select></div>
          <div className="field"><label>工具</label><select name="tool_type" defaultValue=""><option value="">全部</option>{TOOL_LIST.map((tool) => <option key={tool.toolType} value={tool.toolType}>{tool.title}</option>)}</select></div>
          <div className="field"><label>项目ID</label><input name="project_id" /></div>
          <div className="field"><label>标签</label><input name="tag" /></div>
          <div className="field"><label>关键词</label><input name="keyword" /></div>
          <div className="field"><label>数量</label><input name="limit" type="number" defaultValue="100" min="1" max="1000" /></div>
        </form>
        <div className="toolbar" style={{ marginTop: 10 }}>
          <button type="button" className="btn-primary" onClick={queryAssets}>查询</button>
          <button type="button" className="btn-secondary" onClick={() => navigate("/app/tools")}>返回工具箱</button>
        </div>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
      </section>

      <section className="card">
        <h2>素材列表</h2>
        {!assets.length ? (
          <div className="empty-state">暂无素材</div>
        ) : (
          <div className="asset-grid">
            {assets.map((asset) => {
              const imageUrl = asset.image_url || localPathToMedia(asset.local_path);
              const videoUrl = asset.video_url || localPathToMedia(asset.local_path);
              const tool = TOOL_BY_TYPE[asset.tool_type];
              return (
                <article key={asset.asset_id} className="asset-card">
                  {imageUrl ? <img src={imageUrl} alt="asset" /> : videoUrl ? <video src={videoUrl} controls preload="metadata" /> : <div className="empty-state">无预览</div>}
                  <div className="toolbar" style={{ marginTop: 8 }}><span className="badge">{asset.source_type}</span><span className="badge">{asset.kind}</span></div>
                  <div className="muted" style={{ marginTop: 4 }}>项目：{asset.project_id}</div>
                  <div className="muted">状态：{asset.status}</div>
                  {tool && <button type="button" className="btn-secondary" style={{ marginTop: 8 }} onClick={() => navigate(`/app/tools/${tool.slug}/projects/${asset.project_id}`)}>打开项目</button>}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function MultiAnglePad({ values, setValues, previewSrc }) {
  const mountRef = useRef(null);
  const runtimeRef = useRef(null);

  const toYaw360 = (yaw) => {
    const raw = Number(yaw || 0);
    const normalized = ((raw % 360) + 360) % 360;
    return Math.round(normalized);
  };
  const toDistanceFactor = (distanceLabel) => {
    if (distanceLabel === "near") return 0.6;
    if (distanceLabel === "far") return 1.4;
    return 1.0;
  };
  const toDistanceLabel = (factor) => {
    if (factor <= 0.8) return "near";
    if (factor >= 1.2) return "far";
    return "medium";
  };
  const updateParent = useCallback((next) => {
    setValues((prev) => {
      const yaw360 = toYaw360(next.yaw360 ?? toYaw360(prev.camera_yaw));
      const signedYaw = yaw360 > 180 ? yaw360 - 360 : yaw360;
      const pitch = Math.max(-30, Math.min(60, Math.round(next.pitch ?? prev.camera_pitch ?? 0)));
      const distanceFactor = Math.max(0.6, Math.min(1.4, Number(next.distanceFactor ?? toDistanceFactor(prev.camera_distance))));
      return {
        ...prev,
        camera_yaw: signedYaw,
        camera_pitch: pitch,
        camera_distance: toDistanceLabel(distanceFactor),
      };
    });
  }, [setValues]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x12151f);
    const camera = new THREE.PerspectiveCamera(50, mount.clientWidth / mount.clientHeight, 0.1, 100);
    camera.position.set(4.8, 3.2, 4.8);
    camera.lookAt(0, 0.8, 0);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    mount.innerHTML = "";
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dir = new THREE.DirectionalLight(0xffffff, 0.6);
    dir.position.set(3, 6, 2);
    scene.add(dir);
    scene.add(new THREE.GridHelper(10, 20, 0x2b3244, 0x1f2431));

    const center = new THREE.Vector3(0, 0.8, 0);
    const AZ = 2.35;
    const EL = 1.8;

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(AZ, 0.04, 16, 96),
      new THREE.MeshStandardMaterial({ color: 0x20ffc0, emissive: 0x20ffc0, emissiveIntensity: 0.35 })
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.06;
    scene.add(ring);

    const arcPoints = [];
    for (let i = 0; i <= 40; i += 1) {
      const angle = THREE.MathUtils.degToRad(-30 + (90 * i) / 40);
      arcPoints.push(new THREE.Vector3(-0.8, EL * Math.sin(angle) + center.y, EL * Math.cos(angle)));
    }
    const arc = new THREE.Mesh(
      new THREE.TubeGeometry(new THREE.CatmullRomCurve3(arcPoints), 40, 0.04, 8, false),
      new THREE.MeshStandardMaterial({ color: 0xff79cc, emissive: 0xff79cc, emissiveIntensity: 0.35 })
    );
    scene.add(arc);

    const distRail = new THREE.Mesh(
      new THREE.CylinderGeometry(0.03, 0.03, 2.2, 12),
      new THREE.MeshStandardMaterial({ color: 0xffc857, emissive: 0xffc857, emissiveIntensity: 0.25 })
    );
    distRail.rotation.z = Math.PI / 2;
    distRail.position.set(-2.15, center.y, 0);
    scene.add(distRail);

    const mkHandle = (color, type) => {
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(0.17, 18, 18),
        new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.45 })
      );
      mesh.userData.type = type;
      return mesh;
    };
    const azHandle = mkHandle(0x20ffc0, "azimuth");
    const elHandle = mkHandle(0xff79cc, "elevation");
    const distHandle = mkHandle(0xffc857, "distance");
    scene.add(azHandle, elHandle, distHandle);

    const targetPlaneMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide });
    const targetPlane = new THREE.Mesh(new THREE.PlaneGeometry(1.35, 1.35), targetPlaneMaterial);
    targetPlane.position.copy(center);
    scene.add(targetPlane);

    const cameraModel = new THREE.Group();
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x5f90ff, metalness: 0.45, roughness: 0.35 });
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.2, 0.38), bodyMat);
    const lens = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 0.2, 16), bodyMat);
    lens.rotation.x = Math.PI / 2;
    lens.position.z = 0.27;
    cameraModel.add(body, lens);
    scene.add(cameraModel);

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let dragType = null;

    const syncObjects = (state) => {
      const yawDeg = state.yaw360;
      const pitchDeg = state.pitch;
      const dist = state.distanceFactor;
      const yaw = THREE.MathUtils.degToRad(yawDeg);
      const pitch = THREE.MathUtils.degToRad(pitchDeg);

      azHandle.position.set(Math.sin(yaw) * AZ, 0.06, Math.cos(yaw) * AZ);
      elHandle.position.set(-0.8, EL * Math.sin(pitch) + center.y, EL * Math.cos(pitch));
      distHandle.position.set(-2.15 + (dist - 1.0) * 2.2, center.y, 0);

      const r = 1.8 * dist;
      cameraModel.position.set(Math.sin(yaw) * r, center.y + Math.sin(pitch) * 1.05, Math.cos(yaw) * r);
      cameraModel.lookAt(center);
    };

    const state = {
      yaw360: toYaw360(values.camera_yaw),
      pitch: Math.max(-30, Math.min(60, Number(values.camera_pitch || 0))),
      distanceFactor: toDistanceFactor(values.camera_distance),
    };
    syncObjects(state);

    const onPointer = (event) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    };
    const onDown = (event) => {
      onPointer(event);
      raycaster.setFromCamera(mouse, camera);
      const hit = raycaster.intersectObjects([azHandle, elHandle, distHandle])[0];
      dragType = hit?.object?.userData?.type || null;
      renderer.domElement.style.cursor = dragType ? "grabbing" : "default";
    };
    const onMove = (event) => {
      if (!dragType) return;
      onPointer(event);
      raycaster.setFromCamera(mouse, camera);
      if (dragType === "azimuth") {
        const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.06);
        const hit = new THREE.Vector3();
        if (raycaster.ray.intersectPlane(plane, hit)) {
          let next = THREE.MathUtils.radToDeg(Math.atan2(hit.x, hit.z));
          if (next < 0) next += 360;
          state.yaw360 = Math.round(next);
        }
      } else if (dragType === "elevation") {
        const plane = new THREE.Plane(new THREE.Vector3(1, 0, 0), 0.8);
        const hit = new THREE.Vector3();
        if (raycaster.ray.intersectPlane(plane, hit)) {
          const relY = hit.y - center.y;
          const relZ = hit.z;
          state.pitch = Math.max(-30, Math.min(60, Math.round(THREE.MathUtils.radToDeg(Math.atan2(relY, relZ)))));
        }
      } else if (dragType === "distance") {
        state.distanceFactor = Math.max(0.6, Math.min(1.4, state.distanceFactor + event.movementX * 0.004));
      }
      syncObjects(state);
      updateParent(state);
    };
    const onUp = () => {
      dragType = null;
      renderer.domElement.style.cursor = "grab";
    };

    renderer.domElement.addEventListener("pointerdown", onDown);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    renderer.domElement.style.cursor = "grab";

    const handleResize = () => {
      if (!mountRef.current) return;
      camera.aspect = mountRef.current.clientWidth / mountRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    let raf = 0;
    const render = () => {
      renderer.render(scene, camera);
      raf = requestAnimationFrame(render);
    };
    render();

    runtimeRef.current = { state, syncObjects, targetPlaneMaterial };

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.dispose();
      mount.innerHTML = "";
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const rt = runtimeRef.current;
    if (!rt) return;
    const state = rt.state;
    state.yaw360 = toYaw360(values.camera_yaw);
    state.pitch = Math.max(-30, Math.min(60, Number(values.camera_pitch || 0)));
    state.distanceFactor = toDistanceFactor(values.camera_distance);
    rt.syncObjects(state);
  }, [values.camera_yaw, values.camera_pitch, values.camera_distance]);

  useEffect(() => {
    const rt = runtimeRef.current;
    if (!rt?.targetPlaneMaterial) return;
    if (!previewSrc) {
      rt.targetPlaneMaterial.map = null;
      rt.targetPlaneMaterial.needsUpdate = true;
      return;
    }
    new THREE.TextureLoader().load(previewSrc, (texture) => {
      texture.minFilter = THREE.LinearFilter;
      texture.magFilter = THREE.LinearFilter;
      rt.targetPlaneMaterial.map = texture;
      rt.targetPlaneMaterial.needsUpdate = true;
    });
  }, [previewSrc]);

  return (
    <div className="camera-pad-wrap">
      <div className="camera-viewport" ref={mountRef} />
      <div className="toolbar" style={{ marginTop: 8 }}>
        {[{ label: "正面", yaw: 0, pitch: 0 }, { label: "右侧45°", yaw: 45, pitch: 0 }, { label: "背面", yaw: 180, pitch: 0 }, { label: "低角度", yaw: toYaw360(values.camera_yaw), pitch: -30 }, { label: "高角度", yaw: toYaw360(values.camera_yaw), pitch: 60 }].map((item) => (
          <button key={item.label} type="button" className="btn-secondary" onClick={() => updateParent({ yaw360: item.yaw, pitch: item.pitch })}>{item.label}</button>
        ))}
      </div>
      <div className="grid" style={{ marginTop: 8 }}>
        <div className="field"><label>Azimuth (0~315)</label><input type="range" min={0} max={315} step={45} value={toYaw360(values.camera_yaw)} onChange={(event) => updateParent({ yaw360: Number(event.target.value || 0) })} /></div>
        <div className="field"><label>Elevation (-30~60)</label><input type="range" min={-30} max={60} step={30} value={Math.max(-30, Math.min(60, Number(values.camera_pitch || 0)))} onChange={(event) => updateParent({ pitch: Number(event.target.value || 0) })} /></div>
        <div className="field"><label>Distance</label><input type="range" min={0.6} max={1.4} step={0.1} value={toDistanceFactor(values.camera_distance)} onChange={(event) => updateParent({ distanceFactor: Number(event.target.value || 1) })} /></div>
        <div className="field"><label>Focal</label><select value={values.camera_focal_mm} onChange={(event) => setValues((prev) => ({ ...prev, camera_focal_mm: event.target.value }))}><option value="35">35mm</option><option value="50">50mm</option><option value="85">85mm</option></select></div>
      </div>
      <div className="status-banner" style={{ marginTop: 8 }}>
        Azimuth {toYaw360(values.camera_yaw)}° · Elevation {Math.max(-30, Math.min(60, Number(values.camera_pitch || 0)))}° · Distance {values.camera_distance} · {values.camera_focal_mm}mm
      </div>
    </div>
  );
}

function ToolTasksPage({ tool, navigate }) {
  const [templates, setTemplates] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState({ text: "准备中...", type: "" });
  const [createStatus, setCreateStatus] = useState({ text: "填写信息后创建。", type: "" });
  const [creating, setCreating] = useState(false);
  const [formValues, setFormValues] = useState({
    product_name: "",
    platform: tool.slug === "quick-video-15s" ? "tiktok" : "douyin",
    template_name: "general",
    desired_duration_sec: tool.slug === "quick-video-15s" ? 15 : 40,
    key_features: "核心卖点,真实反馈,使用场景",
    target_audience: "注重体验和性价比的人群",
    tone: "真实、克制、有钩子",
    evidence_points: "使用演示,连续反馈",
    channels: "douyin,tiktok",
    compliance_blocklist: "绝对最好,全网第一",
    scene_style: "商业棚拍+生活化场景",
    scene_goals: "主图精修,场景图,细节特写,对比图",
    retouch_targets: "动作自然,面部状态,肤质统一,服装褶皱,光线修正",
    fidelity_requirement: "保持身份一致，避免形变",
    creative_direction: "",
    identity_replace: true,
    camera_yaw: 0,
    camera_pitch: 0,
    camera_distance: "medium",
    camera_focal_mm: "50",
    camera_aspect_ratio: "1:1",
  });
  const [previewSrc, setPreviewSrc] = useState("");
  const [highlightBatch, setHighlightBatch] = useState("");
  const formRef = useRef(null);
  const [fileInputVersion, setFileInputVersion] = useState({
    image: 0,
    images: 0,
    reference_images: 0,
    style_reference_images: 0,
    identity_image: 0,
  });
  const [selectedFiles, setSelectedFiles] = useState({
    image: [],
    images: [],
    reference_images: [],
    style_reference_images: [],
    identity_image: [],
  });

  const onFileChange = useCallback((field, event) => {
    const names = Array.from(event.target.files || []).map((file) => file.name);
    setSelectedFiles((prev) => ({ ...prev, [field]: names }));
    if (field === "image") {
      if (event.target.files?.[0]) {
        setPreviewSrc(URL.createObjectURL(event.target.files[0]));
      } else {
        setPreviewSrc("");
      }
    }
  }, []);

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
      setTemplates(templatesRes);
      setTasks(tasksRes);
      if (templatesRes.length) {
        setFormValues((prev) => ({ ...prev, template_name: templatesRes[0].template_name }));
      }
      setStatus({ text: tasksRes.length ? `任务已加载（${tasksRes.length}）` : "暂无任务", type: "success" });
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    }
  }, [tool.toolType, query]);

  useEffect(() => { loadData(); }, [loadData]);

  const create = async (event) => {
    event.preventDefault();
    const fd = new FormData(formRef.current);
    setCreating(true);
    setCreateStatus({ text: "提交中...", type: "" });
    try {
      if (tool.slug === "model-retouch") {
        const result = await apiFetch("/api/v1/tools/model_retouch/batch-create", { method: "POST", body: fd });
        setHighlightBatch(result.batch_group_id || "");
        setCreateStatus({ text: `批量创建完成：${result.created_count}个任务`, type: "success" });
        await loadData();
        const firstProjectId = result.project_ids?.[0];
        if (firstProjectId) {
          navigate(`/app/tools/${tool.slug}/projects/${firstProjectId}`);
        }
      } else {
        fd.set("tool_type", tool.toolType);
        fd.set("scenario_type", tool.scenarioType);
        if (tool.slug === "quick-video-15s") fd.set("desired_duration_sec", "15");
        const result = await apiFetch("/api/v1/projects", { method: "POST", body: fd });
        const projectId = result?.project?.project_id;
        if (!projectId) throw new Error("创建成功但未返回项目ID");
        setCreateStatus({ text: `创建成功，进入项目 ${projectId}`, type: "success" });
        navigate(`/app/tools/${tool.slug}/projects/${projectId}`);
      }
    } catch (error) {
      setCreateStatus({ text: error.message, type: "error" });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="content-stack">
      <section className="card">
        <h1>{tool.title}</h1>
        <p className="card-subtitle">{tool.subtitle}</p>
        <form ref={formRef} className="grid" onSubmit={create}>
          <div className="field"><label>{tool.slug === "model-retouch" ? "批次名" : "产品名"} *</label><input name="product_name" required value={formValues.product_name} onChange={(event) => setFormValues((prev) => ({ ...prev, product_name: event.target.value }))} /></div>
          {tool.slug === "model-retouch" ? (
            <>
              <div className="field">
                <label>A. 主素材组图（必填）*</label>
                <input
                  key={`images-${fileInputVersion.images}`}
                  name="images"
                  type="file"
                  accept="image/*"
                  multiple
                  required
                  onChange={(event) => onFileChange("images", event)}
                />
                <div className="toolbar">
                  <span className="muted">{selectedFileSummary(selectedFiles.images)}</span>
                  {selectedFiles.images.length > 0 && <button type="button" className="btn-ghost" onClick={() => clearFiles("images")}>撤回已选</button>}
                </div>
              </div>
              <div className="field">
                <label>B. 风格参考图</label>
                <input
                  key={`style-reference-images-${fileInputVersion.style_reference_images}`}
                  name="style_reference_images"
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(event) => onFileChange("style_reference_images", event)}
                />
                <div className="toolbar">
                  <span className="muted">{selectedFileSummary(selectedFiles.style_reference_images)}</span>
                  {selectedFiles.style_reference_images.length > 0 && <button type="button" className="btn-ghost" onClick={() => clearFiles("style_reference_images")}>撤回已选</button>}
                </div>
              </div>
              <div className="field">
                <label>C. 替换模特源图</label>
                <input
                  key={`identity-image-${fileInputVersion.identity_image}`}
                  name="identity_image"
                  type="file"
                  accept="image/*"
                  onChange={(event) => onFileChange("identity_image", event)}
                />
                <div className="toolbar">
                  <span className="muted">{selectedFileSummary(selectedFiles.identity_image)}</span>
                  {selectedFiles.identity_image.length > 0 && <button type="button" className="btn-ghost" onClick={() => clearFiles("identity_image")}>撤回已选</button>}
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="field">
                <label>主图 *</label>
                <input
                  key={`image-${fileInputVersion.image}`}
                  name="image"
                  type="file"
                  accept="image/*"
                  required
                  onChange={(event) => onFileChange("image", event)}
                />
                <div className="toolbar">
                  <span className="muted">{selectedFileSummary(selectedFiles.image)}</span>
                  {selectedFiles.image.length > 0 && <button type="button" className="btn-ghost" onClick={() => clearFiles("image")}>撤回已选</button>}
                </div>
              </div>
              {tool.slug === "product-image" && (
                <div className="field">
                  <label>风格参考图（可多选）</label>
                  <input
                    key={`${tool.slug}-reference-${fileInputVersion.reference_images}`}
                    name="reference_images"
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={(event) => onFileChange("reference_images", event)}
                  />
                  <div className="toolbar">
                    <span className="muted">
                      {selectedFileSummary(selectedFiles.reference_images)}
                    </span>
                    {selectedFiles.reference_images.length > 0 && (
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={() => clearFiles("reference_images")}
                      >
                        撤回已选
                      </button>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
          <div className="field"><label>模板</label><select name="template_name" value={formValues.template_name} onChange={(event) => setFormValues((prev) => ({ ...prev, template_name: event.target.value }))}>{templates.map((item) => <option key={item.template_name} value={item.template_name}>{item.display_name}</option>)}</select></div>
          {tool.slug !== "multi-angle-camera" ? (
            <div className="field"><label>平台</label><input name="platform" value={formValues.platform} onChange={(event) => setFormValues((prev) => ({ ...prev, platform: event.target.value }))} /></div>
          ) : (
            <input name="platform" type="hidden" value={formValues.platform} readOnly />
          )}

          {tool.slug === "intro-video" && (
            <div className="field"><label>时长（秒）</label><input name="desired_duration_sec" type="number" min={15} max={50} value={formValues.desired_duration_sec} onChange={(event) => setFormValues((prev) => ({ ...prev, desired_duration_sec: Number(event.target.value || 15) }))} /></div>
          )}

          {tool.slug === "quick-video-15s" && (
            <div className="field"><label>时长（秒）</label><input value="15（固定）" disabled readOnly /></div>
          )}

          {tool.slug === "product-image" && (
            <>
              <div className="field"><label>场景风格</label><input name="scene_style" value={formValues.scene_style} onChange={(event) => setFormValues((prev) => ({ ...prev, scene_style: event.target.value }))} /></div>
              <div className="field"><label>出图目标（逗号）</label><input name="scene_goals" value={formValues.scene_goals} onChange={(event) => setFormValues((prev) => ({ ...prev, scene_goals: event.target.value }))} /></div>
            </>
          )}

          {tool.slug === "model-retouch" && (
            <>
              <div className="field"><label>精修目标（逗号）</label><input name="retouch_targets" value={formValues.retouch_targets} onChange={(event) => setFormValues((prev) => ({ ...prev, retouch_targets: event.target.value }))} /></div>
              <div className="field"><label>保真要求</label><input name="fidelity_requirement" value={formValues.fidelity_requirement} onChange={(event) => setFormValues((prev) => ({ ...prev, fidelity_requirement: event.target.value }))} /></div>
              <div className="field"><label><input name="identity_replace" type="checkbox" value="true" checked={formValues.identity_replace} onChange={(event) => setFormValues((prev) => ({ ...prev, identity_replace: event.target.checked }))} /> 开启替换模特流程</label></div>
            </>
          )}

          {tool.slug !== "multi-angle-camera" ? (
            <>
              <div className="field"><label>关键卖点（逗号）</label><input name="key_features" value={formValues.key_features} onChange={(event) => setFormValues((prev) => ({ ...prev, key_features: event.target.value }))} /></div>
              <div className="field"><label>受众</label><input name="target_audience" value={formValues.target_audience} onChange={(event) => setFormValues((prev) => ({ ...prev, target_audience: event.target.value }))} /></div>
              <div className="field"><label>语气</label><input name="tone" value={formValues.tone} onChange={(event) => setFormValues((prev) => ({ ...prev, tone: event.target.value }))} /></div>
              <div className="field"><label>证据点（逗号）</label><input name="evidence_points" value={formValues.evidence_points} onChange={(event) => setFormValues((prev) => ({ ...prev, evidence_points: event.target.value }))} /></div>
              <div className="field"><label>渠道（逗号）</label><input name="channels" value={formValues.channels} onChange={(event) => setFormValues((prev) => ({ ...prev, channels: event.target.value }))} /></div>
              <div className="field"><label>合规屏蔽词（逗号）</label><input name="compliance_blocklist" value={formValues.compliance_blocklist} onChange={(event) => setFormValues((prev) => ({ ...prev, compliance_blocklist: event.target.value }))} /></div>
            </>
          ) : (
            <>
              <input name="key_features" type="hidden" value={formValues.key_features} readOnly />
              <input name="target_audience" type="hidden" value={formValues.target_audience} readOnly />
              <input name="tone" type="hidden" value={formValues.tone} readOnly />
              <input name="evidence_points" type="hidden" value={formValues.evidence_points} readOnly />
              <input name="channels" type="hidden" value={formValues.channels} readOnly />
              <input name="compliance_blocklist" type="hidden" value={formValues.compliance_blocklist} readOnly />
            </>
          )}

          {tool.slug === "multi-angle-camera" && (
            <>
              <input type="hidden" name="camera_yaw" value={0} readOnly />
              <input type="hidden" name="camera_pitch" value={0} readOnly />
              <input type="hidden" name="camera_distance" value="medium" readOnly />
              <input type="hidden" name="camera_focal_mm" value={formValues.camera_focal_mm} readOnly />
              <input type="hidden" name="camera_aspect_ratio" value={formValues.camera_aspect_ratio} readOnly />
            </>
          )}

          {tool.slug !== "multi-angle-camera" ? (
            <div className="field" style={{ gridColumn: "1 / -1" }}><label>创意指令</label><textarea name="creative_direction" value={formValues.creative_direction} onChange={(event) => setFormValues((prev) => ({ ...prev, creative_direction: event.target.value }))} /></div>
          ) : (
            <input name="creative_direction" type="hidden" value={formValues.creative_direction} readOnly />
          )}

          <div style={{ gridColumn: "1 / -1" }} className="toolbar">
            <button type="submit" className="btn-primary" disabled={creating}>{creating ? "提交中..." : tool.slug === "model-retouch" ? "批量创建任务" : tool.slug === "multi-angle-camera" ? "创建并进入机位台" : "创建并进入工作台"}</button>
          </div>
        </form>
        <div className={cx("status-banner", createStatus.type)}>{createStatus.text}</div>
      </section>

      <section className="card">
        <details className="details">
          <summary>本工具任务（点击展开）</summary>
          <div className="toolbar" style={{ marginTop: 10 }}>
            <input placeholder="关键词搜索" value={query} onChange={(event) => setQuery(event.target.value)} style={{ width: 220 }} />
            <button type="button" className="btn-secondary" onClick={loadData}>搜索</button>
            <button type="button" className="btn-secondary" onClick={loadData}>刷新</button>
          </div>
          <div className={cx("status-banner", status.type)}>{status.text}</div>
          <div className="table-wrap" style={{ marginTop: 8 }}>
            <table className="table">
              <thead><tr><th>任务</th><th>阶段</th><th>进度</th><th>状态</th><th>更新时间</th><th>操作</th></tr></thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.project_id} style={highlightBatch && task.batch_group_id === highlightBatch ? { background: "#fff8e8" } : undefined}>
                    <td><strong>{task.product_name}</strong>{task.batch_group_id && <div className="muted">批次：{task.batch_group_id}</div>}</td>
                    <td>{STAGE_LABEL[task.current_stage] || task.current_stage}</td>
                    <td>{task.progress_percent}%<div className="muted">{task.progress_label || "-"}</div></td>
                    <td><span className="badge">{STATUS_LABEL[task.status] || task.status}</span></td>
                    <td>{formatDate(task.updated_at)}</td>
                    <td><button type="button" className="btn-secondary" onClick={() => navigate(`/app/tools/${tool.slug}/projects/${task.project_id}`)}>打开</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>
    </div>
  );
}

function ProjectWorkspace({ tool, projectId, navigate }) {
  const [project, setProject] = useState(null);
  const [progress, setProgress] = useState(null);
  const [assets, setAssets] = useState([]);
  const [logs, setLogs] = useState([]);
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState({ text: "加载中...", type: "" });
  const [planStatus, setPlanStatus] = useState({ text: "等待执行", type: "" });
  const [generateStatus, setGenerateStatus] = useState({ text: "等待执行", type: "" });
  const [actionStatus, setActionStatus] = useState({ text: "点击“执行下一步”自动推进", type: "" });
  const [runningNext, setRunningNext] = useState(false);
  const [runningGenerate, setRunningGenerate] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [promptInputs, setPromptInputs] = useState({ goal: "", style: "", shot_focus: "", constraints: "" });
  const [cameraInputs, setCameraInputs] = useState({
    yaw: 0,
    pitch: 0,
    distance: "medium",
    focal_mm: "50",
    aspect_ratio: "1:1",
  });
  const [options, setOptions] = useState({
    candidates_per_prompt: 1,
    variants_per_shot: 2,
    image_aspect_ratio: "1:1",
    image_resolution: "1K",
    image_output_format: "png",
    video_aspect_ratio: "portrait",
    video_n_frames: "10",
    video_size: "standard",
    video_remove_watermark: true,
  });
  const pollRef = useRef(null);

  const generatedAssets = useMemo(() => assets.filter((item) => item.source_type === "generated"), [assets]);
  const identityAssets = useMemo(() => assets.filter((item) => Array.isArray(item.tags) && item.tags.includes("identity")), [assets]);

  const load = useCallback(async () => {
    try {
      const [p, prog, a, l] = await Promise.all([
        apiFetch(`/api/v1/projects/${projectId}`),
        apiFetch(`/api/v1/projects/${projectId}/progress`),
        apiFetch(`/api/v1/projects/${projectId}/assets`),
        apiFetch(`/api/v1/projects/${projectId}/logs?limit=80`),
      ]);
      setProject(p);
      setProgress(prog);
      setAssets(a);
      setLogs(l);
      setPromptInputs({
        goal: p?.prompt_inputs?.goal || "",
        style: p?.prompt_inputs?.style || "",
        shot_focus: p?.prompt_inputs?.shot_focus || "",
        constraints: (p?.prompt_inputs?.constraints || []).join(","),
      });
      setCameraInputs({
        yaw: Number(p?.camera_inputs?.yaw ?? 0),
        pitch: Number(p?.camera_inputs?.pitch ?? 0),
        distance: p?.camera_inputs?.distance || "medium",
        focal_mm: p?.camera_inputs?.focal_mm || "50",
        aspect_ratio: p?.camera_inputs?.aspect_ratio || "1:1",
      });
      setStatus({ text: `阶段：${STAGE_LABEL[prog.current_stage] || prog.current_stage} ｜ 进度：${prog.progress_percent_weighted}% ｜ ${prog.next_action || "按流程执行"}`, type: p.status === "failed" ? "error" : "success" });
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!progress || progress.task_status !== "running") {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    if (!pollRef.current) {
      pollRef.current = setInterval(() => load().catch(() => undefined), 5000);
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [progress, load]);

  const savePrompt = async () => {
    try {
      setPlanStatus({ text: "保存提示词...", type: "" });
      await apiFetch(`/api/v1/projects/${projectId}/prompt-inputs`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt_inputs: { ...promptInputs, constraints: parseCsv(promptInputs.constraints) } }),
      });
      await load();
      setPlanStatus({ text: "提示词已保存", type: "success" });
    } catch (error) {
      setPlanStatus({ text: error.message, type: "error" });
    }
  };

  const requestPlan = async (force = true) => {
    if (tool.slug === "multi-angle-camera") {
      await apiFetch(`/api/v1/projects/${projectId}/multi-angle/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force }),
      });
      return;
    }
    await apiFetch(`/api/v1/projects/${projectId}/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force }),
    });
  };

  const genPlan = async () => {
    try {
      setPlanStatus({ text: "生成AI方案...", type: "" });
      await requestPlan(true);
      await load();
      setPlanStatus({ text: "AI方案已更新", type: "success" });
    } catch (error) {
      setPlanStatus({ text: error.message, type: "error" });
    }
  };

  const applyCameraInputs = async () => {
    await apiFetch(`/api/v1/projects/${projectId}/multi-angle/camera-inputs`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        yaw: Number(cameraInputs.yaw || 0),
        pitch: Number(cameraInputs.pitch || 0),
        distance: cameraInputs.distance,
        focal_mm: cameraInputs.focal_mm,
        aspect_ratio: cameraInputs.aspect_ratio || options.image_aspect_ratio,
      }),
    });
  };

  const derivePrompts = async () => {
    try {
      setPlanStatus({ text: "编译提示词...", type: "" });
      await apiFetch(`/api/v1/projects/${projectId}/derive-prompts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force: true }) });
      await load();
      setPlanStatus({ text: "提示词已编译", type: "success" });
    } catch (error) {
      setPlanStatus({ text: error.message, type: "error" });
    }
  };

  const prepareIntroFlow = async () => {
    if (!project) return;
    if (!project.selected_script && project.script_options?.length) {
      await apiFetch(`/api/v1/projects/${projectId}/select-script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ script_id: project.script_options[0].script_id, edits: [] }),
      });
    }
    await apiFetch(`/api/v1/projects/${projectId}/storyboard/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ regenerate: false, async_mode: false }),
    });
    const latest = await apiFetch(`/api/v1/projects/${projectId}`);
    if (latest.selected_script?.shots?.length) {
      for (const shot of latest.selected_script.shots) {
        await apiFetch(`/api/v1/projects/${projectId}/storyboard/approve-shot`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ shot_id: shot.shot_id, status: "approved" }),
        });
      }
      await apiFetch(`/api/v1/projects/${projectId}/storyboard/confirm`, { method: "POST" });
    }
  };

  const submitGenerate = async (stage = "auto") => {
    if (tool.slug === "intro-video") {
      await prepareIntroFlow();
    }
    return apiFetch(`/api/v1/projects/${projectId}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        stage,
        async_mode: true,
        candidates_per_prompt: options.candidates_per_prompt,
        variants_per_shot: options.variants_per_shot,
        image_aspect_ratio: options.image_aspect_ratio,
        image_resolution: options.image_resolution,
        image_output_format: options.image_output_format,
        video_aspect_ratio: options.video_aspect_ratio,
        video_n_frames: options.video_n_frames,
        video_size: options.video_size,
        video_remove_watermark: options.video_remove_watermark,
      }),
    });
  };

  const runGenerate = async (stage = "auto") => {
    if (runningGenerate) return;
    try {
      setRunningGenerate(true);
      setGenerateStatus({ text: "提交生成任务...", type: "" });
      await submitGenerate(stage);
      await load();
      setGenerateStatus({ text: "任务已提交，结果会自动刷新", type: "success" });
    } catch (error) {
      setGenerateStatus({ text: error.message, type: "error" });
    } finally {
      setRunningGenerate(false);
    }
  };

  const runNextAction = async () => {
    if (runningNext) return;
    try {
      setRunningNext(true);
      setActionStatus({ text: "正在推进下一步...", type: "" });
      setGenerateStatus({ text: "等待执行", type: "" });

      if (!project) {
        await load();
      }
      const current = project || (await apiFetch(`/api/v1/projects/${projectId}`));

      if (tool.slug === "multi-angle-camera") {
        await applyCameraInputs();
        await requestPlan(false);
        await submitGenerate("auto");
        await load();
        setStep(2);
        setActionStatus({ text: "多角度任务已提交，正在按机位批量生成。", type: "success" });
        return;
      }

      if (!current.project_plan) {
        await requestPlan(false);
        await load();
        setStep(1);
        setActionStatus({ text: "已完成AI方案，请确认后继续。", type: "success" });
        return;
      }

      if (!current.prompt_pack) {
        await apiFetch(`/api/v1/projects/${projectId}/derive-prompts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: false }),
        });
        await load();
        setStep(1);
        setActionStatus({ text: "提示词编译完成，可继续执行生成。", type: "success" });
        return;
      }

      if (tool.slug === "model-retouch" && current.identity_required && current.identity_status !== "confirmed") {
        setStep(2);
        setActionStatus({ text: "请先在 Step3 完成身份确认，再执行批量精修。", type: "warning" });
        return;
      }

      await submitGenerate("auto");
      await load();
      setStep(generationStepIndex);
      setActionStatus({ text: "任务已提交，已进入生成阶段。", type: "success" });
    } catch (error) {
      setActionStatus({ text: error.message, type: "error" });
    } finally {
      setRunningNext(false);
    }
  };

  const retry = async () => {
    if (retrying) return;
    try {
      setRetrying(true);
      setGenerateStatus({ text: "提交重试...", type: "" });
      await apiFetch(`/api/v1/projects/${projectId}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ async_mode: true }),
      });
      await load();
      setGenerateStatus({ text: "重试已提交", type: "success" });
    } catch (error) {
      setGenerateStatus({ text: error.message, type: "error" });
    } finally {
      setRetrying(false);
    }
  };

  const generateIdentityCandidate = async (regenerate = false) => {
    try {
      setActionStatus({ text: regenerate ? "重新生成身份候选中..." : "生成身份候选中...", type: "" });
      if (regenerate) {
        await apiFetch(`/api/v1/projects/${projectId}/identity/regenerate-candidate`, { method: "POST" });
      } else {
        await apiFetch(`/api/v1/projects/${projectId}/identity/generate-candidate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: false }),
        });
      }
      await load();
      setActionStatus({ text: "身份候选图已更新，请确认后继续。", type: "success" });
    } catch (error) {
      setActionStatus({ text: error.message, type: "error" });
    }
  };

  const confirmIdentity = async (assetId) => {
    try {
      setActionStatus({ text: "确认身份中...", type: "" });
      await apiFetch(`/api/v1/projects/${projectId}/identity/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: assetId }),
      });
      await load();
      setActionStatus({ text: "身份已确认，可执行批量精修。", type: "success" });
      setStep(3);
    } catch (error) {
      setActionStatus({ text: error.message, type: "error" });
    }
  };

  const reviewAsset = async (assetId, action) => {
    try {
      await apiFetch(`/api/v1/projects/${projectId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: assetId, action }),
      });
      await load();
    } catch (error) {
      setGenerateStatus({ text: error.message, type: "error" });
    }
  };

  const sourceImage = project?.image_public_url || localPathToMedia(project?.image_path || "");
  const crumb = breadcrumbs({ page: "project", toolSlug: tool.slug, projectId }, project?.brief?.product_name || "");
  const generationStepIndex = tool.slug === "model-retouch" ? 3 : Math.min(2, tool.steps.length - 1);
  const identityStepIndex = tool.slug === "model-retouch" ? 2 : -1;

  return (
    <div className="content-stack">
      <div className="breadcrumb">{crumb.join(" / ")}</div>
      <section className="card">
        <div className="toolbar" style={{ justifyContent: "space-between" }}>
          <div>
            <h1>{tool.title} · 工作台</h1>
            <div className="muted">项目ID：{projectId}</div>
          </div>
          <div className="toolbar">
            <button type="button" className="btn-secondary" onClick={load}>刷新</button>
            <button type="button" className="btn-primary" onClick={runNextAction} disabled={runningNext}>{runningNext ? "推进中..." : "执行下一步"}</button>
            <button type="button" className="btn-ghost" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>返回任务中心</button>
          </div>
        </div>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        <div className={cx("status-banner", actionStatus.type)}>{actionStatus.text}</div>
      </section>

      <div className="page-grid">
        <aside className="side-stepper">
          <h3>{tool.title}</h3>
          {tool.steps.map((label, idx) => (
            <button key={label} type="button" className={cx("step-btn", idx === step && "active")} onClick={() => setStep(idx)}>
              {idx + 1}. {label}
            </button>
          ))}
        </aside>

        <div className="content-stack">
          {step === 0 && (
            <section className="card">
              <h2>Step 1 / {tool.steps[0]}</h2>
              {!project ? (
                <div className="empty-state">加载中...</div>
              ) : (
                <div className="grid">
                  <div className="asset-card">
                    <h4>基础信息</h4>
                    <div className="muted">产品：{project.brief?.product_name || "-"}</div>
                    <div className="muted">模板：{project.template_name || "-"}</div>
                    <div className="muted">质量：{project.quality_level || "-"}</div>
                    <div className="muted">更新时间：{formatDate(project.updated_at)}</div>
                  </div>
                  <div className="asset-card">
                    <h4>任务状态</h4>
                    <div className="muted">阶段：{STAGE_LABEL[progress?.current_stage] || progress?.current_stage || "-"}</div>
                    <div className="muted">进度：{progress?.progress_percent_weighted ?? 0}%</div>
                    <div className="muted">状态：{STATUS_LABEL[progress?.task_status] || progress?.task_status || "-"}</div>
                  </div>
                  <div className="asset-card">
                    <h4>主素材</h4>
                    {sourceImage ? <img src={sourceImage} alt="source" /> : <div className="empty-state">无素材</div>}
                  </div>
                </div>
              )}
            </section>
          )}

          {step === 1 && (
            <section className="card">
              <h2>Step 2 / {tool.steps[1]}</h2>
              {tool.slug === "multi-angle-camera" ? (
                <>
                  <div className="field">
                    <label>角度比例</label>
                    <select
                      style={{ width: 150 }}
                      value={cameraInputs.aspect_ratio}
                      onChange={(event) => setCameraInputs((prev) => ({ ...prev, aspect_ratio: event.target.value }))}
                    >
                      <option value="1:1">1:1</option>
                      <option value="4:5">4:5</option>
                      <option value="3:4">3:4</option>
                      <option value="9:16">9:16</option>
                      <option value="16:9">16:9</option>
                    </select>
                  </div>
                  <MultiAnglePad
                    values={{
                      camera_yaw: Number(cameraInputs.yaw || 0),
                      camera_pitch: Number(cameraInputs.pitch || 0),
                      camera_distance: cameraInputs.distance || "medium",
                      camera_focal_mm: cameraInputs.focal_mm || "50",
                    }}
                    setValues={(updater) => {
                      setCameraInputs((prev) => {
                        const current = {
                          camera_yaw: Number(prev.yaw || 0),
                          camera_pitch: Number(prev.pitch || 0),
                          camera_distance: prev.distance || "medium",
                          camera_focal_mm: prev.focal_mm || "50",
                        };
                        const updated = typeof updater === "function" ? updater(current) : updater;
                        return {
                          ...prev,
                          yaw: Number(updated.camera_yaw || 0),
                          pitch: Number(updated.camera_pitch || 0),
                          distance: updated.camera_distance || "medium",
                          focal_mm: updated.camera_focal_mm || "50",
                        };
                      });
                    }}
                    previewSrc={sourceImage}
                  />
                  <div className="toolbar" style={{ marginTop: 10 }}>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={async () => {
                        try {
                          setPlanStatus({ text: "保存机位参数并生成方案...", type: "" });
                          await applyCameraInputs();
                          await requestPlan(true);
                          await load();
                          setPlanStatus({ text: "机位方案已更新。", type: "success" });
                        } catch (error) {
                          setPlanStatus({ text: error.message, type: "error" });
                        }
                      }}
                    >
                      仅保存机位
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="grid">
                    <div className="field"><label>目标</label><input value={promptInputs.goal} onChange={(event) => setPromptInputs((prev) => ({ ...prev, goal: event.target.value }))} /></div>
                    <div className="field"><label>风格</label><input value={promptInputs.style} onChange={(event) => setPromptInputs((prev) => ({ ...prev, style: event.target.value }))} /></div>
                    <div className="field" style={{ gridColumn: "1 / -1" }}><label>镜头重点</label><input value={promptInputs.shot_focus} onChange={(event) => setPromptInputs((prev) => ({ ...prev, shot_focus: event.target.value }))} /></div>
                    <div className="field" style={{ gridColumn: "1 / -1" }}><label>限制（逗号）</label><input value={promptInputs.constraints} onChange={(event) => setPromptInputs((prev) => ({ ...prev, constraints: event.target.value }))} /></div>
                  </div>
                  <div className="toolbar" style={{ marginTop: 10 }}>
                    <button type="button" className="btn-primary" onClick={savePrompt}>保存提示词</button>
                    <button type="button" className="btn-secondary" onClick={genPlan}>生成AI方案</button>
                    <button type="button" className="btn-secondary" onClick={derivePrompts}>编译提示词</button>
                  </div>
                </>
              )}
              <div className={cx("status-banner", planStatus.type)}>{planStatus.text}</div>
              <div style={{ marginTop: 12 }}>
                {tool.slug === "multi-angle-camera" ? (
                  <>
                    <h3>机位参数摘要</h3>
                    <div className="status-banner">
                      yaw {Number(cameraInputs.yaw || 0)}° · pitch {Number(cameraInputs.pitch || 0)}° · {cameraInputs.focal_mm || "50"}mm · {cameraInputs.distance || "medium"} · {cameraInputs.aspect_ratio || "1:1"}
                    </div>
                    <div className="toolbar" style={{ marginTop: 10 }}>
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={async () => {
                          try {
                            setPlanStatus({ text: "保存机位并提交多角度生成...", type: "" });
                            await applyCameraInputs();
                            await requestPlan(false);
                            await submitGenerate("auto");
                            await load();
                            setStep(generationStepIndex);
                            setPlanStatus({ text: "多角度生成任务已提交，正在逐张返回。", type: "success" });
                          } catch (error) {
                            setPlanStatus({ text: error.message, type: "error" });
                          }
                        }}
                      >
                        开始生成多角度图
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <h3>当前方案</h3>
                    {project?.project_plan?.shots?.length ? (
                      <div className="asset-grid">
                        {project.project_plan.shots.map((shot) => (
                          <div className="asset-card" key={shot.shot_id}>
                            <strong>{shot.title || shot.shot_id}</strong>
                            <div className="muted">{shot.intent || ""}</div>
                            <div className="muted">生图：{shot.image_prompt || "-"}</div>
                            {tool.category === "video" && <div className="muted">视频：{shot.video_prompt || "-"}</div>}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="empty-state">暂无方案，请先生成。</div>
                    )}
                  </>
                )}
              </div>
            </section>
          )}

          {step === identityStepIndex && (
            <section className="card">
              <h2>Step 3 / 身份确认</h2>
              {!project?.identity_required ? (
                <div className="empty-state">当前任务未开启替换模特流程，可直接进入批量精修。</div>
              ) : (
                <>
                  <div className="toolbar">
                    <span className="badge">当前状态：{project.identity_status === "confirmed" ? "已确认" : "待确认"}</span>
                    <button type="button" className="btn-primary" onClick={() => generateIdentityCandidate(false)}>生成身份候选</button>
                    <button type="button" className="btn-secondary" onClick={() => generateIdentityCandidate(true)}>重新生成候选</button>
                  </div>
                  {!identityAssets.length ? (
                    <div className="empty-state" style={{ marginTop: 10 }}>暂无身份候选图，先点击“生成身份候选”。</div>
                  ) : (
                    <div className="asset-grid" style={{ marginTop: 10 }}>
                      {identityAssets.map((asset) => {
                        const imageUrl = asset.image_url || localPathToMedia(asset.local_path);
                        const selected = asset.asset_id === project.identity_asset_id;
                        return (
                          <article key={asset.asset_id} className="asset-card">
                            {imageUrl ? <img src={imageUrl} alt="identity-candidate" /> : <div className="empty-state">无预览</div>}
                            <div className="toolbar" style={{ marginTop: 8 }}>
                              <span className="badge">{selected ? "当前锚点" : "候选图"}</span>
                              <button type="button" className="btn-primary" onClick={() => confirmIdentity(asset.asset_id)}>确认身份</button>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </section>
          )}

          {step === generationStepIndex && (
            <section className="card">
              <h2>Step {generationStepIndex + 1} / {tool.steps[generationStepIndex]}</h2>
              <div className="toolbar">
                {tool.category === "image" ? (
                  <>
                    <label className="muted">{tool.slug === "multi-angle-camera" ? "每个角度出图数" : "每镜头生图数"}</label>
                    <input style={{ width: 90 }} type="number" min={1} max={4} value={options.candidates_per_prompt} onChange={(event) => setOptions((prev) => ({ ...prev, candidates_per_prompt: Number(event.target.value || 1) }))} />
                    <label className="muted">比例</label>
                    <select style={{ width: 110 }} value={options.image_aspect_ratio} onChange={(event) => setOptions((prev) => ({ ...prev, image_aspect_ratio: event.target.value }))}><option value="1:1">1:1</option><option value="4:5">4:5</option><option value="3:4">3:4</option><option value="9:16">9:16</option><option value="16:9">16:9</option></select>
                    {tool.slug !== "multi-angle-camera" && (
                      <>
                        <label className="muted">分辨率</label>
                        <select style={{ width: 90 }} value={options.image_resolution} onChange={(event) => setOptions((prev) => ({ ...prev, image_resolution: event.target.value }))}><option value="1K">1K</option><option value="2K">2K</option><option value="4K">4K</option></select>
                        <label className="muted">格式</label>
                        <select style={{ width: 90 }} value={options.image_output_format} onChange={(event) => setOptions((prev) => ({ ...prev, image_output_format: event.target.value }))}><option value="png">png</option><option value="jpg">jpg</option></select>
                      </>
                    )}
                  </>
                ) : (
                  <>
                    <label className="muted">候选数</label>
                    <input style={{ width: 90 }} type="number" min={1} max={4} value={options.variants_per_shot} onChange={(event) => setOptions((prev) => ({ ...prev, variants_per_shot: Number(event.target.value || 2) }))} />
                    <label className="muted">比例</label>
                    <select style={{ width: 110 }} value={options.video_aspect_ratio} onChange={(event) => setOptions((prev) => ({ ...prev, video_aspect_ratio: event.target.value }))}><option value="portrait">portrait</option><option value="landscape">landscape</option></select>
                    <label className="muted">帧数</label>
                    <select style={{ width: 90 }} value={options.video_n_frames} onChange={(event) => setOptions((prev) => ({ ...prev, video_n_frames: event.target.value }))}><option value="10">10</option><option value="15">15</option></select>
                    <label className="muted">质量</label>
                    <select style={{ width: 110 }} value={options.video_size} onChange={(event) => setOptions((prev) => ({ ...prev, video_size: event.target.value }))}><option value="standard">standard</option><option value="high">high</option></select>
                    <label className="muted"><input type="checkbox" checked={options.video_remove_watermark} onChange={(event) => setOptions((prev) => ({ ...prev, video_remove_watermark: event.target.checked }))} /> 去水印</label>
                  </>
                )}
                <button type="button" className="btn-primary" onClick={() => runGenerate("auto")} disabled={runningGenerate}>{runningGenerate ? "提交中..." : "开始生成"}</button>
                <button type="button" className="btn-secondary" onClick={retry} disabled={retrying}>{retrying ? "重试中..." : "失败重试"}</button>
              </div>
              <div className={cx("status-banner", generateStatus.type)}>{generateStatus.text}</div>
            </section>
          )}

          {step === tool.steps.length - 1 && (
            <section className="card">
              <h2>Step {tool.steps.length} / {tool.steps[tool.steps.length - 1]}</h2>
              {!generatedAssets.length ? (
                <div className="empty-state">暂无产物，先执行生成。</div>
              ) : (
                <div className="asset-grid">
                  {generatedAssets.map((asset) => {
                    const imageUrl = asset.image_url || localPathToMedia(asset.local_path);
                    const videoUrl = asset.video_url || localPathToMedia(asset.local_path);
                    return (
                      <article key={asset.asset_id} className="asset-card">
                        {imageUrl ? <img src={imageUrl} alt="asset" /> : videoUrl ? <video src={videoUrl} controls preload="metadata" /> : <div className="empty-state">无预览</div>}
                        <div className="toolbar" style={{ marginTop: 8 }}>
                          <span className="badge">{asset.status}</span>
                          <button type="button" className="btn-secondary" onClick={() => reviewAsset(asset.asset_id, "approve")}>通过</button>
                          <button type="button" className="btn-danger" onClick={() => reviewAsset(asset.asset_id, "reject")}>淘汰</button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          <section className="card">
            <details className="details">
              <summary>运行日志（默认收起）</summary>
              {!logs.length ? (
                <div className="empty-state" style={{ marginTop: 8 }}>暂无日志</div>
              ) : (
                <div className="content-stack" style={{ marginTop: 8 }}>
                  {logs.slice().reverse().slice(0, 30).map((item) => (
                    <div key={item.event_id} className="asset-card">
                      <div><strong>{item.stage}</strong> <span className="muted">{formatDate(item.timestamp)}</span></div>
                      <div className="muted">{item.message}</div>
                    </div>
                  ))}
                </div>
              )}
            </details>
          </section>
        </div>
      </div>
    </div>
  );
}

export default function AppPage() {
  const { route, navigate } = useRouterState();
  const [auth, setAuth] = useState({ loading: true, authenticated: false, username: "" });

  const refreshAuth = useCallback(async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 6000);
    try {
      const resp = await fetch("/api/v1/auth/me", { credentials: "include", signal: controller.signal });
      const data = await resp.json().catch(() => ({}));
      setAuth({ loading: false, authenticated: Boolean(data.authenticated), username: data.username || "" });
    } catch (_) {
      setAuth({ loading: false, authenticated: false, username: "" });
    } finally {
      clearTimeout(timer);
    }
  }, []);

  useEffect(() => { refreshAuth(); }, [refreshAuth]);

  useEffect(() => {
    if (auth.loading) return;
    if (!auth.authenticated && route.page !== "login") navigate("/app/login");
    if (auth.authenticated && route.page === "login") navigate("/app/tools");
  }, [auth, route.page, navigate]);

  const logout = async () => {
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" }).catch(() => undefined);
    setAuth({ loading: false, authenticated: false, username: "" });
    navigate("/app/login");
  };

  if (route.page === "login") {
    return <LoginPage navigate={navigate} />;
  }

  if (auth.loading) {
    return (
      <div className="app-main">
        <section className="card"><div className="status-banner">加载用户信息...</div></section>
      </div>
    );
  }

  if (!auth.authenticated) return null;

  let content = <ToolsHome navigate={navigate} />;
  if (route.page === "assets") {
    content = <AssetsPage navigate={navigate} />;
  } else if (route.page === "tasks") {
    const tool = TOOLS[route.toolSlug] || TOOLS["intro-video"];
    content = <ToolTasksPage tool={tool} navigate={navigate} />;
  } else if (route.page === "project") {
    const tool = TOOLS[route.toolSlug] || TOOLS["intro-video"];
    content = <ProjectWorkspace tool={tool} projectId={route.projectId} navigate={navigate} />;
  }

  return (
    <div className="app-shell">
      <TopBar route={route} auth={auth} navigate={navigate} onLogout={logout} />
      <div className="app-workspace">
        <AppSidebar route={route} navigate={navigate} />
        <main className="workspace-main">
          {(route.page === "assets" || route.page === "tasks") && <div className="breadcrumb">{breadcrumbs(route).join(" / ")}</div>}
          {content}
        </main>
      </div>
    </div>
  );
}
