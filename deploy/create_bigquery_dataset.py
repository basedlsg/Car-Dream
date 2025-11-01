#!/usr/bin/env python3
"""
Create BigQuery dataset with retry logic to handle timeouts.
Alternative to bq CLI which can timeout.
"""

import sys
import time
import os
from google.cloud import bigquery
from google.api_core import retry, exceptions

PROJECT_ID = os.environ.get('GCP_PROJECT_ID', 'vertex-test-1-467818')
DATASET_ID = 'cars_with_a_life'
REGION = os.environ.get('GCP_REGION', 'us-central1')
MAX_RETRIES = 5
RETRY_DELAY = 5


def create_dataset_with_retry():
    """Create BigQuery dataset with exponential backoff retry."""
    client = bigquery.Client(project=PROJECT_ID)
    
    dataset_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = REGION
    dataset.description = "Cars with a Life autonomous driving experiment data"
    
    # Add labels
    dataset.labels = {
        'service': 'cars-with-a-life',
        'environment': 'production'
    }
    
    print(f"Creating BigQuery dataset: {DATASET_ID} in project {PROJECT_ID}")
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            dataset = client.create_dataset(dataset, timeout=60, exists_ok=True)
            print(f"✓ Successfully created dataset: {dataset.dataset_id}")
            print(f"  Location: {dataset.location}")
            print(f"  Full ID: {dataset.full_dataset_id}")
            return True
        except exceptions.Conflict:
            print(f"✓ Dataset {DATASET_ID} already exists")
            return True
        except Exception as e:
            if attempt < MAX_RETRIES:
                wait_time = RETRY_DELAY * attempt
                print(f"✗ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
                print(f"  Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"✗ Failed to create dataset after {MAX_RETRIES} attempts")
                print(f"  Error: {e}")
                return False
    
    return False


def create_tables_from_sql():
    """Create BigQuery tables from SQL schema files."""
    client = bigquery.Client(project=PROJECT_ID)
    schemas_dir = os.path.join(os.path.dirname(__file__), 'schemas')
    
    if not os.path.exists(schemas_dir):
        print(f"Warning: Schemas directory not found: {schemas_dir}")
        return
    
    sql_files = [
        'experiments.sql',
        'autonomous_notes.sql',
        'evaluation_metrics.sql'
    ]
    
    for sql_file in sql_files:
        sql_path = os.path.join(schemas_dir, sql_file)
        if not os.path.exists(sql_path):
            print(f"Warning: SQL file not found: {sql_path}")
            continue
        
        table_name = sql_file.replace('.sql', '')
        print(f"Creating table from {sql_file}...")
        
        with open(sql_path, 'r') as f:
            sql = f.read()
        
        try:
            job = client.query(sql, job_config=bigquery.QueryJobConfig(use_legacy_sql=False))
            job.result(timeout=60)
            print(f"✓ Successfully created table: {table_name}")
        except exceptions.Conflict:
            print(f"✓ Table {table_name} already exists")
        except Exception as e:
            print(f"✗ Failed to create table {table_name}: {e}")


if __name__ == '__main__':
    print(f"BigQuery Dataset Creation Script")
    print(f"Project: {PROJECT_ID}")
    print(f"Dataset: {DATASET_ID}")
    print(f"Region: {REGION}")
    print()
    
    if create_dataset_with_retry():
        print()
        print("Creating tables from SQL schemas...")
        create_tables_from_sql()
        print()
        print("✓ BigQuery setup completed successfully")
        sys.exit(0)
    else:
        print()
        print("✗ BigQuery setup failed")
        sys.exit(1)

