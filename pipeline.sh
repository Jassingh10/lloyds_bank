#!/bin/bash

set -e

# Define log function
log() {
  echo "$(date) - $1"
}

# Define error handling function
handle_error() {
  log "Error occurred: $1"
  exit 1
}

PROJECT_ID="our-card-283408"
REGION="europe-west2"

# log "Starting ETL process..."

# Deploy Terraform infra
cd terraform
log "Deploying Terraform infra..."
terraform init || handle_error "Terraform init failed"
terraform apply -auto-approve \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" || handle_error "Terraform apply failed"

RAW_BUCKET=$(terraform output -raw raw_data_bucket_name)
TEMP_BUCKET=$(terraform output -raw dataflow_temp_bucket_name)
CUSTOMER_RAW="${PROJECT_ID}.raw_data_dataset.customer_raw"
CUSTOMER_STAGING="${PROJECT_ID}.raw_data_dataset.customer_staging"
TRANSACTION_RAW="${PROJECT_ID}.raw_data_dataset.transaction_raw"
TRANSACTION_STAGING="${PROJECT_ID}.raw_data_dataset.transaction_staging"
MONTHLY_SPEND_PER_CUSTOMER="${PROJECT_ID}.raw_data_dataset.monthly_spend_per_customer_mv"
CUSTOMER_LIFETIME_VALUE="${PROJECT_ID}.raw_data_dataset.customer_lifetime_value_mv"

cd ..

# Upload CSVs
log ":outbox_tray: Uploading CSV files..."
gsutil cp data/customers_*.csv gs://${RAW_BUCKET}/ || handle_error "Failed to upload customers.csv"
gsutil cp data/transactions_*.csv gs://${RAW_BUCKET}/ || handle_error "Failed to upload transactions.csv"

# Ingest CUSTOMER CSV to RAW
log "Ingesting CUSTOMER CSV to RAW..."
for file in $(gsutil ls gs://${RAW_BUCKET}/customers_*.csv); do
  file_name=$(basename $file)
  job_name="customer-ingestion-job-${file_name//.csv/}"
  job_name=${job_name//_/-}
  python3 ingest_pipeline.py \
    --input $file \
    --raw_table ${CUSTOMER_RAW} \
    --schema "customer_id:STRING,first_name:STRING,last_name:STRING,email:STRING,creation_date:TIMESTAMP" \
    --runner DataflowRunner \
    --project ${PROJECT_ID} \
    --region ${REGION} \
    --job_name ${job_name} \
    --staging_location gs://${TEMP_BUCKET}/staging/ \
    --temp_location gs://${TEMP_BUCKET}/temp/
done

# Ingest TRANSACTION CSV to RAW
log "Ingesting TRANSACTION CSV to RAW..."
for file in $(gsutil ls gs://${RAW_BUCKET}/transactions_*.csv); do
  file_name=$(basename $file)
  job_name="transaction-ingestion-job-${file_name//.csv/}"
  job_name=${job_name//_/-}
  python3 ingest_pipeline.py \
    --input $file \
    --raw_table ${TRANSACTION_RAW} \
    --schema "transaction_id:STRING,customer_id:STRING,amount:FLOAT,transaction_ts:TIMESTAMP" \
    --runner DataflowRunner \
    --project ${PROJECT_ID} \
    --region ${REGION} \
    --job_name ${job_name} \
    --staging_location gs://${TEMP_BUCKET}/staging/ \
    --temp_location gs://${TEMP_BUCKET}/temp/
done
# sleep 30

# TRANSACTION_JOB_ID=$(gcloud dataflow jobs list --project ${PROJECT_ID} --region ${REGION} --status=active --format="get(id)" --filter="name:transaction-ingestion-job" --limit=1)

# if [ -z "${TRANSACTION_JOB_ID}" ]; then
#   handle_error "Failed to get job ID for transaction-ingestion-job"
# fi

# while true; do
#   JOB_STATUS=$(gcloud dataflow jobs describe ${TRANSACTION_JOB_ID} --project ${PROJECT_ID} --region ${REGION} --format="get(state)")
#   if [ "${JOB_STATUS}" == "JOB_STATE_DONE" ]; then
#     break
#   elif [ "${JOB_STATUS}" == "JOB_STATE_FAILED" ] || [ "${JOB_STATUS}" == "JOB_STATE_CANCELLED" ]; then
#     handle_error "Dataflow job ${TRANSACTION_JOB_ID} failed with status ${JOB_STATUS}"
#   fi
#   sleep 30
# done

# CUSTOMER: Update existing records and insert new records and Insert invalid records into deadletter table
log "Processing CUSTOMER data..."
bq query --use_legacy_sql=false "
DECLARE max_filename STRING;
SET max_filename = (
  SELECT file_name
  FROM \`${CUSTOMER_RAW}\`
  WHERE ingestion_time = (
    SELECT MAX(ingestion_time)
    FROM \`${CUSTOMER_RAW}\`
  )
);

MERGE \`${CUSTOMER_STAGING}\` AS target
USING (
  SELECT * EXCEPT(category)
  FROM (
    SELECT *, IF(customer_id IS NOT NULL AND TRIM(customer_id) != '', 'valid', 'invalid') AS category
    FROM \`${CUSTOMER_RAW}\`
    WHERE file_name = max_filename
  )
  WHERE category = 'valid'
) AS source
ON target.customer_id = source.customer_id
WHEN MATCHED AND target.creation_date < source.creation_date THEN
  UPDATE SET first_name = source.first_name, last_name = source.last_name, email = source.email, creation_date = source.creation_date
WHEN NOT MATCHED THEN
  INSERT (customer_id, first_name, last_name, email, creation_date)
  VALUES (source.customer_id, source.first_name, source.last_name, source.email, source.creation_date);

INSERT INTO \`${CUSTOMER_STAGING}_deadletter\`
SELECT * EXCEPT(category)
FROM (
  SELECT *, IF(customer_id IS NOT NULL AND TRIM(customer_id) != '', 'valid', 'invalid') AS category
  FROM \`${CUSTOMER_RAW}\`
  WHERE file_name = max_filename
)
WHERE category = 'invalid';
" || handle_error "Failed to process CUSTOMER data"


# -- TRANSACTION: Update existing records and insert new records and Insert invalid records into deadletter table
log "Processing TRANSACTION data..."

bq query --use_legacy_sql=false "
  DECLARE max_filename STRING;
  SET max_filename = (
    SELECT file_name
    FROM \`${TRANSACTION_RAW}\`
    WHERE ingestion_time = (
      SELECT MAX(ingestion_time)
      FROM \`${TRANSACTION_RAW}\`
    )
  );

  -- Merge valid transactions into staging table
  MERGE \`${TRANSACTION_STAGING}\` AS target
  USING (
    SELECT * EXCEPT(category)
    FROM (
      SELECT *, 
             IF((transaction_id IS NOT NULL AND TRIM(transaction_id) != '') 
                AND (customer_id IS NOT NULL AND TRIM(customer_id) != ''), 
                'valid', 'invalid') AS category
      FROM \`${TRANSACTION_RAW}\`
      WHERE file_name = max_filename
    )
    WHERE category = 'valid'
  ) AS source
  ON target.transaction_id = source.transaction_id
  WHEN MATCHED AND target.transaction_ts < source.transaction_ts THEN
    UPDATE SET 
      customer_id = source.customer_id, 
      amount = source.amount, 
      transaction_ts = source.transaction_ts
  WHEN NOT MATCHED THEN
    INSERT (transaction_id, customer_id, amount, transaction_ts)
    VALUES (source.transaction_id, source.customer_id, source.amount, source.transaction_ts);

  -- Insert invalid transactions into deadletter table
  INSERT INTO \`${TRANSACTION_STAGING}_deadletter\`
  SELECT * EXCEPT(category)
  FROM (
    SELECT *, 
           IF((transaction_id IS NOT NULL AND TRIM(transaction_id) != '') 
              AND (customer_id IS NOT NULL AND TRIM(customer_id) != ''), 
              'valid', 'invalid') AS category
    FROM \`${TRANSACTION_RAW}\`
    WHERE file_name = max_filename
  )
  WHERE category = 'invalid';
" || handle_error "Failed to process TRANSACTION data"

# Refresh Materialized Views
log ":arrows_counterclockwise: Refreshing Materialized Views..."

bq query --use_legacy_sql=false --location=europe-west2 "CALL BQ.REFRESH_MATERIALIZED_VIEW('${MONTHLY_SPEND_PER_CUSTOMER}')" || handle_error "Failed to refresh ${MONTHLY_SPEND_PER_CUSTOMER}"
bq query --use_legacy_sql=false --location=europe-west2 "CALL BQ.REFRESH_MATERIALIZED_VIEW('${CUSTOMER_LIFETIME_VALUE}')" || handle_error "Failed to refresh ${CUSTOMER_LIFETIME_VALUE}"

log ": ETL complete. Check data in BigQuery."