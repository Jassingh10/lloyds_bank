import pytest
from unittest import mock

@pytest.fixture(autouse=True)
def mock_gcp_services():
    """
    Automatically mock GCP BigQuery and GCS for all tests.
    Prevents real API calls and avoids ADC lookup failures.
    """
    with mock.patch("ingest_pipeline.bigquery.Client") as mock_bq_client, \
         mock.patch("ingest_pipeline.beam.io.gcp.gcsfilesystem.GCSFileSystem.exists", return_value=True) as mock_gcs_exists:
        yield mock_bq_client, mock_gcs_exists