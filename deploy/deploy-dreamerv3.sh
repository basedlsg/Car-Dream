#!/bin/bash

# Deploy DreamerV3 Service to Vertex AI

set -e

PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}

echo "Deploying DreamerV3 Service to Vertex AI..."

# Build Docker image
cd services/dreamerv3-service
gcloud builds submit --tag gcr.io/$PROJECT_ID/dreamerv3-service .
cd ../..

# Create Vertex AI custom training job template
cat > deploy/dreamerv3-job.yaml << EOF
displayName: "DreamerV3 Training Job"
jobSpec:
  workerPoolSpecs:
  - machineSpec:
      machineType: "n1-standard-8"
      acceleratorType: "NVIDIA_TESLA_V100"
      acceleratorCount: 1
    replicaCount: 1
    containerSpec:
      imageUri: "gcr.io/$PROJECT_ID/dreamerv3-service"
      env:
      - name: "GCP_PROJECT_ID"
        value: "$PROJECT_ID"
      - name: "GCP_REGION"
        value: "$REGION"
EOF

# Deploy as Vertex AI endpoint for inference
gcloud ai endpoints create \
    --display-name="dreamerv3-endpoint" \
    --region=$REGION \
    || echo "Endpoint may already exist"

echo "DreamerV3 Service deployment template created."
echo "Use Vertex AI console to submit training jobs and deploy models."