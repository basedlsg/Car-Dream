#!/bin/bash

# DreamerV3 Service Deployment Script for Vertex AI
set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME="dreamerv3-service"
REPOSITORY_NAME="cars-with-a-life-repo"
VERSION=${BUILD_VERSION:-"latest"}
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${SERVICE_NAME}:${VERSION}"
MODEL_DISPLAY_NAME="dreamerv3-autonomous-driving"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is not installed"
        exit 1
    fi
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        echo_error "Docker is not installed"
        exit 1
    fi
    
    # Check if authenticated with gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check if project is set
    if [ "$PROJECT_ID" = "your-project-id" ]; then
        echo_error "Please set GCP_PROJECT_ID environment variable"
        exit 1
    fi
    
    echo_info "Prerequisites check passed"
}

# Enable required APIs
enable_apis() {
    echo_info "Enabling required Google Cloud APIs..."
    
    gcloud services enable \
        aiplatform.googleapis.com \
        containerregistry.googleapis.com \
        cloudbuild.googleapis.com \
        storage-api.googleapis.com \
        pubsub.googleapis.com \
        --project=$PROJECT_ID
    
    echo_info "APIs enabled successfully"
}

# Build and push Docker image
build_and_push_image() {
    echo_info "Verifying image in Artifact Registry..."
    
    # Check if image exists in Artifact Registry
    if gcloud artifacts docker images describe "$IMAGE_NAME" --project=$PROJECT_ID &> /dev/null; then
        echo_info "Image found in Artifact Registry: $IMAGE_NAME"
    else
        echo_error "Image not found in Artifact Registry: $IMAGE_NAME"
        echo_info "Please run './deploy/build-and-push-containers.sh' first"
        exit 1
    fi
}

# Create Cloud Storage bucket for model artifacts
create_model_bucket() {
    local bucket_name="${PROJECT_ID}-dreamerv3-models"
    
    echo_info "Creating Cloud Storage bucket for model artifacts..."
    
    # Check if bucket exists
    if gsutil ls -b gs://$bucket_name &> /dev/null; then
        echo_warn "Bucket gs://$bucket_name already exists"
    else
        gsutil mb -p $PROJECT_ID -l $REGION gs://$bucket_name
        echo_info "Created bucket: gs://$bucket_name"
    fi
    
    # Set bucket permissions
    gsutil iam ch serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com:objectViewer gs://$bucket_name
    
    echo $bucket_name
}

# Upload model artifacts (placeholder)
upload_model_artifacts() {
    local bucket_name=$1
    local model_dir="./models"
    
    echo_info "Uploading model artifacts..."
    
    # Create dummy model files if they don't exist
    if [ ! -d "$model_dir" ]; then
        mkdir -p $model_dir
        echo '{"version": "1.0.0", "input_shape": [64, 64, 3], "action_space": 7, "sequence_length": 50, "batch_size": 1}' > $model_dir/config.json
        echo_warn "Created dummy model config. Replace with actual model files."
    fi
    
    # Upload to Cloud Storage
    gsutil -m cp -r $model_dir/* gs://$bucket_name/models/
    
    echo_info "Model artifacts uploaded to gs://$bucket_name/models/"
}

# Deploy to Vertex AI
deploy_to_vertex_ai() {
    local bucket_name=$1
    local model_uri="gs://$bucket_name/models"
    
    echo_info "Deploying to Vertex AI..."
    
    # Create model
    gcloud ai models upload \
        --region=$REGION \
        --display-name=$MODEL_DISPLAY_NAME \
        --container-image-uri=$IMAGE_NAME \
        --container-predict-route="/predict" \
        --container-health-route="/health" \
        --container-ports=8080 \
        --artifact-uri=$model_uri \
        --project=$PROJECT_ID
    
    echo_info "Model uploaded to Vertex AI"
    
    # Create endpoint
    local endpoint_name="${MODEL_DISPLAY_NAME}-endpoint"
    
    gcloud ai endpoints create \
        --region=$REGION \
        --display-name=$endpoint_name \
        --project=$PROJECT_ID
    
    echo_info "Endpoint created: $endpoint_name"
    
    # Get model and endpoint IDs
    local model_id=$(gcloud ai models list \
        --region=$REGION \
        --filter="displayName:$MODEL_DISPLAY_NAME" \
        --format="value(name)" \
        --project=$PROJECT_ID | head -1)
    
    local endpoint_id=$(gcloud ai endpoints list \
        --region=$REGION \
        --filter="displayName:$endpoint_name" \
        --format="value(name)" \
        --project=$PROJECT_ID | head -1)
    
    # Deploy model to endpoint
    gcloud ai endpoints deploy-model $endpoint_id \
        --region=$REGION \
        --model=$model_id \
        --display-name="${MODEL_DISPLAY_NAME}-deployment" \
        --machine-type=n1-standard-4 \
        --accelerator=type=nvidia-tesla-t4,count=1 \
        --min-replica-count=1 \
        --max-replica-count=3 \
        --traffic-split=0=100 \
        --project=$PROJECT_ID
    
    echo_info "Model deployed to endpoint successfully"
    echo_info "Endpoint ID: $endpoint_id"
}

# Create Pub/Sub topics
create_pubsub_topics() {
    echo_info "Creating Pub/Sub topics..."
    
    local topics=("ai-decisions" "experiment-events" "model-metrics")
    
    for topic in "${topics[@]}"; do
        if gcloud pubsub topics describe $topic --project=$PROJECT_ID &> /dev/null; then
            echo_warn "Topic $topic already exists"
        else
            gcloud pubsub topics create $topic --project=$PROJECT_ID
            echo_info "Created topic: $topic"
        fi
    done
}

# Setup monitoring
setup_monitoring() {
    echo_info "Setting up monitoring..."
    
    # Create log-based metrics (simplified)
    gcloud logging metrics create dreamerv3_predictions \
        --description="DreamerV3 prediction count" \
        --log-filter='resource.type="gce_instance" AND jsonPayload.message:"Prediction logged"' \
        --project=$PROJECT_ID || echo_warn "Metric may already exist"
    
    gcloud logging metrics create dreamerv3_errors \
        --description="DreamerV3 error count" \
        --log-filter='resource.type="gce_instance" AND severity>=ERROR AND jsonPayload.service="dreamerv3"' \
        --project=$PROJECT_ID || echo_warn "Metric may already exist"
    
    echo_info "Monitoring setup completed"
}

# Main deployment function
main() {
    echo_info "Starting DreamerV3 service deployment..."
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --project)
                PROJECT_ID="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --help)
                echo "Usage: $0 [--project PROJECT_ID] [--region REGION] [--skip-build]"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Run deployment steps
    check_prerequisites
    enable_apis
    
    if [ "$SKIP_BUILD" != "true" ]; then
        build_and_push_image
    fi
    
    bucket_name=$(create_model_bucket)
    upload_model_artifacts $bucket_name
    create_pubsub_topics
    setup_monitoring
    deploy_to_vertex_ai $bucket_name
    
    echo_info "Deployment completed successfully!"
    echo_info "Image: $IMAGE_NAME:latest"
    echo_info "Model bucket: gs://$bucket_name"
    echo_info "Project: $PROJECT_ID"
    echo_info "Region: $REGION"
}

# Run main function
main "$@"