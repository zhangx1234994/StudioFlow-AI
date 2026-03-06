"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const TOOLS = {
  "intro-video": {
    slug: "intro-video",
    toolType: "intro_video_multi_script",
    scenarioType: "product_video",
    title: "转化讲解视频工坊",
    subtitle: "AI先生成3套脚本，确认后再分镜与视频候选。",
    category: "video",
    steps: ["需求与素材", "AI方案与执行方案", "视频生成", "人工确认"],
  },
  "product-image": {
    slug: "product-image",
    toolType: "product_image_suite",
    scenarioType: "product_image_suite",
    title: "商品棚拍出图工坊",
    subtitle: "先生成组图拍摄方案，再按每个镜头试拍多张候选图。",
    category: "image",
    steps: ["需求与素材", "组图拍摄方案", "开始试拍", "选片分享"],
  },
  "model-retouch": {
    slug: "model-retouch",
    toolType: "model_retouch",
    scenarioType: "model_retouch",
    title: "模特人像精修工坊",
    subtitle: "先确认身份锚点，再一键并行精修整组图片，逐张回填结果。",
    category: "image",
    steps: ["素材确认", "模特锚点确认", "批量精修执行", "结果审核与导出"],
  },
  "quick-video-15s": {
    slug: "quick-video-15s",
    toolType: "quick_video_15s",
    scenarioType: "product_video",
    title: "15秒场景短片工坊",
    subtitle: "AI规划15秒节奏并默认生成3个候选。",
    category: "video",
    steps: ["需求与素材", "AI方案与执行方案", "一键生成候选", "人工确认"],
  },
  "multi-angle-camera": {
    slug: "multi-angle-camera",
    toolType: "multi_angle_camera",
    scenarioType: "multi_angle_camera",
    title: "多角度展品工坊",
    subtitle: "3D机位控制 + 实时预览，每次生成当前机位的单张角度图。",
    category: "image",
    steps: ["素材与目标", "机位控制", "生成当前角度", "人工确认"],
  },
};

const MODEL_IDENTITY_TEMPLATES = [
  {
    label: "电商清透棚拍",
    identity_source: "beautify_uploaded",
    lighting_preset: "softbox_clean",
    framing_preset: "full_body",
    angle_preset: "front",
    identity_requirements: "肤色均匀自然，保留真实纹理，气质干净高级。",
    preserve_pose: true,
  },
  {
    label: "时尚轮廓大片",
    identity_source: "generate_new",
    lighting_preset: "rim_fashion",
    framing_preset: "full_body",
    angle_preset: "left_45",
    identity_requirements: "时尚感更强，面部结构立体，妆发克制高级。",
    preserve_pose: true,
  },
  {
    label: "自然窗光人像",
    identity_source: "beautify_uploaded",
    lighting_preset: "window_natural",
    framing_preset: "full_body",
    angle_preset: "front",
    identity_requirements: "自然真实，皮肤细节清晰，表情松弛。",
    preserve_pose: true,
  },
];

const TOOL_LIST = Object.values(TOOLS);
const HIDDEN_WEB_TOOL_SLUGS = new Set(["multi-angle-camera"]);
const VISIBLE_TOOL_LIST = TOOL_LIST.filter((tool) => !HIDDEN_WEB_TOOL_SLUGS.has(tool.slug));
const TOOL_BY_TYPE = Object.fromEntries(TOOL_LIST.map((tool) => [tool.toolType, tool]));
const SHOWCASE_TABS = [
  { key: "all", label: "全部样片" },
  { key: "main", label: "主图套图" },
  { key: "scene", label: "场景套图" },
  { key: "model", label: "模特精修" },
  { key: "angle", label: "多角度图" },
];

const RESULT_FILTERS = [
  { key: "all", label: "全部结果" },
  { key: "approved", label: "已通过" },
  { key: "pending", label: "待筛选" },
  { key: "failed", label: "异常" },
];
const IMAGE_ASPECT_OPTIONS = [
  { value: "auto", label: "原图（默认）" },
  { value: "1:1", label: "1:1" },
  { value: "4:5", label: "4:5" },
  { value: "3:4", label: "3:4" },
  { value: "9:16", label: "9:16" },
  { value: "16:9", label: "16:9" },
];
const PLAN_TIMEOUT_MS = 120000;
const QUICK_VIDEO_THEME_OPTIONS = [
  { value: "product_highlight", label: "产品亮点快节奏" },
  { value: "lifestyle_story", label: "生活场景故事感" },
  { value: "before_after", label: "前后对比转化" },
];
const QUICK_VIDEO_PACE_OPTIONS = [
  { value: "fast", label: "快节奏（推荐）" },
  { value: "balanced", label: "中等节奏" },
  { value: "calm", label: "舒缓节奏" },
];
const QUICK_VIDEO_NARRATION_OPTIONS = [
  { value: "direct", label: "直接转化型" },
  { value: "friendly", label: "友好推荐型" },
  { value: "story", label: "故事讲述型" },
];
const QUICK_VIDEO_CTA_OPTIONS = [
  { value: "soft_sell", label: "轻引导（推荐）" },
  { value: "strong_sell", label: "强转化" },
  { value: "brand_follow", label: "品牌关注" },
];
const QUICK_VIDEO_TONE_BY_STYLE = {
  direct: "真实、克制、有钩子",
  friendly: "亲和、可信、具体",
  story: "故事化、场景化、节奏清晰",
};
const QUICK_VIDEO_CTA_TEXT_BY_STYLE = {
  soft_sell: "点击查看同款拍摄方案",
  strong_sell: "立即下单，马上体验",
  brand_follow: "关注我们，获取更多拍摄灵感",
};
const QUICK_VIDEO_THEME_FEATURES = {
  product_highlight: "核心卖点,真实反馈,快速转化钩子",
  lifestyle_story: "生活场景,真实体验,情绪共鸣",
  before_after: "前后对比,问题解决,结果展示",
};

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

const SHOWCASE_FALLBACK_IMAGES = {
  "main-1": "/static/showcase/main-1.jpg",
  "main-2": "/static/showcase/main-2.png",
  "scene-1": "/static/showcase/scene-1.jpg",
  "scene-2": "/static/showcase/scene-2.png",
  "model-1": "/static/showcase/model-1.jpg",
  "angle-1": "/static/showcase/angle-1.png",
};
const DEFAULT_IMAGE_FALLBACK = "/static/showcase/main-1.jpg";
const TOOL_IMAGE_FALLBACKS = {
  product_image_suite: "/static/showcase/main-1.jpg",
  model_retouch: "/static/showcase/model-1.jpg",
  multi_angle_camera: "/static/showcase/angle-1.png",
  intro_video_multi_script: "/static/showcase/scene-1.jpg",
  quick_video_15s: "/static/showcase/scene-2.png",
};

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

const HOT_SELLING_TRACKS = [
  {
    id: "hot-main",
    title: "主图四联包",
    reason: "近7天下单 38 次",
    ctaTool: "product-image",
  },
  {
    id: "hot-model",
    title: "模特精修十张包",
    reason: "近7天复购率 41%",
    ctaTool: "model-retouch",
  },
  {
    id: "hot-angle",
    title: "8角度展品包",
    reason: "详情页停留提升 26%",
    ctaTool: "multi-angle-camera",
  },
];

const USER_ROLE_LABEL = {
  admin: "管理员",
  operator: "运营",
  member: "成员",
};

const ACCOUNT_STATUS_LABEL = {
  active: "账号正常",
  trial: "试用中",
  suspended: "已限制",
  frozen: "已冻结",
};

const STATUS_LABEL = {
  queued: "排队中",
  running: "执行中",
  reviewing: "待审核",
  done: "已完成",
  failed: "失败",
  scripted: "方案已就绪",
  draft: "待生成方案",
  rendering: "生成中",
  completed: "已完成",
};

const ASSET_SOURCE_LABEL = {
  uploaded: "用户上传",
  generated: "AI生成",
};

const ASSET_KIND_LABEL = {
  input: "原始素材",
  plan_keyframe: "方案关键帧",
  generated_image: "图片结果",
  generated_video: "视频结果",
  selected_output: "已入选结果",
};

const ASSET_STATUS_LABEL = {
  pending: "待处理",
  ready: "已生成",
  reviewed: "已入选",
  rejected: "已淘汰",
  failed: "生成失败",
};

const LEDGER_KIND_LABEL = {
  recharge: "充值入账",
  consume_generation: "生成扣费",
  share_reward: "分享奖励",
  manual_adjust: "管理员调整",
};

const RECHARGE_STATUS_LABEL = {
  pending: "待确认",
  paid: "已到账",
  canceled: "已取消",
};

const QUALITY_LABEL = {
  standard: "标准",
  pro: "高级",
  premium: "高级",
  high: "高级",
};

const TASK_RISK_LABEL = {
  blocked: "卡住",
  pending: "待确认",
  running: "执行中",
  other: "普通",
};

const TASK_RISK_PRIORITY = {
  blocked: 0,
  pending: 1,
  running: 2,
  other: 3,
};

const RETOUCH_BATCH_LANES = [
  { key: "pending_confirm", label: "待确认", hint: "先完成身份确认" },
  { key: "executing", label: "执行中", hint: "等待结果回填" },
  { key: "review", label: "待审核", hint: "进入结果审核" },
  { key: "export", label: "可导出", hint: "可下载/交付" },
];

const TEMPLATE_LABEL = {
  general: "通用模板",
  compare: "对比测评",
  scene: "场景故事",
  tutorial: "教程清单",
};

const STAGE_LABEL = {
  master_script: "主脚本",
  plan: "拍摄方案",
  prompt: "执行方案",
  identity: "模特锚点确认",
  storyboard: "分镜",
  generate: "试拍/生成",
  render: "视频生成",
  review: "选片分享",
  completed: "已完成",
  failed: "失败",
};

const ICON_PATHS = {
  spark: ["M12 3l2.6 5.3L20 9l-4 4 .9 6L12 16l-4.9 3 .9-6-4-4 5.4-.7L12 3z"],
  camera: ["M3 7h4l2-2h6l2 2h4v12H3V7z", "M12 10a4 4 0 100 8 4 4 0 000-8z"],
  video: ["M3 7h11v10H3V7z", "M14 10l7-3v10l-7-3z"],
  gallery: ["M3 5h18v14H3V5z", "M7 13l3-3 4 4 2-2 4 4", "M8 9h.01"],
  user: ["M12 12a4 4 0 100-8 4 4 0 000 8z", "M4 21a8 8 0 0116 0"],
  cube: ["M3 7l9-4 9 4-9 4-9-4z", "M3 7v10l9 4 9-4V7", "M12 11v10"],
  task: ["M4 6h2v2H4z", "M8 7h12", "M4 11h2v2H4z", "M8 12h12", "M4 16h2v2H4z", "M8 17h12"],
  assets: ["M4 5h16v14H4V5z", "M8 9h8", "M8 13h8", "M8 17h6"],
  dashboard: ["M4 4h7v7H4z", "M13 4h7v4h-7z", "M13 10h7v10h-7z", "M4 13h7v7H4z"],
  wand: ["M3 21l6-6", "M14 4l6 6", "M12 2l2 2-8 8-2-2 8-8z"],
};

const TOOL_ICON_MAP = {
  "intro-video": "video",
  "product-image": "camera",
  "model-retouch": "user",
  "quick-video-15s": "video",
  "multi-angle-camera": "cube",
};

function Icon({ name, size = 18, className = "" }) {
  const paths = ICON_PATHS[name] || ICON_PATHS.spark;
  return (
    <svg
      className={cx("ui-icon", className)}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths.map((d, idx) => <path key={`${name}-${idx}`} d={d} />)}
    </svg>
  );
}

function toolIconName(toolOrSlug) {
  const slug = typeof toolOrSlug === "string" ? toolOrSlug : toolOrSlug?.slug;
  return TOOL_ICON_MAP[slug] || "spark";
}

function stageLabel(stage, toolSlug) {
  if (!stage) return "-";
  if (toolSlug === "multi-angle-camera" && stage === "plan") return "机位方案";
  if (toolSlug === "model-retouch" && stage === "plan") return "精修方案";
  return STAGE_LABEL[stage] || stage;
}

function resolveTaskRisk(task) {
  const status = String(task?.status || "").toLowerCase();
  const stage = String(task?.current_stage || "").toLowerCase();
  if (["failed", "error"].includes(status) || stage === "failed") return "blocked";
  if (status === "reviewing" || stage === "identity" || stage === "review") return "pending";
  if (["queued", "running", "rendering"].includes(status) || stage === "generate" || stage === "render") return "running";
  return "other";
}

function taskNextActionHint(task) {
  const risk = resolveTaskRisk(task);
  const stage = String(task?.current_stage || "").toLowerCase();
  const status = String(task?.status || "").toLowerCase();
  if (risk === "blocked") return "检查失败原因并点重试";
  if (risk === "pending") {
    if (stage === "identity") return "先确认模特锚点";
    if (stage === "review") return "先完成结果筛选";
    return "先完成当前确认步骤";
  }
  if (risk === "running") return "等待回填，可先处理其他任务";
  if (status === "done" || status === "completed") return "可导出或分享结果";
  if (stage === "plan" || stage === "master_script") return "先确认方案再继续";
  return "进入工作台继续";
}

function resolveTaskWorkspacePath(task) {
  const tool = TOOL_BY_TYPE[task?.tool_type];
  if (!tool) return "/app/tools";
  if (tool.slug === "model-retouch" && task?.batch_group_id) {
    return `/app/tools/model-retouch/batches/${task.batch_group_id}`;
  }
  if (task?.project_id) {
    return `/app/tools/${tool.slug}/projects/${task.project_id}`;
  }
  return `/app/tools/${tool.slug}/tasks`;
}

const DELIVERY_PURPOSE_BY_STAGE = {
  hook: "主图",
  feature: "场景图",
  proof: "细节图",
  cta: "对比图",
};

function resolveDeliveryPurpose(shot, scenarioType) {
  const raw = String(shot?.delivery_purpose || "").trim();
  if (raw) return raw;
  if (scenarioType === "product_image_suite") {
    return DELIVERY_PURPOSE_BY_STAGE[shot?.stage] || "场景图";
  }
  if (scenarioType === "model_retouch") {
    return "单图精修交付";
  }
  if (scenarioType === "multi_angle_camera") {
    return "角度展示图";
  }
  return "视频关键帧";
}

function templateLabel(value) {
  if (!value) return "-";
  return TEMPLATE_LABEL[value] || value;
}

function qualityLabel(value) {
  if (!value) return "-";
  return QUALITY_LABEL[value] || value;
}

function assetSourceLabel(value) {
  if (!value) return "未知来源";
  return ASSET_SOURCE_LABEL[value] || value;
}

function assetKindLabel(value) {
  if (!value) return "未知类型";
  return ASSET_KIND_LABEL[value] || value;
}

function assetStatusLabel(value) {
  if (!value) return "状态未知";
  return ASSET_STATUS_LABEL[value] || STATUS_LABEL[value] || value;
}

function candidateCaption(asset, productName = "") {
  const meta = asset?.metadata || {};
  const title = meta.shot_title || "";
  const intent = meta.shot_intent || "";
  if (meta.intent_summary) return meta.intent_summary;
  if (title && intent) return `${title}：${intent}`;
  if (intent) return intent;
  if (title) return title;
  return productName ? `${productName}亮点展示` : "电商卖点展示";
}

function ecommerceCaption(asset, productName = "") {
  const meta = asset?.metadata || {};
  const marketingCopy = String(meta.marketing_copy || "").trim();
  if (marketingCopy) return marketingCopy;
  const purpose = meta.delivery_purpose || "";
  const intent = meta.shot_intent || "";
  const title = meta.shot_title || "";
  const base = intent || title || productName || "核心卖点";
  if (String(purpose).includes("主图")) return `主图主打：${base}，突出${productName || "产品"}第一印象与点击转化。`;
  if (String(purpose).includes("场景")) return `场景表达：${base}，让用户快速代入真实使用体验。`;
  if (String(purpose).includes("细节")) return `细节卖点：${base}，放大材质和做工信息。`;
  if (String(purpose).includes("对比")) return `对比说明：${base}，帮助用户更快做决策。`;
  if (purpose) return `用途：${purpose}｜卖点：${base}`;
  return `卖点文案：${base}`;
}

function assetReviewBucket(asset) {
  const status = String(asset?.status || "").toLowerCase();
  if (["reviewed", "done", "approved"].includes(status)) return "approved";
  if (["failed", "error", "rejected"].includes(status)) return "failed";
  return "pending";
}

function cx(...items) {
  return items.filter(Boolean).join(" ");
}

function parseCsv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function safeSessionSet(key, value) {
  try {
    if (typeof window !== "undefined" && window.sessionStorage) {
      window.sessionStorage.setItem(key, value);
    }
  } catch (_) {
    // Ignore storage failures (privacy mode / quota / disabled storage)
  }
}

function safeSessionGet(key) {
  try {
    if (typeof window !== "undefined" && window.sessionStorage) {
      return window.sessionStorage.getItem(key);
    }
  } catch (_) {
    return null;
  }
  return null;
}

function safeSessionRemove(key) {
  try {
    if (typeof window !== "undefined" && window.sessionStorage) {
      window.sessionStorage.removeItem(key);
    }
  } catch (_) {
    // Ignore storage failures
  }
}

function safeCreateObjectURL(file) {
  try {
    if (file && typeof URL !== "undefined" && URL.createObjectURL) {
      return URL.createObjectURL(file);
    }
  } catch (_) {
    return "";
  }
  return "";
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: String(error?.message || error || "未知错误") };
  }

  componentDidCatch(error) {
    if (typeof console !== "undefined") {
      console.error("UIErrorBoundary", error);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-main">
          <section className="card">
            <h1>页面发生错误</h1>
            <div className="status-banner error">{this.state.message}</div>
            <div className="toolbar" style={{ marginTop: 10 }}>
              <button type="button" className="btn-primary" onClick={() => window.location.reload()}>刷新页面</button>
            </div>
          </section>
        </div>
      );
    }
    return this.props.children;
  }
}

async function compressImageFile(file, options = {}) {
  const {
    maxBytes = 2 * 1024 * 1024,
    maxDimension = 2048,
    outputType = "image/jpeg",
    startQuality = 0.9,
    minQuality = 0.55,
  } = options;
  if (!(file instanceof File) || !file.type.startsWith("image/")) return file;
  if (file.size <= maxBytes) return file;

  const srcUrl = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error("图片读取失败"));
      element.src = srcUrl;
    });

    const width = img.naturalWidth || img.width;
    const height = img.naturalHeight || img.height;
    if (!width || !height) return file;

    const scale = Math.min(1, maxDimension / Math.max(width, height));
    const targetWidth = Math.max(1, Math.round(width * scale));
    const targetHeight = Math.max(1, Math.round(height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(img, 0, 0, targetWidth, targetHeight);

    const fileBase = (file.name || "upload").replace(/\.[^.]+$/, "");
    let quality = startQuality;
    let blob = await new Promise((resolve) => canvas.toBlob(resolve, outputType, quality));
    while (blob && blob.size > maxBytes && quality > minQuality) {
      quality = Math.max(minQuality, quality - 0.08);
      blob = await new Promise((resolve) => canvas.toBlob(resolve, outputType, quality));
    }
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], `${fileBase}.jpg`, { type: outputType });
  } catch (_) {
    return file;
  } finally {
    URL.revokeObjectURL(srcUrl);
  }
}

async function buildSafeFormData(rawFormData) {
  const safe = new FormData();
  for (const [key, value] of rawFormData.entries()) {
    if (!(value instanceof File)) {
      safe.append(key, value);
      continue;
    }
    const optimized = await compressImageFile(value);
    safe.append(key, optimized);
  }
  return safe;
}

function buildFormDataWithoutFiles(rawFormData) {
  const safe = new FormData();
  for (const [key, value] of rawFormData.entries()) {
    if (value instanceof File) continue;
    safe.append(key, value);
  }
  return safe;
}

async function apiFetch(url, options = {}) {
  const resp = await fetch(url, { credentials: "include", ...options });
  const payload = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    if (resp.status === 413) {
      throw new Error("上传图片过大（413）。请压缩图片后重试。");
    }
    throw new Error(payload?.detail || payload?.msg || `请求失败 (${resp.status})`);
  }
  return payload;
}

async function signOssUpload({ projectId, filename, contentType, role }) {
  return apiFetch("/api/v1/oss/sign", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      filename,
      content_type: contentType || "",
      role,
    }),
  });
}

async function uploadToOss({ file, projectId, role }) {
  const sign = await signOssUpload({
    projectId,
    filename: file.name || "upload.png",
    contentType: file.type || "image/png",
    role,
  });
  const form = new FormData();
  form.append("key", sign.key);
  form.append("policy", sign.policy);
  form.append("OSSAccessKeyId", sign.access_id);
  form.append("signature", sign.signature);
  form.append("success_action_status", "200");
  form.append("file", file);
  const resp = await fetch(sign.upload_url, { method: "POST", body: form });
  if (!resp.ok) {
    throw new Error("OSS上传失败，请重试");
  }
  return { public_url: sign.public_url, key: sign.key };
}

function formatDate(value) {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString();
}

function formatProgressLabel(value) {
  const text = String(value || "").trim();
  if (!text) return "-";
  const parts = text.split("|").map((item) => item.trim()).filter(Boolean);
  if (parts.length >= 2) return parts[1];
  return text.replaceAll("_", " ");
}

function selectedFileSummary(files) {
  if (!files?.length) return "未选择文件";
  if (files.length === 1) return files[0];
  return `${files[0]} 等 ${files.length} 个文件`;
}

function createClientProjectId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `proj_${Date.now()}_${Math.random().toString(16).slice(2, 10)}`;
}

function localPathToMedia(path) {
  if (!path) return "";
  const normalized = String(path).replaceAll("\\", "/");
  if (normalized.startsWith("data/")) return `/media/${normalized.slice(5)}`;
  const idx = normalized.indexOf("/data/");
  if (idx >= 0) return `/media/${normalized.slice(idx + 6)}`;
  return "";
}

function applyImageFallback(event, fallbackSrc = "") {
  const fallback = fallbackSrc || DEFAULT_IMAGE_FALLBACK;
  if (!fallback) return;
  const target = event.currentTarget;
  if (target.dataset.fallbackApplied === "1") return;
  target.dataset.fallbackApplied = "1";
  target.src = fallback;
}

function fallbackImageForToolType(toolType) {
  return TOOL_IMAGE_FALLBACKS[String(toolType || "").toLowerCase()] || DEFAULT_IMAGE_FALLBACK;
}

function detectFrontendBuildTag() {
  if (typeof document === "undefined") return "";
  const forced = process.env.NEXT_PUBLIC_APP_VERSION;
  if (forced) return String(forced);
  const resources = typeof performance !== "undefined"
    ? performance.getEntriesByType("resource").map((entry) => String(entry.name || ""))
    : [];
  const scripts = Array.from(document.querySelectorAll("script[src]"))
    .map((node) => node.getAttribute("src") || "");
  const candidates = [...resources, ...scripts];
  const appChunk = candidates.find((src) => src.includes("/_next/static/chunks/app/page-"));
  if (!appChunk) return "";
  const match = appChunk.match(/page-([a-z0-9]+)\.js/i);
  return match?.[1]?.slice(0, 8) || "";
}

function parseRoute(pathname) {
  const normalized = (pathname.startsWith("/app") ? pathname.slice(4) : pathname).replace(/\/+$/, "") || "/";
  const parts = normalized.split("/").filter(Boolean);
  if (!parts.length) return { page: "tools" };
  if (parts[0] === "login") return { page: "login" };
  if (parts[0] === "register") return { page: "register" };
  if (parts[0] === "assets") return { page: "assets" };
  if (parts[0] === "billing") return { page: "billing" };
  if (parts[0] === "users") return { page: "users" };
  if (parts[0] === "tools" && parts.length === 1) return { page: "tools" };
  if (parts[0] === "tools" && parts.length === 3 && parts[2] === "tasks") {
    return { page: "tasks", toolSlug: parts[1] };
  }
  if (parts[0] === "tools" && parts.length >= 4 && parts[2] === "batches") {
    return { page: "batch", toolSlug: parts[1], batchGroupId: decodeURIComponent(parts[3]) };
  }
  if (parts[0] === "tools" && parts.length >= 4 && parts[2] === "projects") {
    return { page: "project", toolSlug: parts[1], projectId: decodeURIComponent(parts[3]) };
  }
  return { page: "tools" };
}

function breadcrumbs(route, projectName = "") {
  if (route.page === "login") return ["登录"];
  if (route.page === "register") return ["注册"];
  if (route.page === "tools") return ["首页", "工具箱"];
  if (route.page === "assets") return ["首页", "资产中台"];
  if (route.page === "billing") return ["首页", "积分中心"];
  if (route.page === "users") return ["首页", "用户管理"];
  const tool = TOOLS[route.toolSlug];
  if (route.page === "tasks") return ["首页", tool?.title || "工具", "任务中心"];
  if (route.page === "batch") return ["首页", tool?.title || "工具", "任务中心", route.batchGroupId || "批次"];
  if (route.page === "project") {
    return ["首页", tool?.title || "工具", "任务中心", projectName || route.projectId || "项目"];
  }
  return ["首页"];
}

function useRouterState() {
  const [pathname, setPathname] = useState("/app/login");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return () => undefined;
    const updatePath = () => setPathname(window.location.pathname || "/app/login");
    updatePath();
    setReady(true);
    const onPop = () => updatePath();
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((target) => {
    if (typeof window === "undefined") return;
    const url = target.startsWith("/app") ? target : `/app${target.startsWith("/") ? target : `/${target}`}`;
    window.history.pushState({}, "", url);
    setPathname(url);
  }, []);

  return { pathname, route: parseRoute(pathname), navigate, ready };
}

function LoginPage({ navigate, onLoginSuccess }) {
  const initialStatus = (() => {
    if (typeof window === "undefined") return { text: "请输入账号密码", type: "" };
    const params = new URLSearchParams(window.location.search || "");
    const error = params.get("error") || "";
    if (error === "invalid_credentials") return { text: "账号或密码错误，请重新输入。", type: "error" };
    if (error === "too_many_attempts") return { text: "登录请求过于频繁，请稍后重试。", type: "error" };
    if (error === "account_suspended") return { text: "账号已被限制登录，请联系管理员。", type: "error" };
    if (error === "auth_not_configured") return { text: "认证服务未配置，请联系管理员。", type: "error" };
    if (error === "auth_provider_error") return { text: "认证服务暂时不可用，请稍后重试。", type: "error" };
    return { text: "请输入账号密码", type: "" };
  })();
  const [status, setStatus] = useState(initialStatus);
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const rawUsername = String(formData.get("username") || "").trim();
    const normalized = !rawUsername.includes("@") && rawUsername.toLowerCase() === "admin"
      ? "admin@studioflow.local"
      : rawUsername;
    formData.set("username", normalized);
    setLoading(true);
    setStatus({ text: "登录中...", type: "" });
    try {
      await apiFetch("/api/v1/auth/login", { method: "POST", body: formData });
      setStatus({ text: "登录成功，正在跳转...", type: "success" });
      onLoginSuccess?.(rawUsername || "admin");
      navigate("/app/tools");
    } catch (error) {
      const message = String(error?.message || "");
      if (message.includes("账号或密码错误")) {
        setStatus({ text: "账号或密码错误，请重新输入。", type: "error" });
      } else if (message.includes("Unauthorized")) {
        setStatus({ text: "会话已失效，请重新登录。", type: "error" });
      } else if (message.includes("账号已被限制登录")) {
        setStatus({ text: "账号已被限制登录，请联系管理员。", type: "error" });
      } else if (message.includes("过于频繁") || message.includes("锁定")) {
        setStatus({ text: message, type: "error" });
      } else if (message.includes("认证服务")) {
        setStatus({ text: "认证服务暂时不可用，请稍后重试。", type: "error" });
      } else {
        setStatus({ text: message || "登录失败，请稍后重试。", type: "error" });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-glow auth-glow-left" />
      <div className="auth-glow auth-glow-right" />
      <section className="auth-stage">
        <aside className="auth-hero">
          <div className="auth-brand-pill"><Icon name="spark" size={14} />StudioFlow AI · Premium Studio</div>
          <h1>豪华影棚级 AI 内容中台</h1>
          <p className="auth-hero-subtitle">
            不是工具堆叠，而是一条完整的商业摄影动线。
            从脚本、拍摄方案到交付样片，统一留在你的品牌资产库。
          </p>
          <div className="auth-hero-copygrid">
            <article className="auth-copy-card">
              <span>主图套图</span>
              <strong>从 1 张参考图到一整套电商交付图</strong>
            </article>
            <article className="auth-copy-card">
              <span>模特精修</span>
              <strong>先锁身份锚点，再整批回填结果</strong>
            </article>
            <article className="auth-copy-card">
              <span>视频工作流</span>
              <strong>先脚本后生成，保留每一步可确认节点</strong>
            </article>
          </div>
          <div className="auth-visual-grid">
            <article className="auth-shot auth-shot-main">
              <img src="/static/login/hero-portrait.jpg" alt="影棚样片" />
              <div className="auth-shot-caption">品牌主视觉样片</div>
            </article>
            <article className="auth-shot auth-shot-small auth-shot-a">
              <img src="/static/login/hero-runway.png" alt="模特样片局部" />
              <div className="auth-shot-caption">模特质感精修</div>
            </article>
            <article className="auth-shot auth-shot-small auth-shot-b">
              <img src="/static/login/hero-editorial.png" alt="视频关键帧样片" />
              <div className="auth-shot-caption">短视频关键帧</div>
            </article>
          </div>
          <div className="auth-kpi-strip">
            <div><strong>5</strong><span>工具工坊</span></div>
            <div><strong>批量</strong><span>组图流程</span></div>
            <div><strong>资产</strong><span>统一沉淀</span></div>
          </div>
        </aside>
        <section className="card auth-panel">
          <div className="auth-panel-head">
            <div>
              <h2>登录 AI摄影棚</h2>
              <p className="auth-panel-subtitle">默认测试账号：admin / admin123</p>
            </div>
            <div className="auth-panel-badge">商业版工作台</div>
          </div>
          <form className="grid auth-form" onSubmit={submit} method="post" action="/app/login">
            <div className="field"><label>用户名</label><input name="username" defaultValue="admin" required /></div>
            <div className="field"><label>密码</label><input name="password" type="password" defaultValue="admin123" required /></div>
            <button type="submit" className="btn-primary auth-submit" disabled={loading}>{loading ? "登录中..." : "进入工作台"}</button>
          </form>
          <div className="auth-panel-note">登录后将直接进入工具箱，可从首页继续上次任务。</div>
          <div className="toolbar auth-secondary-actions">
            <button type="button" className="btn-secondary" onClick={() => navigate("/app/register")}>注册新账号</button>
          </div>
          <div className={cx("status-banner", status.type, "auth-status")}>{status.text}</div>
        </section>
      </section>
    </div>
  );
}

function RegisterPage({ navigate }) {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState({ text: "创建账号后可立即登录。", type: "" });

  const submit = async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const password = String(formData.get("password") || "");
    const confirm = String(formData.get("confirm_password") || "");
    if (password !== confirm) {
      setStatus({ text: "两次输入的密码不一致。", type: "error" });
      return;
    }
    const payload = {
      username: String(formData.get("username") || "").trim(),
      email: String(formData.get("email") || "").trim(),
      display_name: String(formData.get("display_name") || "").trim() || null,
      password,
      invite_code: String(formData.get("invite_code") || "").trim() || null,
    };
    setLoading(true);
    setStatus({ text: "注册中...", type: "" });
    try {
      await apiFetch("/api/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setStatus({ text: "注册成功，请登录。", type: "success" });
      setTimeout(() => navigate("/app/login"), 600);
    } catch (error) {
      setStatus({ text: String(error?.message || "注册失败，请稍后重试。"), type: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-main" style={{ maxWidth: 560, paddingTop: 70 }}>
      <section className="card">
        <h1>注册 AI摄影棚</h1>
        <p className="card-subtitle">注册后默认为试用账号，管理员可补充积分与权限。</p>
        <form className="grid" onSubmit={submit}>
          <div className="field"><label>用户名</label><input name="username" required placeholder="member01" /></div>
          <div className="field"><label>邮箱</label><input name="email" type="email" required placeholder="member@company.com" /></div>
          <div className="field"><label>显示名</label><input name="display_name" placeholder="运营同学A" /></div>
          <div className="field"><label>密码</label><input name="password" type="password" required minLength={8} /></div>
          <div className="field"><label>确认密码</label><input name="confirm_password" type="password" required minLength={8} /></div>
          <div className="field"><label>邀请码（可选）</label><input name="invite_code" placeholder="如有可填写" /></div>
          <button type="submit" className="btn-primary" disabled={loading}>{loading ? "注册中..." : "注册并创建账号"}</button>
        </form>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <button type="button" className="btn-secondary" onClick={() => navigate("/app/login")}>返回登录</button>
        </div>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
      </section>
    </div>
  );
}

function TopBar({ route, auth, navigate, onLogout }) {
  const [keyword, setKeyword] = useState("");
  const [buildTag, setBuildTag] = useState("");
  const workspaceLabel = auth.workspaceId
    ? auth.workspaceId === "default_workspace"
      ? "主工作区"
      : auth.workspaceId.replaceAll("_", " ")
    : "主工作区";
  const roleLabel = USER_ROLE_LABEL[auth.role] || "成员";
  const accountStatusLabel = ACCOUNT_STATUS_LABEL[auth.accountStatus] || "状态未知";
  const pointsLabel = Number(auth.pointsBalance || 0).toLocaleString();

  useEffect(() => {
    setBuildTag(detectFrontendBuildTag());
  }, []);

  const jump = async () => {
    if (!keyword.trim()) return;
    try {
      const rows = await apiFetch(`/api/v1/projects?limit=1&query=${encodeURIComponent(keyword.trim())}`);
      if (!rows.length) return;
      const tool = TOOL_BY_TYPE[rows[0].tool_type];
      if (!tool) return;
      if (tool.slug === "model-retouch" && rows[0].batch_group_id) {
        navigate(`/app/tools/model-retouch/batches/${rows[0].batch_group_id}`);
      } else {
        navigate(`/app/tools/${tool.slug}/projects/${rows[0].project_id}`);
      }
      setKeyword("");
    } catch (_) {
      // no-op
    }
  };

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="topbar-brand-block">
          <a className="brand" href="/app/tools" onClick={(event) => { event.preventDefault(); navigate("/app/tools"); }}>
            <Icon name="spark" size={16} />
            <span>AI摄影棚</span>
          </a>
          <div className="topbar-brand-copy">StudioFlow AI · 商业影棚工作台</div>
        </div>
        <nav className="nav-links">
          <a className={cx("nav-link", ["tools", "tasks", "project", "batch"].includes(route.page) && "active")} href="/app/tools" onClick={(event) => { event.preventDefault(); navigate("/app/tools"); }}><Icon name="dashboard" size={14} />工具箱</a>
          <a className={cx("nav-link", route.page === "assets" && "active")} href="/app/assets" onClick={(event) => { event.preventDefault(); navigate("/app/assets"); }}><Icon name="assets" size={14} />资产中台</a>
          <a className={cx("nav-link", route.page === "billing" && "active")} href="/app/billing" onClick={(event) => { event.preventDefault(); navigate("/app/billing"); }}><Icon name="spark" size={14} />积分中心</a>
          {auth.role === "admin" && (
            <a className={cx("nav-link", route.page === "users" && "active")} href="/app/users" onClick={(event) => { event.preventDefault(); navigate("/app/users"); }}><Icon name="task" size={14} />用户管理</a>
          )}
        </nav>
        <div className="topbar-right">
          <div className="topbar-quick-search">
            <input className="quick-jump" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索任务 / 项目ID" onKeyDown={(event) => event.key === "Enter" && jump()} />
            <button type="button" className="btn-secondary topbar-mini-btn" onClick={jump}>查找</button>
          </div>
          <div className="topbar-meta-stack">
            <span className="topbar-user-name">{auth.username || "未命名账号"} · {roleLabel}</span>
            <div className="topbar-meta">
              <span className="topbar-chip">{accountStatusLabel}</span>
              <span className="topbar-chip">{workspaceLabel}</span>
              <span className="topbar-chip topbar-chip-strong">积分 {pointsLabel}</span>
              {buildTag ? <span className="topbar-version">v{buildTag}</span> : null}
            </div>
          </div>
          <div className="topbar-actions">
            <button type="button" className="btn-ghost topbar-mini-btn" onClick={() => navigate("/app/tools")}>首页</button>
            <button type="button" className="btn-ghost topbar-mini-btn" onClick={onLogout}>退出</button>
          </div>
        </div>
      </div>
    </header>
  );
}

function AppSidebar({ route, navigate, auth }) {
  const activeTool = route.toolSlug || "";
  return (
    <aside className="app-sidebar">
      <div className="sidebar-card">
        <h3 className="title-row"><Icon name="dashboard" size={16} />工具箱</h3>
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
            资产中台
          </button>
          <button
            type="button"
            className={cx("sidebar-link", route.page === "billing" && "active")}
            onClick={() => navigate("/app/billing")}
          >
            积分中心
          </button>
          {auth.role === "admin" && (
            <button
              type="button"
              className={cx("sidebar-link", route.page === "users" && "active")}
              onClick={() => navigate("/app/users")}
            >
              用户管理
            </button>
          )}
        </div>
      </div>

      <div className="sidebar-card">
        <h4 className="title-row"><Icon name="gallery" size={16} />图片工具</h4>
        <div className="sidebar-links">
          {VISIBLE_TOOL_LIST.filter((item) => item.category === "image").map((item) => (
            <button
              key={item.slug}
              type="button"
              className={cx("sidebar-link", activeTool === item.slug && "active")}
              onClick={() => navigate(`/app/tools/${item.slug}/tasks`)}
            >
              <Icon name={toolIconName(item)} size={14} />{item.title}
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar-card">
        <h4 className="title-row"><Icon name="video" size={16} />视频工具</h4>
        <div className="sidebar-links">
          {VISIBLE_TOOL_LIST.filter((item) => item.category === "video").map((item) => (
            <button
              key={item.slug}
              type="button"
              className={cx("sidebar-link", activeTool === item.slug && "active")}
              onClick={() => navigate(`/app/tools/${item.slug}/tasks`)}
            >
              <Icon name={toolIconName(item)} size={14} />{item.title}
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
      const localImageUrl = asset ? localPathToMedia(asset.local_path) : "";
      const remoteImageUrl = asset?.image_url || "";
      return {
        ...preset,
        tool,
        imageUrl: localImageUrl || remoteImageUrl || fallbackImageUrl,
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
  const coreKpis = useMemo(() => ([
    { label: "进行中任务", value: kpi?.running_projects ?? 0, icon: "task" },
    { label: "今日完成", value: kpi?.done_projects ?? 0, icon: "spark" },
    { label: "样片已分享", value: kpi?.showcase_assets ?? 0, icon: "gallery" },
    { label: "可用素材", value: kpi?.total_assets ?? 0, icon: "assets" },
    { label: "分享积分", value: kpi?.share_points_earned ?? 0, icon: "spark" },
  ]), [kpi]);
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
      <section className="card home-hero-card">
        <div className="hero-banner hero-banner-luxe">
          <div className="hero-copy">
            <div className="hero-kicker"><Icon name="spark" size={14} />StudioFlow AI · 商业摄影工作台</div>
            <h1 className="title-row"><Icon name="spark" size={20} />把电商拍摄、样片、视频统一进一个品牌资产引擎</h1>
            <p className="card-subtitle">从商品棚拍、模特精修到 15 秒短片，先产出可审核内容，再沉淀成可复用的商业样片和资产模板。</p>
            <div className="toolbar hero-cta-row" style={{ marginTop: 10 }}>
              <button type="button" className="btn-primary" onClick={() => navigate("/app/tools/product-image/tasks")}>立即开拍</button>
              <button type="button" className="btn-secondary" onClick={() => navigate("/app/tools/intro-video/tasks")}>制作视频</button>
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
        {continueTask ? (
          <div className="home-continue-band">
            <div>
              <div className="home-continue-label">继续上次任务</div>
              <strong>{continueTask.product_name || "未命名任务"}</strong>
              <span> · {continueTool?.title || continueTask.tool_type} · {stageLabel(continueTask.current_stage, continueTool?.slug)}</span>
            </div>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => navigate(resolveTaskWorkspacePath(continueTask))}
            >
              回到工作台
            </button>
          </div>
        ) : null}
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        <div className="kpi-grid kpi-grid-compact home-kpi-grid" style={{ marginTop: 10 }}>
          {coreKpis.map((item) => (
            <div key={item.label} className="kpi-item">
              <div className="label title-row"><Icon name={item.icon} size={13} />{item.label}</div>
              <div className="value">{item.value}</div>
            </div>
          ))}
        </div>
        <div className="kpi-chip-row home-kpi-chip-row" style={{ marginTop: 8 }}>
          {secondaryKpis.map((item) => (
            <span key={item.label} className="kpi-chip">{item.label}：{item.value}</span>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="ops-banner">
          <div>
            <h2 className="title-row" style={{ marginBottom: 6 }}><Icon name="gallery" size={18} />摄影棚样片墙</h2>
            <p className="muted">这里仅展示“主动分享”的样片。你的原始素材与项目仍在“我的素材库”私有保存。</p>
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
        {!featuredShowcaseCard ? (
          <div className="empty-state premium-empty" style={{ marginTop: 10 }}>
            <div className="title-row"><Icon name="gallery" size={16} />暂未生成样片</div>
            <p className="muted">先去任一工具创建并筛选结果，再在“选片分享”步骤推送到样片墙。</p>
            <div className="toolbar" style={{ marginTop: 8 }}>
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

      <section className="card">
        <h2 className="title-row"><Icon name="gallery" size={18} />图片类工具</h2>
        <div className="tool-grid">
          {VISIBLE_TOOL_LIST.filter((tool) => tool.category === "image").map((tool) => (
            <article key={tool.slug} className="tool-card tool-card-featured">
              <div className="tool-card-kicker">{tool.category === "image" ? "Image Workflow" : "Video Workflow"}</div>
              <h3 className="title-row"><Icon name={toolIconName(tool)} size={16} />{tool.title}</h3>
              <p className="muted">{tool.subtitle}</p>
              <div className="tool-card-meta">
                <span className="badge">{tool.steps.length} 步流程</span>
                <span className="badge">{tool.category === "image" ? "图片交付" : "视频交付"}</span>
              </div>
              <button type="button" className="btn-primary" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>进入任务中心</button>
            </article>
          ))}
        </div>
      </section>

      <section className="card">
        <h2 className="title-row"><Icon name="video" size={18} />视频类工具</h2>
        <div className="tool-grid">
          {VISIBLE_TOOL_LIST.filter((tool) => tool.category === "video").map((tool) => (
            <article key={tool.slug} className="tool-card tool-card-featured">
              <div className="tool-card-kicker">{tool.category === "image" ? "Image Workflow" : "Video Workflow"}</div>
              <h3 className="title-row"><Icon name={toolIconName(tool)} size={16} />{tool.title}</h3>
              <p className="muted">{tool.subtitle}</p>
              <div className="tool-card-meta">
                <span className="badge">{tool.steps.length} 步流程</span>
                <span className="badge">{tool.category === "image" ? "图片交付" : "视频交付"}</span>
              </div>
              <button type="button" className="btn-primary" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>进入任务中心</button>
            </article>
          ))}
        </div>
      </section>

      <section className="card">
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

      <section className="card">
        <div className="ops-banner" style={{ marginBottom: 8 }}>
          <div>
            <h2 className="title-row" style={{ marginBottom: 6 }}><Icon name="task" size={18} />运营任务看板</h2>
            <p className="muted">仅显示最近 5 条任务，聚焦当前最需要跟进的项目。</p>
          </div>
          <span className="badge">共 {tasks.length} 条</span>
        </div>
        {!tasks.length ? (
          <div className="empty-state premium-empty">
            <div className="title-row"><Icon name="task" size={16} />暂无任务</div>
            <p className="muted">从左侧选择任一工坊创建任务，系统会把进度实时同步到看板。</p>
            <div className="toolbar" style={{ marginTop: 8 }}>
              <button type="button" className="btn-primary" onClick={() => navigate("/app/tools/product-image/tasks")}>创建首个任务</button>
              <button type="button" className="btn-secondary" onClick={() => navigate("/app/tools/intro-video/tasks")}>去视频工坊</button>
            </div>
          </div>
        ) : (
          <div className="asset-task-grid home-ops-grid">
            {visibleTasks.map((task) => {
              const tool = TOOL_BY_TYPE[task.tool_type];
              const taskPath = resolveTaskWorkspacePath(task);
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

function AssetsPage({ navigate }) {
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
    const running = tasks.filter((item) => item.status === "running" || item.status === "queued").length;
    const completed = tasks.filter((item) => item.status === "done" || item.status === "completed").length;
    const approvedAssets = assets.filter((item) => item.status === "reviewed" || item.status === "approved").length;
    return {
      running,
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
      <section className="card hub-hero-card asset-hub-hero-card">
        <div className="asset-hub-hero asset-hub-hero-luxe">
          <div className="asset-hub-copy">
            <div className="asset-hub-kicker"><Icon name="assets" size={14} />Asset Command Center</div>
            <h1 className="title-row"><Icon name="assets" size={20} />资产操作台</h1>
            <p className="card-subtitle">把任务、素材、样片放到同一张运营画布里，优先处理当前最该推进的内容，再把优质结果推向样片墙和复用模板。</p>
            <div className="toolbar asset-hub-cta-row">
              <button type="button" className="btn-primary" onClick={() => setActiveTab("tasks")}>进入任务流</button>
              <button type="button" className="btn-secondary" onClick={() => setActiveTab("library")}>查看素材库</button>
              <button type="button" className="btn-secondary" onClick={() => setActiveTab("showcase")}>运营样片墙</button>
            </div>
            <div className="asset-hub-kpis">
              <div className="asset-hub-kpi"><span>进行中</span><strong>{hubKpis.running}</strong></div>
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
                {assetHeroLead ? (
                  <img
                    src={assetHeroLead.image_url || localPathToMedia(assetHeroLead.local_path)}
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
                    <img
                      src={asset.image_url || localPathToMedia(asset.local_path)}
                      alt="样片缩略图"
                      onError={(event) => applyImageFallback(event, fallbackImageForToolType(asset.tool_type))}
                    />
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
            </div>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => navigate(resolveTaskWorkspacePath(continueTask))}
            >
              立即继续
            </button>
          </div>
        ) : null}
        <div className={cx("status-banner", status.type)}>{status.text}</div>
      </section>

      <section className="card asset-hub-card">
        <div className="asset-hub-head">
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
                        <strong>{taskNextActionHint(task)}</strong>
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
                const imageUrl = asset.image_url || localPathToMedia(asset.local_path);
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

function BillingPage({ navigate, auth, onAuthRefresh }) {
  const [summary, setSummary] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [orders, setOrders] = useState([]);
  const [status, setStatus] = useState({ text: "加载中...", type: "" });
  const [adjusting, setAdjusting] = useState(false);
  const adjustFormRef = useRef(null);
  const weeklyOverview = useMemo(() => {
    const now = new Date();
    const dayMap = new Map();
    for (let i = 6; i >= 0; i -= 1) {
      const d = new Date(now);
      d.setDate(now.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      dayMap.set(key, { key, label: `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`, income: 0, cost: 0 });
    }
    for (const item of ledger) {
      const dt = new Date(item.created_at || 0);
      if (Number.isNaN(dt.getTime())) continue;
      const key = dt.toISOString().slice(0, 10);
      if (!dayMap.has(key)) continue;
      const delta = Number(item.delta || 0);
      if (delta >= 0) dayMap.get(key).income += delta;
      else dayMap.get(key).cost += Math.abs(delta);
    }
    const days = Array.from(dayMap.values());
    const totalIncome = days.reduce((acc, cur) => acc + cur.income, 0);
    const totalCost = days.reduce((acc, cur) => acc + cur.cost, 0);
    const costDays = days.filter((item) => item.cost > 0).length;
    const averageDailyCost = costDays ? totalCost / costDays : 0;
    const balance = Number(summary?.balance ?? 0);
    const fallbackDays = averageDailyCost > 0 ? Math.floor(balance / averageDailyCost) : null;
    const availableDays = Number(summary?.available_days_estimate ?? fallbackDays ?? 0);
    return {
      days,
      totalIncome,
      totalCost,
      averageDailyCost,
      availableDays,
      balance,
    };
  }, [ledger, summary?.balance, summary?.available_days_estimate]);
  const businessInsights = useMemo(() => {
    const totalOutputCount = ledger
      .filter((item) => item.kind === "consume_generation")
      .reduce((acc, item) => acc + Math.max(0, Math.abs(Number(item.delta || 0))), 0);
    const rewardPoints = ledger
      .filter((item) => item.kind === "share_reward")
      .reduce((acc, item) => acc + Math.max(0, Number(item.delta || 0)), 0);
    const estimatedSavedHours = Number((totalOutputCount * 0.2).toFixed(1));
    const payoutRiskLevel = weeklyOverview.availableDays <= 3
      ? "高"
      : weeklyOverview.availableDays <= 7
        ? "中"
        : "低";
    return {
      totalOutputCount,
      rewardPoints,
      estimatedSavedHours,
      payoutRiskLevel,
    };
  }, [ledger, weeklyOverview.availableDays]);

  const load = useCallback(async () => {
    setStatus({ text: "加载积分数据...", type: "" });
    try {
      const [summaryRes, ledgerRes, rechargeRes] = await Promise.all([
        apiFetch("/api/v1/billing/me"),
        apiFetch("/api/v1/billing/ledger?limit=120"),
        apiFetch("/api/v1/billing/recharges?limit=120"),
      ]);
      setSummary(summaryRes);
      setLedger(Array.isArray(ledgerRes?.items) ? ledgerRes.items : []);
      setOrders(Array.isArray(rechargeRes?.items) ? rechargeRes.items : []);
      setStatus({ text: "积分数据已更新", type: "success" });
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const adjustPoints = async () => {
    if (!adjustFormRef.current) return;
    const fd = new FormData(adjustFormRef.current);
    const payload = {
      username: String(fd.get("username") || "").trim(),
      delta: Number(fd.get("delta") || 0),
      note: String(fd.get("note") || "").trim(),
    };
    setAdjusting(true);
    try {
      await apiFetch("/api/v1/billing/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setStatus({ text: "积分调整已生效。", type: "success" });
      await load();
      onAuthRefresh?.();
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    } finally {
      setAdjusting(false);
    }
  };

  return (
    <div className="content-stack">
      <section className="card">
        <h1 className="title-row"><Icon name="spark" size={18} />积分中心</h1>
        <p className="card-subtitle">查看余额与积分流水。当前阶段仅支持管理员手动调分，充值接口已预留。</p>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <span className="badge">当前用户：{auth.username || "-"}</span>
          <span className="badge">余额：{summary?.balance ?? 0}</span>
          <span className="badge">今日收入：{summary?.today_income ?? 0}</span>
          <span className="badge">今日消耗：{summary?.today_cost ?? 0}</span>
          <span className="badge">待确认充值：{summary?.pending_recharge_count ?? 0}</span>
          <button type="button" className="btn-secondary" onClick={load}>刷新</button>
          <button type="button" className="btn-ghost" onClick={() => navigate("/app/tools")}>返回工具箱</button>
        </div>
      </section>

      <section className="card">
        <h2 className="title-row"><Icon name="dashboard" size={16} />积分概览（优先）</h2>
        <div className="kpi-grid kpi-grid-compact" style={{ marginTop: 8 }}>
          <div className="kpi-item"><div className="label">当前余额</div><div className="value">{weeklyOverview.balance}</div></div>
          <div className="kpi-item"><div className="label">可用天数（估算）</div><div className="value">{weeklyOverview.availableDays || 0}</div></div>
          <div className="kpi-item"><div className="label">近7天收入</div><div className="value">{weeklyOverview.totalIncome}</div></div>
          <div className="kpi-item"><div className="label">近7天消耗</div><div className="value">{weeklyOverview.totalCost}</div></div>
        </div>
        <div className="kpi-chip-row" style={{ marginTop: 8 }}>
          {weeklyOverview.days.map((day) => (
            <span key={day.key} className="kpi-chip">{day.label} +{day.income} / -{day.cost}</span>
          ))}
        </div>
      </section>

      <section className="card">
        <h2 className="title-row"><Icon name="spark" size={16} />经营结论（近7天）</h2>
        <div className="business-insight-grid" style={{ marginTop: 8 }}>
          <article className="business-insight-card">
            <span className="muted">预计节省工时</span>
            <strong>{businessInsights.estimatedSavedHours} 小时</strong>
            <p className="muted">按单次产出替代人工 12 分钟估算，用于排班参考。</p>
          </article>
          <article className="business-insight-card">
            <span className="muted">素材产出规模</span>
            <strong>{businessInsights.totalOutputCount} 项</strong>
            <p className="muted">建议把高转化素材优先推到样片墙，提升复用率。</p>
          </article>
          <article className="business-insight-card">
            <span className="muted">分享激励回收</span>
            <strong>{businessInsights.rewardPoints} 分</strong>
            <p className="muted">当前余额风险等级：{businessInsights.payoutRiskLevel}，可据此安排补分节奏。</p>
          </article>
        </div>
        <p className="business-insight-note">经营建议：先控“每日消耗”再做“批量分享”，用样片奖励覆盖部分生成成本。</p>
      </section>

      <section className="card">
        <h2 className="title-row"><Icon name="task" size={16} />充值通道（预留）</h2>
        <p className="muted">在线支付接口将在后续版本接入。当前请使用管理员账号执行积分调整。</p>
      </section>

      {auth.role === "admin" && (
        <section className="card">
          <h2 className="title-row"><Icon name="task" size={16} />管理员积分调整</h2>
          <form ref={adjustFormRef} className="grid">
            <div className="field"><label>用户名</label><input name="username" placeholder="member01" /></div>
            <div className="field"><label>积分变更</label><input name="delta" type="number" defaultValue="100" /></div>
            <div className="field"><label>备注</label><input name="note" placeholder="运营活动补贴" /></div>
          </form>
          <div className="toolbar" style={{ marginTop: 8 }}>
            <button type="button" className="btn-primary" disabled={adjusting} onClick={adjustPoints}>{adjusting ? "调整中..." : "执行积分调整"}</button>
          </div>
        </section>
      )}

      <section className="card">
        <details className="details">
          <summary><span className="title-row"><Icon name="dashboard" size={16} />充值订单明细（{orders.length}）</span></summary>
          {!orders.length ? (
            <div className="empty-state" style={{ marginTop: 8 }}>充值通道未开放，暂无订单</div>
          ) : (
            <div className="task-table-wrap" style={{ marginTop: 8 }}>
              <table className="task-table">
                <thead>
                  <tr><th>订单ID</th><th>用户</th><th>积分</th><th>金额</th><th>状态</th><th>时间</th><th>操作</th></tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.order_id}>
                      <td>{order.order_id.slice(0, 8)}</td>
                      <td>{order.username}</td>
                      <td>{order.points}</td>
                      <td>¥{Number(order.amount_cny || 0).toFixed(2)}</td>
                      <td>{RECHARGE_STATUS_LABEL[order.status] || order.status}</td>
                      <td>{formatDate(order.created_at)}</td>
                      <td><span className="muted">预留</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </details>
      </section>

      <section className="card">
        <details className="details">
          <summary><span className="title-row"><Icon name="assets" size={16} />积分流水明细（{ledger.length}）</span></summary>
          {!ledger.length ? (
            <div className="empty-state" style={{ marginTop: 8 }}>暂无积分流水</div>
          ) : (
            <div className="task-table-wrap" style={{ marginTop: 8 }}>
              <table className="task-table">
                <thead>
                  <tr><th>时间</th><th>类型</th><th>变更</th><th>余额</th><th>备注</th><th>项目</th></tr>
                </thead>
                <tbody>
                  {ledger.map((item) => (
                    <tr key={item.ledger_id}>
                      <td>{formatDate(item.created_at)}</td>
                      <td>{LEDGER_KIND_LABEL[item.kind] || item.kind}</td>
                      <td>{item.delta > 0 ? `+${item.delta}` : item.delta}</td>
                      <td>{item.balance_after}</td>
                      <td>{item.note || "-"}</td>
                      <td>{item.project_id || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </details>
      </section>
    </div>
  );
}

function UsersPage({ auth }) {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState({ text: "加载中...", type: "" });
  const [userView, setUserView] = useState("abnormal");
  const createRef = useRef(null);

  const load = useCallback(async () => {
    setStatus({ text: "加载用户列表...", type: "" });
    try {
      const data = await apiFetch("/api/v1/users");
      setRows(Array.isArray(data?.items) ? data.items : []);
      setStatus({ text: `共 ${Array.isArray(data?.items) ? data.items.length : 0} 个用户`, type: "success" });
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    }
  }, []);

  useEffect(() => { if (auth.role === "admin") load(); }, [auth.role, load]);

  const abnormalRows = useMemo(
    () => rows.filter((row) => !row.is_active || ["suspended", "frozen"].includes(String(row.account_status || "").toLowerCase())),
    [rows],
  );
  const pendingRows = useMemo(
    () => rows.filter((row) => String(row.account_status || "").toLowerCase() === "trial" || Number(row.points_balance || 0) <= 0),
    [rows],
  );
  const visibleRows = useMemo(() => {
    if (userView === "abnormal") return abnormalRows;
    if (userView === "pending") return pendingRows;
    return rows;
  }, [userView, rows, abnormalRows, pendingRows]);

  const createUser = async () => {
    if (!createRef.current) return;
    const fd = new FormData(createRef.current);
    const payload = {
      username: String(fd.get("username") || "").trim(),
      password: String(fd.get("password") || "").trim(),
      email: String(fd.get("email") || "").trim() || null,
      display_name: String(fd.get("display_name") || "").trim() || null,
      workspace_id: String(fd.get("workspace_id") || "").trim() || null,
      role: String(fd.get("role") || "member"),
      account_status: String(fd.get("account_status") || "active"),
      is_active: String(fd.get("is_active") || "true") === "true",
      initial_points: Number(fd.get("initial_points") || 0),
    };
    try {
      await apiFetch("/api/v1/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setStatus({ text: "用户创建成功。", type: "success" });
      createRef.current.reset();
      await load();
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    }
  };

  const updateUser = async (row, next) => {
    try {
      await apiFetch(`/api/v1/users/${encodeURIComponent(row.username)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      });
      setStatus({ text: `用户 ${row.username} 已更新。`, type: "success" });
      await load();
    } catch (error) {
      setStatus({ text: error.message, type: "error" });
    }
  };

  if (auth.role !== "admin") {
    return (
      <div className="content-stack">
        <section className="card">
          <h1 className="title-row"><Icon name="task" size={18} />用户管理</h1>
          <div className="status-banner warning">仅管理员可访问该页面。</div>
        </section>
      </div>
    );
  }

  return (
    <div className="content-stack">
      <section className="card">
        <h1 className="title-row"><Icon name="task" size={18} />用户管理</h1>
        <p className="card-subtitle">管理后台账号、角色、启用状态和初始化积分。</p>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
      </section>

      <section className="card">
        <h2 className="title-row"><Icon name="spark" size={16} />创建用户</h2>
        <form ref={createRef} className="grid">
          <div className="field"><label>用户名</label><input name="username" placeholder="operator01" /></div>
          <div className="field"><label>密码</label><input name="password" type="password" placeholder="至少 6 位" /></div>
          <div className="field"><label>邮箱</label><input name="email" placeholder="operator@studioflow.local" /></div>
          <div className="field"><label>显示名</label><input name="display_name" placeholder="运营同学" /></div>
          <div className="field"><label>工作空间</label><input name="workspace_id" defaultValue="default_workspace" /></div>
          <div className="field"><label>角色</label><select name="role" defaultValue="member"><option value="member">member</option><option value="operator">operator</option><option value="admin">admin</option></select></div>
          <div className="field"><label>账号类型</label><select name="account_status" defaultValue="active"><option value="active">active</option><option value="trial">trial</option><option value="suspended">suspended</option><option value="frozen">frozen</option></select></div>
          <div className="field"><label>初始积分</label><input name="initial_points" type="number" min="0" defaultValue="0" /></div>
          <div className="field"><label>状态</label><select name="is_active" defaultValue="true"><option value="true">active</option><option value="false">disabled</option></select></div>
        </form>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <button type="button" className="btn-primary" onClick={createUser}>创建用户</button>
          <button type="button" className="btn-secondary" onClick={load}>刷新列表</button>
        </div>
      </section>

      <section className="card">
        <h2 className="title-row"><Icon name="dashboard" size={16} />账号列表</h2>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <button type="button" className={cx(userView === "abnormal" ? "btn-primary" : "btn-secondary")} onClick={() => setUserView("abnormal")}>异常账号（{abnormalRows.length}）</button>
          <button type="button" className={cx(userView === "pending" ? "btn-primary" : "btn-secondary")} onClick={() => setUserView("pending")}>待处理账号（{pendingRows.length}）</button>
          <button type="button" className={cx(userView === "all" ? "btn-primary" : "btn-secondary")} onClick={() => setUserView("all")}>全部账号（{rows.length}）</button>
        </div>
        {!visibleRows.length ? (
          <div className="empty-state">暂无用户</div>
        ) : (
          <div className="task-table-wrap">
            <table className="task-table">
              <thead>
                <tr><th>用户名</th><th>显示名</th><th>空间</th><th>角色</th><th>账号类型</th><th>积分</th><th>状态</th><th>最近登录</th><th>操作</th></tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <tr key={row.username}>
                    <td>{row.username}</td>
                    <td>{row.display_name}</td>
                    <td>{row.workspace_id || "-"}</td>
                    <td>{row.role}</td>
                    <td>{row.account_status || "-"}</td>
                    <td>{row.points_balance}</td>
                    <td>{row.is_active ? "active" : "disabled"}</td>
                    <td>{row.last_login_at ? formatDate(row.last_login_at) : "-"}</td>
                    <td>
                      <div className="toolbar">
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => {
                            const next = !row.is_active;
                            const ok = window.confirm(next ? `确认启用账号 ${row.username} 吗？` : `确认禁用账号 ${row.username} 吗？`);
                            if (ok) updateUser(row, { is_active: next });
                          }}
                        >
                          {row.is_active ? "禁用" : "启用"}
                        </button>
                        {row.role !== "admin" && (
                          <button
                            type="button"
                            className="btn-secondary"
                            onClick={() => {
                              const ok = window.confirm(`确认将 ${row.username} 设为运营角色吗？`);
                              if (ok) updateUser(row, { role: "operator" });
                            }}
                          >
                            设为运营
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function MultiAnglePad({ values, setValues, previewSrc }) {
  const mountRef = useRef(null);
  const runtimeRef = useRef(null);
  const [initError, setInitError] = useState("");

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
  const azimuthLabel = (yaw) => {
    const m = {
      0: "正面",
      45: "右前 45°",
      90: "右侧 90°",
      135: "右后 135°",
      180: "背面",
      225: "左后 225°",
      270: "左侧 270°",
      315: "左前 315°",
    };
    return m[yaw] || "正面";
  };
  const elevationLabel = (pitch) => {
    const m = {
      "-30": "低角度",
      "0": "平视",
      "30": "俯视",
      "60": "高俯视",
    };
    return m[String(pitch)] || "平视";
  };
  const distanceLabel = (distance) => {
    if (distance === "near") return "近景";
    if (distance === "far") return "远景";
    return "中景";
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
    setInitError("");
    let scene;
    let camera;
    let renderer;
    try {
      scene = new THREE.Scene();
      scene.background = new THREE.Color(0x12151f);
      camera = new THREE.PerspectiveCamera(50, mount.clientWidth / mount.clientHeight, 0.1, 100);
      camera.position.set(4.8, 3.2, 4.8);
      camera.lookAt(0, 0.8, 0);
      renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(mount.clientWidth, mount.clientHeight);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      mount.innerHTML = "";
      mount.appendChild(renderer.domElement);
    } catch (error) {
      setInitError(`3D预览不可用：${String(error?.message || "浏览器不支持 WebGL")}`);
      runtimeRef.current = null;
      return;
    }

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
    try {
      new THREE.TextureLoader().load(
        previewSrc,
        (texture) => {
          texture.minFilter = THREE.LinearFilter;
          texture.magFilter = THREE.LinearFilter;
          rt.targetPlaneMaterial.map = texture;
          rt.targetPlaneMaterial.needsUpdate = true;
        },
        undefined,
        () => {
          rt.targetPlaneMaterial.map = null;
          rt.targetPlaneMaterial.needsUpdate = true;
        }
      );
    } catch (_) {
      rt.targetPlaneMaterial.map = null;
      rt.targetPlaneMaterial.needsUpdate = true;
    }
  }, [previewSrc]);

  return (
    <div className="camera-pad-wrap">
      <div className="camera-panel-title">3D 机位控制</div>
      <div className="camera-viewport" ref={mountRef} />
      <div className="camera-hint">拖动绿色/粉色/黄色控制球或使用预设按钮，实时校准机位。</div>
      {initError && <div className="status-banner warning" style={{ marginTop: 8 }}>{initError}</div>}
      <div className="camera-token">
        当前机位：{azimuthLabel(toYaw360(values.camera_yaw))} · {elevationLabel(Math.max(-30, Math.min(60, Number(values.camera_pitch || 0))))} · {distanceLabel(values.camera_distance)} · {values.camera_focal_mm}mm
      </div>
      <div className="toolbar" style={{ marginTop: 8 }}>
        {[{ label: "正面", yaw: 0, pitch: 0 }, { label: "右侧45°", yaw: 45, pitch: 0 }, { label: "背面", yaw: 180, pitch: 0 }, { label: "低角度", yaw: toYaw360(values.camera_yaw), pitch: -30 }, { label: "高角度", yaw: toYaw360(values.camera_yaw), pitch: 60 }].map((item) => (
          <button key={item.label} type="button" className="btn-secondary" onClick={() => updateParent({ yaw360: item.yaw, pitch: item.pitch })}>{item.label}</button>
        ))}
      </div>
      <div className="grid camera-slider-grid" style={{ marginTop: 8 }}>
        <div className="field"><label>方位角 (0~315)</label><input type="range" min={0} max={315} step={45} value={toYaw360(values.camera_yaw)} onChange={(event) => updateParent({ yaw360: Number(event.target.value || 0) })} /></div>
        <div className="field"><label>俯仰角 (-30~60)</label><input type="range" min={-30} max={60} step={30} value={Math.max(-30, Math.min(60, Number(values.camera_pitch || 0)))} onChange={(event) => updateParent({ pitch: Number(event.target.value || 0) })} /></div>
        <div className="field"><label>距离</label><input type="range" min={0.6} max={1.4} step={0.1} value={toDistanceFactor(values.camera_distance)} onChange={(event) => updateParent({ distanceFactor: Number(event.target.value || 1) })} /></div>
        <div className="field"><label>焦段</label><select value={values.camera_focal_mm} onChange={(event) => setValues((prev) => ({ ...prev, camera_focal_mm: event.target.value }))}><option value="35">35mm</option><option value="50">50mm</option><option value="85">85mm</option></select></div>
      </div>
      <div className="status-banner" style={{ marginTop: 8 }}>
        方位 {toYaw360(values.camera_yaw)}° · 俯仰 {Math.max(-30, Math.min(60, Number(values.camera_pitch || 0)))}° · 距离 {distanceLabel(values.camera_distance)} · {values.camera_focal_mm}mm
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
  const mountedRef = useRef(true);
  const requestTokenRef = useRef(0);
  const buildDefaultFormValues = useCallback(
    (slug) => ({
      product_name: "",
      platform: slug === "quick-video-15s" ? "tiktok" : "douyin",
      template_name: "general",
      desired_duration_sec: slug === "quick-video-15s" ? 15 : 40,
      key_features: "核心卖点,真实反馈,使用场景",
      target_audience: "注重体验和性价比的人群",
      tone: "真实、克制、有钩子",
      evidence_points: "使用演示,连续反馈",
      channels: "douyin,tiktok",
      compliance_blocklist: "绝对最好,全网第一",
      scene_style: "商业棚拍+生活化场景",
      scene_goals: "主图精修,场景图,细节特写,对比图",
      target_final_count: 9,
      takes_per_shot: 3,
      retouch_targets: "动作自然,面部状态,肤质统一,服装褶皱,光线修正",
      fidelity_requirement: "保持身份一致，避免形变",
      background_policy: "keep_original",
      output_aspect_ratio: "original",
      retouch_strength: "light",
      creative_direction: "",
      identity_replace: true,
      camera_yaw: 0,
      camera_pitch: 0,
      camera_distance: "medium",
      camera_focal_mm: "50",
      camera_aspect_ratio: "1:1",
      quick_video_theme: "product_highlight",
      quick_video_pace: "fast",
      quick_video_narration_style: "direct",
      quick_video_cta_style: "soft_sell",
    }),
    []
  );
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
    const names = Array.from(event.target.files || []).map((file) => file.name);
    setSelectedFiles((prev) => ({ ...prev, [field]: names }));
    if (field === "image") {
      if (event.target.files?.[0]) {
        setPreviewSrc(safeCreateObjectURL(event.target.files[0]));
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
  const latestTaskPath = latestTask ? resolveTaskWorkspacePath(latestTask) : "";
  const taskRows = useMemo(() => {
    const sorted = [...tasks].sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime());
    if (tool.slug !== "model-retouch") return sorted;
    const grouped = {};
    for (const task of sorted) {
      const key = task.batch_group_id || task.project_id;
      if (!grouped[key]) {
        grouped[key] = { ...task, _batch_total: 1 };
      } else {
        grouped[key]._batch_total = (grouped[key]._batch_total || 1) + 1;
      }
    }
    return Object.values(grouped);
  }, [tasks, tool.slug]);
  const recentRows = useMemo(() => taskRows.slice(0, 3), [taskRows]);
  const priorityRows = useMemo(
    () => (
      taskRows
        .map((task) => ({ ...task, _risk: resolveTaskRisk(task) }))
        .filter((task) => task._risk !== "other")
        .sort((a, b) => {
          const riskDiff = TASK_RISK_PRIORITY[a._risk] - TASK_RISK_PRIORITY[b._risk];
          if (riskDiff !== 0) return riskDiff;
          return new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime();
        })
        .slice(0, 6)
    ),
    [taskRows],
  );
  const createScene = useMemo(() => {
    if (tool.slug === "product-image") {
      return {
        eyebrow: "Product Suite",
        title: "主图、场景图、细节图一次性规划",
        description: "适合电商上新、详情页改版和活动期集中出图。先定镜头，再批量试拍，再集中选片。",
        imageMain: "/static/showcase/main-1.jpg",
        imageSide: "/static/showcase/scene-1.jpg",
        bullets: ["主图套图", "场景故事", "细节特写"],
      };
    }
    if (tool.slug === "model-retouch") {
      return {
        eyebrow: "Model Retouch",
        title: "先锁模特身份，再批量回填整组精修结果",
        description: "适合服饰、人像和品牌拍摄补拍场景。先确认锚点，再用同一身份批量替换与精修。",
        imageMain: "/static/showcase/model-1.jpg",
        imageSide: "/static/login/hero-runway.png",
        bullets: ["身份锚点", "原图比例", "批量精修"],
      };
    }
    if (tool.slug === "multi-angle-camera") {
      return {
        eyebrow: "Multi-angle Camera",
        title: "围绕单一展品，逐角度生成展示图",
        description: "适合 3C、配件、潮玩和收藏品。创建后直接进入机位控制台，按当前视角生成单张角度图。",
        imageMain: "/static/showcase/angle-1.png",
        imageSide: "/static/showcase/main-2.jpg",
        bullets: ["360°拖动", "焦段控制", "单角度输出"],
      };
    }
    if (tool.slug === "quick-video-15s") {
      return {
        eyebrow: "Quick Video 15s",
        title: "15 秒节奏先行，适合短平快转化内容",
        description: "适合抖音、TikTok 和投流素材。先定主题、节奏、语气和结尾动作，再生成候选短片。",
        imageMain: "/static/showcase/scene-2.png",
        imageSide: "/static/login/hero-editorial.png",
        bullets: ["15 秒固定", "快节奏脚本", "3 个候选"],
      };
    }
    return {
      eyebrow: "Intro Video",
      title: "先讲什么、怎么讲，再生成讲解视频",
      description: "适合电商讲解、种草口播和产品教育内容。先确认主脚本，再进入执行方案和视频生成。",
      imageMain: "/static/showcase/scene-1.jpg",
      imageSide: "/static/login/hero-editorial.png",
      bullets: ["3 套脚本", "执行方案", "视频候选"],
    };
  }, [tool.slug]);

  const outcomePreview = useMemo(() => {
    if (tool.slug === "product-image") {
      const targetCount = Math.max(3, Math.min(30, Number(formValues.target_final_count || 9)));
      const takesPerShot = Math.max(1, Math.min(4, Number(formValues.takes_per_shot || 3)));
      const shotCount = Math.max(1, Math.ceil(targetCount / Math.max(1, takesPerShot)));
      return {
        summary: `系统将先生成 ${shotCount} 个镜头方案，再按每镜头 ${takesPerShot} 张候选试拍，目标交付 ${targetCount} 张成片。`,
        chips: [`镜头方案 ${shotCount}`, `候选 ${shotCount * takesPerShot} 张`, `目标成片 ${targetCount} 张`],
      };
    }
    if (tool.slug === "model-retouch") {
      const sourceCount = selectedFiles.images.length || Number(tasks.find((item) => item.batch_group_id)?.total_images || 0) || 0;
      const finalCount = sourceCount > 0 ? sourceCount : "按上传数量";
      return {
        summary: "创建后先确认一张可复用的模特锚点图，再并行替换整组套图里的模特。",
        chips: [`批量任务 ${finalCount}`, "默认保留原背景", "默认原图比例"],
      };
    }
    if (tool.slug === "multi-angle-camera") {
      return {
        summary: "创建后进入机位控制台，按当前视角逐张生成展品图。",
        chips: ["1次生成1个角度", "支持360°拖动", "支持远近/高低调整"],
      };
    }
    if (tool.slug === "quick-video-15s") {
      return {
        summary: "AI先规划 15 秒节奏与镜头，再并行生成候选短片。",
        chips: ["时长 15 秒", "默认 3 个候选", "先方案后生成"],
      };
    }
    return {
      summary: "先确认脚本和执行方案，再批量生成讲解视频候选。",
      chips: ["先脚本后生成", "默认 3 套脚本", `目标时长 ${Math.max(15, Number(formValues.desired_duration_sec || 40))} 秒`],
    };
  }, [tool.slug, formValues.target_final_count, formValues.takes_per_shot, formValues.desired_duration_sec, selectedFiles.images.length, tasks]);

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
      let useDirectUpload = false;
      let uploadedMain = null;
      let uploadedRefs = [];
      let uploadedStyleRefs = [];
      let uploadedIdentity = null;
      let uploadedBatch = [];
      let directUploadFallbackHint = "";
      try {
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
            useDirectUpload = true;
          }
          const styleFiles = raw.getAll("style_reference_images").filter((item) => item instanceof File && item.size > 0);
          if (styleFiles.length) {
            let done = 0;
            for (const file of styleFiles) {
              const result = await uploadToOss({ file, projectId: uploadProjectId, role: "style_reference" });
              uploadedStyleRefs.push(result.public_url);
              done += 1;
              setCreateStatus({ text: `执行中：风格参考已上传 ${done}/${styleFiles.length}`, type: "" });
            }
            useDirectUpload = true;
          }
          const identityFile = raw.get("identity_image");
          if (identityFile instanceof File && identityFile.size > 0) {
            setCreateStatus({ text: "提交中：上传替换模特图...", type: "" });
            const result = await uploadToOss({ file: identityFile, projectId: uploadProjectId, role: "identity" });
            uploadedIdentity = result.public_url;
            useDirectUpload = true;
          }
        } else {
          const mainFile = raw.get("image");
          if (mainFile instanceof File && mainFile.size > 0) {
            setCreateStatus({ text: "提交中：上传主图中（直传OSS）...", type: "" });
            const result = await uploadToOss({ file: mainFile, projectId: uploadProjectId, role: "source" });
            uploadedMain = { url: result.public_url, mime: mainFile.type || "image/png", suffix: getSuffix(mainFile.name) };
            useDirectUpload = true;
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
            useDirectUpload = true;
          }
          const styleFiles = raw.getAll("style_reference_images").filter((item) => item instanceof File && item.size > 0);
          if (styleFiles.length) {
            let done = 0;
            for (const file of styleFiles) {
              const result = await uploadToOss({ file, projectId: uploadProjectId, role: "style_reference" });
              uploadedStyleRefs.push(result.public_url);
              done += 1;
              setCreateStatus({ text: `执行中：风格参考已上传 ${done}/${styleFiles.length}`, type: "" });
            }
            useDirectUpload = true;
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error || "unknown");
        directUploadFallbackHint = `直传OSS失败，已自动切换服务器上传（${message}）`;
        useDirectUpload = false;
        uploadedMain = null;
        uploadedRefs = [];
        uploadedStyleRefs = [];
        uploadedIdentity = null;
        uploadedBatch = [];
        setCreateStatus({ text: `执行中：${directUploadFallbackHint}`, type: "warning" });
      }

      const fd = useDirectUpload ? buildFormDataWithoutFiles(raw) : await buildSafeFormData(raw);
      if (useDirectUpload) {
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
          text: directUploadFallbackHint
            ? `成功：${directUploadFallbackHint}；批次创建完成，共 ${result.created_count} 张，进入批量工作台。`
            : `成功：批次创建完成，共 ${result.created_count} 张，进入批量工作台。`,
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
            text: directUploadFallbackHint
              ? `成功：${directUploadFallbackHint}；创建成功，进入工作台后先设置机位，再生成当前角度（项目 ${projectId}）`
              : `成功：创建成功，进入工作台后先设置机位，再生成当前角度（项目 ${projectId}）`,
            type: "success",
          });
        } else {
          setCreateStatus({
            text: directUploadFallbackHint
              ? `成功：${directUploadFallbackHint}；创建成功，进入项目 ${projectId}`
              : `成功：创建成功，进入项目 ${projectId}`,
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
          <div className="status-banner" style={{ marginTop: 8 }}>
            最近任务：{latestTask.product_name || "未命名任务"} · {stageLabel(latestTask.current_stage, tool.slug)} · {STATUS_LABEL[latestTask.status] || latestTask.status}
            <button
              type="button"
              className="btn-secondary"
              style={{ marginLeft: 10 }}
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
                <label>B. 风格参考图</label>
                <div className="file-picker">
                  <input
                    key={`style-reference-images-${fileInputVersion.style_reference_images}`}
                    id={fileInputIds.style_reference_images}
                    className="file-input-hidden"
                    name="style_reference_images"
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={(event) => onFileChange("style_reference_images", event)}
                  />
                  <label className="btn-secondary" htmlFor={fileInputIds.style_reference_images}>选择多张</label>
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
                  <label>风格参考图（可多选）</label>
                  <div className="file-picker">
                    <input
                      key={`${tool.slug}-reference-${fileInputVersion.reference_images}`}
                      id={fileInputIds.reference_images}
                      className="file-input-hidden"
                      name="reference_images"
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={(event) => onFileChange("reference_images", event)}
                    />
                    <label className="btn-secondary" htmlFor={fileInputIds.reference_images}>选择多张</label>
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
          {tool.slug !== "quick-video-15s" ? (
            <div className="field"><label>模板</label><select name="template_name" value={formValues.template_name} onChange={(event) => setFormValues((prev) => ({ ...prev, template_name: event.target.value }))}>{templates.map((item) => <option key={item.template_name} value={item.template_name}>{item.display_name}</option>)}</select></div>
          ) : (
            <input name="template_name" type="hidden" value={formValues.template_name} readOnly />
          )}
          {tool.slug !== "multi-angle-camera" && tool.slug !== "quick-video-15s" ? (
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
              <input type="hidden" name="camera_yaw" value={0} readOnly />
              <input type="hidden" name="camera_pitch" value={0} readOnly />
              <input type="hidden" name="camera_distance" value="medium" readOnly />
              <input type="hidden" name="camera_focal_mm" value={formValues.camera_focal_mm} readOnly />
              <input type="hidden" name="camera_aspect_ratio" value={formValues.camera_aspect_ratio} readOnly />
            </>
          )}

          <div style={{ gridColumn: "1 / -1" }} className="toolbar">
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

      <section className="card">
        <div className="ops-banner">
          <div>
            <h2 className="title-row" style={{ marginBottom: 4 }}><Icon name="task" size={16} />任务优先队列</h2>
            <p className="muted">默认优先显示卡住/待确认/执行中任务，再显示最近 3 条任务。</p>
          </div>
          <div className="toolbar">
            <input placeholder="关键词搜索" value={query} onChange={(event) => setQuery(event.target.value)} style={{ width: 220 }} />
            <button type="button" className="btn-secondary" onClick={loadData}>搜索</button>
            <button type="button" className="btn-secondary" onClick={loadData}>刷新</button>
          </div>
        </div>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        {!taskRows.length ? (
          <div className="empty-state" style={{ marginTop: 10 }}>暂无任务</div>
        ) : (
          <>
            <div className="tool-grid" style={{ marginTop: 10 }}>
              <article className="tool-card">
                <h3 className="title-row"><Icon name="spark" size={15} />优先处理（最多 6 条）</h3>
                {!priorityRows.length ? (
                  <p className="muted">当前没有卡住、待确认或执行中的任务。</p>
                ) : (
                  <div className="asset-grid">
                    {priorityRows.map((task) => (
                      <article
                        key={`priority-${task.batch_group_id || task.project_id}`}
                        className="asset-card"
                        style={highlightBatch && task.batch_group_id === highlightBatch ? { background: "#fff8e8" } : undefined}
                      >
                        <div><strong>{task.batch_group_id ? `批次：${task.batch_group_id}` : task.product_name}</strong></div>
                        {task._batch_total ? <div className="muted">任务数：{task._batch_total}</div> : null}
                        <div className="muted">阶段：{stageLabel(task.current_stage, tool.slug)}</div>
                        <div className="muted">进度：{task.progress_percent}% · {task.progress_label || "-"}</div>
                        <div className="toolbar" style={{ marginTop: 8 }}>
                          <span className="badge">{TASK_RISK_LABEL[task._risk] || "普通"}</span>
                          <span className="badge">{STATUS_LABEL[task.status] || task.status}</span>
                          <button type="button" className="btn-secondary" onClick={() => navigate(resolveTaskWorkspacePath(task))}>打开</button>
                        </div>
                        <div className="muted" style={{ marginTop: 6 }}>下一步：{taskNextActionHint(task)}</div>
                      </article>
                    ))}
                  </div>
                )}
              </article>
              <article className="tool-card">
                <h3 className="title-row"><Icon name="gallery" size={15} />最近 3 条</h3>
                <div className="asset-grid">
                  {recentRows.map((task) => (
                    <article
                      key={`recent-${task.batch_group_id || task.project_id}`}
                      className="asset-card"
                      style={highlightBatch && task.batch_group_id === highlightBatch ? { background: "#fff8e8" } : undefined}
                    >
                      <div><strong>{task.batch_group_id ? `批次：${task.batch_group_id}` : task.product_name}</strong></div>
                      <div className="muted">{stageLabel(task.current_stage, tool.slug)} · {formatDate(task.updated_at)}</div>
                      <div className="toolbar" style={{ marginTop: 8 }}>
                        <span className="badge">{STATUS_LABEL[task.status] || task.status}</span>
                        <button type="button" className="btn-secondary" onClick={() => navigate(resolveTaskWorkspacePath(task))}>打开</button>
                      </div>
                      <div className="muted" style={{ marginTop: 6 }}>下一步：{taskNextActionHint(task)}</div>
                    </article>
                  ))}
                </div>
              </article>
            </div>

            <details className="details" style={{ marginTop: 10 }}>
              <summary><span className="title-row"><Icon name="task" size={15} />查看全部任务（{taskRows.length}）</span></summary>
              {tool.slug === "model-retouch" ? (
                <div className="retouch-wall" style={{ marginTop: 8 }}>
                  {taskRows.map((task) => (
                    <article
                      key={task.batch_group_id || task.project_id}
                      className="asset-card"
                      style={highlightBatch && task.batch_group_id === highlightBatch ? { background: "#fff8e8" } : undefined}
                    >
                      <div><strong>{task.batch_group_id ? `批次：${task.batch_group_id}` : task.product_name}</strong></div>
                      {task._batch_total ? <div className="muted">任务数：{task._batch_total}</div> : null}
                      <div className="muted">阶段：{stageLabel(task.current_stage, tool.slug)}</div>
                      <div className="muted">进度：{task.progress_percent}% · {task.progress_label || "-"}</div>
                      <div className="toolbar" style={{ marginTop: 8 }}>
                        <span className="badge">{STATUS_LABEL[task.status] || task.status}</span>
                        <button type="button" className="btn-secondary" onClick={() => navigate(resolveTaskWorkspacePath(task))}>
                          {task.batch_group_id ? "打开批量工作台" : "打开任务"}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="table-wrap" style={{ marginTop: 8 }}>
                  <table className="table">
                    <thead><tr><th>任务</th><th>阶段</th><th>进度</th><th>风险</th><th>下一步</th><th>状态</th><th>更新时间</th><th>操作</th></tr></thead>
                    <tbody>
                      {taskRows.map((task) => {
                        const risk = resolveTaskRisk(task);
                        return (
                          <tr key={task.project_id} style={highlightBatch && task.batch_group_id === highlightBatch ? { background: "#fff8e8" } : undefined}>
                            <td><strong>{task.product_name}</strong>{task.batch_group_id && <div className="muted">批次：{task.batch_group_id}</div>}</td>
                            <td>{stageLabel(task.current_stage, tool.slug)}</td>
                            <td>{task.progress_percent}%<div className="muted">{task.progress_label || "-"}</div></td>
                            <td><span className={cx("badge", risk === "blocked" && "warning")}>{TASK_RISK_LABEL[risk] || "普通"}</span></td>
                            <td className="muted">{taskNextActionHint(task)}</td>
                            <td><span className="badge">{STATUS_LABEL[task.status] || task.status}</span></td>
                            <td>{formatDate(task.updated_at)}</td>
                            <td><button type="button" className="btn-secondary" onClick={() => navigate(resolveTaskWorkspacePath(task))}>打开</button></td>
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

function ModelRetouchBatchWorkspace({ batchGroupId, navigate }) {
  const tool = TOOLS["model-retouch"];
  const [batch, setBatch] = useState(null);
  const [assetsByProject, setAssetsByProject] = useState({});
  const [status, setStatus] = useState({ text: "加载批次中...", type: "" });
  const [runningGenerate, setRunningGenerate] = useState(false);
  const [runningIdentity, setRunningIdentity] = useState(false);
  const [showNewIdentityForm, setShowNewIdentityForm] = useState(false);
  const [identityUploadFile, setIdentityUploadFile] = useState(null);
  const [identityUploadVersion, setIdentityUploadVersion] = useState(0);
  const [batchGenerateOptions, setBatchGenerateOptions] = useState({
    output_aspect_ratio: "original",
    image_resolution: "1K",
    image_output_format: "png",
  });
  const [step, setStep] = useState(0);
  const [identityDesign, setIdentityDesign] = useState({
    identity_source: "use_uploaded",
    identity_requirements: "",
    lighting_preset: "softbox_clean",
    framing_preset: "full_body",
    angle_preset: "front",
    preserve_pose: true,
  });
  const mountedRef = useRef(true);
  const pollingRef = useRef(null);

  const projects = batch?.projects || [];
  const controllerProjectId = batch?.controller_project_id || projects[0]?.project_id || "";
  const controllerAssets = assetsByProject[controllerProjectId] || [];
  const identityAssets = controllerAssets.filter((item) => Array.isArray(item.tags) && item.tags.includes("identity"));
  const uploadedIdentityAssets = identityAssets.filter((item) => item.source_type === "uploaded");
  const uploadedIdentityAsset = uploadedIdentityAssets[uploadedIdentityAssets.length - 1] || null;
  const confirmedIdentityAsset = identityAssets.find((item) => item.asset_id === batch?.identity_anchor_asset_id) || null;
  const identityConfirmed = batch?.identity_status === "confirmed";
  const hasUploadedIdentity = uploadedIdentityAssets.length > 0;
  const sourcePreviewProjects = projects.slice(0, 12);
  const identitySource = identityDesign.identity_source || "generate_new";
  const identityPrimaryLabel = identitySource === "use_uploaded"
    ? "使用上传模特图"
    : identitySource === "beautify_uploaded"
      ? "先精修这张模特照"
      : "生成新的模特照";
  const identityPrimaryDisabled = runningIdentity || ((identitySource === "use_uploaded" || identitySource === "beautify_uploaded") && !hasUploadedIdentity);

  const load = useCallback(async () => {
    try {
      const summary = await apiFetch(`/api/v1/tools/model_retouch/batches/${batchGroupId}`);
      if (!mountedRef.current) return;
      setBatch(summary);
      const controllerProject = (summary.projects || []).find((item) => item.project_id === summary.controller_project_id)
        || summary.projects?.[0];
      if (controllerProject) {
        const controllerAspect = String(controllerProject.output_aspect_ratio || "original").toLowerCase();
        setBatchGenerateOptions((prev) => ({
          ...prev,
          output_aspect_ratio: controllerAspect === "auto" ? "original" : controllerAspect,
        }));
      }
      const entries = await Promise.all(
        (summary.projects || []).map(async (item) => {
          try {
            const rows = await apiFetch(`/api/v1/projects/${item.project_id}/assets`);
            return [item.project_id, rows];
          } catch (_) {
            return [item.project_id, []];
          }
        }),
      );
      if (!mountedRef.current) return;
      setAssetsByProject(Object.fromEntries(entries));
      setStatus({
        text: `批次 ${batchGroupId} ｜ 总数 ${summary.total_images} · 运行 ${summary.running_images} · 完成 ${summary.done_images} · 失败 ${summary.failed_images}`,
        type: summary.failed_images > 0 ? "warning" : "success",
      });
    } catch (error) {
      if (!mountedRef.current) return;
      setStatus({ text: `加载失败：${error.message}`, type: "error" });
    }
  }, [batchGroupId]);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => {
      mountedRef.current = false;
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [load]);

  useEffect(() => {
    if (!batch) return;
    if (batch.identity_status !== "confirmed") setStep(1);
    else if ((batch.done_images + batch.failed_images) < batch.total_images) setStep(2);
    else setStep(3);
  }, [batch?.identity_status, batch?.done_images, batch?.failed_images, batch?.total_images]);

  useEffect(() => {
    const shouldPoll = runningGenerate || (batch && (batch.running_images > 0 || batch.queued_images > 0));
    if (!shouldPoll) {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }
    if (!pollingRef.current) {
      pollingRef.current = setInterval(async () => {
        await load();
      }, 5000);
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [runningGenerate, batch?.running_images, batch?.queued_images, load, batch]);

  const generateIdentityCandidate = useCallback(async (force = false, modeOverride = null) => {
    const designPayload = {
      ...identityDesign,
      identity_source: modeOverride || identityDesign.identity_source,
    };
    try {
      setRunningIdentity(true);
      setStatus({
        text:
          designPayload.identity_source === "use_uploaded"
            ? "正在切换为上传模特图..."
            : "身份候选生成中...",
        type: "",
      });
      const payload = await apiFetch(`/api/v1/tools/model_retouch/batches/${batchGroupId}/identity/generate-candidate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...designPayload, force }),
      });
      if (!mountedRef.current) return;
      setBatch(payload);
      setIdentityDesign((prev) => ({ ...prev, identity_source: designPayload.identity_source }));
      await load();
      setStatus({
        text:
          designPayload.identity_source === "use_uploaded"
            ? "已切换为上传模特图，请确认锚点。"
            : "身份候选已更新，请确认锚点。",
        type: "success",
      });
    } catch (error) {
      if (!mountedRef.current) return;
      setStatus({ text: `身份候选生成失败：${error.message}`, type: "error" });
    } finally {
      if (mountedRef.current) setRunningIdentity(false);
    }
  }, [batchGroupId, identityDesign, load]);

  const uploadIdentity = useCallback(async () => {
    if (!identityUploadFile) {
      setStatus({ text: "请先选择要替换的模特图。", type: "warning" });
      return;
    }
    if (!controllerProjectId) {
      setStatus({ text: "控制项目未就绪，请刷新后重试。", type: "error" });
      return;
    }
    try {
      setRunningIdentity(true);
      setStatus({ text: "上传替换模特图中...", type: "" });
      const uploaded = await uploadToOss({
        file: identityUploadFile,
        projectId: controllerProjectId,
        role: "identity",
      });
      const payload = await apiFetch(`/api/v1/tools/model_retouch/batches/${batchGroupId}/identity/upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_public_url: uploaded.public_url,
          image_mime: identityUploadFile.type || "image/png",
        }),
      });
      if (!mountedRef.current) return;
      setBatch(payload);
      setIdentityUploadFile(null);
      setIdentityUploadVersion((prev) => prev + 1);
      setIdentityDesign((prev) => ({ ...prev, identity_source: "use_uploaded" }));
      await load();
      setStatus({ text: "替换模特图已更新，请确认锚点。", type: "success" });
    } catch (error) {
      if (!mountedRef.current) return;
      setStatus({ text: `上传替换模特图失败：${error.message}`, type: "error" });
    } finally {
      if (mountedRef.current) setRunningIdentity(false);
    }
  }, [batchGroupId, controllerProjectId, identityUploadFile, load]);

  const clearUploadedIdentity = useCallback(async () => {
    if (!uploadedIdentityAsset) {
      setStatus({ text: "当前没有可移除的上传模特图。", type: "warning" });
      return;
    }
    try {
      setRunningIdentity(true);
      setStatus({ text: "移除上传模特图中...", type: "" });
      const payload = await apiFetch(`/api/v1/tools/model_retouch/batches/${batchGroupId}/identity/clear-uploaded`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: uploadedIdentityAsset.asset_id }),
      });
      if (!mountedRef.current) return;
      setBatch(payload);
      setIdentityUploadFile(null);
      setIdentityUploadVersion((prev) => prev + 1);
      setIdentityDesign((prev) => ({ ...prev, identity_source: "generate_new" }));
      await load();
      setStatus({ text: "已移除上传模特图，可重新上传或直接生成新模特。", type: "success" });
    } catch (error) {
      if (!mountedRef.current) return;
      setStatus({ text: `移除失败：${error.message}`, type: "error" });
    } finally {
      if (mountedRef.current) setRunningIdentity(false);
    }
  }, [batchGroupId, uploadedIdentityAsset, load]);

  const confirmIdentity = useCallback(async (assetId) => {
    try {
      setRunningIdentity(true);
      setStatus({ text: "确认身份锚点中...", type: "" });
      const payload = await apiFetch(`/api/v1/tools/model_retouch/batches/${batchGroupId}/identity/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: assetId }),
      });
      if (!mountedRef.current) return;
      setBatch(payload);
      await load();
      setStatus({ text: "身份锚点已确认，下一步可开始批量精修。", type: "success" });
    } catch (error) {
      if (!mountedRef.current) return;
      setStatus({ text: `身份确认失败：${error.message}`, type: "error" });
    } finally {
      if (mountedRef.current) setRunningIdentity(false);
    }
  }, [batchGroupId, load]);

  const startBatchGenerate = useCallback(async () => {
    try {
      setRunningGenerate(true);
      setStatus({ text: "批量精修任务已提交，结果将逐张回填...", type: "" });
      const payloadBody = {
        async_mode: true,
        output_aspect_ratio: batchGenerateOptions.output_aspect_ratio || "original",
        image_output_format: batchGenerateOptions.image_output_format || "png",
      };
      if ((batchGenerateOptions.output_aspect_ratio || "original") !== "original") {
        payloadBody.image_resolution = batchGenerateOptions.image_resolution || "1K";
      }
      const payload = await apiFetch(`/api/v1/tools/model_retouch/batches/${batchGroupId}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payloadBody),
      });
      if (!mountedRef.current) return;
      setBatch(payload);
      await load();
    } catch (error) {
      if (!mountedRef.current) return;
      setStatus({ text: `批量精修失败：${error.message}`, type: "error" });
      setRunningGenerate(false);
    }
  }, [batchGroupId, batchGenerateOptions, load]);

  const retryFailed = useCallback(async () => {
    try {
      setStatus({ text: "正在重试失败任务...", type: "" });
      const payload = await apiFetch(`/api/v1/tools/model_retouch/batches/${batchGroupId}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!mountedRef.current) return;
      setBatch(payload);
      await load();
      setRunningGenerate(true);
      setStatus({ text: "失败任务已重试。", type: "success" });
    } catch (error) {
      if (!mountedRef.current) return;
      setStatus({ text: `重试失败：${error.message}`, type: "error" });
    }
  }, [batchGroupId, load]);

  const downloadBatchArchive = useCallback((scope) => {
    const safeScope = ["generated", "approved", "shared"].includes(scope) ? scope : "approved";
    window.location.href = `/api/v1/tools/model_retouch/batches/${batchGroupId}/download-images?scope=${safeScope}`;
  }, [batchGroupId]);

  const retrySingleProject = useCallback(async (projectId) => {
    if (!projectId) return;
    try {
      setStatus({ text: `正在重试任务 ${projectId.slice(0, 8)}...`, type: "" });
      const payload = await apiFetch(`/api/v1/tools/model_retouch/batches/${batchGroupId}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_ids: [projectId] }),
      });
      if (!mountedRef.current) return;
      setBatch(payload);
      await load();
      setRunningGenerate(true);
      setStatus({ text: `任务 ${projectId.slice(0, 8)} 已提交重试。`, type: "success" });
    } catch (error) {
      if (!mountedRef.current) return;
      setStatus({ text: `单任务重试失败：${error.message}`, type: "error" });
    }
  }, [batchGroupId, load]);

  useEffect(() => {
    if (!batch) return;
    if (runningGenerate && batch.running_images === 0 && batch.queued_images === 0) {
      setRunningGenerate(false);
      setStatus({ text: "批量精修执行完成。", type: batch.failed_images > 0 ? "warning" : "success" });
    }
  }, [batch?.running_images, batch?.queued_images, batch?.failed_images, runningGenerate, batch]);

  const allGeneratedAssets = useMemo(() => (
    Object.entries(assetsByProject).flatMap(([pid, rows]) => (
      (rows || [])
        .filter((item) => item.source_type === "generated" && item.kind === "generated_image")
        .map((item) => ({ ...item, __projectId: pid }))
    ))
  ), [assetsByProject]);
  const approvedGeneratedAssets = useMemo(() => (
    allGeneratedAssets.filter((asset) => assetReviewBucket(asset) === "approved")
  ), [allGeneratedAssets]);
  const projectLaneCards = useMemo(() => {
    return projects.map((item) => {
      const rows = assetsByProject[item.project_id] || [];
      const generated = rows.filter((asset) => asset.source_type === "generated" && asset.kind === "generated_image");
      const approvedCount = generated.filter((asset) => assetReviewBucket(asset) === "approved").length;
      const pendingCount = generated.filter((asset) => assetReviewBucket(asset) === "pending").length;
      const failedCount = generated.filter((asset) => assetReviewBucket(asset) === "failed").length;
      const taskStatus = String(item.task_status || "").toLowerCase();
      const isTaskFailed = ["failed", "error"].includes(taskStatus);
      const isTaskRunning = ["queued", "running", "rendering"].includes(taskStatus);
      const preview = (generated[generated.length - 1]?.image_url || localPathToMedia(generated[generated.length - 1]?.local_path))
        || item.image_public_url
        || localPathToMedia(item.image_path);
      const latestUpdatedAt = generated[generated.length - 1]?.updated_at || item.updated_at || item.created_at;
      const staleMs = latestUpdatedAt ? (Date.now() - new Date(latestUpdatedAt).getTime()) : 0;
      const noResult = generated.length === 0;
      let lane = "review";
      if (batch?.identity_status !== "confirmed") lane = "pending_confirm";
      else if (isTaskRunning) lane = "executing";
      else if (isTaskFailed || noResult) lane = "review";
      else if (pendingCount > 0 || failedCount > 0) lane = "review";
      else lane = "export";
      return {
        ...item,
        preview,
        generatedCount: generated.length,
        approvedCount,
        pendingCount,
        failedCount,
        noResult,
        isTaskFailed,
        isTaskRunning,
        staleExecution: lane === "executing" && staleMs > 180000,
        lane,
      };
    });
  }, [projects, assetsByProject, batch?.identity_status]);
  const laneColumns = useMemo(() => {
    const map = Object.fromEntries(RETOUCH_BATCH_LANES.map((lane) => [lane.key, []]));
    for (const item of projectLaneCards) {
      if (!map[item.lane]) map[item.lane] = [];
      map[item.lane].push(item);
    }
    return map;
  }, [projectLaneCards]);
  const batchProgressText = useMemo(() => {
    const total = Number(batch?.total_images || 0);
    const done = Number(batch?.done_images || 0);
    const failed = Number(batch?.failed_images || 0);
    const running = Number(batch?.running_images || 0);
    const queued = Number(batch?.queued_images || 0);
    if (!total) return "等待批次初始化";
    if (running > 0 || queued > 0) {
      const currentIndex = Math.min(total, done + failed + 1);
      return `正在处理第 ${currentIndex}/${total} 张 · 已完成 ${done} 张 · 异常 ${failed} 张`;
    }
    if (done > 0 || failed > 0) {
      return `本轮已完成 ${done}/${total} 张 · 异常 ${failed} 张`;
    }
    return `准备开始处理 ${total} 张套图`;
  }, [batch?.total_images, batch?.done_images, batch?.failed_images, batch?.running_images, batch?.queued_images]);

  const reviewAsset = useCallback(async (projectId, assetId, action) => {
    try {
      await apiFetch(`/api/v1/projects/${projectId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: assetId, action }),
      });
      await load();
      setStatus({ text: action === "approve" ? "已通过该结果。" : "已驳回该结果。", type: "success" });
    } catch (error) {
      setStatus({ text: `审核失败：${error.message}`, type: "error" });
    }
  }, [load]);

  useEffect(() => {
    if (identityDesign.identity_source === "use_uploaded" && !hasUploadedIdentity) {
      setIdentityDesign((prev) => ({ ...prev, identity_source: "generate_new" }));
    }
  }, [hasUploadedIdentity, identityDesign.identity_source]);

  useEffect(() => {
    if (hasUploadedIdentity && identityDesign.identity_source === "generate_new" && identityAssets.every((item) => item.source_type === "uploaded")) {
      setIdentityDesign((prev) => ({ ...prev, identity_source: "use_uploaded" }));
    }
  }, [hasUploadedIdentity, identityDesign.identity_source, identityAssets]);

  const autoPolling = runningGenerate || Boolean(batch && (batch.running_images > 0 || batch.queued_images > 0));

  return (
    <div className="content-stack">
      <section className="card workflow-top-card">
        <div className="workflow-top-head">
          <div>
            <h1 className="title-row"><Icon name={toolIconName(tool)} size={20} />{tool.title} · 批量工作台</h1>
            <div className="muted">批次：{batchGroupId}</div>
          </div>
          <div className="toolbar">
            <button type="button" className="btn-secondary" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>返回任务中心</button>
            <button type="button" className="btn-ghost" onClick={() => navigate("/app/tools")}>返回工具箱</button>
          </div>
        </div>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        <div className="step-rail top-step-rail" style={{ marginTop: 10 }}>
          {tool.steps.map((label, idx) => (
            <button
              key={label}
              type="button"
              className={cx("step-chip", idx === step && "active")}
              onClick={() => setStep(idx)}
            >
              {idx + 1}. {label}
            </button>
          ))}
        </div>
      </section>

      {step === 0 && (
        <section className="card workflow-panel">
          <div className="workflow-panel-head">
            <div className="step-kicker">STEP 1</div>
            <h2 className="title-row"><Icon name="gallery" size={18} />素材确认</h2>
          </div>
          <div className="status-banner">已载入 {projects.length} 张主素材。确认后进入身份确认。</div>
          <div className="asset-grid" style={{ marginTop: 10 }}>
            {projects.map((item) => {
              const source = item.image_public_url || localPathToMedia(item.image_path);
              return (
                <article key={item.project_id} className="asset-card">
                  {source ? <img src={source} alt="source" loading="lazy" decoding="async" /> : <div className="empty-state">无素材</div>}
                  <div className="muted" style={{ marginTop: 6 }}>{item.brief?.product_name || item.project_id}</div>
                </article>
              );
            })}
          </div>
          <div className="toolbar" style={{ marginTop: 10 }}>
            <button type="button" className="btn-primary" onClick={() => setStep(1)}>进入模特锚点确认</button>
          </div>
        </section>
      )}

      {step === 1 && (
        <section className="card workflow-panel">
          <div className="workflow-panel-head">
            <div className="step-kicker">STEP 2</div>
            <h2 className="title-row"><Icon name="user" size={18} />模特锚点确认台</h2>
          </div>
          <div className="status-banner">先确认一张可复用的模特锚点图，再批量替换整组套图中的模特。默认推荐上传全身标准照式模特图，便于稳定锁定脸、发型、肩线、腰线和腿部比例，避免后续替换时模型自行补全身体。</div>
          <div className="review-summary-grid" style={{ marginTop: 10 }}>
            <div className="review-summary-card">
              <span className="muted">阶段 1</span>
              <strong>先定模特本人</strong>
            </div>
            <div className="review-summary-card">
              <span className="muted">推荐输入</span>
              <strong>全身标准照</strong>
            </div>
            <div className="review-summary-card">
              <span className="muted">默认约束</span>
              <strong>保留原图动作</strong>
            </div>
            <div className="review-summary-card">
              <span className="muted">阶段 2</span>
              <strong>再替换整组套图</strong>
            </div>
          </div>
          <div className="identity-workbench" style={{ marginTop: 10 }}>
            <div className="identity-panel">
              <div className="identity-panel-head">
                <h3 className="title-row"><Icon name="gallery" size={16} />主素材预览</h3>
                <span className="badge">{sourcePreviewProjects.length} 张</span>
              </div>
              <div className="asset-grid">
                {sourcePreviewProjects.map((item) => {
                  const source = item.image_public_url || localPathToMedia(item.image_path);
                  return (
                    <article key={`retouch-source-${item.project_id}`} className="asset-card">
                      {source ? <img src={source} alt="retouch-source" /> : <div className="empty-state">无素材</div>}
                    </article>
                  );
                })}
              </div>
            </div>

            <div className="identity-panel">
              <div className="identity-panel-head">
                <h3 className="title-row"><Icon name="user" size={16} />模特锚点来源</h3>
                <span className="muted">建议全身标准照 / 可替换 / 可移除</span>
              </div>
              {uploadedIdentityAsset ? (
                <div className="asset-grid">
                  <article className="asset-card">
                    <img src={uploadedIdentityAsset.image_url || localPathToMedia(uploadedIdentityAsset.local_path)} alt="uploaded-identity" loading="lazy" decoding="async" />
                    <div className="toolbar" style={{ marginTop: 8 }}>
                      <span className="badge">已带入</span>
                      <button type="button" className="btn-danger" disabled={runningIdentity} onClick={clearUploadedIdentity}>
                        {runningIdentity ? "处理中..." : "X 移除"}
                      </button>
                    </div>
                  </article>
                </div>
              ) : (
                <div className="empty-state">当前无上传模特图。建议上传一张全身标准照式模特图；如果没有现成模特，也可以直接生成新的模特锚点。</div>
              )}
              <div className="file-picker" style={{ marginTop: 8 }}>
                <input
                  key={`batch-identity-upload-${identityUploadVersion}`}
                  id={`batch-identity-upload-${identityUploadVersion}`}
                  className="file-input-hidden"
                  type="file"
                  accept="image/*"
                  onChange={(event) => setIdentityUploadFile(event.target.files?.[0] || null)}
                />
                <label className="btn-secondary" htmlFor={`batch-identity-upload-${identityUploadVersion}`}>选择文件</label>
                <span className="muted">{identityUploadFile ? identityUploadFile.name : "未选择文件"}</span>
                {identityUploadFile ? (
                  <button type="button" className="btn-ghost" onClick={() => { setIdentityUploadFile(null); setIdentityUploadVersion((prev) => prev + 1); }}>
                    撤回已选
                  </button>
                ) : null}
              </div>
              <div className="toolbar" style={{ marginTop: 8 }}>
                <button type="button" className="btn-secondary" disabled={runningIdentity || !identityUploadFile} onClick={uploadIdentity}>
                  {runningIdentity ? "上传中..." : "上传并替换模特图"}
                </button>
              </div>
              <div className="identity-mode-group" style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className={cx("identity-mode-btn", identitySource === "use_uploaded" && "active")}
                  disabled={!hasUploadedIdentity}
                  onClick={() => setIdentityDesign((prev) => ({ ...prev, identity_source: "use_uploaded" }))}
                >
                  直接使用这张模特照
                </button>
                <button
                  type="button"
                  className={cx("identity-mode-btn", identitySource === "beautify_uploaded" && "active")}
                  disabled={!hasUploadedIdentity}
                  onClick={() => setIdentityDesign((prev) => ({ ...prev, identity_source: "beautify_uploaded" }))}
                >
                  先精修这张模特照
                </button>
                <button
                  type="button"
                  className={cx("identity-mode-btn", identitySource === "generate_new" && "active")}
                  onClick={() => setIdentityDesign((prev) => ({ ...prev, identity_source: "generate_new" }))}
                >
                  生成新的模特照
                </button>
              </div>
              {!hasUploadedIdentity ? <div className="muted" style={{ marginTop: 6 }}>未上传模特图时，仅可选择“生成新的模特照”。</div> : null}
            </div>

            <div className="identity-panel">
              <div className="identity-panel-head">
                <h3 className="title-row"><Icon name="spark" size={16} />当前锚点总览</h3>
                {identityConfirmed ? <span className="badge">已确认</span> : <span className="badge warning">待确认</span>}
              </div>
              {confirmedIdentityAsset ? (
                <div className="toolbar">
                  <span className="muted">来源：{confirmedIdentityAsset.source_type === "uploaded" ? "上传模特图" : "生成候选图"}</span>
                  <span className="muted">资产ID：{confirmedIdentityAsset.asset_id.slice(0, 8)}</span>
                </div>
              ) : (
                <div className="muted">未确认锚点，请在下方候选图点击“确认锚点”。</div>
              )}
              {confirmedIdentityAsset ? (
                <div className="asset-grid" style={{ marginTop: 8 }}>
                  <article className="asset-card" style={{ border: "2px solid #4b82f0" }}>
                    <img src={confirmedIdentityAsset.image_url || localPathToMedia(confirmedIdentityAsset.local_path)} alt="confirmed-anchor" loading="lazy" decoding="async" />
                  </article>
                </div>
              ) : null}
              <div className="toolbar" style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={identityPrimaryDisabled}
                  onClick={() => generateIdentityCandidate(false, identitySource)}
                >
                  {runningIdentity ? "处理中..." : identityPrimaryLabel}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={runningIdentity || identitySource !== "generate_new"}
                  onClick={() => generateIdentityCandidate(true, "generate_new")}
                >
                  重新生成
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={runningIdentity || identitySource !== "generate_new"}
                  onClick={() => setShowNewIdentityForm((prev) => !prev)}
                >
                  {showNewIdentityForm ? "收起细节参数" : "展开细节参数"}
                </button>
              </div>
              {identitySource === "generate_new" && showNewIdentityForm ? (
                <div className="grid" style={{ marginTop: 8 }}>
                  <div className="field">
                    <label>景别</label>
                    <select value={identityDesign.framing_preset} onChange={(event) => setIdentityDesign((prev) => ({ ...prev, framing_preset: event.target.value }))}>
                      <option value="full_body">全身人像</option>
                      <option value="half_body">半身人像</option>
                      <option value="headshot">近景头像</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>角度</label>
                    <select value={identityDesign.angle_preset} onChange={(event) => setIdentityDesign((prev) => ({ ...prev, angle_preset: event.target.value }))}>
                      <option value="front">正面</option>
                      <option value="left_45">左前45°</option>
                      <option value="right_45">右前45°</option>
                      <option value="slight_low">轻微仰拍</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>预设模板</label>
                    <select
                      value={MODEL_IDENTITY_TEMPLATES.findIndex((item) => item.framing_preset === identityDesign.framing_preset && item.angle_preset === identityDesign.angle_preset) >= 0
                        ? String(MODEL_IDENTITY_TEMPLATES.findIndex((item) => item.framing_preset === identityDesign.framing_preset && item.angle_preset === identityDesign.angle_preset))
                        : ""}
                      onChange={(event) => {
                        const idx = Number(event.target.value);
                        const preset = MODEL_IDENTITY_TEMPLATES[idx];
                        if (preset) setIdentityDesign((prev) => ({ ...prev, ...preset, identity_source: "generate_new" }));
                      }}
                    >
                      <option value="">自定义</option>
                      {MODEL_IDENTITY_TEMPLATES.map((item, idx) => (
                        <option key={item.label} value={idx}>{item.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="field" style={{ gridColumn: "1 / -1" }}>
                    <label>补充描述（可选）</label>
                    <textarea
                      value={identityDesign.identity_requirements}
                      placeholder="例如：自然妆容、商务质感、保留真实皮肤纹理。"
                      onChange={(event) => setIdentityDesign((prev) => ({ ...prev, identity_requirements: event.target.value }))}
                    />
                  </div>
                </div>
              ) : null}
            </div>
          </div>
          {!identityAssets.length ? (
            <div className="empty-state" style={{ marginTop: 10 }}>
              暂无候选图。先点击上方主按钮生成候选，再确认锚点。
            </div>
          ) : (
            <div className="asset-grid" style={{ marginTop: 10 }}>
              {identityAssets.map((asset) => {
                const imageUrl = asset.image_url || localPathToMedia(asset.local_path);
                const selected = asset.asset_id === batch?.identity_anchor_asset_id;
                const identityLayoutLabel = asset.metadata?.identity_layout === "triptych_front_side_back" ? "三视图定妆照" : "候选";
                return (
                  <article key={asset.asset_id} className="asset-card" style={selected ? { border: "2px solid #4b82f0" } : undefined}>
                    {imageUrl ? <img src={imageUrl} alt="identity-candidate" loading="lazy" decoding="async" /> : <div className="empty-state">无预览</div>}
                    <div className="toolbar" style={{ marginTop: 8 }}>
                      <span className="badge">{selected ? (identityConfirmed ? "当前锚点" : "待确认锚点") : "锚点图"}</span>
                      <span className="badge">{identityLayoutLabel}</span>
                      <button type="button" className="btn-secondary" disabled={runningIdentity || (selected && identityConfirmed)} onClick={() => confirmIdentity(asset.asset_id)}>
                        {selected ? (identityConfirmed ? "已确认" : "确认该锚点") : "确认锚点"}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
          <div className="toolbar" style={{ marginTop: 12 }}>
            <button
              type="button"
              className="btn-primary"
              disabled={!identityConfirmed || runningIdentity}
              onClick={() => setStep(2)}
            >
              确认锚点并开始整组替换
            </button>
          </div>
          {!identityConfirmed ? <div className="muted" style={{ marginTop: 6 }}>请先在候选区确认一张模特锚点图，再开始整组替换精修。</div> : null}
        </section>
      )}

      {step === 2 && (
        <section className="card workflow-panel">
          <div className="workflow-panel-head">
            <div className="step-kicker">STEP 3</div>
            <h2 className="title-row"><Icon name="wand" size={18} />批量精修执行</h2>
          </div>
          <div className="status-banner">
            {batchProgressText}
          </div>
          <div className="muted" style={{ marginTop: 6 }}>
            {autoPolling ? "自动刷新中（每 5 秒回填一次）" : "当前未检测到运行任务"}
            {batch?.failed_images ? " · 可点“仅重跑失败项”快速恢复" : ""}
          </div>
          {batch?.failed_images ? (
            <div className="status-banner warning" style={{ marginTop: 8 }}>
              当前已有 {batch.failed_images} 张结果被标记为异常。异常通常意味着：模特锚点未稳定命中、人物结构异常，或模型返回不完整。请优先查看异常卡片，不要把它当成正常替换结果。
            </div>
          ) : null}
          <div className="status-banner" style={{ marginTop: 8 }}>
            参考顺序固定为：主图作为基底输入 → 模特锚点作为首个参考输入 → 其他风格参考图排在其后。
          </div>
          <div className="toolbar" style={{ marginTop: 10 }}>
            <label className="muted">比例</label>
            <select
              style={{ width: 130 }}
              value={batchGenerateOptions.output_aspect_ratio}
              onChange={(event) => setBatchGenerateOptions((prev) => ({ ...prev, output_aspect_ratio: event.target.value }))}
            >
              <option value="original">原图（默认）</option>
              <option value="1:1">1:1</option>
              <option value="4:5">4:5</option>
              <option value="3:4">3:4</option>
              <option value="9:16">9:16</option>
              <option value="16:9">16:9</option>
            </select>
            <label className="muted">分辨率</label>
            <select
              style={{ width: 90 }}
              value={batchGenerateOptions.image_resolution}
              disabled={batchGenerateOptions.output_aspect_ratio === "original"}
              onChange={(event) => setBatchGenerateOptions((prev) => ({ ...prev, image_resolution: event.target.value }))}
            >
              <option value="1K">1K</option>
              <option value="2K">2K</option>
              <option value="4K">4K</option>
            </select>
            {batchGenerateOptions.output_aspect_ratio === "original" ? <span className="muted">原图比例模式下不传分辨率</span> : null}
            <label className="muted">格式</label>
            <select
              style={{ width: 90 }}
              value={batchGenerateOptions.image_output_format}
              onChange={(event) => setBatchGenerateOptions((prev) => ({ ...prev, image_output_format: event.target.value }))}
            >
              <option value="png">png</option>
              <option value="jpg">jpg</option>
            </select>
            <button type="button" className="btn-primary" onClick={startBatchGenerate} disabled={runningGenerate || batch?.identity_status !== "confirmed"}>
              {runningGenerate ? "执行中..." : "一键开始批量精修"}
            </button>
            <button type="button" className="btn-secondary" onClick={retryFailed} disabled={!batch?.failed_images}>仅重跑失败项</button>
            <button type="button" className="btn-secondary" onClick={load}>刷新状态</button>
            <button type="button" className="btn-secondary" onClick={() => setStep(3)}>查看结果</button>
          </div>
          <div className="tool-grid" style={{ marginTop: 10 }}>
            {RETOUCH_BATCH_LANES.map((lane) => {
              const rows = laneColumns[lane.key] || [];
              return (
                <article key={lane.key} className="tool-card">
                  <div className="toolbar" style={{ justifyContent: "space-between" }}>
                    <h3 className="title-row"><Icon name="task" size={15} />{lane.label}</h3>
                    <span className="badge">{rows.length}</span>
                  </div>
                  <div className="muted">{lane.hint}</div>
                  {!rows.length ? (
                    <div className="empty-state" style={{ marginTop: 8 }}>暂无任务</div>
                  ) : (
                    <div className="asset-grid" style={{ marginTop: 8 }}>
                      {rows.map((item) => (
                        <article key={`lane-${lane.key}-${item.project_id}`} className="asset-card">
                          {item.preview ? (
                            <img
                              src={item.preview}
                              alt="retouch-result"
                              onError={(event) => applyImageFallback(event, fallbackImageForToolType(tool.toolType))}
                            />
                          ) : <div className="empty-state">等待结果</div>}
                          <div className="muted" style={{ marginTop: 6 }}>任务 {item.project_id.slice(0, 8)}</div>
                          <div className="toolbar" style={{ marginTop: 8 }}>
                            <span className="badge">回填 {item.generatedCount}</span>
                            <span className="badge">通过 {item.approvedCount}</span>
                            <span className="badge">待审 {item.pendingCount}</span>
                            <span className="badge">异常 {item.failedCount}</span>
                          </div>
                          {item.staleExecution ? <div className="muted warning-text" style={{ marginTop: 6 }}>等待超过 3 分钟，建议重试该任务。</div> : null}
                          {item.noResult && !item.isTaskRunning ? <div className="muted warning-text" style={{ marginTop: 6 }}>当前无回填结果，可直接重试该任务。</div> : null}
                          {(item.isTaskFailed || (item.noResult && !item.isTaskRunning)) ? (
                            <div className="toolbar" style={{ marginTop: 8 }}>
                              <button type="button" className="btn-secondary" onClick={() => retrySingleProject(item.project_id)}>重试该任务</button>
                            </div>
                          ) : null}
                        </article>
                      ))}
                    </div>
                  )}
                  {lane.key === "review" && rows.length > 0 ? (
                    <div className="toolbar" style={{ marginTop: 8 }}>
                      <button type="button" className="btn-secondary" onClick={() => setStep(3)}>进入结果审核</button>
                    </div>
                  ) : null}
                  {lane.key === "export" && rows.length > 0 ? (
                    <div className="toolbar" style={{ marginTop: 8 }}>
                      <button type="button" className="btn-secondary" onClick={() => setStep(3)}>查看可导出结果</button>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="card workflow-panel">
          <div className="workflow-panel-head">
            <div className="step-kicker">STEP 4</div>
            <h2 className="title-row"><Icon name="task" size={18} />结果审核与导出</h2>
          </div>
          {allGeneratedAssets.length === 0 ? (
            <div className="empty-state">暂无结果，先执行批量精修。</div>
          ) : (
            <>
              <div className="toolbar" style={{ marginBottom: 12, justifyContent: "space-between", flexWrap: "wrap" }}>
                <div className="muted">已通过 {approvedGeneratedAssets.length} 张，可直接交付；也可打包下载全部结果继续筛选。</div>
                <div className="toolbar">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={approvedGeneratedAssets.length === 0}
                    onClick={() => downloadBatchArchive("approved")}
                  >
                    打包下载已通过结果
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => downloadBatchArchive("generated")}
                  >
                    打包下载全部结果
                  </button>
                </div>
              </div>
              <div className="asset-grid">
              {allGeneratedAssets.map((asset) => {
                const imageUrl = asset.image_url || localPathToMedia(asset.local_path);
                const bucket = assetReviewBucket(asset);
                return (
                  <article key={asset.asset_id} className="asset-card">
                    {imageUrl ? <img src={imageUrl} alt="review-asset" loading="lazy" decoding="async" /> : <div className="empty-state">无预览</div>}
                    <div className="muted" style={{ marginTop: 6 }}>{candidateCaption(asset)}</div>
                    <div className="toolbar" style={{ marginTop: 8 }}>
                      <span className={cx("badge", bucket === "failed" && "warning")}>
                        {bucket === "approved" ? "已通过" : bucket === "failed" ? "异常" : "待审核"}
                      </span>
                      <button type="button" className="btn-secondary" disabled={bucket === "approved"} onClick={() => reviewAsset(asset.__projectId, asset.asset_id, "approve")}>通过</button>
                      <button type="button" className="btn-danger" onClick={() => reviewAsset(asset.__projectId, asset.asset_id, "reject")}>驳回</button>
                    </div>
                  </article>
                );
              })}
            </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}

function ProjectWorkspace({ tool, projectId, navigate }) {
  const [project, setProject] = useState(null);
  const [progress, setProgress] = useState(null);
  const [assets, setAssets] = useState([]);
  const [logs, setLogs] = useState([]);
  const [batchTasks, setBatchTasks] = useState([]);
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState({ text: "加载中...", type: "" });
  const [planStatus, setPlanStatus] = useState({ text: "等待执行", type: "" });
  const [generateStatus, setGenerateStatus] = useState({ text: "等待执行", type: "" });
  const [actionStatus, setActionStatus] = useState({ text: "点击“一键继续”自动推进", type: "" });
  const [generateFilter, setGenerateFilter] = useState("all");
  const [reviewFilter, setReviewFilter] = useState("all");
  const [logDrawerOpen, setLogDrawerOpen] = useState(false);
  const [runningNext, setRunningNext] = useState(false);
  const [runningGenerate, setRunningGenerate] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [manualReviewMode, setManualReviewMode] = useState(false);
  const [downloadingArchiveScope, setDownloadingArchiveScope] = useState("");
  const [savingPlan, setSavingPlan] = useState(false);
  const [scriptSelecting, setScriptSelecting] = useState(false);
  const [introSelectedScriptId, setIntroSelectedScriptId] = useState("");
  const [promptInputs, setPromptInputs] = useState({ goal: "", style: "", shot_focus: "", constraints: "" });
  const [planDraftShots, setPlanDraftShots] = useState([]);
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
    image_aspect_ratio: "auto",
    image_resolution: "1K",
    image_output_format: "png",
    video_aspect_ratio: "portrait",
    video_n_frames: "10",
    video_size: "standard",
    video_remove_watermark: true,
  });
  const planLabel = tool.slug === "model-retouch"
    ? "精修方案"
    : tool.slug === "product-image"
    ? "拍摄方案"
    : tool.slug === "multi-angle-camera"
    ? "机位方案"
    : tool.slug === "intro-video" || tool.slug === "quick-video-15s"
    ? "AI方案"
    : "方案";
  const preferenceLabels = {
    goal: tool.slug === "model-retouch" ? "精修目标" : tool.slug === "product-image" ? "拍摄目标" : "目标",
    style: "风格",
    focus: tool.slug === "model-retouch" ? "精修重点" : "镜头重点",
    constraints: tool.slug === "model-retouch" ? "注意事项（逗号）" : "限制（逗号）",
  };
  const [identityDesign, setIdentityDesign] = useState({
    identity_source: "beautify_uploaded",
    identity_requirements: "",
    lighting_preset: "softbox_clean",
    framing_preset: "full_body",
    angle_preset: "front",
    preserve_pose: true,
  });
  const pollRef = useRef(null);
  const pollUntilRef = useRef(0);
  const initializedStepRef = useRef(false);
  const mountedRef = useRef(true);
  const actionTokenRef = useRef(0);
  const generateTokenRef = useRef(0);
  const pendingPlanRef = useRef(false);
  const pendingPromptRef = useRef(false);
  const planPendingSinceRef = useRef(0);
  const actionStatusRef = useRef(actionStatus);
  const [pollingActive, setPollingActive] = useState(false);
  const pendingCreateRef = useRef(false);
  const createDeadlineRef = useRef(0);
  const redirectedBatchRef = useRef(false);
  const autoAdvanceReviewRef = useRef(false);

  const generatedAssets = useMemo(
    () => assets.filter(
      (item) => item.source_type === "generated" && (item.kind === "generated_image" || item.kind === "generated_video")
    ),
    [assets],
  );
  const identityAssets = useMemo(() => assets.filter((item) => Array.isArray(item.tags) && item.tags.includes("identity")), [assets]);
  const activeIdentityAssetId = project?.identity_asset_id || identityAssets[0]?.asset_id || "";
  const introScriptOptions = useMemo(() => project?.script_options || [], [project?.script_options]);
  const selectedIntroScript = useMemo(() => {
    if (project?.selected_script) return project.selected_script;
    if (introSelectedScriptId) {
      return introScriptOptions.find((item) => item.script_id === introSelectedScriptId) || null;
    }
    return introScriptOptions[0] || null;
  }, [project?.selected_script, introScriptOptions, introSelectedScriptId]);
  const introScriptReady = Boolean(selectedIntroScript || project?.selected_script);
  const generationStepIndex = tool.slug === "model-retouch" ? 3 : Math.min(2, tool.steps.length - 1);
  const identityStepIndex = tool.slug === "model-retouch" ? 2 : -1;
  const selectedFinalCount = generatedAssets.filter((item) => assetReviewBucket(item) === "approved").length;
  const requiredFinalCount = Number(project?.set_config?.target_final_count || 0);
  const candidatePoolCount = generatedAssets.length;
  const hasFailedCandidates = generatedAssets.some((item) => assetReviewBucket(item) === "failed");
  const expectedCandidateTotal = Math.max(0, (project?.project_plan?.shots?.length || 0) * Number(options.candidates_per_prompt || 1));
  const batchTotal = project?.batch_stats?.total_images || 0;
  const isProjectRunning = progress?.task_status === "running";
  const showRetry = progress?.task_status === "failed" || generateStatus.type === "error";
  const isInitializing = Boolean(
    actionStatus?.text?.includes("正在处理上传")
    || actionStatus?.text?.includes("任务创建中")
    || actionStatus?.text?.includes("同步素材")
  );
  const planShotCount = project?.project_plan?.shots?.length || 0;
  const expectedPlanCount = tool.slug === "product-image"
    ? Math.max(planShotCount, requiredFinalCount || 0)
    : tool.slug === "model-retouch"
      ? Math.max(batchTotal || 0, planShotCount || 0, 1)
      : planShotCount;
  const minPlanSlots = tool.slug === "model-retouch" ? 1 : 4;
  const maxPlanSlots = tool.slug === "model-retouch" ? 60 : 30;
  const planSlotsToShow = Math.min(Math.max(expectedPlanCount || 0, minPlanSlots), maxPlanSlots);
  const isPlanLoading = !planShotCount
    && (
      (progress?.task_status === "running" && progress?.current_stage === "plan")
      || pendingPlanRef.current
    );

  useEffect(() => {
    if (tool.slug !== "intro-video") return;
    const next = project?.selected_script?.script_id || project?.script_options?.[0]?.script_id || "";
    setIntroSelectedScriptId(next);
  }, [tool.slug, project?.selected_script?.script_id, project?.script_options]);

  const startPolling = useCallback((durationMs = 120000) => {
    pollUntilRef.current = Date.now() + durationMs;
    setPollingActive(true);
  }, []);

  const stopPolling = useCallback(() => {
    pollUntilRef.current = 0;
    setPollingActive(false);
  }, []);

  const load = useCallback(async () => {
    try {
      const [p, prog, a, l] = await Promise.all([
        apiFetch(`/api/v1/projects/${projectId}`),
        apiFetch(`/api/v1/projects/${projectId}/progress`),
        apiFetch(`/api/v1/projects/${projectId}/assets`),
        apiFetch(`/api/v1/projects/${projectId}/logs?limit=80`),
      ]);
      let batchList = [];
      if (tool.slug === "model-retouch" && p?.batch_group_id) {
        try {
          const allTasks = await apiFetch(`/api/v1/tools/${tool.toolType}/tasks?limit=200`);
          batchList = allTasks.filter((item) => item.batch_group_id === p.batch_group_id);
        } catch (_) {
          batchList = [];
        }
      }
      if (!mountedRef.current) return { p, prog, a, l };
      if (typeof window !== "undefined") {
        safeSessionRemove(`pending_project_${projectId}`);
        const createError = safeSessionGet(`create_error_${projectId}`);
        if (createError) {
          setActionStatus({ text: `失败：${createError}`, type: "error" });
          safeSessionRemove(`create_error_${projectId}`);
        }
      }
      const wasPendingCreate = pendingCreateRef.current;
      pendingCreateRef.current = false;
      setProject(p);
      setProgress(prog);
      setAssets(a);
      setLogs(l);
      setBatchTasks(batchList);
      if (wasPendingCreate && actionStatusRef.current?.text?.includes("正在处理上传")) {
        setActionStatus({ text: `素材已就绪，可生成${planLabel}。`, type: "success" });
      }
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
      setPlanDraftShots(
        (p?.project_plan?.shots || []).map((shot) => ({
          shot_id: shot.shot_id,
          title: shot.title || "",
          intent: shot.intent || "",
          delivery_purpose: resolveDeliveryPurpose(shot, p?.scenario_type),
          image_prompt: shot.image_prompt || "",
        })),
      );
      setOptions((prev) => ({
        ...prev,
        candidates_per_prompt: tool.slug === "product-image"
          ? Number(p?.set_config?.takes_per_shot || prev.candidates_per_prompt || 1)
          : prev.candidates_per_prompt,
        image_aspect_ratio: tool.category === "image"
          ? ((p?.output_aspect_ratio && p.output_aspect_ratio !== "original") ? p.output_aspect_ratio : "auto")
          : prev.image_aspect_ratio,
      }));
      const nextAction = tool.slug === "multi-angle-camera"
        ? "下一步：进入机位控制并生成当前角度"
        : (prog.next_action || "按流程执行");
      setStatus({ text: `阶段：${stageLabel(prog.current_stage, tool.slug)} ｜ 进度：${prog.progress_percent_weighted}% ｜ ${nextAction}`, type: p.status === "failed" ? "error" : "success" });
      if (pendingPlanRef.current && p?.project_plan) {
        pendingPlanRef.current = false;
        planPendingSinceRef.current = 0;
        setPlanStatus({ text: `成功：${planLabel}已更新`, type: "success" });
        if (actionStatusRef.current?.text?.includes("方案")) {
          setActionStatus({ text: `成功：${planLabel}已就绪，请继续下一步。`, type: "success" });
        }
      }
      if (pendingPlanRef.current && prog?.task_status === "failed") {
        pendingPlanRef.current = false;
        planPendingSinceRef.current = 0;
        setPlanStatus({ text: `失败：${p?.error_message || `${planLabel}生成失败，请重试`}`, type: "error" });
      }
      if (
        pendingPlanRef.current
        && !p?.project_plan
        && planPendingSinceRef.current > 0
        && Date.now() - planPendingSinceRef.current > PLAN_TIMEOUT_MS
      ) {
        pendingPlanRef.current = false;
        planPendingSinceRef.current = 0;
        setPlanStatus({ text: `失败：${planLabel}生成超时（2分钟），请重试。`, type: "error" });
      } else if (!p?.project_plan && prog?.task_status === "running" && prog?.current_stage === "plan") {
        setPlanStatus({ text: "执行中：方案生成中，完成后自动刷新", type: "" });
      } else if (!pendingPlanRef.current && !p?.project_plan && prog?.current_stage === "plan") {
        setPlanStatus({
          text: tool.slug === "multi-angle-camera"
            ? "等待执行：先保存机位或点击“开始生成当前角度”。"
            : `等待执行：点击“生成${planLabel}”开始。`,
          type: "warning",
        });
      }
      if (pendingPromptRef.current && p?.prompt_pack) {
        pendingPromptRef.current = false;
        setPlanStatus({ text: "成功：执行方案已准备", type: "success" });
      }
      return { p, prog, a, l };
    } catch (error) {
      const message = String(error?.message || "");
      if (typeof window !== "undefined") {
        const pendingKey = `pending_project_${projectId}`;
        const pending = safeSessionGet(pendingKey);
        const storedError = safeSessionGet(`create_error_${projectId}`);
        if (storedError) {
          safeSessionRemove(pendingKey);
          pendingCreateRef.current = false;
          setStatus({ text: `失败：${storedError}`, type: "error" });
          safeSessionRemove(`create_error_${projectId}`);
          return;
        }
        if (pending) {
          if (!pendingCreateRef.current) {
            pendingCreateRef.current = true;
            createDeadlineRef.current = Date.now() + 120000;
          }
          if (Date.now() > createDeadlineRef.current) {
            safeSessionRemove(pendingKey);
            pendingCreateRef.current = false;
            setStatus({ text: "失败：项目创建超时，请返回任务中心重新提交。", type: "error" });
            stopPolling();
            return;
          }
          setStatus({ text: "任务创建中，正在同步素材，请稍候…", type: "warning" });
          setActionStatus({ text: "正在处理上传与任务初始化，请稍候自动刷新。", type: "" });
          startPolling(120000);
          return;
        }
      }
      setStatus({ text: message || "加载失败", type: "error" });
    }
  }, [projectId, tool.slug]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    setActionStatus({
      text: tool.slug === "multi-angle-camera"
        ? "进入机位控制后调整参数并生成当前角度。"
        : tool.slug === "product-image"
          ? "先生成拍摄方案，再确认后进入试拍。"
          : tool.slug === "model-retouch"
            ? "先确认模特身份（精修上传模特或生成新模特），再执行单图精修。"
            : "点击“一键继续”自动推进",
      type: "",
    });
  }, [tool.slug]);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);
  useEffect(() => {
    actionStatusRef.current = actionStatus;
  }, [actionStatus]);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const pending = safeSessionGet(`pending_project_${projectId}`);
    if (!pending) return;
    pendingCreateRef.current = true;
    createDeadlineRef.current = Date.now() + 120000;
    setStatus({ text: "任务创建中，正在同步素材，请稍候…", type: "warning" });
    setActionStatus({ text: "正在处理上传与任务初始化，请稍候自动刷新。", type: "" });
    startPolling(120000);
  }, [projectId, startPolling]);
  useEffect(() => {
    if (!project || !progress || initializedStepRef.current) return;
    let nextStep = 0;
    const stage = String(progress.current_stage || "");
    if (tool.slug === "multi-angle-camera") {
      nextStep = 1;
    } else if (["plan", "prompt", "master_script", "storyboard", "scripted"].includes(stage)) {
      nextStep = tool.slug === "model-retouch" && identityStepIndex >= 0 ? identityStepIndex : 1;
    } else if (stage === "identity" && identityStepIndex >= 0) {
      nextStep = identityStepIndex;
    } else if (["generate", "render"].includes(stage)) {
      nextStep = generationStepIndex;
    } else if (["review", "completed", "failed"].includes(stage)) {
      nextStep = tool.steps.length - 1;
    } else if (project?.project_plan && !project?.prompt_pack) {
      nextStep = tool.slug === "model-retouch" && identityStepIndex >= 0 ? identityStepIndex : 1;
    } else if (project?.prompt_pack) {
      nextStep = generationStepIndex;
    }
    setStep(nextStep);
    initializedStepRef.current = true;
  }, [tool.slug, project, progress, generationStepIndex, identityStepIndex, tool.steps.length]);

  useEffect(() => {
    if (tool.slug !== "quick-video-15s") return;
    if (step !== 1) return;
    if (!project?.prompt_pack) return;
    setStep(generationStepIndex);
    setActionStatus((prev) => prev.type === "success" ? prev : { text: "执行方案已准备，已进入候选生成。", type: "success" });
  }, [tool.slug, step, project?.prompt_pack, generationStepIndex]);

  useEffect(() => {
    if (tool.slug !== "product-image") return;
    if (step !== generationStepIndex) return;
    if (!expectedCandidateTotal || candidatePoolCount < expectedCandidateTotal) {
      autoAdvanceReviewRef.current = false;
      return;
    }
    if (isProjectRunning || autoAdvanceReviewRef.current) return;
    autoAdvanceReviewRef.current = true;
    setStep(tool.steps.length - 1);
    setActionStatus({
      text: `候选图已全部回填（${candidatePoolCount}/${expectedCandidateTotal}），已自动进入“选片分享”。`,
      type: "success",
    });
  }, [
    tool.slug,
    step,
    generationStepIndex,
    expectedCandidateTotal,
    candidatePoolCount,
    isProjectRunning,
    tool.steps.length,
  ]);

  useEffect(() => {
    if (!project) return;
    if (tool.slug !== "model-retouch") return;
    if (!project.batch_group_id) return;
    if (redirectedBatchRef.current) return;
    redirectedBatchRef.current = true;
    navigate(`/app/tools/model-retouch/batches/${project.batch_group_id}`);
  }, [project, tool.slug, navigate]);

  useEffect(() => {
    if (tool.slug !== "model-retouch") return;
    if (step !== 1) return;
    if (identityStepIndex >= 0) {
      setStep(identityStepIndex);
    }
  }, [tool.slug, step, identityStepIndex]);

  useEffect(() => {
    const shouldPoll = pollingActive
      || progress?.task_status === "running"
      || (
        progress?.task_status === "queued"
        && (pendingPlanRef.current || pendingPromptRef.current || runningGenerate || runningNext || pendingCreateRef.current)
      );
    if (!shouldPoll) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    if (!pollRef.current) {
      pollRef.current = setInterval(async () => {
        const result = await load().catch(() => null);
        if (!pollingActive || !pollUntilRef.current) return;
        if (!result?.prog) return;
        const pendingWork = pendingPlanRef.current || pendingPromptRef.current || runningGenerate || runningNext || pendingCreateRef.current;
        const stillRunning = result.prog.task_status === "running" || (result.prog.task_status === "queued" && pendingWork);
        if (!stillRunning && !pendingWork) {
          stopPolling();
          return;
        }
        if (Date.now() > pollUntilRef.current && !stillRunning) {
          stopPolling();
        }
      }, 5000);
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [progress, load, pollingActive, stopPolling, runningGenerate, runningNext]);

  const savePrompt = async () => {
    try {
      setPlanStatus({ text: "提交中：保存方案偏好...", type: "" });
      await apiFetch(`/api/v1/projects/${projectId}/prompt-inputs`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt_inputs: { ...promptInputs, constraints: parseCsv(promptInputs.constraints) } }),
      });
      await load();
      setPlanStatus({ text: "成功：方案偏好已保存", type: "success" });
    } catch (error) {
      setPlanStatus({ text: `失败：${error.message}`, type: "error" });
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
      body: JSON.stringify({ force, async_mode: true }),
    });
  };

  const genPlan = async () => {
    try {
      setPlanStatus({ text: `提交中：生成${planLabel}...`, type: "" });
      pendingPlanRef.current = true;
      planPendingSinceRef.current = Date.now();
      startPolling(120000);
      await requestPlan(true);
      if (!mountedRef.current) return;
      await load();
      if (pendingPlanRef.current) {
        setPlanStatus({ text: "执行中：方案生成中，完成后自动刷新", type: "" });
      } else {
        setPlanStatus({ text: `成功：${planLabel}已更新`, type: "success" });
      }
    } catch (error) {
      if (!mountedRef.current) return;
      pendingPlanRef.current = false;
      planPendingSinceRef.current = 0;
      setPlanStatus({ text: `失败：${error.message}`, type: "error" });
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
      setPlanStatus({ text: "提交中：生成执行方案...", type: "" });
      pendingPromptRef.current = true;
      startPolling(120000);
      await apiFetch(`/api/v1/projects/${projectId}/derive-prompts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force: true }) });
      if (!mountedRef.current) return;
      await load();
      if (pendingPromptRef.current) {
        setPlanStatus({ text: "执行中：执行方案整理中，完成后自动刷新", type: "" });
      } else {
        setPlanStatus({ text: "成功：执行方案已准备", type: "success" });
        if (tool.slug === "quick-video-15s") {
          setStep(generationStepIndex);
          setActionStatus({ text: "成功：执行方案已准备，已进入候选生成。", type: "success" });
        }
      }
    } catch (error) {
      if (!mountedRef.current) return;
      pendingPromptRef.current = false;
      setPlanStatus({ text: `失败：${error.message}`, type: "error" });
    }
  };

  const updatePlanDraftShot = (shotId, field, value) => {
    setPlanDraftShots((prev) => prev.map((item) => (
      item.shot_id === shotId ? { ...item, [field]: value } : item
    )));
  };

  const savePlanDraft = async () => {
    if (!project?.project_plan?.shots?.length) {
      setPlanStatus({ text: `暂无可保存的${planLabel}`, type: "warning" });
      return;
    }
    try {
      setSavingPlan(true);
      setPlanStatus({ text: `提交中：保存${planLabel}...`, type: "" });
      const draftMap = Object.fromEntries(planDraftShots.map((item) => [item.shot_id, item]));
      const nextPlan = {
        ...project.project_plan,
        shots: project.project_plan.shots.map((shot) => {
          const draft = draftMap[shot.shot_id];
          if (!draft) return shot;
          return {
            ...shot,
            title: draft.title || shot.title,
            intent: draft.intent || shot.intent,
            delivery_purpose: resolveDeliveryPurpose(
              { ...shot, delivery_purpose: draft.delivery_purpose || shot.delivery_purpose },
              project?.scenario_type,
            ),
            image_prompt: draft.image_prompt || shot.image_prompt,
          };
        }),
      };
      await apiFetch(`/api/v1/projects/${projectId}/plan`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_plan: nextPlan }),
      });
      if (!mountedRef.current) return;
      await load();
      setPlanStatus({ text: `成功：${planLabel}已保存`, type: "success" });
    } catch (error) {
      if (!mountedRef.current) return;
      setPlanStatus({ text: `失败：${error.message}`, type: "error" });
    } finally {
      setSavingPlan(false);
    }
  };

  const confirmPlanAndProceed = async () => {
    if (savingPlan) return;
    if (!project?.project_plan?.shots?.length) {
      await genPlan();
      return;
    }
    try {
      setSavingPlan(true);
      setPlanStatus({ text: `提交中：确认${planLabel}...`, type: "" });
      const draftMap = Object.fromEntries(planDraftShots.map((item) => [item.shot_id, item]));
      const nextPlan = {
        ...project.project_plan,
        shots: project.project_plan.shots.map((shot) => {
          const draft = draftMap[shot.shot_id];
          if (!draft) return shot;
          return {
            ...shot,
            title: draft.title || shot.title,
            intent: draft.intent || shot.intent,
            delivery_purpose: resolveDeliveryPurpose(
              { ...shot, delivery_purpose: draft.delivery_purpose || shot.delivery_purpose },
              project?.scenario_type,
            ),
            image_prompt: draft.image_prompt || shot.image_prompt,
          };
        }),
      };
      await apiFetch(`/api/v1/projects/${projectId}/plan`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_plan: nextPlan }),
      });
      await derivePrompts();
      if (!mountedRef.current) return;
      if (tool.slug === "model-retouch" && project?.identity_required && project?.identity_status !== "confirmed") {
        setStep(identityStepIndex);
        setActionStatus({ text: "成功：精修方案已确认，请先完成身份确认。", type: "success" });
      } else {
        setStep(generationStepIndex);
        setActionStatus({
          text: tool.slug === "product-image" ? "成功：拍摄方案已确认，进入试拍。" : "成功：方案已确认，进入生成。",
          type: "success",
        });
      }
    } catch (error) {
      if (!mountedRef.current) return;
      setPlanStatus({ text: `失败：${error.message}`, type: "error" });
    } finally {
      setSavingPlan(false);
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
    const resolvedAspectRatio = tool.slug === "multi-angle-camera"
      ? (cameraInputs.aspect_ratio || options.image_aspect_ratio)
      : options.image_aspect_ratio;
    const isOriginalImageMode = tool.category === "image" && resolvedAspectRatio === "auto";
    const requestBody = {
      stage,
      async_mode: true,
      candidates_per_prompt: options.candidates_per_prompt,
      variants_per_shot: options.variants_per_shot,
      image_aspect_ratio: resolvedAspectRatio,
      image_output_format: options.image_output_format,
      video_aspect_ratio: options.video_aspect_ratio,
      video_n_frames: options.video_n_frames,
      video_size: options.video_size,
      video_remove_watermark: options.video_remove_watermark,
    };
    if (!isOriginalImageMode) {
      requestBody.image_resolution = options.image_resolution;
    }
    return apiFetch(`/api/v1/projects/${projectId}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
  };

  const startMultiAngleGenerationFlow = async ({ auto = false } = {}) => {
    const candidateCount = 1;
    if (auto) {
      setGenerateStatus({ text: "执行中：系统已自动启动多角度生成（首轮 1 张/角度）...", type: "" });
    } else {
      setActionStatus({ text: "提交中：保存机位并启动多角度生成...", type: "" });
      setGenerateStatus({ text: "提交中：提交当前机位生成任务...", type: "" });
    }
    startPolling(180000);
    await applyCameraInputs();
    await requestPlan(true);
    await apiFetch(`/api/v1/projects/${projectId}/multi-angle/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        stage: "auto",
        async_mode: true,
        candidates_per_prompt: candidateCount,
        image_aspect_ratio: cameraInputs.aspect_ratio || options.image_aspect_ratio,
        image_resolution: options.image_resolution,
        image_output_format: options.image_output_format,
      }),
    });
    if (!mountedRef.current) return;
    await load();
    setStep(generationStepIndex);
    if (auto) {
      setGenerateStatus({ text: "执行中：已进入多角度生成，结果会自动刷新。", type: "success" });
      setActionStatus({ text: "已自动执行：机位方案 → 当前角度单张生成。", type: "success" });
    } else {
      setActionStatus({ text: "执行中：多角度任务已提交，预计 1-3 分钟返回。", type: "success" });
      setGenerateStatus({ text: "执行中：当前机位生成中，完成后可切换角度再拍一张。", type: "success" });
    }
  };

  const runGenerate = async (stage = "auto") => {
    if (runningGenerate) return;
    const token = generateTokenRef.current + 1;
    generateTokenRef.current = token;
    try {
      if (tool.slug === "multi-angle-camera") {
        setRunningGenerate(true);
        await startMultiAngleGenerationFlow({ auto: false });
        return;
      }
      startPolling(180000);
      const plannedShots = project?.project_plan?.shots?.length || 0;
      const requiredFinal = Number(project?.set_config?.target_final_count || 0);
      const predictedCandidates = plannedShots * Number(options.candidates_per_prompt || 1);
      if (tool.slug === "product-image" && requiredFinal > 0 && plannedShots > 0 && predictedCandidates < requiredFinal) {
        setGenerateStatus({
          text: `失败：当前试拍候选仅 ${predictedCandidates} 张，低于目标成片 ${requiredFinal} 张，请提高每方案试拍数。`,
          type: "warning",
        });
        return;
      }
      setRunningGenerate(true);
      setGenerateStatus({ text: "提交中：提交生成任务...", type: "" });
      await submitGenerate(stage);
      if (!mountedRef.current || token !== generateTokenRef.current) return;
      await load();
      setGenerateStatus({ text: "执行中：任务已提交，结果会自动刷新", type: "success" });
    } catch (error) {
      if (!mountedRef.current || token !== generateTokenRef.current) return;
      setGenerateStatus({ text: `失败：${error.message}`, type: "error" });
    } finally {
      if (mountedRef.current && token === generateTokenRef.current) {
        setRunningGenerate(false);
      }
    }
  };

  const runNextAction = async () => {
    if (runningNext) return;
    const token = actionTokenRef.current + 1;
    actionTokenRef.current = token;
    try {
      setRunningNext(true);
      setActionStatus({ text: "提交中：正在推进下一步（可能需要1-2分钟，可先离开工作台）...", type: "" });
      setGenerateStatus({ text: "等待执行", type: "" });
      startPolling(120000);

      if (!project) {
        await load();
      }
      const current = project || (await apiFetch(`/api/v1/projects/${projectId}`));
      const planStepForTool = tool.slug === "model-retouch" && identityStepIndex >= 0 ? identityStepIndex : 1;

      if (tool.slug === "multi-angle-camera") {
        setStep(1);
        setActionStatus({ text: "已切换到机位控制，请调整参数后生成当前角度。", type: "success" });
        return;
      }

      const scriptSelected = Boolean(current.master_script || current.selected_script);

      if (tool.slug === "intro-video" && scriptSelected === false && current.project_plan) {
        setStep(planStepForTool);
        setActionStatus({ text: "请先在 Step2 选择一套主脚本，再继续生成分镜与视频。", type: "warning" });
        return;
      }

      if (!current.project_plan) {
        pendingPlanRef.current = true;
        planPendingSinceRef.current = Date.now();
        await requestPlan(false);
        if (!mountedRef.current || token !== actionTokenRef.current) return;
        await load();
        setStep(planStepForTool);
        if (pendingPlanRef.current) {
          setActionStatus({ text: `执行中：${planLabel}生成中，完成后自动刷新。`, type: "" });
        } else {
          setActionStatus({ text: `成功：已生成${planLabel}，请确认后继续。`, type: "success" });
        }
        return;
      }

      if (tool.slug === "intro-video" && !scriptSelected) {
        setStep(planStepForTool);
        setActionStatus({ text: "请先在 Step2 选择一套主脚本，再编译提示词。", type: "warning" });
        return;
      }

      if (!current.prompt_pack) {
        pendingPromptRef.current = true;
        await apiFetch(`/api/v1/projects/${projectId}/derive-prompts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: false }),
        });
        if (!mountedRef.current || token !== actionTokenRef.current) return;
        await load();
        setStep(planStepForTool);
        if (pendingPromptRef.current) {
          setActionStatus({ text: "执行中：执行方案整理中，完成后自动刷新。", type: "" });
        } else {
          setActionStatus({ text: "成功：执行方案已准备，可继续执行生成。", type: "success" });
        }
        return;
      }

      if (tool.slug === "model-retouch" && current.identity_required && current.identity_status !== "confirmed") {
        setStep(identityStepIndex >= 0 ? identityStepIndex : 2);
        setActionStatus({ text: "请先在 Step3 完成身份确认，再执行批量精修。", type: "warning" });
        return;
      }

      if (tool.slug === "product-image") {
        const shotCount = current?.project_plan?.shots?.length || 0;
        const requiredFinal = Number(current?.set_config?.target_final_count || 0);
        const predictedCandidates = shotCount * Number(options.candidates_per_prompt || 1);
        if (requiredFinal > 0 && shotCount > 0 && predictedCandidates < requiredFinal) {
          setStep(generationStepIndex);
          setActionStatus({
            text: `请先调整试拍数量：当前候选 ${predictedCandidates} < 目标成片 ${requiredFinal}。`,
            type: "warning",
          });
          return;
        }
      }

      await submitGenerate("auto");
      if (!mountedRef.current || token !== actionTokenRef.current) return;
      await load();
      setStep(generationStepIndex);
      setActionStatus({ text: "执行中：任务已提交，已进入生成阶段。", type: "success" });
    } catch (error) {
      if (!mountedRef.current || token !== actionTokenRef.current) return;
      pendingPlanRef.current = false;
      pendingPromptRef.current = false;
      setActionStatus({ text: `失败：${error.message}`, type: "error" });
    } finally {
      if (mountedRef.current && token === actionTokenRef.current) {
        setRunningNext(false);
      }
    }
  };

  const retry = async () => {
    if (retrying) return;
    try {
      setRetrying(true);
      setGenerateStatus({ text: "提交中：提交重试...", type: "" });
      await apiFetch(`/api/v1/projects/${projectId}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ async_mode: true }),
      });
      await load();
      setGenerateStatus({ text: "执行中：重试已提交", type: "success" });
    } catch (error) {
      setGenerateStatus({ text: `失败：${error.message}`, type: "error" });
    } finally {
      setRetrying(false);
    }
  };

  const generateIdentityCandidate = async (regenerate = false) => {
    try {
      setActionStatus({ text: regenerate ? "重新生成身份候选中..." : "生成身份候选中...", type: "" });
      startPolling(120000);
      await apiFetch(`/api/v1/projects/${projectId}/identity/generate-candidate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          force: regenerate,
          identity_source: identityDesign.identity_source,
          identity_requirements: identityDesign.identity_requirements,
          lighting_preset: identityDesign.lighting_preset,
          framing_preset: identityDesign.framing_preset,
          angle_preset: identityDesign.angle_preset,
          preserve_pose: identityDesign.preserve_pose,
        }),
      });
      await load();
      setActionStatus({ text: "身份候选图已更新，请确认后继续。", type: "success" });
    } catch (error) {
      setActionStatus({ text: error.message, type: "error" });
    }
  };

  const confirmIdentity = async (assetId) => {
    try {
      setActionStatus({ text: "确认身份中...", type: "" });
      startPolling(120000);
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

  const selectIntroScript = async (scriptId, { silent = false } = {}) => {
    if (!scriptId) return false;
    try {
      setScriptSelecting(true);
      if (!silent) {
        setPlanStatus({ text: "提交中：选择主脚本...", type: "" });
      }
      await apiFetch(`/api/v1/projects/${projectId}/select-script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ script_id: scriptId, edits: [] }),
      });
      if (!mountedRef.current) return false;
      setIntroSelectedScriptId(scriptId);
      await load();
      if (!silent) {
        setPlanStatus({ text: "成功：主脚本已切换。", type: "success" });
      }
      return true;
    } catch (error) {
      if (!mountedRef.current) return false;
      setPlanStatus({ text: `失败：${error.message}`, type: "error" });
      return false;
    } finally {
      if (mountedRef.current) setScriptSelecting(false);
    }
  };

  const confirmIntroScriptAndProceed = async () => {
    if (scriptSelecting || isPlanLoading) return;
    if (!project) return;
    if (!introScriptOptions.length && !project.selected_script) {
      await genPlan();
      return;
    }
    const targetScriptId = introSelectedScriptId || project?.selected_script?.script_id || introScriptOptions[0]?.script_id || "";
    if (!targetScriptId) {
      setPlanStatus({ text: "失败：未找到可确认的主脚本，请先生成脚本候选。", type: "error" });
      return;
    }
    if (project?.selected_script?.script_id !== targetScriptId) {
      const ok = await selectIntroScript(targetScriptId, { silent: true });
      if (!ok) return;
    }
    try {
      setPlanStatus({ text: "提交中：确认主脚本并整理执行方案...", type: "" });
      pendingPromptRef.current = true;
      startPolling(120000);
      await apiFetch(`/api/v1/projects/${projectId}/derive-prompts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force: true }),
      });
      if (!mountedRef.current) return;
      await load();
      if (pendingPromptRef.current) {
        setPlanStatus({ text: "执行中：执行方案整理中，完成后自动刷新", type: "" });
      } else {
        setPlanStatus({ text: "成功：主脚本已确认，执行方案已准备。", type: "success" });
      }
      setStep(generationStepIndex);
      setActionStatus({ text: "成功：主脚本已确认，已进入视频生成。", type: "success" });
    } catch (error) {
      if (!mountedRef.current) return;
      pendingPromptRef.current = false;
      setPlanStatus({ text: `失败：${error.message}`, type: "error" });
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

  const shareAsset = async (assetId, shared) => {
    try {
      const result = await apiFetch(`/api/v1/projects/${projectId}/share`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: assetId, shared }),
      });
      await load();
      const awarded = Number(result?.awarded_points || 0);
      if (shared) {
        setActionStatus({
          text: awarded > 0 ? `成功：已分享到首页样片墙，积分 +${awarded}` : "成功：已分享到首页样片墙",
          type: "success",
        });
      } else {
        setActionStatus({ text: "已取消分享，该样片将从首页样片墙移除。", type: "success" });
      }
    } catch (error) {
      setActionStatus({ text: `失败：${error.message}`, type: "error" });
    }
  };

  const bulkApproveProductImages = async () => {
    if (bulkBusy || !productImagePendingAssets.length) return;
    try {
      setBulkBusy(true);
      setActionStatus({ text: `正在批量入选 ${productImagePendingAssets.length} 张候选图...`, type: "" });
      for (const asset of productImagePendingAssets) {
        await apiFetch(`/api/v1/projects/${projectId}/review`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ asset_id: asset.asset_id, action: "approve" }),
        });
      }
      await load();
      setActionStatus({ text: `成功：已批量入选 ${productImagePendingAssets.length} 张图片。`, type: "success" });
    } catch (error) {
      setActionStatus({ text: `失败：${error.message}`, type: "error" });
    } finally {
      setBulkBusy(false);
    }
  };

  const bulkShareApprovedProductImages = async () => {
    if (bulkBusy || !productImageApprovedUnsharedAssets.length) return;
    try {
      setBulkBusy(true);
      setActionStatus({ text: `正在批量分享 ${productImageApprovedUnsharedAssets.length} 张入选图...`, type: "" });
      let awarded = 0;
      for (const asset of productImageApprovedUnsharedAssets) {
        const result = await apiFetch(`/api/v1/projects/${projectId}/share`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ asset_id: asset.asset_id, shared: true }),
        });
        awarded += Number(result?.awarded_points || 0);
      }
      await load();
      setActionStatus({
        text: awarded > 0
          ? `成功：已批量分享 ${productImageApprovedUnsharedAssets.length} 张，积分 +${awarded}。`
          : `成功：已批量分享 ${productImageApprovedUnsharedAssets.length} 张。`,
        type: "success",
      });
    } catch (error) {
      setActionStatus({ text: `失败：${error.message}`, type: "error" });
    } finally {
      setBulkBusy(false);
    }
  };

  const downloadProductImageArchive = async (scope) => {
    const safeScope = ["generated", "approved", "shared"].includes(scope) ? scope : "generated";
    try {
      setDownloadingArchiveScope(safeScope);
      setActionStatus({ text: `正在打包${safeScope === "approved" ? "已入选" : safeScope === "shared" ? "已分享" : "全部"}图片，请稍候...`, type: "" });
      const response = await fetch(`/api/v1/projects/${projectId}/download-images?scope=${safeScope}`, {
        credentials: "include",
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "打包下载失败");
      }
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") || "";
      const matched = /filename="([^"]+)"/.exec(disposition);
      const filename = matched?.[1] || `${projectId}-${safeScope}.zip`;
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setActionStatus({ text: `成功：${filename} 已开始下载。`, type: "success" });
    } catch (error) {
      setActionStatus({ text: `失败：${error.message}`, type: "error" });
    } finally {
      setDownloadingArchiveScope("");
    }
  };

  const sourceImage = project?.image_public_url || localPathToMedia(project?.image_path || "");
  const crumb = breadcrumbs({ page: "project", toolSlug: tool.slug, projectId }, project?.brief?.product_name || "");
  const stepIconForIndex = (idx) => {
    if (idx === 0) return "assets";
    if (tool.slug === "multi-angle-camera" && idx === 1) return "cube";
    if (idx === identityStepIndex) return "user";
    if (idx === generationStepIndex) return tool.category === "video" ? "video" : "camera";
    if (idx === tool.steps.length - 1) return "task";
    return "wand";
  };
  const progressStageText = stageLabel(progress?.current_stage, tool.slug);
  const progressPercentText = `${progress?.progress_percent_weighted ?? 0}%`;
  const progressStatusText = STATUS_LABEL[progress?.task_status] || progress?.task_status || "-";
  const nextActionText = progress?.next_action || "按当前步骤主按钮继续流程。";
  const visibleStepIndexes = useMemo(() => {
    if (tool.slug === "model-retouch") {
      return tool.steps.map((_, idx) => idx).filter((idx) => idx !== 1);
    }
    return tool.steps.map((_, idx) => idx);
  }, [tool.slug, tool.steps]);
  const visibleStepTotal = visibleStepIndexes.length;
  const visibleStepPos = Math.max(1, visibleStepIndexes.indexOf(step) + 1);
  const reviewedAssetsCount = generatedAssets.filter((asset) => assetReviewBucket(asset) === "approved").length;
  const failedAssetsCount = generatedAssets.filter((asset) => assetReviewBucket(asset) === "failed").length;
  const pendingAssetsCount = Math.max(0, generatedAssets.length - reviewedAssetsCount - failedAssetsCount);
  const sharedAssetsCount = generatedAssets.filter((asset) => Boolean(asset?.metadata?.showcase_shared)).length;
  const sharePointsInProject = generatedAssets.reduce((total, asset) => total + Number(asset?.metadata?.share_reward_points || 0), 0);
  const productImagePendingAssets = generatedAssets.filter((asset) => assetReviewBucket(asset) === "pending");
  const productImageApprovedUnsharedAssets = generatedAssets.filter(
    (asset) => assetReviewBucket(asset) === "approved" && !Boolean(asset?.metadata?.showcase_shared),
  );
  const generatedAssetsInFilter = generatedAssets.filter((asset) => generateFilter === "all" || assetReviewBucket(asset) === generateFilter);
  const reviewAssetsInFilter = generatedAssets.filter((asset) => reviewFilter === "all" || assetReviewBucket(asset) === reviewFilter);

  return (
    <div className="content-stack">
      <div className="breadcrumb">{crumb.join(" / ")}</div>
      <section className="card">
        <div className="toolbar" style={{ justifyContent: "space-between" }}>
          <div>
            <h1 className="title-row"><Icon name={toolIconName(tool)} size={20} />{tool.title} · 工作台</h1>
            <div className="muted">项目ID：{projectId}</div>
          </div>
          <div className="toolbar">
            <button type="button" className="btn-secondary" onClick={load}>刷新</button>
            <button type="button" className="btn-ghost" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>返回任务中心</button>
          </div>
        </div>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        <div className={cx("status-banner", actionStatus.type)}>{actionStatus.text}</div>
      </section>

      <section className="card workflow-stepper-card">
        <div className="workflow-stepper-head">
          <h3 className="title-row"><Icon name="task" size={16} />{tool.title} 流程进度</h3>
          <div className="muted">当前步骤 {visibleStepPos} / {visibleStepTotal}</div>
        </div>
        <div className="workflow-stepper-track" role="tablist" aria-label={`${tool.title} 流程步骤`}>
          {visibleStepIndexes.map((idx) => {
            const label = tool.steps[idx];
            const isActive = idx === step;
            const isDone = idx < step;
            return (
              <button
                key={`${label}-${idx}`}
                type="button"
                role="tab"
                aria-selected={isActive}
                className={cx("workflow-step-chip", isActive && "active", isDone && "done")}
                onClick={() => setStep(idx)}
              >
                <span className="workflow-step-index">{visibleStepIndexes.indexOf(idx) + 1}</span>
                <span className="workflow-step-icon"><Icon name={stepIconForIndex(idx)} size={12} /></span>
                <span className="workflow-step-label">{label}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="card workspace-meta-strip">
        <div className="workspace-meta-grid">
          <div className="workspace-meta-chip">
            <Icon name="task" size={15} />
            <div>
              <div className="muted">当前阶段</div>
              <strong>{progressStageText}</strong>
            </div>
          </div>
          <div className="workspace-meta-chip">
            <Icon name="dashboard" size={15} />
            <div>
              <div className="muted">综合进度</div>
              <strong>{progressPercentText}</strong>
            </div>
          </div>
          <div className="workspace-meta-chip">
            <Icon name="spark" size={15} />
            <div>
              <div className="muted">任务状态</div>
              <strong>{progressStatusText}</strong>
            </div>
          </div>
          <div className="workspace-meta-chip workspace-meta-chip-wide">
            <Icon name="wand" size={15} />
            <div>
              <div className="muted">下一步建议</div>
              <strong>{nextActionText}</strong>
            </div>
          </div>
        </div>
      </section>

      <div className="content-stack">
          {step === 0 && (
            <section className="card workflow-panel">
              <div className="workflow-panel-head">
                <div className="step-kicker">STEP 1</div>
                <h2 className="title-row"><Icon name={stepIconForIndex(0)} size={18} />{tool.steps[0]}</h2>
              </div>
              <div className="status-banner">
                {tool.slug === "multi-angle-camera"
                  ? "上传完成后直接进入机位控制，调整角度并生成当前视角。"
                  : (
                    progress?.next_action
                    || (tool.slug === "product-image"
                      ? "下一步：生成组图拍摄方案，确认镜头后开始试拍。"
                      : tool.slug === "model-retouch"
                        ? "下一步：先进入模特确认，确认后再执行单图精修。"
                        : "下一步：生成方案或继续当前流程。")
                  )}
              </div>
              <div className="toolbar" style={{ marginTop: 8 }}>
                {tool.slug === "multi-angle-camera" ? (
                  <button type="button" className="btn-primary" onClick={() => setStep(1)}>
                    进入机位控制
                  </button>
                ) : tool.slug === "product-image" ? (
                  <>
                    {!project?.project_plan?.shots?.length ? (
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={async () => {
                          setStep(1);
                          await genPlan();
                        }}
                        disabled={!project || isInitializing || isPlanLoading}
                      >
                        {isPlanLoading ? "方案生成中，请稍等..." : isInitializing ? "初始化中..." : "生成拍摄方案"}
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => setStep(1)}
                        disabled={isInitializing}
                      >
                        查看拍摄方案
                      </button>
                    )}
                  </>
                ) : tool.slug === "model-retouch" ? (
                  <>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={async () => {
                        const next = project?.identity_status === "confirmed" ? generationStepIndex : identityStepIndex;
                        if (!project?.project_plan?.shots?.length && !isPlanLoading) {
                          await genPlan();
                        }
                        setStep(next >= 0 ? next : generationStepIndex);
                      }}
                      disabled={!project || isInitializing || isPlanLoading}
                    >
                      {isPlanLoading
                        ? "准备中：生成精修约束..."
                        : project?.identity_status === "confirmed"
                          ? "进入单张精修"
                          : "进入模特确认"}
                    </button>
                  </>
                ) : (
                  <>
                    <button type="button" className="btn-primary" onClick={runNextAction} disabled={runningNext || isPlanLoading}>
                      {runningNext
                        ? "执行中：推进中..."
                        : isPlanLoading
                          ? "执行中：方案生成中..."
                        : !project?.project_plan?.shots?.length
                          ? "生成AI方案"
                          : !project?.prompt_pack
                            ? "编译提示词"
                            : "一键继续"}
                    </button>
                  </>
                )}
              </div>
              {!project ? (
                <div className="empty-state">加载中...</div>
              ) : (
                <div className="grid">
                  <div className="asset-card">
                    <h4 className="title-row"><Icon name="dashboard" size={14} />基础信息</h4>
                    <div className="muted">{tool.slug === "model-retouch" ? "批次" : "产品"}：{project.brief?.product_name || "-"}</div>
                    <div className="muted">模板：{templateLabel(project.template_name)}</div>
                    <div className="muted">质量：{qualityLabel(project.quality_level)}</div>
                    <div className="muted">更新时间：{formatDate(project.updated_at)}</div>
                  </div>
                  <div className="asset-card">
                    <h4 className="title-row"><Icon name="task" size={14} />任务状态</h4>
                    <div className="muted">阶段：{stageLabel(progress?.current_stage, tool.slug)}</div>
                    <div className="muted">进度：{progress?.progress_percent_weighted ?? 0}%</div>
                    <div className="muted">状态：{STATUS_LABEL[progress?.task_status] || progress?.task_status || "-"}</div>
                  </div>
                  {tool.slug === "product-image" && (
                    <div className="asset-card">
                      <h4 className="title-row"><Icon name="cube" size={14} />交付配置</h4>
                      <div className="muted">目标成片：{requiredFinalCount || 0} 张</div>
                      <div className="muted">每方案试拍：{Number(project?.set_config?.takes_per_shot || options.candidates_per_prompt || 1)} 张</div>
                      <div className="muted">候选池：{progress?.candidate_total ?? candidatePoolCount} 张</div>
                    </div>
                  )}
                  <div className="asset-card">
                    <h4 className="title-row"><Icon name="camera" size={14} />主素材</h4>
                    {sourceImage ? <img src={sourceImage} alt="source" loading="lazy" decoding="async" /> : <div className="empty-state">无素材</div>}
                  </div>
                </div>
              )}
            </section>
          )}

          {step === 1 && tool.slug !== "model-retouch" && (
            <section className="card workflow-panel">
              <div className="workflow-panel-head">
                <div className="step-kicker">STEP 2</div>
                <h2 className="title-row"><Icon name={stepIconForIndex(1)} size={18} />{tool.steps[1]}</h2>
              </div>
              {tool.slug === "model-retouch" && (
                <>
                  <div className="status-banner">
                    当前页只确认「当前单图」的精修策略。若开启了替换模特，确认后会先进入身份确认，再开始精修。
                  </div>
                  <div className="toolbar" style={{ marginTop: 10 }}>
                    {!project?.project_plan?.shots?.length ? (
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={genPlan}
                        disabled={isInitializing || isPlanLoading}
                      >
                        {isPlanLoading ? "方案生成中..." : isInitializing ? "初始化中..." : "生成精修方案"}
                      </button>
                    ) : (
                      <button type="button" className="btn-primary" onClick={confirmPlanAndProceed} disabled={savingPlan}>
                        {savingPlan
                          ? "提交中：确认中..."
                          : project?.identity_required && project?.identity_status !== "confirmed"
                            ? "确认方案并进入身份确认"
                            : "确认方案并进入精修"}
                      </button>
                    )}
                    <button type="button" className="btn-secondary" onClick={() => genPlan()} disabled={isInitializing || isPlanLoading}>
                      重新生成方案
                    </button>
                  </div>
                </>
              )}
              {tool.slug === "model-retouch" && batchTasks.length > 0 && (
                <div className="asset-card" style={{ marginBottom: 12 }}>
                  <div className="toolbar" style={{ justifyContent: "space-between" }}>
                    <strong>本批次任务（{batchTasks.length}）</strong>
                    <button type="button" className="btn-ghost" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>回任务中心</button>
                  </div>
                  <div className="muted">每张图都是独立精修任务，点击卡片即可切换查看该张。</div>
                  <div className="retouch-wall" style={{ marginTop: 8 }}>
                    {batchTasks.map((task) => (
                      (() => {
                        const isCurrentTask = task.project_id === projectId;
                        const viewPath = `/app/tools/${tool.slug}/projects/${task.project_id}`;
                        return (
                      <article
                        key={task.project_id}
                        className="asset-card"
                        style={isCurrentTask ? { borderColor: "#2563eb", boxShadow: "0 0 0 2px rgba(37,99,235,0.15)" } : undefined}
                        onClick={() => {
                          if (!isCurrentTask) navigate(viewPath);
                        }}
                      >
                        <div><strong>{task.product_name}</strong></div>
                        <div className="muted">当前阶段：{stageLabel(task.current_stage, tool.slug)}</div>
                        <div className="muted">进度：{task.progress_percent}%</div>
                        <div className="toolbar" style={{ marginTop: 8 }}>
                          <span className="badge">{STATUS_LABEL[task.status] || task.status}</span>
                          <button
                            type="button"
                            className="btn-secondary"
                            disabled={isCurrentTask}
                            onClick={(event) => {
                              event.stopPropagation();
                              if (!isCurrentTask) navigate(viewPath);
                            }}
                          >
                            {isCurrentTask ? "当前查看" : "查看该图"}
                          </button>
                        </div>
                      </article>
                        );
                      })()
                    ))}
                  </div>
                </div>
              )}
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
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={isProjectRunning}
                      onClick={async () => {
                        try {
                          await startMultiAngleGenerationFlow({ auto: false });
                        } catch (error) {
                          setPlanStatus({ text: error.message, type: "error" });
                        }
                      }}
                    >
                      {isProjectRunning ? "执行中：生成中..." : "开始生成当前角度"}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  {tool.slug === "intro-video" && (
                    <div className="asset-card" style={{ marginBottom: 12 }}>
                      <div className="toolbar" style={{ justifyContent: "space-between" }}>
                        <h3 className="title-row"><Icon name="video" size={16} />主脚本预览</h3>
                        <span className="badge">
                          {introScriptOptions.length ? `候选 ${introScriptOptions.length} 套` : "等待脚本候选"}
                        </span>
                      </div>
                      {!introScriptOptions.length ? (
                        <div className="status-banner warning" style={{ marginTop: 8 }}>
                          当前没有脚本候选，请先点击主按钮生成脚本候选。
                        </div>
                      ) : (
                        <div className="asset-grid" style={{ marginTop: 10 }}>
                          {introScriptOptions.map((script) => {
                            const active = (project?.selected_script?.script_id || introSelectedScriptId) === script.script_id;
                            return (
                              <article
                                key={script.script_id}
                                className="asset-card"
                                style={active ? { borderColor: "#2563eb", boxShadow: "0 0 0 2px rgba(37,99,235,0.15)" } : undefined}
                              >
                                <div className="toolbar" style={{ justifyContent: "space-between" }}>
                                  <strong>{script.title || "未命名脚本"}</strong>
                                  <span className="badge">{active ? "当前主脚本" : script.format_type}</span>
                                </div>
                                <div className="muted" style={{ marginTop: 6 }}>
                                  总时长 {script.total_duration_sec}s · 镜头 {script.shots?.length || 0} 个
                                </div>
                                <div className="muted" style={{ marginTop: 4 }}>{script.strategy_note || "暂无策略说明"}</div>
                                <div className="toolbar" style={{ marginTop: 8 }}>
                                  <button
                                    type="button"
                                    className="btn-secondary"
                                    disabled={scriptSelecting || active}
                                    onClick={() => selectIntroScript(script.script_id)}
                                  >
                                    {active ? "已选中" : "设为主脚本"}
                                  </button>
                                </div>
                              </article>
                            );
                          })}
                        </div>
                      )}
                      {selectedIntroScript?.shots?.length ? (
                        <div className="asset-grid" style={{ marginTop: 10 }}>
                          {selectedIntroScript.shots.slice(0, 4).map((shot, idx) => (
                            <article key={shot.shot_id || `${selectedIntroScript.script_id}-${idx}`} className="asset-card">
                              <strong>镜头 {idx + 1} · {shot.stage || "hook"}</strong>
                              <div className="muted" style={{ marginTop: 6 }}>{shot.narration || "暂无口播描述"}</div>
                              <div className="muted">时长 {shot.duration_sec || 0}s</div>
                            </article>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  )}
                  <details className="details">
                    <summary>{tool.slug === "model-retouch" ? "精修偏好（可选）" : "方案偏好（可选）"}</summary>
                    <div className="grid" style={{ marginTop: 10 }}>
                      <div className="field"><label>{preferenceLabels.goal}</label><input value={promptInputs.goal} onChange={(event) => setPromptInputs((prev) => ({ ...prev, goal: event.target.value }))} /></div>
                      <div className="field"><label>{preferenceLabels.style}</label><input value={promptInputs.style} onChange={(event) => setPromptInputs((prev) => ({ ...prev, style: event.target.value }))} /></div>
                      <div className="field" style={{ gridColumn: "1 / -1" }}><label>{preferenceLabels.focus}</label><input value={promptInputs.shot_focus} onChange={(event) => setPromptInputs((prev) => ({ ...prev, shot_focus: event.target.value }))} /></div>
                      <div className="field" style={{ gridColumn: "1 / -1" }}><label>{preferenceLabels.constraints}</label><input value={promptInputs.constraints} onChange={(event) => setPromptInputs((prev) => ({ ...prev, constraints: event.target.value }))} /></div>
                    </div>
                    <div className="toolbar" style={{ marginTop: 10 }}>
                      <button type="button" className="btn-secondary" onClick={savePrompt}>保存偏好</button>
                    </div>
                  </details>
                  <div className="toolbar" style={{ marginTop: 10 }}>
                    {tool.slug === "product-image" ? (
                      <>
                        {!project?.project_plan?.shots?.length ? (
                          <button
                            type="button"
                            className="btn-primary"
                            onClick={genPlan}
                            disabled={isInitializing || isPlanLoading}
                          >
                            {isPlanLoading ? "方案生成中..." : isInitializing ? "初始化中..." : "生成拍摄方案"}
                          </button>
                        ) : (
                          <>
                            <button type="button" className="btn-primary" onClick={confirmPlanAndProceed} disabled={savingPlan}>
                              {savingPlan ? "提交中：确认中..." : "确认方案并进入试拍"}
                            </button>
                            <button type="button" className="btn-secondary" onClick={() => genPlan()} disabled={isInitializing || isPlanLoading}>
                              重新生成方案
                            </button>
                          </>
                        )}
                      </>
                    ) : tool.slug === "model-retouch" ? null : (
                      tool.slug === "intro-video" ? (
                        <>
                          <button
                            type="button"
                            className="btn-primary"
                            onClick={confirmIntroScriptAndProceed}
                            disabled={isInitializing || isPlanLoading || scriptSelecting}
                          >
                            {isPlanLoading
                              ? "执行中：脚本生成中..."
                              : scriptSelecting
                                ? "提交中：切换主脚本..."
                                : !introScriptOptions.length
                                  ? "生成脚本候选"
                                  : introScriptReady
                                    ? "确认主脚本并准备视频生成"
                                    : "选择主脚本后继续"}
                          </button>
                          {introScriptOptions.length > 0 ? (
                            <button type="button" className="btn-secondary" onClick={genPlan} disabled={isInitializing || isPlanLoading || scriptSelecting}>
                              重新生成脚本候选
                            </button>
                          ) : null}
                        </>
                      ) : (
                        <>
                          {!project?.project_plan?.shots?.length ? (
                            <button type="button" className="btn-primary" onClick={genPlan} disabled={isInitializing || isPlanLoading}>
                              {isPlanLoading ? "方案生成中..." : isInitializing ? "初始化中..." : "生成AI方案"}
                            </button>
                          ) : !project?.prompt_pack ? (
                            <button type="button" className="btn-primary" onClick={derivePrompts} disabled={isInitializing || isPlanLoading}>
                              {isPlanLoading ? "执行方案准备中..." : "生成执行方案"}
                            </button>
                          ) : (
                            <button type="button" className="btn-primary" onClick={() => setStep(generationStepIndex)} disabled={isInitializing || isPlanLoading}>
                              进入候选生成
                            </button>
                          )}
                          {project?.project_plan?.shots?.length ? (
                            <button type="button" className="btn-secondary" onClick={genPlan} disabled={isInitializing || isPlanLoading}>
                              重新生成AI方案
                            </button>
                          ) : null}
                        </>
                      )
                    )}
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
                      <div className="muted">机位控制页用于校准参数，确认后点击“开始生成当前角度”。</div>
                    </div>
                  </>
                ) : (
                  <>
                    <h3>
                      {tool.slug === "product-image"
                        ? "组图拍摄方案（可编辑）"
                        : tool.slug === "model-retouch"
                          ? "精修方案（可预览）"
                          : "当前方案"}
                    </h3>
                    {tool.slug === "model-retouch" && (
                      <div className="status-banner">
                        {batchTotal > 0
                          ? `本批次共 ${batchTotal} 张；当前只在处理其中 1 张。确认当前图后，可切换到下一张继续。`
                          : "当前为单图精修任务，方案仅覆盖当前图片。"}
                      </div>
                    )}
                    {project?.project_plan?.shots?.length ? (
                      tool.slug === "product-image" ? (
                        <>
                          <div className="status-banner">
                            当前方案镜头：{project.project_plan.shots.length} 个 · 目标成片 {requiredFinalCount || 0} 张 · 每镜头试拍 {options.candidates_per_prompt} 张 · 预计候选 {project.project_plan.shots.length * options.candidates_per_prompt} 张
                          </div>
                          <div className="asset-grid" style={{ marginTop: 10 }}>
                            {planDraftShots.map((shot) => (
                              <div className="asset-card" key={shot.shot_id}>
                                <div className="field">
                                  <label>镜头标题</label>
                                  <input value={shot.title} onChange={(event) => updatePlanDraftShot(shot.shot_id, "title", event.target.value)} />
                                </div>
                                <div className="field" style={{ marginTop: 8 }}>
                                  <label>预期用途（主图/场景图/细节图/对比图）</label>
                                  <input value={shot.delivery_purpose || ""} onChange={(event) => updatePlanDraftShot(shot.shot_id, "delivery_purpose", event.target.value)} />
                                </div>
                                <div className="field" style={{ marginTop: 8 }}>
                                  <label>表达意义（为什么拍这张）</label>
                                  <input value={shot.intent} onChange={(event) => updatePlanDraftShot(shot.shot_id, "intent", event.target.value)} />
                                </div>
                                <div className="field" style={{ marginTop: 8 }}>
                                  <label>试拍指令</label>
                                  <textarea value={shot.image_prompt} onChange={(event) => updatePlanDraftShot(shot.shot_id, "image_prompt", event.target.value)} />
                                </div>
                              </div>
                            ))}
                          </div>
                          <div className="toolbar" style={{ marginTop: 10 }}>
                            <button type="button" className="btn-secondary" onClick={savePlanDraft} disabled={savingPlan}>{savingPlan ? "提交中：保存中..." : "仅保存修改"}</button>
                          </div>
                        </>
                      ) : (
                        <div className="asset-grid">
                          {project.project_plan.shots.map((shot) => (
                            <div className="asset-card" key={shot.shot_id}>
                              <strong>{shot.title || shot.shot_id}</strong>
                              {shot.intent ? <div className="muted">{shot.intent}</div> : null}
                              {tool.slug === "model-retouch" ? (
                                <>
                                  {shot.retouch_goal ? <div className="muted">精修目标：{shot.retouch_goal}</div> : null}
                                  {shot.retouch_prompt ? <div className="muted">精修指令：{shot.retouch_prompt}</div> : null}
                                  {shot.identity_lock_rules?.length ? <div className="muted">一致性规则：{shot.identity_lock_rules.join(" / ")}</div> : null}
                                  {shot.local_edit_instructions?.length ? <div className="muted">局部调整：{shot.local_edit_instructions.join(" / ")}</div> : null}
                                  {shot.negative_constraints?.length ? <div className="muted">避免事项：{shot.negative_constraints.join(" / ")}</div> : null}
                                </>
                              ) : (
                                <>
                                  <div className="muted">画面指令：{shot.image_prompt || "-"}</div>
                                  {tool.category === "video" && <div className="muted">视频指令：{shot.video_prompt || "-"}</div>}
                                </>
                              )}
                            </div>
                          ))}
                        </div>
                      )
                    ) : isPlanLoading ? (
                      <>
                        <div className="status-banner">
                          {tool.slug === "model-retouch"
                            ? `方案生成中（预计 1-2 分钟）· 当前图已预留 ${planSlotsToShow} 个修正项（修正项数量不等于批次张数）。`
                            : `方案生成中（预计 1-2 分钟）· 已预留 ${planSlotsToShow} 个镜头位。`}
                        </div>
                        <div className="asset-grid" style={{ marginTop: 10 }}>
                          {Array.from({ length: planSlotsToShow }).map((_, idx) => (
                            <div key={`plan-skeleton-${idx}`} className="asset-card skeleton-card">
                              <div className="skeleton-line" />
                              <div className="skeleton-line short" />
                              <div className="skeleton-block" />
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <div className="empty-state">暂无方案，请先生成。</div>
                    )}
                  </>
                )}
              </div>
            </section>
          )}

          {step === identityStepIndex && (
            <section className="card workflow-panel">
              <div className="workflow-panel-head">
                <div className="step-kicker">STEP {identityStepIndex + 1}</div>
                <h2 className="title-row"><Icon name={stepIconForIndex(identityStepIndex)} size={18} />身份确认</h2>
              </div>
              <div className="muted">可选择“美化上传模特”或“生成新模特”，系统会带着套图和模特锚点完成后续替换精修。</div>
              <div className="grid" style={{ marginTop: 10 }}>
                <div className="field">
                  <label>身份方案</label>
                  <select
                    value={identityDesign.identity_source}
                    onChange={(event) => setIdentityDesign((prev) => ({ ...prev, identity_source: event.target.value }))}
                  >
                    <option value="beautify_uploaded">美化上传模特</option>
                    <option value="generate_new">生成新模特</option>
                  </select>
                </div>
                <div className="field">
                  <label>打光模板</label>
                  <select
                    value={identityDesign.lighting_preset}
                    onChange={(event) => setIdentityDesign((prev) => ({ ...prev, lighting_preset: event.target.value }))}
                  >
                    <option value="softbox_clean">柔光棚拍</option>
                    <option value="window_natural">自然窗光</option>
                    <option value="rim_fashion">轮廓时尚光</option>
                  </select>
                </div>
                <div className="field">
                  <label>景别模板</label>
                  <select
                    value={identityDesign.framing_preset}
                    onChange={(event) => setIdentityDesign((prev) => ({ ...prev, framing_preset: event.target.value }))}
                  >
                    <option value="headshot">近景头像</option>
                    <option value="half_body">半身人像</option>
                    <option value="full_body">全身人像</option>
                  </select>
                </div>
                <div className="field">
                  <label>角度模板</label>
                  <select
                    value={identityDesign.angle_preset}
                    onChange={(event) => setIdentityDesign((prev) => ({ ...prev, angle_preset: event.target.value }))}
                  >
                    <option value="front">正面平视</option>
                    <option value="left_45">左前45°</option>
                    <option value="right_45">右前45°</option>
                    <option value="slight_low">轻微仰拍</option>
                  </select>
                </div>
                <div className="field" style={{ gridColumn: "1 / -1" }}>
                  <label>补充需求（可选）</label>
                  <textarea
                    value={identityDesign.identity_requirements}
                    placeholder="例如：气质更偏轻奢、妆面自然、发丝整洁、肤质不过度磨皮。"
                    onChange={(event) => setIdentityDesign((prev) => ({ ...prev, identity_requirements: event.target.value }))}
                  />
                </div>
                <div className="field" style={{ gridColumn: "1 / -1" }}>
                  <label>
                    <input
                      type="checkbox"
                      checked={identityDesign.preserve_pose}
                      onChange={(event) => setIdentityDesign((prev) => ({ ...prev, preserve_pose: event.target.checked }))}
                    /> 保持原图姿态与服装版型
                  </label>
                </div>
              </div>
              <div className="toolbar" style={{ marginTop: 10 }}>
                {MODEL_IDENTITY_TEMPLATES.map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    className="btn-secondary"
                    onClick={() => setIdentityDesign(item)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="toolbar" style={{ marginTop: 10 }}>
                <span className="badge">当前状态：{project?.identity_status === "confirmed" ? "已确认" : "待确认"}</span>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={!activeIdentityAssetId}
                  onClick={async () => {
                    if (!activeIdentityAssetId) return;
                    await confirmIdentity(activeIdentityAssetId);
                    if (project?.identity_status === "confirmed" || activeIdentityAssetId) {
                      setStep(generationStepIndex);
                    }
                  }}
                >
                  确认锚点并进入下一步
                </button>
                <button type="button" className="btn-secondary" onClick={() => generateIdentityCandidate(false)}>生成身份候选</button>
                <button type="button" className="btn-secondary" onClick={() => generateIdentityCandidate(true)}>重新生成候选</button>
              </div>
              <div className="status-banner" style={{ marginTop: 8 }}>
                当前锚点：{activeIdentityAssetId ? activeIdentityAssetId.slice(0, 8) : "未选择"} · 主操作为“确认锚点并进入下一步”
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
                        {imageUrl ? <img src={imageUrl} alt="identity-candidate" loading="lazy" decoding="async" /> : <div className="empty-state">无预览</div>}
                        <div className="toolbar" style={{ marginTop: 8 }}>
                          <span className="badge">{selected ? "当前锚点" : "候选图"}</span>
                          <button type="button" className="btn-secondary" disabled={selected} onClick={() => confirmIdentity(asset.asset_id)}>
                            {selected ? "已设为锚点" : "设为锚点"}
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {step === generationStepIndex && (
            <section className="card workflow-panel">
              <div className="workflow-panel-head">
                <div className="step-kicker">STEP {generationStepIndex + 1}</div>
                <h2 className="title-row"><Icon name={stepIconForIndex(generationStepIndex)} size={18} />{tool.steps[generationStepIndex]}</h2>
              </div>
              <div className="desktop-stage-shell">
                <div className="desktop-stage-main">
                  <div className="generate-control-deck">
                <div className="generate-control-head">
                  <h3 className="title-row"><Icon name="wand" size={16} />生成控制台</h3>
                  <div className="muted">
                    {tool.category === "video"
                      ? "设置候选与输出规格后提交，系统会持续回填候选视频。"
                      : "设置规格与候选数量后提交，系统会实时回填生成结果。"}
                  </div>
                </div>
                {tool.slug === "product-image" && (
                  <div className="status-banner">
                    当前方案镜头 {project?.project_plan?.shots?.length || 0} × 每方案试拍 {options.candidates_per_prompt} = 预计候选 {expectedCandidateTotal} 张；目标成片 {requiredFinalCount || 0} 张
                  </div>
                )}
                <div className="toolbar generate-control-toolbar">
                {tool.category === "image" ? (
                  tool.slug === "multi-angle-camera" ? (
                    <>
                      <span className="muted">当前角度固定生成 1 张（单次）</span>
                      <label className="muted">比例</label>
                      <select style={{ width: 110 }} value={cameraInputs.aspect_ratio} onChange={(event) => setCameraInputs((prev) => ({ ...prev, aspect_ratio: event.target.value }))}><option value="1:1">1:1</option><option value="4:5">4:5</option><option value="3:4">3:4</option><option value="9:16">9:16</option><option value="16:9">16:9</option></select>
                      <label className="muted">分辨率</label>
                      <select style={{ width: 90 }} value={options.image_resolution} onChange={(event) => setOptions((prev) => ({ ...prev, image_resolution: event.target.value }))}><option value="1K">1K</option><option value="2K">2K</option><option value="4K">4K</option></select>
                      <label className="muted">格式</label>
                      <select style={{ width: 90 }} value={options.image_output_format} onChange={(event) => setOptions((prev) => ({ ...prev, image_output_format: event.target.value }))}><option value="png">png</option><option value="jpg">jpg</option></select>
                    </>
                  ) : (
                    <>
                      <label className="muted">{tool.slug === "product-image" ? "每方案试拍数" : tool.slug === "model-retouch" ? "单图候选数" : "每镜头生图数"}</label>
                      <input style={{ width: 90 }} type="number" min={1} max={4} value={options.candidates_per_prompt} onChange={(event) => setOptions((prev) => ({ ...prev, candidates_per_prompt: Number(event.target.value || 1) }))} />
                      <label className="muted">比例</label>
                      <select style={{ width: 130 }} value={options.image_aspect_ratio} onChange={(event) => setOptions((prev) => ({ ...prev, image_aspect_ratio: event.target.value }))}>
                        {IMAGE_ASPECT_OPTIONS.map((item) => (
                          <option key={item.value} value={item.value}>{item.label}</option>
                        ))}
                      </select>
                      <label className="muted">分辨率</label>
                      <select
                        style={{ width: 90 }}
                        value={options.image_resolution}
                        disabled={options.image_aspect_ratio === "auto"}
                        onChange={(event) => setOptions((prev) => ({ ...prev, image_resolution: event.target.value }))}
                      ><option value="1K">1K</option><option value="2K">2K</option><option value="4K">4K</option></select>
                      {options.image_aspect_ratio === "auto" ? <span className="muted">原图比例模式下不传分辨率</span> : null}
                      <label className="muted">格式</label>
                      <select style={{ width: 90 }} value={options.image_output_format} onChange={(event) => setOptions((prev) => ({ ...prev, image_output_format: event.target.value }))}><option value="png">png</option><option value="jpg">jpg</option></select>
                    </>
                  )
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
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => runGenerate("auto")}
                  disabled={runningGenerate || isProjectRunning}
                >
                  {runningGenerate
                    ? "提交中：正在提交..."
                    : isProjectRunning
                    ? "执行中：生成中..."
                    : tool.slug === "product-image"
                    ? "开始试拍"
                    : tool.slug === "model-retouch"
                    ? "开始精修"
                    : tool.slug === "multi-angle-camera"
                    ? "追加生成"
                    : "开始生成"}
                </button>
                {showRetry && (
                  <button type="button" className="btn-secondary" onClick={retry} disabled={retrying}>{retrying ? "重试中..." : "失败重试"}</button>
                )}
                {tool.slug === "product-image" && hasFailedCandidates && !isProjectRunning && (
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={runningGenerate}
                    onClick={() => runGenerate("regenerate")}
                  >
                    {runningGenerate ? "补拍中..." : "补拍失败项"}
                  </button>
                )}
                </div>
              </div>
                  <div className={cx("status-banner", generateStatus.type)}>{generateStatus.text}</div>
                </div>
                <aside className="desktop-stage-side">
                  <div className="desktop-side-card">
                    <div className="desktop-side-card-head">
                      <h3 className="title-row"><Icon name="dashboard" size={16} />执行摘要</h3>
                      <span className="badge">实时同步</span>
                    </div>
                    <p className="muted">先看当前产出与异常数量，再决定是否补拍、重试或进入结果墙。</p>
                    <div className="generate-metrics">
                <div className="generate-metric">
                  <span className="muted">已生成</span>
                  <strong>{generatedAssets.length}</strong>
                </div>
                <div className="generate-metric">
                  <span className="muted">已通过</span>
                  <strong>{reviewedAssetsCount}</strong>
                </div>
                <div className="generate-metric">
                  <span className="muted">待筛选</span>
                  <strong>{pendingAssetsCount}</strong>
                </div>
                <div className="generate-metric">
                  <span className="muted">异常</span>
                  <strong>{failedAssetsCount}</strong>
                </div>
                    </div>
                  </div>
                  {tool.slug === "product-image" && candidatePoolCount > 0 && (
                    <div className="desktop-side-card desktop-side-card-accent" style={{ marginTop: 12 }}>
                      <div className="toolbar" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
                  <div className="status-banner success" style={{ flex: 1, minWidth: 320 }}>
                    候选已产出，主操作建议：先一键入选，再批量分享/下载交付。
                  </div>
                  <div className="toolbar" style={{ gap: 8 }}>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setStep(tool.steps.length - 1)}
                    >
                      进入选片分享
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={bulkBusy || !productImagePendingAssets.length}
                      onClick={bulkApproveProductImages}
                    >
                      {bulkBusy ? "处理中..." : `一键入选(${productImagePendingAssets.length})`}
                    </button>
                    <button type="button" className="btn-secondary" disabled={downloadingArchiveScope === "generated"} onClick={() => downloadProductImageArchive("generated")}>
                      {downloadingArchiveScope === "generated" ? "打包中..." : "打包下载全部"}
                    </button>
                    <button
                      type="button"
                      className={manualReviewMode ? "btn-secondary" : "btn-ghost"}
                      onClick={() => setManualReviewMode((prev) => !prev)}
                    >
                      {manualReviewMode ? "收起手动筛选" : "手动筛选"}
                    </button>
                  </div>
                      </div>
                    </div>
                  )}
                </aside>
              </div>
              {tool.slug === "product-image" && (
                <div className="result-wall result-wall-spacious" style={{ marginTop: 14 }}>
                  <div className="result-wall-head">
                    <h3 className="title-row"><Icon name="gallery" size={16} />试拍结果（实时回填）</h3>
                    <div className="toolbar">
                      {RESULT_FILTERS.map((filter) => (
                        <button
                          key={filter.key}
                          type="button"
                          className={cx(generateFilter === filter.key ? "btn-primary" : "btn-secondary")}
                          onClick={() => setGenerateFilter(filter.key)}
                        >
                          {filter.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="status-banner">
                    已生成 {candidatePoolCount} / {expectedCandidateTotal} 张 · 当前筛选：{RESULT_FILTERS.find((item) => item.key === generateFilter)?.label || "全部结果"}
                  </div>
                  <div className="shot-group-list" style={{ marginTop: 10 }}>
                    {(() => {
                      const grouped = new Map();
                      for (const asset of generatedAssetsInFilter) {
                        const shotId = asset?.metadata?.shot_id || "unknown";
                        if (!grouped.has(shotId)) grouped.set(shotId, []);
                        grouped.get(shotId).push(asset);
                      }
                      const plannedShots = project?.project_plan?.shots || [];
                      const plannedShotIds = plannedShots.map((shot) => shot.shot_id);
                      const plannedMap = new Map(plannedShots.map((shot) => [shot.shot_id, shot]));
                      const extraShotIds = Array.from(grouped.keys()).filter((id) => !plannedMap.has(id));
                      const orderedShotIds = [...plannedShotIds, ...extraShotIds];
                      return orderedShotIds
                        .filter((shotId) => generateFilter === "all" || (grouped.get(shotId) || []).length > 0)
                        .map((shotId, index) => {
                        const shotAssets = grouped.get(shotId) || [];
                        const shotPlan = plannedMap.get(shotId) || null;
                        const firstMeta = shotAssets[0]?.metadata || {};
                        const title = shotPlan?.title || firstMeta.shot_title || `镜头 ${index + 1}`;
                        const intent = shotPlan?.intent || firstMeta.shot_intent || "";
                        const purpose = resolveDeliveryPurpose(
                          {
                            stage: shotPlan?.stage,
                            delivery_purpose: shotPlan?.delivery_purpose || firstMeta.delivery_purpose || "",
                          },
                          project?.scenario_type,
                        );
                        const expectedCandidates = Number(options.candidates_per_prompt || 1);
                        const approvedInShot = shotAssets.filter((asset) => assetReviewBucket(asset) === "approved").length;
                        const failedInShot = shotAssets.filter((asset) => assetReviewBucket(asset) === "failed").length;
                        const pendingInShot = Math.max(0, shotAssets.length - approvedInShot - failedInShot);
                        return (
                          <section key={shotId} className="shot-row">
                            <div className="shot-info">
                              <div className="badge"><Icon name="camera" size={12} />镜头 {index + 1}</div>
                              <h4>{title}</h4>
                              <div className="muted">{intent || "等待镜头意图回填"}</div>
                              <div className="muted">{purpose ? `用途：${purpose}` : "用途：待定义"}</div>
                              <div className="shot-meta-badges">
                                <span className="badge">候选 {shotAssets.length}/{expectedCandidates}</span>
                                <span className="badge">通过 {approvedInShot}</span>
                                <span className="badge">待筛选 {pendingInShot}</span>
                                <span className="badge">异常 {failedInShot}</span>
                              </div>
                            </div>
                            <div className="shot-candidates">
                              {shotAssets.map((asset) => {
                                const imageUrl = asset.image_url || localPathToMedia(asset.local_path);
                                const bucket = assetReviewBucket(asset);
                                return (
                                  <article key={asset.asset_id} className="asset-card">
                                    {imageUrl ? <img src={imageUrl} alt="candidate" loading="lazy" decoding="async" /> : <div className="empty-state">无预览</div>}
                                    <div className="muted" style={{ marginTop: 6 }}>
                                      {ecommerceCaption(asset, project?.brief?.product_name || "")}
                                    </div>
                                    <div className="toolbar" style={{ marginTop: 8 }}>
                                      <span className={cx("badge", bucket === "failed" && "warning")}>
                                        {bucket === "approved" ? "已入选" : bucket === "failed" ? "异常候选" : "候选"}
                                      </span>
                                      {manualReviewMode && (
                                        <>
                                          <button type="button" className="btn-secondary" onClick={() => reviewAsset(asset.asset_id, "approve")} disabled={bucket === "approved"}>入选</button>
                                          <button type="button" className="btn-danger" onClick={() => reviewAsset(asset.asset_id, "reject")}>淘汰</button>
                                        </>
                                      )}
                                    </div>
                                  </article>
                                );
                              })}
                              {generateFilter === "all" && (() => {
                                const remaining = Math.max(0, expectedCandidates - shotAssets.length);
                                const slots = Math.min(remaining, 3);
                                if (!remaining) return null;
                                return Array.from({ length: slots }).map((_, idx) => (
                                  <div key={`gen-skeleton-${shotId}-${idx}`} className="asset-card skeleton-card">
                                    <div className="skeleton-block" />
                                    <div className="skeleton-line short" />
                                  </div>
                                ));
                              })()}
                            </div>
                          </section>
                        );
                      });
                    })()}
                  </div>
                  {generatedAssetsInFilter.length === 0 && (
                    <div className="empty-state" style={{ marginTop: 8 }}>
                      {candidatePoolCount === 0 ? "暂无候选图，点击“开始试拍”后会逐张回填。" : "当前筛选下暂无结果，切换筛选查看其他结果。"}
                    </div>
                  )}
                </div>
              )}
              {tool.slug !== "product-image" && (
                <div className="result-wall" style={{ marginTop: 12 }}>
                  <div className="result-wall-head">
                    <div className="result-wall-copy">
                      <h3 className="title-row"><Icon name="gallery" size={16} />执行结果（实时回填）</h3>
                      <p className="muted">候选会逐条回填到这里，优先看通过率和异常，再决定下一步。</p>
                    </div>
                    <div className="toolbar result-wall-filters">
                      {RESULT_FILTERS.map((filter) => (
                        <button
                          key={filter.key}
                          type="button"
                          className={cx(generateFilter === filter.key ? "btn-primary" : "btn-secondary")}
                          onClick={() => setGenerateFilter(filter.key)}
                        >
                          {filter.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  {!generatedAssetsInFilter.length ? (
                    <div className="empty-state">
                      {candidatePoolCount === 0 ? "尚未返回结果，执行后会逐条回填。" : "当前筛选下暂无结果，切换筛选查看其他结果。"}
                    </div>
                  ) : (
                    <div className="asset-grid">
                      {generatedAssetsInFilter.map((asset) => {
                        const imageUrl = asset.image_url || localPathToMedia(asset.local_path);
                        const videoUrl = asset.video_url || localPathToMedia(asset.local_path);
                        const bucket = assetReviewBucket(asset);
                        return (
                          <article key={asset.asset_id} className="asset-card">
                            {imageUrl ? <img src={imageUrl} alt="candidate" loading="lazy" decoding="async" /> : videoUrl ? <video src={videoUrl} controls preload="metadata" /> : <div className="empty-state">无预览</div>}
                            <div className="toolbar" style={{ marginTop: 8 }}>
                              <span className={cx("badge", bucket === "failed" && "warning")}>
                                {bucket === "approved" ? "已通过" : bucket === "failed" ? "异常候选" : "待筛选"}
                              </span>
                              {bucket === "failed" && tool.slug === "model-retouch" ? <span className="badge warning">优先排查</span> : null}
                              <button type="button" className="btn-secondary" onClick={() => reviewAsset(asset.asset_id, "approve")} disabled={bucket === "approved"}>通过</button>
                              <button type="button" className="btn-danger" onClick={() => reviewAsset(asset.asset_id, "reject")}>淘汰</button>
                            </div>
                            {bucket === "failed" && tool.slug === "model-retouch" ? (
                              <div className="status-banner warning" style={{ marginTop: 8 }}>
                                这张结果已被系统标记为异常，请优先怀疑：没有稳定使用模特锚点或返回结果不完整。建议先重跑或驳回，不要直接当成正常套图。
                              </div>
                            ) : null}
                            {asset.metadata?.intent_summary && <div className="muted" style={{ marginTop: 6 }}>{asset.metadata.intent_summary}</div>}
                          </article>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </section>
          )}

          {step === tool.steps.length - 1 && (
            <section className="card workflow-panel">
              <div className="workflow-panel-head">
                <div className="step-kicker">STEP {tool.steps.length}</div>
                <h2 className="title-row"><Icon name={stepIconForIndex(tool.steps.length - 1)} size={18} />{tool.steps[tool.steps.length - 1]}</h2>
              </div>
              <div className="review-summary-grid">
                <div className="review-summary-card">
                  <span className="muted">总产物</span>
                  <strong>{generatedAssets.length}</strong>
                </div>
                <div className="review-summary-card">
                  <span className="muted">已入选</span>
                  <strong>{reviewedAssetsCount}</strong>
                </div>
                {tool.slug === "product-image" && (
                  <div className="review-summary-card">
                    <span className="muted">已分享</span>
                    <strong>{sharedAssetsCount}</strong>
                  </div>
                )}
                {tool.slug === "product-image" && (
                  <div className="review-summary-card">
                    <span className="muted">分享积分</span>
                    <strong>{sharePointsInProject}</strong>
                  </div>
                )}
                <div className="review-summary-card">
                  <span className="muted">{tool.slug === "product-image" ? "待筛选" : "待审核"}</span>
                  <strong>{pendingAssetsCount}</strong>
                </div>
                <div className="review-summary-card">
                  <span className="muted">异常</span>
                  <strong>{failedAssetsCount}</strong>
                </div>
              </div>
              <div className="result-wall-head" style={{ marginBottom: 10 }}>
                <div className="result-wall-copy">
                  <h3 className="title-row"><Icon name="task" size={16} />选片分享墙</h3>
                  <p className="muted">先聚焦通过率和异常，再决定分享或打包交付。</p>
                </div>
                <div className="toolbar result-wall-filters">
                  {RESULT_FILTERS.map((filter) => (
                    <button
                      key={filter.key}
                      type="button"
                      className={cx(reviewFilter === filter.key ? "btn-primary" : "btn-secondary")}
                      onClick={() => setReviewFilter(filter.key)}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
              </div>
              {tool.slug === "product-image" && (
                <div className={cx("status-banner", requiredFinalCount > 0 && selectedFinalCount < requiredFinalCount ? "warning" : "success")}>
                  已选成片 {selectedFinalCount}/{requiredFinalCount || "-"} · 候选池 {candidatePoolCount} 张
                  {requiredFinalCount > 0 && selectedFinalCount < requiredFinalCount ? "（未达标，请继续入选）" : "（可交付）"}
                </div>
              )}
              {tool.slug === "model-retouch" && failedAssetsCount > 0 ? (
                <div className="status-banner warning" style={{ marginTop: 10 }}>
                  当前有 {failedAssetsCount} 张结果已被系统标记为异常。异常通常意味着没有稳定命中模特锚点、人物结构异常，或模型返回不完整。请优先处理异常卡片。
                </div>
              ) : null}
              {tool.slug === "product-image" && (
                <div className="toolbar" style={{ marginTop: 10, justifyContent: "space-between", flexWrap: "wrap" }}>
                  <div className="toolbar" style={{ gap: 8 }}>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={bulkBusy || !productImagePendingAssets.length}
                      onClick={bulkApproveProductImages}
                    >
                      {bulkBusy ? "处理中..." : `一键入选剩余(${productImagePendingAssets.length})`}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={bulkBusy || !productImageApprovedUnsharedAssets.length}
                      onClick={bulkShareApprovedProductImages}
                    >
                      {bulkBusy ? "处理中..." : `批量分享到首页(${productImageApprovedUnsharedAssets.length})`}
                    </button>
                  </div>
                  <div className="toolbar" style={{ gap: 8 }}>
                    <button type="button" className="btn-secondary" disabled={downloadingArchiveScope === "approved"} onClick={() => downloadProductImageArchive("approved")}>{downloadingArchiveScope === "approved" ? "打包中..." : "打包下载入选图"}</button>
                    <button type="button" className="btn-secondary" disabled={downloadingArchiveScope === "generated"} onClick={() => downloadProductImageArchive("generated")}>{downloadingArchiveScope === "generated" ? "打包中..." : "打包下载全部"}</button>
                    <button
                      type="button"
                      className={manualReviewMode ? "btn-secondary" : "btn-ghost"}
                      onClick={() => setManualReviewMode((prev) => !prev)}
                    >
                      {manualReviewMode ? "收起单张操作" : "手动微调"}
                    </button>
                  </div>
                </div>
              )}
              {tool.slug === "model-retouch" && project?.batch_stats && (
                <div className="status-banner">
                  批次进度：总数 {project.batch_stats.total_images} · 已完成 {project.batch_stats.done_images} · 失败 {project.batch_stats.failed_images} · 处理中 {project.batch_stats.queued_images}
                </div>
              )}
              {!reviewAssetsInFilter.length ? (
                <div className="empty-state">
                  {generatedAssets.length === 0
                    ? (isProjectRunning ? "生成中，预计 1-3 分钟，请稍候自动刷新。" : "暂无产物，先执行生成。")
                    : "当前筛选下暂无结果，切换筛选查看其他结果。"}
                </div>
              ) : (
                <>
                  <div className="asset-grid">
                    {reviewAssetsInFilter.map((asset) => {
                      const imageUrl = asset.image_url || localPathToMedia(asset.local_path);
                      const videoUrl = asset.video_url || localPathToMedia(asset.local_path);
                      const isPlaceholder = asset.metadata?.source === "original";
                      const bucket = assetReviewBucket(asset);
                      const isShared = Boolean(asset.metadata?.showcase_shared);
                      return (
                        <article key={asset.asset_id} className="asset-card result-asset-card">
                          {imageUrl ? <img src={imageUrl} alt="asset" loading="lazy" decoding="async" /> : videoUrl ? <video src={videoUrl} controls preload="metadata" /> : <div className="empty-state">无预览</div>}
                          <div className="result-asset-body">
                            <div className="result-asset-head">
                              <span className={cx("badge", bucket === "failed" && "warning")}>
                                {bucket === "approved" ? "已通过" : bucket === "failed" ? "异常候选" : "待筛选"}
                              </span>
                              {bucket === "failed" && tool.slug === "model-retouch" ? <span className="badge warning">疑似未稳定命中锚点</span> : null}
                              {isPlaceholder && <span className="badge warning">原图占位</span>}
                            </div>
                            {asset.metadata?.intent_summary && <div className="result-asset-copy muted">{asset.metadata.intent_summary}</div>}
                            {tool.slug === "product-image" && (
                              <div className="muted result-asset-note">
                                {isShared ? "已在首页样片墙展示" : manualReviewMode ? "入选后可分享到首页样片墙" : "可通过顶部“批量分享到首页”快速处理"}
                              </div>
                            )}
                            <div className="toolbar result-asset-actions" style={{ marginTop: 8 }}>
                              {(tool.slug !== "product-image" || manualReviewMode) && (
                                <button type="button" className="btn-secondary" onClick={() => reviewAsset(asset.asset_id, "approve")} disabled={bucket === "approved"}>{tool.slug === "product-image" ? "入选" : "通过"}</button>
                              )}
                              {(tool.slug !== "product-image" || manualReviewMode) && (
                                <button type="button" className="btn-danger" onClick={() => reviewAsset(asset.asset_id, "reject")}>淘汰</button>
                              )}
                              {tool.slug === "product-image" && manualReviewMode && (
                                <button
                                  type="button"
                                  className="btn-secondary"
                                  disabled={!isShared && bucket !== "approved"}
                                  onClick={() => shareAsset(asset.asset_id, !isShared)}
                                >
                                  {isShared ? "取消分享" : "分享到首页 (+2)"}
                                </button>
                              )}
                            </div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                  {tool.slug === "product-image" && manualReviewMode && (
                    <div className="toolbar" style={{ marginTop: 10 }}>
                      <button
                        type="button"
                        className="btn-secondary"
                        disabled={requiredFinalCount > 0 && selectedFinalCount < requiredFinalCount}
                        onClick={() => {
                          if (requiredFinalCount > 0 && selectedFinalCount < requiredFinalCount) {
                            setActionStatus({ text: `选片未达目标：${selectedFinalCount}/${requiredFinalCount}，请继续入选。`, type: "warning" });
                            return;
                          }
                          setActionStatus({ text: `成功：已完成本轮选片分享（已分享 ${sharedAssetsCount} 张）`, type: "success" });
                        }}
                      >
                        完成选片分享
                      </button>
                    </div>
                  )}
                </>
              )}
            </section>
          )}

          <section className="card low-priority-card log-launcher-card">
            <div className="toolbar log-launcher-head" style={{ justifyContent: "space-between" }}>
              <div>
                <h3 className="title-row"><Icon name="task" size={16} />运行日志</h3>
                <div className="muted">默认收起，仅在排查失败或追踪耗时时查看。</div>
              </div>
              <button type="button" className="btn-secondary" onClick={() => setLogDrawerOpen((prev) => !prev)}>
                {logDrawerOpen ? "收起日志" : "查看日志"}（{logs.length}）
              </button>
            </div>
          </section>
          {logDrawerOpen && <button type="button" aria-label="关闭日志抽屉" className="log-drawer-mask" onClick={() => setLogDrawerOpen(false)} />}
          {logDrawerOpen && (
            <aside className="log-drawer" aria-label="运行日志抽屉">
              <div className="log-drawer-head">
                <strong>运行日志（最近 30 条）</strong>
                <button type="button" className="btn-ghost" onClick={() => setLogDrawerOpen(false)}>关闭</button>
              </div>
              {!logs.length ? (
                <div className="empty-state" style={{ marginTop: 8 }}>暂无日志</div>
              ) : (
                <div className="log-drawer-list">
                  {logs.slice().reverse().slice(0, 30).map((item) => (
                    <article key={item.event_id} className="asset-card">
                      <div><strong>{item.stage}</strong> <span className="muted">{formatDate(item.timestamp)}</span></div>
                      <div className="muted">{item.message}</div>
                    </article>
                  ))}
                </div>
              )}
            </aside>
          )}
      </div>
    </div>
  );
}

export default function AppPage() {
  const { route, navigate, ready } = useRouterState();
  const [auth, setAuth] = useState({
    phase: "booting",
    authenticated: false,
    username: "",
    role: "",
    accountStatus: "",
    workspaceId: "",
    pointsBalance: 0,
    error: "",
  });

  const refreshAuth = useCallback(async () => {
    setAuth((prev) => ({ ...prev, phase: "booting", error: "" }));
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 6000);
    try {
      const resp = await fetch("/api/v1/auth/me", { credentials: "include", signal: controller.signal });
      const data = await resp.json().catch(() => ({}));
      if (Boolean(data.authenticated)) {
        setAuth({
          phase: "authenticated",
          authenticated: true,
          username: data.username || "",
          role: data.role || "",
          accountStatus: data.account_status || "",
          workspaceId: data.workspace_id || "",
          pointsBalance: Number(data.points_balance || 0),
          error: "",
        });
      } else {
        setAuth({
          phase: "unauthenticated",
          authenticated: false,
          username: "",
          role: "",
          accountStatus: "",
          workspaceId: "",
          pointsBalance: 0,
          error: "",
        });
      }
    } catch (error) {
      setAuth({
        phase: "error",
        authenticated: false,
        username: "",
        role: "",
        accountStatus: "",
        workspaceId: "",
        pointsBalance: 0,
        error: String(error?.message || "认证检查失败"),
      });
    } finally {
      clearTimeout(timer);
    }
  }, []);

  useEffect(() => { refreshAuth(); }, [refreshAuth]);

  useEffect(() => {
    if (auth.phase === "booting") return;
    if (auth.phase === "unauthenticated" && !["login", "register"].includes(route.page)) navigate("/app/login");
    if (auth.phase === "authenticated" && ["login", "register"].includes(route.page)) navigate("/app/tools");
  }, [auth.phase, route.page, navigate]);

  const logout = async () => {
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" }).catch(() => undefined);
    setAuth({
      phase: "unauthenticated",
      authenticated: false,
      username: "",
      role: "",
      accountStatus: "",
      workspaceId: "",
      pointsBalance: 0,
      error: "",
    });
    navigate("/app/login");
  };

  if (!ready) {
    return (
      <div className="app-main">
        <section className="card"><div className="status-banner">加载应用中...</div></section>
      </div>
    );
  }

  if (route.page === "login") {
    return (
      <LoginPage
        navigate={navigate}
        onLoginSuccess={(username) => {
          setAuth((prev) => ({
            phase: "authenticated",
            authenticated: true,
            username: username || "admin",
            role: prev.role || "",
            accountStatus: prev.accountStatus || "",
            workspaceId: prev.workspaceId || "",
            pointsBalance: prev.pointsBalance || 0,
            error: "",
          }));
          refreshAuth();
        }}
      />
    );
  }
  if (route.page === "register") {
    return <RegisterPage navigate={navigate} />;
  }

  if (auth.phase === "booting") {
    return (
      <div className="app-main">
        <section className="card"><div className="status-banner">加载用户信息...</div></section>
      </div>
    );
  }

  if (auth.phase === "error") {
    return (
      <div className="app-main">
        <section className="card">
          <h1>登录状态异常</h1>
          <div className="status-banner error">{auth.error || "认证服务不可用，请重试。"}</div>
          <div className="toolbar" style={{ marginTop: 10 }}>
            <button type="button" className="btn-primary" onClick={refreshAuth}>重新检查</button>
            <button type="button" className="btn-secondary" onClick={() => navigate("/app/login")}>返回登录</button>
          </div>
        </section>
      </div>
    );
  }

  if (!auth.authenticated) {
    return (
      <div className="app-main">
        <section className="card">
          <div className="status-banner warning">会话已失效，正在跳转登录...</div>
          <div className="toolbar" style={{ marginTop: 10 }}>
            <button type="button" className="btn-primary" onClick={() => navigate("/app/login")}>去登录</button>
          </div>
        </section>
      </div>
    );
  }

  let content = <ToolsHome navigate={navigate} />;
  if (route.page === "assets") {
    content = <AssetsPage navigate={navigate} />;
  } else if (route.page === "billing") {
    content = <BillingPage navigate={navigate} auth={auth} onAuthRefresh={refreshAuth} />;
  } else if (route.page === "users") {
    content = <UsersPage auth={auth} />;
  } else if (route.page === "tasks") {
    const tool = TOOLS[route.toolSlug] || TOOLS["intro-video"];
    content = <ToolTasksPage tool={tool} navigate={navigate} />;
  } else if (route.page === "batch") {
    const tool = TOOLS[route.toolSlug] || TOOLS["model-retouch"];
    if (tool.slug === "model-retouch") {
      content = <ModelRetouchBatchWorkspace batchGroupId={route.batchGroupId} navigate={navigate} />;
    } else {
      content = <ToolTasksPage tool={tool} navigate={navigate} />;
    }
  } else if (route.page === "project") {
    const tool = TOOLS[route.toolSlug] || TOOLS["intro-video"];
    content = <ProjectWorkspace tool={tool} projectId={route.projectId} navigate={navigate} />;
  }

  return (
    <ErrorBoundary>
      <div className="app-shell">
        <TopBar route={route} auth={auth} navigate={navigate} onLogout={logout} />
        <div className="app-workspace">
          <AppSidebar route={route} navigate={navigate} auth={auth} />
          <main className="workspace-main">
            {["assets", "tasks", "batch", "billing", "users"].includes(route.page) && <div className="breadcrumb">{breadcrumbs(route).join(" / ")}</div>}
            {content}
          </main>
        </div>
        <nav className="mobile-tabbar">
          <button type="button" className={cx("mobile-tab-btn", (route.page === "tools" || route.page === "tasks" || route.page === "project" || route.page === "batch") && "active")} onClick={() => navigate("/app/tools")}>工具箱</button>
          <button type="button" className={cx("mobile-tab-btn", route.page === "assets" && "active")} onClick={() => navigate("/app/assets")}>资产中台</button>
          <button type="button" className={cx("mobile-tab-btn", route.page === "billing" && "active")} onClick={() => navigate("/app/billing")}>积分</button>
          {route.toolSlug && (
            <button type="button" className={cx("mobile-tab-btn", (route.page === "tasks" || route.page === "project" || route.page === "batch") && "active")} onClick={() => navigate(`/app/tools/${route.toolSlug}/tasks`)}>任务中心</button>
          )}
        </nav>
      </div>
    </ErrorBoundary>
  );
}
