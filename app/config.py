from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # BBS API接続
    BBS_API_BASE_URL: str = "http://localhost:8787"
    BBS_API_BASE_PATH: str = "/api/v1"

    # Cloudflare Turnstile (BBS側でENABLE_TURNSTILE=trueの場合)
    # trueにするとログイン画面にTurnstileセッションID入力欄を表示する
    ENABLE_TURNSTILE: bool = False

    # アプリ設定
    SECRET_KEY: str = "changeme-in-production"
    LOG_LEVEL: str = "INFO"
    # Trueにするとセッションクッキーを HTTPS のみで送信する（本番環境では True 推奨）
    SESSION_HTTPS_ONLY: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
