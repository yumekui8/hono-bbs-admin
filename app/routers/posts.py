"""
投稿管理ルーター: 一覧・詳細表示・内容編集・ソフトデリート
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

@router.get("/{board_id}/{thread_id}")
async def post_list(request: Request, board_id: str, thread_id: str):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    result = await client.get_posts(board_id, thread_id, session["session_id"])
    return render(request, "posts/list.html", {
        "board_id": board_id,
        "thread": result["thread"],
        "posts": result["posts"],
    })


# ----------------------------------------------------------------- 詳細表示

@router.get("/{board_id}/{thread_id}/{post_number}")
async def post_detail(request: Request, board_id: str, thread_id: str, post_number: int):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    post = await client.get_post(board_id, thread_id, post_number, session["session_id"])
    return render(request, "posts/detail.html", {
        "board_id": board_id,
        "thread_id": thread_id,
        "post": post,
    })


# -------------------------------------------------------------- 内容編集

@router.get("/{board_id}/{thread_id}/{post_number}/edit")
async def post_edit_page(request: Request, board_id: str, thread_id: str, post_number: int):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    post = await client.get_post(board_id, thread_id, post_number, session["session_id"])
    return render(request, "posts/edit.html", {
        "board_id": board_id,
        "thread_id": thread_id,
        "post": post,
    })


@router.post("/{board_id}/{thread_id}/{post_number}/edit")
async def post_edit_post(
    request: Request,
    board_id: str,
    thread_id: str,
    post_number: int,
    content: str = Form(...),
    poster_name: str = Form(default=""),
    poster_option_info: str = Form(default=""),
):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    data: dict = {"content": content}
    if poster_name:
        data["posterName"] = poster_name
    data["posterOptionInfo"] = poster_option_info

    client = get_api_client()
    try:
        await client.update_post(
            board_id, thread_id, post_number, data,
            session["session_id"], session.get("turnstile_session_id"),
        )
        flash(request, f"レス{post_number}の内容を更新しました。", "success")
        return RedirectResponse(f"/boards/{board_id}/{thread_id}", status_code=303)
    except APIError as e:
        flash(request, f"更新に失敗しました: {e.message}", "error")
        return RedirectResponse(f"/boards/{board_id}/{thread_id}/{post_number}/edit", status_code=303)


# --------------------------------------------------------------- ソフトデリート

@router.post("/{board_id}/{thread_id}/{post_number}/delete")
async def post_soft_delete(
    request: Request,
    board_id: str,
    thread_id: str,
    post_number: int,
):
    session, redirect = _require_login(request)
    if redirect:
        return redirect

    client = get_api_client()
    try:
        await client.soft_delete_post(
            board_id, thread_id, post_number,
            session["session_id"], session.get("turnstile_session_id"),
        )
        flash(request, f"レス{post_number}を削除しました。", "success")
    except APIError as e:
        flash(request, f"削除に失敗しました: {e.message}", "error")
    return RedirectResponse(f"/boards/{board_id}/{thread_id}", status_code=303)
