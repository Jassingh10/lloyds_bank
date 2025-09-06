# :package: Lloyds Bank Data Platform — Customer Transactions Pipeline
## :page_facing_up: Overview
This project implements a **fully automated ETL data pipeline** for ingesting **customer** and **transaction** data from CSV files stored in Google Cloud Storage (GCS) into **Google BigQuery** for analytics.
It uses:
- **Terraform** for provisioning infrastructure (GCS buckets, BigQuery datasets/tables)
- **Apache Beam (DataflowRunner)** for scalable ingestion from CSV → BigQuery raw tables
- **SQL MERGE** for staging, deduplication, and data validation
- **Deadletter tables** for invalid records
- **Materialized views** for reusable analytics
- **A single shell script (pipeline.sh)** to orchestrate the whole workflow
---
## :hammer_and_wrench: Architecture
**Flow Summary:**
1. **Terraform** provisions:
   - Raw data GCS bucket
   - Dataflow temp/staging bucket
   - BigQuery datasets & tables (raw, staging, deadletter)
2. **Raw CSV Upload** — Local CSVs in /data are uploaded to the raw GCS bucket.
3. **Apache Beam Ingestion**:
   - Reads customers_*.csv and transactions_*.csv from GCS
   - Writes them into **raw tables** in BigQuery with ingestion time and file name
4. **BigQuery SQL Processing**:
   - MERGE raw → staging tables
   - Validate records (based on required fields)
   - Insert invalid records into _deadletter tables
5. **Materialized Views**:
   - **Monthly spend per customer**
   - **Customer lifetime value**
   - A **standard view** to return only the **top 5% customers** by LTV
6. **Trigger** — pipeline.sh runs everything end-to-end.
---
## :open_file_folder: Project Structure
lloylds_bank/
│
├── ingest_pipeline.py        # Apache Beam CSV → BigQuery pipeline
├── pipeline.sh               # Orchestrates Terraform, GCS upload, Dataflow ingestion, BQ merges, MV refresh
├── terraform/                # Terraform IaC for infra
│   ├── main.tf
│   ├── outputs.tf
│   ├── variables.tf
├── data/                     # Raw CSV files
│   ├── customers_*.csv
│   ├── transactions_*.csv
├── test/                     # Pytest suite (mocked, offline)
│   ├── test_pipelines.py
│   └── README.md
├── pytest.ini                # Pytest configuration (coverage, paths)
├── test_runner.sh             # Runs tests with coverage
├── README.md                  # This document
---
## :bar_chart: Data Model
### **Source CSVs**
- **Customers**
  - customer_id (STRING, required)
  - first_name (STRING)
  - last_name (STRING)
  - email (STRING)
  - creation_date (TIMESTAMP)
- **Transactions**
  - transaction_id (STRING, required)
  - customer_id (STRING, required)
  - amount (FLOAT)
  - transaction_ts (TIMESTAMP)
---
### **Raw Tables**
These store all ingested rows **exactly as read** from CSV (plus ingestion metadata).
Example: 
PROJECT_ID.raw_data_dataset.customer_raw
Columns include:
- All CSV columns
- file_name (STRING)
- ingestion_time (TIMESTAMP)
---
### **Staging Tables**
Contain **latest valid records**. Populated via MERGE from raw tables:
- Update existing if newer
- Insert new customers/transactions
---
### **Deadletter Tables**
Contain **invalid records** from ingestion e.g. missing customer_id or transaction_id.
---
### **Materialized Views**
1. **monthly_spend_per_customer_mv** — total and average monthly spend per customer.
2. **customer_lifetime_value_mv** — total lifetime value per customer.
3. **top_5_percent_customers** (standard view) — filters lifetime value MV down to top 5%.
---
### :one: Transaction Staging Table
hcl
time_partitioning {
  type  = "MONTH"
  field = "transaction_ts"
}

clustering = ["customer_id"]
**Why it helps:**
- **Monthly time partitioning on transaction_ts** 
  Your downstream queries filter, group, or aggregate by month (e.g., monthly spend). Partitioning means BigQuery only scans the relevant month’s data, reducing scanned data size and speeding up queries.
- **Clustering on customer_id** 
  Queries like:
  
sql
  GROUP BY customer_id, month
  
  benefit because clustering stores rows with the same customer_id physically close together within each monthly partition. This reduces the amount of data read when querying for specific customers or doing group-by aggregations.
---
### :two: monthly_spend_per_customer_mv
hcl
time_partitioning {
  type = "MONTH"
  field = "month"
}
clustering = ["customer_id"]
**Why:**
- This MV computes **totals and averages per month per customer**. 
  - Partitioning by month allows fast refresh and queries for specific date ranges.
  - Clustering by customer_id accelerates per-customer lookups or sub-group aggregations in BI tools.
---
### :three: customer_lifetime_value_mv
hcl
clustering = ["customer_id"]
**Why:**
- This MV aggregates SUM(amount) per customer across all time. 
  - Clustering by customer_id makes queries like top N customers more efficient because BigQuery can process grouped customer blocks faster.
  - It also speeds up joins with other customer-dimension tables.
---
### :rocket: Overall performance impact
Your queries:
- **View total and average monthly spend per customer** 
  → Benefit from time partitioning (limit to relevant months) + clustering on customer_id (fast group-by).
- **Identify top 5% customers by LTV** 
  → Benefit from clustering on customer_id in the LTV MV (efficient grouping/sorting).
**Benefits:**
- :moneybag: Lower cost (less data scanned)
- :zap: Faster query performance
- :arrows_counterclockwise: Faster materialized view refresh times, since only new/changed partitions are recomputed.
## :bar_chart: Partitioning & Clustering Benefits
Partitioning and clustering make our BigQuery queries **cheaper** and **faster** because BigQuery can **prune** (skip) unnecessary data during query execution.
---
### :one: Without Partitioning (full table scan)
If we query the last month’s transactions without partitioning:
sql
EXPLAIN
SELECT customer_id, SUM(amount) AS total_spend
FROM `PROJECT_ID.raw_data_dataset.transaction_staging`
WHERE transaction_ts BETWEEN '2024-06-01' AND '2024-06-30'
GROUP BY customer_id;
Without partitions, BigQuery will **scan the entire table** even if you only filter on one month. 
Example scanned data: **5 GB** (hypothetical).
---
### :two: With Monthly Time Partitioning
Because transaction_staging is **partitioned by transaction_ts** in your Terraform:
sql
EXPLAIN
SELECT customer_id, SUM(amount) AS total_spend
FROM `PROJECT_ID.raw_data_dataset.transaction_staging`
WHERE transaction_ts BETWEEN '2024-06-01' AND '2024-06-30'
GROUP BY customer_id;
Now, BigQuery scans **only the June partition**, skipping all others. 
Example scanned data: **300 MB** (94% less than above).
---
### :three: Clustering on customer_id
For a query on a specific customer or small subset:
sql
EXPLAIN
SELECT *
FROM `PROJECT_ID.raw_data_dataset.transaction_staging`
WHERE customer_id = 'CUST_123';
Because of clustering by customer_id, BigQuery can jump to the specific cluster instead of scanning all rows in the partition.
- Without clustering: scans **300 MB**
- With clustering: scans **a few MB** for the indexed block
---
### :rocket: Summary of Gains
| Optimization                     | Scenario                           | Benefit                                      |
|-----------------------------------|-------------------------------------|----------------------------------------------|
| Monthly Partitioning              | Time range queries                  | Skip irrelevant months → less data scanned   |
| Clustering by customer_id         | Single-customer lookups & group-bys | Jump directly to relevant blocks of storage  |
| Partition + Clustering together   | Both time & customer filters        | Maximum scan reduction                       |
---