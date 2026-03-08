# 認証セットアップガイド

このドキュメントでは、inbody-analyzer の2つの認証方法について説明します。

## 🎯 どの方法を選ぶ？

| 環境 | 認証方式 | セットアップの難易度 | 推奨される用途 |
|------|---------|-------------------|------------|
| **ローカル開発** | OAuth 2.0 | 中程度 | 個人での開発・テスト |
| **デプロイ（GCP/クラウド）** | サービスアカウント | 簡単 | 本番環境・自動実行 |

---

## 📍 方法1: ローカル開発（OAuth 2.0）

### 概要
- ブラウザで Google アカウントでログイン
- 初回実行時のみ認証（以後は自動）
- デスクトップ・ラップトップなど、ディスプレイがある環境向け

### セットアップ手順

#### ステップ1: Google Cloud プロジェクトの作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 上部のプロジェクト選択ボタンをクリック
3. 「新しいプロジェクト」をクリック
4. プロジェクト名を入力（例: `inbody-analyzer`）
5. 「作成」をクリック

#### ステップ2: Google Drive API を有効化

1. コンソール内で、検索バーに「Google Drive API」と入力
2. 検索結果で「Google Drive API」をクリック
3. 「有効にする」ボタンをクリック

#### ステップ3: OAuth 2.0 認証情報を作成

1. コンソール左メニューから「認証情報」をクリック
2. 「認証情報を作成」ボタンをクリック
3. 「OAuth クライアント ID」を選択
4. アプリケーションの種類を「デスクトップ アプリケーション」に設定
5. 「作成」をクリック

#### ステップ4: credentials.json をダウンロード

1. 作成した認証情報の右側、ダウンロードアイコン（↓）をクリック
2. ダウンロード後、ダウンロードフォルダから下記のようにコピー
   ```bash
   cp ~/Downloads/client_secret_*.json /Users/hisato/git/inbody-analyzer/credentials.json
   ```

✅ **確認**
```bash
ls -la /Users/hisato/git/inbody-analyzer/credentials.json
```

#### ステップ5: Gemini API キーを取得

1. [Google AI Studio](https://aistudio.google.com/app/apikey) にアクセス
2. 「API キーを作成」をクリック
3. 作成されたキーをコピー

#### ステップ6: 環境変数を設定

`.env.local` ファイルを作成して、キーを設定します：

```bash
cat > .env.local << 'EOF'
GEMINI_API_KEY="your-api-key-here"
DRIVE_INPUT_FOLDER_ID="your-drive-folder-id"
DRIVE_PROCESSED_FOLDER_ID="your-processed-folder-id"
EOF
```

**環境変数の説明**
- `GEMINI_API_KEY`: Google AI Studio から取得したキー
- `DRIVE_INPUT_FOLDER_ID`: Google Drive の入力フォルダ ID（URL から取得可）
- `DRIVE_PROCESSED_FOLDER_ID`: 処理済みファイルを移動するフォルダ ID

#### ステップ7: 初回実行

```bash
python main.py
```

初回実行時は以下の流れになります：
1. ブラウザが自動で開く
2. Google アカウントでログイン
3. 「アプリがアカウントにアクセスすることを許可しますか？」→「許可」をクリック
4. `token.json` が自動生成される
5. 以后はこのトークンが自動で使用されます

✅ **完了！**

### トラブルシューティング

**Q: ブラウザが開かない**
- A: ターミナルに表示される URL をコピーしてブラウザで開いてください

**Q: `credentials.json not found` エラー**
- A: Step 4 をもう一度確認し、`credentials.json` が正しい場所にあるか確認してください

**Q: `token.json` を削除したい場合**
- 次回実行時に再度認証画面が表示されます
  ```bash
  rm token.json
  python main.py  # 再認証
  ```

---

## ☁️ 方法2: デプロイ環境（サービスアカウント認証）

### 概要
- API キーベースの自動認証
- ブラウザ操作不要
- GCP Cloud Run、Docker コンテナなど自動実行環境向け

### セットアップ手順

#### ステップ1: サービスアカウントを作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 左メニューから「サービスアカウント」をクリック
3. 「サービスアカウントを作成」をクリック
4. サービスアカウント名を入力（例: `inbody-analyzer-bot`）
5. 「作成」をクリック

#### ステップ2: キーを生成

1. 作成したサービスアカウントをクリック
2. 「キー」タブをクリック
3. 「キーを追加」→「新しいキーを作成」
4. 形式を **JSON** に設定
5. 「作成」をクリック
6. JSON ファイルが自動ダウンロード

#### ステップ3: 環境変数を設定

**方法A: JSON ファイルのパスを指定**（推奨）
```bash
export GOOGLE_SERVICE_ACCOUNT_JSON_PATH="/path/to/service-account.json"
export GEMINI_API_KEY="your-api-key"
export DRIVE_INPUT_FOLDER_ID="your-folder-id"
export DRIVE_PROCESSED_FOLDER_ID="your-folder-id"
python main.py
```

**方法B: JSON 全体を環境変数に指定**
```bash
# service-account.json の内容をコピー
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
python main.py
```

#### ステップ4: Google Drive へのアクセス権限を付与

1. Google Drive の フォルダを開く
2. 共有設定をクリック
3. サービスアカウントのメールアドレス（`xxx@xxx.iam.gserviceaccount.com`）を追加
4. 「編集者」権限で共有

✅ **完了！**

---

## 📋 別紙: Google Drive フォルダ ID の取得方法

### ブラウザで確認
1. Google Drive で該当フォルダを開く
2. URL を確認
   ```
   https://drive.google.com/drive/folders/XXXXXXXXXXXXXXXX
                                          ↑ ここがフォルダ ID
   ```
3. この ID を環境変数に設定

### ターミナルで確認（Google Drive API）
```bash
# Google Drive API を使用して一覧取得
curl -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  'https://www.googleapis.com/drive/v3/files?q=mimeType%3D"application/vnd.google-apps.folder"&spaces=drive&pageSize=10&fields=files(id,name)'
```

---

## 🔐 セキュリティのベストプラクティス

### ✅ 実施すること
- `credentials.json` と `token.json` を Git にコミット**しない**（`.gitignore` に記載済み）
- `.env.local` を Git にコミット**しない**（`.gitignore` に記載済み）
- API キーを GitHub の Secret に設定する（デプロイ時）
- サービスアカウントキーを定期的にローテーション（90日～180日ごと）

### ❌ してはいけないこと
- API キーを ソースコード に直接埋め込む
- API キーを README に記載する
- `credentials.json` を GitHub にアップロード

---

## 参考資料

- [Google Drive API ドキュメント](https://developers.google.com/drive/api/guides/about-sdk)
- [Google Generative AI API ドキュメント](https://ai.google.dev/docs)
- [DEPLOYMENT.md](./DEPLOYMENT.md) - より詳細な実装ガイド
