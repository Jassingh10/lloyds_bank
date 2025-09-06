import sys
import os
import pytest
import datetime
from unittest import mock
from google.cloud.exceptions import NotFound
# Ensure repo root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
import ingest_pipeline as pipeline_script
# --- Unit tests for helper functions ---
@pytest.mark.unit
def test_parse_csv_line():
    schema = ["id", "name", "date"]
    result = pipeline_script.parse_csv_line("1,John,2024-06-02", schema)
    assert result == {"id": "1", "name": "John", "date": "2024-06-02"}
@pytest.mark.unit
def test_add_ingestion_time():
    element = {"id": "1"}
    result = pipeline_script.add_ingestion_time(element.copy())
    assert "ingestion_time" in result
    assert isinstance(result["ingestion_time"], datetime.datetime)
@pytest.mark.unit
def test_add_file_name(tmp_path):
    tmp_file = tmp_path / "test.csv"
    tmp_file.write_text("data")
    element = {"id": "1"}
    result = pipeline_script.add_file_name(element.copy(), str(tmp_file))
    assert result["file_name"] == "test.csv"
@pytest.mark.unit
def test_check_table_exists_true():
    mock_client = mock.Mock()
    mock_client.get_table.return_value = True
    assert pipeline_script.check_table_exists(mock_client, "project.dataset.table")
@pytest.mark.unit
def test_check_table_exists_false():
    mock_client = mock.Mock()
    mock_client.get_table.side_effect = NotFound("not found")
    assert not pipeline_script.check_table_exists(mock_client, "project.dataset.table")
# --- Offline "run" tests for control flow ---
@pytest.mark.unit
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
@pytest.mark.unit
def test_run_local_file_exists(tmp_path, monkeypatch):
    fake_csv = tmp_path / "data.csv"
    fake_csv.write_text("id,name\n1,John")
    # :white_check_mark: Prevent actual Beam execution
    monkeypatch.setattr(pipeline_script, "create_pipeline", lambda *a, **k: None)
    argv = [
        "--input", str(fake_csv),
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    pipeline_script.run(argv)
@pytest.mark.unit
def test_run_file_not_exists(monkeypatch, caplog):
    argv = [
        "--input", "non_existing.csv",
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    caplog.set_level("ERROR")
    pipeline_script.run(argv)
    assert "does not exist" in caplog.text
@pytest.mark.unit
def test_run_gcs_file_exists(monkeypatch):
    argv = [
        "--input", "gs://bucket/data.csv",
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    # :white_check_mark: Prevent actual Beam execution
    monkeypatch.setattr(pipeline_script, "create_pipeline", lambda *a, **k: None)
    pipeline_script.run(argv)
@pytest.mark.unit
def test_run_gcs_file_not_exists(monkeypatch, caplog):
    monkeypatch.setattr(
        "ingest_pipeline.beam.io.gcp.gcsfilesystem.GCSFileSystem.exists",
        lambda *a, **kw: False
    )
    argv = [
        "--input", "gs://bucket/missing.csv",
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    caplog.set_level("ERROR")
    pipeline_script.run(argv)
    assert "does not exist" in caplog.text

@pytest.mark.unit
def test_run_table_does_not_exist(tmp_path, caplog, monkeypatch):
    """Covers the warning branch when the BQ table is missing."""
    fake_csv = tmp_path / "data.csv"
    fake_csv.write_text("id,name\n1,John")
    caplog.set_level("WARNING")
    # Force check_table_exists to return False
    monkeypatch.setattr(pipeline_script, "check_table_exists", lambda *a, **k: False)
    # ✅ Prevent actual Beam execution
    monkeypatch.setattr(pipeline_script, "create_pipeline", lambda *a, **k: None)

    argv = [
        "--input", str(fake_csv),
        "--raw_table", "project.dataset.table",
        "--schema", "id:STRING,name:STRING"
    ]
    pipeline_script.run(argv)
    assert "does not exist. It will be created" in caplog.text


@pytest.mark.unit
def test_run_generic_exception(monkeypatch, caplog):
    """Covers the generic exception handling path in run()."""

    def boom(*args, **kwargs):
        raise RuntimeError("Boom!")

    # Force create_pipeline to raise an exception
    monkeypatch.setattr(pipeline_script, "create_pipeline", boom)
    caplog.set_level("ERROR")

    with pytest.raises(RuntimeError):
        pipeline_script.run([
            "--input", "gs://bucket/data.csv",
            "--raw_table", "project.dataset.table",
            "--schema", "id:STRING,name:STRING"
        ])

    assert "Pipeline error" in caplog.text