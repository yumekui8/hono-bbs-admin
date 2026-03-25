"""
BBS APIクライアント。httpxを使用してhono-bbs APIと通信する。
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{error_code}] {message}")


class APINetworkError(APIError):
    """ネットワークエラー・タイムアウト"""


class APIAuthError(APIError):
    """401 Unauthorized"""


class APIForbiddenError(APIError):
    """403 Forbidden"""


class APINotFoundError(APIError):
    """404 Not Found"""


from contextlib import asynccontextmanager


@asynccontextmanager
async def _http_client():
    """httpxクライアントを生成し、ネットワーク例外をAPINetworkErrorに変換する"""
    async with httpx.AsyncClient() as client:
        try:
            yield client
        except httpx.TimeoutException as e:
            logger.error("API request timed out: %s", e)
            raise APINetworkError(0, "TIMEOUT", f"APIリクエストがタイムアウトしました: {e}") from e
        except httpx.NetworkError as e:
            logger.error("API network error: %s", e)
            raise APINetworkError(0, "NETWORK_ERROR", f"APIへの接続に失敗しました: {e}") from e


def _raise_for_response(resp: httpx.Response) -> None:
    """エラーレスポンスを例外に変換する"""
    if resp.is_success:
        return
    try:
        body = resp.json()
        error_code = body.get("error", "UNKNOWN_ERROR")
        message = body.get("message", resp.text)
    except Exception:
        error_code = "UNKNOWN_ERROR"
        message = resp.text

    logger.warning("API error %s: [%s] %s", resp.status_code, error_code, message)

    if resp.status_code in (401, 429):
        raise APIAuthError(resp.status_code, error_code, message)
    if resp.status_code == 403:
        raise APIForbiddenError(resp.status_code, error_code, message)
    if resp.status_code == 404:
        raise APINotFoundError(resp.status_code, error_code, message)
    raise APIError(resp.status_code, error_code, message)


def _build_headers(
    session_id: str | None = None,
    turnstile_session_id: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if session_id:
        headers["X-Session-Id"] = session_id
    if turnstile_session_id:
        headers["X-Turnstile-Session"] = turnstile_session_id
    return headers


class BBSApiClient:
    def __init__(self, base_url: str, base_path: str):
        self._base_url = base_url.rstrip("/")
        self._base_path = base_path

    def _url(self, path: str) -> str:
        return f"{self._base_url}{self._base_path}{path}"

    # ------------------------------------------------------------------ 認証

    async def login(
        self,
        user_id: str,
        password: str,
        turnstile_session_id: str | None = None,
    ) -> dict[str, Any]:
        """ログインしてBBSセッション情報を返す"""
        logger.info("Login attempt for user: %s", user_id)
        async with _http_client() as client:
            resp = await client.post(
                self._url("/auth/login"),
                json={"id": user_id, "password": password},
                headers=_build_headers(turnstile_session_id=turnstile_session_id),
                timeout=10.0,
            )
            _raise_for_response(resp)
            logger.info("Login successful for user: %s", user_id)
            return resp.json()["data"]

    async def logout(self, session_id: str) -> None:
        """ログアウトしてセッションを無効化する"""
        logger.info("Logout session: %s", session_id[:8] + "...")
        async with _http_client() as client:
            resp = await client.post(
                self._url("/auth/logout"),
                headers=_build_headers(session_id=session_id),
                timeout=10.0,
            )
            # ログアウトは失敗してもエラーにしない
            if not resp.is_success:
                logger.warning("Logout returned %s", resp.status_code)

    # ------------------------------------------------------------------ 板

    async def get_boards(self, session_id: str) -> list[dict]:
        """板一覧を取得する"""
        logger.debug("GET /boards")
        async with _http_client() as client:
            resp = await client.get(
                self._url("/boards"),
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def create_board(
        self,
        session_id: str,
        turnstile_session_id: str | None,
        data: dict,
    ) -> dict:
        """板を作成する"""
        logger.info("POST /boards name=%s", data.get("name"))
        async with _http_client() as client:
            resp = await client.post(
                self._url("/boards"),
                json=data,
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def update_board(
        self,
        board_id: str,
        session_id: str,
        turnstile_session_id: str | None,
        data: dict,
    ) -> dict:
        """板の表示情報を更新する (PUT: name/description/category のみ)"""
        logger.info("PUT /boards/%s", board_id)
        async with _http_client() as client:
            resp = await client.put(
                self._url(f"/boards/{board_id}"),
                json=data,
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def patch_board(
        self,
        board_id: str,
        session_id: str,
        turnstile_session_id: str | None,
        data: dict,
    ) -> dict:
        """板の全フィールドを更新する (PATCH: upsert)"""
        logger.info("PATCH /boards/%s", board_id)
        async with _http_client() as client:
            resp = await client.patch(
                self._url(f"/boards/{board_id}"),
                json=data,
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def delete_board(
        self,
        board_id: str,
        session_id: str,
        turnstile_session_id: str | None,
    ) -> None:
        """板を削除する（スレッド・投稿もCASCADE削除）"""
        logger.info("DELETE /boards/%s", board_id)
        async with _http_client() as client:
            resp = await client.delete(
                self._url(f"/boards/{board_id}"),
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)

    # --------------------------------------------------------------- スレッド

    async def get_threads(self, board_id: str, session_id: str) -> dict:
        """板のメタ情報とスレッド一覧を取得する"""
        logger.debug("GET /boards/%s", board_id)
        async with _http_client() as client:
            resp = await client.get(
                self._url(f"/boards/{board_id}"),
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]  # { board, threads }

    async def update_thread(
        self,
        board_id: str,
        thread_id: str,
        session_id: str,
        turnstile_session_id: str | None,
        data: dict,
    ) -> dict:
        """スレッドのタイトル・投稿者名を更新する (PUT: title/posterName のみ)"""
        logger.info("PUT /boards/%s/%s", board_id, thread_id)
        async with _http_client() as client:
            resp = await client.put(
                self._url(f"/boards/{board_id}/{thread_id}"),
                json=data,
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def patch_thread(
        self,
        board_id: str,
        thread_id: str,
        session_id: str,
        turnstile_session_id: str | None,
        data: dict,
    ) -> dict:
        """スレッドの設定を更新する (PATCH: maxPosts/idFormat/permissions 等)"""
        logger.info("PATCH /boards/%s/%s", board_id, thread_id)
        async with _http_client() as client:
            resp = await client.patch(
                self._url(f"/boards/{board_id}/{thread_id}"),
                json=data,
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def delete_thread(
        self,
        board_id: str,
        thread_id: str,
        session_id: str,
        turnstile_session_id: str | None,
    ) -> None:
        """スレッドを削除する（投稿もCASCADE削除）"""
        logger.info("DELETE /boards/%s/%s", board_id, thread_id)
        async with _http_client() as client:
            resp = await client.delete(
                self._url(f"/boards/{board_id}/{thread_id}"),
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)

    # ------------------------------------------------------------------ 投稿

    async def get_posts(self, board_id: str, thread_id: str, session_id: str) -> dict:
        """スレッドの詳細と投稿一覧を取得する"""
        logger.debug("GET /boards/%s/%s", board_id, thread_id)
        async with _http_client() as client:
            resp = await client.get(
                self._url(f"/boards/{board_id}/{thread_id}"),
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]  # { thread, posts }

    async def get_post(
        self,
        board_id: str,
        thread_id: str,
        post_number: int,
        session_id: str,
    ) -> dict:
        """レス番号で単一の投稿を取得する"""
        logger.debug("GET /boards/%s/%s/%s", board_id, thread_id, post_number)
        async with _http_client() as client:
            resp = await client.get(
                self._url(f"/boards/{board_id}/{thread_id}/{post_number}"),
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def update_post(
        self,
        board_id: str,
        thread_id: str,
        post_number: int,
        data: dict,
        session_id: str,
        turnstile_session_id: str | None,
    ) -> dict:
        """投稿の内容を更新する (PUT: content/posterName/posterOptionInfo, isEdited フラグが立つ)"""
        logger.info("PUT /boards/%s/%s/%s", board_id, thread_id, post_number)
        async with _http_client() as client:
            resp = await client.put(
                self._url(f"/boards/{board_id}/{thread_id}/{post_number}"),
                json=data,
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def patch_post(
        self,
        board_id: str,
        thread_id: str,
        post_number: int,
        session_id: str,
        turnstile_session_id: str | None,
        data: dict,
    ) -> dict:
        """投稿の権限設定を更新する (PATCH: isEditedフラグは変化しない)"""
        logger.info("PATCH /boards/%s/%s/%s (update permissions)", board_id, thread_id, post_number)
        async with _http_client() as client:
            resp = await client.patch(
                self._url(f"/boards/{board_id}/{thread_id}/{post_number}"),
                json=data,
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def soft_delete_post(
        self,
        board_id: str,
        thread_id: str,
        post_number: int,
        session_id: str,
        turnstile_session_id: str | None,
    ) -> dict:
        """投稿をソフトデリートする (DELETE → isDeletedフラグ)"""
        logger.info("DELETE /boards/%s/%s/%s (soft delete)", board_id, thread_id, post_number)
        async with _http_client() as client:
            resp = await client.delete(
                self._url(f"/boards/{board_id}/{thread_id}/{post_number}"),
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    # --------------------------------------------------------------- ユーザー

    async def get_users(
        self,
        session_id: str,
        page: int = 1,
        limit: int = 50,
    ) -> dict:
        """ユーザー一覧を取得する (ページネーション対応)"""
        logger.debug("GET /identity/users page=%s", page)
        async with _http_client() as client:
            resp = await client.get(
                self._url("/identity/users"),
                params={"page": page, "limit": limit},
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def get_user(self, user_id: str, session_id: str) -> dict:
        """ユーザー情報を取得する"""
        logger.debug("GET /identity/users/%s", user_id)
        async with _http_client() as client:
            resp = await client.get(
                self._url(f"/identity/users/{user_id}"),
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def update_user(
        self,
        user_id: str,
        session_id: str,
        turnstile_session_id: str | None,
        data: dict,
    ) -> dict:
        """ユーザー情報を更新する (id は変更不可、isActive もここで変更可能)"""
        logger.info("PUT /identity/users/%s", user_id)
        async with _http_client() as client:
            resp = await client.put(
                self._url(f"/identity/users/{user_id}"),
                json=data,
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def delete_user(
        self,
        user_id: str,
        session_id: str,
        turnstile_session_id: str | None,
    ) -> None:
        """ユーザーを削除する (投稿は残りuserIdがnullになる)"""
        logger.info("DELETE /identity/users/%s", user_id)
        async with _http_client() as client:
            resp = await client.delete(
                self._url(f"/identity/users/{user_id}"),
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)

    # --------------------------------------------------------------- ロール

    async def get_roles(
        self,
        session_id: str,
        page: int = 1,
        limit: int = 50,
    ) -> dict:
        """ロール一覧を取得する (ページネーション対応)"""
        logger.debug("GET /identity/roles page=%s", page)
        async with _http_client() as client:
            resp = await client.get(
                self._url("/identity/roles"),
                params={"page": page, "limit": limit},
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def get_role(self, role_id: str, session_id: str) -> dict:
        """ロール情報を取得する"""
        logger.debug("GET /identity/roles/%s", role_id)
        async with _http_client() as client:
            resp = await client.get(
                self._url(f"/identity/roles/{role_id}"),
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def create_role(self, session_id: str, data: dict) -> dict:
        """ロールを作成する"""
        logger.info("POST /identity/roles name=%s", data.get("name"))
        async with _http_client() as client:
            resp = await client.post(
                self._url("/identity/roles"),
                json=data,
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def update_role(self, role_id: str, session_id: str, data: dict) -> dict:
        """ロール名を更新する (システムロールは変更不可)"""
        logger.info("PUT /identity/roles/%s", role_id)
        async with _http_client() as client:
            resp = await client.put(
                self._url(f"/identity/roles/{role_id}"),
                json=data,
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
            return resp.json()["data"]

    async def delete_role(self, role_id: str, session_id: str) -> None:
        """ロールを削除する (システムロールは削除不可)"""
        logger.info("DELETE /identity/roles/%s", role_id)
        async with _http_client() as client:
            resp = await client.delete(
                self._url(f"/identity/roles/{role_id}"),
                headers=_build_headers(session_id=session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)

    async def add_role_member(
        self,
        role_id: str,
        session_id: str,
        turnstile_session_id: str | None,
        user_id: str,
    ) -> None:
        """ロールにメンバーを追加する (204 No Content)"""
        logger.info("POST /identity/roles/%s/members userId=%s", role_id, user_id)
        async with _http_client() as client:
            resp = await client.post(
                self._url(f"/identity/roles/{role_id}/members"),
                json={"userId": user_id},
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)

    async def remove_role_member(
        self,
        role_id: str,
        member_user_id: str,
        session_id: str,
        turnstile_session_id: str | None,
    ) -> None:
        """ロールからメンバーを削除する"""
        logger.info("DELETE /identity/roles/%s/members/%s", role_id, member_user_id)
        async with _http_client() as client:
            resp = await client.delete(
                self._url(f"/identity/roles/{role_id}/members/{member_user_id}"),
                headers=_build_headers(session_id=session_id, turnstile_session_id=turnstile_session_id),
                timeout=15.0,
            )
            _raise_for_response(resp)
