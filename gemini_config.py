"""Gemini and local-app settings for the documentation assistant MVP."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


def _is_true(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_key: str
    chat_model: str
    embedding_model: str
    app_host: str
    app_port: int
    auth_required: bool
    public_docs_only: bool


def get_settings(require_api_key: bool = True) -> Settings:
    """Read configuration after .env loading, without exposing the API key."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if require_api_key and (not api_key or api_key == "replace_with_your_gemini_api_key"):
        raise ValueError("Set GEMINI_API_KEY in .env or the process environment.")

    try:
        app_port = int(os.getenv("APP_PORT", "8000"))
    except ValueError as exc:
        raise ValueError("APP_PORT must be an integer.") from exc
    if not 1 <= app_port <= 65535:
        raise ValueError("APP_PORT must be between 1 and 65535.")

    auth_required = _is_true(os.getenv("APP_AUTH_REQUIRED", "false"))
    public_docs_only = _is_true(os.getenv("PUBLIC_DOCS_ONLY", "true"))
    if auth_required:
        raise ValueError("This MVP has no sign-in implementation; set APP_AUTH_REQUIRED=false.")
    if not public_docs_only:
        raise ValueError("This MVP may only index public documents; set PUBLIC_DOCS_ONLY=true.")

    return Settings(
        api_key=api_key,
        chat_model=os.getenv("GEMINI_CHAT_MODEL", "gemini-3.8-flash").strip(),
        embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip(),
        app_host=os.getenv("APP_HOST", "127.0.0.1").strip(),
        app_port=app_port,
        auth_required=auth_required,
        public_docs_only=public_docs_only,
    )
