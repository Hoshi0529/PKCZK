# pokecham

## ローカル起動

Python 3.15.2 / Streamlit 1.66.1 / Supabase 2.33.0 / python-dotenv 1.2.4 で確認しています。

この PC では通常の `streamlit` コマンドが使う環境にも必要なライブラリをインストールしています。
`python`・`pip`・`streamlit` は Python 3.15 の環境を優先する設定です。
環境を切り替えた直後はターミナルを開き直してください。
プロジェクトのフォルダで、次のコマンドで起動できます。

```powershell
streamlit run Login.py
```

プロジェクト専用の `.venv` を使って起動する場合は、次のコマンドを実行します。
`run.cmd` はプロジェクト専用の Python を使うため、通常の `streamlit` コマンドの環境に影響されません。

```powershell
.\run.cmd
```

Python を直接指定する場合は、次のコマンドでも起動できます。

```powershell
.\.venv\Scripts\python.exe -m streamlit run Login.py
```

別の PC で通常の `streamlit` コマンドを使う場合は、Python 3.15.2 をインストールして PATH に追加し、次を実行します。

```powershell
python -m pip install -r requirements.txt
streamlit run Login.py
```

プロジェクト専用の `.venv` を用意する場合も、Python 3.15.2 を選んでから実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run Login.py
```

`back/.env.example` を参考に `back/.env` を用意します。既存の `.env` は上書きしないでください。
環境変数が設定されている場合は、そちらを優先します。

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_your_key
```

Supabase のメール＋パスワード認証と新規登録を有効にします。
開発時に登録直後からログインする場合は Confirm email を無効にします。
有効な場合は確認メールの案内を表示するため、メール確認後にログインしてください。
接続文字列・Secret key・service_role・JWKS URL はこの認証処理では使用しません。
実際の `.env` は Git にコミットしないでください。

登録・ログインが成功すると、同じ画面に完了メッセージとメールアドレスを表示します。
認証状態は利用者ごとの Streamlit 接続内だけに保持します。
ブラウザの再読み込みや新しい接続では再ログインが必要です。
会話データの読み書き、画面遷移、他画面の認証制御、ログアウトは今回の対象外です。

## テスト

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

テストは認証APIをモックし、実ユーザーや会話データを作成しません。
