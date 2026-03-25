"""
認証ルーター: ログイン・ログアウト
"""
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.api_client import APIAuthError, APIError
from app.config import get_settings
from app.dependencies import flash, get_api_client, get_session, render

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    if get_session(request):
        return RedirectResponse("/boards", status_code=303)
    settings = get_settings()
    return render(request, "login.html", {
        "enable_turnstile": settings.ENABLE_TURNSTILE,
    })


@router.post("/login")
async def login_post(
    request: Request,
    user_id: str = Form(...),
    password: str = Form(...),
    turnstile_session_id: str = Form(default=""),
):
    settings = get_settings()
    client = get_api_client()

    ts_id: str | None = turnstile_session_id.strip() or None
    if settings.ENABLE_TURNSTILE and not ts_id:
        flash(request, "TurnstileセッションIDを入力してください。", "error")
        return RedirectResponse("/login", status_code=303)

    try:
        session_data = await client.login(user_id, password, ts_id)
    except APIAuthError as e:
        if e.error_code == "TOO_MANY_ATTEMPTS":
            flash(request, "ログイン失敗が多すぎます。15分後に再試行してください。", "error")
        else:
            flash(request, "ユーザIDまたはパスワードが正しくありません。", "error")
        return RedirectResponse("/login", status_code=303)
    except APIError as e:
        flash(request, f"ログインエラー: {e.message}", "error")
        return RedirectResponse("/login", status_code=303)

    request.session["session_id"] = session_data["sessionId"]
    request.session["user_id"] = session_data["userId"]
    request.session["display_name"] = session_data.get("displayName", session_data["userId"])
    if ts_id:
        request.session["turnstile_session_id"] = ts_id

    logger.info("User logged in: %s", session_data["userId"])
    return RedirectResponse("/boards", status_code=303)


@router.post("/logout")
async def logout_post(request: Request):
    session = get_session(request)
    if session:
        client = get_api_client()
        await client.logout(session["session_id"])
    request.session.clear()
    logger.info("User logged out")
    return RedirectResponse("/login", status_code=303)
