"""
ロール管理ルーター: 一覧・作成・編集・削除・メンバー管理
"""
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.api_client import APIError
from app.dependencies import flash, get_api_client, get_session, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/roles")

SYSTEM_ROLES = {"admin-role", "user-admin-role", "general-role"}


def _require_login(request: Request):
    session = get_session(request)
    if session is None:
        return None, RedirectResponse("/login", status_code=303)
    return session, None


# -------------------------------------------------------------------- 一覧

@router.get("")
async def role_list(request: Request, page: int = 1):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    result = await client.get_roles(session["session_id"], page=page)
    return render(request, "roles/list.html", {
        "roles": result["data"],
        "page": result.get("page", page),
        "limit": result.get("limit", 0),
        "system_roles": SYSTEM_ROLES,
    })


# -------------------------------------------------------------------- 作成
# NOTE: /new は /{role_id} より前に登録する必要がある（パス競合防止）

@router.get("/new")
async def role_new_page(request: Request):
    session, redirect = _require_login(request)
    if redirect:
        return redirect
    return render(request, "roles/new.html")


@router.post("/new")
async def role_new_post(
    request: Request,
    name: str = Form(...),
):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    try:
        role = await client.create_role(session["session_id"], {"name": name})
        flash(request, f"ロール「{role['id']}」を作成しました。", "success")
        return RedirectResponse(f"/roles/{role['id']}", status_code=303)
    except APIError as e:
        flash(request, f"作成に失敗しました: {e.message}", "error")
        return RedirectResponse("/roles/new", status_code=303)


# -------------------------------------------------------------------- 詳細

@router.get("/{role_id}")
async def role_detail(request: Request, role_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    role = await client.get_role(role_id, session["session_id"])
    return render(request, "roles/detail.html", {
        "role": role,
        "is_system": role_id in SYSTEM_ROLES,
    })


# -------------------------------------------------------------------- 編集

@router.get("/{role_id}/edit")
async def role_edit_page(request: Request, role_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    if role_id in SYSTEM_ROLES:
        flash(request, "システムロールは編集できません。", "error")
        return RedirectResponse(f"/roles/{role_id}", status_code=303)

    client = get_api_client()
    role = await client.get_role(role_id, session["session_id"])
    return render(request, "roles/edit.html", {"role": role})


@router.post("/{role_id}/edit")
async def role_edit_post(
    request: Request,
    role_id: str,
    name: str = Form(...),
):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    try:
        role = await client.update_role(role_id, session["session_id"], {"name": name})
        flash(request, f"ロール「{role['id']}」を更新しました。", "success")
        return RedirectResponse(f"/roles/{role['id']}", status_code=303)
    except APIError as e:
        flash(request, f"更新に失敗しました: {e.message}", "error")
        return RedirectResponse(f"/roles/{role_id}/edit", status_code=303)


# -------------------------------------------------------------------- 削除

@router.post("/{role_id}/delete")
async def role_delete(request: Request, role_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    try:
        await client.delete_role(role_id, session["session_id"])
        flash(request, f"ロール「{role_id}」を削除しました。", "success")
        return RedirectResponse("/roles", status_code=303)
    except APIError as e:
        flash(request, f"削除に失敗しました: {e.message}", "error")
        return RedirectResponse(f"/roles/{role_id}", status_code=303)


# ---------------------------------------------------------------- メンバー追加

@router.post("/{role_id}/members/add")
async def role_member_add(
    request: Request,
    role_id: str,
    user_id: str = Form(...),
):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    try:
        await client.add_role_member(
            role_id,
            session["session_id"],
            session.get("turnstile_session_id"),
            user_id,
        )
        flash(request, f"ユーザー「{user_id}」をロールに追加しました。", "success")
    except APIError as e:
        flash(request, f"追加に失敗しました: {e.message}", "error")
    return RedirectResponse(f"/roles/{role_id}", status_code=303)


# ---------------------------------------------------------------- メンバー削除

@router.post("/{role_id}/members/{member_user_id}/remove")
async def role_member_remove(
    request: Request,
    role_id: str,
    member_user_id: str,
):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    try:
        await client.remove_role_member(
            role_id,
            member_user_id,
            session["session_id"],
            session.get("turnstile_session_id"),
        )
        flash(request, f"ユーザー「{member_user_id}」をロールから削除しました。", "success")
    except APIError as e:
        flash(request, f"削除に失敗しました: {e.message}", "error")
    return RedirectResponse(f"/roles/{role_id}", status_code=303)
