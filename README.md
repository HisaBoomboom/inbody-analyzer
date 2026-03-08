# inbody-analyzer

InBodyの測定結果PDFをGemini APIで構造化データとして抽出し、蓄積するシステム。
ローカルでの実行に加え、将来的にはGCP上での本格的なデータ分析基盤として稼働することを想定しています。

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

# 必要なパッケージを追加
uv pip install pydantic google-generativeai

# 開発用パッケージ (Linter/Formatterなど) を追加する場合
uv pip install ruff pytest
```

実行の際は、環境変数としてGemini APIのキーを設定してください。

```bash
export GEMINI_API_KEY="your_api_key_here"
# 実行
python main.py
```

## 2. GCPアーキテクチャ案

本格的な運用として、GCPにデプロイする場合のアーキテクチャ案は以下の通りです。

### アーキテクチャ構成
1. **Cloud Storage (入力バケット):** スキャンしたPDFファイル（`スキャン_*.pdf`）をアップロードする場所。
2. **Eventarc:** 入力バケットへのファイルアップロードイベント（`google.cloud.storage.object.v1.finalized`）を検知し、Cloud Runへリクエストを送信。
3. **Cloud Run (処理コンテナ):**
   - `main.py` をFastAPI等でラップしたWebサーバーとしてデプロイ。
   - Eventarcからのリクエストを受け取り、Cloud Storageから該当PDFをダウンロード。
   - Gemini APIを呼び出し、データを構造化して抽出。
   - （現状はローカルCSV追記ですが、GCP上では）**BigQuery** へ直接データをストリーミングインサート。
   - 処理後、元のPDFファイル名を `InBody_YYYYMMDD_HHMM.pdf` にリネームして**Cloud Storage (保存用バケット)**に移動。
4. **Secret Manager:** Gemini APIのAPIキーを安全に保存し、Cloud Runの環境変数として注入。

本リポジトリに含まれる `main.tf` は、このアーキテクチャのベースとなるCloud Storage、Cloud Run、Eventarcトリガー、および必要なIAM権限を構築するためのTerraformのひな形です。
