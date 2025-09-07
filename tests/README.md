## :test_tube: Testing Strategy
This project has **two distinct test types**:
### :one: Unit Tests
- **Location:** tests/unit_offline/
- **Purpose:** 
  - Test only our pipeline’s logic and helpers (parse_csv_line, run(), etc.).
  - All Google Cloud services (BigQuery, GCS, Dataflow) are **mocked**.
- **Benefits:** 
  - Fast — run in seconds 
  - Offline — no internet or GCP required 
  - Runs in **all environments** (local, CI/CD, forks, PRs)
- **Run locally:** 
  
bash
  pytest -m unit --cov=ingest_pipeline --cov-report=term-missing
  
- **Run in CI:** 
  Always runs on every push/PR — this is our main quality gate.
---
### :two: Integration Tests
- **Location:** tests/integration/
- **Purpose:** 
  - Run full **Apache Beam → BigQuery** ingestion paths end-to-end in a **real GCP environment**.
  - Upload test CSVs to GCS and verify rows appear in BigQuery.
  - Validate schema, transformations, and Dataflow execution.
- **Requirements:** 
  - GCP project with required APIs enabled (BigQuery, Storage, Dataflow)
  - Raw & temp buckets available
  - Service account key with roles:
    - roles/bigquery.admin
    - roles/storage.admin
    - roles/dataflow.admin
  - Locally: 
    
bash
    gcloud auth application-default login
    export PROJECT_ID=<project-id>
    export RAW_BUCKET=<bucket>
    export TEMP_BUCKET=<bucket>
    
- **Run locally:** 
  
bash
  pytest -m integration
  
- **Run in CI/CD:** 
  :x: Not run as part of the main CI pipeline. 
  :white_check_mark: Run manually via a dedicated **Integration Workflow** or locally with credentials.
---
## :vertical_traffic_light: CI/CD Policy
- The **main CI pipeline** (.github/workflows/ci.yml) runs **only unit tests**:
  - Keeps builds **fast** 
  - Avoids GCP dependency & credentials in every run 
  - Prevents accidental costs & flaky cloud test failures
- **Integration tests** are run:
  - Manually (workflow_dispatch) in GitHub Actions **when needed**
  - Locally by engineers before major releases or changes in GCP-specific code.
---
## :bulb: Why This Approach
- **Fast feedback:** Unit tests run on every commit — developers get results in minutes.
- **Reliability:** CI builds won’t fail from GCP network/auth issues.
- **Security:** GCP credentials aren’t stored/exposed in every CI job.
- **Flexibility:** Integration tests can still be run whenever real GCP validation is needed.
---