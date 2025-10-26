#!/bin/bash

# BigQuery and Cloud Storage Setup Script for Cars with a Life
# This script creates BigQuery datasets, tables, and Cloud Storage buckets

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
DATASET_NAME="cars_with_a_life"
LOCATION="US"  # Multi-region for analytics
STORAGE_BUCKET_PREFIX="cars-with-a-life"
STORAGE_LOCATION="US"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up BigQuery and Cloud Storage for Cars with a Life...${NC}"

# Validate required environment variables
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID is not set${NC}"
    exit 1
fi

echo "Project ID: $PROJECT_ID"
echo "Dataset: $DATASET_NAME"
echo "Location: $LOCATION"

# Create BigQuery dataset
echo -e "${YELLOW}Creating BigQuery dataset...${NC}"
if ! bq ls -d "$PROJECT_ID:$DATASET_NAME" >/dev/null 2>&1; then
    bq mk \
        --location=$LOCATION \
        --description="Dataset for Cars with a Life autonomous driving experiments" \
        "$PROJECT_ID:$DATASET_NAME"
    echo -e "${GREEN}BigQuery dataset created: $DATASET_NAME${NC}"
else
    echo -e "${YELLOW}BigQuery dataset already exists: $DATASET_NAME${NC}"
fi

# Create tables using schema files
echo -e "${YELLOW}Creating BigQuery tables from schema files...${NC}"

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create experiments table
echo -e "${YELLOW}Creating experiments table...${NC}"
EXPERIMENTS_SQL=$(sed "s/{project_id}/$PROJECT_ID/g; s/{dataset}/$DATASET_NAME/g" "$SCRIPT_DIR/schemas/experiments.sql")
echo "$EXPERIMENTS_SQL" | bq query --use_legacy_sql=false

# Create autonomous_notes table
echo -e "${YELLOW}Creating autonomous_notes table...${NC}"
NOTES_SQL=$(sed "s/{project_id}/$PROJECT_ID/g; s/{dataset}/$DATASET_NAME/g" "$SCRIPT_DIR/schemas/autonomous_notes.sql")
echo "$NOTES_SQL" | bq query --use_legacy_sql=false

# Create evaluation_metrics table
echo -e "${YELLOW}Creating evaluation_metrics table...${NC}"
METRICS_SQL=$(sed "s/{project_id}/$PROJECT_ID/g; s/{dataset}/$DATASET_NAME/g" "$SCRIPT_DIR/schemas/evaluation_metrics.sql")
echo "$METRICS_SQL" | bq query --use_legacy_sql=false

echo -e "${GREEN}BigQuery tables created successfully${NC}"

# Create Cloud Storage buckets
echo -e "${YELLOW}Creating Cloud Storage buckets...${NC}"

# Bucket for experiment artifacts
ARTIFACTS_BUCKET="${STORAGE_BUCKET_PREFIX}-artifacts-${PROJECT_ID}"
if ! gsutil ls "gs://$ARTIFACTS_BUCKET" >/dev/null 2>&1; then
    gsutil mb -l $STORAGE_LOCATION "gs://$ARTIFACTS_BUCKET"
    echo -e "${GREEN}Created artifacts bucket: $ARTIFACTS_BUCKET${NC}"
else
    echo -e "${YELLOW}Artifacts bucket already exists: $ARTIFACTS_BUCKET${NC}"
fi

# Bucket for reports
REPORTS_BUCKET="${STORAGE_BUCKET_PREFIX}-reports-${PROJECT_ID}"
if ! gsutil ls "gs://$REPORTS_BUCKET" >/dev/null 2>&1; then
    gsutil mb -l $STORAGE_LOCATION "gs://$REPORTS_BUCKET"
    echo -e "${GREEN}Created reports bucket: $REPORTS_BUCKET${NC}"
else
    echo -e "${YELLOW}Reports bucket already exists: $REPORTS_BUCKET${NC}"
fi

# Bucket for model artifacts and checkpoints
MODELS_BUCKET="${STORAGE_BUCKET_PREFIX}-models-${PROJECT_ID}"
if ! gsutil ls "gs://$MODELS_BUCKET" >/dev/null 2>&1; then
    gsutil mb -l $STORAGE_LOCATION "gs://$MODELS_BUCKET"
    echo -e "${GREEN}Created models bucket: $MODELS_BUCKET${NC}"
else
    echo -e "${YELLOW}Models bucket already exists: $MODELS_BUCKET${NC}"
fi

echo -e "${YELLOW}Setting up data retention policies...${NC}"

# Set lifecycle policies for cost optimization
cat > /tmp/lifecycle-artifacts.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {"age": 30}
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 90}
      },
      {
        "action": {"type": "Delete"},
        "condition": {"age": 365}
      }
    ]
  }
}
EOF

cat > /tmp/lifecycle-reports.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {"age": 7}
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 30}
      }
    ]
  }
}
EOF

# Apply lifecycle policies
gsutil lifecycle set /tmp/lifecycle-artifacts.json "gs://$ARTIFACTS_BUCKET"
gsutil lifecycle set /tmp/lifecycle-reports.json "gs://$REPORTS_BUCKET"

# Clean up temporary files
rm /tmp/lifecycle-artifacts.json /tmp/lifecycle-reports.json

echo -e "${YELLOW}Setting up access control...${NC}"

# Set up IAM policies for service accounts
# Orchestrator service account needs read/write access to BigQuery and Storage
ORCHESTRATOR_SA="orchestrator-service@${PROJECT_ID}.iam.gserviceaccount.com"
REPORTER_SA="reporter-service@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant BigQuery permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$ORCHESTRATOR_SA" \
    --role="roles/bigquery.dataEditor" || echo "Orchestrator SA may not exist yet"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$REPORTER_SA" \
    --role="roles/bigquery.dataEditor" || echo "Reporter SA may not exist yet"

# Grant Storage permissions
gsutil iam ch "serviceAccount:$ORCHESTRATOR_SA:objectAdmin" "gs://$ARTIFACTS_BUCKET" || echo "Orchestrator SA may not exist yet"
gsutil iam ch "serviceAccount:$REPORTER_SA:objectAdmin" "gs://$REPORTS_BUCKET" || echo "Reporter SA may not exist yet"
gsutil iam ch "serviceAccount:$REPORTER_SA:objectAdmin" "gs://$ARTIFACTS_BUCKET" || echo "Reporter SA may not exist yet"

echo -e "${GREEN}Data infrastructure setup completed successfully!${NC}"
echo ""
echo "Created resources:"
echo "  - BigQuery dataset: $DATASET_NAME"
echo "  - Tables: experiments, autonomous_notes, evaluation_metrics"
echo "  - Storage buckets: $ARTIFACTS_BUCKET, $REPORTS_BUCKET, $MODELS_BUCKET"
echo "  - Lifecycle policies applied for cost optimization"
echo ""
echo "Environment variables for services:"
echo "  BIGQUERY_DATASET=$DATASET_NAME"
echo "  ARTIFACTS_BUCKET=$ARTIFACTS_BUCKET"
echo "  REPORTS_BUCKET=$REPORTS_BUCKET"
echo "  MODELS_BUCKET=$MODELS_BUCKET"