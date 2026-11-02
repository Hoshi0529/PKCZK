from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest
from supabase import AuthApiError

from back.auth import AuthenticationError


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.auth.get_session.return_value = None
        self.factory = patch("front.login.create_auth_client", return_value=self.client).start()
        patch("front.login.get_pokemon_artwork", return_value=({}, [])).start()
        self.addCleanup(patch.stopall)

    def app(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "Login.py"), default_timeout=15).run()
        self.assertFalse(app.exception)
        return app

    def fill(self, app, password="password"):
        app.text_input(key="account_email").input("a@example.com")
        app.text_input(key="account_password").input(password)

    def successful_response(self):
        user = SimpleNamespace(email="a@example.com")
        session = SimpleNamespace(user=user)

        def signed_in(_):
            self.client.auth.get_session.return_value = session
            return SimpleNamespace(user=user, session=session)

        return signed_in

    def test_login_success_and_rerun(self):
        self.client.auth.sign_in_with_password.side_effect = self.successful_response()
        app = self.app()
        self.fill(app)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.success)
        self.assertEqual(app.text[0].value, "a@example.com")
        self.assertEqual(len(app.text_input), 0)
        self.assertNotIn("account_password", app.session_state)
        app.run()
        self.assertTrue(app.success)
        self.client.auth.sign_in_with_password.assert_called_once()

    def test_registration_success(self):
        self.client.auth.sign_up.side_effect = self.successful_response()
        app = self.app()
        app.button_group[0].set_value("新規登録").run()
        self.fill(app)
        app.text_input(key="account_confirm_password").input("password")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIn("新規登録が完了", app.success[0].value)

    def test_invalid_input_does_not_call_api(self):
        app = self.app()
        app.button[0].click().run()
        self.assertTrue(app.error)
        self.client.auth.sign_in_with_password.assert_not_called()

    def test_invalid_credentials_remain_on_form(self):
        self.client.auth.sign_in_with_password.side_effect = AuthApiError("raw", 400, "invalid_credentials")
        app = self.app()
        self.fill(app)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertFalse(app.success)
        self.assertEqual(len(app.text_input), 2)

    def test_confirmation_required_does_not_show_success(self):
        self.client.auth.sign_up.return_value = SimpleNamespace(user=object(), session=None)
        app = self.app()
        app.button_group[0].set_value("新規登録").run()
        self.fill(app)
        app.text_input(key="account_confirm_password").input("password")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        self.assertFalse(app.success)

    def test_missing_settings(self):
        self.factory.side_effect = AuthenticationError("接続設定がありません。")
        app = self.app()
        self.assertIn("接続設定", app.error[0].value)
        self.assertFalse(app.button)

    def test_new_connection_is_not_logged_in(self):
        self.client.auth.sign_in_with_password.side_effect = self.successful_response()
        app = self.app()
        self.fill(app)
        app.button[0].click().run()
        fresh_client = Mock()
        fresh_client.auth.get_session.return_value = None
        self.factory.return_value = fresh_client
        fresh_app = self.app()
        self.assertFalse(fresh_app.success)
        self.assertEqual(len(fresh_app.text_input), 2)
        self.assertIsNot(app.session_state["auth_client"], fresh_app.session_state["auth_client"])


if __name__ == "__main__":
    unittest.main()
