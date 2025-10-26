#!/bin/bash

# Deploy Orchestrator Service to Cloud Run using Artifact Registry

set -e

PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME="orchestrator"
REPOSITORY_NAME="cars-with-a-life-repo"
VERSION=${BUILD_VERSION:-"latest"}

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo_info "Deploying Orchestrator to Cloud Run..."

# Image URL from Artifact Registry
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${SERVICE_NAME}:${VERSION}"

echo_info "Using image: $IMAGE_URL"

# Verify image exists in Artifact Registry
if ! gcloud artifacts docker images describe "$IMAGE_URL" --project=$PROJECT_ID &> /dev/null; then
    echo_error "Image not found in Artifact Registry: $IMAGE_URL"
    echo_info "Please run './deploy/build-and-push-containers.sh' first"
    exit 1
fi

# Deploy to Cloud Run
echo_info "Deploying to Cloud Run..."

gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_URL \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 1 \
    --max-instances 10 \
    --concurrency 100 \
    --timeout 900 \
    --port 8080 \
    --set-env-vars \
GCP_PROJECT_ID=$PROJECT_ID,\
GCP_REGION=$REGION,\
ARTIFACT_REGISTRY_URL=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME},\
SERVICE_VERSION=$VERSION \
    --labels service=orchestrator,version=${VERSION//[^a-zA-Z0-9]/-} \
    --project $PROJECT_ID

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region=$REGION \
    --project=$PROJECT_ID \
    --format="value(status.url)")

echo_info "Orchestrator deployed successfully!"
echo_info "Service URL: $SERVICE_URL"
echo_info "Image: $IMAGE_URL"
echo ""
echo_info "To check status:"
echo "  gcloud run services describe $SERVICE_NAME --region=$REGION"
echo "  gcloud run services get-iam-policy $SERVICE_NAME --region=$REGION"
echo ""
echo_info "Health check: curl $SERVICE_URL/health"