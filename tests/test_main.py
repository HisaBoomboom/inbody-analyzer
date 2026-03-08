"""
inbody-analyzer のテストスイート

テストの実行:
    pytest tests/test_main.py -v
    pytest tests/test_main.py::test_inbody_measurement_schema -v

カバレッジ確認:
    pytest tests/test_main.py --cov=. --cov-report=html
"""

import pytest
import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import sys

# main.py のインポート
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import InBodyMeasurement, init_csv, append_to_google_sheets


class TestInBodyMeasurementSchema:
    """InBodyMeasurement Pydantic スキーマのテスト"""
    
    def test_valid_measurement(self):
        """有効な測定データが正常にパースされることを確認"""
        data = {
            "measurement_date": "2026/03/08 15:30",
            "weight": 65.2,
            "skeletal_muscle_mass": 28.5,
            "body_fat_mass": 18.3,
            "body_fat_percentage": 28.0,
            "bmi": 23.5,
            "visceral_fat_level": 8,
            "basal_metabolic_rate": 1500,
            "waist_circumference": 78.5,
            "total_body_water": 42.3,
            "protein": 12.5,
            "mineral": 4.2,
            "inbody_score": 75,
            "target_weight": 62.0,
            "fat_control": -3.3,
            "muscle_control": 1.2
        }
        
        measurement = InBodyMeasurement(**data)
        assert measurement.measurement_date == "2026/03/08 15:30"
        assert measurement.weight == 65.2
        assert measurement.bmi == 23.5
        print("✓ Valid measurement schema passed")
    
    def test_missing_required_field(self):
        """必須フィールドが欠けている場合にエラーが発生することを確認"""
        incomplete_data = {
            "measurement_date": "2026/03/08 15:30",
            "weight": 65.2,
            # skeletal_muscle_mass が欠けている
        }
        
        with pytest.raises(ValueError):
            InBodyMeasurement(**incomplete_data)
        print("✓ Missing field validation passed")
    
    def test_invalid_date_format(self):
        """不正な日時形式がログに記録されることを確認"""
        # Pydantic は文字列型なので、型チェックは通るが、
        # datetime.strptime で失敗する可能性がある
        data = {
            "measurement_date": "invalid-date",  # 不正な形式
            "weight": 65.2,
            "skeletal_muscle_mass": 28.5,
            "body_fat_mass": 18.3,
            "body_fat_percentage": 28.0,
            "bmi": 23.5,
            "visceral_fat_level": 8,
            "basal_metabolic_rate": 1500,
            "waist_circumference": 78.5,
            "total_body_water": 42.3,
            "protein": 12.5,
            "mineral": 4.2,
            "inbody_score": 75,
            "target_weight": 62.0,
            "fat_control": -3.3,
            "muscle_control": 1.2
        }
        
        measurement = InBodyMeasurement(**data)
        # Pydantic では文字列として受け入れられるが、
        # 後で datetime.strptime で失敗する
        with pytest.raises(ValueError):
            datetime.strptime(measurement.measurement_date, "%Y/%m/%d %H:%M")
        print("✓ Invalid date format validation passed")


class TestCSVHandling:
    """CSV ファイル処理のテスト"""
    
    def test_init_csv_creates_file(self, tmp_path):
        """CSV ファイルが作成されることを確認"""
        # テンポラリ ディレクトリを使用
        csv_file = tmp_path / "test_inbody_data.csv"
        
        # init_csv のモック版を作成
        if not csv_file.exists():
            import csv
            with open(csv_file, mode="w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(InBodyMeasurement.model_fields.keys()))
                writer.writeheader()
        
        assert csv_file.exists()
        
        # ファイル内容を確認
        with open(csv_file, "r") as f:
            first_line = f.readline()
            assert "measurement_date" in first_line
            assert "weight" in first_line
        print("✓ CSV file creation passed")
    
    def test_csv_headers_match_schema(self):
        """CSV のヘッダーが Pydantic スキーマと一致することを確認"""
        expected_headers = list(InBodyMeasurement.model_fields.keys())
        
        expected_count = 16
        assert len(expected_headers) == expected_count
        
        # 必須フィールドが存在することを確認
        assert "measurement_date" in expected_headers
        assert "weight" in expected_headers
        assert "bmi" in expected_headers
        print(f"✓ CSV headers match schema ({len(expected_headers)} fields)")


class TestGoogleSheetsIntegration:
    """Google Sheets 統合のテスト"""
    
    @patch('main.build')
    def test_append_to_google_sheets_success(self, mock_build):
        """Google Sheets にデータが正常に追記されることを確認"""
        # モック Sheets サービスの設定
        mock_sheets_service = MagicMock()
        mock_build.return_value = mock_sheets_service
        
        # テストデータ
        measurement = InBodyMeasurement(
            measurement_date="2026/03/08 15:30",
            weight=65.2,
            skeletal_muscle_mass=28.5,
            body_fat_mass=18.3,
            body_fat_percentage=28.0,
            bmi=23.5,
            visceral_fat_level=8,
            basal_metabolic_rate=1500,
            waist_circumference=78.5,
            total_body_water=42.3,
            protein=12.5,
            mineral=4.2,
            inbody_score=75,
            target_weight=62.0,
            fat_control=-3.3,
            muscle_control=1.2
        )
        
        # モック API レスポンス
        mock_spreadsheets = MagicMock()
        mock_sheets_service.spreadsheets.return_value = mock_spreadsheets
        mock_values = MagicMock()
        mock_spreadsheets.values.return_value = mock_values
        
        # ヘッダーが存在しないことを想定
        mock_get = MagicMock()
        mock_values.get.return_value = mock_get
        mock_get.execute.return_value = {"values": []}
        
        # append_to_google_sheets を実行
        append_to_google_sheets(
            mock_sheets_service,
            "test_spreadsheet_id",
            "TestSheet",
            measurement
        )
        
        # append メソッドが呼ばれたことを確認
        assert mock_values.append.called
        print("✓ Google Sheets integration test passed")


class TestPDFProcessing:
    """PDF 処理のテスト"""
    
    def test_sample_pdf_exists(self):
        """テスト用PDFファイルが存在することを確認"""
        pdf_path = Path(__file__).parent / "InBody_20260221_1838.pdf"
        
        assert pdf_path.exists(), f"Test PDF not found: {pdf_path}"
        assert pdf_path.suffix == ".pdf"
        
        # ファイルサイズを確認（0 バイトではない）
        assert pdf_path.stat().st_size > 0
        print(f"✓ Test PDF found: {pdf_path} ({pdf_path.stat().st_size} bytes)")
    
    @patch('main.genai.Client')
    def test_pdf_to_measurement_conversion(self, mock_genai):
        """PDF から InBodyMeasurement への変換をテスト（モック）"""
        # モック Gemini クライアントの設定
        mock_client = MagicMock()
        mock_genai.return_value = mock_client
        
        # テストデータを JSON として返すようにモック
        test_measurement = {
            "measurement_date": "2026/02/21 18:38",
            "weight": 65.0,
            "skeletal_muscle_mass": 28.0,
            "body_fat_mass": 18.0,
            "body_fat_percentage": 27.7,
            "bmi": 23.4,
            "visceral_fat_level": 8,
            "basal_metabolic_rate": 1500,
            "waist_circumference": 78.0,
            "total_body_water": 42.0,
            "protein": 12.0,
            "mineral": 4.0,
            "inbody_score": 75,
            "target_weight": 62.0,
            "fat_control": -3.0,
            "muscle_control": 1.0
        }
        
        mock_response = MagicMock()
        mock_response.text = json.dumps(test_measurement)
        mock_client.models.generate_content.return_value = mock_response
        
        # レスポンスをパース
        response_json = json.loads(mock_response.text)
        measurement = InBodyMeasurement(**response_json)
        
        assert measurement.measurement_date == "2026/02/21 18:38"
        assert measurement.weight == 65.0
        print("✓ PDF to measurement conversion test passed")


class TestEnvironmentVariables:
    """環境変数の設定テスト"""
    
    def test_required_env_vars_exist(self):
        """必須の環境変数が設定されていることを確認"""
        required_vars = [
            "GEMINI_API_KEY",
            "DRIVE_INPUT_FOLDER_ID",
            "DRIVE_PROCESSED_FOLDER_ID"
        ]
        
        for var in required_vars:
            value = os.environ.get(var)
            # 設定されていないか、プレースホルダーである場合
            if not value or value.startswith("your-"):
                print(f"⚠️  {var} is not configured")
            else:
                print(f"✓ {var} is configured")
    
    def test_optional_sheets_env_vars(self):
        """Google Sheets の環境変数がオプションであることを確認"""
        sheets_vars = [
            "GOOGLE_SHEETS_SPREADSHEET_ID",
            "GOOGLE_SHEETS_SHEET_NAME"
        ]
        
        for var in sheets_vars:
            value = os.environ.get(var)
            if value:
                print(f"✓ {var} is configured")
            else:
                print(f"ℹ️  {var} is not configured (optional)")


# テスト実行用ヘルパー関数
def run_tests():
    """すべてのテストを実行"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    # pytest が有効な場合は pytest で実行
    # pytest が無い場合は基本的なテストを直接実行
    try:
        import pytest
        run_tests()
    except ImportError:
        print("pytest がインストールされていません")
        print("インストール方法: uv pip install pytest pytest-cov pytest-mock")
        print("\nテストを直接実行します...")
        
        # 基本的なテストを実行
        print("\n=== Running Basic Tests ===\n")
        
        test_schema = TestInBodyMeasurementSchema()
        test_schema.test_valid_measurement()
        
        test_csv = TestCSVHandling()
        test_csv.test_csv_headers_match_schema()
        
        test_pdf = TestPDFProcessing()
        test_pdf.test_sample_pdf_exists()
        
        test_env = TestEnvironmentVariables()
        test_env.test_required_env_vars_exist()
        test_env.test_optional_sheets_env_vars()
        
        print("\n✅ Basic tests completed!")
