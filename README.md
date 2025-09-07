# Lloyds Bank Data Ingestion Pipeline
## Table of Contents
- [Overview](#overview) 
- [Features](#features) 
- [Requirements](#requirements) 
- [Setup](#setup) 
- [Architecture](#architecture) 
- [Terraform](#terraform) 
- [Usage](#usage) 
- [Pipeline Steps](#pipeline-steps) 
- [Error Handling](#error-handling) 
- [ETL Script Details](#etl-script-details) 
- [Contributing](#contributing) 
- [License](#license) 
---
## Overview
This project implements a **data ingestion pipeline** to load CSV data from **local storage** into **Google Cloud Storage (GCS)** and subsequently process and load it into **BigQuery** using **Dataflow (Apache Beam)**.

Local CSV Files
   │
   ▼  Upload
Google Cloud Storage (GCS)
   │
   ▼  Process
Dataflow (Apache Beam)
   │
   ▼  Load
BigQuery Raw Tables
   │
   ▼  Transform & Clean
BigQuery Staging Tables
   │
   ▼  Aggregate/Analyze
BigQuery Materialized Views

---
## Features
- Bulk loads CSV files from local storage to GCS
- Processes files using Dataflow with Apache Beam
- Loads clean data into BigQuery staging tables
- Supports an analytics layer via materialized views
- Includes error and logging framework
---
## Requirements
- Google Cloud Platform account
- [Terraform](https://www.terraform.io/)
- [Apache Beam Python SDK](https://beam.apache.org/)
- Google Cloud SDK (gcloud)
- Python **3.9+**
---
## Setup
1. **Install dependencies**
   
bash
   pip install "apache-beam[gcp]" google-cloud-bigquery
   
2. **Set up a GCP project and enable APIs**
   - BigQuery
   - Cloud Storage
   - Dataflow
3. **Create a service account**
   - Grant necessary roles (roles/bigquery.admin, roles/dataflow.developer, roles/storage.admin)
   - Download the JSON key and set:
     
bash
     export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
     
---
## Architecture
**Flow:**
1. CSV data lands in local storage.
2. CSV is uploaded to **raw_data_bucket** in GCS.
3. Dataflow pipeline parses CSV and loads into **BigQuery raw tables** (all columns NULLABLE).
4. Transformations filter and insert into **staging tables** with stricter schemas (IDs REQUIRED).
5. Analytics layer materializes key metrics (e.g., monthly spend per customer, top customers by LTV).
**Note:** No Cloud Functions / Pub/Sub — ingestion is manually or scheduler-triggered.
---
## Terraform
Terraform is used to manage:
- GCS bucket creation
- BigQuery dataset and tables
- IAM roles for Dataflow and BigQuery
**Deploy:**
bash
cd terraform
terraform init
terraform apply -auto-approve -var="project_id=YOUR_PROJECT" -var="region=YOUR_REGION"
---
## Usage
bash
./pipeline.sh
This will:
1. Deploy infrastructure with Terraform.
2. Upload customer/transaction CSVs to GCS.
3. Run Dataflow job(s) to load into _raw tables.
4. Run BigQuery SQL to transform _raw → _staging, splitting invalid rows to _deadletter.
---
## Pipeline Steps
1. **Read CSV** from local folder.
2. **Upload to GCS** raw bucket.
3. **Dataflow CSV→Raw**: raw tables have all fields NULLABLE for fault tolerance.
4. **BigQuery Transform**: one-scan CTE filters valid rows into staging, invalid into dead-letter.
5. **Materialized Views** in analytics layer for key KPIs.
---
## Error Handling
- Logging to console for quick diagnosis.
---

## ETL Script Details
**Partitioning and Clustering:**
- **Monthly partitioning** by month column → reduces cost for time-filtered queries.
- **Clustering by customer_id** → speeds up queries filtered on customer.
- Ideal for time-based reporting + customer-level analysis.
**Triggering:**
- Manual ./pipeline.sh run or schedule via cron/Cloud Scheduler.
---

## Materialized Views
The following materialized views are created:
- monthly_spend_per_customer_mv: This materialized view calculates the total and average monthly spend per customer.
- customer_lifetime_value_mv: This materialized view calculates the lifetime value of each customer.

## Views
The following views are created:
- top_customers_ltv_v: This view identifies the top 5% of customers by lifetime value.



## PIPELINE.SH
---
**Script setup & helpers**
- set -e makes the script stop on any error.
- log() outputs a timestamped log message.
- handle_error() logs an error message and exits with a non‑zero code.
---
**Variables**
- Sets Project ID, Region.
- Logs “Starting ETL”.
- Paths for GCP resources (buckets, raw/staging/deadletter tables, materialized views) will be pulled from Terraform outputs later.
---
**Terraform deployment**
1. cd terraform
2. terraform init → initialise Terraform backend/plugins.
3. terraform apply → deploy infra for buckets, datasets, tables. 
   Uses -auto-approve and passes the project/region vars.
4. Saves key Terraform outputs into shell vars: raw bucket, temp bucket, table names.
---
**Upload CSVs**
- Copies data/customers_*.csv and data/transactions_*.csv from local data/ dir into the raw bucket in GCS using gsutil cp.
- If any copy fails, handle_error aborts the job.
---
**Ingest CSV → RAW tables (Dataflow)** 
Runs Apache Beam Python pipeline for **each CSV file** in the raw bucket:
- For customers:
  - Loops for file in gs://${RAW_BUCKET}/customers_*.csv.
  - Builds a Dataflow job name from the filename.
  - Runs python3 ingest_pipeline.py with:
    - --input pointing to that GCS file
    - --raw_table pointing to the BigQuery customer_raw table (all NULLABLE columns)
    - Schema for parsing
    - DataflowRunner + GCP options for staging/temp paths
- Same loop for transactions, targeting transaction_raw table.
---
**Find most recent batch**
- Queries BigQuery for MAX(ingestion_time) in both raw tables to find the latest load timestamp.
- If no records found, abort.
---
**Transform RAW → STAGING and Deadletter (BigQuery SQL)**
For each entity type:
- **Customer logic:**
  - Declares max_filename as the file name associated with the latest ingestion_time in customer_raw.
  - **MERGE** customer_staging with valid records from that file:
    - valid = non‑null, non‑empty customer_id
    - When matched and incoming creation_date is newer → update name/email/date.
    - When not matched → insert new record.
  - **INSERT** invalid records (category='invalid') into customer_staging_deadletter.
- **Transaction logic:**
  - Similar pattern: declare latest file, merge valid rows into staging (transaction_id and customer_id present, plus update if timestamp newer), and insert invalids into transaction_staging_deadletter.


need to add info about clustering  customer and partitioning by month this was done due to the requirments of analytic layer 
- monthly_spend_per_customer_mv: This materialized view calculates the total and average monthly spend per customer.
- customer_lifetime_value_mv: This materialized view calculates the lifetime value of each customer.

---
**Refresh materialized views**
- Calls BQ.REFRESH_MATERIALIZED_VIEW for monthly_spend_per_customer_mv and customer_lifetime_value_mv to update analytics layer.
---
**Final log**
- Logs ETL completion.
---
**In summary**:
1. Deploy infra.
2. Stage CSVs to GCS.
3. Load GCS CSVs into BigQuery “raw” tables via Dataflow pipelines.
4. Use BigQuery SQL MERGE/INSERT to split raw → staging/deadletter.
5. Refresh MV analytics.

##Improvements and assumptions

## **:dart: Current State**
- **Trigger:** Manual pipeline.sh execution
- **Flow:** Bash → Terraform infra → GCS upload → Beam pipeline → BQ staging/deadletter → manual MV refresh
- **Issues:** 
  - Manual run → prone to delays & human error 
  - Refresh logic not automatically tied to ingest completion 
---
## **:rocket: Target Architecture Improvements**
### :one: Event-Driven Trigger via Cloud Functions / Cloud Run

**Goal:** Stop manual execution when files land in GCS.

**Approach:**
- Set up a **GCS event notification** on the RAW_BUCKET (Object Finalize event).
- Use **Cloud Functions** to:
  - Parse object name (e.g. customers_*.csv vs transactions_*.csv)
  - Submit the Dataflow (Apache Beam) flex job with the correct params.

**Benefits:**
- **Real-time ingestion** (minutes from file drop to availability in BQ)
- Pay only when triggered

---
### :two: Infra-as-Code + Continuous Deployment for Terraform
- Integrate Terraform runs in CI/CD (GitHub Actions/Cloud Build)
  - Apply infra changes on merges to main
---

### :three: Automate BigQuery Staging Merge via Cloud Composer / Workflows
**Problem:** Right now, staged merges + MV refresh are executed in Bash after ingestion.
**Solution Paths:**
#### Option A — **Cloud Composer (Airflow)**
  - Has sensors/operators to monitor:
    - GCS file arrival 
    - Dataflow job completion
  - Then runs BigQueryOperator tasks:
    - MERGE raw → staging/deadletter
    - REFRESH_MATERIALIZED_VIEW for your reporting layer 
  - Great for flexible dependencies & retries
#### Option B — **GCP Workflows**
  - Light-weight YAML orchestration
  - Triggered by Pub/Sub from the ingestion function
  - Steps:
    1. Wait for Dataflow job completion
    2. Call BigQuery to run merge queries
    3. Refresh MVs
  - Lower cost & complexity than Composer
---
### :four: Automate MV Refresh / Incremental Logic
Materialized Views in BigQuery can:
- **Auto-refresh** (if supported & cheap for your volumes)
- Or use workflow/composer to refresh **only the impacted partition**
- Use table partition filters (WHERE month = ...) in MV definition for performance
---
### :five: Monitoring & Alerting
Add **end-to-end observability**:
- Dataflow job monitoring with Stackdriver alerts on FAILED status
- Cloud Logging metrics for failed merges or deadletter growth
- Optional:
  - **Deadletter dashboard**
  - Alert if >X% of batch goes to deadletter
---
## **:arrows_counterclockwise: Updated Automated Flow if Beam was required**
[Raw CSV lands in GCS]
      |
      v
[GCS Event Notification]
      |
      v
[Pub/Sub topic]
      |
      v
[Cloud Function / Cloud Run]
      |
 triggers Dataflow job (Beam ingestion)
      |
      v
[Dataflow → BQ Raw Tables]
      |
      v
[Composer DAG / Workflow]
   • Run MERGE raw → staging/deadletter
   • Refresh Materialized Views
      |
      v
[Analytical Layer Updated]
---
## **:bulb: Recommended Next Steps**
1. **Separate infra from data logic**
   - Terraform apply happens only in CI/CD for infra changes
2. **Replace bash trigger with GCS-triggered Cloud Function**
   - Handles Dataflow job submit
3. **Move staging + MV refresh to Composer DAG**
   - Trigger DAG when Dataflow → Raw BQ table data lands
4. **Add tests for orchestration logic**
- Unit test function parses filenames & sends correct job args
5. **Add alerting**
   - Failed Dataflow → PagerDuty/Slack
   - Too many deadletters → Slack report
---
## **:arrows_counterclockwise: My Preffered approach remove beam and have composer deal woith eveything **
[Raw CSV lands in GCS]
      |
      v
[Composer checks landing bucket]
      |
      v
[Python code in composer to use name of file against config file]
      |
      v
[Trigger → BQ Raw Tables]
      |
      v
[Composer DAG]
   • Run MERGE raw → staging/deadletter
   • Refresh Materialized Views
      |
      v
[Analytical Layer Updated]
---

The following assumptions have been made in designing, building, and running this pipeline:
1. **Source Data**
   - Raw CSV files arriving in the GCS RAW_BUCKET is a daily file: