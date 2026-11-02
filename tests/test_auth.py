from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from httpx import ConnectError
from supabase import AuthApiError

from back.auth import (
    AuthenticationError,
    authenticate_account,
    create_auth_client,
    get_account_session,
    validate_account_input,
)


class AuthTests(unittest.TestCase):
    def test_registration_validation(self):
        cases = [
            ("", "password", "password", "入力"),
            ("invalid", "password", "password", "メール"),
            ("a@example.com", "short", "short", "8文字"),
            ("a@example.com", "password", "different", "一致"),
        ]
        for email, password, confirmation, message in cases:
            with self.subTest(email=email, message=message):
                self.assertIn(message, validate_account_input(email, password, True, confirmation))
        self.assertIsNone(validate_account_input(" a@example.com ", "password", True, "password"))
        self.assertIsNone(validate_account_input("a@example.com", "short", False, ""))

    @patch("back.auth.dotenv_values", return_value={})
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_configuration_is_safe(self, _):
        with self.assertRaisesRegex(AuthenticationError, "back/.env"):
            create_auth_client()

    @patch("back.auth.create_client")
    @patch("back.auth.dotenv_values", return_value={
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_example",
        "SUPABASE_SECRET_KEY": "unused-secret",
    })
    @patch.dict("os.environ", {}, clear=True)
    def test_only_public_credentials_are_used(self, _, factory):
        create_auth_client()
        self.assertEqual(factory.call_args.args, (
            "https://example.supabase.co", "sb_publishable_example",
        ))
        self.assertTrue(factory.call_args.kwargs["options"].persist_session)
        self.assertFalse(factory.call_args.kwargs["options"].auto_refresh_token)

    @patch("back.auth.create_client")
    @patch("back.auth.dotenv_values", return_value={})
    @patch.dict("os.environ", {
        "SUPABASE_URL": "https://environment.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_env",
    }, clear=True)
    def test_environment_configuration(self, _, factory):
        create_auth_client()
        self.assertEqual(factory.call_args.args[0], "https://environment.supabase.co")

    def test_login_and_registration_preserve_password(self):
        for registering in (False, True):
            with self.subTest(registering=registering):
                client = Mock()
                response = SimpleNamespace(user=object(), session=object())
                method = client.auth.sign_up if registering else client.auth.sign_in_with_password
                method.return_value = response
                result = authenticate_account(client, " a@example.com ", " password ", registering)
                method.assert_called_once_with({"email": "a@example.com", "password": " password "})
                self.assertIs(result.session, response.session)
                other = client.auth.sign_in_with_password if registering else client.auth.sign_up
                other.assert_not_called()

    def test_registration_without_session_is_not_authenticated(self):
        client = Mock()
        client.auth.sign_up.return_value = SimpleNamespace(user=object(), session=None)
        result = authenticate_account(client, "a@example.com", "password", True)
        self.assertIsNone(result.session)
        self.assertIsNone(result.user)
        self.assertIn("確認メール", result.notice)

    def test_login_without_session_fails(self):
        client = Mock()
        client.auth.sign_in_with_password.return_value = SimpleNamespace(user=object(), session=None)
        with self.assertRaises(AuthenticationError):
            authenticate_account(client, "a@example.com", "password", False)

    def test_api_errors_are_translated_without_raw_details(self):
        for code, expected in (
            ("invalid_credentials", "正しくありません"),
            ("user_already_exists", "登録済み"),
            ("email_not_confirmed", "確認メール"),
            ("weak_password", "登録条件"),
            (None, "認証できません"),
        ):
            with self.subTest(code=code):
                client = Mock()
                client.auth.sign_in_with_password.side_effect = AuthApiError("private-detail", 400, code)
                with self.assertRaises(AuthenticationError) as caught:
                    authenticate_account(client, "a@example.com", "password", False)
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("private-detail", str(caught.exception))

    def test_network_failure_is_translated(self):
        client = Mock()
        client.auth.sign_up.side_effect = ConnectError("private-url")
        with self.assertRaisesRegex(AuthenticationError, "接続できません"):
            authenticate_account(client, "a@example.com", "password", True)

    def test_expired_session_is_translated(self):
        client = Mock()
        client.auth.get_session.side_effect = AuthApiError("private-token", 400, None)
        with self.assertRaisesRegex(AuthenticationError, "もう一度ログイン"):
            get_account_session(client)


if __name__ == "__main__":
    unittest.main()
