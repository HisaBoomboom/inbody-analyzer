# inbody-analyzer

InBodyの測定結果PDFをGemini APIで構造化データとして抽出し、蓄積するシステム。
ローカルでの実行に加え、将来的にはGCP上での本格的なデータ分析基盤として稼働することを想定しています。

現在のアーキテクチャでは、個人のスマートフォンから手軽にアップロードできる**Google Drive**をファイルの一時保管場所として採用しています。

## 1. プロジェクトのセットアップ (`uv` を使用)

このプロジェクトはパッケージ管理に [uv](https://github.com/astral-sh/uv) を使用しています。Python 3.12以上が必要です。

```bash
# uv のインストール (まだインストールしていない場合)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Python 3.12 のインストール (必要な場合)
uv python install 3.12

# 仮想環境の作成と依存パッケージのインストール
uv venv --python 3.12
source .venv/bin/activate

# 必要なパッケージを追加 (Gemini, Google Drive API, Pydantic)
uv pip install google-genai google-api-python-client google-auth-oauthlib python-dotenv pydantic

# 開発用パッケージ (Linter/Formatterなど) を追加する場合
uv pip install ruff pytest
```

### 認証セットアップ

本プロジェクトでは、以下の2つの認証方式をサポートしています：

| 環境 | 方式 | 対象 |
|------|------|------|
| **ローカル開発** | OAuth 2.0 | 個人での開発・テスト |
| **デプロイ環境** | サービスアカウント | GCP Cloud Run など |

**詳細なセットアップ方法は [AUTH_SETUP.md](./AUTH_SETUP.md) を参照してください。**

#### クイックスタート（ローカル開発）

```bash
# 1. credentials.json を Google Cloud Console からダウンロード
#    → プロジェクトルートに配置

# 2. .env.local を作成
cat > .env.local << 'EOF'
GEMINI_API_KEY="your-api-key-here"
DRIVE_INPUT_FOLDER_ID="your-folder-id"
DRIVE_PROCESSED_FOLDER_ID="your-folder-id"
EOF

# icon実行
python main.py
# → ブラウザが開いて認証画面が表示されます
```

## 3. テストの実行

PyTest を使用してテストを実行できます。

### テスト環境のセットアップ

```bash
# テスト用パッケージをインストール
uv pip install pytest pytest-cov pytest-mock
```

### テストの実行方法

```bash
# すべてのテストを実行
pytest

# 特定のテストのみ実行
pytest tests/test_main.py -v

# スキーマのテストのみ実行
pytest tests/test_main.py::TestInBodyMeasurementSchema -v

# カバレッジレポートを生成
pytest --cov --cov-report=html
```

### テスト内容

テストスイート（[tests/test_main.py](./tests/test_main.py)）では以下を検証：

- ✅ **Pydantic スキーマ**: 入力データのバリデーション
- ✅ **CSV 処理**: ファイルの作成と書き込み
- ✅ **Google Sheets 統合**: データの追記（モック）
- ✅ **PDF 処理**: テスト PDF の存在確認
- ✅ **環境変数**: 必須・オプショナル設定の確認

テスト用 PDF：
- `InBody_20260221_1838.pdf` - サンプルの InBody 測定結果（テスト用）

## 4. GCPアーキテクチャ案 (Google Driveベース)

本格的な運用として、GCPにデプロイする場合のアーキテクチャ案は以下の通りです。
スマートフォンアプリのGoogle Drive機能を使って紙の結果をスキャン・保存すると、GCP側で定期的に回収・分析します。

### アーキテクチャ構成
1. **Google Drive (入力フォルダ):** スキャンしたPDFファイル（スマートフォンのスキャン機能等で自動作成された任意の名前のPDF）を保存する場所。
2. **Cloud Scheduler:** 毎日決まった時間（例: 毎晩0時、または1時間ごと）に起動イベントを発火。
3. **Cloud Run (Job):**
   - イベントをトリガーとして `main.py` がバッチジョブとして起動。
   - Google Drive APIを使用して未処理のPDFをダウンロード。
   - Gemini APIを呼び出し、データを構造化して抽出。
   - （現状はローカルCSV追記ですが、GCP上では）**BigQuery** へ直接データをストリーミングインサート。
   - 処理後、Google Drive上の元のPDFファイル名を `InBody_YYYYMMDD_HHMM.pdf` にリネームし、**処理済みフォルダ**に移動。
4. **Secret Manager:** Gemini APIのキーなど、機密情報を安全に保存し、Cloud Runの環境変数として注入。

本リポジトリに含まれる `main.tf` は、このアーキテクチャのベースとなるCloud Run Job、Cloud Scheduler、および必要なIAM権限を構築するためのTerraformのひな形です。将来的にサービス規模が拡大した場合は、Google DriveからCloud Storageベース（Eventarc駆動）に変更することも容易です。
