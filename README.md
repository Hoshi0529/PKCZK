# pokecham

Streamlit と Supabase Auth を使った、新規登録・ログイン画面です。

## セットアップ

Python 環境に必要なパッケージをインストールします。

```powershell
python -m pip install -r requirements.txt
```

`back/.env` に接続情報を設定します。既存のファイルは上書きしないでください。
環境変数でも設定でき、環境変数の値を優先します。

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_your_key
```

Supabase のメール認証と新規登録を有効にします。
確認メールなしで登録する場合は、Authentication → Sign In / Providers の
「Confirm email」を OFF にして保存します。
実際の `.env` は Git にコミットしないでください。

## 起動

```powershell
streamlit run Login.py
```

新規登録ではユーザー名（空白のみ不可・前後の空白を除いて1〜50文字）を入力します。
ユーザー名は登録時に Supabase Auth のユーザーメタデータ `username` に保存します。
専用テーブルの追加は不要で、ユーザー名の重複は許可します。
登録・ログインに成功すると、同じ画面にユーザー名・メールアドレス・完了メッセージを表示します。
ユーザー名を持たない既存アカウントでも、これまでどおりログインできます。
認証状態は Streamlit の接続中だけ保持し、ブラウザを再読み込みすると再ログインが必要です。
画面遷移・ログアウト・会話データとの連携は未実装です。
