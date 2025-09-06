**real GCP Beam → BigQuery** tests.
---
## :test_tube: Running Integration Tests (Real GCP)
Our integration tests in tests/integration/test_pipeline_gcp.py run the **actual** ingestion pipeline (ingest_pipeline.py) against Google Cloud Platform:
- Uploads **test CSVs** to your Raw GCS bucket.
- Runs **Apache Beam** (DirectRunner or DataflowRunner).
- Writes to **BigQuery** tables in your dataset.
- Asserts that data is correctly ingested.
### :warning: Prerequisites
You must have the following **ready** in your GCP project:
1. **GCP Project** with:
   - BigQuery, Dataflow, and Cloud Storage APIs enabled.
2. **GCS buckets**:
   - Raw data bucket (RAW_BUCKET)
   - Temp bucket (TEMP_BUCKET) for Beam temporary files.
3. **BigQuery dataset** — default is raw_data_dataset (can override using BQ_DATASET env var).
4. **Service account / ADC**:
   - With roles: roles/bigquery.admin, roles/storage.admin, roles/dataflow.admin
   - Locally: run 
     
bash
     gcloud auth application-default login
     
     This updates your local ADC to be used by the BigQuery & Storage clients.
---
### :small_blue_diamond: Setting Required Environment Variables
Before running, export these environment variables:
bash
export PROJECT_ID="your-gcp-project-id"
export REGION="europe-west2"                    # or your GCP region
export RAW_BUCKET="your-raw-data-bucket"        # without gs:// prefix
export TEMP_BUCKET="your-temp-bucket"           # without gs:// prefix
# Optional:
# export BQ_DATASET="raw_data_dataset"
---
### :small_blue_diamond: Running Integration Tests Locally
**Run all integration tests only:**
bash
pytest -m integration
**Run both unit & integration tests together:**
bash
pytest -m "unit or integration"
---
### :small_blue_diamond: Running via Helper Script
We have a convenience script run_integration_test.sh to ensure the right Python is used:
bash
chmod +x run_integration_test.sh
./run_integration_test.sh
This will:
1. Install dependencies
2. Run only the @pytest.mark.integration tests
---
### :small_blue_diamond: Expected Behaviour
- A **random BigQuery table name** is created for each integration test (no data collisions).
- After tests run, you should see:
  - A customer_raw_inttest_* table populated from the customer CSV upload
  - A transaction_raw_inttest_* table populated from the transaction CSV upload
- Tests will **skip automatically** if any required env var is missing.
---
### :small_blue_diamond: In CI/CD
We **do not** run integration tests on every push unless GCP credentials are present. 
Configure the following secrets in your GitHub repository to enable:
- GCP_SA_KEY — Service account JSON key
- GCP_PROJECT_ID
- GCP_REGION
- GCP_RAW_BUCKET
- GCP_TEMP_BUCKET
---