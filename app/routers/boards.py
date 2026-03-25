"""
板管理ルーター: 一覧・作成・編集・削除
"""
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.api_client import APIError
from app.dependencies import flash, get_api_client, get_session, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/boards")


def _require_login(request: Request):
    session = get_session(request)
    if session is None:
        return None, RedirectResponse("/login", status_code=303)
    return session, None


# -------------------------------------------------------------------- 一覧

@router.get("")
async def board_list(request: Request):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    boards = await client.get_boards(session["session_id"])
    return render(request, "boards/list.html", {"boards": boards})


# ------------------------------------------------------------------- 作成

@router.get("/new")
async def board_new_page(request: Request):
    session, redirect = _require_login(request)
    if redirect:
        return redirect
    return render(request, "boards/new.html")


@router.post("/new")
async def board_new_post(
    request: Request,
    board_id: str = Form(default=""),
    name: str = Form(...),
    description: str = Form(default=""),
    administrators: str = Form(default="$CREATOR"),
    members: str = Form(default=""),
    permissions: str = Form(default="31,28,24,16"),
    max_threads: int = Form(default=1000),
    max_thread_title_length: int = Form(default=200),
    default_poster_name: str = Form(default="名無しさん"),
    default_id_format: str = Form(default="daily_hash"),
    default_max_posts: int = Form(default=1000),
    default_max_post_length: int = Form(default=2000),
    default_max_post_lines: int = Form(default=100),
    default_max_poster_name_length: int = Form(default=50),
    default_max_poster_option_length: int = Form(default=100),
    default_thread_administrators: str = Form(default="$CREATOR"),
    default_thread_members: str = Form(default=""),
    default_thread_permissions: str = Form(default="31,28,24,16"),
    default_post_administrators: str = Form(default="$CREATOR"),
    default_post_members: str = Form(default=""),
    default_post_permissions: str = Form(default="31,28,24,16"),
    category: str = Form(default=""),
):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    data: dict = {
        "name": name,
        "description": description or None,
        "administrators": administrators,
        "members": members,
        "permissions": permissions,
        "maxThreads": max_threads,
        "maxThreadTitleLength": max_thread_title_length,
        "defaultPosterName": default_poster_name,
        "defaultIdFormat": default_id_format,
        "defaultMaxPosts": default_max_posts,
        "defaultMaxPostLength": default_max_post_length,
        "defaultMaxPostLines": default_max_post_lines,
        "defaultMaxPosterNameLength": default_max_poster_name_length,
        "defaultMaxPosterOptionLength": default_max_poster_option_length,
        "defaultThreadAdministrators": default_thread_administrators,
        "defaultThreadMembers": default_thread_members,
        "defaultThreadPermissions": default_thread_permissions,
        "defaultPostAdministrators": default_post_administrators,
        "defaultPostMembers": default_post_members,
        "defaultPostPermissions": default_post_permissions,
        "category": category or None,
    }
    if board_id:
        data["id"] = board_id

    client = get_api_client()
    try:
        board = await client.create_board(
            session["session_id"], session.get("turnstile_session_id"), data
        )
        flash(request, f"板「{board['name']}」を作成しました。", "success")
        return RedirectResponse("/boards", status_code=303)
    except APIError as e:
        flash(request, f"作成に失敗しました: {e.message}", "error")
        return RedirectResponse("/boards/new", status_code=303)


# -------------------------------------------------------------------- 編集

@router.get("/{board_id}/edit")
async def board_edit_page(request: Request, board_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    # 板情報はスレッド一覧取得APIから取得する
    result = await client.get_threads(board_id, session["session_id"])
    board = result["board"]
    return render(request, "boards/edit.html", {"board": board})


@router.post("/{board_id}/edit")
async def board_edit_post(
    request: Request,
    board_id: str,
    name: str = Form(...),
    description: str = Form(default=""),
    category: str = Form(default=""),
    administrators: str = Form(default=""),
    members: str = Form(default=""),
    permissions: str = Form(default=""),
    max_threads: int = Form(default=1000),
    max_thread_title_length: int = Form(default=200),
    default_poster_name: str = Form(default="名無しさん"),
    default_id_format: str = Form(default="daily_hash"),
    default_max_posts: int = Form(default=1000),
    default_max_post_length: int = Form(default=2000),
    default_max_post_lines: int = Form(default=100),
    default_thread_administrators: str = Form(default="$CREATOR"),
    default_thread_members: str = Form(default=""),
    default_thread_permissions: str = Form(default="31,28,24,16"),
    default_post_administrators: str = Form(default="$CREATOR"),
    default_post_members: str = Form(default=""),
    default_post_permissions: str = Form(default="31,28,24,16"),
):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    # PATCH: 全フィールド更新（upsert）
    data: dict = {
        "name": name,
        "description": description or None,
        "category": category or None,
        "administrators": administrators,
        "members": members,
        "maxThreads": max_threads,
        "maxThreadTitleLength": max_thread_title_length,
        "defaultPosterName": default_poster_name,
        "defaultIdFormat": default_id_format,
        "defaultMaxPosts": default_max_posts,
        "defaultMaxPostLength": default_max_post_length,
        "defaultMaxPostLines": default_max_post_lines,
        "defaultThreadAdministrators": default_thread_administrators,
        "defaultThreadMembers": default_thread_members,
        "defaultThreadPermissions": default_thread_permissions,
        "defaultPostAdministrators": default_post_administrators,
        "defaultPostMembers": default_post_members,
        "defaultPostPermissions": default_post_permissions,
    }
    if permissions:
        data["permissions"] = permissions

    client = get_api_client()
    try:
        board = await client.patch_board(
            board_id, session["session_id"], session.get("turnstile_session_id"), data
        )
        flash(request, f"板「{board['name']}」を更新しました。", "success")
        return RedirectResponse("/boards", status_code=303)
    except APIError as e:
        flash(request, f"更新に失敗しました: {e.message}", "error")
        return RedirectResponse(f"/boards/{board_id}/edit", status_code=303)


# -------------------------------------------------------------------- 削除

@router.post("/{board_id}/delete")
async def board_delete(request: Request, board_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    try:
        await client.delete_board(
            board_id, session["session_id"], session.get("turnstile_session_id")
        )
        flash(request, f"板「{board_id}」を削除しました。", "success")
    except APIError as e:
        flash(request, f"削除に失敗しました: {e.message}", "error")
    return RedirectResponse("/boards", status_code=303)
