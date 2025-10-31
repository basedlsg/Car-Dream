#!/usr/bin/env python3
"""
BigQuery Dataset Setup Script - Python Alternative
This script creates BigQuery datasets using the Python client library as a fallback
when the bq command-line tool experiences timeout issues.
"""

import os
import sys
import time
from typing import Optional

try:
    from google.cloud import bigquery
    from google.api_core import exceptions, retry
    from google.api_core.client_options import ClientOptions
except ImportError:
    print("Error: google-cloud-bigquery library not installed")
    print("Install it with: pip install google-cloud-bigquery")
    sys.exit(1)


# Configuration
PROJECT_ID = os.environ.get('PROJECT_ID') or os.environ.get('GCP_PROJECT_ID')
DATASET_NAME = "cars_with_a_life"
LOCATION = "US"
MAX_RETRIES = 4
INITIAL_BACKOFF = 2

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color


def print_color(message: str, color: str = NC):
    """Print colored message."""
    print(f"{color}{message}{NC}")


def retry_with_exponential_backoff(func, max_retries: int = MAX_RETRIES):
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts

    Returns:
        Function result or raises exception after max retries
    """
    backoff = INITIAL_BACKOFF

    for attempt in range(1, max_retries + 1):
        try:
            print_color(f"Attempt {attempt} of {max_retries}...", YELLOW)
            return func()
        except Exception as e:
            if attempt == max_retries:
                print_color(f"Failed after {max_retries} attempts", RED)
                raise

            print_color(f"Attempt failed: {str(e)}", YELLOW)
            print_color(f"Retrying in {backoff}s...", YELLOW)
            time.sleep(backoff)
            backoff *= 2


def create_bigquery_dataset(project_id: str, dataset_name: str, location: str) -> bool:
    """
    Create a BigQuery dataset with retry logic.

    Args:
        project_id: GCP project ID
        dataset_name: Name of the dataset to create
        location: Dataset location (e.g., 'US')

    Returns:
        True if successful, False otherwise
    """
    print_color(f"Creating BigQuery dataset: {dataset_name}", GREEN)
    print_color(f"Project: {project_id}", YELLOW)
    print_color(f"Location: {location}", YELLOW)

    try:
        # Configure client with increased timeout
        client_options = ClientOptions(
            api_endpoint="https://bigquery.googleapis.com"
        )

        def create_dataset():
            # Initialize BigQuery client with custom timeout
            client = bigquery.Client(
                project=project_id,
                client_options=client_options
            )

            # Check if dataset already exists
            dataset_id = f"{project_id}.{dataset_name}"
            try:
                dataset = client.get_dataset(dataset_id)
                print_color(f"Dataset {dataset_name} already exists", YELLOW)
                return dataset
            except exceptions.NotFound:
                print_color(f"Dataset not found, creating new dataset...", YELLOW)

            # Create dataset
            dataset = bigquery.Dataset(dataset_id)
            dataset.location = location
            dataset.description = "Dataset for Cars with a Life autonomous driving experiments"

            # Create the dataset with custom retry settings
            custom_retry = retry.Retry(
                initial=1.0,
                maximum=60.0,
                multiplier=2.0,
                deadline=300.0,  # 5 minutes
                predicate=retry.if_exception_type(
                    exceptions.DeadlineExceeded,
                    exceptions.ServiceUnavailable,
                    exceptions.InternalServerError,
                )
            )

            dataset = client.create_dataset(dataset, timeout=300, retry=custom_retry)
            print_color(f"Successfully created dataset {dataset_name}", GREEN)
            return dataset

        # Retry with exponential backoff
        result = retry_with_exponential_backoff(create_dataset)

        if result:
            print_color(f"Dataset {dataset_name} is ready", GREEN)
            return True

    except exceptions.Conflict:
        print_color(f"Dataset {dataset_name} already exists", YELLOW)
        return True
    except exceptions.Forbidden as e:
        print_color(f"Permission denied: {str(e)}", RED)
        print_color("Please ensure you have the 'bigquery.datasets.create' permission", YELLOW)
        return False
    except exceptions.GoogleAPIError as e:
        print_color(f"BigQuery API error: {str(e)}", RED)
        print_color("This might be a transient error. Please try again in a few minutes.", YELLOW)
        return False
    except Exception as e:
        print_color(f"Unexpected error: {str(e)}", RED)
        return False


def create_table_from_schema(
    project_id: str,
    dataset_name: str,
    table_name: str,
    schema_file: str
) -> bool:
    """
    Create a BigQuery table from a SQL schema file.

    Args:
        project_id: GCP project ID
        dataset_name: Dataset name
        table_name: Table name
        schema_file: Path to SQL schema file

    Returns:
        True if successful, False otherwise
    """
    print_color(f"Creating table {table_name}...", YELLOW)

    try:
        client = bigquery.Client(project=project_id)

        # Read and process schema file
        with open(schema_file, 'r') as f:
            sql = f.read()

        # Replace placeholders
        sql = sql.replace('{project_id}', project_id)
        sql = sql.replace('{dataset}', dataset_name)

        def run_query():
            # Execute query with timeout
            job_config = bigquery.QueryJobConfig()
            query_job = client.query(sql, job_config=job_config, timeout=300)
            query_job.result(timeout=300)  # Wait for query to complete
            print_color(f"Table {table_name} created successfully", GREEN)

        retry_with_exponential_backoff(run_query)
        return True

    except FileNotFoundError:
        print_color(f"Schema file not found: {schema_file}", YELLOW)
        return False
    except Exception as e:
        print_color(f"Failed to create table {table_name}: {str(e)}", RED)
        return False


def main():
    """Main function."""
    print_color("=" * 60, GREEN)
    print_color("BigQuery Dataset Setup (Python Alternative)", GREEN)
    print_color("=" * 60, GREEN)

    # Validate configuration
    if not PROJECT_ID:
        print_color("Error: PROJECT_ID environment variable is not set", RED)
        print_color("Set it with: export PROJECT_ID=your-project-id", YELLOW)
        sys.exit(1)

    # Create dataset
    success = create_bigquery_dataset(PROJECT_ID, DATASET_NAME, LOCATION)

    if not success:
        print_color("\nDataset creation failed. Troubleshooting steps:", RED)
        print_color("1. Check Google Cloud Status: https://status.cloud.google.com/", YELLOW)
        print_color("2. Verify BigQuery API is enabled:", YELLOW)
        print_color(f"   gcloud services enable bigquery.googleapis.com --project={PROJECT_ID}", YELLOW)
        print_color("3. Check your permissions:", YELLOW)
        print_color(f"   gcloud projects get-iam-policy {PROJECT_ID}", YELLOW)
        print_color("4. Try creating the dataset via Cloud Console:", YELLOW)
        print_color(f"   https://console.cloud.google.com/bigquery?project={PROJECT_ID}", YELLOW)
        sys.exit(1)

    # Create tables from schema files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schemas_dir = os.path.join(script_dir, 'schemas')

    tables = {
        'experiments': os.path.join(schemas_dir, 'experiments.sql'),
        'autonomous_notes': os.path.join(schemas_dir, 'autonomous_notes.sql'),
        'evaluation_metrics': os.path.join(schemas_dir, 'evaluation_metrics.sql'),
    }

    print_color("\nCreating tables...", GREEN)
    for table_name, schema_file in tables.items():
        if os.path.exists(schema_file):
            create_table_from_schema(PROJECT_ID, DATASET_NAME, table_name, schema_file)
        else:
            print_color(f"Schema file not found for {table_name}, skipping", YELLOW)

    print_color("\n" + "=" * 60, GREEN)
    print_color("Setup completed!", GREEN)
    print_color("=" * 60, GREEN)
    print_color(f"\nDataset: {PROJECT_ID}.{DATASET_NAME}", YELLOW)
    print_color(f"Location: {LOCATION}", YELLOW)
    print_color("\nNext steps:", YELLOW)
    print_color("1. Run the storage bucket setup if not already done", YELLOW)
    print_color("2. Configure your services to use this dataset", YELLOW)
    print_color(f"3. View your dataset: https://console.cloud.google.com/bigquery?project={PROJECT_ID}&d={DATASET_NAME}", YELLOW)


if __name__ == "__main__":
    main()
