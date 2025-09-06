variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "our-card-283408" # Change if you deploy to a different project
}

variable "region" {
  description = "The Google Cloud region to deploy resources in"
  type        = string
  default     = "europe-west2"
}

variable "raw_data_bucket_name" {
  description = "The name suffix for the GCS bucket to store raw data"
  type        = string
  default     = "raw-data-bucket"
}

variable "dataflow_temp_bucket_name" {
  description = "The name suffix for the GCS bucket used for Dataflow temporary storage"
  type        = string
  default     = "dataflow-temp-bucket"
}

variable "dataset_id" {
  description = "The ID for the BigQuery dataset where data will be stored"
  type        = string
  default     = "raw_data_dataset"
}

variable "customer_lifetime_value_mv_id" {
  description = "The ID for the customer lifetime value materialized view"
  type        = string
  default     = "customer_lifetime_value_mv"
}

variable "top_customers_ltv_v_id" {
  description = "The ID for the top customers LTV view"
  type        = string
  default     = "top_customers_ltv_v"
}