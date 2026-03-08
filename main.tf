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

# --- Service Account for Cloud Run Job ---
resource "google_service_account" "inbody_runner" {
  account_id   = "inbody-cloudrun-job-sa"
  display_name = "Service Account for InBody Cloud Run Analyzer Job"
}

# Grant Cloud Run SA access to BigQuery (for future use)
resource "google_project_iam_member" "bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.inbody_runner.email}"
}

# Note: The service account also needs access to Google Drive API.
# You will need to share the Google Drive folders with this Service Account's email address.

# --- Cloud Run Job (Placeholder) ---
# Note: You need to build and push a Docker image containing main.py before deploying this.
resource "google_cloud_run_v2_job" "inbody_analyzer_job" {
  name     = "inbody-analyzer-job"
  location = var.region

  template {
    template {
      service_account = google_service_account.inbody_runner.email
      containers {
        # Replace with your actual container image URI
        image = "us-docker.pkg.dev/cloudrun/container/job"

        # Example of setting Environment Variables
        # env {
        #   name = "GEMINI_API_KEY"
        #   value_source {
        #     secret_key_ref {
        #       secret  = google_secret_manager_secret.gemini_key.secret_id
        #       version = "latest"
        #     }
        #   }
        # }
        # env {
        #   name  = "DRIVE_INPUT_FOLDER_ID"
        #   value = "your_input_folder_id"
        # }
        # env {
        #   name  = "DRIVE_PROCESSED_FOLDER_ID"
        #   value = "your_processed_folder_id"
        # }
      }
    }
  }
}

# --- Cloud Scheduler ---
# Trigger the Cloud Run Job periodically (e.g., every day at midnight)
resource "google_cloud_scheduler_job" "inbody_job_trigger" {
  name             = "trigger-inbody-analyzer-job"
  description      = "Triggers the InBody Analyzer Cloud Run Job"
  schedule         = "0 0 * * *"
  time_zone        = "Asia/Tokyo"
  region           = var.region

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.inbody_analyzer_job.name}:run"

    oauth_token {
      service_account_email = google_service_account.inbody_runner.email
    }
  }
}

# Grant the Scheduler service account permission to invoke Cloud Run Jobs
resource "google_project_iam_member" "scheduler_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.inbody_runner.email}"
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
