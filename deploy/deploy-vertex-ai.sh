#!/bin/bash

# Deploy Vertex AI Resources with Monitoring and Auto-scaling
# Enhanced deployment for DreamerV3 Service

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
REPOSITORY_NAME="cars-with-a-life-repo"
VERSION=${BUILD_VERSION:-"latest"}

# Model configuration
MODEL_DISPLAY_NAME="dreamerv3-autonomous-driving"
ENDPOINT_DISPLAY_NAME="${MODEL_DISPLAY_NAME}-endpoint"
SERVICE_NAME="dreamerv3-service"

# Auto-scaling configuration
MIN_REPLICA_COUNT=1
MAX_REPLICA_COUNT=5
MACHINE_TYPE="n1-standard-4"
ACCELERATOR_TYPE="NVIDIA_TESLA_T4"
ACCELERATOR_COUNT=1

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

echo_deploy() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites for Vertex AI deployment..."
    
    # Check if gcloud is installed and authenticated
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is not installed"
        exit 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check if Vertex AI API is enabled
    if ! gcloud services list --enabled --filter="name:aiplatform.googleapis.com" --project=$PROJECT_ID | grep -q aiplatform; then
        echo_error "Vertex AI API is not enabled. Enable it first."
        exit 1
    fi
    
    # Verify image exists in Artifact Registry
    local image_url="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${SERVICE_NAME}:${VERSION}"
    if ! gcloud artifacts docker images describe "$image_url" --project=$PROJECT_ID &> /dev/null; then
        echo_error "Image not found in Artifact Registry: $image_url"
        echo_info "Please run './deploy/build-and-push-containers.sh' first"
        exit 1
    fi
    
    echo_info "Prerequisites check passed"
}

# Create Cloud Storage bucket for model artifacts
create_model_bucket() {
    local bucket_name="${PROJECT_ID}-vertex-ai-models"
    
    echo_deploy "Creating Cloud Storage bucket for model artifacts..."
    
    # Check if bucket exists
    if gsutil ls -b gs://$bucket_name &> /dev/null; then
        echo_warn "Bucket gs://$bucket_name already exists"
    else
        gsutil mb -p $PROJECT_ID -l $REGION gs://$bucket_name
        echo_info "Created bucket: gs://$bucket_name"
    fi
    
    # Set bucket permissions for Vertex AI
    local project_number=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
    local vertex_ai_sa="service-${project_number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
    
    gsutil iam ch serviceAccount:${vertex_ai_sa}:objectViewer gs://$bucket_name
    gsutil iam ch serviceAccount:${vertex_ai_sa}:objectCreator gs://$bucket_name
    
    echo $bucket_name
}

# Upload model artifacts and configuration
upload_model_artifacts() {
    local bucket_name=$1
    local model_dir="./vertex-ai-models"
    
    echo_deploy "Uploading model artifacts..."
    
    # Create model configuration directory
    mkdir -p $model_dir
    
    # Create model configuration
    cat > $model_dir/config.json << EOF
{
    "version": "$VERSION",
    "model_type": "dreamerv3",
    "input_shape": [64, 64, 3],
    "action_space": 7,
    "sequence_length": 50,
    "batch_size": 1,
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "container_image": "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${SERVICE_NAME}:${VERSION}"
}
EOF
    
    # Create model metadata
    cat > $model_dir/metadata.json << EOF
{
    "name": "$MODEL_DISPLAY_NAME",
    "description": "DreamerV3 world model for autonomous driving in CARLA simulation",
    "version": "$VERSION",
    "framework": "tensorflow",
    "runtime": "custom-container",
    "prediction_schema": {
        "input": {
            "simulation_state": "object",
            "sensor_data": "object",
            "context": "object"
        },
        "output": {
            "actions": "array",
            "confidence": "number",
            "reasoning": "string"
        }
    }
}
EOF
    
    # Create sample prediction request for testing
    cat > $model_dir/sample_request.json << EOF
{
    "instances": [
        {
            "simulation_state": {
                "vehicle_position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "vehicle_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
                "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
            },
            "sensor_data": {
                "camera": "base64_encoded_image_data",
                "lidar": "base64_encoded_lidar_data"
            },
            "context": {
                "scenario": "urban_driving",
                "weather": "clear"
            }
        }
    ]
}
EOF
    
    # Upload to Cloud Storage
    gsutil -m cp -r $model_dir/* gs://$bucket_name/models/
    
    echo_info "Model artifacts uploaded to gs://$bucket_name/models/"
    
    # Clean up local files
    rm -rf $model_dir
}

# Create and upload Vertex AI model
create_vertex_ai_model() {
    local bucket_name=$1
    local model_uri="gs://$bucket_name/models"
    local image_url="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${SERVICE_NAME}:${VERSION}"
    
    echo_deploy "Creating Vertex AI model..."
    
    # Check if model already exists
    local existing_model=$(gcloud ai models list \
        --region=$REGION \
        --filter="displayName:$MODEL_DISPLAY_NAME" \
        --format="value(name)" \
        --project=$PROJECT_ID | head -1)
    
    if [ -n "$existing_model" ]; then
        echo_warn "Model $MODEL_DISPLAY_NAME already exists: $existing_model"
        echo "$existing_model"
        return 0
    fi
    
    # Create model
    local model_id=$(gcloud ai models upload \
        --region=$REGION \
        --display-name=$MODEL_DISPLAY_NAME \
        --description="DreamerV3 world model for autonomous driving experiments" \
        --container-image-uri=$image_url \
        --container-predict-route="/predict" \
        --container-health-route="/health" \
        --container-ports=8080 \
        --artifact-uri=$model_uri \
        --labels=service=dreamerv3,version=${VERSION//[^a-zA-Z0-9]/-} \
        --project=$PROJECT_ID \
        --format="value(model)")
    
    echo_info "Model created: $model_id"
    echo "$model_id"
}

# Create Vertex AI endpoint
create_vertex_ai_endpoint() {
    echo_deploy "Creating Vertex AI endpoint..."
    
    # Check if endpoint already exists
    local existing_endpoint=$(gcloud ai endpoints list \
        --region=$REGION \
        --filter="displayName:$ENDPOINT_DISPLAY_NAME" \
        --format="value(name)" \
        --project=$PROJECT_ID | head -1)
    
    if [ -n "$existing_endpoint" ]; then
        echo_warn "Endpoint $ENDPOINT_DISPLAY_NAME already exists: $existing_endpoint"
        echo "$existing_endpoint"
        return 0
    fi
    
    # Create endpoint
    local endpoint_id=$(gcloud ai endpoints create \
        --region=$REGION \
        --display-name=$ENDPOINT_DISPLAY_NAME \
        --description="Endpoint for DreamerV3 autonomous driving model" \
        --labels=service=dreamerv3,version=${VERSION//[^a-zA-Z0-9]/-} \
        --project=$PROJECT_ID \
        --format="value(name)")
    
    echo_info "Endpoint created: $endpoint_id"
    echo "$endpoint_id"
}

# Deploy model to endpoint with auto-scaling
deploy_model_to_endpoint() {
    local model_id=$1
    local endpoint_id=$2
    
    echo_deploy "Deploying model to endpoint with auto-scaling..."
    
    # Check if model is already deployed
    local deployed_model=$(gcloud ai endpoints describe $endpoint_id \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(deployedModels[0].id)" 2>/dev/null)
    
    if [ -n "$deployed_model" ]; then
        echo_warn "Model already deployed to endpoint. Updating deployment..."
        
        # Update existing deployment
        gcloud ai endpoints update $endpoint_id \
            --region=$REGION \
            --project=$PROJECT_ID \
            --update-labels=version=${VERSION//[^a-zA-Z0-9]/-}
        
        return 0
    fi
    
    # Deploy model to endpoint
    gcloud ai endpoints deploy-model $endpoint_id \
        --region=$REGION \
        --model=$model_id \
        --display-name="${MODEL_DISPLAY_NAME}-deployment" \
        --machine-type=$MACHINE_TYPE \
        --accelerator=type=$ACCELERATOR_TYPE,count=$ACCELERATOR_COUNT \
        --min-replica-count=$MIN_REPLICA_COUNT \
        --max-replica-count=$MAX_REPLICA_COUNT \
        --traffic-split=0=100 \
        --enable-access-logging \
        --project=$PROJECT_ID
    
    echo_info "Model deployed to endpoint with auto-scaling configuration"
}

# Setup monitoring and logging
setup_monitoring() {
    local endpoint_id=$1
    
    echo_deploy "Setting up monitoring and logging..."
    
    # Create log-based metrics for Vertex AI
    gcloud logging metrics create vertex_ai_predictions \
        --description="Vertex AI prediction count" \
        --log-filter="resource.type=\"aiplatform.googleapis.com/Endpoint\" AND resource.labels.endpoint_id=\"$(basename $endpoint_id)\"" \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    gcloud logging metrics create vertex_ai_errors \
        --description="Vertex AI prediction errors" \
        --log-filter="resource.type=\"aiplatform.googleapis.com/Endpoint\" AND resource.labels.endpoint_id=\"$(basename $endpoint_id)\" AND severity>=ERROR" \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    gcloud logging metrics create vertex_ai_latency \
        --description="Vertex AI prediction latency" \
        --log-filter="resource.type=\"aiplatform.googleapis.com/Endpoint\" AND resource.labels.endpoint_id=\"$(basename $endpoint_id)\" AND jsonPayload.prediction_latency_ms>0" \
        --value-extractor="EXTRACT(jsonPayload.prediction_latency_ms)" \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    echo_info "Monitoring metrics created for Vertex AI endpoint"
}

# Test endpoint deployment
test_endpoint() {
    local endpoint_id=$1
    
    echo_deploy "Testing endpoint deployment..."
    
    # Get endpoint URL
    local endpoint_url=$(gcloud ai endpoints describe $endpoint_id \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(name)")
    
    # Create test prediction request
    cat > /tmp/test_request.json << EOF
{
    "instances": [
        {
            "simulation_state": {
                "vehicle_position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "vehicle_velocity": {"x": 5.0, "y": 0.0, "z": 0.0},
                "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
            },
            "sensor_data": {
                "camera": "test_image_data",
                "lidar": "test_lidar_data"
            },
            "context": {
                "scenario": "test_scenario",
                "weather": "clear"
            }
        }
    ]
}
EOF
    
    # Test prediction (this may fail if model is not fully ready)
    echo_info "Sending test prediction request..."
    if gcloud ai endpoints predict $endpoint_id \
        --region=$REGION \
        --json-request=/tmp/test_request.json \
        --project=$PROJECT_ID &> /tmp/prediction_result.json; then
        echo_info "✓ Test prediction successful"
        cat /tmp/prediction_result.json
    else
        echo_warn "Test prediction failed (model may still be initializing)"
        echo_info "Check endpoint status: gcloud ai endpoints describe $endpoint_id --region=$REGION"
    fi
    
    # Clean up test files
    rm -f /tmp/test_request.json /tmp/prediction_result.json
}

# Display deployment summary
display_summary() {
    local model_id=$1
    local endpoint_id=$2
    local bucket_name=$3
    
    echo_info "Vertex AI Deployment Summary"
    echo "============================="
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Model: $model_id"
    echo "Endpoint: $endpoint_id"
    echo "Model Bucket: gs://$bucket_name"
    echo "Machine Type: $MACHINE_TYPE"
    echo "Accelerator: $ACCELERATOR_TYPE x $ACCELERATOR_COUNT"
    echo "Auto-scaling: $MIN_REPLICA_COUNT - $MAX_REPLICA_COUNT replicas"
    echo "Image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${SERVICE_NAME}:${VERSION}"
    echo ""
    echo "Useful commands:"
    echo "  Describe model: gcloud ai models describe $model_id --region=$REGION"
    echo "  Describe endpoint: gcloud ai endpoints describe $endpoint_id --region=$REGION"
    echo "  List deployments: gcloud ai endpoints list --region=$REGION"
    echo "  View logs: gcloud logging read 'resource.type=\"aiplatform.googleapis.com/Endpoint\"' --limit=50"
    echo "  Test prediction: gcloud ai endpoints predict $endpoint_id --region=$REGION --json-request=request.json"
}

# Main function
main() {
    echo_deploy "Starting Vertex AI deployment for DreamerV3 Service..."
    
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
            --version)
                VERSION="$2"
                shift 2
                ;;
            --min-replicas)
                MIN_REPLICA_COUNT="$2"
                shift 2
                ;;
            --max-replicas)
                MAX_REPLICA_COUNT="$2"
                shift 2
                ;;
            --machine-type)
                MACHINE_TYPE="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --project PROJECT_ID      GCP Project ID"
                echo "  --region REGION           GCP Region"
                echo "  --version VERSION         Container version"
                echo "  --min-replicas NUM        Minimum replicas (default: 1)"
                echo "  --max-replicas NUM        Maximum replicas (default: 5)"
                echo "  --machine-type TYPE       Machine type (default: n1-standard-4)"
                echo "  --help                    Show this help"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    check_prerequisites
    
    bucket_name=$(create_model_bucket)
    upload_model_artifacts "$bucket_name"
    model_id=$(create_vertex_ai_model "$bucket_name")
    endpoint_id=$(create_vertex_ai_endpoint)
    deploy_model_to_endpoint "$model_id" "$endpoint_id"
    setup_monitoring "$endpoint_id"
    test_endpoint "$endpoint_id"
    
    display_summary "$model_id" "$endpoint_id" "$bucket_name"
    
    echo_info "Vertex AI deployment completed successfully!"
}

# Run main function
main "$@"