"use client";

import React from "react";

import { assetReviewBucket, cx } from "./app-utils";
import { localPathToMedia, resolveAssetImageSrc } from "./media-utils";
import { Icon } from "./shared-ui";
import { RESULT_FILTERS } from "./ui-config";

export function ReviewStagePanel({
  tool,
  stepCount,
  stepIconName,
  generatedAssets,
  reviewedAssetsCount,
  sharedAssetsCount,
  sharePointsInProject,
  pendingAssetsCount,
  failedAssetsCount,
  reviewFilter,
  setReviewFilter,
  requiredFinalCount,
  selectedFinalCount,
  candidatePoolCount,
  productImageReviewPrimaryHint,
  runningGenerate,
  isProjectRunning,
  runGenerate,
  bulkBusy,
  productImagePendingAssets,
  bulkApproveProductImages,
  productImageApprovedUnsharedAssets,
  bulkShareApprovedProductImages,
  downloadingArchiveScope,
  downloadProductImageArchive,
  manualReviewMode,
  setManualReviewMode,
  project,
  reviewAssetsInFilter,
  reviewFailedAssets,
  reviewHealthyAssets,
  reviewAsset,
  shareAsset,
  setActionStatus,
}) {
  const useProductImageVisualRefresh = tool.slug === "product-image";
  const productImagePrimaryAction = tool.slug !== "product-image"
    ? null
    : failedAssetsCount > 0
      ? "retry-failed"
      : productImagePendingAssets.length > 0
        ? "approve-pending"
        : productImageApprovedUnsharedAssets.length > 0
          ? "share-approved"
          : null;

  return (
    <section className={cx("card workflow-panel", useProductImageVisualRefresh && "product-workflow-panel product-review-panel")}>
      <div className="workflow-panel-head">
        <div className="step-kicker">STEP {stepCount}</div>
        <h2 className="title-row"><Icon name={stepIconName} size={18} />{tool.steps[stepCount - 1]}</h2>
      </div>
      {useProductImageVisualRefresh ? (
        <div className="product-step-intro">
          <div className="product-step-intro-kicker">交付筛选</div>
          <div className="product-step-intro-copy">
            先处理异常，再批量入选，最后统一分享或下载交付。手动微调只处理少量边缘结果。
          </div>
        </div>
      ) : null}
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
              className={cx("btn-secondary", reviewFilter === filter.key && "active")}
              onClick={() => setReviewFilter(filter.key)}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>
      {tool.slug === "product-image" && (
        <div className={cx("status-banner", requiredFinalCount > 0 && selectedFinalCount < requiredFinalCount ? "warning" : "success", useProductImageVisualRefresh && "product-stage-status-banner")}>
          已选成片 {selectedFinalCount}/{requiredFinalCount || "-"} · 候选池 {candidatePoolCount} 张
          {requiredFinalCount > 0 && selectedFinalCount < requiredFinalCount ? "（未达标，请继续入选）" : "（可交付）"}
        </div>
      )}
      {tool.slug === "product-image" ? (
        <div className={cx("status-banner", failedAssetsCount > 0 ? "warning" : requiredFinalCount > 0 && selectedFinalCount < requiredFinalCount ? "" : "success", useProductImageVisualRefresh && "product-stage-status-banner")} style={{ marginTop: 10 }}>
          {productImageReviewPrimaryHint}
        </div>
      ) : null}
      {tool.slug === "product-image" && failedAssetsCount > 0 ? (
        <div className={cx("asset-card", useProductImageVisualRefresh && "product-control-card")} style={{ marginTop: 10 }}>
          <h3 className="title-row"><Icon name="spark" size={16} />异常候选处置</h3>
          <div className="status-banner warning" style={{ marginTop: 8 }}>
            当前有 {failedAssetsCount} 张异常候选。建议先只看异常结果，确认问题后直接补拍失败项，避免把原图占位或异常图混进交付。
          </div>
          <div className="toolbar" style={{ marginTop: 10 }}>
            <button type="button" className={cx("btn-secondary", reviewFilter === "failed" && "active")} onClick={() => setReviewFilter("failed")}>
              只看异常({failedAssetsCount})
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={runningGenerate || isProjectRunning}
              onClick={() => runGenerate("regenerate")}
            >
              {runningGenerate ? "补拍中..." : `补拍失败项(${failedAssetsCount})`}
            </button>
          </div>
        </div>
      ) : null}
      {tool.slug === "model-retouch" && failedAssetsCount > 0 ? (
        <div className="status-banner warning" style={{ marginTop: 10 }}>
          当前有 {failedAssetsCount} 张结果已被系统标记为异常。异常通常意味着没有稳定命中你确认的模特来源、人物结构异常，或模型返回不完整。请优先处理异常卡片。
        </div>
      ) : null}
      {tool.slug === "product-image" && (
        <div className="toolbar product-review-action-bar" style={{ marginTop: 10 }} data-cta-scope="workspace.review.product-image">
          <div className="toolbar product-review-action-group">
            {failedAssetsCount > 0 ? (
              <button
                type="button"
                className={productImagePrimaryAction === "retry-failed" ? "btn-primary" : "btn-secondary"}
                disabled={runningGenerate || isProjectRunning}
                onClick={() => runGenerate("regenerate")}
              >
                {runningGenerate ? "补拍中..." : `优先补拍异常(${failedAssetsCount})`}
              </button>
            ) : null}
            <button
              type="button"
              className={productImagePrimaryAction === "approve-pending" ? "btn-primary" : "btn-secondary"}
              disabled={bulkBusy || !productImagePendingAssets.length}
              onClick={bulkApproveProductImages}
            >
              {bulkBusy ? "处理中..." : `一键入选剩余(${productImagePendingAssets.length})`}
            </button>
            <button
              type="button"
              className={productImagePrimaryAction === "share-approved" ? "btn-primary" : "btn-secondary"}
              disabled={bulkBusy || !productImageApprovedUnsharedAssets.length}
              onClick={bulkShareApprovedProductImages}
            >
              {bulkBusy ? "处理中..." : `批量分享到首页(${productImageApprovedUnsharedAssets.length})`}
            </button>
          </div>
          <div className="toolbar product-review-action-group product-review-action-group-secondary">
            <button type="button" className="btn-secondary" disabled={downloadingArchiveScope === "approved"} onClick={() => downloadProductImageArchive("approved")}>{downloadingArchiveScope === "approved" ? "打包中..." : "打包下载入选图"}</button>
            <button type="button" className="btn-secondary" disabled={downloadingArchiveScope === "generated"} onClick={() => downloadProductImageArchive("generated")}>{downloadingArchiveScope === "generated" ? "打包中..." : "打包下载全部"}</button>
          </div>
        </div>
      )}
      {tool.slug === "product-image" && (
        <div className="toolbar product-review-secondary-bar" style={{ marginTop: 8 }}>
          <div className="muted product-review-secondary-copy">
            手动微调只用于处理少量边缘结果，默认主路径仍是先补拍异常、再批量入选、最后分享或下载交付。
          </div>
          <button
            type="button"
            className={manualReviewMode ? "btn-secondary" : "btn-ghost"}
            onClick={() => setManualReviewMode((prev) => !prev)}
          >
            {manualReviewMode ? "收起手动微调" : "打开手动微调"}
          </button>
        </div>
      )}
      {tool.slug !== "product-image" && (
        <div className="toolbar" style={{ marginTop: 10, justifyContent: "space-between", flexWrap: "wrap" }} data-cta-scope={`workspace.review.${tool.slug}`}>
          <div className="toolbar" style={{ gap: 8 }}>
            <button
              type="button"
              className="btn-primary"
              onClick={() => setReviewFilter("pending")}
            >
              {pendingAssetsCount > 0 ? `先看待审核(${pendingAssetsCount})` : "查看全部结果"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setReviewFilter("approved")}
            >
              已通过({reviewedAssetsCount})
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setReviewFilter("failed")}
            >
              异常({failedAssetsCount})
            </button>
          </div>
          <div className="muted" style={{ maxWidth: 420 }}>
            首屏主路径：先聚焦待审核结果，再在卡片内逐张通过或淘汰。
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
          {tool.slug === "product-image" && reviewFilter === "all" && reviewFailedAssets.length > 0 ? (
            <div className="asset-card" style={{ marginBottom: 10 }}>
              <h3 className="title-row"><Icon name="spark" size={16} />异常候选区</h3>
              <div className="status-banner warning" style={{ marginTop: 8 }}>
                这里集中展示异常候选，建议优先处理后，再回到正常候选继续入选与分享。
              </div>
              <div className="asset-grid" style={{ marginTop: 10 }}>
                {reviewFailedAssets.map((asset) => {
                  const imageUrl = resolveAssetImageSrc(asset);
                  const videoUrl = asset.video_url || localPathToMedia(asset.local_path);
                  const isPlaceholder = asset.metadata?.source === "original";
                  return (
                    <article key={`failed-${asset.asset_id}`} className="asset-card result-asset-card failed">
                      {imageUrl ? <img src={imageUrl} alt="asset" loading="lazy" decoding="async" /> : videoUrl ? <video src={videoUrl} controls preload="metadata" /> : <div className="empty-state">无预览</div>}
                      <div className="result-asset-body">
                        <div className="result-asset-head">
                          <span className="badge warning">异常候选</span>
                          {isPlaceholder ? <span className="badge warning">原图占位</span> : null}
                        </div>
                        <div className="result-asset-copy muted">{asset.metadata?.intent_summary || "当前候选已被系统判为异常，请优先排查。"}</div>
                        <div className="result-asset-meta-strip warning">
                          <span>镜头：{asset.metadata?.shot_title || "待同步"}</span>
                          <span>用途：{asset.metadata?.delivery_purpose || "待同步"}</span>
                        </div>
                        <div className="muted result-asset-note">建议先补拍失败项或直接淘汰，避免异常图进入交付结果。</div>
                        <div className="toolbar result-asset-actions" style={{ marginTop: 8 }}>
                          <button type="button" className="btn-danger" onClick={() => reviewAsset(asset.asset_id, "reject")}>淘汰</button>
                          {manualReviewMode ? (
                            <button type="button" className="btn-secondary" onClick={() => reviewAsset(asset.asset_id, "approve")}>强制入选</button>
                          ) : null}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            </div>
          ) : null}
          {tool.slug === "product-image" && (reviewFilter === "all" || reviewFilter === "approved" || reviewFilter === "pending") ? (
            <div className="asset-card" style={{ marginBottom: 10 }}>
              <h3 className="title-row"><Icon name="gallery" size={16} />正常候选区</h3>
              <div className="muted" style={{ marginTop: 8 }}>
                这里保留正常候选与已入选结果。先处理异常区，再回到这里做批量入选、分享或下载交付。
              </div>
            </div>
          ) : null}
          <div className="asset-grid">
            {(tool.slug === "product-image" && reviewFilter === "all" ? reviewHealthyAssets : reviewAssetsInFilter).map((asset) => {
              const imageUrl = resolveAssetImageSrc(asset);
              const videoUrl = asset.video_url || localPathToMedia(asset.local_path);
              const isPlaceholder = asset.metadata?.source === "original";
              const bucket = assetReviewBucket(asset);
              const isShared = Boolean(asset.metadata?.showcase_shared);
              return (
                <article key={asset.asset_id} className={cx("asset-card result-asset-card", bucket === "failed" && "failed")}>
                  {imageUrl ? <img src={imageUrl} alt="asset" loading="lazy" decoding="async" /> : videoUrl ? <video src={videoUrl} controls preload="metadata" /> : <div className="empty-state">无预览</div>}
                  <div className="result-asset-body">
                    <div className="result-asset-head">
                      <span className={cx("badge", bucket === "failed" && "warning")}>
                        {bucket === "approved" ? "已通过" : bucket === "failed" ? "异常候选" : "待筛选"}
                      </span>
                      {bucket === "failed" && tool.slug === "model-retouch" ? <span className="badge warning">疑似未稳定命中模特来源</span> : null}
                      {isPlaceholder && <span className="badge warning">原图占位</span>}
                    </div>
                    {asset.metadata?.intent_summary && <div className="result-asset-copy muted">{asset.metadata.intent_summary}</div>}
                    {tool.slug === "product-image" && (
                      <div className="muted result-asset-note">
                        {bucket === "failed"
                          ? "这张是异常候选，建议先补拍失败项或只看异常筛掉后再继续交付。"
                          : isShared
                            ? "已在首页样片墙展示"
                            : manualReviewMode
                              ? "入选后可分享到首页样片墙"
                              : "可通过顶部“批量分享到首页”快速处理"}
                      </div>
                    )}
                    {tool.slug === "product-image" ? (
                      <div className={cx("result-asset-meta-strip", bucket === "failed" && "warning")}>
                        <span>镜头：{asset.metadata?.shot_title || "待同步"}</span>
                        <span>用途：{asset.metadata?.delivery_purpose || "待同步"}</span>
                      </div>
                    ) : null}
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
  );
}
