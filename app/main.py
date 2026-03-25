"""
BBS管理者UI - FastAPIアプリケーションエントリポイント
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api_client import APIAuthError, APIError, APIForbiddenError, APINetworkError, APINotFoundError
from app.config import get_settings
from app.dependencies import flash, render
from app.routers import auth, boards, posts, roles, threads, users

settings = get_settings()

# ロギング設定
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="BBS管理者UI", docs_url=None, redoc_url=None)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",       # クロスサイトPOSTでクッキーを送信しない（CSRF緩和）
    https_only=settings.SESSION_HTTPS_ONLY,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(boards.router)
app.include_router(threads.router)
app.include_router(posts.router)
app.include_router(users.router)
app.include_router(roles.router)


@app.exception_handler(APIAuthError)
async def handle_auth_error(request: Request, exc: APIAuthError):
    logger.warning("Auth error: %s", exc)
    flash(request, "セッションが切れました。再度ログインしてください。", "error")
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(APIForbiddenError)
async def handle_forbidden_error(request: Request, exc: APIForbiddenError):
    logger.warning("Forbidden: %s", exc)
    return render(request, "error.html", {"error_title": "権限エラー", "error_message": str(exc.message)}, status_code=403)


@app.exception_handler(APINotFoundError)
async def handle_not_found_error(request: Request, exc: APINotFoundError):
    logger.warning("Not found: %s", exc)
    return render(request, "error.html", {"error_title": "見つかりません", "error_message": str(exc.message)}, status_code=404)


@app.exception_handler(APINetworkError)
async def handle_network_error(request: Request, exc: APINetworkError):
    logger.error("Network error: %s", exc)
    return render(request, "error.html", {"error_title": "接続エラー", "error_message": str(exc.message)}, status_code=502)


@app.exception_handler(APIError)
async def handle_api_error(request: Request, exc: APIError):
    logger.error("API error: %s", exc)
    return render(request, "error.html", {"error_title": "APIエラー", "error_message": str(exc.message)}, status_code=500)


@app.get("/")
async def root():
    return RedirectResponse("/boards", status_code=303)
