#!/usr/bin/env python3
"""
Create BigQuery dataset using Python API to avoid CLI timeout issues.
"""

import os
import sys
import time
from google.cloud import bigquery
from google.api_core import exceptions

PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'vertex-test-1-467818')
DATASET_ID = 'cars_with_a_life'
REGION = os.getenv('GCP_REGION', 'us-central1')


def create_dataset_with_retry(client, dataset_id, max_retries=5):
    """Create BigQuery dataset with exponential backoff retry."""
    dataset_ref = client.dataset(dataset_id)
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = REGION
    dataset.description = "Cars with a Life autonomous driving experiment data"
    
    for attempt in range(max_retries):
        try:
            dataset = client.create_dataset(dataset, timeout=60, exists_ok=True)
            print(f"✓ Successfully created dataset: {PROJECT_ID}.{dataset_id}")
            return dataset
        except exceptions.AlreadyExists:
            print(f"✓ Dataset {PROJECT_ID}.{dataset_id} already exists")
            return client.get_dataset(dataset_ref)
        except (exceptions.ServiceUnavailable, exceptions.DeadlineExceeded, Exception) as e:
            wait_time = 2 ** attempt
            print(f"⚠ Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                print(f"   Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"✗ Failed to create dataset after {max_retries} attempts")
                raise
    
    return None


def create_tables_from_sql(client, dataset_id, sql_dir):
    """Create BigQuery tables from SQL schema files."""
    schema_files = [
        'autonomous_notes.sql',
        'evaluation_metrics.sql',
        'experiments.sql'
    ]
    
    created_tables = []
    for schema_file in schema_files:
        sql_path = os.path.join(sql_dir, schema_file)
        if not os.path.exists(sql_path):
            print(f"⚠ SQL file not found: {sql_path}")
            continue
        
        table_name = schema_file.replace('.sql', '')
        
        # Check if table already exists
        table_ref = client.dataset(dataset_id).table(table_name)
        try:
            client.get_table(table_ref)
            print(f"✓ Table {dataset_id}.{table_name} already exists")
            continue
        except exceptions.NotFound:
            pass
        
        # Read and execute SQL
        with open(sql_path, 'r') as f:
            sql = f.read()
        
        try:
            job = client.query(sql, job_config=bigquery.QueryJobConfig(use_legacy_sql=False))
            job.result(timeout=60)  # Wait for job to complete
            print(f"✓ Created table {dataset_id}.{table_name} from {schema_file}")
            created_tables.append(table_name)
        except Exception as e:
            print(f"⚠ Failed to create table {dataset_id}.{table_name}: {e}")
    
    return created_tables


def main():
    """Main function."""
    print(f"Creating BigQuery dataset: {PROJECT_ID}.{DATASET_ID}")
    print(f"Region: {REGION}")
    
    try:
        client = bigquery.Client(project=PROJECT_ID)
        
        # Create dataset
        dataset = create_dataset_with_retry(client, DATASET_ID)
        if not dataset:
            sys.exit(1)
        
        # Create tables from SQL schemas
        sql_dir = os.path.join(os.path.dirname(__file__), 'schemas')
        if os.path.exists(sql_dir):
            print(f"\nCreating tables from schemas in: {sql_dir}")
            created_tables = create_tables_from_sql(client, DATASET_ID, sql_dir)
            if created_tables:
                print(f"\n✓ Created {len(created_tables)} table(s)")
        else:
            print(f"⚠ Schema directory not found: {sql_dir}")
        
        print("\n✓ BigQuery setup completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())

