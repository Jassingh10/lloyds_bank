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
## **:arrows_counterclockwise: Updated Automated Flow**
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