from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
import google.genai as genai
import os
from main import extract_data_from_pdf, init_csv, append_to_google_sheets, CSV_FILE, InBodyMeasurement
import csv
from googleapiclient.discovery import build
import pickle

app = FastAPI(title="InBody Analyzer Web")

# Load environment variables
from dotenv import load_dotenv
load_dotenv('.env.local')

# Setup Gemini API key
api_key = os.environ.get("GEMINI_API_KEY")

def get_sheets_service():
    """Google Sheets サービスの初期化（main.py からの処理を簡略化して流用）"""
    sheets_spreadsheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID")
    sheets_sheet_name = os.environ.get("GOOGLE_SHEETS_SHEET_NAME")

    if not sheets_spreadsheet_id or not sheets_sheet_name:
        return None, None, None

    try:
        SCOPES = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets"
        ]
        TOKEN_FILE = "token.json"

        credentials = None
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "rb") as token:
                credentials = pickle.load(token)

        if credentials and credentials.valid:
            sheets_service = build("sheets", "v4", credentials=credentials)
            return sheets_service, sheets_spreadsheet_id, sheets_sheet_name
    except Exception as e:
        print(f"Warning: Google Sheets service not available. {e}")

    return None, None, None

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>InBody Analyzer Web</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container mt-5">
            <h2 class="mb-4">InBody PDF Analyzer</h2>
            <div class="card p-4">
                <form id="uploadForm">
                    <div class="mb-3">
                        <label for="pdfFile" class="form-label">InBody 測定結果 PDFをアップロードしてください</label>
                        <input class="form-control" type="file" id="pdfFile" accept="application/pdf" required>
                    </div>
                    <button type="submit" class="btn btn-primary" id="submitBtn">解析する</button>
                    <div class="spinner-border text-primary ms-3 d-none" id="loadingSpinner" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </form>
            </div>

            <div id="resultCard" class="card mt-4 p-4 d-none">
                <h4 class="mb-3">解析結果</h4>
                <div id="resultContent"></div>
            </div>

            <div id="errorAlert" class="alert alert-danger mt-4 d-none" role="alert"></div>
        </div>

        <script>
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();

                const fileInput = document.getElementById('pdfFile');
                const file = fileInput.files[0];
                if (!file) return;

                const submitBtn = document.getElementById('submitBtn');
                const loadingSpinner = document.getElementById('loadingSpinner');
                const resultCard = document.getElementById('resultCard');
                const resultContent = document.getElementById('resultContent');
                const errorAlert = document.getElementById('errorAlert');

                // Reset UI
                submitBtn.disabled = true;
                loadingSpinner.classList.remove('d-none');
                resultCard.classList.add('d-none');
                errorAlert.classList.add('d-none');

                const formData = new FormData();
                formData.append('file', file);

                try {
                    const response = await fetch('/api/upload', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok) {
                        resultContent.innerHTML = `<pre><code>${JSON.stringify(data, null, 2)}</code></pre>`;
                        resultCard.classList.remove('d-none');
                    } else {
                        errorAlert.textContent = data.detail || 'エラーが発生しました';
                        errorAlert.classList.remove('d-none');
                    }
                } catch (error) {
                    errorAlert.textContent = '通信エラーが発生しました';
                    errorAlert.classList.remove('d-none');
                } finally {
                    submitBtn.disabled = false;
                    loadingSpinner.classList.add('d-none');
                }
            });
        </script>
    </body>
    </html>
    """

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDFファイルのみアップロード可能です")

    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEYが設定されていません")

    try:
        # Read PDF bytes
        pdf_bytes = await file.read()

        # Initialize Gemini client
        client = genai.Client(api_key=api_key)

        # Extract data
        measurement = extract_data_from_pdf(client, pdf_bytes)

        # Save to CSV
        init_csv()
        with open(CSV_FILE, mode="a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(InBodyMeasurement.model_fields.keys()))
            writer.writerow(measurement.model_dump())

        # Optional: Save to Google Sheets
        sheets_service, sheets_spreadsheet_id, sheets_sheet_name = get_sheets_service()
        if sheets_service and sheets_spreadsheet_id and sheets_sheet_name:
            append_to_google_sheets(sheets_service, sheets_spreadsheet_id, sheets_sheet_name, measurement)

        return measurement.model_dump()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
