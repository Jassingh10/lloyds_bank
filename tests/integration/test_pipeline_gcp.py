import os
import uuid
import datetime
from google.cloud import bigquery
import pytest
import ingest_pipeline as pipeline_script
pytestmark = pytest.mark.integration  # mark all tests here as integration
# Pull required config from environment
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION", "europe-west2")
RAW_BUCKET = os.environ.get("RAW_BUCKET")
TEMP_BUCKET = os.environ.get("TEMP_BUCKET")
DATASET_ID = os.environ.get("BQ_DATASET", "raw_data_dataset")
# Fail early if required env vars are missing
REQUIRED_VARS = ["PROJECT_ID", "RAW_BUCKET", "TEMP_BUCKET"]
for var in REQUIRED_VARS:
    if not os.environ.get(var):
        pytest.skip(
            f"Skipping integration tests — missing env var: {var}",
            allow_module_level=True
        )
def _bq_client():
    return bigquery.Client(project=PROJECT_ID)
def _random_table_name(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
def _upload_test_csv(bucket_name, blob_name, content):
    """Upload a small CSV file to GCS."""
    from google.cloud import storage
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(content, content_type="text/csv")
    return f"gs://{bucket_name}/{blob_name}"
def test_pipeline_ingests_to_bq():
    """Runs ingest_pipeline.py on a real GCS CSV and checks BigQuery table contents."""
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{_random_table_name('customer_raw_inttest')}"
    # Small test CSV content
    csv_content = (
        "customer_id,first_name,last_name,email,creation_date\n"
        "cust_001,John,Doe,john@example.com,2024-06-02T12:00:00Z\n"
    )
    # Upload CSV to raw GCS bucket
    blob_name = f"inttests/customers_{uuid.uuid4().hex[:6]}.csv"
    input_gcs_path = _upload_test_csv(RAW_BUCKET, blob_name, csv_content)
    # Run the pipeline
    argv = [
        "--input", input_gcs_path,
        "--raw_table", table_id,
        "--schema", "customer_id:STRING,first_name:STRING,last_name:STRING,email:STRING,creation_date:TIMESTAMP",
        "--runner", "DirectRunner",
        "--project", PROJECT_ID,
        "--region", REGION,
        "--temp_location", f"gs://{TEMP_BUCKET}/temp"
    ]
    pipeline_script.run(argv)
    # Query BQ to see if row arrived
    client = _bq_client()
    query = f"SELECT customer_id, first_name FROM {table_id}"
    rows = list(client.query(query))
    assert len(rows) == 1
    assert rows[0].customer_id == "cust_001"
    assert rows[0].first_name == "John"
def test_transactions_pipeline_ingests_to_bq():
    """Runs ingest_pipeline.py for a transaction file and checks BigQuery table contents."""
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{_random_table_name('transaction_raw_inttest')}"
    csv_content = (
        "transaction_id,customer_id,amount,transaction_ts\n"
        f"txn_{uuid.uuid4().hex[:4]},cust_001,99.99,{datetime.datetime.utcnow().isoformat()}\n"
    )
    blob_name = f"inttests/transactions_{uuid.uuid4().hex[:6]}.csv"
    input_gcs_path = _upload_test_csv(RAW_BUCKET, blob_name, csv_content)
    argv = [
        "--input", input_gcs_path,
        "--raw_table", table_id,
        "--schema", "transaction_id:STRING,customer_id:STRING,amount:FLOAT,transaction_ts:TIMESTAMP",
        "--runner", "DirectRunner",
        "--project", PROJECT_ID,
        "--region", REGION,
        "--temp_location", f"gs://{TEMP_BUCKET}/temp"
    ]
    pipeline_script.run(argv)
    # Query BQ to see row arrived
    client = _bq_client()
    query = f"SELECT amount FROM {table_id}"
    rows = list(client.query(query))
    assert len(rows) == 1