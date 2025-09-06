import pytest
import pytest
pytestmark = pytest.mark.unit
from unittest import mock

@pytest.fixture(autouse=True)
def mock_gcp_services():
    """Auto-mock BigQuery and GCS so no real GCP calls happen."""
    with mock.patch("ingest_pipeline.bigquery.Client") as mock_bq_client, \
         mock.patch("ingest_pipeline.beam.io.gcp.gcsfilesystem.GCSFileSystem.exists", return_value=True) as mock_gcs_exists:
        yield mock_bq_client, mock_gcs_exists