from dataclasses import dataclass
import os
from pathlib import Path
import re
from urllib.parse import urlparse

from dotenv import dotenv_values
from httpx import HTTPError
from supabase import AuthApiError, AuthError, AuthRetryableError, Client, ClientOptions, create_client
from supabase_auth import Session, User


ENV_PATH = Path(__file__).resolve().parent / ".env"


class AuthenticationError(RuntimeError):
    """An authentication failure safe to display to the user."""


@dataclass(frozen=True)
class AccountResult:
    user: User | None
    session: Session | None
    notice: str | None = None


def create_auth_client() -> Client:
    # Read only the settings needed by Auth. Never load the admin credentials.
    settings = dotenv_values(ENV_PATH, encoding="utf-8-sig", interpolate=False)
    url = (os.getenv("SUPABASE_URL") or settings.get("SUPABASE_URL") or "").strip()
    key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or settings.get("SUPABASE_PUBLISHABLE_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise AuthenticationError(
            "back/.env に SUPABASE_URL と SUPABASE_PUBLISHABLE_KEY を設定してください。"
        )
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise AuthenticationError("SUPABASE_URL に正しい https のプロジェクトURLを設定してください。")
    if not key.startswith("sb_publishable_"):
        raise AuthenticationError("SUPABASE_PUBLISHABLE_KEY に Publishable key を設定してください。")
    try:
        # Refresh on get_session(), avoiding background timers after a browser disconnects.
        return create_client(url, key, options=ClientOptions(auto_refresh_token=False, persist_session=True))
    except Exception:
        # SDK errors may contain configuration values; do not expose them.
        raise AuthenticationError("認証の接続設定を確認してください。") from None


def _auth_error_message(error: AuthError) -> str:
    if isinstance(error, AuthRetryableError):
        return "認証サーバーに接続できませんでした。時間をおいて試してください。"
    code = getattr(error, "code", None)
    messages = {
        "invalid_credentials": "メールアドレスまたはパスワードが正しくありません。",
        "email_not_confirmed": "確認メールのリンクを開いてからログインしてください。",
        "user_already_exists": "このメールアドレスは登録済みです。ログインしてください。",
        "email_exists": "このメールアドレスは登録済みです。ログインしてください。",
        "weak_password": "パスワードが登録条件を満たしていません。より強いパスワードを入力してください。",
        "signup_disabled": "現在、新規登録は停止されています。",
        "email_provider_disabled": "メールアドレスによる認証が無効になっています。",
        "email_address_invalid": "正しいメールアドレスを入力してください。",
        "over_email_send_rate_limit": "メール送信の上限に達しました。時間をおいて試してください。",
        "over_request_rate_limit": "試行回数が多すぎます。時間をおいて試してください。",
    }
    if code in messages:
        return messages[code]
    if isinstance(error, AuthApiError) and str(error.status) == "429":
        return "試行回数が多すぎます。時間をおいて試してください。"
    return "認証できませんでした。入力内容と接続状況を確認して、もう一度試してください。"


def authenticate_account(
    client: Client, email: str, password: str, is_registering: bool
) -> AccountResult:
    credentials = {"email": email.strip(), "password": password}
    try:
        response = (
            client.auth.sign_up(credentials)
            if is_registering
            else client.auth.sign_in_with_password(credentials)
        )
    except AuthError as error:
        raise AuthenticationError(_auth_error_message(error)) from None
    except (HTTPError, OSError):
        raise AuthenticationError("認証サーバーに接続できませんでした。時間をおいて試してください。") from None

    if response.user and response.session:
        return AccountResult(response.user, response.session)
    if is_registering and response.user:
        # Supabase may return a masked user for an existing account.
        return AccountResult(
            None, None,
            "確認メールが届いている場合はリンクを開いてからログインしてください。"
            "登録済みの場合は、そのままログインしてください。",
        )
    raise AuthenticationError("認証を完了できませんでした。もう一度試してください。")


def get_account_session(client: Client) -> Session | None:
    try:
        return client.auth.get_session()
    except AuthRetryableError:
        raise AuthenticationError("ログイン状態を確認できませんでした。時間をおいて再度お試しください。") from None
    except AuthError:
        raise AuthenticationError("ログインの有効期限が切れました。もう一度ログインしてください。") from None
    except (HTTPError, OSError):
        raise AuthenticationError("ログイン状態を確認できませんでした。時間をおいて再度お試しください。") from None


def validate_account_input(
    email: str,
    password: str,
    is_registering: bool,
    confirm_password: str,
) -> str | None:
    if not email.strip() or not password:
        return "メールアドレスとパスワードを入力してください。"
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
        return "正しいメールアドレスを入力してください。"
    if is_registering and len(password) < 8:
        return "パスワードは8文字以上で入力してください。"
    if is_registering and password != confirm_password:
        return "確認用パスワードが一致しません。"
    return None
