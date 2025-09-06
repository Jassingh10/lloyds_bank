import sys
import os
import pytest
import datetime
from unittest import mock
from google.cloud.exceptions import NotFound

# Ensure repo root is in sys.path for module imports
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import ingest_pipeline as pipeline_script


def test_parse_csv_line():
    schema = ["id", "name", "date"]
    result = pipeline_script.parse_csv_line("1,John,2024-06-02", schema)
    assert result == {"id": "1", "name": "John", "date": "2024-06-02"}


def test_add_ingestion_time():
    element = {"id": "1"}
    result = pipeline_script.add_ingestion_time(element.copy())
    assert "ingestion_time" in result
    assert isinstance(result["ingestion_time"], datetime.datetime)


def test_add_file_name(tmp_path):
    tmp_file = tmp_path / "test.csv"
    tmp_file.write_text("data")
    element = {"id": "1"}
    result = pipeline_script.add_file_name(element.copy(), str(tmp_file))
    assert result["file_name"] == "test.csv"


def test_check_table_exists_true():
    mock_client = mock.Mock()
    mock_client.get_table.return_value = True
    assert pipeline_script.check_table_exists(mock_client, "project.dataset.table")


def test_check_table_exists_false():
    mock_client = mock.Mock()
    mock_client.get_table.side_effect = NotFound("not found")
    assert not pipeline_script.check_table_exists(mock_client, "project.dataset.table")

def test_run_local_file_missing(monkeypatch, caplog):
    argv = [
        "--input", "missing.csv",
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    caplog.set_level("ERROR")
    pipeline_script.run(argv)
    assert "does not exist" in caplog.text


@mock.patch("ingest_pipeline.bigquery.Client")
@mock.patch("ingest_pipeline.check_table_exists")
@mock.patch("ingest_pipeline.create_pipeline")
def test_run_local_file_exists(mock_create_pipeline, mock_check_table, mock_bq_client, tmp_path):
    mock_check_table.return_value = True
    fake_csv = tmp_path / "data.csv"
    fake_csv.write_text("id,name\n1,John")
    argv = [
        "--input", str(fake_csv),
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    pipeline_script.run(argv)
    mock_create_pipeline.assert_called_once()
    mock_bq_client.assert_called_once()


@mock.patch("ingest_pipeline.bigquery.Client")
@mock.patch("ingest_pipeline.check_table_exists")
def test_run_file_not_exists(mock_check_table, mock_bq_client):
    argv = [
        "--input", "non_existing.csv",
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    pipeline_script.run(argv)
    mock_check_table.assert_not_called()
    mock_bq_client.assert_not_called()


@mock.patch("ingest_pipeline.beam.io.gcp.gcsfilesystem.GCSFileSystem.exists")
@mock.patch("ingest_pipeline.bigquery.Client")
@mock.patch("ingest_pipeline.check_table_exists")
@mock.patch("ingest_pipeline.create_pipeline")
def test_run_gcs_file_exists(mock_create_pipeline, mock_check_table, mock_bq_client, mock_gcs_exists):
    mock_check_table.return_value = True
    mock_gcs_exists.return_value = True

    argv = [
        "--input", "gs://bucket/data.csv",
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    pipeline_script.run(argv)
    mock_create_pipeline.assert_called_once()
    mock_gcs_exists.assert_called_once_with("gs://bucket/data.csv")


@mock.patch("ingest_pipeline.beam.io.gcp.gcsfilesystem.GCSFileSystem.exists")
@mock.patch("ingest_pipeline.bigquery.Client")
@mock.patch("ingest_pipeline.check_table_exists")
def test_run_gcs_file_not_exists(mock_check_table, mock_bq_client, mock_gcs_exists):
    mock_gcs_exists.return_value = False

    argv = [
        "--input", "gs://bucket/missing.csv",
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    pipeline_script.run(argv)
    mock_check_table.assert_not_called()
    mock_bq_client.assert_not_called()

@mock.patch("ingest_pipeline.bigquery.Client")
@mock.patch("ingest_pipeline.create_pipeline")
def test_run_table_does_not_exist(mock_create_pipeline, mock_bq_client, caplog, tmp_path):
    """Covers line 79: warning for missing BQ table."""
    fake_csv = tmp_path / "data.csv"
    fake_csv.write_text("id,name\n1,John")
    caplog.set_level("WARNING")
    # Mock table existence check
    with mock.patch("ingest_pipeline.check_table_exists", return_value=False):
        pipeline_script.run([
            "--input", str(fake_csv),
            "--raw_table", "project.dataset.table",
            "--schema", "id:STRING,name:STRING"
        ])
    assert "does not exist. It will be created" in caplog.text


@mock.patch("ingest_pipeline.beam.io.gcp.gcsfilesystem.GCSFileSystem.exists", return_value=True)
def test_run_generic_exception(mock_gcs_exists, monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("Boom!")

    # Replace create_pipeline with a function that raises
    monkeypatch.setattr(pipeline_script, "create_pipeline", boom)

    caplog.set_level("ERROR")

    with pytest.raises(RuntimeError):
        pipeline_script.run([
            "--input", "gs://bucket/data.csv",
            "--raw_table", "project.dataset.table",
            "--schema", "id:STRING,name:STRING"
        ])

    mock_gcs_exists.assert_called_once()
    assert "Pipeline error" in caplog.text