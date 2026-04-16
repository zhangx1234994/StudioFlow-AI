"use client";

import React, { useEffect, useState } from "react";

import { apiFetch, cx } from "./app-utils";
import { detectFrontendBuildTag } from "./media-utils";
import { resolveTaskWorkspacePath } from "./workspace-flow";
import {
  ACCOUNT_STATUS_LABEL,
  TOOL_BY_TYPE,
  VISIBLE_TOOL_LIST,
  toolIconName,
} from "./tool-config";
import { Icon } from "./shared-ui";

export function TopBar({ route, auth, navigate, onLogout }) {
  const [keyword, setKeyword] = useState("");
  const [buildTag, setBuildTag] = useState("");
  const workspaceLabel = auth.workspaceId
    ? auth.workspaceId === "default_workspace"
      ? "主工作区"
      : auth.workspaceId.replaceAll("_", " ")
    : "主工作区";
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
      navigate(resolveTaskWorkspacePath(rows[0], TOOL_BY_TYPE));
      setKeyword("");
    } catch (_) {
      // no-op
    }
  };

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <a className="brand" href="/app/tools" onClick={(event) => { event.preventDefault(); navigate("/app/tools"); }}>
          <span className="brand-mark">
            <Icon name="spark" size={13} />
          </span>
          <span>AI摄影棚</span>
        </a>
        <nav className="nav-links">
          <a className={cx("nav-link", ["tools", "tasks", "project", "batch"].includes(route.page) && "active")} href="/app/tools" onClick={(event) => { event.preventDefault(); navigate("/app/tools"); }}><Icon name="dashboard" size={14} />工具中心</a>
          <a className={cx("nav-link", route.page === "assets" && "active")} href="/app/assets" onClick={(event) => { event.preventDefault(); navigate("/app/assets"); }}><Icon name="assets" size={14} />资产中台</a>
          <a className={cx("nav-link", route.page === "billing" && "active")} href="/app/billing" onClick={(event) => { event.preventDefault(); navigate("/app/billing"); }}><Icon name="spark" size={14} />积分中心</a>
          {auth.role === "admin" && (
            <a className={cx("nav-link", route.page === "users" && "active")} href="/app/users" onClick={(event) => { event.preventDefault(); navigate("/app/users"); }}><Icon name="task" size={14} />用户管理</a>
          )}
        </nav>
        <div className="topbar-right">
          <div className="topbar-quick-search">
            <input className="quick-jump" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="快速搜索" onKeyDown={(event) => event.key === "Enter" && jump()} />
            <button type="button" className="btn-secondary topbar-mini-btn" onClick={jump}>查找</button>
          </div>
          <div className="topbar-account">
            <span className="topbar-account-avatar">{(auth.username || "A").slice(0, 1).toUpperCase()}</span>
            <span className="topbar-account-name">{auth.username || "未命名账号"}</span>
          </div>
          <div className="topbar-meta">
            <span className="topbar-chip">{accountStatusLabel}</span>
            <span className="topbar-chip">{workspaceLabel}</span>
            <span className="topbar-chip topbar-chip-strong">积分 {pointsLabel}</span>
            {buildTag ? <span className="topbar-version">v{buildTag}</span> : null}
          </div>
          <div className="topbar-actions">
            <button type="button" className="btn-ghost topbar-mini-btn" onClick={onLogout}>退出</button>
          </div>
        </div>
      </div>
    </header>
  );
}

export function AppSidebar({ route, navigate, auth }) {
  const activeTool = route.toolSlug || "";
  return (
    <aside className="app-sidebar">
      <div className="sidebar-card">
        <h3 className="title-row"><Icon name="dashboard" size={16} />工具箱</h3>
        <div className="sidebar-links">
          <button type="button" className={cx("sidebar-link", route.page === "tools" && "active")} onClick={() => navigate("/app/tools")}>总览首页</button>
          <button type="button" className={cx("sidebar-link", route.page === "assets" && "active")} onClick={() => navigate("/app/assets")}>资产中台</button>
          <button type="button" className={cx("sidebar-link", route.page === "billing" && "active")} onClick={() => navigate("/app/billing")}>积分中心</button>
          {auth.role === "admin" && (
            <button type="button" className={cx("sidebar-link", route.page === "users" && "active")} onClick={() => navigate("/app/users")}>用户管理</button>
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
