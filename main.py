import os
import io
import csv
from datetime import datetime
from pydantic import BaseModel, Field
import google.generativeai as genai

# Google Drive API 関連
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth import default as google_auth_default

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

def get_drive_service():
    """Google Drive APIクライアントを取得する"""
    try:
        credentials, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/drive"])
        service = build("drive", "v3", credentials=credentials)
        return service
    except Exception as e:
        print(f"Failed to initialize Google Drive API: {e}")
        return None

def process_inbody_pdfs():
    """Google Driveの指定フォルダからPDFを探してGeminiに送信し、処理後にリネームして別フォルダに移動する。
    すでに InBody_ から始まるファイルは処理対象外とする。"""

    # 環境変数の読み込み
    api_key = os.environ.get("GEMINI_API_KEY")
    input_folder_id = os.environ.get("DRIVE_INPUT_FOLDER_ID")
    processed_folder_id = os.environ.get("DRIVE_PROCESSED_FOLDER_ID")

    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        return

    if not input_folder_id or not processed_folder_id:
        print("Error: DRIVE_INPUT_FOLDER_ID or DRIVE_PROCESSED_FOLDER_ID environment variable is not set.")
        print("Skipping Drive process. You need to set these variables.")
        return

    # APIの初期化
    genai.configure(api_key=api_key)
    drive_service = get_drive_service()
    if not drive_service:
        return

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

        # google-generativeai SDKは内部でエンコードするため、そのままbytesを渡す
        pdf_part = {
            "mime_type": "application/pdf",
            "data": pdf_bytes
        }

        # Gemini API の呼び出し
        prompt = (
            "You are a helpful assistant. Please extract the requested measurements from the provided InBody scan PDF. "
            "Ensure the output strictly follows the required JSON schema."
        )

        try:
            model = genai.GenerativeModel("gemini-1.5-flash")

            # Structured OutputsとしてPydanticのSchemaを渡す
            response = model.generate_content(
                [prompt, pdf_part],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=InBodyMeasurement,
                    temperature=0.0,
                )
            )

            # Pydanticモデルで検証・パース
            measurement = InBodyMeasurement.model_validate_json(response.text)
            print(f"Extracted Data: {measurement}")

            # CSVへ追記
            with open(CSV_FILE, mode="a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(InBodyMeasurement.model_fields.keys()))
                writer.writerow(measurement.model_dump())

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
