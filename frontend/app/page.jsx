"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import {
  IdentityDesignFields,
  MODEL_IDENTITY_TEMPLATES,
  identityCandidateStartCopy,
  identityCandidateSuccessCopy,
  identityConfirmSuccessCopy,
  identityMissingUploadWarning,
  identityPrimaryActionState,
  identitySourceNeedsUploadedAsset,
  useIdentityFlowActions,
  useIdentityDesignState,
} from "./identity-flow";
import {
  resolveDeliveryPurpose,
  resolveTaskWorkspacePath,
  STAGE_LABEL,
  TASK_RISK_LABEL,
  resolveTaskRisk,
  stageLabel,
  taskNextActionHint,
  templateLabel,
} from "./workspace-flow";
import {
  resolveProductReferenceEmptyCopy,
  resolveProductReferenceHint,
  resolveProductReferenceLabel,
  resolveProductReferenceReadyCopy,
  resolveProductReferenceType,
} from "./product-reference";
import {
  ACCOUNT_STATUS_LABEL,
  assetKindLabel,
  assetSourceLabel,
  assetStatusLabel,
  ASSET_KIND_LABEL,
  HIDDEN_WEB_TOOL_SLUGS,
  LEDGER_KIND_LABEL,
  PRODUCT_TYPE_OPTIONS,
  QUALITY_LABEL,
  RECHARGE_STATUS_LABEL,
  RETOUCH_BATCH_LANES,
  STATUS_LABEL,
  TASK_RISK_PRIORITY,
  TEMPLATE_LABEL,
  TOOLS,
  TOOL_BY_TYPE,
  TOOL_ICON_MAP,
  TOOL_LIST,
  USER_ROLE_LABEL,
  VISIBLE_TOOL_LIST,
  qualityLabel,
  toolIconName,
} from "./tool-config";
import { ErrorBoundary, Icon } from "./shared-ui";
import {
  applyImageFallback,
  fallbackImageForToolType,
  HOT_SELLING_TRACKS,
  IMAGE_ASPECT_OPTIONS,
  QUICK_VIDEO_CTA_OPTIONS,
  QUICK_VIDEO_CTA_TEXT_BY_STYLE,
  QUICK_VIDEO_NARRATION_OPTIONS,
  QUICK_VIDEO_PACE_OPTIONS,
  QUICK_VIDEO_THEME_FEATURES,
  QUICK_VIDEO_THEME_OPTIONS,
  QUICK_VIDEO_TONE_BY_STYLE,
  RESULT_FILTERS,
  SALES_PACKAGES,
  SHOWCASE_FALLBACK_IMAGES,
  SHOWCASE_TABS,
  STUDIO_SHOWCASE_CASES,
} from "./ui-config";
import { LoginPage, RegisterPage } from "./auth-pages";
import { TopBar } from "./app-shell";
import {
  detectFrontendBuildTag,
  localPathToMedia,
  safeCreateObjectURL,
  safeSessionGet,
  safeSessionRemove,
  safeSessionSet,
  withMediaVersion,
} from "./media-utils";
import {
  apiFetch,
  assetReviewBucket,
  breadcrumbs,
  buildFormDataWithoutFiles,
  buildSafeFormData,
  candidateCaption,
  compressImageFile,
  createClientProjectId,
  cx,
  ecommerceCaption,
  fileLimitForField,
  formatDate,
  formatProgressLabel,
  parseCsv,
  parseRoute,
  selectedFileSummary,
  signOssUpload,
  uploadToOss,
} from "./app-utils";
import { useRouterState } from "./router-state";
import { MultiAnglePad } from "./multi-angle-pad";
import { ToolsHome } from "./tools-home";
import { AssetsPage } from "./assets-page";
import { BillingPage } from "./billing-page";
import { UsersPage } from "./users-page";
import { ToolTasksPage } from "./tool-tasks-page";
import { ModelRetouchBatchWorkspace } from "./model-retouch-batch-workspace";
import { ProjectWorkspace } from "./project-workspace";

const PLAN_TIMEOUT_MS = 120000;

export default function AppPage() {
  const { pathname, route, navigate, ready } = useRouterState();
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

  useEffect(() => {
    if (typeof document === "undefined") return;
    if (route.page === "project" || route.page === "batch") return;
    const cleanup = () => {
      document.querySelectorAll(".log-drawer-mask, .log-drawer").forEach((node) => {
        if (node instanceof HTMLElement) {
          node.style.pointerEvents = "none";
          node.style.opacity = "0";
          node.style.display = "none";
        }
      });
    };
    cleanup();
    const timer = window.setTimeout(cleanup, 80);
    return () => window.clearTimeout(timer);
  }, [route.page, pathname]);

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
    content = <ProjectWorkspace tool={tool} projectId={route.projectId} navigate={navigate} authRole={auth.role} />;
  }

  const useDedicatedProductImageShell = route.page === "project" && route.toolSlug === "product-image";

  if (useDedicatedProductImageShell) {
    return (
      <ErrorBoundary>
        <div className="app-shell app-shell-product-image">
          <main className="workspace-main workspace-main-product-image">
            {content}
          </main>
        </div>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <div className="app-shell">
        <TopBar route={route} auth={auth} navigate={navigate} onLogout={logout} />
        <div className="app-workspace app-workspace-static">
          <main className="workspace-main workspace-main-static">
            {content}
          </main>
        </div>
        <nav className="mobile-tabbar">
          <button type="button" className={cx("mobile-tab-btn", (route.page === "tools" || route.page === "tasks" || route.page === "project" || route.page === "batch") && "active")} onClick={() => navigate("/app/tools")}>工具中心</button>
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
