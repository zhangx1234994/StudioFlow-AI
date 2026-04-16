"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiFetch, cx, formatDate } from "./app-utils";
import { ACCOUNT_STATUS_LABEL, STATUS_LABEL, USER_ROLE_LABEL } from "./tool-config";
import { Icon } from "./shared-ui";

export function UsersPage({ auth }) {
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

  useEffect(() => {
    if (!rows.length) return;
    setUserView((current) => {
      if (current === "abnormal" && abnormalRows.length) return current;
      if (current === "pending" && pendingRows.length) return current;
      if (abnormalRows.length) return "abnormal";
      if (pendingRows.length) return "pending";
      return "all";
    });
  }, [rows, abnormalRows.length, pendingRows.length]);

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
      <section className="card page-hero-card users-hero-card">
        <h1 className="title-row"><Icon name="task" size={18} />用户管理</h1>
        <p className="card-subtitle">这里处理账号启用、角色配置、工作区归属和初始积分。先看异常账号，再做创建与批量修正。</p>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        <div className="users-hero-kpis">
          <div className="users-hero-kpi"><span>异常账号</span><strong>{abnormalRows.length}</strong></div>
          <div className="users-hero-kpi"><span>待处理</span><strong>{pendingRows.length}</strong></div>
          <div className="users-hero-kpi"><span>全部账号</span><strong>{rows.length}</strong></div>
        </div>
      </section>

      <section className="card page-content-card users-create-card">
        <h2 className="title-row"><Icon name="spark" size={16} />创建用户</h2>
        <form ref={createRef} className="grid">
          <div className="field"><label>用户名</label><input name="username" autoComplete="username" placeholder="operator01" /></div>
          <div className="field"><label>密码</label><input name="password" type="password" autoComplete="new-password" placeholder="至少 6 位" /></div>
          <div className="field"><label>邮箱</label><input name="email" type="email" autoComplete="email" placeholder="operator@studioflow.local" /></div>
          <div className="field"><label>显示名</label><input name="display_name" autoComplete="nickname" placeholder="运营同学" /></div>
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

      <section className="card page-content-card users-list-card">
        <div className="page-tab-head">
          <h2 className="title-row"><Icon name="dashboard" size={16} />账号列表</h2>
          <div className="page-tab-strip">
          <button type="button" className={cx("btn-secondary", userView === "abnormal" && "active")} onClick={() => setUserView("abnormal")}>异常账号（{abnormalRows.length}）</button>
          <button type="button" className={cx("btn-secondary", userView === "pending" && "active")} onClick={() => setUserView("pending")}>待处理账号（{pendingRows.length}）</button>
          <button type="button" className={cx("btn-secondary", userView === "all" && "active")} onClick={() => setUserView("all")}>全部账号（{rows.length}）</button>
          </div>
        </div>
        {!visibleRows.length ? (
          <div className="empty-state">
            当前筛选下没有账号。
            {rows.length ? (
              <div className="toolbar" style={{ marginTop: 8 }}>
                <button type="button" className="btn-secondary" onClick={() => setUserView("all")}>查看全部账号</button>
              </div>
            ) : null}
          </div>
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
