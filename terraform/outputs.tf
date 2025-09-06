output "raw_data_bucket_name" {
  description = "Raw data GCS bucket name"
  value       = google_storage_bucket.raw_data_bucket.name
}

output "dataflow_temp_bucket_name" {
  description = "GCS bucket for Dataflow temporary storage"
  value       = google_storage_bucket.dataflow_temp_bucket.name
}

output "customer_staging_table_fqn" {
  description = "Fully qualified name for the customer staging table"
  value       = "${var.project_id}:${google_bigquery_dataset.raw_data_dataset.dataset_id}.${google_bigquery_table.customer_staging.table_id}"
}

output "transaction_staging_table_fqn" {
  description = "Fully qualified name for the transaction staging table"
  value       = "${var.project_id}:${google_bigquery_dataset.raw_data_dataset.dataset_id}.${google_bigquery_table.transaction_staging.table_id}"
}

output "customer_lifetime_value_mv_fqn" {
  description = "Fully qualified name for the customer lifetime value materialized view"
  value       = "${var.project_id}:${google_bigquery_dataset.raw_data_dataset.dataset_id}.${google_bigquery_table.customer_lifetime_value_mv.table_id}"
}

output "top_customers_ltv_v_fqn" {
  description = "Fully qualified name for the top customers LTV view"
  value       = "${var.project_id}:${google_bigquery_dataset.raw_data_dataset.dataset_id}.${google_bigquery_table.top_customers_ltv_v.table_id}"
}