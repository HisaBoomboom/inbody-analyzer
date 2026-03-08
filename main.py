import os
import glob
import base64
import csv
from datetime import datetime
from pydantic import BaseModel, Field
import google.generativeai as genai

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
            # Pydanticモデルからフィールド名を取得
            writer = csv.DictWriter(f, fieldnames=list(InBodyMeasurement.model_fields.keys()))
            writer.writeheader()

def process_inbody_pdfs():
    """ローカルの「スキャン_*.pdf」を探してGeminiに送信、抽出結果をCSVに追記し、リネームする"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        return

    genai.configure(api_key=api_key)

    # PDFファイルの検索
    pdf_files = glob.glob("スキャン_*.pdf")
    if not pdf_files:
        print("No matching PDF files found (スキャン_*.pdf).")
        return

    init_csv()

    for file_path in pdf_files:
        print(f"Processing: {file_path}")

        # Base64でエンコード (gemini-1.5-flashへのMIME渡し用)
        try:
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()
        except Exception as e:
            print(f"Failed to read file {file_path}: {e}")
            continue

        # File APIを使ったアップロード（Flash 1.5でPDFを解釈する推奨方法）
        # ただし単純にインラインで投げる場合は base64化し `mime_type` を指定する
        encoded_pdf = base64.b64encode(pdf_bytes).decode('utf-8')

        pdf_part = {
            "mime_type": "application/pdf",
            "data": encoded_pdf
        }

        # Gemini API の呼び出し
        prompt = (
            "You are a helpful assistant. Please extract the requested measurements from the provided InBody scan PDF. "
            "Ensure the output strictly follows the required JSON schema."
        )

        try:
            # gemini-1.5-flashを使用
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

            # 抽出されたJSON文字列をPydanticモデルで検証・パース
            measurement = InBodyMeasurement.model_validate_json(response.text)
            print(f"Extracted Data: {measurement}")

            # CSVへ追記
            with open(CSV_FILE, mode="a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(InBodyMeasurement.model_fields.keys()))
                writer.writerow(measurement.model_dump())

            # ファイルのリネーム
            # measurement.measurement_date を "YYYY/MM/DD HH:mm" -> "YYYYMMDD_HHMM" に変換
            date_obj = datetime.strptime(measurement.measurement_date, "%Y/%m/%d %H:%M")
            new_filename = f"InBody_{date_obj.strftime('%Y%m%d_%H%M')}.pdf"

            os.rename(file_path, new_filename)
            print(f"Renamed {file_path} to {new_filename}")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    process_inbody_pdfs()
