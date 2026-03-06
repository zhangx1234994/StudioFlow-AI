from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from threading import Lock
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote_plus

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.deps import get_pipeline_service
from app.store import utc_now
from app.schemas import (
    ApproveStoryboardShotRequest,
    AccountStatus,
    AssetRecord,
    BackgroundPolicy,
    BatchGenerateRequest,
    BatchIdentityConfirmRequest,
    BatchIdentityClearUploadRequest,
    BatchIdentityGenerateRequest,
    BatchIdentityUploadRequest,
    BatchRetryRequest,
    BatchRole,
    BatchCreateModelRetouchResponse,
    BatchCreateProjectResponse,
    BatchCreateRequest,
    BillingSummary,
    CameraInputsRequest,
    CreateProjectResponse,
    DashboardKpi,
    DerivePromptsRequest,
    GenerateRequest,
    GenerateAssetsResponse,
    GenerateIdentityCandidateRequest,
    GenerateImagesRequest,
    GeneratePlanRequest,
    GenerateStoryboardRequest,
    GenerateVideosRequest,
    IdentityActionRequest,
    IdentityActionResponse,
    PresenterMode,
    PresenterSource,
    ProductBrief,
    ProjectLog,
    ProjectProgress,
    ProjectRecord,
    ProjectTaskItem,
    PromptVersionMetricsResponse,
    ModelRetouchBatchSummaryResponse,
    OssSignRequest,
    OssSignResponse,
    ManualAdjustPointsRequest,
    LedgerListResponse,
    QualityLevel,
    QualitySummaryResponse,
    QualityReport,
    PointsLedgerEntry,
    RechargeOrder,
    RechargeConfirmRequest,
    RechargeCreateRequest,
    RechargeListResponse,
    RetouchStrength,
    RetryProjectRequest,
    RegenerateStoryboardShotRequest,
    RenderRecord,
    RenderRequest,
    RenderResponse,
    ReviewDecision,
    ReviewRequest,
    ReviewResponse,
    ShareAssetRequest,
    ShareAssetResponse,
    ShowcaseRemixRequest,
    ShowcaseRemixResponse,
    ScenarioType,
    SelectScriptRequest,
    SetConfig,
    ToolTemplateOption,
    ToolType,
    UserCreateRequest,
    UserListResponse,
    UserRegisterRequest,
    UserRecord,
    UserRole,
    UserUpdateRequest,
    UpdateMasterScriptRequest,
    UpdatePromptInputsRequest,
    UpdatePlanRequest,
    WorkflowMode,
)
from app.services.pipeline_service import PipelineService
from app.services.auth_service import AuthService, AuthSession
from app.utils.image_tools import get_image_dimensions
from app.utils.logging_setup import setup_logging


settings = get_settings()
setup_logging(settings)
logger = logging.getLogger(__name__)
app = FastAPI(title="AI摄影棚", version="0.3.0")
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
frontend_out_dir = Path(__file__).resolve().parent.parent / "frontend" / "out"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    candidates = [
        frontend_out_dir / "favicon.ico",
        frontend_out_dir / "app" / "favicon.ico",
        Path(__file__).resolve().parent.parent / "frontend" / "public" / "favicon.ico",
        static_dir / "favicon.ico",
    ]
    for path in candidates:
        if path.exists():
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="favicon not found")

AUTH_COOKIE_NAME = "photo2video_session"
AUTH_ACCESS_COOKIE_NAME = "access_token"
AUTH_REFRESH_COOKIE_NAME = "refresh_token"
TOOL_SLUG_MAP: dict[ToolType, str] = {
    ToolType.intro_video_multi_script: "intro-video",
    ToolType.product_image_suite: "product-image",
    ToolType.model_retouch: "model-retouch",
    ToolType.quick_video_15s: "quick-video-15s",
    ToolType.multi_angle_camera: "multi-angle-camera",
}
TOOL_TYPE_BY_SLUG: dict[str, ToolType] = {slug: tool for tool, slug in TOOL_SLUG_MAP.items()}
TOOL_BY_TYPE_TEXT: dict[ToolType, str] = {
    ToolType.intro_video_multi_script: "转化讲解视频工坊",
    ToolType.product_image_suite: "商品棚拍出图工坊",
    ToolType.model_retouch: "模特人像精修工坊",
    ToolType.quick_video_15s: "15秒场景短片工坊",
    ToolType.multi_angle_camera: "多角度展品工坊",
}
auth_service = AuthService(settings)
LOGIN_FAIL_WINDOW_SECONDS = 10 * 60
LOGIN_MAX_FAILS = 5
LOGIN_LOCK_SECONDS = 15 * 60
LOGIN_IP_WINDOW_SECONDS = 60
LOGIN_IP_MAX_ATTEMPTS = 20
_login_guard_lock = Lock()
_login_failures_by_user: dict[str, list[int]] = {}
_login_lock_by_user: dict[str, int] = {}
_login_attempts_by_ip: dict[str, list[int]] = {}


def _now_ts() -> int:
    return int(time.time())


def _sign_token(payload_json: str) -> str:
    digest = hmac.new(
        settings.auth_secret.encode("utf-8"),
        payload_json.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _create_session_token(username: str) -> str:
    payload = {
        "u": username,
        "exp": _now_ts() + max(1, settings.auth_session_hours) * 3600,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8").rstrip("=")
    signature = _sign_token(payload_json)
    return f"{payload_b64}.{signature}"


def _decode_session_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    payload_b64, signature = token.split(".", 1)
    try:
        padding = "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode((payload_b64 + padding).encode("utf-8")).decode("utf-8")
        expected_signature = _sign_token(payload_json)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        payload = json.loads(payload_json)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    exp = payload.get("exp")
    username = payload.get("u")
    if not isinstance(exp, int) or not isinstance(username, str):
        return None
    if exp < _now_ts():
        return None
    return username


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", "")
    return value or str(uuid4())


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _prune_attempts(buckets: dict[str, list[int]], *, now_ts: int, window: int) -> None:
    for key, values in list(buckets.items()):
        kept = [item for item in values if now_ts - item <= window]
        if kept:
            buckets[key] = kept
        else:
            buckets.pop(key, None)


def _check_login_guard(username: str, request: Request) -> tuple[int | None, str | None, str | None]:
    now_ts = int(time.time())
    normalized_user = (username or "").strip().lower() or "_anonymous"
    ip = _client_ip(request)
    with _login_guard_lock:
        _prune_attempts(_login_attempts_by_ip, now_ts=now_ts, window=LOGIN_IP_WINDOW_SECONDS)
        _prune_attempts(_login_failures_by_user, now_ts=now_ts, window=LOGIN_FAIL_WINDOW_SECONDS)
        for key, until in list(_login_lock_by_user.items()):
            if until <= now_ts:
                _login_lock_by_user.pop(key, None)
        ip_attempts = _login_attempts_by_ip.get(ip, [])
        if len(ip_attempts) >= LOGIN_IP_MAX_ATTEMPTS:
            return (
                status.HTTP_429_TOO_MANY_REQUESTS,
                "登录请求过于频繁，请稍后再试。",
                "LOGIN_RATE_LIMITED",
            )
        locked_until = _login_lock_by_user.get(normalized_user, 0)
        if locked_until > now_ts:
            wait_seconds = locked_until - now_ts
            wait_minutes = max(1, (wait_seconds + 59) // 60)
            return (
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"登录失败次数过多，账号已锁定，请 {wait_minutes} 分钟后重试。",
                "LOGIN_LOCKED",
            )
    return None, None, None


def _record_login_attempt(username: str, request: Request, *, success: bool) -> None:
    now_ts = int(time.time())
    normalized_user = (username or "").strip().lower() or "_anonymous"
    ip = _client_ip(request)
    with _login_guard_lock:
        _login_attempts_by_ip.setdefault(ip, []).append(now_ts)
        _prune_attempts(_login_attempts_by_ip, now_ts=now_ts, window=LOGIN_IP_WINDOW_SECONDS)
        if success:
            _login_failures_by_user.pop(normalized_user, None)
            _login_lock_by_user.pop(normalized_user, None)
            return
        failures = _login_failures_by_user.setdefault(normalized_user, [])
        failures.append(now_ts)
        _prune_attempts(_login_failures_by_user, now_ts=now_ts, window=LOGIN_FAIL_WINDOW_SECONDS)
        failures = _login_failures_by_user.get(normalized_user, [])
        if len(failures) >= LOGIN_MAX_FAILS:
            _login_lock_by_user[normalized_user] = now_ts + LOGIN_LOCK_SECONDS


def _resolve_username_from_login(login_value: str, service: PipelineService) -> str:
    normalized = (login_value or "").strip().lower()
    if not normalized:
        return ""
    direct = service.get_user(normalized)
    if direct:
        return direct.username
    for item in service.list_users():
        if item.email.lower() == normalized:
            return item.username
    return normalized


def _json_error(
    *,
    request: Request,
    status_code: int,
    detail: str,
    code: str | None = None,
) -> JSONResponse:
    payload: dict[str, str] = {"detail": detail, "request_id": _request_id(request)}
    if code:
        payload["code"] = code
    return JSONResponse(status_code=status_code, content=payload)


def _session_max_age_seconds() -> int:
    if settings.auth_provider == "supabase":
        days = max(1, int(settings.auth_session_days or 7))
        return days * 24 * 3600
    return max(1, settings.auth_session_hours) * 3600


def _cookie_secure(request: Request | None = None) -> bool:
    if os.getenv("VERCEL"):
        return True
    if request is None:
        return False
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    scheme = (request.url.scheme or "").lower()
    return forwarded_proto == "https" or scheme == "https"


def _set_supabase_auth_cookies(
    response: Response,
    session: AuthSession,
    *,
    request: Request | None = None,
) -> None:
    max_age = _session_max_age_seconds()
    secure = _cookie_secure(request)
    response.set_cookie(
        key=AUTH_ACCESS_COOKIE_NAME,
        value=session.access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=AUTH_REFRESH_COOKIE_NAME,
        value=session.refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(AUTH_ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(AUTH_REFRESH_COOKIE_NAME, path="/")


def _decode_jwt_exp(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    try:
        _, payload_b64, _ = token.split(".", 2)
        padding = "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode((payload_b64 + padding).encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)
        exp = int(payload.get("exp") or 0)
        if exp <= 0:
            return None
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp))
    except Exception:
        return None


def _auth_exempt_path(path: str) -> bool:
    if path in {
        "/healthz",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/app",
        "/app/",
        "/app/login",
        "/app/login/",
        "/app/register",
        "/app/register/",
    }:
        return True
    if (
        path.startswith("/static/")
        or path.startswith("/media/")
        or path.startswith("/app/_next/")
        or path.startswith("/_next/")
    ):
        return True
    if path.startswith("/api/v1/auth/"):
        return True
    return False


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not settings.auth_enabled or _auth_exempt_path(request.url.path):
        return await call_next(request)

    if settings.auth_provider == "supabase":
        access_token = request.cookies.get(AUTH_ACCESS_COOKIE_NAME)
        refresh_token = request.cookies.get(AUTH_REFRESH_COOKIE_NAME)
        if access_token and auth_service.is_configured:
            user = await auth_service.verify_access_token(access_token)
            if user:
                request.state.username = str(user.get("username") or "")
                return await call_next(request)
        if refresh_token and auth_service.is_configured:
            try:
                session = await auth_service.refresh_session(refresh_token)
                user = await auth_service.verify_access_token(session.access_token)
                if user:
                    request.state.username = str(user.get("username") or session.username or "")
                    response = await call_next(request)
                    _set_supabase_auth_cookies(response, session, request=request)
                    return response
            except Exception as exc:  # pragma: no cover - network instability
                logger.warning("Auth refresh failed (request_id=%s): %s", _request_id(request), exc)
    else:
        username = _decode_session_token(request.cookies.get(AUTH_COOKIE_NAME))
        if username:
            service = get_pipeline_service()
            request.state.username = _resolve_username_from_login(username, service)
            return await call_next(request)

    if request.url.path.startswith("/api/"):
        return _json_error(
            request=request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. Please login first.",
            code="UNAUTHORIZED",
        )
    return RedirectResponse(url="/app/login", status_code=status.HTTP_302_FOUND)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/app/tools", status_code=status.HTTP_302_FOUND)


@app.get("/login", include_in_schema=False)
def login_legacy() -> RedirectResponse:
    return RedirectResponse(url="/app/login", status_code=status.HTTP_302_FOUND)


@app.get("/register", include_in_schema=False)
def register_legacy() -> RedirectResponse:
    return RedirectResponse(url="/app/register", status_code=status.HTTP_302_FOUND)


@app.get("/tools", include_in_schema=False)
def tools_home_legacy() -> RedirectResponse:
    return RedirectResponse(url="/app/tools", status_code=status.HTTP_302_FOUND)


@app.get("/assets", include_in_schema=False)
def assets_legacy() -> RedirectResponse:
    return RedirectResponse(url="/app/assets", status_code=status.HTTP_302_FOUND)


@app.get("/billing", include_in_schema=False)
def billing_legacy() -> RedirectResponse:
    return RedirectResponse(url="/app/billing", status_code=status.HTTP_302_FOUND)


@app.get("/users", include_in_schema=False)
def users_legacy() -> RedirectResponse:
    return RedirectResponse(url="/app/users", status_code=status.HTTP_302_FOUND)


def _frontend_file_or_index(full_path: str) -> FileResponse:
    if not frontend_out_dir.exists():
        raise HTTPException(
            status_code=503,
            detail="Frontend assets are not built. Run `npm --prefix frontend install && npm --prefix frontend run build`.",
        )
    candidate = (frontend_out_dir / full_path).resolve()
    root = frontend_out_dir.resolve()
    if not (candidate == root or candidate.is_relative_to(root)):
        raise HTTPException(status_code=404, detail="Page not found")
    if candidate.is_file():
        return FileResponse(candidate)
    index_file = frontend_out_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=503, detail="Frontend index not found")
    return FileResponse(index_file)


def _frontend_static_asset(full_path: str) -> FileResponse:
    if not frontend_out_dir.exists():
        raise HTTPException(status_code=503, detail="Frontend assets are not built.")
    candidate = (frontend_out_dir / full_path).resolve()
    root = frontend_out_dir.resolve()
    if not (candidate == root or candidate.is_relative_to(root)):
        raise HTTPException(status_code=404, detail="Asset not found")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(candidate)


@app.get("/app", include_in_schema=False)
def app_root() -> RedirectResponse:
    return RedirectResponse(url="/app/tools", status_code=status.HTTP_302_FOUND)


@app.get("/app/{full_path:path}", include_in_schema=False)
def app_spa(full_path: str) -> FileResponse:
    normalized = full_path.strip("/")
    if not normalized:
        return _frontend_file_or_index("")
    return _frontend_file_or_index(normalized)


@app.get("/_next/{full_path:path}", include_in_schema=False)
def app_next_assets(full_path: str) -> FileResponse:
    return _frontend_static_asset(f"_next/{full_path.strip('/')}")


async def _login_response(
    *,
    request: Request,
    username: str,
    password: str,
    redirect: bool,
) -> Response:
    username = _normalize_login_username(username)
    def _redirect(url: str) -> RedirectResponse:
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)

    guard_status, guard_detail, guard_code = _check_login_guard(username, request)
    if guard_status is not None:
        if redirect:
            return _redirect("/app/login?error=too_many_attempts")
        return _json_error(
            request=request,
            status_code=guard_status,
            detail=guard_detail or "登录请求过于频繁，请稍后重试。",
            code=guard_code or "LOGIN_RATE_LIMITED",
        )

    def _success_response(session_username: str, session: AuthSession | None = None) -> Response:
        if redirect:
            response = _redirect("/app/tools")
        else:
            response = JSONResponse(
                content={"ok": True, "username": session_username, "expires_in": _session_max_age_seconds()}
            )
        if session is not None:
            _set_supabase_auth_cookies(response, session, request=request)
        return response

    if not settings.auth_enabled:
        if redirect:
            return _redirect("/app/tools")
        return JSONResponse(content={"ok": True, "username": "dev", "expires_in": _session_max_age_seconds()})

    if settings.auth_provider == "supabase":
        if not auth_service.is_configured:
            if redirect:
                return _redirect("/app/login?error=auth_not_configured")
            return _json_error(
                request=request,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Supabase auth is not configured.",
                code="AUTH_NOT_CONFIGURED",
            )
        try:
            session = await auth_service.sign_in_with_password(username, password)
        except ValueError:
            _record_login_attempt(username, request, success=False)
            if redirect:
                return _redirect("/app/login?error=invalid_credentials")
            return _json_error(
                request=request,
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账号或密码错误",
                code="INVALID_CREDENTIALS",
            )
        except Exception as exc:  # pragma: no cover - network instability
            logger.exception("Supabase login failed (request_id=%s): %s", _request_id(request), exc)
            if redirect:
                return _redirect("/app/login?error=auth_provider_error")
            return _json_error(
                request=request,
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="认证服务暂时不可用，请稍后重试",
                code="AUTH_PROVIDER_ERROR",
            )
        _record_login_attempt(username, request, success=True)
        return _success_response(session.username or settings.admin_username, session)

    service = get_pipeline_service()
    local_user = service.authenticate_local_user(username_or_email=username, password=password)
    if not local_user:
        candidate = service.find_user_by_login(username)
        if candidate and candidate.account_status in {AccountStatus.suspended, AccountStatus.frozen}:
            _record_login_attempt(username, request, success=False)
            if redirect:
                return _redirect("/app/login?error=account_suspended")
            return _json_error(
                request=request,
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被限制登录，请联系管理员。",
                code="ACCOUNT_SUSPENDED",
            )
        _record_login_attempt(username, request, success=False)
        if redirect:
            return _redirect("/app/login?error=invalid_credentials")
        return _json_error(
            request=request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
            code="INVALID_CREDENTIALS",
        )
    _record_login_attempt(username, request, success=True)
    session_username = local_user.username
    token = _create_session_token(username=session_username)
    if redirect:
        response: Response = _redirect("/app/tools")
    else:
        response = JSONResponse(
            content={"ok": True, "username": session_username, "expires_in": _session_max_age_seconds()}
        )
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
        max_age=_session_max_age_seconds(),
        path="/",
    )
    return response


@app.post("/api/v1/auth/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> JSONResponse:
    response = await _login_response(
        request=request,
        username=username,
        password=password,
        redirect=False,
    )
    if isinstance(response, JSONResponse):
        return response
    # Fallback guard; /api login should always return JSON.
    detail = quote_plus("Unexpected login response type")
    return JSONResponse(status_code=500, content={"detail": detail, "code": "AUTH_RESPONSE_INVALID"})


@app.post("/api/v1/auth/register")
def register(
    payload: UserRegisterRequest,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> JSONResponse:
    if settings.auth_provider != "local":
        return _json_error(
            request=request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="当前认证模式不支持本地注册。",
            code="REGISTER_NOT_AVAILABLE",
        )
    try:
        user = service.register_user(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        return _json_error(
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            code="REGISTER_INVALID_INPUT",
        )
    return JSONResponse(
        content={
            "ok": True,
            "username": user.username,
            "workspace_id": user.workspace_id,
            "account_status": user.account_status.value,
        }
    )


@app.post("/app/login", include_in_schema=False)
async def app_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    response = await _login_response(
        request=request,
        username=username,
        password=password,
        redirect=True,
    )
    return response


@app.post("/api/v1/auth/logout")
async def logout(request: Request) -> JSONResponse:
    if settings.auth_provider == "supabase" and settings.auth_enabled:
        access_token = request.cookies.get(AUTH_ACCESS_COOKIE_NAME)
        try:
            await auth_service.sign_out(access_token or "")
        except Exception as exc:  # pragma: no cover - network instability
            logger.warning("Supabase logout failed (request_id=%s): %s", _request_id(request), exc)
    response = JSONResponse(content={"ok": True})
    _clear_auth_cookies(response)
    return response


@app.get("/api/v1/auth/me")
async def auth_me(
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> dict[str, str | bool | None | int]:
    if not settings.auth_enabled:
        return {
            "authenticated": True,
            "username": "dev",
            "session_expires_at": None,
            "role": UserRole.admin.value,
            "account_status": AccountStatus.active.value,
            "workspace_id": "default_workspace",
            "points_balance": 0,
        }
    if settings.auth_provider == "supabase" and auth_service.is_configured:
        access_token = request.cookies.get(AUTH_ACCESS_COOKIE_NAME)
        if not access_token:
            return {
                "authenticated": False,
                "username": "",
                "session_expires_at": None,
                "role": "",
                "account_status": "",
                "workspace_id": "",
                "points_balance": 0,
            }
        user = await auth_service.verify_access_token(access_token)
        if not user:
            return {
                "authenticated": False,
                "username": "",
                "session_expires_at": None,
                "role": "",
                "account_status": "",
                "workspace_id": "",
                "points_balance": 0,
            }
        username = _resolve_username_from_login(str(user.get("username") or settings.admin_username), service)
        profile = service.get_user(username)
        return {
            "authenticated": True,
            "username": username,
            "session_expires_at": _decode_jwt_exp(access_token),
            "role": (profile.role.value if profile else UserRole.member.value),
            "account_status": (profile.account_status.value if profile else AccountStatus.active.value),
            "workspace_id": (profile.workspace_id if profile else "default_workspace"),
            "points_balance": int(profile.points_balance if profile else 0),
        }
    username = _resolve_username_from_login(
        _decode_session_token(request.cookies.get(AUTH_COOKIE_NAME)) or "",
        service,
    )
    profile = service.get_user(username or "") if username else None
    return {
        "authenticated": bool(username),
        "username": username or "",
        "session_expires_at": _decode_jwt_exp(request.cookies.get(AUTH_COOKIE_NAME)),
        "role": (profile.role.value if profile else ""),
        "account_status": (profile.account_status.value if profile else ""),
        "workspace_id": (profile.workspace_id if profile else ""),
        "points_balance": int(profile.points_balance if profile else 0),
    }


def _current_username(request: Request) -> str:
    service = get_pipeline_service()
    state_username = str(getattr(request.state, "username", "") or "").strip().lower()
    if state_username:
        return _resolve_username_from_login(state_username, service)
    token_username = _decode_session_token(request.cookies.get(AUTH_COOKIE_NAME))
    if token_username:
        return _resolve_username_from_login(token_username, service)
    return _resolve_username_from_login((settings.admin_username or "admin"), service)


def _require_admin(request: Request, service: PipelineService) -> str:
    username = _current_username(request)
    user = service.get_user(username)
    if not user or user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin permission required")
    return username


def _require_privileged(request: Request, service: PipelineService) -> str:
    username = _current_username(request)
    user = service.get_user(username)
    if not user or user.role not in {UserRole.admin, UserRole.operator}:
        raise HTTPException(status_code=403, detail="Admin or operator permission required")
    return username


def _current_user_record(request: Request, service: PipelineService) -> UserRecord | None:
    username = _current_username(request)
    return service.get_user(username)


def _is_privileged_user(user: UserRecord | None) -> bool:
    if not user:
        return False
    return user.role in {UserRole.admin, UserRole.operator}


def _can_access_project(project: ProjectRecord, user: UserRecord | None) -> bool:
    if _is_privileged_user(user):
        return True
    if not user:
        return False
    return (project.owner_username or "").strip().lower() == user.username.strip().lower()


def _ensure_project_access(
    *,
    project_id: str,
    request: Request,
    service: PipelineService,
) -> ProjectRecord:
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    user = _current_user_record(request, service)
    if _can_access_project(project, user):
        return project
    raise HTTPException(status_code=403, detail="Forbidden: no access to this project")


def _ensure_model_retouch_batch_access(
    *,
    batch_group_id: str,
    request: Request,
    service: PipelineService,
) -> None:
    projects = [
        item
        for item in service.list_projects_by_tool(tool_type=ToolType.model_retouch, limit=10000)
        if item.batch_group_id == batch_group_id
    ]
    if not projects:
        raise HTTPException(status_code=404, detail="Batch not found")
    user = _current_user_record(request, service)
    for item in projects:
        if _can_access_project(item, user):
            return
    raise HTTPException(status_code=403, detail="Forbidden: no access to this batch")


@app.get("/api/v1/users", response_model=UserListResponse)
def list_users(
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> UserListResponse:
    _require_admin(request, service)
    return UserListResponse(items=service.list_users())


@app.post("/api/v1/users", response_model=UserRecord)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> UserRecord:
    _require_admin(request, service)
    try:
        return service.create_user(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            display_name=payload.display_name,
            workspace_id=payload.workspace_id,
            role=payload.role,
            account_status=payload.account_status,
            is_active=payload.is_active,
            initial_points=payload.initial_points,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/v1/users/{username}", response_model=UserRecord)
def update_user(
    username: str,
    payload: UserUpdateRequest,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> UserRecord:
    _require_admin(request, service)
    try:
        return service.update_user(
            username=username,
            display_name=payload.display_name,
            workspace_id=payload.workspace_id,
            role=payload.role,
            account_status=payload.account_status,
            is_active=payload.is_active,
            password=payload.password,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/billing/me", response_model=BillingSummary)
def billing_summary(
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> BillingSummary:
    username = _current_username(request)
    try:
        return service.get_billing_summary(username)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found") from None


@app.get("/api/v1/billing/ledger", response_model=LedgerListResponse)
def billing_ledger(
    request: Request,
    limit: int = 100,
    service: PipelineService = Depends(get_pipeline_service),
) -> LedgerListResponse:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    username = _current_username(request)
    return LedgerListResponse(items=service.list_points_ledger(username=username, limit=limit))


@app.get("/api/v1/billing/recharges", response_model=RechargeListResponse)
def billing_recharges(
    request: Request,
    limit: int = 100,
    service: PipelineService = Depends(get_pipeline_service),
) -> RechargeListResponse:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    username = _current_username(request)
    current_user = service.get_user(username)
    if current_user and current_user.role == UserRole.admin:
        return RechargeListResponse(items=service.list_recharge_orders(username=None, limit=limit))
    return RechargeListResponse(items=service.list_recharge_orders(username=username, limit=limit))


def _ensure_recharge_channel_enabled() -> None:
    if not settings.billing_recharge_enabled:
        raise HTTPException(
            status_code=503,
            detail="Recharge channel reserved. Please ask admin to adjust points manually.",
        )


@app.post("/api/v1/billing/recharge", response_model=RechargeOrder)
def billing_create_recharge(
    payload: RechargeCreateRequest,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> RechargeOrder:
    _ensure_recharge_channel_enabled()
    username = _current_username(request)
    try:
        return service.create_recharge_order(
            username=username,
            points=payload.points,
            amount_cny=payload.amount_cny,
            channel=payload.channel,
            note=payload.note,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found") from None


@app.post("/api/v1/billing/recharge/confirm", response_model=RechargeOrder)
def billing_confirm_recharge(
    payload: RechargeConfirmRequest,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> RechargeOrder:
    _ensure_recharge_channel_enabled()
    operator = _require_admin(request, service)
    try:
        return service.confirm_recharge_order(order_id=payload.order_id, operator=operator)
    except KeyError:
        raise HTTPException(status_code=404, detail="Recharge order not found") from None


@app.post("/api/v1/billing/adjust", response_model=PointsLedgerEntry)
def billing_adjust_points(
    payload: ManualAdjustPointsRequest,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> PointsLedgerEntry:
    _require_admin(request, service)
    try:
        return service.adjust_points(username=payload.username, delta=payload.delta, note=payload.note)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/oss/sign", response_model=OssSignResponse)
def sign_oss_upload(
    request: OssSignRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> OssSignResponse:
    oss = service.oss
    if not oss.enabled:
        raise HTTPException(status_code=503, detail="OSS is not enabled")
    project_id = request.project_id.strip()
    if not project_id:
        raise HTTPException(status_code=422, detail="project_id is required")
    filename = request.filename.strip() or "upload.png"
    suffix = _guess_suffix(filename, ".png")
    role = (request.role or "source").strip().lower()
    if role == "source":
        key = oss.object_key("inputs", project_id, f"source_{uuid4().hex}{suffix}")
    elif role == "identity":
        key = oss.object_key("inputs", project_id, f"identity{suffix}")
    elif role == "style_reference":
        key = oss.object_key("inputs", project_id, "references", f"style_{uuid4().hex}{suffix}")
    elif role == "reference":
        key = oss.object_key("inputs", project_id, "references", f"ref_{uuid4().hex}{suffix}")
    else:
        key = oss.object_key("inputs", project_id, "misc", f"{uuid4().hex}{suffix}")
    payload = oss.sign_post(object_key=key)
    payload["updated_at"] = utc_now()
    return OssSignResponse(**payload)


@app.get("/tasks", include_in_schema=False)
def task_center_legacy() -> RedirectResponse:
    return RedirectResponse(url="/app/tools", status_code=302)


@app.get("/tools/{tool_type}/tasks", include_in_schema=False)
def tool_task_center_legacy(tool_type: ToolType) -> RedirectResponse:
    slug = TOOL_SLUG_MAP.get(tool_type, "intro-video")
    return RedirectResponse(url=f"/app/tools/{slug}/tasks", status_code=302)


@app.get("/projects/{project_id}", include_in_schema=False)
def project_workspace_legacy(
    project_id: str,
    service: PipelineService = Depends(get_pipeline_service),
) -> RedirectResponse:
    project = service.get_project(project_id)
    if project and project.tool_type == ToolType.model_retouch and project.batch_group_id:
        return RedirectResponse(
            url=f"/app/tools/model-retouch/batches/{project.batch_group_id}",
            status_code=302,
        )
    slug = TOOL_SLUG_MAP[project.tool_type] if project else TOOL_SLUG_MAP[ToolType.intro_video_multi_script]
    return RedirectResponse(url=f"/app/tools/{slug}/projects/{project_id}", status_code=302)


@app.get("/tools/{tool_type}/projects/{project_id}", include_in_schema=False)
def tool_project_workspace_legacy(
    tool_type: ToolType,
    project_id: str,
    service: PipelineService = Depends(get_pipeline_service),
) -> RedirectResponse:
    if tool_type == ToolType.model_retouch:
        project = service.get_project(project_id)
        if project and project.batch_group_id:
            return RedirectResponse(
                url=f"/app/tools/model-retouch/batches/{project.batch_group_id}",
                status_code=302,
            )
    slug = TOOL_SLUG_MAP.get(tool_type, "intro-video")
    return RedirectResponse(url=f"/app/tools/{slug}/projects/{project_id}", status_code=302)


def _resolve_media_asset(asset_path: str) -> Path:
    target = (settings.storage_root / asset_path).resolve()
    allowed_roots = (
        (settings.storage_root / "uploads").resolve(),
        (settings.storage_root / "renders").resolve(),
    )
    if not any(target == root or target.is_relative_to(root) for root in allowed_roots):
        raise HTTPException(status_code=404, detail="Media not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Media not found")
    return target


@app.get("/media/{asset_path:path}", include_in_schema=False)
def serve_media_asset(asset_path: str) -> FileResponse:
    return FileResponse(_resolve_media_asset(asset_path))


@app.get("/healthz")
def healthcheck(settings: Settings = Depends(get_settings)) -> dict[str, str | bool]:
    backend = _resolved_store_backend(settings)
    return {
        "status": "ok",
        "mock_mode": settings.use_mock_providers,
        "background_tasks": settings.allow_background_tasks,
        "store_backend": backend,
        "shared_store": backend in {"redis", "oss"},
    }


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _truthy(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _resolved_store_backend(settings: Settings) -> str:
    backend = (settings.store_backend or "auto").strip().lower()
    if backend == "auto":
        if settings.redis_url:
            return "redis"
        if all([settings.oss_access_key, settings.oss_secret_key, settings.oss_bucket, settings.oss_endpoint]):
            return "oss"
        return "local"
    return backend


def _normalize_login_username(raw: str) -> str:
    # Accept common accidental suffix punctuation and spaces in manually typed usernames.
    return (raw or "").strip().rstrip(".。")


def _validate_duration_by_scenario(duration_sec: int, scenario_type: ScenarioType) -> None:
    if scenario_type == ScenarioType.product_video:
        if duration_sec < 15 or duration_sec > 50:
            raise HTTPException(
                status_code=422,
                detail="desired_duration_sec must be between 15 and 50 for product_video",
            )
        return
    if duration_sec < 15 or duration_sec > 50:
        raise HTTPException(
            status_code=422,
            detail="desired_duration_sec must be between 15 and 50",
        )


def _resolve_tool_type(raw_tool_type: str | None) -> ToolType:
    if not raw_tool_type:
        return ToolType.intro_video_multi_script
    value = raw_tool_type.strip()
    try:
        return ToolType(value)
    except Exception as exc:  # pragma: no cover - validation path
        raise HTTPException(status_code=422, detail=f"Invalid tool_type: {raw_tool_type}") from exc


def _normalize_async_mode(request: object) -> object:
    if settings.allow_background_tasks:
        return request
    if hasattr(request, "async_mode"):
        return request.model_copy(update={"async_mode": False})
    return request


def _guess_suffix(value: str, fallback: str = ".png") -> str:
    try:
        suffix = Path(value).suffix
    except Exception:
        suffix = ""
    return suffix if suffix else fallback


def _guess_mime_from_suffix(suffix: str, fallback: str = "image/png") -> str:
    ext = suffix.lower().lstrip(".")
    if ext in {"jpg", "jpeg"}:
        return "image/jpeg"
    if ext == "webp":
        return "image/webp"
    if ext == "gif":
        return "image/gif"
    if ext == "bmp":
        return "image/bmp"
    if ext == "png":
        return "image/png"
    return fallback


@app.post("/api/v1/projects", response_model=CreateProjectResponse)
async def create_project(
    http_request: Request,
    image: UploadFile | None = File(default=None),
    style_reference_images: list[UploadFile] = File(default=[]),
    reference_images: list[UploadFile] = File(default=[]),
    identity_image: UploadFile | None = File(default=None),
    product_name: str = Form(...),
    tool_type: str = Form(ToolType.intro_video_multi_script.value),
    scenario_type: ScenarioType = Form(ScenarioType.product_video),
    template_name: str = Form("general"),
    quality_level: QualityLevel = Form(QualityLevel.standard),
    target_audience: str = Form("注重体验和性价比的人群"),
    platform: str = Form("douyin"),
    price_band: str = Form("未填写"),
    key_features: str = Form(""),
    cta_text: str = Form("点击了解详情"),
    desired_duration_sec: int = Form(15),
    tone: str = Form("真实、克制、有钩子"),
    scene_style: str = Form(""),
    scene_goals: str = Form(""),
    retouch_targets: str = Form(""),
    fidelity_requirement: str = Form(""),
    background_policy: str = Form(BackgroundPolicy.keep_original.value),
    output_aspect_ratio: str = Form("original"),
    retouch_strength: str = Form(RetouchStrength.light.value),
    content_template: str = Form("talking_head"),
    presenter_mode: PresenterMode = Form(PresenterMode.none),
    presenter_source: PresenterSource = Form(PresenterSource.virtual),
    presenter_image_url: str | None = Form(default=None),
    goal_type: str = Form("conversion"),
    evidence_points: str = Form(""),
    compliance_blocklist: str = Form(""),
    channels: str = Form("douyin"),
    creative_direction: str = Form(""),
    target_final_count: int = Form(9),
    takes_per_shot: int = Form(3),
    shot_plan_mode: str = Form("meaning_first"),
    workflow_mode: str | None = Form(default=None),
    identity_replace: str = Form("false"),
    image_public_url: str | None = Form(default=None),
    image_mime: str | None = Form(default=None),
    image_suffix: str | None = Form(default=None),
    reference_image_public_urls: str = Form(""),
    style_reference_image_public_urls: str = Form(""),
    identity_image_public_url: str | None = Form(default=None),
    project_id: str | None = Form(default=None),
    camera_yaw: int = Form(0),
    camera_pitch: int = Form(0),
    camera_distance: str = Form("medium"),
    camera_focal_mm: str = Form("50"),
    camera_aspect_ratio: str = Form("1:1"),
    service: PipelineService = Depends(get_pipeline_service),
) -> CreateProjectResponse:
    resolved_tool = _resolve_tool_type(tool_type)
    mapped_scenario = service.tool_to_scenario(resolved_tool)
    scenario = mapped_scenario if scenario_type == ScenarioType.product_video else scenario_type
    template_defaults = service.get_template_defaults(resolved_tool, template_name)

    _validate_duration_by_scenario(desired_duration_sec, scenario)

    normalized_shot_plan_mode = shot_plan_mode.strip() or "meaning_first"
    if normalized_shot_plan_mode != "meaning_first":
        raise HTTPException(status_code=422, detail="shot_plan_mode must be meaning_first")

    resolved_workflow_mode = WorkflowMode.default
    if workflow_mode and workflow_mode.strip():
        try:
            resolved_workflow_mode = WorkflowMode(workflow_mode.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="workflow_mode is invalid") from exc

    image_bytes = b""
    resolved_image_public_url = (image_public_url or "").strip() or None
    resolved_image_suffix = str(image_suffix or "")
    resolved_image_mime = str(image_mime or "")
    if image is not None:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image file")
        dimensions = get_image_dimensions(image_bytes)
        if dimensions and (dimensions[0] < 14 or dimensions[1] < 14):
            raise HTTPException(
                status_code=422,
                detail="Image is too small. Minimum supported size is 14x14 pixels.",
            )
        resolved_image_suffix = Path(image.filename).suffix if image.filename else ".png"
        resolved_image_mime = image.content_type or "image/png"
    else:
        if not resolved_image_public_url:
            raise HTTPException(status_code=422, detail="image or image_public_url is required")
        resolved_image_suffix = resolved_image_suffix or _guess_suffix(resolved_image_public_url, ".png")
        resolved_image_mime = resolved_image_mime or _guess_mime_from_suffix(resolved_image_suffix)

    features = _split_csv(key_features)
    if not features:
        features = [
            str(item)
            for item in template_defaults.get("key_features", [])
            if str(item).strip()
        ]
    evidence = _split_csv(evidence_points)
    if not evidence:
        evidence = [
            str(item)
            for item in template_defaults.get("evidence_points", [])
            if str(item).strip()
        ]
    effective_platform = platform.strip() or str(template_defaults.get("platform") or "douyin")
    effective_target_audience = target_audience.strip() or str(
        template_defaults.get("target_audience") or "注重体验和性价比的人群"
    )
    effective_tone = tone.strip() or str(template_defaults.get("tone") or "真实、克制、有钩子")
    effective_channels = _split_csv(channels)
    if not effective_channels:
        effective_channels = [
            str(item)
            for item in template_defaults.get("channels", [])
            if str(item).strip()
        ] or [effective_platform]
    effective_blocklist = _split_csv(compliance_blocklist)
    if not effective_blocklist:
        effective_blocklist = [
            str(item)
            for item in template_defaults.get("compliance_blocklist", [])
            if str(item).strip()
        ]
    if scenario == ScenarioType.product_image_suite:
        final_scene_style = scene_style.strip() or str(template_defaults.get("scene_style") or "").strip()
        raw_scene_goals = scene_goals.strip()
        if not raw_scene_goals:
            raw_scene_goals = ",".join(
                [str(item) for item in template_defaults.get("scene_goals", []) if str(item).strip()]
            )
        if final_scene_style:
            features.append(f"风格:{final_scene_style}")
        if raw_scene_goals:
            evidence.append(f"出图目标:{raw_scene_goals}")
    if scenario == ScenarioType.model_retouch:
        final_retouch_targets = retouch_targets.strip() or ",".join(
            [str(item) for item in template_defaults.get("retouch_targets", []) if str(item).strip()]
        )
        final_fidelity = fidelity_requirement.strip() or str(template_defaults.get("fidelity_requirement") or "")
        if final_retouch_targets:
            features.append(f"精修目标:{final_retouch_targets}")
        if final_fidelity:
            evidence.append(f"保真要求:{final_fidelity}")
    if creative_direction.strip():
        evidence.append(f"创意指令:{creative_direction.strip()}")

    try:
        brief = ProductBrief(
            product_name=product_name,
            target_audience=effective_target_audience,
            platform=effective_platform,
            price_band=price_band,
            key_features=features,
            cta_text=cta_text,
            desired_duration_sec=15 if resolved_tool == ToolType.quick_video_15s else desired_duration_sec,
            tone=effective_tone,
            content_template=content_template,
            presenter_mode=presenter_mode,
            presenter_source=presenter_source,
            presenter_image_url=presenter_image_url,
            goal_type=goal_type,
            evidence_points=evidence,
            compliance_blocklist=effective_blocklist,
            channels=effective_channels,
            creative_direction=creative_direction.strip(),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    parsed_reference_public_urls = _split_csv(reference_image_public_urls.replace("\n", ","))
    parsed_style_public_urls = _split_csv(style_reference_image_public_urls.replace("\n", ","))
    if parsed_style_public_urls:
        parsed_reference_public_urls.extend(parsed_style_public_urls)
    identity_public_url = identity_image_public_url.strip() if identity_image_public_url else ""

    all_reference_images = [*style_reference_images, *reference_images]
    uploaded_reference_images: list[dict[str, str | bytes]] = []
    for idx, ref in enumerate(all_reference_images):
        ref_bytes = await ref.read()
        if not ref_bytes:
            continue
        ref_dimensions = get_image_dimensions(ref_bytes)
        if ref_dimensions and (ref_dimensions[0] < 14 or ref_dimensions[1] < 14):
            raise HTTPException(
                status_code=422,
                detail="Reference image is too small. Minimum supported size is 14x14 pixels.",
            )
        uploaded_reference_images.append(
            {
                "image_bytes": ref_bytes,
                "image_mime": ref.content_type or "image/png",
                "image_suffix": Path(ref.filename).suffix if ref.filename else ".png",
                "role": f"reference_{idx + 1}",
            }
        )

    identity_required = _truthy(identity_replace) if scenario == ScenarioType.model_retouch else False
    if identity_image is not None:
        identity_bytes = await identity_image.read()
        if identity_bytes:
            identity_dimensions = get_image_dimensions(identity_bytes)
            if identity_dimensions and (identity_dimensions[0] < 14 or identity_dimensions[1] < 14):
                raise HTTPException(
                    status_code=422,
                    detail="Identity image is too small. Minimum supported size is 14x14 pixels.",
                )
            uploaded_reference_images.append(
                {
                    "image_bytes": identity_bytes,
                    "image_mime": identity_image.content_type or "image/png",
                    "image_suffix": Path(identity_image.filename).suffix if identity_image.filename else ".png",
                    "role": "identity",
                }
            )
            identity_required = True
    if identity_public_url:
        identity_required = True

    reference_count = len(uploaded_reference_images) + len(parsed_reference_public_urls) + (1 if identity_public_url else 0)
    if reference_count > 0:
        evidence_with_refs = [*brief.evidence_points, f"参考图数量:{reference_count}"]
        brief = brief.model_copy(update={"evidence_points": evidence_with_refs[:12]})

    suffix = resolved_image_suffix
    image_mime = resolved_image_mime

    resolved_background_policy = BackgroundPolicy.keep_original
    resolved_retouch_strength = RetouchStrength.light
    resolved_output_aspect_ratio = "original"
    if scenario == ScenarioType.model_retouch:
        try:
            resolved_background_policy = BackgroundPolicy(background_policy.strip() or BackgroundPolicy.keep_original.value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="background_policy is invalid") from exc
        try:
            resolved_retouch_strength = RetouchStrength(retouch_strength.strip() or RetouchStrength.light.value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="retouch_strength is invalid") from exc
        allowed_output_aspect = {"original", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
        resolved_output_aspect_ratio = (output_aspect_ratio or "original").strip().lower() or "original"
        if resolved_output_aspect_ratio not in allowed_output_aspect:
            raise HTTPException(status_code=422, detail="output_aspect_ratio is invalid")

    camera_inputs: dict[str, str | int] | None = None
    if resolved_tool == ToolType.multi_angle_camera:
        camera_inputs = {
            "yaw": max(-180, min(180, int(camera_yaw))),
            "pitch": max(-45, min(45, int(camera_pitch))),
            "distance": str(camera_distance or "medium"),
            "focal_mm": str(camera_focal_mm or "50"),
            "aspect_ratio": str(camera_aspect_ratio or "1:1"),
        }

    set_config: SetConfig | None = None
    if resolved_tool == ToolType.product_image_suite:
        if target_final_count < 3 or target_final_count > 30:
            raise HTTPException(status_code=422, detail="target_final_count must be between 3 and 30")
        if takes_per_shot < 1 or takes_per_shot > 4:
            raise HTTPException(status_code=422, detail="takes_per_shot must be between 1 and 4")
        set_config = SetConfig(
            target_final_count=target_final_count,
            takes_per_shot=takes_per_shot,
            required_min_candidates=target_final_count,
        )
        if resolved_workflow_mode == WorkflowMode.default:
            resolved_workflow_mode = WorkflowMode.product_set
    elif resolved_tool == ToolType.model_retouch and resolved_workflow_mode == WorkflowMode.default:
        resolved_workflow_mode = WorkflowMode.retouch_per_image

    project = await service.create_project(
        image_bytes=image_bytes,
        image_mime=image_mime,
        image_suffix=suffix,
        brief=brief,
        image_public_url=resolved_image_public_url,
        owner_username=_current_username(http_request),
        tool_type=resolved_tool,
        scenario_type=scenario,
        template_name=template_name,
        quality_level=quality_level,
        reference_images=uploaded_reference_images,
        reference_image_public_urls=parsed_reference_public_urls,
        identity_image_public_url=identity_public_url or None,
        identity_required=identity_required,
        background_policy=resolved_background_policy,
        output_aspect_ratio=resolved_output_aspect_ratio,
        retouch_strength=resolved_retouch_strength,
        camera_inputs=camera_inputs,
        set_config=set_config,
        workflow_mode=resolved_workflow_mode,
        project_id=project_id,
    )
    return CreateProjectResponse(project=project)


@app.post("/api/v1/tools/model_retouch/batch-create", response_model=BatchCreateModelRetouchResponse)
async def batch_create_model_retouch(
    http_request: Request,
    images: list[UploadFile] = File(default=[]),
    style_reference_images: list[UploadFile] = File(default=[]),
    identity_image: UploadFile | None = File(default=None),
    image_public_urls: str = Form(""),
    style_reference_image_public_urls: str = Form(""),
    identity_image_public_url: str | None = Form(default=None),
    product_name: str = Form("模特精修任务"),
    template_name: str = Form("general"),
    quality_level: QualityLevel = Form(QualityLevel.standard),
    target_audience: str = Form("服饰与人像内容团队"),
    platform: str = Form("xiaohongshu"),
    price_band: str = Form("未填写"),
    key_features: str = Form(""),
    cta_text: str = Form("点击了解详情"),
    tone: str = Form("写实精修，克制自然"),
    evidence_points: str = Form(""),
    compliance_blocklist: str = Form(""),
    channels: str = Form("xiaohongshu,instagram,tiktok"),
    creative_direction: str = Form(""),
    retouch_targets: str = Form(""),
    fidelity_requirement: str = Form(""),
    retouch_scope: str = Form("per_image"),
    workflow_mode: str | None = Form(default=None),
    identity_replace: str = Form("false"),
    background_policy: str = Form(BackgroundPolicy.keep_original.value),
    output_aspect_ratio: str = Form("original"),
    retouch_strength: str = Form(RetouchStrength.light.value),
    service: PipelineService = Depends(get_pipeline_service),
) -> BatchCreateModelRetouchResponse:
    parsed_image_public_urls = _split_csv(image_public_urls.replace("\n", ","))
    if not images and not parsed_image_public_urls:
        raise HTTPException(status_code=422, detail="images or image_public_urls is required")
    normalized_scope = retouch_scope.strip().lower() if retouch_scope else "per_image"
    if normalized_scope != "per_image":
        raise HTTPException(status_code=422, detail="retouch_scope only supports per_image")
    resolved_workflow_mode = WorkflowMode.retouch_per_image
    if workflow_mode and workflow_mode.strip():
        try:
            resolved_workflow_mode = WorkflowMode(workflow_mode.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="workflow_mode is invalid") from exc
    if resolved_workflow_mode == WorkflowMode.default:
        resolved_workflow_mode = WorkflowMode.retouch_per_image
    if resolved_workflow_mode != WorkflowMode.retouch_per_image:
        raise HTTPException(
            status_code=422,
            detail="model_retouch batch_create only supports workflow_mode=retouch_per_image",
        )
    try:
        resolved_background_policy = BackgroundPolicy(background_policy.strip() or BackgroundPolicy.keep_original.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="background_policy is invalid") from exc
    try:
        resolved_retouch_strength = RetouchStrength(retouch_strength.strip() or RetouchStrength.light.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="retouch_strength is invalid") from exc
    allowed_output_aspect = {"original", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
    resolved_output_aspect_ratio = (output_aspect_ratio or "original").strip().lower() or "original"
    if resolved_output_aspect_ratio not in allowed_output_aspect:
        raise HTTPException(status_code=422, detail="output_aspect_ratio is invalid")
    template_defaults = service.get_template_defaults(ToolType.model_retouch, template_name)
    effective_channels = _split_csv(channels)
    if not effective_channels:
        effective_channels = [
            str(item)
            for item in template_defaults.get("channels", [])
            if str(item).strip()
        ] or [platform]
    features = _split_csv(key_features) or [
        str(item)
        for item in template_defaults.get("key_features", [])
        if str(item).strip()
    ]
    evidence = _split_csv(evidence_points) or [
        str(item)
        for item in template_defaults.get("evidence_points", [])
        if str(item).strip()
    ]
    if retouch_targets.strip():
        features.append(f"精修目标:{retouch_targets.strip()}")
    if fidelity_requirement.strip():
        evidence.append(f"保真要求:{fidelity_requirement.strip()}")
    if creative_direction.strip():
        evidence.append(f"创意指令:{creative_direction.strip()}")
    constraints = _split_csv(compliance_blocklist) or [
        str(item)
        for item in template_defaults.get("compliance_blocklist", [])
        if str(item).strip()
    ]

    style_refs: list[dict[str, str | bytes]] = []
    style_public_urls = _split_csv(style_reference_image_public_urls.replace("\n", ","))
    for idx, ref in enumerate(style_reference_images, start=1):
        ref_bytes = await ref.read()
        if not ref_bytes:
            continue
        dims = get_image_dimensions(ref_bytes)
        if dims and (dims[0] < 14 or dims[1] < 14):
            raise HTTPException(status_code=422, detail="Reference image is too small. Minimum supported size is 14x14 pixels.")
        style_refs.append(
            {
                "image_bytes": ref_bytes,
                "image_mime": ref.content_type or "image/png",
                "image_suffix": Path(ref.filename).suffix if ref.filename else ".png",
                "role": f"reference_{idx}",
            }
        )

    identity_ref: dict[str, str | bytes] | None = None
    if identity_image is not None:
        identity_bytes = await identity_image.read()
        if identity_bytes:
            dims = get_image_dimensions(identity_bytes)
            if dims and (dims[0] < 14 or dims[1] < 14):
                raise HTTPException(status_code=422, detail="Identity image is too small. Minimum supported size is 14x14 pixels.")
            identity_ref = {
                "image_bytes": identity_bytes,
                "image_mime": identity_image.content_type or "image/png",
                "image_suffix": Path(identity_image.filename).suffix if identity_image.filename else ".png",
                "role": "identity",
            }
    identity_public_url = identity_image_public_url.strip() if identity_image_public_url else ""

    batch_group_id = str(uuid4())
    projects: list[ProjectRecord] = []
    identity_required = _truthy(identity_replace) or bool(identity_ref) or bool(identity_public_url)
    all_images: list[tuple[str, bytes, str, str | None]] = []
    for image in images:
        image_bytes = await image.read()
        if not image_bytes:
            continue
        dims = get_image_dimensions(image_bytes)
        if dims and (dims[0] < 14 or dims[1] < 14):
            raise HTTPException(status_code=422, detail="Image is too small. Minimum supported size is 14x14 pixels.")
        all_images.append((image.filename or "image.png", image_bytes, image.content_type or "image/png", None))
    for url in parsed_image_public_urls:
        if not url:
            continue
        all_images.append((url, b"", _guess_mime_from_suffix(_guess_suffix(url, ".png")), url))

    for idx, (name, image_bytes, mime, public_url) in enumerate(all_images, start=1):
        refs = [*style_refs]
        if identity_ref:
            refs = [*refs, identity_ref]
        brief = ProductBrief(
            product_name=f"{product_name}-{idx}",
            target_audience=target_audience,
            platform=platform,
            price_band=price_band,
            key_features=features[:8],
            cta_text=cta_text,
            desired_duration_sec=15,
            tone=tone,
            evidence_points=evidence[:12],
            compliance_blocklist=constraints[:20],
            channels=effective_channels[:6],
            creative_direction=creative_direction.strip(),
        )
        project = await service.create_project(
            image_bytes=image_bytes,
            image_mime=mime,
            image_suffix=_guess_suffix(name, ".png"),
            brief=brief,
            image_public_url=public_url,
            owner_username=_current_username(http_request),
            tool_type=ToolType.model_retouch,
            scenario_type=ScenarioType.model_retouch,
            template_name=template_name,
            quality_level=quality_level,
            batch_group_id=batch_group_id,
            batch_role=BatchRole.controller if idx == 1 else BatchRole.member,
            reference_images=refs,
            reference_image_public_urls=style_public_urls,
            identity_image_public_url=identity_public_url or None,
            identity_required=identity_required or bool(identity_public_url),
            background_policy=resolved_background_policy,
            output_aspect_ratio=resolved_output_aspect_ratio,
            retouch_strength=resolved_retouch_strength,
            workflow_mode=resolved_workflow_mode,
        )
        projects.append(project)
    if not projects:
        raise HTTPException(status_code=422, detail="未读取到有效主素材图片，请重新上传")
    done_images = sum(
        1 for item in projects if item.task_status.value == "done" or item.status.value == "completed"
    )
    failed_images = sum(
        1 for item in projects if item.task_status.value == "failed" or item.status.value == "failed"
    )
    queued_images = max(0, len(projects) - done_images - failed_images)
    return BatchCreateModelRetouchResponse(
        batch_group_id=batch_group_id,
        controller_project_id=projects[0].project_id if projects else None,
        project_ids=[item.project_id for item in projects],
        created_count=len(projects),
        total_images=len(projects),
        done_images=done_images,
        failed_images=failed_images,
        queued_images=queued_images,
        projects=projects,
    )


@app.post("/api/v1/projects/batch", response_model=BatchCreateProjectResponse)
async def create_batch_projects(
    http_request: Request,
    request: BatchCreateRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> BatchCreateProjectResponse:
    scenario = service.tool_to_scenario(request.tool_type)
    if request.scenario_type != ScenarioType.product_video:
        scenario = request.scenario_type
    projects = await service.create_batch_projects(
        items=[item.model_dump(mode="json") for item in request.items],
        scenario_type=scenario,
        template_name=request.template_name,
        quality_level=request.quality_level,
        owner_username=_current_username(http_request),
        tool_type=request.tool_type,
    )
    return BatchCreateProjectResponse(projects=projects)


@app.get("/api/v1/projects/{project_id}", response_model=ProjectRecord)
def get_project(
    project_id: str,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    return _ensure_project_access(project_id=project_id, request=request, service=service)


@app.get("/api/v1/projects", response_model=list[ProjectTaskItem])
def list_projects(
    request: Request,
    limit: int = 20,
    query: str | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[ProjectTaskItem]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    current_user = _current_user_record(request, service)
    projects = service.list_projects(limit=limit, query=query)
    projects = [item for item in projects if _can_access_project(item, current_user)]

    task_items: list[ProjectTaskItem] = []
    for item in projects:
        try:
            progress = service.get_project_progress(item.project_id)
            percent = progress.progress_percent_weighted
            current_stage = progress.current_stage
            label = (
                f"{progress.progress_profile} | {progress.completion_criteria}"
                if progress.completion_criteria
                else progress.current_stage
            )
        except Exception as exc:  # pragma: no cover - defensive fallback for legacy/broken records
            logger.exception("Failed to compute progress for project %s: %s", item.project_id, exc)
            percent = 0
            current_stage = "failed" if item.status.value == "failed" else "plan"
            label = "progress_unavailable | 使用默认进度兜底"
        task_items.append(
            ProjectTaskItem(
                project_id=item.project_id,
                tool_type=item.tool_type,
                product_name=item.brief.product_name,
                scenario_type=item.scenario_type,
                template_name=item.template_name,
                status=item.status,
                storyboard_status=item.storyboard_status,
                current_stage=current_stage,
                progress_percent=percent,
                progress_label=label,
                batch_group_id=item.batch_group_id,
                render_id=item.render_id,
                updated_at=item.updated_at,
            )
        )
    stage_rank = {
        "master_script": 0,
        "plan": 1,
        "prompt": 2,
        "identity": 3,
        "storyboard": 3,
        "generate": 3,
        "render": 4,
        "review": 5,
        "completed": 6,
        "failed": 7,
    }
    task_items.sort(
        key=lambda row: (
            stage_rank.get(row.current_stage, 99),
            -(row.progress_percent or 0),
            -row.updated_at.timestamp(),
        )
    )
    return task_items


@app.get("/api/v1/tools/kpi", response_model=DashboardKpi)
def get_tools_kpi(
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> DashboardKpi:
    current_user = _current_user_record(request, service)
    if _is_privileged_user(current_user):
        return DashboardKpi.model_validate(service.get_dashboard_kpi())
    projects = [item for item in service.list_projects(limit=10000) if _can_access_project(item, current_user)]
    project_ids = {item.project_id for item in projects}
    assets = [
        item
        for item in service.list_assets_global(limit=100000)
        if item.project_id in project_ids
    ]
    showcase_assets = sum(1 for item in assets if "showcase_shared" in [tag.lower() for tag in item.tags])
    share_points_earned = sum(int((item.metadata or {}).get("share_reward_points") or 0) for item in assets)
    return DashboardKpi(
        total_projects=len(projects),
        running_projects=sum(
            1
            for item in projects
            if item.task_status.value in {"running", "queued"}
        ),
        failed_projects=sum(1 for item in projects if item.task_status.value == "failed"),
        done_projects=sum(1 for item in projects if item.task_status.value == "done"),
        total_assets=len(assets),
        uploaded_assets=sum(1 for item in assets if item.source_type.value == "uploaded"),
        generated_assets=sum(1 for item in assets if item.source_type.value == "generated"),
        showcase_assets=showcase_assets,
        share_points_earned=share_points_earned,
    )


@app.get("/api/v1/quality/summary", response_model=QualitySummaryResponse)
def get_quality_summary(
    request: Request,
    days: int = 7,
    tool_type: ToolType | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> QualitySummaryResponse:
    _require_privileged(request, service)
    if days < 1 or days > 90:
        raise HTTPException(status_code=422, detail="days must be between 1 and 90")
    return service.get_quality_summary(days=days, tool_type=tool_type)


@app.get("/api/v1/prompts/metrics", response_model=PromptVersionMetricsResponse)
def get_prompt_metrics(
    request: Request,
    days: int = 7,
    tool_type: ToolType | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> PromptVersionMetricsResponse:
    _require_privileged(request, service)
    if days < 1 or days > 90:
        raise HTTPException(status_code=422, detail="days must be between 1 and 90")
    return service.get_prompt_version_metrics(days=days, tool_type=tool_type)


@app.get("/api/v1/ui/tool-meta")
def get_ui_tool_meta() -> list[dict[str, object]]:
    meta = {
        ToolType.intro_video_multi_script: {
            "name": "转化讲解视频工坊",
            "category": "video",
            "default_cta": "创建并进入工作台",
            "stages": ["需求与素材", "AI方案与提示词", "视频生成", "人工确认"],
        },
        ToolType.product_image_suite: {
            "name": "商品棚拍出图工坊",
            "category": "image",
            "default_cta": "创建并进入工作台",
            "stages": ["需求与素材", "组图拍摄方案", "开始试拍", "选片分享"],
        },
        ToolType.model_retouch: {
            "name": "模特人像精修工坊",
            "category": "image",
            "default_cta": "批量创建任务",
            "stages": ["素材确认", "身份确认", "批量精修执行", "结果审核与导出"],
        },
        ToolType.quick_video_15s: {
            "name": "15秒场景短片工坊",
            "category": "video",
            "default_cta": "创建并进入工作台",
            "stages": ["需求与素材", "AI方案与提示词", "一键生成候选", "人工确认"],
        },
        ToolType.multi_angle_camera: {
            "name": "多角度展品工坊",
            "category": "image",
            "default_cta": "创建并进入工作台",
            "stages": ["素材与目标", "机位控制", "生成当前角度", "人工确认"],
        },
    }
    rows: list[dict[str, object]] = []
    for tool_type, slug in TOOL_SLUG_MAP.items():
        info = meta[tool_type]
        rows.append(
            {
                "tool_type": tool_type.value,
                "slug": slug,
                "name": info["name"],
                "category": info["category"],
                "default_cta": info["default_cta"],
                "stages": info["stages"],
            }
        )
    return rows


@app.get("/api/v1/ui/nav-context")
def get_ui_nav_context(
    request: Request,
    project_id: str | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> dict[str, object]:
    if not project_id:
        return {"breadcrumbs": ["首页", "工具箱"]}
    project = _ensure_project_access(project_id=project_id, request=request, service=service)
    slug = TOOL_SLUG_MAP.get(project.tool_type, "intro-video")
    return {
        "breadcrumbs": [
            "首页",
            TOOL_BY_TYPE_TEXT[project.tool_type],
            "任务中心",
            project.brief.product_name or project.project_id,
        ],
        "tool_slug": slug,
    }


@app.get("/api/v1/tools/{tool_type}/templates", response_model=list[ToolTemplateOption])
def list_tool_templates(
    tool_type: ToolType,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[ToolTemplateOption]:
    templates = service.list_tool_templates(tool_type=tool_type)
    return [ToolTemplateOption.model_validate(item) for item in templates]


@app.get("/api/v1/tools/{tool_type}/tasks", response_model=list[ProjectTaskItem])
def list_tool_tasks(
    tool_type: ToolType,
    request: Request,
    limit: int = 20,
    query: str | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[ProjectTaskItem]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    current_user = _current_user_record(request, service)
    items = service.list_projects_by_tool(tool_type=tool_type, limit=limit, query=query)
    items = [item for item in items if _can_access_project(item, current_user)]
    output: list[ProjectTaskItem] = []
    for item in items:
        try:
            progress = service.get_project_progress(item.project_id)
            percent = progress.progress_percent_weighted
            current_stage = progress.current_stage
            progress_label = (
                f"{progress.progress_profile} | {progress.completion_criteria}"
                if progress.completion_criteria
                else progress.current_stage
            )
        except Exception as exc:  # pragma: no cover - defensive fallback for legacy/broken records
            logger.exception("Failed to compute tool progress for project %s: %s", item.project_id, exc)
            percent = 0
            current_stage = "failed" if item.status.value == "failed" else "plan"
            progress_label = "progress_unavailable | 使用默认进度兜底"
        output.append(
            ProjectTaskItem(
                project_id=item.project_id,
                tool_type=item.tool_type,
                product_name=item.brief.product_name,
                scenario_type=item.scenario_type,
                template_name=item.template_name,
                status=item.status,
                storyboard_status=item.storyboard_status,
                current_stage=current_stage,
                progress_percent=percent,
                progress_label=progress_label,
                batch_group_id=item.batch_group_id,
                render_id=item.render_id,
                updated_at=item.updated_at,
            )
        )
    return output


@app.get("/api/v1/projects/{project_id}/progress", response_model=ProjectProgress)
def get_project_progress(
    project_id: str,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectProgress:
    _ensure_project_access(project_id=project_id, request=request, service=service)
    try:
        return service.get_project_progress(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None


@app.post("/api/v1/projects/{project_id}/retry", response_model=ProjectRecord)
async def retry_project(
    project_id: str,
    http_request: Request,
    request: RetryProjectRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    stage = request.stage if request else None
    async_mode = bool(request.async_mode) if request else False
    try:
        return await service.retry_project(project_id=project_id, stage=stage, async_mode=async_mode)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/projects/{project_id}/logs", response_model=list[ProjectLog])
def get_project_logs(
    project_id: str,
    request: Request,
    limit: int = 200,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[ProjectLog]:
    _ensure_project_access(project_id=project_id, request=request, service=service)
    try:
        return service.get_project_logs(project_id=project_id, limit=limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None


@app.post("/api/v1/projects/{project_id}/plan", response_model=ProjectRecord)
async def generate_project_plan(
    project_id: str,
    http_request: Request,
    request: GeneratePlanRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    force = bool(request.force) if request else False
    async_mode = bool(request.async_mode) if request else True
    try:
        return await service.generate_project_plan(project_id=project_id, force=force, async_mode=async_mode)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/v1/projects/{project_id}/plan", response_model=ProjectRecord)
def update_project_plan(
    project_id: str,
    http_request: Request,
    request: UpdatePlanRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        return service.update_project_plan(project_id=project_id, project_plan=request.project_plan)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/v1/projects/{project_id}/master-script", response_model=ProjectRecord)
def update_master_script(
    project_id: str,
    http_request: Request,
    request: UpdateMasterScriptRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        return service.update_master_script(project_id=project_id, master_script=request.master_script)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/derive-prompts", response_model=ProjectRecord)
async def derive_prompts(
    project_id: str,
    http_request: Request,
    request: DerivePromptsRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    force = bool(request.force) if request else False
    try:
        return await service.derive_prompts(project_id=project_id, force=force)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/v1/projects/{project_id}/multi-angle/camera-inputs", response_model=ProjectRecord)
def update_multi_angle_camera_inputs(
    project_id: str,
    http_request: Request,
    request: CameraInputsRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        return service.update_camera_inputs(project_id=project_id, camera_inputs=request.model_dump())
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/multi-angle/plan", response_model=ProjectRecord)
async def generate_multi_angle_plan(
    project_id: str,
    http_request: Request,
    request: GeneratePlanRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        return await service.generate_multi_angle_plan(project_id=project_id, force=bool(request.force) if request else False)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/multi-angle/generate", response_model=GenerateAssetsResponse)
async def generate_multi_angle_assets(
    project_id: str,
    http_request: Request,
    request: GenerateRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> GenerateAssetsResponse:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    normalized = _normalize_async_mode(request)
    try:
        result = await service.generate_for_project(
            project_id=project_id,
            stage="auto",
            candidates_per_prompt=1,
            async_mode=normalized.async_mode,
            image_aspect_ratio=normalized.image_aspect_ratio,
            image_resolution=normalized.image_resolution,
            image_output_format=normalized.image_output_format,
        )
        return GenerateAssetsResponse(
            project=result["project"],
            assets=result.get("assets", []),
            quality_reports=result.get("quality_reports", []),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/identity/generate-candidate", response_model=IdentityActionResponse)
async def generate_identity_candidate(
    project_id: str,
    http_request: Request,
    request: GenerateIdentityCandidateRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> IdentityActionResponse:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        project, asset = await service.generate_identity_candidate(
            project_id=project_id,
            regenerate=bool(request.force) if request else False,
            design_inputs=request.model_dump(exclude={"force"}) if request else None,
        )
        return IdentityActionResponse(project=project, asset=asset)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/identity/regenerate-candidate", response_model=IdentityActionResponse)
async def regenerate_identity_candidate(
    project_id: str,
    http_request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> IdentityActionResponse:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        project, asset = await service.generate_identity_candidate(project_id=project_id, regenerate=True)
        return IdentityActionResponse(project=project, asset=asset)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/identity/confirm", response_model=IdentityActionResponse)
def confirm_identity_candidate(
    project_id: str,
    http_request: Request,
    request: IdentityActionRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> IdentityActionResponse:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        project, asset = service.confirm_identity_candidate(
            project_id=project_id,
            asset_id=request.asset_id if request else None,
        )
        return IdentityActionResponse(project=project, asset=asset)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/v1/tools/model_retouch/batches/{batch_group_id}",
    response_model=ModelRetouchBatchSummaryResponse,
)
def get_model_retouch_batch_summary(
    batch_group_id: str,
    http_request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> ModelRetouchBatchSummaryResponse:
    _ensure_model_retouch_batch_access(batch_group_id=batch_group_id, request=http_request, service=service)
    try:
        payload = service.get_model_retouch_batch(batch_group_id=batch_group_id)
        return ModelRetouchBatchSummaryResponse.model_validate(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Batch not found") from None


@app.post(
    "/api/v1/tools/model_retouch/batches/{batch_group_id}/identity/generate-candidate",
    response_model=ModelRetouchBatchSummaryResponse,
)
async def generate_model_retouch_batch_identity_candidate(
    batch_group_id: str,
    http_request: Request,
    request: BatchIdentityGenerateRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> ModelRetouchBatchSummaryResponse:
    _ensure_model_retouch_batch_access(batch_group_id=batch_group_id, request=http_request, service=service)
    try:
        payload, _ = await service.generate_model_retouch_batch_identity_candidate(
            batch_group_id=batch_group_id,
            design_inputs=request.model_dump(exclude={"force"}) if request else None,
            regenerate=bool(request.force) if request else False,
        )
        return ModelRetouchBatchSummaryResponse.model_validate(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Batch not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/v1/tools/model_retouch/batches/{batch_group_id}/identity/confirm",
    response_model=ModelRetouchBatchSummaryResponse,
)
def confirm_model_retouch_batch_identity(
    batch_group_id: str,
    http_request: Request,
    request: BatchIdentityConfirmRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ModelRetouchBatchSummaryResponse:
    _ensure_model_retouch_batch_access(batch_group_id=batch_group_id, request=http_request, service=service)
    try:
        payload, _ = service.confirm_model_retouch_batch_identity(
            batch_group_id=batch_group_id,
            asset_id=request.asset_id,
        )
        return ModelRetouchBatchSummaryResponse.model_validate(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Batch not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/v1/tools/model_retouch/batches/{batch_group_id}/identity/upload",
    response_model=ModelRetouchBatchSummaryResponse,
)
def upload_model_retouch_batch_identity(
    batch_group_id: str,
    http_request: Request,
    request: BatchIdentityUploadRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ModelRetouchBatchSummaryResponse:
    _ensure_model_retouch_batch_access(batch_group_id=batch_group_id, request=http_request, service=service)
    try:
        image_public_url = request.image_public_url.strip()
        if not image_public_url:
            raise ValueError("image_public_url is required")
        suffix = request.image_suffix.strip() if request.image_suffix else _guess_suffix(image_public_url, ".png")
        mime = request.image_mime.strip() if request.image_mime else _guess_mime_from_suffix(suffix)
        payload, _ = service.upload_model_retouch_batch_identity(
            batch_group_id=batch_group_id,
            image_public_url=image_public_url,
            image_mime=mime,
            image_suffix=suffix,
        )
        return ModelRetouchBatchSummaryResponse.model_validate(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Batch not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/v1/tools/model_retouch/batches/{batch_group_id}/identity/clear-uploaded",
    response_model=ModelRetouchBatchSummaryResponse,
)
def clear_model_retouch_batch_uploaded_identity(
    batch_group_id: str,
    http_request: Request,
    request: BatchIdentityClearUploadRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> ModelRetouchBatchSummaryResponse:
    _ensure_model_retouch_batch_access(batch_group_id=batch_group_id, request=http_request, service=service)
    try:
        payload, _ = service.clear_model_retouch_batch_uploaded_identity(
            batch_group_id=batch_group_id,
            asset_id=(request.asset_id or "").strip() if request else None,
        )
        return ModelRetouchBatchSummaryResponse.model_validate(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Batch not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/v1/tools/model_retouch/batches/{batch_group_id}/generate",
    response_model=ModelRetouchBatchSummaryResponse,
)
async def generate_model_retouch_batch_assets(
    batch_group_id: str,
    http_request: Request,
    request: BatchGenerateRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> ModelRetouchBatchSummaryResponse:
    _ensure_model_retouch_batch_access(batch_group_id=batch_group_id, request=http_request, service=service)
    payload_request = request or BatchGenerateRequest()
    if payload_request.async_mode:
        async def _runner() -> None:
            try:
                await service.generate_model_retouch_batch(
                    batch_group_id=batch_group_id,
                    project_ids=payload_request.project_ids,
                    output_aspect_ratio=payload_request.output_aspect_ratio,
                    image_resolution=payload_request.image_resolution,
                    image_output_format=payload_request.image_output_format,
                )
            except Exception:
                logger.exception("model retouch batch async generation failed: batch=%s", batch_group_id)

        asyncio.create_task(_runner())
        payload = service.get_model_retouch_batch(batch_group_id=batch_group_id)
        return ModelRetouchBatchSummaryResponse.model_validate(payload)
    try:
        payload = await service.generate_model_retouch_batch(
            batch_group_id=batch_group_id,
            project_ids=payload_request.project_ids,
            output_aspect_ratio=payload_request.output_aspect_ratio,
            image_resolution=payload_request.image_resolution,
            image_output_format=payload_request.image_output_format,
        )
        return ModelRetouchBatchSummaryResponse.model_validate(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Batch not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/v1/tools/model_retouch/batches/{batch_group_id}/retry",
    response_model=ModelRetouchBatchSummaryResponse,
)
async def retry_model_retouch_batch_assets(
    batch_group_id: str,
    http_request: Request,
    request: BatchRetryRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> ModelRetouchBatchSummaryResponse:
    _ensure_model_retouch_batch_access(batch_group_id=batch_group_id, request=http_request, service=service)
    try:
        payload = await service.retry_model_retouch_batch(
            batch_group_id=batch_group_id,
            project_ids=request.project_ids if request else None,
        )
        return ModelRetouchBatchSummaryResponse.model_validate(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Batch not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/tools/model_retouch/batches/{batch_group_id}/download-images")
async def download_model_retouch_batch_images(
    batch_group_id: str,
    request: Request,
    scope: str = "approved",
    service: PipelineService = Depends(get_pipeline_service),
) -> Response:
    _ensure_model_retouch_batch_access(batch_group_id=batch_group_id, request=request, service=service)
    try:
        archive_name, archive_bytes = await service.export_model_retouch_batch_archive(
            batch_group_id=batch_group_id,
            scope=scope,
        )
        return Response(
            content=archive_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{archive_name}"'},
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Batch not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/generate-images", response_model=GenerateAssetsResponse)
async def generate_images(
    project_id: str,
    http_request: Request,
    request: GenerateImagesRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> GenerateAssetsResponse:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    normalized = _normalize_async_mode(request)
    try:
        project, assets, quality_reports = await service.generate_images_for_project(
            project_id=project_id,
            request=normalized,
        )
        return GenerateAssetsResponse(
            project=project,
            assets=assets,
            quality_reports=quality_reports,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/generate-videos", response_model=RenderResponse)
async def generate_videos(
    project_id: str,
    http_request: Request,
    request: GenerateVideosRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> RenderResponse:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    normalized = _normalize_async_mode(request)
    try:
        return await service.generate_videos_for_project(project_id=project_id, request=normalized)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/review", response_model=ReviewResponse)
def review_asset(
    project_id: str,
    http_request: Request,
    request: ReviewRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ReviewResponse:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        project, decision = service.review_asset(project_id=project_id, request=request)
        return ReviewResponse(project=project, decision=decision)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/share", response_model=ShareAssetResponse)
def share_asset(
    project_id: str,
    http_request: Request,
    request: ShareAssetRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ShareAssetResponse:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        project, asset, awarded_points, total_points = service.share_asset_to_showcase(
            project_id=project_id,
            asset_id=request.asset_id,
            shared=request.shared,
        )
        return ShareAssetResponse(
            project=project,
            asset=asset,
            awarded_points=awarded_points,
            total_points=total_points,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/projects/{project_id}/download-images")
async def download_project_images(
    project_id: str,
    request: Request,
    scope: str = "generated",
    service: PipelineService = Depends(get_pipeline_service),
) -> Response:
    _ensure_project_access(project_id=project_id, request=request, service=service)
    try:
        archive_name, archive_bytes = await service.export_project_image_archive(
            project_id=project_id,
            scope=scope,
        )
        return Response(
            content=archive_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{archive_name}"'},
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/showcase/assets", response_model=list[AssetRecord])
def list_showcase_assets(
    limit: int = 120,
    tool_type: ToolType | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[AssetRecord]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    return service.list_showcase_assets(tool_type=tool_type, limit=limit)


@app.post("/api/v1/showcase/remix", response_model=ShowcaseRemixResponse)
async def remix_from_showcase(
    request: Request,
    payload: ShowcaseRemixRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ShowcaseRemixResponse:
    try:
        return await service.create_project_from_showcase_asset(
            owner_username=_current_username(request),
            asset_id=payload.asset_id,
            product_name=payload.product_name,
            template_name=payload.template_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/projects/{project_id}/assets", response_model=list[AssetRecord])
def list_project_assets(
    project_id: str,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[AssetRecord]:
    _ensure_project_access(project_id=project_id, request=request, service=service)
    return service.list_assets(project_id=project_id)


@app.get("/api/v1/projects/{project_id}/quality-reports", response_model=list[QualityReport])
def list_project_quality_reports(
    project_id: str,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[QualityReport]:
    _ensure_project_access(project_id=project_id, request=request, service=service)
    return service.list_quality_reports(project_id=project_id)


@app.get("/api/v1/projects/{project_id}/reviews", response_model=list[ReviewDecision])
def list_project_review_decisions(
    project_id: str,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[ReviewDecision]:
    _ensure_project_access(project_id=project_id, request=request, service=service)
    return service.list_review_decisions(project_id=project_id)


@app.get("/api/v1/assets/{asset_id}", response_model=AssetRecord)
def get_asset(
    asset_id: str,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> AssetRecord:
    asset = service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    project = _ensure_project_access(project_id=asset.project_id, request=request, service=service)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return asset


@app.get("/api/v1/assets", response_model=list[AssetRecord])
def list_assets_global(
    request: Request,
    source_type: str | None = None,
    tool_type: str | None = None,
    project_id: str | None = None,
    keyword: str | None = None,
    tag: str | None = None,
    limit: int = 200,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[AssetRecord]:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    items = service.list_assets_global(
        source_type=source_type,
        tool_type=tool_type,
        project_id=project_id,
        keyword=keyword,
        tag=tag,
        limit=limit,
    )
    current_user = _current_user_record(request, service)
    if _is_privileged_user(current_user):
        return items
    visible: list[AssetRecord] = []
    for item in items:
        project = service.get_project(item.project_id)
        if project and _can_access_project(project, current_user):
            visible.append(item)
    return visible


@app.patch("/api/v1/projects/{project_id}/prompt-inputs", response_model=ProjectRecord)
def update_prompt_inputs(
    project_id: str,
    http_request: Request,
    request: UpdatePromptInputsRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        return service.update_prompt_inputs(project_id=project_id, prompt_inputs=request.prompt_inputs)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None


@app.post("/api/v1/projects/{project_id}/generate")
async def generate_project(
    project_id: str,
    http_request: Request,
    request: GenerateRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> dict[str, object]:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    payload = request or GenerateRequest()
    normalized = _normalize_async_mode(payload)
    try:
        result = await service.generate_for_project(
            project_id=project_id,
            stage=normalized.stage,
            variants_per_shot=normalized.variants_per_shot,
            candidates_per_prompt=normalized.candidates_per_prompt,
            async_mode=normalized.async_mode,
            image_aspect_ratio=normalized.image_aspect_ratio,
            image_resolution=normalized.image_resolution,
            image_output_format=normalized.image_output_format,
            video_aspect_ratio=normalized.video_aspect_ratio,
            video_n_frames=normalized.video_n_frames,
            video_size=normalized.video_size,
            video_remove_watermark=normalized.video_remove_watermark,
            video_upload_method=normalized.video_upload_method,
        )
        return {"ok": True, **result}
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# Backward-compatible video-first endpoints
@app.post("/api/v1/projects/{project_id}/select-script", response_model=ProjectRecord)
def select_script(
    project_id: str,
    http_request: Request,
    request: SelectScriptRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        return service.select_script(project_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/storyboard/generate", response_model=ProjectRecord)
async def generate_storyboard(
    project_id: str,
    http_request: Request,
    request: GenerateStoryboardRequest | None = None,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    normalized = _normalize_async_mode(request) if request else None
    regenerate = bool(normalized.regenerate) if normalized else False
    try:
        if normalized and normalized.async_mode:
            return service.start_storyboard_generation(
                project_id=project_id,
                regenerate=regenerate,
            )
        return await service.generate_storyboard(project_id=project_id, regenerate=regenerate)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/storyboard/regenerate-shot", response_model=ProjectRecord)
async def regenerate_storyboard_shot(
    project_id: str,
    http_request: Request,
    request: RegenerateStoryboardShotRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    normalized = _normalize_async_mode(request)
    try:
        if normalized.async_mode:
            return service.start_storyboard_shot_regeneration(
                project_id=project_id,
                shot_id=normalized.shot_id,
            )
        return await service.regenerate_storyboard_shot(
            project_id=project_id,
            shot_id=normalized.shot_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/storyboard/approve-shot", response_model=ProjectRecord)
def approve_storyboard_shot(
    project_id: str,
    http_request: Request,
    request: ApproveStoryboardShotRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        return service.approve_storyboard_shot(
            project_id=project_id,
            shot_id=request.shot_id,
            status=request.status,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/storyboard/confirm", response_model=ProjectRecord)
def confirm_storyboard(
    project_id: str,
    http_request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> ProjectRecord:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    try:
        return service.confirm_storyboard(project_id=project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/projects/{project_id}/render", response_model=RenderResponse)
async def render_project(
    project_id: str,
    http_request: Request,
    request: RenderRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> RenderResponse:
    _ensure_project_access(project_id=project_id, request=http_request, service=service)
    normalized = _normalize_async_mode(request)
    try:
        if normalized.async_mode:
            project, render = service.start_render_project(project_id, normalized)
            return RenderResponse(project=project, render=render)
        project, render = await service.render_project(project_id, normalized)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RenderResponse(project=project, render=render)


@app.get("/api/v1/renders/{render_id}", response_model=RenderRecord)
def get_render(
    render_id: str,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
) -> RenderRecord:
    render = service.get_render(render_id)
    if not render:
        raise HTTPException(status_code=404, detail="Render not found")
    _ensure_project_access(project_id=render.project_id, request=request, service=service)
    return render
