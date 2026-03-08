# デプロイメントガイド

このドキュメントでは、inbody-analyzer を異なる環境での実行方法を説明します。

## 実行環境の認証方法の選択

本プロジェクトは 2 つの認証方式をサポートしています：

| 環境 | 認証方式 | 対象環境 |
|------|---------|---------|
| **ローカル開発** | OAuth 2.0（インタラクティブ） | デスクトップ・ラップトップ |
| **デプロイ ** | サービスアカウント（非対話） | サーバー・コンテナ・CI/CD |

---

## 1. ローカル開発環境（OAuth 2.0）

### 初回セットアップ

#### 1.1 Google Cloud Console で認証情報を取得

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを作成（または既存プロジェクトを選択）
3. "Google Drive API" を有効化
   - 検索: "Google Drive API"
   - 「有効にする」をクリック

4. OAuth 2.0 認証情報を作成
   - メニュー: 「認証情報」を選択
   - 「認証情報を作成」 → 「OAuth クライアント ID」
   - アプリケーションの種類: **デスクトップアプリケーション**
   - 「作成」をクリック

5. `credentials.json` をダウンロード
   - 作成した認証情報の横の「↓」アイコン
   - ダウンロードして、プロジェクトルートに配置

```bash
cp ~/Downloads/client_secret_*.json ./credentials.json
```

**⚠️  セキュリティ警告**
- `credentials.json` を Git にコミット**しないでください**
- `.gitignore` に既に追加済みです

#### 1.2 初回実行時の認証

```bash
python main.py
```

- ブラウザが自動で開く
- Google アカウントで許可
- `token.json` が自動生成される

#### 1.3 以降の実行

```bash
python main.py
```

- `token.json` が自動で使用される
- 有効期限切れ時は自動更新
- **ユーザー操作は不要**

---

## 2. デプロイ環境（サービスアカウント認証）

### 対応環境

- ☁️  Google Cloud Run
- 🐳 Docker/Kubernetes
- 🚀 CI/CD パイプライン
- 📡 クラウドサーバー（AWS, Azure など）

### セットアップ

#### 2.1 Google Cloud でサービスアカウントを作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 「サービスアカウント」を選択
3. 「サービスアカウントを作成」をクリック
4. サービスアカウント名を入力（例: `inbody-analyzer`）
5. [オプション] 説明を追加

#### 2.2 キーを生成

1. サービスアカウントをクリック
2. 「キー」タブを選択
3. 「キーを追加」 → 「新しいキーを作成」
4. 形式: **JSON** を選択
5. 「作成」をクリック → JSON ファイルが自動ダウンロード

#### 2.3 Google Drive へのアクセス権を付与

1. Google Drive フォルダを開く
2. 共有設定で、サービスアカウント用のメールアドレス`xxxxxxx@xxxxxx.iam.gserviceaccount.com`を追加

#### 2.4 環境変数を設定

**方法A: JSON ファイルのパスを指定（推奨）**

```bash
export GOOGLE_SERVICE_ACCOUNT_JSON_PATH="/path/to/service-account.json"
python main.py
```

**方法B: JSON 文字列を直接指定**

```bash
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
python main.py
```

### デプロイ例

#### Docker での実行

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV GOOGLE_SERVICE_ACCOUNT_JSON_PATH="/app/secrets/service-account.json"
ENV GEMINI_API_KEY="your_api_key"

CMD ["python", "main.py"]
```

実行方法：

```bash
docker run \
  -e GOOGLE_SERVICE_ACCOUNT_JSON_PATH="/app/secrets/service-account.json" \
  -e GEMINI_API_KEY="your_api_key" \
  -v /path/to/service-account.json:/app/secrets/service-account.json:ro \
  inbody-analyzer
```

#### GitHub Actions での実行

```yaml
name: Run inbody-analyzer

on:
  schedule:
    - cron: '0 0 * * *'  # 毎日実行

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run analyzer
        env:
          GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python main.py
```

---

## トラブルシューティング

### ❌ "credentials.json not found" エラー（ローカル開発環境）

**原因**: OAuth 認証ファイルが見つからない

**解決方法**:
1. Google Cloud Console から `credentials.json` をダウンロード
2. プロジェクトルートに配置
   ```bash
   ls -la credentials.json
   ```

### ❌ OAuth フロー失敗（サーバー環境）

**原因**: サーバー環境ではブラウザが利用できない

**解決方法**:
1. サービスアカウント認証を使用してください
2. 環境変数を設定：
   ```bash
   export GOOGLE_SERVICE_ACCOUNT_JSON_PATH="/path/to/service-account.json"
   ```

### ❌ "Permission denied" エラー

**原因**:
- Google Drive フォルダへのアクセス権限がない
- token.json のファイルパーミッションが不正

**解決方法**:
1. Google Drive フォルダをサービスアカウントと共有
2. token.json のパーミッションを確認：
   ```bash
   ls -la token.json
   ```
   期待値: `rw-------` (600)

### ❌ "token.json has insecure permissions" 警告

**原因**: token.json が他のユーザーに読み取り可能

**解決方法**:
```bash
chmod 600 token.json
```

---

## セキュリティベストプラクティス

### ✅ ローカル開発

- ✓ `token.json` は `.gitignore` に記載（自動保護）
- ✓ ファイルパーミッション自動設定（600）
- ✓ 認証情報はローカルに保存、クラウドに送信されない

### ✅ デプロイ環境

- ✓ サービスアカウント JSON は Git に含めない
- ✓ CI/CD シークレット管理を使用（GitHub Secrets など）
- ✓ サービスアカウントに最小限の権限を付与
- ✓ 定期的にキーをローテーション

---

## Q&A

**Q: ローカルとデプロイ環境で認証を随時切り替えたい**

A: 自動フォールバック機能がついています！
1. デプロイ環境では`GOOGLE_SERVICE_ACCOUNT_JSON_PATH` を設定
2. 見つからない場合、自動的に OAuth フロー（credentials.json）にフォールバック

**Q: サービスアカウントキーの有効期限は？**

A: GCP で生成した JSON キーに有効期限はありません。ですが、セキュリティのため**定期的なキーローテーション（90日～180日ごと）** を推奨します。

**Q: 複数の環境でインスタンスを走らせている場合は？**

A: 各環境で異なる`token.json`を使うため、問題ありません。JSON ファイルはマシンローカルに保存です。
