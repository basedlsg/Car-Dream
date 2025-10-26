#!/bin/bash

# Data Infrastructure Configuration for Cars with a Life
# This file contains configuration variables for BigQuery and Cloud Storage

# BigQuery Configuration
export BIGQUERY_DATASET="cars_with_a_life"
export BIGQUERY_LOCATION="US"

# Cloud Storage Configuration
export STORAGE_LOCATION="US"
export STORAGE_BUCKET_PREFIX="cars-with-a-life"

# Derived bucket names (will include project ID)
export ARTIFACTS_BUCKET="${STORAGE_BUCKET_PREFIX}-artifacts-${PROJECT_ID}"
export REPORTS_BUCKET="${STORAGE_BUCKET_PREFIX}-reports-${PROJECT_ID}"
export MODELS_BUCKET="${STORAGE_BUCKET_PREFIX}-models-${PROJECT_ID}"

# Data retention settings (in days)
export ARTIFACTS_NEARLINE_AGE=30
export ARTIFACTS_COLDLINE_AGE=90
export ARTIFACTS_DELETE_AGE=365
export REPORTS_NEARLINE_AGE=7
export REPORTS_COLDLINE_AGE=30

# Service account names
export ORCHESTRATOR_SA="orchestrator-service@${PROJECT_ID}.iam.gserviceaccount.com"
export REPORTER_SA="reporter-service@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Data infrastructure configuration loaded:"
echo "  Dataset: $BIGQUERY_DATASET"
echo "  Artifacts bucket: $ARTIFACTS_BUCKET"
echo "  Reports bucket: $REPORTS_BUCKET"
echo "  Models bucket: $MODELS_BUCKET"