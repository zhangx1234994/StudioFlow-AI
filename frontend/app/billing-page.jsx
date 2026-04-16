"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiFetch, cx, formatDate } from "./app-utils";
import { Icon } from "./shared-ui";
import { LEDGER_KIND_LABEL, RECHARGE_STATUS_LABEL, USER_ROLE_LABEL } from "./tool-config";

export function BillingPage({ navigate, auth, onAuthRefresh }) {
  const [summary, setSummary] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [orders, setOrders] = useState([]);
  const [tab, setTab] = useState("overview");
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
      <section className="card page-hero-card billing-hero-card">
        <h1 className="title-row"><Icon name="spark" size={18} />积分中心</h1>
        <p className="card-subtitle">查看余额与积分流水。当前阶段仅支持管理员手动调分，充值接口已预留。</p>
        <div className={cx("status-banner", status.type)}>{status.text}</div>
        <div className="toolbar billing-hero-toolbar" style={{ marginTop: 8 }}>
          <span className="badge">当前用户：{auth.username || "-"}</span>
          <span className="badge">余额：{summary?.balance ?? 0}</span>
          <span className="badge">今日收入：{summary?.today_income ?? 0}</span>
          <span className="badge">今日消耗：{summary?.today_cost ?? 0}</span>
          <span className="badge">待确认充值：{summary?.pending_recharge_count ?? 0}</span>
          <button type="button" className="btn-secondary" onClick={load}>刷新</button>
          <button type="button" className="btn-ghost" onClick={() => navigate("/app/tools")}>返回工具箱</button>
        </div>
      </section>

      <section className="card page-content-card billing-summary-card">
        <div className="page-tab-head">
          <div className="page-tab-strip">
            <button type="button" className={cx("page-tab", tab === "overview" && "active")} onClick={() => setTab("overview")}>积分概览</button>
            <button type="button" className={cx("page-tab", tab === "history" && "active")} onClick={() => setTab("history")}>收支明细</button>
            <button type="button" className={cx("page-tab", tab === "earn" && "active")} onClick={() => setTab("earn")}>获取积分</button>
            <button type="button" className={cx("page-tab", tab === "recharge" && "active")} onClick={() => setTab("recharge")}>充值</button>
          </div>
        </div>
        {tab === "overview" ? (
          <>
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
          </>
        ) : null}
        {tab === "history" ? (
          <div className="billing-tab-empty">
            <h2 className="title-row"><Icon name="assets" size={16} />收支明细</h2>
            <p className="muted">下方保留完整充值订单和积分流水表格，便于核对收支记录。</p>
          </div>
        ) : null}
        {tab === "earn" ? (
          <div className="billing-tab-empty">
            <h2 className="title-row"><Icon name="spark" size={16} />获取积分</h2>
            <p className="muted">优先通过样片分享奖励和管理员活动补贴获取积分，再决定是否充值。</p>
          </div>
        ) : null}
        {tab === "recharge" ? (
          <div className="billing-tab-empty">
            <h2 className="title-row"><Icon name="task" size={16} />充值说明</h2>
            <p className="muted">在线支付接口尚未接入，当前仍以管理员调分和手工确认充值为主。</p>
          </div>
        ) : null}
      </section>

      {(tab === "overview" || tab === "earn") && (
      <section className="card page-content-card billing-insight-card">
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
      )}

      {(tab === "overview" || tab === "recharge") && (
      <section className="card page-content-card billing-recharge-card">
        <h2 className="title-row"><Icon name="task" size={16} />充值通道（预留）</h2>
        <p className="muted">在线支付接口将在后续版本接入。当前请使用管理员账号执行积分调整。</p>
      </section>
      )}

      {auth.role === "admin" && (tab === "overview" || tab === "recharge") && (
        <section className="card page-content-card billing-admin-card">
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

      {(tab === "overview" || tab === "history" || tab === "recharge") && (
      <section className="card page-content-card billing-details-card">
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
      )}

      {(tab === "overview" || tab === "history" || tab === "earn") && (
      <section className="card page-content-card billing-details-card">
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
      )}
    </div>
  );
}
