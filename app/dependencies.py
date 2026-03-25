"""
FastAPI依存性・共通ユーティリティ
"""
from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.api_client import BBSApiClient
from app.config import get_settings

templates = Jinja2Templates(directory="app/templates", autoescape=True)


def get_api_client() -> BBSApiClient:
    settings = get_settings()
    return BBSApiClient(settings.BBS_API_BASE_URL, settings.BBS_API_BASE_PATH)


def get_session(request: Request) -> dict | None:
    """セッション情報を返す。未ログインの場合はNone。"""
    session_id = request.session.get("session_id")
    if not session_id:
        return None
    return {
        "session_id": session_id,
        "turnstile_session_id": request.session.get("turnstile_session_id"),
        "user_id": request.session.get("user_id"),
        "display_name": request.session.get("display_name"),
    }


def flash(request: Request, text: str, level: str = "info") -> None:
    """フラッシュメッセージをセッションに追加する"""
    messages = request.session.get("flash_messages", [])
    messages.append({"text": text, "level": level})
    request.session["flash_messages"] = messages


def get_flash_messages(request: Request) -> list:
    """フラッシュメッセージを取得してセッションから削除する"""
    messages = request.session.pop("flash_messages", [])
    return messages


def render(
    request: Request,
    template_name: str,
    context: dict | None = None,
    status_code: int = 200,
):
    """テンプレートを共通コンテキスト付きでレンダリングする"""
    session = get_session(request)
    ctx = {
        "request": request,
        "user_id": session["user_id"] if session else None,
        "display_name": session["display_name"] if session else None,
        "messages": get_flash_messages(request),
    }
    if context:
        ctx.update(context)
    return templates.TemplateResponse(template_name, ctx, status_code=status_code)
