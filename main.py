from dotenv import load_dotenv
load_dotenv('.env.local')

import os
import io
import csv
import stat
import json
from datetime import datetime
from pydantic import BaseModel, Field
import google.genai as genai

# Google Drive API 関連
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
import pickle

# --- Pydantic Schema ---
class InBodyMeasurement(BaseModel):
    measurement_date: str = Field(description="The date and time of the measurement in 'YYYY/MM/DD HH:mm' format")
    weight: float = Field(description="Weight in kg")
    skeletal_muscle_mass: float = Field(description="Skeletal Muscle Mass in kg")
    body_fat_mass: float = Field(description="Body Fat Mass in kg")
    body_fat_percentage: float = Field(description="Percent Body Fat (PBF)")
    bmi: float = Field(description="Body Mass Index (BMI)")
    visceral_fat_level: int = Field(description="Visceral Fat Level")
    basal_metabolic_rate: int = Field(description="Basal Metabolic Rate in kcal")
    waist_circumference: float = Field(description="Waist-Hip Ratio or Waist Circumference. If Waist Circumference is written, output its value.")
    total_body_water: float = Field(description="Total Body Water in L")
    protein: float = Field(description="Protein in kg")
    mineral: float = Field(description="Mineral in kg")
    inbody_score: int = Field(description="InBody Score")
    target_weight: float = Field(description="Target Weight in kg")
    fat_control: float = Field(description="Fat Control in kg")
    muscle_control: float = Field(description="Muscle Control in kg")

# --- Constants ---
CSV_FILE = "inbody_data.csv"

def init_csv():
    """CSVファイルが存在しない場合はヘッダーを書き込んで作成する"""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(InBodyMeasurement.model_fields.keys()))
            writer.writeheader()

def _secure_save_token(token_file, credentials):
    """トークンをセキュアに保存（ファイルパーミッション: 600）"""
    with open(token_file, "wb") as token:
        pickle.dump(credentials, token)
    # ファイルパーミッションを 600 (所有者のみ読み書き可) に設定
    os.chmod(token_file, stat.S_IRUSR | stat.S_IWUSR)

def get_drive_service():
    """Google Drive APIクライアントを取得する（OAuth または サービスアカウント認証）
    
    優先順位:
    1. サービスアカウント認証（環境変数から）
       - GOOGLE_SERVICE_ACCOUNT_JSON_PATH: JSONファイルのパス
       - GOOGLE_SERVICE_ACCOUNT_JSON: JSON文字列
       ※デプロイ環境での使用に適しています
    
    2. OAuth 2.0 フロー（ローカル開発環境向け）
       - credentials.json + token.json
       - 初回実行時はブラウザで認証
    
    セキュリティ機能:
    - token.json はファイルパーミッション 600 で保存
    - credentials.json が存在しない場合はエラーで終了
    """
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    TOKEN_FILE = "token.json"
    CREDENTIALS_FILE = "credentials.json"
    
    # === 1. サービスアカウント認証を試行（デプロイ環境向け）===
    service_account_json_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    
    if service_account_json_path or service_account_json:
        try:
            if service_account_json_path:
                # ファイルパスから読み込む
                credentials = ServiceAccountCredentials.from_service_account_file(
                    service_account_json_path,
                    scopes=SCOPES
                )
            else:
                # JSON文字列から読み込む
                service_account_info = json.loads(service_account_json)
                credentials = ServiceAccountCredentials.from_service_account_info(
                    service_account_info,
                    scopes=SCOPES
                )
            
            service = build("drive", "v3", credentials=credentials)
            print("✓ Using Service Account authentication (deployment mode)")
            return service
        except Exception as e:
            print(f"Failed to use Service Account authentication: {e}")
            print("Falling back to OAuth 2.0...\n")
    
    # === 2. OAuth 2.0 フロー（ローカル開発環境向け）===
    credentials = None
    
    # 既存のトークンを読み込む
    if os.path.exists(TOKEN_FILE):
        # トークンファイルのパーミッションを確認（セキュリティチェック）
        token_stat = os.stat(TOKEN_FILE)
        token_mode = stat.S_IMODE(token_stat.st_mode)
        if token_mode != (stat.S_IRUSR | stat.S_IWUSR):
            print(f"Warning: token.json has insecure permissions: {oct(token_mode)}")
            print("Fixing permissions to 600...")
            os.chmod(TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)
        
        with open(TOKEN_FILE, "rb") as token:
            credentials = pickle.load(token)
    
    # トークンが有効でない場合は、新たに取得する
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            # トークンを更新
            credentials.refresh(Request())
            _secure_save_token(TOKEN_FILE, credentials)
        else:
            # 認証情報ファイルがない場合
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Error: {CREDENTIALS_FILE} not found.")
                print("\nFor local development:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create an OAuth 2.0 Desktop App")
                print("3. Download the credentials.json file")
                print(f"4. Place it in: {os.getcwd()}/credentials.json")
                print("\nFor deployment:")
                print("Set environment variables:")
                print("  - GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/path/to/service-account.json")
                print("  OR")
                print("  - GOOGLE_SERVICE_ACCOUNT_JSON='{json_string}'")
                print("\n⚠️  SECURITY WARNING: Never commit credentials.json to GitHub!")
                return None
            
            # OAuth 2.0フロー: ブラウザで認証
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES)
                # デスクトップアプリケーション設定で動作
                credentials = flow.run_local_server(port=0)
                print("✓ Using OAuth 2.0 authentication (local development mode)")
            except Exception as oauth_error:
                print(f"Failed to start OAuth flow: {oauth_error}")
                print("\nMake sure:")
                print("- You're running this on a machine with a display (not a headless server)")
                print("- OR set environment variables for Service Account authentication")
                return None
        
        # トークンをセキュアに保存（ファイルパーミッション: 600）
        if credentials:
            _secure_save_token(TOKEN_FILE, credentials)
    
    try:
        service = build("drive", "v3", credentials=credentials)
        return service
    except Exception as e:
        print(f"Failed to initialize Google Drive API: {e}")
        return None

def append_to_google_sheets(sheets_service, spreadsheet_id, sheet_name, measurement):
    """Google Sheets にデータを追記する
    
    Args:
        sheets_service: Google Sheets API クライアント
        spreadsheet_id: スプレッドシート ID
        sheet_name: シート名
        measurement: InBodyMeasurement オブジェクト
    """
    try:
        # ヘッダーと値を取得
        headers = list(InBodyMeasurement.model_fields.keys())
        values = [measurement.model_dump()[field] for field in headers]
        
        # A1 表記でシートの範囲を指定（最後の行に追加）
        range_name = f"{sheet_name}!A1"
        
        # 最初にヘッダーを確認
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!1:1"
        ).execute()
        
        existing_headers = result.get("values", [None])[0] if result.get("values") else None
        
        # ヘッダーがない場合は追加
        if not existing_headers:
            sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body={"values": [headers]}
            ).execute()
            print(f"✓ Added headers to Google Sheet: {sheet_name}")
        
        # データを追記
        sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": [values]}
        ).execute()
        print(f"✓ Appended data to Google Sheet: {sheet_name}")
        
    except Exception as e:
        print(f"Error appending to Google Sheets: {e}")

def extract_data_from_pdf(client: genai.Client, pdf_bytes: bytes) -> InBodyMeasurement:
    """PDFのバイトデータを受け取り、Gemini APIを使用してInBodyMeasurementモデルを返す"""
    prompt = (
        "You are a helpful assistant. Please extract the requested measurements from the provided InBody scan PDF. "
        "Ensure the output strictly follows the required JSON schema."
    )

    schema = {
        "type": "object",
        "properties": {
            "measurement_date": {"type": "string", "description": "The date and time of the measurement in 'YYYY/MM/DD HH:mm' format"},
            "weight": {"type": "number", "description": "Weight in kg"},
            "skeletal_muscle_mass": {"type": "number", "description": "Skeletal Muscle Mass in kg"},
            "body_fat_mass": {"type": "number", "description": "Body Fat Mass in kg"},
            "body_fat_percentage": {"type": "number", "description": "Percent Body Fat (PBF)"},
            "bmi": {"type": "number", "description": "Body Mass Index (BMI)"},
            "visceral_fat_level": {"type": "integer", "description": "Visceral Fat Level"},
            "basal_metabolic_rate": {"type": "integer", "description": "Basal Metabolic Rate in kcal"},
            "waist_circumference": {"type": "number", "description": "Waist-Hip Ratio or Waist Circumference. If Waist Circumference is written, output its value."},
            "total_body_water": {"type": "number", "description": "Total Body Water in L"},
            "protein": {"type": "number", "description": "Protein in kg"},
            "mineral": {"type": "number", "description": "Mineral in kg"},
            "inbody_score": {"type": "integer", "description": "InBody Score"},
            "target_weight": {"type": "number", "description": "Target Weight in kg"},
            "fat_control": {"type": "number", "description": "Fat Control in kg"},
            "muscle_control": {"type": "number", "description": "Muscle Control in kg"}
        },
        "required": [
            "measurement_date", "weight", "skeletal_muscle_mass", "body_fat_mass",
            "body_fat_percentage", "bmi", "visceral_fat_level", "basal_metabolic_rate",
            "waist_circumference", "total_body_water", "protein", "mineral",
            "inbody_score", "target_weight", "fat_control", "muscle_control"
        ]
    }

    pdf_part = genai.types.Part.from_bytes(
        data=pdf_bytes,
        mime_type="application/pdf"
    )

    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[
            prompt,
            pdf_part
        ],
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,
        )
    )

    response_json = json.loads(response.text)
    return InBodyMeasurement(**response_json)

def process_inbody_pdfs():
    """Google Driveの指定フォルダからPDFを探してGeminiに送信し、処理後にリネームして別フォルダに移動する。
    すでに InBody_ から始まるファイルは処理対象外とする。"""

    # 環境変数の読み込み
    api_key = os.environ.get("GEMINI_API_KEY")
    input_folder_id = os.environ.get("DRIVE_INPUT_FOLDER_ID")
    processed_folder_id = os.environ.get("DRIVE_PROCESSED_FOLDER_ID")
    sheets_spreadsheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID")
    sheets_sheet_name = os.environ.get("GOOGLE_SHEETS_SHEET_NAME")

    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        return

    if not input_folder_id or not processed_folder_id:
        print("Error: DRIVE_INPUT_FOLDER_ID or DRIVE_PROCESSED_FOLDER_ID environment variable is not set.")
        print("Skipping Drive process. You need to set these variables.")
        return

    # google-genai Client の初期化
    client = genai.Client(api_key=api_key)
    drive_service = get_drive_service()
    if not drive_service:
        return

    # Google Sheets サービスの初期化（オプション）
    sheets_service = None
    if sheets_spreadsheet_id and sheets_sheet_name:
        try:
            # Drive サービスと同じ credentials を使用して Sheets サービスを初期化
            if hasattr(drive_service, 'auth'):
                sheets_service = build("sheets", "v4", credentials=drive_service.auth)
            else:
                # 別の方法で認証情報を取得して Sheets サービスを初期化
                from google_auth_oauthlib.flow import InstalledAppFlow
                SCOPES = [
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/spreadsheets"
                ]
                TOKEN_FILE = "token.json"
                CREDENTIALS_FILE = "credentials.json"
                
                credentials = None
                if os.path.exists(TOKEN_FILE):
                    with open(TOKEN_FILE, "rb") as token:
                        credentials = pickle.load(token)
                
                if credentials and credentials.valid:
                    sheets_service = build("sheets", "v4", credentials=credentials)
        except Exception as e:
            print(f"Warning: Google Sheets service not available. {e}")
        
        if sheets_service:
            print("✓ Google Sheets service initialized")
        else:
            print("Warning: Google Sheets service not available. CSV will be saved locally only.")
    else:
        print("Info: GOOGLE_SHEETS_SPREADSHEET_ID or GOOGLE_SHEETS_SHEET_NAME not set. Using local CSV only.")

    init_csv()

    # 入力フォルダ内の PDF ファイルを検索（ただし、すでに "InBody_" で始まるものは除外）
    query = f"'{input_folder_id}' in parents and mimeType='application/pdf' and trashed=false and not name contains 'InBody_'"
    try:
        results = drive_service.files().list(q=query, fields="files(id, name, parents)").execute()
        files = results.get("files", [])
    except Exception as e:
        print(f"Error searching files in Drive: {e}")
        return

    if not files:
        print(f"No unprocessed PDF files found in Drive folder: {input_folder_id}")
        return

    for file_info in files:
        file_id = file_info["id"]
        file_name = file_info["name"]
        print(f"Processing Drive file: {file_name} (ID: {file_id})")

        # ファイルのダウンロード
        try:
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            pdf_bytes = fh.getvalue()
        except Exception as e:
            print(f"Failed to download file {file_name}: {e}")
            continue

        try:
            # Gemini API の呼び出しを共通関数に委譲
            measurement = extract_data_from_pdf(client, pdf_bytes)
            print(f"Extracted Data: {measurement}")

            # CSVへ追記
            with open(CSV_FILE, mode="a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(InBodyMeasurement.model_fields.keys()))
                writer.writerow(measurement.model_dump())

            # Google Sheets に追記（設定されている場合）
            if sheets_service and sheets_spreadsheet_id and sheets_sheet_name:
                append_to_google_sheets(sheets_service, sheets_spreadsheet_id, sheets_sheet_name, measurement)

            # ファイルのリネームと移動（Google Drive上）
            date_obj = datetime.strptime(measurement.measurement_date, "%Y/%m/%d %H:%M")
            new_filename = f"InBody_{date_obj.strftime('%Y%m%d_%H%M')}.pdf"

            # 元の親フォルダを取得して、それを削除し、新しいフォルダを追加する (Move操作)
            previous_parents = ",".join(file_info.get("parents", []))

            drive_service.files().update(
                fileId=file_id,
                addParents=processed_folder_id,
                removeParents=previous_parents,
                body={"name": new_filename},
                fields="id, parents"
            ).execute()
            print(f"Renamed and moved {file_name} to {new_filename} in processed folder.")

        except Exception as e:
            print(f"Error processing {file_name}: {e}")

if __name__ == "__main__":
    process_inbody_pdfs()
