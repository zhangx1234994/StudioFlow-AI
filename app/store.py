from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, TypeVar
from uuid import uuid4

from app.schemas import (
    AssetRecord,
    LogLevel,
    ProjectLog,
    ProjectRecord,
    QualityReport,
    RenderRecord,
    ReviewDecision,
)

T = TypeVar("T")
logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional runtime dependency
    import redis
except Exception:  # pragma: no cover - optional runtime dependency
    redis = None

try:  # pragma: no cover - optional runtime dependency
    import oss2
except Exception:  # pragma: no cover - optional runtime dependency
    oss2 = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryStore:
    STORE_SCHEMA_VERSION = 2

    def __init__(
        self,
        persist_path: Path | None = None,
        redis_url: str | None = None,
        redis_state_key: str = "photo2video:state",
        oss_access_key: str | None = None,
        oss_secret_key: str | None = None,
        oss_bucket: str | None = None,
        oss_endpoint: str | None = None,
        oss_state_key: str = "photo2video/state/store.json",
    ) -> None:
        self._projects: dict[str, ProjectRecord] = {}
        self._renders: dict[str, RenderRecord] = {}
        self._assets: dict[str, AssetRecord] = {}
        self._quality_reports: dict[str, QualityReport] = {}
        self._review_decisions: dict[str, ReviewDecision] = {}
        self._project_logs: dict[str, list[ProjectLog]] = {}
        self._lock = Lock()
        self._persist_path = persist_path
        self._redis_url = redis_url
        self._redis_state_key = redis_state_key
        self._redis_client = None
        self._oss_bucket = None
        self._oss_state_key = oss_state_key

        if self._redis_url:
            if redis is None:
                raise RuntimeError(
                    "Redis backend requested but `redis` package is not installed. "
                    "Install with: pip install redis"
                )
            self._redis_client = redis.Redis.from_url(
                self._redis_url,
                decode_responses=True,
            )
            self._load_from_persistence()
        elif all([oss_access_key, oss_secret_key, oss_bucket, oss_endpoint]):
            if oss2 is None:
                raise RuntimeError(
                    "OSS backend requested but `oss2` package is not installed. "
                    "Install with: pip install oss2"
                )
            auth = oss2.Auth(oss_access_key, oss_secret_key)
            self._oss_bucket = oss2.Bucket(auth, f"https://{oss_endpoint}", oss_bucket)
            self._load_from_persistence()
        elif self._persist_path:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_persistence()

    def add_project(self, project: ProjectRecord) -> None:
        with self._lock:
            self._projects[project.project_id] = project
            self._project_logs.setdefault(project.project_id, [])
            self._persist_locked()

    def get_project(self, project_id: str) -> ProjectRecord | None:
        with self._lock:
            project = self._projects.get(project_id)
        if project is not None or not self._has_remote_persistence:
            return project
        self._sync_from_remote()
        with self._lock:
            return self._projects.get(project_id)

    def update_project(
        self,
        project_id: str,
        updater: Callable[[ProjectRecord], None],
    ) -> ProjectRecord:
        if self._has_remote_persistence:
            with self._lock:
                missing = project_id not in self._projects
            if missing:
                self._sync_from_remote()
        with self._lock:
            project = self._projects[project_id]
            updater(project)
            project.updated_at = utc_now()
            self._persist_locked()
            return project

    def add_render(self, render: RenderRecord) -> None:
        with self._lock:
            self._renders[render.render_id] = render
            self._persist_locked()

    def get_render(self, render_id: str) -> RenderRecord | None:
        with self._lock:
            render = self._renders.get(render_id)
        if render is not None or not self._has_remote_persistence:
            return render
        self._sync_from_remote()
        with self._lock:
            return self._renders.get(render_id)

    def update_render(
        self,
        render_id: str,
        updater: Callable[[RenderRecord], None],
    ) -> RenderRecord:
        with self._lock:
            render = self._renders[render_id]
            updater(render)
            render.updated_at = utc_now()
            self._persist_locked()
            return render

    def add_asset(self, asset: AssetRecord) -> None:
        with self._lock:
            self._assets[asset.asset_id] = asset
            self._persist_locked()

    def get_asset(self, asset_id: str) -> AssetRecord | None:
        with self._lock:
            asset = self._assets.get(asset_id)
        if asset is not None or not self._has_remote_persistence:
            return asset
        self._sync_from_remote()
        with self._lock:
            return self._assets.get(asset_id)

    def update_asset(self, asset_id: str, updater: Callable[[AssetRecord], None]) -> AssetRecord:
        with self._lock:
            asset = self._assets[asset_id]
            updater(asset)
            asset.updated_at = utc_now()
            self._persist_locked()
            return asset

    def list_assets(self, project_id: str) -> list[AssetRecord]:
        with self._lock:
            items = [item for item in self._assets.values() if item.project_id == project_id]
            items.sort(key=lambda item: item.created_at)
            return items

    def list_assets_global(
        self,
        *,
        source_type: str | None = None,
        tool_type: str | None = None,
        project_id: str | None = None,
        keyword: str | None = None,
        tag: str | None = None,
        limit: int = 200,
    ) -> list[AssetRecord]:
        with self._lock:
            items = list(self._assets.values())
            if source_type:
                source_value = source_type.strip().lower()
                items = [item for item in items if item.source_type.value == source_value]
            if tool_type:
                tool_value = tool_type.strip().lower()
                items = [item for item in items if item.tool_type.value == tool_value]
            if project_id:
                items = [item for item in items if item.project_id == project_id]
            if tag:
                target_tag = tag.strip().lower()
                items = [item for item in items if any(item_tag.lower() == target_tag for item_tag in item.tags)]
            if keyword:
                needle = keyword.strip().lower()
                items = [
                    item
                    for item in items
                    if needle in item.project_id.lower()
                    or needle in (item.prompt or "").lower()
                    or any(needle in item_tag.lower() for item_tag in item.tags)
                ]
            items.sort(key=lambda item: item.updated_at, reverse=True)
            if limit <= 0:
                return []
            return items[:limit]

    def add_quality_report(self, report: QualityReport) -> None:
        with self._lock:
            self._quality_reports[report.quality_id] = report
            self._persist_locked()

    def get_quality_report(self, quality_id: str) -> QualityReport | None:
        with self._lock:
            return self._quality_reports.get(quality_id)

    def list_quality_reports(self, project_id: str) -> list[QualityReport]:
        with self._lock:
            items = [item for item in self._quality_reports.values() if item.project_id == project_id]
            items.sort(key=lambda item: item.created_at)
            return items

    def add_review_decision(self, decision: ReviewDecision) -> None:
        with self._lock:
            self._review_decisions[decision.decision_id] = decision
            self._persist_locked()

    def list_review_decisions(self, project_id: str) -> list[ReviewDecision]:
        with self._lock:
            items = [item for item in self._review_decisions.values() if item.project_id == project_id]
            items.sort(key=lambda item: item.created_at)
            return items

    def add_project_log(
        self,
        project_id: str,
        level: LogLevel,
        stage: str,
        message: str,
        details: dict[str, Any] | None = None,
        render_id: str | None = None,
    ) -> ProjectLog:
        event = ProjectLog(
            event_id=str(uuid4()),
            project_id=project_id,
            timestamp=utc_now(),
            level=level,
            stage=stage,
            message=message,
            details=details or {},
            render_id=render_id,
        )
        with self._lock:
            self._project_logs.setdefault(project_id, []).append(event)
            self._persist_locked()
        return event

    def list_project_logs(self, project_id: str, limit: int = 200) -> list[ProjectLog]:
        with self._lock:
            logs = self._project_logs.get(project_id, [])
            if limit <= 0:
                return []
            return logs[-limit:]

    def list_projects(self, limit: int = 20, query: str | None = None) -> list[ProjectRecord]:
        if self._has_remote_persistence:
            self._sync_from_remote()
        with self._lock:
            projects = list(self._projects.values())
            if query:
                q = query.strip().lower()
                if q:
                    projects = [
                        item
                        for item in projects
                        if q in item.project_id.lower()
                        or q in item.brief.product_name.lower()
                        or q in item.scenario_type.value.lower()
                        or q in item.template_name.lower()
                        or q in item.status.value.lower()
                    ]
            projects.sort(key=lambda item: item.updated_at, reverse=True)
            if limit <= 0:
                return []
            return projects[:limit]

    @property
    def _has_remote_persistence(self) -> bool:
        return self._redis_client is not None or self._oss_bucket is not None

    def _sync_from_remote(self) -> None:
        if not self._has_remote_persistence:
            return
        self._load_from_persistence()

    def _load_from_persistence(self) -> None:
        raw_payload: str | None = None
        if self._redis_client is not None:
            try:
                raw_payload = self._redis_client.get(self._redis_state_key)
            except Exception as exc:  # pragma: no cover - network instability
                logger.warning("Failed to load persisted store from redis: %s", exc)
                return
            if not raw_payload:
                return
        elif self._oss_bucket is not None:
            try:
                response = self._oss_bucket.get_object(self._oss_state_key)
                raw_payload = response.read().decode("utf-8")
            except Exception as exc:  # pragma: no cover - network instability
                message = str(exc).lower()
                if "no such key" in message or "not found" in message or "404" in message:
                    return
                logger.warning("Failed to load persisted store from OSS key %s: %s", self._oss_state_key, exc)
                return
        elif self._persist_path and self._persist_path.exists():
            raw_payload = self._persist_path.read_text(encoding="utf-8")
        else:
            return

        try:
            raw = json.loads(raw_payload)
            version = int(raw.get("schema_version", 1))
            if version != self.STORE_SCHEMA_VERSION:
                raise ValueError(
                    f"store schema version mismatch: got {version}, expected {self.STORE_SCHEMA_VERSION}"
                )
            project_rows = raw.get("projects", [])
            render_rows = raw.get("renders", [])
            asset_rows = raw.get("assets", [])
            quality_rows = raw.get("quality_reports", [])
            decision_rows = raw.get("review_decisions", [])
            log_rows = raw.get("project_logs", {})

            projects = {row["project_id"]: ProjectRecord.model_validate(row) for row in project_rows}
            renders = {row["render_id"]: RenderRecord.model_validate(row) for row in render_rows}
            assets = {row["asset_id"]: AssetRecord.model_validate(row) for row in asset_rows}
            quality_reports = {
                row["quality_id"]: QualityReport.model_validate(row) for row in quality_rows
            }
            review_decisions = {
                row["decision_id"]: ReviewDecision.model_validate(row) for row in decision_rows
            }
            loaded_logs: dict[str, list[ProjectLog]] = {}
            if isinstance(log_rows, dict):
                for project_id, rows in log_rows.items():
                    if isinstance(rows, list):
                        loaded_logs[project_id] = [
                            ProjectLog.model_validate(item) for item in rows
                        ]
            for project_id in projects:
                loaded_logs.setdefault(project_id, [])
            with self._lock:
                self._projects = projects
                self._renders = renders
                self._assets = assets
                self._quality_reports = quality_reports
                self._review_decisions = review_decisions
                self._project_logs = loaded_logs
            if self._redis_client is not None:
                logger.info("Loaded persisted store from redis key %s", self._redis_state_key)
            elif self._oss_bucket is not None:
                logger.info("Loaded persisted store from OSS key %s", self._oss_state_key)
            else:
                logger.info("Loaded persisted store from %s", self._persist_path)
        except Exception as exc:  # pragma: no cover - defensive path
            if self._redis_client is not None:
                logger.warning(
                    "Failed to load persisted store from redis key %s: %s",
                    self._redis_state_key,
                    exc,
                )
            elif self._oss_bucket is not None:
                logger.warning(
                    "Failed to load persisted store from OSS key %s: %s",
                    self._oss_state_key,
                    exc,
                )
            else:
                logger.warning("Failed to load persisted store %s: %s", self._persist_path, exc)
            with self._lock:
                self._projects = {}
                self._renders = {}
                self._assets = {}
                self._quality_reports = {}
                self._review_decisions = {}
                self._project_logs = {}

    def _persist_locked(self) -> None:
        if not self._persist_path and self._redis_client is None and self._oss_bucket is None:
            return
        payload = {
            "schema_version": self.STORE_SCHEMA_VERSION,
            "projects": [item.model_dump(mode="json") for item in self._projects.values()],
            "renders": [item.model_dump(mode="json") for item in self._renders.values()],
            "assets": [item.model_dump(mode="json") for item in self._assets.values()],
            "quality_reports": [
                item.model_dump(mode="json") for item in self._quality_reports.values()
            ],
            "review_decisions": [
                item.model_dump(mode="json") for item in self._review_decisions.values()
            ],
            "project_logs": {
                project_id: [event.model_dump(mode="json") for event in logs]
                for project_id, logs in self._project_logs.items()
            },
        }
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if self._redis_client is not None:
            try:
                self._redis_client.set(self._redis_state_key, payload_json)
            except Exception as exc:  # pragma: no cover - network instability
                logger.warning(
                    "Failed to persist store to redis key %s: %s",
                    self._redis_state_key,
                    exc,
                )
            return
        if self._oss_bucket is not None:
            try:
                self._oss_bucket.put_object(
                    self._oss_state_key,
                    payload_json.encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
            except Exception as exc:  # pragma: no cover - network instability
                logger.warning(
                    "Failed to persist store to OSS key %s: %s",
                    self._oss_state_key,
                    exc,
                )
            return

        tmp_path = self._persist_path.with_suffix(self._persist_path.suffix + ".tmp")
        tmp_path.write_text(payload_json, encoding="utf-8")
        tmp_path.replace(self._persist_path)
