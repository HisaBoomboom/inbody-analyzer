terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type        = string
  description = "The GCP project ID"
}

variable "region" {
  type        = string
  default     = "asia-northeast1"
  description = "The GCP region to deploy resources"
}

# --- Cloud Storage (Input and Output Buckets) ---
resource "google_storage_bucket" "input_bucket" {
  name          = "${var.project_id}-inbody-input"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "processed_bucket" {
  name          = "${var.project_id}-inbody-processed"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
}

# --- Service Account for Cloud Run ---
resource "google_service_account" "inbody_runner" {
  account_id   = "inbody-cloudrun-sa"
  display_name = "Service Account for InBody Cloud Run Analyzer"
}

# Grant Cloud Run SA access to Storage
resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.inbody_runner.email}"
}

# Grant Cloud Run SA access to BigQuery (for future use)
resource "google_project_iam_member" "bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.inbody_runner.email}"
}

# --- Cloud Run Service (Placeholder) ---
# Note: You need to build and push a Docker image (e.g., using Artifact Registry)
# containing main.py wrapped with a Web Server (like FastAPI or Flask) before deploying this.
resource "google_cloud_run_v2_service" "inbody_analyzer" {
  name     = "inbody-analyzer-service"
  location = var.region

  template {
    service_account = google_service_account.inbody_runner.email
    containers {
      # Replace with your actual container image URI
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      # Example of how to pass the Secret Manager secret to Cloud Run
      # env {
      #   name = "GEMINI_API_KEY"
      #   value_source {
      #     secret_key_ref {
      #       secret  = google_secret_manager_secret.gemini_key.secret_id
      #       version = "latest"
      #     }
      #   }
      # }
    }
  }
}

# --- Eventarc Trigger ---
# Trigger Cloud Run when a new object is uploaded to the input bucket
resource "google_eventarc_trigger" "bucket_upload_trigger" {
  name     = "inbody-pdf-upload-trigger"
  location = var.region

  service_account = google_service_account.inbody_runner.email

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.input_bucket.name
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.inbody_analyzer.name
      region  = var.region
    }
  }
}

# --- BigQuery Dataset (For future data storage) ---
resource "google_bigquery_dataset" "inbody_data" {
  dataset_id                  = "inbody_analytics"
  friendly_name               = "InBody Analytics Dataset"
  description                 = "Dataset for storing structured InBody measurement data"
  location                    = var.region
}

# --- BigQuery Table (For future data storage) ---
resource "google_bigquery_table" "inbody_measurements" {
  dataset_id = google_bigquery_dataset.inbody_data.dataset_id
  table_id   = "measurements"

  # Schema roughly matches the Pydantic model
  schema = <<EOF
[
  {"name": "measurement_date", "type": "STRING", "mode": "REQUIRED"},
  {"name": "weight", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "skeletal_muscle_mass", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "body_fat_mass", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "body_fat_percentage", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "bmi", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "visceral_fat_level", "type": "INTEGER", "mode": "REQUIRED"},
  {"name": "basal_metabolic_rate", "type": "INTEGER", "mode": "REQUIRED"},
  {"name": "waist_circumference", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "total_body_water", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "protein", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "mineral", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "inbody_score", "type": "INTEGER", "mode": "REQUIRED"},
  {"name": "target_weight", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "fat_control", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "muscle_control", "type": "FLOAT", "mode": "REQUIRED"}
]
EOF
}
