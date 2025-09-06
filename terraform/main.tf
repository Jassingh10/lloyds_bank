terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
  required_version = ">= 1.1.0"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# -------------------
# Storage buckets
# -------------------
resource "google_storage_bucket" "raw_data_bucket" {
  name                        = "${var.project_id}-${var.raw_data_bucket_name}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "dataflow_temp_bucket" {
  name          = "${var.project_id}-${var.dataflow_temp_bucket_name}"
  location      = var.region
  force_destroy = true
}

# -------------------
# BigQuery dataset
# -------------------
resource "google_bigquery_dataset" "raw_data_dataset" {
  dataset_id                  = var.dataset_id
  location                    = var.region
  delete_contents_on_destroy = true
}

# -------------------
# Customer Raw Table (all NULLABLE - for initial load)
# -------------------
resource "google_bigquery_table" "customer_raw" {
  dataset_id          = google_bigquery_dataset.raw_data_dataset.dataset_id
  table_id            = "customer_raw"
  deletion_protection = false

  schema = <<EOF
[
  {"name": "customer_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "first_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "last_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "email", "type": "STRING", "mode": "NULLABLE"},
  {"name": "creation_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "ingestion_time", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "file_name", "type": "STRING", "mode": "NULLABLE"}
]
EOF
}

# -------------------
# Customer Staging Table (clean - REQUIRED IDs)
# -------------------
resource "google_bigquery_table" "customer_staging" {
  dataset_id          = google_bigquery_dataset.raw_data_dataset.dataset_id
  table_id            = "customer_staging"
  deletion_protection = false

  schema = <<EOF
[
  {"name": "customer_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "first_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "last_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "email", "type": "STRING", "mode": "NULLABLE"},
  {"name": "creation_date", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

# -------------------
# Customer Dead Letter Table
# -------------------
resource "google_bigquery_table" "customer_deadletter" {
  dataset_id          = google_bigquery_dataset.raw_data_dataset.dataset_id
  table_id            = "customer_staging_deadletter"
  deletion_protection = false

  schema = google_bigquery_table.customer_raw.schema
}

# -------------------
# Transaction Raw Table (all NULLABLE - for initial load)
# -------------------
resource "google_bigquery_table" "transaction_raw" {
  dataset_id          = google_bigquery_dataset.raw_data_dataset.dataset_id
  table_id            = "transaction_raw"
  deletion_protection = false

  schema = <<EOF
[
  {"name": "transaction_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "customer_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "amount", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "transaction_ts", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "ingestion_time", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "file_name", "type": "STRING", "mode": "NULLABLE"}
]
EOF
}

# -------------------
# Transaction Staging Table (clean - REQUIRED IDs)
# -------------------
resource "google_bigquery_table" "transaction_staging" {
  dataset_id          = google_bigquery_dataset.raw_data_dataset.dataset_id
  table_id            = "transaction_staging"
  deletion_protection = false

  schema = <<EOF
[
  {"name": "transaction_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "customer_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "amount", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "transaction_ts", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF

  time_partitioning {
    type  = "MONTH"
    field = "transaction_ts"
  }

  clustering = ["customer_id"]
}

# -------------------
# Transaction Dead Letter Table
# -------------------
resource "google_bigquery_table" "transaction_deadletter" {
  dataset_id          = google_bigquery_dataset.raw_data_dataset.dataset_id
  table_id            = "transaction_staging_deadletter"
  deletion_protection = false

  schema = google_bigquery_table.transaction_raw.schema
}

# -------------------
# Analytics Layer
# -------------------
resource "google_bigquery_table" "monthly_spend_per_customer_mv" {
  dataset_id = google_bigquery_dataset.raw_data_dataset.dataset_id
  table_id   = "monthly_spend_per_customer_mv"
  deletion_protection = false
  materialized_view {
    query = <<EOF
      SELECT customer_id, DATE_TRUNC(transaction_ts, MONTH) AS month, SUM(amount) AS total_monthly_spend, AVG(amount) AS avg_monthly_spend
      FROM ${google_bigquery_dataset.raw_data_dataset.dataset_id}.${google_bigquery_table.transaction_staging.table_id}
      GROUP BY customer_id, month
    EOF
    enable_refresh = false
  }
  time_partitioning {
    type = "MONTH"
    field = "month"
  }
  clustering = ["customer_id"]
}

resource "google_bigquery_table" "customer_lifetime_value_mv" {
  dataset_id = google_bigquery_dataset.raw_data_dataset.dataset_id
  table_id   = "customer_lifetime_value_mv"
  deletion_protection = false
  materialized_view {
    query = <<EOF
      SELECT customer_id, SUM(amount) AS lifetime_value
      FROM ${google_bigquery_dataset.raw_data_dataset.dataset_id}.${google_bigquery_table.transaction_staging.table_id}
      GROUP BY customer_id
    EOF
    enable_refresh = false
  }
  clustering = ["customer_id"]
}

resource "google_bigquery_table" "top_customers_ltv_v" {
  dataset_id = google_bigquery_dataset.raw_data_dataset.dataset_id
  table_id   = "top_customers_ltv_v"
  deletion_protection = false

  view {
    query = <<EOF
    SELECT customer_id, lifetime_value
    FROM (
      SELECT customer_id, lifetime_value,
             PERCENT_RANK() OVER (ORDER BY lifetime_value DESC) AS percentile_rank
      FROM ${google_bigquery_dataset.raw_data_dataset.dataset_id}.${google_bigquery_table.customer_lifetime_value_mv.table_id}
    )
    WHERE percentile_rank <= 0.05
    EOF
    use_legacy_sql = false
  }
}

# -------------------
# Enable dataflow
# -------------------
resource "google_project_service" "dataflow" {
  project            = var.project_id
  service            = "dataflow.googleapis.com"
  disable_on_destroy = false
}
