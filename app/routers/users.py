"""
ユーザー管理ルーター: 一覧・詳細・編集・削除
"""
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.api_client import APIError
from app.dependencies import flash, get_api_client, get_session, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users")


def _require_login(request: Request):
    session = get_session(request)
    if session is None:
        return None, RedirectResponse("/login", status_code=303)
    return session, None


# -------------------------------------------------------------------- 一覧

@router.get("")
async def user_list(request: Request, page: int = 1):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    result = await client.get_users(session["session_id"], page=page)
    return render(request, "users/list.html", {
        "users": result["data"],
        "page": result.get("page", page),
        "limit": result.get("limit", 0),
    })


# -------------------------------------------------------------------- 詳細

@router.get("/{user_id}")
async def user_detail(request: Request, user_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    user = await client.get_user(user_id, session["session_id"])
    return render(request, "users/detail.html", {"user": user})


# -------------------------------------------------------------------- 編集

@router.get("/{user_id}/edit")
async def user_edit_page(request: Request, user_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    user = await client.get_user(user_id, session["session_id"])
    return render(request, "users/edit.html", {"user": user})


@router.post("/{user_id}/edit")
async def user_edit_post(
    request: Request,
    user_id: str,
    display_name: str = Form(default=""),
    bio: str = Form(default=""),
    email: str = Form(default=""),
    is_active: str = Form(default=""),
):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    data: dict = {}
    if display_name:
        data["displayName"] = display_name
    data["bio"] = bio or None
    data["email"] = email or None
    if is_active != "":
        data["isActive"] = is_active == "true"

    client = get_api_client()
    try:
        user = await client.update_user(
            user_id,
            session["session_id"],
            session.get("turnstile_session_id"),
            data,
        )
        flash(request, f"ユーザー「{user['id']}」を更新しました。", "success")
        return RedirectResponse(f"/users/{user_id}", status_code=303)
    except APIError as e:
        flash(request, f"更新に失敗しました: {e.message}", "error")
        return RedirectResponse(f"/users/{user_id}/edit", status_code=303)


# -------------------------------------------------------------------- 削除

@router.post("/{user_id}/delete")
async def user_delete(request: Request, user_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    try:
        await client.delete_user(
            user_id,
            session["session_id"],
            session.get("turnstile_session_id"),
        )
        flash(request, f"ユーザー「{user_id}」を削除しました。", "success")
        return RedirectResponse("/users", status_code=303)
    except APIError as e:
        flash(request, f"削除に失敗しました: {e.message}", "error")
        return RedirectResponse(f"/users/{user_id}", status_code=303)
