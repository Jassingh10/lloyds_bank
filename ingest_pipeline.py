import argparse
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
import logging
import datetime
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import os

def parse_csv_line(line, schema_fields):
    """Parse a CSV line into a dictionary."""
    values = line.split(",")
    return dict(zip(schema_fields, values))

def add_ingestion_time(element):
    """Add the ingestion time to the element."""
    element['ingestion_time'] = datetime.datetime.now()
    return element

def add_file_name(element, file_name):
    """Add the file name to the element."""
    element['file_name'] = os.path.basename(file_name)
    return element

def check_table_exists(bq_client, table_ref):
    """Check if a BigQuery table exists."""
    try:
        bq_client.get_table(table_ref)
        return True
    except NotFound:
        return False

def create_pipeline(pipeline_options, input_path, raw_table, schema):
    """Create a Beam pipeline."""
    schema_fields = [c.split(":")[0] for c in schema.split(",")]
    with beam.Pipeline(options=pipeline_options) as p:
        (p | "ReadCSV" >> beam.io.ReadFromText(input_path, skip_header_lines=1)
           | "ParseCSV" >> beam.Map(lambda line: parse_csv_line(line, schema_fields))
           | "AddFileName" >> beam.Map(lambda element: add_file_name(element, input_path))
           | "AddIngestionTime" >> beam.Map(add_ingestion_time)
           | "WriteToBQ" >> beam.io.WriteToBigQuery(
                raw_table,
                schema=schema + ",file_name:STRING,ingestion_time:TIMESTAMP",
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
            )
        )

def run(argv=None):
    """Run the pipeline."""
    try:
        parser = argparse.ArgumentParser(description='Load CSV data into BigQuery')
        parser.add_argument("--input", required=True, help="Path to CSV file")
        parser.add_argument("--raw_table", required=True, help="BQ raw table: proj.dataset.table")
        parser.add_argument("--schema", required=True, help="Schema: col1:STRING,col2:DATE,...")
        args, beam_args = parser.parse_known_args(argv)

        # Check if file exists
        if not os.path.exists(args.input.replace("gs://", "/gcs/")) and not args.input.startswith("gs://"):
            logging.error(f"File {args.input} does not exist")
            return

        pipeline_options = PipelineOptions(flags=beam_args, save_main_session=True, streaming=False)

        if args.input.startswith("gs://"):
            gcs = beam.io.gcp.gcsfilesystem.GCSFileSystem(pipeline_options)
            if not gcs.exists(args.input):
                logging.error(f"File {args.input} does not exist")
                return

        # Initialize BigQuery client
        bq_client = bigquery.Client()

        # Parse table reference
        table_ref = bigquery.TableReference.from_string(args.raw_table, default_project=bq_client.project)

        # Check if table exists
        if not check_table_exists(bq_client, table_ref):
            logging.warning(f"Table {args.raw_table} does not exist. It will be created.")

        create_pipeline(pipeline_options, args.input, args.raw_table, args.schema)
        logging.info("Pipeline finished.")

    except Exception as e:
        logging.error(f"Pipeline error: {e}")
        raise

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()