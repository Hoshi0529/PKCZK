def validate_account_input(
    email: str,
    password: str,
    is_registering: bool,
    confirm_password: str,
) -> str | None:
    if not email.strip() or not password:
        return "メールアドレスとパスワードを入力してください。"
    if is_registering and password != confirm_password:
        return "確認用パスワードが一致しません。"
    return None
