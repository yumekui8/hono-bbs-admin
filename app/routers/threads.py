"""
スレッド管理ルーター: 一覧・編集・削除
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

@router.get("/{board_id}")
async def thread_list(request: Request, board_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    result = await client.get_threads(board_id, session["session_id"])
    return render(request, "threads/list.html", {
        "board": result["board"],
        "threads": result["threads"],
    })


# -------------------------------------------------------------------- 編集

@router.get("/{board_id}/{thread_id}/edit")
async def thread_edit_page(request: Request, board_id: str, thread_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    result = await client.get_posts(board_id, thread_id, session["session_id"])
    return render(request, "threads/edit.html", {
        "board_id": board_id,
        "thread": result["thread"],
    })


@router.post("/{board_id}/{thread_id}/edit")
async def thread_edit_post(
    request: Request,
    board_id: str,
    thread_id: str,
    title: str = Form(default=""),
    poster_name: str = Form(default=""),
):
    """タイトル・投稿者名を更新する (PUT: isEdited フラグが立つ)"""
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    data: dict = {}
    if title:
        data["title"] = title
    if poster_name:
        data["posterName"] = poster_name

    client = get_api_client()
    try:
        thread = await client.update_thread(
            board_id, thread_id, session["session_id"], session.get("turnstile_session_id"), data
        )
        flash(request, f"スレッド「{thread['title']}」を更新しました。", "success")
        return RedirectResponse(f"/boards/{board_id}", status_code=303)
    except APIError as e:
        flash(request, f"更新に失敗しました: {e.message}", "error")
        return RedirectResponse(f"/boards/{board_id}/{thread_id}/edit", status_code=303)


@router.post("/{board_id}/{thread_id}/settings")
async def thread_settings_post(
    request: Request,
    board_id: str,
    thread_id: str,
    administrators: str = Form(default=""),
    members: str = Form(default=""),
    permissions: str = Form(default=""),
    max_posts: int = Form(default=0),
    max_post_length: int = Form(default=0),
    max_post_lines: int = Form(default=0),
    id_format: str = Form(default=""),
):
    """スレッドの設定を更新する (PATCH: isEdited フラグは変化しない)"""
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    data: dict = {
        "administrators": administrators,
        "members": members,
        "maxPosts": max_posts,
        "maxPostLength": max_post_length,
        "maxPostLines": max_post_lines,
        "idFormat": id_format,
    }
    if permissions:
        data["permissions"] = permissions

    client = get_api_client()
    try:
        thread = await client.patch_thread(
            board_id, thread_id, session["session_id"], session.get("turnstile_session_id"), data
        )
        flash(request, f"スレッド「{thread['title']}」の設定を更新しました。", "success")
        return RedirectResponse(f"/boards/{board_id}", status_code=303)
    except APIError as e:
        flash(request, f"更新に失敗しました: {e.message}", "error")
        return RedirectResponse(f"/boards/{board_id}/{thread_id}/edit", status_code=303)


# -------------------------------------------------------------------- 削除

@router.post("/{board_id}/{thread_id}/delete")
async def thread_delete(request: Request, board_id: str, thread_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    try:
        await client.delete_thread(
            board_id, thread_id, session["session_id"], session.get("turnstile_session_id")
        )
        flash(request, "スレッドを削除しました。", "success")
    except APIError as e:
        flash(request, f"削除に失敗しました: {e.message}", "error")
    return RedirectResponse(f"/boards/{board_id}", status_code=303)
