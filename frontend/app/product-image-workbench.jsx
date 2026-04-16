"use client";

import React from "react";

import { assetReviewBucket, cx, ecommerceCaption, formatDate } from "./app-utils";
import { localPathToMedia, resolveAssetImageSrc } from "./media-utils";
import { Icon } from "./shared-ui";
import { RESULT_FILTERS } from "./ui-config";

function StatusChip({ tone, label }) {
  return (
    <span className={cx("product-status-chip", `tone-${tone || "pending"}`)}>
      <span className="product-status-chip-dot" />
      {label}
    </span>
  );
}

function StaticStepper({ steps, currentStep, descriptions, setStep, canEnterStep, blockedStepMessage, setStepperStatus }) {
  return (
    <div className="product-stepper-shell">
      <div className="product-stepper">
        {steps.map((label, index) => {
          const stepNumber = index + 1;
          const isDone = currentStep > index;
          const isActive = currentStep === index;
          const isLast = index === steps.length - 1;
          return (
            <div key={label} className="product-stepper-slot">
              <button
                type="button"
                onClick={() => {
                  if (!canEnterStep(index)) {
                    setStepperStatus({ text: blockedStepMessage(index), type: "warning" });
                    return;
                  }
                  setStepperStatus({ text: "", type: "" });
                  setStep(index);
                }}
                className={cx("product-stepper-step", isDone && "done", isActive && "active")}
                disabled={!canEnterStep(index)}
              >
                <div className="product-stepper-step-index">
                  {isDone ? "✓" : stepNumber}
                </div>
                <div className="product-stepper-step-copy">
                  <div className="product-stepper-step-title">{label}</div>
                  <div className="product-stepper-step-caption">{descriptions[index] || ""}</div>
                </div>
              </button>
              {!isLast ? (
                <div className={cx("product-stepper-divider", isDone && "done")} />
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MiniLogCard({ logs, logDrawerOpen, setLogDrawerOpen }) {
  const visible = logs.slice(-6).reverse();
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <div className="flex items-center gap-2">
          <Icon name="task" size={12} className="" />
          <span style={{ fontSize: 11, color: "#5A5A6A", fontWeight: 500 }}>运行日志</span>
        </div>
        <button type="button" onClick={() => setLogDrawerOpen((prev) => !prev)} style={{ background: "transparent", border: 0, padding: 0, fontSize: 11, color: "#7A798A" }}>
          {logDrawerOpen ? "收起" : `查看日志（${logs.length}）`}
        </button>
      </div>
      {logDrawerOpen ? (
        <div className="p-3 flex flex-col gap-1.5" style={{ maxHeight: 220, overflowY: "auto" }}>
          {visible.length ? visible.map((log) => (
            <div key={log.event_id} className="flex gap-2 items-start">
              <span style={{ fontSize: 9, color: "#3A3A4A", fontFamily: "monospace", flexShrink: 0, marginTop: 2 }}>
                {formatDate(log.created_at)}
              </span>
              <span style={{ fontSize: 11, color: "#7A798A", lineHeight: 1.4 }}>
                {log.message || log.stage || "日志更新"}
              </span>
            </div>
          )) : <div style={{ fontSize: 11, color: "#5A5A6A" }}>暂无运行日志</div>}
        </div>
      ) : null}
    </div>
  );
}

function ProductImageAssetCard({ asset, status, primaryAction, secondaryAction, dimmed = false }) {
  const imageUrl = resolveAssetImageSrc(asset);
  const assetLabel = asset?.metadata?.delivery_purpose || asset?.metadata?.shot_title || "候选图";
  const assetCaption = ecommerceCaption(asset, "");
  const statusConfig = {
    approved: { label: "完成", color: "#3DBA71", bg: "rgba(61,186,113,0.12)", border: "rgba(61,186,113,0.25)" },
    pending: { label: "生成中", color: "#6B9BFF", bg: "rgba(107,155,255,0.12)", border: "rgba(107,155,255,0.25)" },
    failed: { label: "失败", color: "#E5484D", bg: "rgba(229,72,77,0.12)", border: "rgba(229,72,77,0.25)" },
    rejected: { label: "已淘汰", color: "#7A798A", bg: "rgba(255,255,255,0.06)", border: "rgba(255,255,255,0.08)" },
  };
  const current = statusConfig[status] || statusConfig.pending;
  return (
    <div
      className="group relative rounded-xl overflow-hidden"
      style={{
        background: "#14141A",
        border: `1px solid ${current.border}`,
        boxShadow: "0 14px 34px rgba(0,0,0,0.22)",
      }}
    >
      <div
        className="absolute z-10"
        style={{
          left: 12,
          top: 12,
          right: 12,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 8,
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            maxWidth: "72%",
            padding: "6px 10px",
            borderRadius: 12,
            background: "rgba(12,12,18,0.72)",
            backdropFilter: "blur(8px)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <div style={{ fontSize: 11, color: "#F0EEE8", fontWeight: 600, lineHeight: 1.35 }}>{assetLabel}</div>
          <div style={{ fontSize: 10, color: "#8F8A7D", marginTop: 3 }}>
            {asset?.metadata?.candidate_index ? `候选 ${asset.metadata.candidate_index}` : "试拍候选"}
          </div>
        </div>
        <span
          className="px-2 py-0.5 rounded"
          style={{
            fontSize: 10,
            fontWeight: 600,
            background: current.bg,
            color: current.color,
            border: `1px solid ${current.border}`,
            backdropFilter: "blur(8px)",
          }}
        >
          {current.label}
        </span>
      </div>
      {status === "pending" ? (
        <div
          className="absolute z-10"
          style={{
            left: 12,
            right: 12,
            bottom: 12,
            padding: "8px 10px",
            borderRadius: 12,
            background: "rgba(18,24,38,0.82)",
            border: "1px solid rgba(107,155,255,0.22)",
            backdropFilter: "blur(10px)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Icon name="spark" size={14} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 11, color: "#6B9BFF", fontWeight: 600 }}>生成中</div>
            <div style={{ fontSize: 10, color: "#7A798A", marginTop: 2 }}>等待预览图和结果回填</div>
          </div>
        </div>
      ) : null}
      {status === "failed" ? (
        <div
          className="absolute z-10"
          style={{
            left: 12,
            right: 12,
            bottom: 12,
            padding: "8px 10px",
            borderRadius: 12,
            background: "rgba(42,16,18,0.84)",
            border: "1px solid rgba(229,72,77,0.24)",
            backdropFilter: "blur(10px)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Icon name="spark" size={14} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 11, color: "#E5484D", fontWeight: 600 }}>异常候选</div>
            <div style={{ fontSize: 10, color: "#A98488", marginTop: 2 }}>优先补拍或直接淘汰</div>
          </div>
        </div>
      ) : null}
      {status === "approved" && imageUrl ? (
        <div
          className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity z-10 flex items-end justify-center"
          style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0) 28%, rgba(0,0,0,0.68) 100%)", paddingBottom: 52 }}
        >
          <div className="flex items-center gap-8px" style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={() => window.open(imageUrl, "_blank", "noopener,noreferrer")}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 12px", borderRadius: 10, background: "rgba(255,255,255,0.14)", backdropFilter: "blur(6px)", color: "#fff", border: "1px solid rgba(255,255,255,0.18)", fontSize: 12 }}
            >
              <Icon name="gallery" size={13} />预览
            </button>
            <button
              type="button"
              onClick={() => window.open(imageUrl, "_blank", "noopener,noreferrer")}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 12px", borderRadius: 10, background: "rgba(201,168,76,0.9)", color: "#000", border: "1px solid rgba(201,168,76,0.35)", fontSize: 12, fontWeight: 600 }}
            >
              <Icon name="task" size={13} />下载
            </button>
          </div>
        </div>
      ) : null}
      {imageUrl ? (
        <img
          src={imageUrl}
          alt={asset?.asset_id || "candidate"}
          loading="lazy"
          decoding="async"
          className="w-full object-cover"
          style={{ height: 212, opacity: dimmed ? 0.22 : status === "pending" ? 0.38 : 1 }}
        />
      ) : (
        <div
          className="relative overflow-hidden"
          style={{
            height: 212,
            background: "linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.015))",
          }}
        >
          <div className="absolute" style={{ inset: 14, borderRadius: 14, border: "1px dashed rgba(255,255,255,0.10)" }} />
          <div className="absolute" style={{ left: "50%", top: "50%", width: 74, height: 94, transform: "translate(-50%, -56%)", borderRadius: 20, background: "linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0.04))", border: "1px solid rgba(255,255,255,0.10)" }} />
          <div className="absolute" style={{ left: "50%", top: "calc(50% - 58px)", width: 36, height: 36, transform: "translateX(-50%)", borderRadius: 999, background: status === "failed" ? "rgba(229,72,77,0.12)" : "rgba(107,155,255,0.12)", border: status === "failed" ? "1px solid rgba(229,72,77,0.24)" : "1px solid rgba(107,155,255,0.24)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name={status === "failed" ? "task" : "gallery"} size={14} />
          </div>
          <div className="absolute" style={{ left: 16, right: 16, bottom: 14, fontSize: 11, color: "#7A798A", lineHeight: 1.55 }}>
            {status === "failed" ? "本轮候选返回异常，可继续补拍或直接淘汰。" : status === "pending" ? "候选已入队，等待预览图和结果回填。" : "候选已生成，等待预览回填或直接进入后续操作。"}
          </div>
        </div>
      )}
      <div style={{ padding: "12px 12px 12px", borderTop: "1px solid rgba(255,255,255,0.04)" }}>
        <div style={{ fontSize: 11, color: "#7A798A", lineHeight: 1.6, minHeight: 36 }}>
          {assetCaption}
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 12, marginBottom: primaryAction || secondaryAction ? 10 : 0 }}>
          <span style={{ fontSize: 10, color: "#5A5A6A" }}>
            {asset?.created_at ? formatDate(asset.created_at) : "待回填时间"}
          </span>
          <span style={{ fontSize: 10, color: "#8F8A7D" }}>
            {asset?.asset_id ? asset.asset_id.slice(0, 8) : "待生成"}
          </span>
        </div>
        {(primaryAction || secondaryAction) ? (
          <div className="flex items-center gap-2">
            {primaryAction}
            {secondaryAction}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function WorkbenchVisualPanel({ title, subtitle, tone = "neutral", imageSrc, imageAlt, placeholderTitle, placeholderBody, placeholderBadge, badgeTone = "pending" }) {
  const frameBorder = tone === "accent" ? "rgba(201,168,76,0.22)" : "rgba(255,255,255,0.06)";
  const frameGlow = tone === "accent"
    ? "radial-gradient(circle at top, rgba(201,168,76,0.18), rgba(201,168,76,0) 58%)"
    : "radial-gradient(circle at top, rgba(107,155,255,0.14), rgba(107,155,255,0) 58%)";
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: "#14141A", border: `1px solid ${frameBorder}` }}>
      <div className="p-4 flex items-center justify-between" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div>
          <p style={{ fontSize: 13, color: tone === "accent" ? "#C9A84C" : "#8A8899", fontWeight: tone === "accent" ? 500 : 400 }}>{title}</p>
          {subtitle ? <p style={{ fontSize: 11, color: "#5A5A6A", marginTop: 4 }}>{subtitle}</p> : null}
        </div>
        {placeholderBadge ? <StatusChip tone={badgeTone} label={placeholderBadge} /> : null}
      </div>
      <div className="p-4">
        {imageSrc ? (
          <img src={imageSrc} alt={imageAlt || title} className="w-full rounded-lg object-cover" style={{ height: 320 }} />
        ) : (
          <div
            className="rounded-2xl relative overflow-hidden"
            style={{
              height: 320,
              border: "1px solid rgba(255,255,255,0.07)",
              background: "#101018",
            }}
          >
            <div className="absolute inset-0" style={{ background: frameGlow }} />
            <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0) 35%, rgba(0,0,0,0.36) 100%)" }} />
            <div className="absolute" style={{ inset: 22, borderRadius: 18, border: "1px dashed rgba(255,255,255,0.11)" }} />
            <div className="absolute" style={{ inset: 46, borderRadius: 22, border: "1px solid rgba(255,255,255,0.06)", background: "linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.015))" }} />
            <div className="absolute" style={{ left: "50%", top: "50%", width: 112, height: 144, transform: "translate(-50%, -56%)", borderRadius: 28, background: "linear-gradient(180deg, rgba(255,255,255,0.22), rgba(255,255,255,0.04))", border: "1px solid rgba(255,255,255,0.10)", boxShadow: "0 28px 60px rgba(0,0,0,0.38)" }} />
            <div className="absolute" style={{ left: "50%", top: "calc(50% - 86px)", width: 46, height: 46, transform: "translateX(-50%)", borderRadius: 999, background: "rgba(201,168,76,0.16)", border: "1px solid rgba(201,168,76,0.28)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Icon name="gallery" size={18} />
            </div>
            <div className="absolute" style={{ left: 24, right: 24, bottom: 26 }}>
              <div style={{ fontSize: 13, color: "#F0EEE8", fontWeight: 600 }}>{placeholderTitle}</div>
              <div style={{ fontSize: 11, color: "#7A798A", lineHeight: 1.65, marginTop: 6 }}>{placeholderBody}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SelectionPlaceholderCard({ title, body, label, active = false }) {
  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: "#14141A",
        border: active ? "2px solid rgba(201,168,76,0.45)" : "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="p-3 flex items-center justify-between">
        <span style={{ fontSize: 11, color: "#C9A84C", fontWeight: 600 }}>{label}</span>
        {active ? <span style={{ fontSize: 10, color: "#3DBA71" }}>默认基准</span> : null}
      </div>
      <div className="px-3 pb-3">
        <div
          className="rounded-xl relative overflow-hidden"
          style={{
            height: 180,
            background: "linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.015))",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <div className="absolute" style={{ inset: 14, borderRadius: 16, border: "1px dashed rgba(255,255,255,0.10)" }} />
          <div className="absolute" style={{ left: "50%", top: "50%", width: 76, height: 98, transform: "translate(-50%, -58%)", borderRadius: 20, background: "linear-gradient(180deg, rgba(255,255,255,0.20), rgba(255,255,255,0.05))", border: "1px solid rgba(255,255,255,0.10)" }} />
        </div>
      </div>
      <div style={{ padding: 12, fontSize: 12, color: "#7A798A", lineHeight: 1.55 }}>
        <div style={{ color: "#F0EEE8", fontWeight: 500, marginBottom: 4 }}>{title}</div>
        {body}
      </div>
    </div>
  );
}

function AssetGridPlaceholder({ title, body }) {
  return (
    <div
      className="rounded-xl p-5"
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px dashed rgba(255,255,255,0.10)",
        minHeight: 232,
      }}
    >
      <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 14 }}>
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="rounded-xl overflow-hidden" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ height: 166, background: "linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02))" }} />
            <div className="p-3">
              <div style={{ width: "58%", height: 10, borderRadius: 999, background: "rgba(255,255,255,0.08)" }} />
              <div style={{ width: "82%", height: 8, borderRadius: 999, background: "rgba(255,255,255,0.05)", marginTop: 8 }} />
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 18, fontSize: 13, color: "#F0EEE8", fontWeight: 600 }}>{title}</div>
      <div style={{ marginTop: 6, fontSize: 12, color: "#7A798A", lineHeight: 1.65 }}>{body}</div>
    </div>
  );
}

export function ProductImageWorkbench(props) {
  const {
    tool,
    projectId,
    project,
    progress,
    step,
    setStep,
    load,
    navigate,
    status,
    actionStatus,
    stepperStatus,
    setStepperStatus,
    visibleStepIndexes,
    canEnterStep,
    blockedStepMessage,
    progressStatusText,
    nextActionText,
    originalSourceImage,
    productReferenceImage,
    productReferenceChoices,
    activeProductReferenceAsset,
    activeProductChoiceLabel,
    setSelectedProductReferenceAssetId,
    productImageModelProvider,
    updateProductImageModelProvider,
    productLockMode,
    setProductLockMode,
    productLockCandidateCount,
    setProductLockCandidateCount,
    lockingProduct,
    isProductLockRunning,
    isInitializing,
    generateProductLock,
    confirmProductReference,
    productReferencePersistedUrl,
    productReferenceDisplayLabel,
    planDraftShots,
    isPlanLoading,
    genPlan,
    confirmPlanAndProceed,
    savingPlan,
    savePlanDraft,
    updatePlanDraftShot,
    requiredFinalCount,
    expectedCandidateTotal,
    options,
    runningGenerate,
    isProjectRunning,
    runGenerate,
    showRetry,
    retry,
    retrying,
    hasFailedCandidates,
    generateStatus,
    generatedAssets,
    generatedAssetsInFilter,
    generateFilter,
    setGenerateFilter,
    candidatePoolCount,
    failedAssetsCount,
    pendingAssetsCount,
    reviewedAssetsCount,
    reviewFilter,
    setReviewFilter,
    reviewAssetsInFilter,
    reviewFailedAssets,
    reviewHealthyAssets,
    productImageReviewPrimaryHint,
    selectedFinalCount,
    productImagePendingAssets,
    productImageApprovedUnsharedAssets,
    bulkBusy,
    bulkApproveProductImages,
    bulkShareApprovedProductImages,
    downloadingArchiveScope,
    downloadProductImageArchive,
    manualReviewMode,
    setManualReviewMode,
    reviewAsset,
    sharedAssetsCount,
    sharePointsInProject,
    logs,
    logDrawerOpen,
    setLogDrawerOpen,
  } = props;

  const stepDescriptions = [
    "先看看你上传的东西",
    "AI 看图，帮你定好拍什么",
    "按方案开始出候选",
    "筛选、分享和下载",
  ];
  const currentStepDisplay = step + 1;
  const statusTone = isProjectRunning
    ? "running"
    : progress?.task_status === "completed"
      ? "success"
      : progress?.task_status === "failed"
        ? "failed"
        : step === tool.steps.length - 1
          ? "review"
          : "pending";
  const productName = project?.brief?.product_name || "新建商品棚拍任务";
  const visibleLogs = logs.slice(-6).reverse();
  const stepStatusLine = currentStepDisplay === 1
    ? "看看你的商品，确认后再进入组图拍摄方案。"
    : currentStepDisplay === 2
      ? planDraftShots.length
        ? `方案定好了，当前 ${planDraftShots.length} 个镜头，共 ${expectedCandidateTotal} 张候选。`
        : "AI 看图中，正在帮你定拍什么。"
      : currentStepDisplay === 3
        ? `试拍中，已返回 ${candidatePoolCount}/${expectedCandidateTotal} 张，结果会持续回填。`
        : productImageReviewPrimaryHint;
  const cardPrimaryButtonStyle = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    flex: 1,
    minWidth: 0,
    padding: "9px 12px",
    borderRadius: 10,
    fontSize: 11,
    fontWeight: 700,
    border: "1px solid rgba(212,175,99,0.36)",
    background: "linear-gradient(135deg, #D4AF63, #9E7321)",
    color: "#0F0F15",
    boxShadow: "none",
  };
  const cardSecondaryButtonStyle = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    flex: 1,
    minWidth: 0,
    padding: "9px 12px",
    borderRadius: 10,
    fontSize: 11,
    fontWeight: 500,
    border: "1px solid rgba(255,255,255,0.08)",
    background: "rgba(255,255,255,0.04)",
    color: "#C8C5BC",
  };

  const renderStep1 = () => (
    <div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(340px, 0.9fr)", gap: 24, marginBottom: 24 }}>
        <WorkbenchVisualPanel
          title="你上传的原图"
          subtitle="原图会作为主体识别和参考板生成的输入。"
          imageSrc={originalSourceImage}
          imageAlt="source"
          placeholderTitle="等待上传主体图"
          placeholderBody="这里会显示你上传的原图。上传后，系统会先识别主体，再决定是直接使用原图还是生成标准化参考板。"
        />
        <WorkbenchVisualPanel
          title="当前拍摄基准"
          subtitle="确认后，后续所有方案和试拍都基于这张主体图执行。"
          tone="accent"
          imageSrc={productReferenceImage || originalSourceImage}
          imageAlt="reference"
          placeholderTitle="待确认后续拍摄基准"
          placeholderBody="如果你选择直接用原图，这里会显示原图；如果启用智能参考板，这里会显示新的主体基准。"
          placeholderBadge={activeProductReferenceAsset ? "已锁定主体" : "待确认"}
          badgeTone={activeProductReferenceAsset ? "success" : "pending"}
        />
      </div>

      <div className="rounded-xl p-4 mb-4" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            <div style={{ fontSize: 13, color: "#F0EEE8", fontWeight: 600 }}>参考板策略</div>
            <div style={{ fontSize: 12, color: "#7A798A", marginTop: 4 }}>先决定是直接用原图，还是生成标准化参考板再选。</div>
          </div>
          <StatusChip tone={statusTone} label={progressStatusText} />
        </div>
        <div className="toolbar" style={{ marginTop: 8, flexWrap: "wrap" }}>
          <button type="button" aria-pressed={productImageModelProvider === "self_hosted"} className={cx("btn-secondary", productImageModelProvider === "self_hosted" && "active")} onClick={() => updateProductImageModelProvider("self_hosted")}>自营模型</button>
          <button type="button" aria-pressed={productImageModelProvider === "commercial"} className={cx("btn-secondary", productImageModelProvider === "commercial" && "active")} onClick={() => updateProductImageModelProvider("commercial")}>商业模型</button>
        </div>
        <div className="toolbar" style={{ marginTop: 8, flexWrap: "wrap" }}>
          <button type="button" aria-pressed={productLockMode === "direct"} className={cx("btn-secondary", productLockMode === "direct" && "active")} onClick={() => setProductLockMode("direct")}>直接使用原图</button>
          <button type="button" aria-pressed={productLockMode === "enhance"} className={cx("btn-secondary", productLockMode === "enhance" && "active")} onClick={() => setProductLockMode("enhance")}>智能精修参考板</button>
          {productLockMode === "enhance" ? (
            <>
              <button type="button" aria-pressed={productLockCandidateCount === 1} className={cx("btn-secondary", productLockCandidateCount === 1 && "active")} onClick={() => setProductLockCandidateCount(1)}>1 张</button>
              <button type="button" aria-pressed={productLockCandidateCount === 2} className={cx("btn-secondary", productLockCandidateCount === 2 && "active")} onClick={() => setProductLockCandidateCount(2)}>2 张（默认）</button>
            </>
          ) : null}
        </div>
      </div>

      <div className="rounded-xl p-4 mb-4" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div style={{ fontSize: 14, color: "#F0EEE8", fontWeight: 600 }}>选择后续拍摄基准</div>
            <div style={{ fontSize: 12, color: "#7A798A", marginTop: 4 }}>确认后，后续所有方案和试拍都基于这张主体图执行。</div>
          </div>
          <div style={{ fontSize: 12, color: "#C9A84C" }}>当前选择：{activeProductChoiceLabel}</div>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 16 }}>
          {productReferenceChoices.length ? productReferenceChoices.map((asset) => {
            const assetImage = resolveAssetImageSrc(asset);
            const isActive = asset.asset_id === activeProductReferenceAsset?.asset_id;
            const isOriginal = asset.asset_id === productReferenceChoices[0]?.asset_id;
            return (
              <button
                key={asset.asset_id}
                type="button"
                onClick={() => setSelectedProductReferenceAssetId(asset.asset_id)}
                className="rounded-xl overflow-hidden text-left"
                style={{
                  background: "#14141A",
                  border: isActive ? "2px solid rgba(201,168,76,0.45)" : "1px solid rgba(255,255,255,0.06)",
                  padding: 0,
                }}
              >
                <div className="p-3 flex items-center justify-between">
                  <span style={{ fontSize: 11, color: "#C9A84C", fontWeight: 600 }}>{isOriginal ? "原图" : `候选 ${asset?.metadata?.candidate_index || "-"}`}</span>
                  {isActive ? <span style={{ fontSize: 10, color: "#3DBA71" }}>已选基准</span> : null}
                </div>
                {assetImage ? <img src={assetImage} alt={asset.asset_id} className="w-full object-cover" style={{ height: 180 }} /> : <div className="empty-state" style={{ minHeight: 180 }}>待显示</div>}
                <div style={{ padding: 12, fontSize: 12, color: "#7A798A", lineHeight: 1.55 }}>
                  {isOriginal ? "直接把上传原图作为后续拍摄基准。" : "标准化商品主体参考板，适合减少背景或道具干扰。"}
                </div>
              </button>
            );
          }) : (
            <>
              <SelectionPlaceholderCard title="上传原图" label="原图" active body="直接把你上传的原图当成后续试拍基准，适合主体已经清楚、背景干扰较少的情况。" />
              <SelectionPlaceholderCard title="标准化主体板" label="候选 A" body="系统会生成一张干净、可控的主体参考板，适合后续要批量出多张组图的情况。" />
              <SelectionPlaceholderCard title="精修参考板" label="候选 B" body="适合高反光、复杂包装或画面元素很多的商品，先把主体定准，再进入拍摄方案。" />
            </>
          )}
        </div>
      </div>

      <div className="flex justify-end gap-3">
        {productLockMode === "enhance" && !productReferenceChoices.slice(1).length ? (
          <button
            type="button"
            className="btn-primary"
            onClick={() => generateProductLock(false)}
            disabled={isInitializing || lockingProduct || isProductLockRunning}
          >
            {lockingProduct || isProductLockRunning ? `${productReferenceDisplayLabel}生成中...` : `生成${productLockCandidateCount}张${productReferenceDisplayLabel}`}
          </button>
        ) : (
          <button
            type="button"
            className="btn-primary"
            onClick={async () => {
              if (activeProductReferenceAsset?.asset_id) {
                await confirmProductReference(activeProductReferenceAsset.asset_id);
              }
              setStep(1);
            }}
            disabled={!activeProductReferenceAsset}
          >
            认出来了，去定方案
          </button>
        )}
        <button type="button" className="btn-secondary" onClick={() => generateProductLock(true)} disabled={productLockMode === "direct" || isInitializing || lockingProduct || isProductLockRunning}>
          重新生成参考板
        </button>
        {productReferencePersistedUrl ? (
          <button type="button" className="btn-secondary" onClick={() => window.open(productReferencePersistedUrl, "_blank", "noopener,noreferrer")}>
            预览当前选择
          </button>
        ) : null}
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 0.95fr) minmax(0, 1.05fr)", gap: 24, marginBottom: 24 }}>
        <WorkbenchVisualPanel
          title="AI 看图中间稿"
          subtitle="系统会结合主体图、成片目标和用途，自动生成镜头草稿。"
          imageSrc={productReferenceImage || originalSourceImage}
          imageAlt="plan-source"
          placeholderTitle="等待主体基准进入方案阶段"
          placeholderBody="确认主体后，这里会显示 AI 分析中的中间稿，用来解释为什么会推荐这些镜头和场景。"
        />
        <div className="rounded-xl overflow-hidden flex flex-col" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
            <Icon name="wand" size={14} />
            <span style={{ fontSize: 12, color: "#C9A84C", fontWeight: 500 }}>AI 看出来的拍摄重点</span>
          </div>
          <div className="p-4 flex flex-col gap-2.5 flex-1">
            {(planDraftShots.length ? planDraftShots : [{ shot_id: "empty", title: "待生成方案", intent: "系统会结合主体图、拍摄目标和目标成片数来生成镜头草稿。", delivery_purpose: "等待 AI 输出" }]).slice(0, 4).map((shot, idx) => (
              <div
                key={shot.shot_id || idx}
                className="flex items-start gap-3 p-3 rounded-xl"
                style={{
                  background: planDraftShots.length ? "rgba(201,168,76,0.05)" : "rgba(255,255,255,0.02)",
                  border: planDraftShots.length ? "1px solid rgba(201,168,76,0.14)" : "1px solid rgba(255,255,255,0.04)",
                }}
              >
                <span style={{ fontSize: 16, color: "#C9A84C", lineHeight: 1, flexShrink: 0, marginTop: 2 }}>{idx + 1}</span>
                <div className="flex-1">
                  <div style={{ fontSize: 11, color: "#C9A84C", fontWeight: 600, marginBottom: 4 }}>{shot.delivery_purpose || "拍摄用途"}</div>
                  <div style={{ fontSize: 13, color: "#F0EEE8", fontWeight: 500 }}>{shot.title || `镜头 ${idx + 1}`}</div>
                  <p style={{ fontSize: 12, color: "#8A8899", lineHeight: 1.55, marginTop: 4 }}>{shot.intent || "等待系统生成镜头意图。"}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="px-4 pb-4">
            <div className="flex items-center justify-between mb-1.5">
              <span style={{ fontSize: 11, color: "#5A5A6A" }}>方案进度</span>
              <span style={{ fontSize: 11, color: "#C9A84C" }}>{planDraftShots.length ? `${planDraftShots.length} 个镜头` : "待生成"}</span>
            </div>
            <div className="rounded-full overflow-hidden" style={{ height: 3, background: "rgba(255,255,255,0.06)" }}>
              <div className="h-full rounded-full" style={{ width: `${planDraftShots.length ? 100 : 20}%`, background: "linear-gradient(90deg,#C9A84C,#F5D07A)" }} />
            </div>
          </div>
        </div>
      </div>

      {!planDraftShots.length ? (
        <div className="flex justify-end gap-3">
          <button type="button" className="btn-primary" onClick={genPlan} disabled={isInitializing || isPlanLoading}>
            {isPlanLoading ? "方案生成中..." : "生成 AI 方案"}
          </button>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Icon name="task" size={16} />
              <h2 style={{ fontSize: 15, fontWeight: 600, color: "#F0EEE8" }}>给你定的拍摄方案</h2>
              <span className="px-2 py-0.5 rounded" style={{ fontSize: 10, fontWeight: 600, background: "rgba(201,168,76,0.1)", border: "1px solid rgba(201,168,76,0.25)", color: "#C9A84C" }}>AI 看图自动生成</span>
            </div>
            <div style={{ fontSize: 12, color: "#5A5A6A" }}>镜头 {planDraftShots.length} 个 · 目标成片 {requiredFinalCount || 0} 张</div>
          </div>
          <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16, marginBottom: 16 }}>
            {planDraftShots.map((shot) => (
              <div key={shot.shot_id} className="rounded-xl p-4" style={{ background: "#14141A", border: "2px solid rgba(201,168,76,0.22)" }}>
                <div className="mb-3">
                  <label style={{ fontSize: 11, color: "#5A5A6A", marginBottom: 6, display: "block" }}>镜头名称</label>
                  <input value={shot.title} onChange={(event) => updatePlanDraftShot(shot.shot_id, "title", event.target.value)} className="w-full rounded-lg px-3 py-2 outline-none" style={{ background: "#1A1A24", border: "1px solid rgba(255,255,255,0.1)", color: "#F0EEE8", fontSize: 12 }} />
                </div>
                <div className="mb-3">
                  <label style={{ fontSize: 11, color: "#C9A84C", marginBottom: 6, display: "block" }}>用途</label>
                  <input value={shot.delivery_purpose || ""} onChange={(event) => updatePlanDraftShot(shot.shot_id, "delivery_purpose", event.target.value)} className="w-full rounded-lg px-3 py-2 outline-none" style={{ background: "#1A1A24", border: "1px solid rgba(255,255,255,0.1)", color: "#F0EEE8", fontSize: 12 }} />
                </div>
                <div className="mb-3">
                  <label style={{ fontSize: 11, color: "#C9A84C", marginBottom: 6, display: "block" }}>为什么拍这张</label>
                  <input value={shot.intent} onChange={(event) => updatePlanDraftShot(shot.shot_id, "intent", event.target.value)} className="w-full rounded-lg px-3 py-2 outline-none" style={{ background: "#1A1A24", border: "1px solid rgba(255,255,255,0.1)", color: "#F0EEE8", fontSize: 12 }} />
                </div>
                <div>
                  <label style={{ fontSize: 11, color: "#6B9BFF", marginBottom: 6, display: "block" }}>试拍提示词</label>
                  <textarea value={shot.image_prompt} onChange={(event) => updatePlanDraftShot(shot.shot_id, "image_prompt", event.target.value)} rows={4} className="w-full rounded-lg px-3 py-2 outline-none resize-none" style={{ background: "rgba(107,155,255,0.06)", border: "1px solid rgba(107,155,255,0.25)", color: "#C0C8E0", fontSize: 12, lineHeight: 1.7 }} />
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between p-4 rounded-xl" style={{ background: "rgba(107,155,255,0.06)", border: "1px solid rgba(107,155,255,0.15)" }}>
            <div className="flex items-center gap-5">
              <span style={{ fontSize: 13, color: "#6B9BFF" }}>{planDraftShots.length} 个镜头 · 共 <strong style={{ color: "#F0EEE8" }}>{expectedCandidateTotal}</strong> 张候选</span>
              <span style={{ fontSize: 13, color: "#5A5A6A" }}>约 {Math.ceil(expectedCandidateTotal * 0.28)} 分钟 · 目标成片 <span style={{ color: "#C9A84C" }}>{requiredFinalCount || 0}</span> 张</span>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" className="btn-secondary" onClick={savePlanDraft} disabled={savingPlan}>
                {savingPlan ? "保存中..." : "仅保存修改"}
              </button>
              <button type="button" className="btn-secondary" onClick={() => genPlan()} disabled={isInitializing || isPlanLoading}>
                重新生成方案
              </button>
              <button type="button" className="btn-primary" onClick={confirmPlanAndProceed} disabled={savingPlan}>
                {savingPlan ? "提交中..." : "方案没问题，开始出图"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );

  const renderStep3 = () => (
    <div className="grid gap-6" style={{ gridTemplateColumns: "minmax(0, 1fr) 280px" }}>
      <div className="min-w-0">
        <div className="rounded-xl p-5 mb-4" style={{ background: "#14141A", border: "1px solid rgba(107,155,255,0.22)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.15fr) minmax(260px, 0.85fr)", gap: 18, marginBottom: 18 }}>
            <div className="rounded-xl p-4" style={{ background: "linear-gradient(180deg, rgba(107,155,255,0.05), rgba(107,155,255,0.02))", border: "1px solid rgba(107,155,255,0.18)" }}>
              <div className="flex items-center justify-between gap-4" style={{ marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 11, color: "#6B9BFF", fontWeight: 600, letterSpacing: "0.04em", marginBottom: 6 }}>试拍执行</div>
                  <p style={{ fontSize: 16, fontWeight: 600, color: "#F0EEE8" }}>AI 出图中</p>
                  <p style={{ fontSize: 12, color: "#7A798A", marginTop: 4 }}>
                    这一屏只看候选回填和运行状态，不提前做交付。试拍够了再进入选片分享。
                  </p>
                </div>
                <StatusChip tone={statusTone} label={isProjectRunning ? "进行中" : "待执行"} />
              </div>
              <div
                className="rounded-xl"
                style={{
                  marginTop: 14,
                  padding: "12px 14px",
                  background: "rgba(107,155,255,0.08)",
                  border: "1px solid rgba(107,155,255,0.18)",
                }}
              >
                <div style={{ fontSize: 11, color: "#6B9BFF", fontWeight: 600, marginBottom: 6 }}>当前目标</div>
                <div style={{ fontSize: 13, color: "#F0EEE8", lineHeight: 1.55 }}>
                  先拿到足够候选，再进入选片分享。当前计划 {planDraftShots.length} 个镜头，目标成片 {requiredFinalCount} 张。
                </div>
              </div>
              <div className="rounded-full overflow-hidden" style={{ height: 6, background: "rgba(255,255,255,0.06)", marginTop: 14 }}>
                <div className="h-full rounded-full transition-all" style={{ width: `${expectedCandidateTotal ? (candidatePoolCount / expectedCandidateTotal) * 100 : 0}%`, background: "linear-gradient(90deg,#6B9BFF,#A78BFA)" }} />
              </div>
            </div>
            <div className="rounded-xl p-4" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015))", border: "1px solid rgba(255,255,255,0.06)" }}>
              <div style={{ fontSize: 11, color: "#7A798A", marginBottom: 10 }}>回填进度</div>
              <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
                {[
                  { label: "已返回", value: candidatePoolCount, tone: "#6B9BFF" },
                  { label: "待筛选", value: pendingAssetsCount, tone: "#A78BFA" },
                  { label: "已通过", value: reviewedAssetsCount, tone: "#3DBA71" },
                  { label: "失败", value: failedAssetsCount, tone: "#E5484D" },
                ].map((item) => (
                  <div key={item.label} className="rounded-xl p-3" style={{ background: "#111119", border: "1px solid rgba(255,255,255,0.08)", boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)" }}>
                    <div style={{ fontSize: 11, color: "#5A5A6A" }}>{item.label}</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: item.tone, marginTop: 8 }}>
                      {item.value}
                      {item.label === "已返回" ? <span style={{ fontSize: 12, color: "#5A5A6A", fontWeight: 400 }}> / {expectedCandidateTotal}</span> : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 16, alignItems: "end" }}>
            <div>
              <div className="flex items-center gap-1.5">
                {RESULT_FILTERS.map((filter) => (
                  <button
                    key={filter.key}
                    type="button"
                    onClick={() => setGenerateFilter(filter.key)}
                    className={cx("btn-secondary", "product-filter-btn", generateFilter === filter.key && "active")}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
              <div style={{ fontSize: 11, color: "#5A5A6A", marginTop: 8 }}>
                当前展示 {generatedAssetsInFilter.length} 张候选，试拍阶段只看回填进度，不在这里做交付。
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap justify-end">
              <button type="button" className="btn-primary product-toolbar-btn" onClick={() => runGenerate("auto")} disabled={runningGenerate || isProjectRunning}>
                {runningGenerate ? "提交中..." : isProjectRunning ? "试拍中..." : "开始试拍"}
              </button>
              {showRetry ? <button type="button" className="btn-secondary product-toolbar-btn" onClick={retry} disabled={retrying}>{retrying ? "重试中..." : "失败重试"}</button> : null}
              {hasFailedCandidates ? <button type="button" className="btn-secondary product-toolbar-btn" onClick={() => runGenerate("regenerate")} disabled={runningGenerate}>补拍失败项</button> : null}
            </div>
          </div>
        </div>

        {generatedAssetsInFilter.length ? (
          <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16 }}>
            {generatedAssetsInFilter.map((asset) => {
              const bucket = assetReviewBucket(asset);
              return (
                <ProductImageAssetCard
                  key={asset.asset_id}
                  asset={asset}
                  status={bucket === "approved" ? "approved" : bucket === "failed" ? "failed" : "pending"}
                  primaryAction={bucket === "approved" ? (
                    <button type="button" style={cardPrimaryButtonStyle} onClick={() => setStep(3)}>进入选片分享</button>
                  ) : manualReviewMode ? (
                    <button type="button" style={cardPrimaryButtonStyle} onClick={() => reviewAsset(asset.asset_id, "approve")} disabled={bucket === "approved"}>入选</button>
                  ) : null}
                  secondaryAction={manualReviewMode ? (
                    <button type="button" style={cardSecondaryButtonStyle} onClick={() => reviewAsset(asset.asset_id, "reject")}>淘汰</button>
                  ) : null}
                />
              );
            })}
          </div>
        ) : (
          <AssetGridPlaceholder
            title="试拍候选会在这里持续回填"
            body="开始试拍后，候选图会按镜头逐步出现。试拍阶段只看回填进度，不在这里直接做交付。"
          />
        )}

      </div>

      <div style={{ width: 280, display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="rounded-xl p-4" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.07)" }}>
          <p style={{ fontSize: 11, color: "#5A5A6A", marginBottom: 10 }}>本次任务</p>
          <p style={{ fontSize: 13, fontWeight: 600, color: "#F0EEE8", marginBottom: 12, lineHeight: 1.4 }}>{productName}</p>
          {[
            { label: "拍摄方案", value: `${planDraftShots.length} 个镜头` },
            { label: "输出总数", value: `${expectedCandidateTotal} 张` },
            { label: "目标成片", value: `${requiredFinalCount} 张` },
            { label: "已返回", value: `${candidatePoolCount} 张`, highlight: true },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between py-2" style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <span style={{ fontSize: 12, color: "#5A5A6A" }}>{item.label}</span>
              <span style={{ fontSize: 12, color: item.highlight ? "#C9A84C" : "#C0BEB8", fontWeight: item.highlight ? 600 : 400 }}>{item.value}</span>
            </div>
          ))}
        </div>

        <div className="rounded-xl p-4" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.07)" }}>
          <div className="flex items-center gap-2 mb-2">
            <Icon name="task" size={13} />
            <p style={{ fontSize: 11, color: "#C9A84C", fontWeight: 500 }}>出图中，去忙别的吧</p>
          </div>
          <p style={{ fontSize: 11, color: "#5A5A6A", lineHeight: 1.65, marginBottom: 10 }}>图出完会自动保存，结果不会丢。可以回任务中心或资产中台继续处理。</p>
          <div className="flex flex-col gap-2">
            <button type="button" className="btn-secondary product-sidebar-btn" onClick={() => navigate("/app/assets")}>资产中台看进度</button>
            <button type="button" className="btn-ghost product-sidebar-btn" onClick={() => navigate("/app/tools")}>回工具中心</button>
            <button type="button" className="btn-ghost product-sidebar-btn" onClick={() => navigate("/app/tools/product-image/tasks")}>回商品棚拍任务中心</button>
          </div>
        </div>

        <MiniLogCard logs={visibleLogs} logDrawerOpen={logDrawerOpen} setLogDrawerOpen={setLogDrawerOpen} />
      </div>
    </div>
  );

  const renderStep4 = () => (
    <div className="grid gap-6" style={{ gridTemplateColumns: "minmax(0, 1fr) 280px" }}>
      <div className="min-w-0">
        <div className="rounded-xl p-5 mb-4" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.07)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.2fr) minmax(260px, 0.8fr)", gap: 18, marginBottom: 18 }}>
            <div className="rounded-xl p-4" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015))", border: "1px solid rgba(255,255,255,0.06)" }}>
              <div className="flex items-center justify-between gap-4" style={{ marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 11, color: "#C9A84C", fontWeight: 600, letterSpacing: "0.04em", marginBottom: 6 }}>交付决策</div>
                  <p style={{ fontSize: 16, fontWeight: 600, color: "#F0EEE8" }}>选片分享墙</p>
                  <p style={{ fontSize: 12, color: "#7A798A", marginTop: 4 }}>
                    这一步不再生成新图，只处理交付决策。先清掉异常，再批量入选，再分享或下载。
                  </p>
                </div>
                <StatusChip tone={statusTone} label={progressStatusText} />
              </div>
              <div
                className="rounded-xl"
                style={{
                  marginTop: 14,
                  padding: "12px 14px",
                  background: "rgba(212,175,99,0.08)",
                  border: "1px solid rgba(212,175,99,0.18)",
                }}
              >
                <div style={{ fontSize: 11, color: "#C9A84C", fontWeight: 600, marginBottom: 6 }}>当前主路径</div>
                <div style={{ fontSize: 13, color: "#F0EEE8", lineHeight: 1.55 }}>{productImageReviewPrimaryHint}</div>
              </div>
              <div className="flex items-center gap-8px" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                {[
                  failedAssetsCount > 0 ? { label: `异常 ${failedAssetsCount} 张`, tone: "#E5484D", bg: "rgba(229,72,77,0.10)", border: "rgba(229,72,77,0.18)" } : null,
                  pendingAssetsCount > 0 ? { label: `待筛选 ${pendingAssetsCount} 张`, tone: "#6B9BFF", bg: "rgba(107,155,255,0.10)", border: "rgba(107,155,255,0.18)" } : null,
                  { label: `目标成片 ${requiredFinalCount} 张`, tone: "#C9A84C", bg: "rgba(201,168,76,0.10)", border: "rgba(201,168,76,0.18)" },
                ].filter(Boolean).map((item) => (
                  <span
                    key={item.label}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      padding: "6px 10px",
                      borderRadius: 999,
                      fontSize: 11,
                      color: item.tone,
                      border: `1px solid ${item.border}`,
                      background: item.bg,
                    }}
                  >
                    {item.label}
                  </span>
                ))}
              </div>
            </div>
            <div className="rounded-xl p-4" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015))", border: "1px solid rgba(255,255,255,0.06)" }}>
              <div style={{ fontSize: 11, color: "#7A798A", marginBottom: 10 }}>交付进度</div>
              <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
                {[
                  { label: "已入选", value: reviewedAssetsCount, tone: "#3DBA71" },
                  { label: "待筛选", value: pendingAssetsCount, tone: "#6B9BFF" },
                  { label: "异常", value: failedAssetsCount, tone: "#E5484D" },
                  { label: "已分享", value: sharedAssetsCount, tone: "#C9A84C" },
                ].map((item) => (
                  <div key={item.label} className="rounded-xl p-3" style={{ background: "#111119", border: "1px solid rgba(255,255,255,0.08)", boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)" }}>
                    <div style={{ fontSize: 11, color: "#5A5A6A" }}>{item.label}</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: item.tone, marginTop: 8 }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div>
              <div style={{ fontSize: 11, color: "#7A798A", marginBottom: 8 }}>主动作</div>
              <div className="flex items-center gap-2 flex-wrap">
                {failedAssetsCount > 0 ? <button type="button" className="btn-primary product-toolbar-btn" onClick={() => runGenerate("regenerate")} disabled={runningGenerate || isProjectRunning}>{runningGenerate ? "补拍中..." : `优先补拍异常(${failedAssetsCount})`}</button> : null}
                <button
                  type="button"
                  className={cx("product-toolbar-btn", failedAssetsCount === 0 && productImagePendingAssets.length > 0 ? "btn-primary" : "btn-secondary")}
                  onClick={bulkApproveProductImages}
                  disabled={bulkBusy || !productImagePendingAssets.length}
                >
                  {bulkBusy ? "处理中..." : `一键入选剩余(${productImagePendingAssets.length})`}
                </button>
                <button
                  type="button"
                  className={cx("product-toolbar-btn", failedAssetsCount === 0 && !productImagePendingAssets.length && productImageApprovedUnsharedAssets.length > 0 ? "btn-primary" : "btn-secondary")}
                  onClick={bulkShareApprovedProductImages}
                  disabled={bulkBusy || !productImageApprovedUnsharedAssets.length}
                >
                  {bulkBusy ? "处理中..." : `批量分享到首页(${productImageApprovedUnsharedAssets.length})`}
                </button>
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: "#7A798A", marginBottom: 8 }}>交付动作</div>
              <div className="flex items-center gap-2 flex-wrap">
                <button type="button" className="btn-secondary product-toolbar-btn" disabled={downloadingArchiveScope === "approved"} onClick={() => downloadProductImageArchive("approved")}>{downloadingArchiveScope === "approved" ? "打包中..." : "打包下载入选图"}</button>
                <button type="button" className="btn-ghost product-toolbar-btn" disabled={downloadingArchiveScope === "generated"} onClick={() => downloadProductImageArchive("generated")}>{downloadingArchiveScope === "generated" ? "打包中..." : "打包下载全部"}</button>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-1.5">
            {RESULT_FILTERS.map((filter) => (
              <button
                key={filter.key}
                type="button"
                onClick={() => setReviewFilter(filter.key)}
                className={cx("btn-secondary", "product-filter-btn", reviewFilter === filter.key && "active")}
              >
                {filter.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <span style={{ fontSize: 11, color: "#5A5A6A" }}>
              当前展示 {reviewAssetsInFilter.length} 张候选
            </span>
            <button type="button" className={cx("product-toolbar-btn", manualReviewMode ? "btn-secondary" : "btn-ghost")} onClick={() => setManualReviewMode((prev) => !prev)}>
              {manualReviewMode ? "收起手动微调" : "打开手动微调"}
            </button>
          </div>
        </div>

        {reviewFailedAssets.length ? (
          <div className="rounded-xl p-4 mb-4" style={{ background: "linear-gradient(180deg, rgba(229,72,77,0.08), rgba(229,72,77,0.03))", border: "1px solid rgba(229,72,77,0.2)" }}>
            <div className="flex items-center justify-between gap-3" style={{ marginBottom: 8 }}>
              <div>
                <div style={{ fontSize: 11, color: "#EAA1A4", fontWeight: 600, letterSpacing: "0.04em", marginBottom: 4 }}>异常优先区</div>
                <div style={{ fontSize: 13, color: "#E5484D", fontWeight: 600 }}>异常候选区</div>
              </div>
              <span style={{ fontSize: 11, color: "#EAA1A4", padding: "6px 10px", borderRadius: 999, background: "rgba(229,72,77,0.08)", border: "1px solid rgba(229,72,77,0.16)" }}>
                {reviewFailedAssets.length} 张需优先处理
              </span>
            </div>
            <div style={{ fontSize: 12, color: "#8A8899", marginBottom: 12 }}>先处理异常，再回到正常候选做入选和分享。</div>
            <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16 }}>
              {reviewFailedAssets.map((asset) => (
                <ProductImageAssetCard
                  key={`failed-${asset.asset_id}`}
                  asset={asset}
                  status="failed"
                  dimmed
                  primaryAction={<button type="button" style={cardPrimaryButtonStyle} onClick={() => reviewAsset(asset.asset_id, "approve")}>强制入选</button>}
                  secondaryAction={<button type="button" style={cardSecondaryButtonStyle} onClick={() => reviewAsset(asset.asset_id, "reject")}>淘汰</button>}
                />
              ))}
            </div>
          </div>
        ) : null}

        <div className="rounded-xl p-4" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015))", border: "1px solid rgba(255,255,255,0.07)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 10 }}>
            <div>
              <div style={{ fontSize: 11, color: "#C9A84C", fontWeight: 600, letterSpacing: "0.04em", marginBottom: 4 }}>交付候选区</div>
              <div style={{ fontSize: 13, color: "#F0EEE8", fontWeight: 600 }}>正常候选区</div>
              <div style={{ fontSize: 12, color: "#7A798A", marginTop: 6 }}>先处理异常区，再回到这里做批量入选、分享或下载交付。</div>
            </div>
            <div style={{ fontSize: 11, color: "#C9A84C", whiteSpace: "nowrap", padding: "6px 10px", borderRadius: 999, background: "rgba(201,168,76,0.08)", border: "1px solid rgba(201,168,76,0.16)" }}>
              候选 {reviewHealthyAssets.length} 张
            </div>
          </div>
          {reviewHealthyAssets.length ? (
            <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16 }}>
              {reviewHealthyAssets.map((asset) => {
                const bucket = assetReviewBucket(asset);
                return (
                <ProductImageAssetCard
                  key={asset.asset_id}
                  asset={asset}
                  status={bucket === "approved" ? "approved" : bucket === "failed" ? "failed" : "pending"}
                    primaryAction={manualReviewMode ? <button type="button" style={cardPrimaryButtonStyle} onClick={() => reviewAsset(asset.asset_id, "approve")} disabled={bucket === "approved"}>入选</button> : null}
                    secondaryAction={manualReviewMode ? <button type="button" style={cardSecondaryButtonStyle} onClick={() => reviewAsset(asset.asset_id, "reject")}>淘汰</button> : null}
                  />
                );
              })}
            </div>
          ) : (
            <AssetGridPlaceholder
              title="正常候选会在这里做批量入选和分享"
              body="先处理异常区，再回到这里完成入选、分享或下载。没有候选时，也会保持和静态稿一致的结果墙版式。"
            />
          )}
        </div>
      </div>

      <div style={{ width: 280, display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="rounded-xl p-4" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.07)" }}>
          <p style={{ fontSize: 11, color: "#5A5A6A", marginBottom: 10 }}>交付摘要</p>
          <p style={{ fontSize: 13, fontWeight: 600, color: "#F0EEE8", marginBottom: 12, lineHeight: 1.4 }}>{productName}</p>
          {[
            { label: "目标成片", value: `${requiredFinalCount} 张` },
            { label: "已入选", value: `${selectedFinalCount} 张` },
            { label: "已分享", value: `${sharedAssetsCount} 张` },
            { label: "分享积分", value: `${sharePointsInProject}`, highlight: true },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between py-2" style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <span style={{ fontSize: 12, color: "#5A5A6A" }}>{item.label}</span>
              <span style={{ fontSize: 12, color: item.highlight ? "#C9A84C" : "#C0BEB8", fontWeight: item.highlight ? 600 : 400 }}>{item.value}</span>
            </div>
          ))}
        </div>

        <div className="rounded-xl p-4" style={{ background: "#14141A", border: "1px solid rgba(255,255,255,0.07)" }}>
          <div className="flex items-center gap-2 mb-2">
            <Icon name="gallery" size={13} />
            <p style={{ fontSize: 11, color: "#C9A84C", fontWeight: 500 }}>当前主路径</p>
          </div>
          <p style={{ fontSize: 12, color: "#7A798A", lineHeight: 1.65 }}>{productImageReviewPrimaryHint}</p>
        </div>

        <MiniLogCard logs={visibleLogs} logDrawerOpen={logDrawerOpen} setLogDrawerOpen={setLogDrawerOpen} />
      </div>
    </div>
  );

  return (
    <div className="product-workbench-shell">
      <div className="product-workbench-container">
      <section className="product-workbench-header">
        <div className="product-workbench-breadcrumbs">
          <button type="button" className="product-workbench-breadcrumb-btn" onClick={() => navigate("/app/tools")}>工具中心</button>
          <span className="product-workbench-breadcrumb-sep">/</span>
          <button type="button" className="product-workbench-breadcrumb-btn" onClick={() => navigate(`/app/tools/${tool.slug}/tasks`)}>商品棚拍</button>
          <span className="product-workbench-breadcrumb-sep">/</span>
          <span className="product-workbench-breadcrumb-current">{projectId}</span>
        </div>
        <div className="product-workbench-head">
          <div className="product-workbench-copy">
            <div className="product-workbench-title-row">
              <h1 className="product-workbench-title">{productName}</h1>
              <StatusChip tone={statusTone} label={progressStatusText} />
            </div>
            <div className="product-workbench-subtitle">商品棚拍工作台 · {tool.title}</div>
          </div>
        <div className="product-workbench-actions">
          <button
            type="button"
            className="btn-secondary product-workbench-action-btn"
            onClick={() => navigate("/app/assets")}
          >
            <Icon name="gallery" size={14} />资产中台
          </button>
          <button
            type="button"
            className={cx("btn-secondary product-workbench-action-btn", logDrawerOpen && "active")}
            onClick={() => setLogDrawerOpen((prev) => !prev)}
          >
            <Icon name="task" size={14} />运行日志
          </button>
          <button
            type="button"
            className="btn-ghost product-workbench-action-btn"
            onClick={load}
          >
            刷新
          </button>
          </div>
        </div>

        <StaticStepper
          steps={tool.steps}
          currentStep={step}
          descriptions={stepDescriptions}
          setStep={setStep}
          canEnterStep={canEnterStep}
          blockedStepMessage={blockedStepMessage}
          setStepperStatus={setStepperStatus}
        />

        <div className="product-workbench-status-strip">
          <div className="product-workbench-status-pill primary">{stepStatusLine}</div>
          <div className="product-workbench-status-pill secondary">{nextActionText}</div>
        </div>
      </section>

      {stepperStatus.text ? (
        <div className={cx("status-banner", stepperStatus.type)} style={{ marginTop: 12 }}>
          {stepperStatus.text}
        </div>
      ) : null}

      <div className="product-workbench-stage-stack">
        {currentStepDisplay === 1 ? renderStep1() : null}
        {currentStepDisplay === 2 ? renderStep2() : null}
        {currentStepDisplay === 3 ? renderStep3() : null}
        {currentStepDisplay === 4 ? renderStep4() : null}
      </div>
      </div>
    </div>
  );
}
