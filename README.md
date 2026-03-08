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
uv pip install pydantic google-generativeai google-api-python-client google-auth

# 開発用パッケージ (Linter/Formatterなど) を追加する場合
uv pip install ruff pytest
```

### 環境変数の設定

**方法1: `.env.local` ファイルを使用（推奨）**

1. プロジェクトルートに `.env.local` ファイルを作成します：
```bash
cp .env.example .env.local
```

2. `.env.local` を編集して、実際の値を設定してください：
```bash
GEMINI_API_KEY="your_api_key_here"
GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service-account.json"
DRIVE_INPUT_FOLDER_ID="your_input_folder_id"
DRIVE_PROCESSED_FOLDER_ID="your_processed_folder_id"
```

3. `python-dotenv` をインストールします：
```bash
uv pip install python-dotenv
```

4. `main.py` の先頭に以下を追加して、`.env.local` を自動読み込みします：
```python
from dotenv import load_dotenv
load_dotenv('.env.local')
```

**.env.local は `.gitignore` に含まれているため、Git にはコミットされません。機密情報は安全に管理されます。**

**方法2: 環境変数を直接設定する場合**
```bash
export GEMINI_API_KEY="your_api_key_here"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service-account.json"
export DRIVE_INPUT_FOLDER_ID="your_input_folder_id"
export DRIVE_PROCESSED_FOLDER_ID="your_processed_folder_id"
```

実行
```bash
python main.py
```

## 2. GCPアーキテクチャ案 (Google Driveベース)

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
