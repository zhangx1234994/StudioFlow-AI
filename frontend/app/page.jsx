"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
  const [dragging, setDragging] = useState(false);
  const padRef = useRef(null);

  const move = useCallback((event) => {
    const pad = padRef.current;
    if (!pad) return;
    const rect = pad.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
    setValues((prev) => ({ ...prev, camera_yaw: Math.round(x * 360 - 180), camera_pitch: Math.round(45 - y * 90) }));
  }, [setValues]);

  const perspective = values.camera_focal_mm === "35" ? 520 : values.camera_focal_mm === "85" ? 920 : 720;
  const scale = values.camera_distance === "near" ? 1.12 : values.camera_distance === "far" ? 0.9 : 1;

  return (
    <div className="camera-pad-wrap">
      <div
        ref={padRef}
        className="camera-pad"
        onPointerDown={(event) => { setDragging(true); move(event); }}
        onPointerMove={(event) => { if (dragging) move(event); }}
        onPointerUp={() => setDragging(false)}
        onPointerLeave={() => setDragging(false)}
      >
        <div className="camera-cross-x" />
        <div className="camera-cross-y" />
        <div className="camera-dot" style={{ left: `${((values.camera_yaw + 180) / 360) * 100}%`, top: `${((45 - values.camera_pitch) / 90) * 100}%` }} />
      </div>
      <div className="toolbar" style={{ marginTop: 8 }}>
        {[{ label: "主视角", yaw: 0, pitch: 0 }, { label: "左前45", yaw: -45, pitch: 0 }, { label: "右前45", yaw: 45, pitch: 0 }, { label: "俯视角", yaw: 0, pitch: -20 }].map((item) => (
          <button key={item.label} type="button" className="btn-secondary" onClick={() => setValues((prev) => ({ ...prev, camera_yaw: item.yaw, camera_pitch: item.pitch }))}>{item.label}</button>
        ))}
      </div>
      <div className="grid" style={{ marginTop: 8 }}>
        <div className="field"><label>yaw</label><input type="number" min={-180} max={180} value={values.camera_yaw} onChange={(event) => setValues((prev) => ({ ...prev, camera_yaw: Number(event.target.value || 0) }))} /></div>
        <div className="field"><label>pitch</label><input type="number" min={-45} max={45} value={values.camera_pitch} onChange={(event) => setValues((prev) => ({ ...prev, camera_pitch: Number(event.target.value || 0) }))} /></div>
        <div className="field"><label>distance</label><select value={values.camera_distance} onChange={(event) => setValues((prev) => ({ ...prev, camera_distance: event.target.value }))}><option value="near">near</option><option value="medium">medium</option><option value="far">far</option></select></div>
        <div className="field"><label>focal</label><select value={values.camera_focal_mm} onChange={(event) => setValues((prev) => ({ ...prev, camera_focal_mm: event.target.value }))}><option value="35">35mm</option><option value="50">50mm</option><option value="85">85mm</option></select></div>
      </div>
      <div className="status-banner" style={{ marginTop: 8 }}>yaw {values.camera_yaw}° | pitch {values.camera_pitch}° | {values.camera_focal_mm}mm | {values.camera_distance}</div>
      <div className="preview-stage" style={{ marginTop: 8 }}>
        {previewSrc ? (
          <img
            src={previewSrc}
            alt="camera-preview"
            style={{ transform: `perspective(${perspective}px) rotateY(${(values.camera_yaw * 0.35).toFixed(2)}deg) rotateX(${(-values.camera_pitch * 0.5).toFixed(2)}deg) scale(${scale})` }}
          />
        ) : (
          <span className="muted">上传主图后可预览机位变化</span>
        )}
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
              {(tool.slug === "product-image" || tool.slug === "multi-angle-camera") && (
                <div className="field">
                  <label>风格参考图（可多选）</label>
                  <input
                    key={`${tool.slug}-reference-${tool.slug === "product-image" ? fileInputVersion.reference_images : fileInputVersion.style_reference_images}`}
                    name={tool.slug === "product-image" ? "reference_images" : "style_reference_images"}
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={(event) => onFileChange(tool.slug === "product-image" ? "reference_images" : "style_reference_images", event)}
                  />
                  <div className="toolbar">
                    <span className="muted">
                      {selectedFileSummary(tool.slug === "product-image" ? selectedFiles.reference_images : selectedFiles.style_reference_images)}
                    </span>
                    {(tool.slug === "product-image" ? selectedFiles.reference_images.length : selectedFiles.style_reference_images.length) > 0 && (
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={() => clearFiles(tool.slug === "product-image" ? "reference_images" : "style_reference_images")}
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
          <div className="field"><label>平台</label><input name="platform" value={formValues.platform} onChange={(event) => setFormValues((prev) => ({ ...prev, platform: event.target.value }))} /></div>

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

          <div className="field"><label>关键卖点（逗号）</label><input name="key_features" value={formValues.key_features} onChange={(event) => setFormValues((prev) => ({ ...prev, key_features: event.target.value }))} /></div>
          <div className="field"><label>受众</label><input name="target_audience" value={formValues.target_audience} onChange={(event) => setFormValues((prev) => ({ ...prev, target_audience: event.target.value }))} /></div>
          <div className="field"><label>语气</label><input name="tone" value={formValues.tone} onChange={(event) => setFormValues((prev) => ({ ...prev, tone: event.target.value }))} /></div>
          <div className="field"><label>证据点（逗号）</label><input name="evidence_points" value={formValues.evidence_points} onChange={(event) => setFormValues((prev) => ({ ...prev, evidence_points: event.target.value }))} /></div>
          <div className="field"><label>渠道（逗号）</label><input name="channels" value={formValues.channels} onChange={(event) => setFormValues((prev) => ({ ...prev, channels: event.target.value }))} /></div>
          <div className="field"><label>合规屏蔽词（逗号）</label><input name="compliance_blocklist" value={formValues.compliance_blocklist} onChange={(event) => setFormValues((prev) => ({ ...prev, compliance_blocklist: event.target.value }))} /></div>

          {tool.slug === "multi-angle-camera" && (
            <>
              <input type="hidden" name="camera_yaw" value={formValues.camera_yaw} readOnly />
              <input type="hidden" name="camera_pitch" value={formValues.camera_pitch} readOnly />
              <input type="hidden" name="camera_distance" value={formValues.camera_distance} readOnly />
              <input type="hidden" name="camera_focal_mm" value={formValues.camera_focal_mm} readOnly />
              <input type="hidden" name="camera_aspect_ratio" value={formValues.camera_aspect_ratio} readOnly />
              <div className="field" style={{ gridColumn: "1 / -1" }}>
                <label>可视化机位控制</label>
                <MultiAnglePad values={formValues} setValues={setFormValues} previewSrc={previewSrc} />
              </div>
            </>
          )}

          <div className="field" style={{ gridColumn: "1 / -1" }}><label>创意指令</label><textarea name="creative_direction" value={formValues.creative_direction} onChange={(event) => setFormValues((prev) => ({ ...prev, creative_direction: event.target.value }))} /></div>

          <div style={{ gridColumn: "1 / -1" }} className="toolbar">
            <button type="submit" className="btn-primary" disabled={creating}>{creating ? "提交中..." : tool.slug === "model-retouch" ? "批量创建任务" : "创建并进入工作台"}</button>
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
                      className="btn-primary"
                      onClick={async () => {
                        try {
                          setPlanStatus({ text: "保存机位参数并生成方案...", type: "" });
                          await applyCameraInputs();
                          await requestPlan(true);
                          await load();
                          setPlanStatus({ text: "机位方案已更新，可执行批量生成。", type: "success" });
                        } catch (error) {
                          setPlanStatus({ text: error.message, type: "error" });
                        }
                      }}
                    >
                      保存机位并更新方案
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
                    <label className="muted">每镜头生图数</label>
                    <input style={{ width: 90 }} type="number" min={1} max={4} value={options.candidates_per_prompt} onChange={(event) => setOptions((prev) => ({ ...prev, candidates_per_prompt: Number(event.target.value || 1) }))} />
                    <label className="muted">比例</label>
                    <select style={{ width: 110 }} value={options.image_aspect_ratio} onChange={(event) => setOptions((prev) => ({ ...prev, image_aspect_ratio: event.target.value }))}><option value="1:1">1:1</option><option value="4:5">4:5</option><option value="3:4">3:4</option><option value="9:16">9:16</option><option value="16:9">16:9</option></select>
                    <label className="muted">分辨率</label>
                    <select style={{ width: 90 }} value={options.image_resolution} onChange={(event) => setOptions((prev) => ({ ...prev, image_resolution: event.target.value }))}><option value="1K">1K</option><option value="2K">2K</option><option value="4K">4K</option></select>
                    <label className="muted">格式</label>
                    <select style={{ width: 90 }} value={options.image_output_format} onChange={(event) => setOptions((prev) => ({ ...prev, image_output_format: event.target.value }))}><option value="png">png</option><option value="jpg">jpg</option></select>
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
    const isViewportBlocker = (el) => {
      if (!(el instanceof HTMLElement)) return false;
      if (el.classList.contains("app-shell")) return false;
      if (el.classList.contains("topbar")) return false;
      const style = window.getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden") return false;
      if (!["fixed", "absolute"].includes(style.position)) return false;
      if (style.pointerEvents === "none") return false;
      const rect = el.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const coversViewport = rect.width >= vw * 0.95 && rect.height >= vh * 0.95;
      if (!coversViewport) return false;
      return true;
    };

    const neutralizeBlockers = () => {
      const nodes = Array.from(document.querySelectorAll("body *"));
      for (const node of nodes) {
        if (!isViewportBlocker(node)) continue;
        node.setAttribute("data-overlay-neutralized", "true");
        node.style.pointerEvents = "none";
        node.style.background = "transparent";
        node.style.backdropFilter = "none";
      }
    };

    neutralizeBlockers();
    const timer = window.setInterval(neutralizeBlockers, 1000);
    const observer = new MutationObserver(() => neutralizeBlockers());
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "class", "open"] });
    return () => {
      window.clearInterval(timer);
      observer.disconnect();
    };
  }, []);

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
