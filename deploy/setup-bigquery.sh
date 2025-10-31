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

# Retry and timeout configuration
MAX_RETRIES=4
INITIAL_BACKOFF=2
BQ_TIMEOUT=300  # 5 minutes instead of default 60 seconds

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

# Function to retry commands with exponential backoff
retry_with_backoff() {
    local max_attempts=$1
    shift
    local command=("$@")
    local attempt=1
    local backoff=$INITIAL_BACKOFF

    while [ $attempt -le $max_attempts ]; do
        echo -e "${YELLOW}Attempt $attempt of $max_attempts...${NC}"
        if "${command[@]}"; then
            return 0
        fi

        if [ $attempt -lt $max_attempts ]; then
            echo -e "${YELLOW}Command failed, retrying in ${backoff}s...${NC}"
            sleep $backoff
            backoff=$((backoff * 2))
        fi
        attempt=$((attempt + 1))
    done

    echo -e "${RED}Command failed after $max_attempts attempts${NC}"
    return 1
}

# Enable BigQuery API if not already enabled
echo -e "${YELLOW}Ensuring BigQuery API is enabled...${NC}"
if gcloud services enable bigquery.googleapis.com --project=$PROJECT_ID 2>/dev/null; then
    echo -e "${GREEN}BigQuery API enabled${NC}"
    # Wait a bit for API to fully propagate
    echo -e "${YELLOW}Waiting for API to propagate...${NC}"
    sleep 10
else
    echo -e "${YELLOW}BigQuery API already enabled or check skipped${NC}"
fi

# Create BigQuery dataset with retry logic
echo -e "${YELLOW}Creating BigQuery dataset...${NC}"
check_dataset_exists() {
    bq --project_id=$PROJECT_ID --apilog=false ls -d "$PROJECT_ID:$DATASET_NAME" >/dev/null 2>&1
}

create_dataset() {
    bq --project_id=$PROJECT_ID \
       --apilog=false \
       --max_rows_per_request=100 \
       mk \
       --location=$LOCATION \
       --description="Dataset for Cars with a Life autonomous driving experiments" \
       "$PROJECT_ID:$DATASET_NAME"
}

if ! check_dataset_exists; then
    echo -e "${YELLOW}Dataset not found, creating with retry logic...${NC}"
    if retry_with_backoff $MAX_RETRIES create_dataset; then
        echo -e "${GREEN}BigQuery dataset created: $DATASET_NAME${NC}"
    else
        echo -e "${RED}Failed to create BigQuery dataset after multiple attempts${NC}"
        echo -e "${YELLOW}Please try:${NC}"
        echo "  1. Check Google Cloud Status: https://status.cloud.google.com/"
        echo "  2. Verify BigQuery API is enabled in the Cloud Console"
        echo "  3. Try creating the dataset manually via the BigQuery Console"
        echo "  4. Check your network connectivity and firewall settings"
        exit 1
    fi
else
    echo -e "${YELLOW}BigQuery dataset already exists: $DATASET_NAME${NC}"
fi

# Create tables using schema files
echo -e "${YELLOW}Creating BigQuery tables from schema files...${NC}"

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to create a table with retry logic
create_table_with_retry() {
    local table_name=$1
    local schema_file=$2

    echo -e "${YELLOW}Creating $table_name table...${NC}"

    create_table_cmd() {
        local sql=$(sed "s/{project_id}/$PROJECT_ID/g; s/{dataset}/$DATASET_NAME/g" "$schema_file")
        echo "$sql" | bq --project_id=$PROJECT_ID --apilog=false query --use_legacy_sql=false
    }

    if retry_with_backoff $MAX_RETRIES create_table_cmd; then
        echo -e "${GREEN}$table_name table created successfully${NC}"
    else
        echo -e "${RED}Failed to create $table_name table${NC}"
        return 1
    fi
}

# Create experiments table
if [ -f "$SCRIPT_DIR/schemas/experiments.sql" ]; then
    create_table_with_retry "experiments" "$SCRIPT_DIR/schemas/experiments.sql"
else
    echo -e "${YELLOW}Warning: experiments.sql schema file not found, skipping${NC}"
fi

# Create autonomous_notes table
if [ -f "$SCRIPT_DIR/schemas/autonomous_notes.sql" ]; then
    create_table_with_retry "autonomous_notes" "$SCRIPT_DIR/schemas/autonomous_notes.sql"
else
    echo -e "${YELLOW}Warning: autonomous_notes.sql schema file not found, skipping${NC}"
fi

# Create evaluation_metrics table
if [ -f "$SCRIPT_DIR/schemas/evaluation_metrics.sql" ]; then
    create_table_with_retry "evaluation_metrics" "$SCRIPT_DIR/schemas/evaluation_metrics.sql"
else
    echo -e "${YELLOW}Warning: evaluation_metrics.sql schema file not found, skipping${NC}"
fi

echo -e "${GREEN}BigQuery tables created successfully${NC}"

# Create Cloud Storage buckets
echo -e "${YELLOW}Creating Cloud Storage buckets...${NC}"

# Function to create bucket with retry logic
create_bucket_with_retry() {
    local bucket_name=$1
    local bucket_description=$2

    check_bucket() {
        gsutil ls "gs://$bucket_name" >/dev/null 2>&1
    }

    create_bucket_cmd() {
        gsutil mb -p $PROJECT_ID -l $STORAGE_LOCATION "gs://$bucket_name"
    }

    if ! check_bucket; then
        if retry_with_backoff $MAX_RETRIES create_bucket_cmd; then
            echo -e "${GREEN}Created $bucket_description bucket: $bucket_name${NC}"
        else
            echo -e "${RED}Failed to create $bucket_description bucket: $bucket_name${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}$bucket_description bucket already exists: $bucket_name${NC}"
    fi
}

# Bucket for experiment artifacts
ARTIFACTS_BUCKET="${STORAGE_BUCKET_PREFIX}-artifacts-${PROJECT_ID}"
create_bucket_with_retry "$ARTIFACTS_BUCKET" "artifacts"

# Bucket for reports
REPORTS_BUCKET="${STORAGE_BUCKET_PREFIX}-reports-${PROJECT_ID}"
create_bucket_with_retry "$REPORTS_BUCKET" "reports"

# Bucket for model artifacts and checkpoints
MODELS_BUCKET="${STORAGE_BUCKET_PREFIX}-models-${PROJECT_ID}"
create_bucket_with_retry "$MODELS_BUCKET" "models"

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
echo ""
echo -e "${GREEN}NOTE:${NC} If you experienced timeout issues, you can alternatively use:"
echo "  python3 $SCRIPT_DIR/setup-bigquery-python.py"
echo ""
echo -e "${YELLOW}Troubleshooting timeout issues:${NC}"
echo "  1. Check: https://status.cloud.google.com/"
echo "  2. Ensure BigQuery API is enabled"
echo "  3. Verify network connectivity"
echo "  4. Try from a different network/location"
echo "  5. Use the Python alternative script above"