#!/bin/bash

# Deploy Cloud Run Services with Advanced Configuration
# Comprehensive deployment for Orchestrator and Reporter services

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
REPOSITORY_NAME="cars-with-a-life-repo"
VERSION=${BUILD_VERSION:-"latest"}

# Service configurations
declare -A SERVICES=(
    ["orchestrator"]="orchestrator"
    ["reporter"]="reporter"
)

declare -A SERVICE_CONFIGS=(
    ["orchestrator_memory"]="2Gi"
    ["orchestrator_cpu"]="2"
    ["orchestrator_min_instances"]="1"
    ["orchestrator_max_instances"]="10"
    ["orchestrator_concurrency"]="100"
    ["orchestrator_timeout"]="900"
    ["reporter_memory"]="2Gi"
    ["reporter_cpu"]="2"
    ["reporter_min_instances"]="0"
    ["reporter_max_instances"]="5"
    ["reporter_concurrency"]="50"
    ["reporter_timeout"]="600"
)

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
    echo_info "Checking prerequisites for Cloud Run deployment..."
    
    # Check if gcloud is installed and authenticated
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is not installed"
        exit 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check if Cloud Run API is enabled
    if ! gcloud services list --enabled --filter="name:run.googleapis.com" --project=$PROJECT_ID | grep -q run; then
        echo_error "Cloud Run API is not enabled. Enable it first."
        exit 1
    fi
    
    # Verify images exist in Artifact Registry
    for service in "${!SERVICES[@]}"; do
        local image_url="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${service}:${VERSION}"
        if ! gcloud artifacts docker images describe "$image_url" --project=$PROJECT_ID &> /dev/null; then
            echo_error "Image not found in Artifact Registry: $image_url"
            echo_info "Please run './deploy/build-and-push-containers.sh' first"
            exit 1
        fi
    done
    
    echo_info "Prerequisites check passed"
}

# Create service account for Cloud Run services
create_service_account() {
    local sa_name="cloud-run-services"
    local sa_email="${sa_name}@${PROJECT_ID}.iam.gserviceaccount.com"
    
    echo_deploy "Creating service account for Cloud Run services..."
    
    # Create service account
    gcloud iam service-accounts create $sa_name \
        --display-name="Cloud Run Services Account" \
        --description="Service account for Cars with a Life Cloud Run services" \
        --project=$PROJECT_ID \
        || echo_warn "Service account may already exist"
    
    # Grant necessary permissions
    local roles=(
        "roles/pubsub.publisher"
        "roles/pubsub.subscriber"
        "roles/storage.objectAdmin"
        "roles/bigquery.dataEditor"
        "roles/bigquery.jobUser"
        "roles/aiplatform.user"
        "roles/compute.viewer"
        "roles/logging.logWriter"
        "roles/monitoring.metricWriter"
        "roles/cloudtrace.agent"
    )
    
    for role in "${roles[@]}"; do
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:${sa_email}" \
            --role="$role" \
            --quiet || echo_warn "Role binding may already exist: $role"
    done
    
    echo_info "Service account configured: $sa_email"
    echo "$sa_email"
}

# Deploy single Cloud Run service
deploy_cloud_run_service() {
    local service_name=$1
    local sa_email=$2
    
    echo_deploy "Deploying Cloud Run service: $service_name"
    
    # Get service configuration
    local memory=${SERVICE_CONFIGS["${service_name}_memory"]}
    local cpu=${SERVICE_CONFIGS["${service_name}_cpu"]}
    local min_instances=${SERVICE_CONFIGS["${service_name}_min_instances"]}
    local max_instances=${SERVICE_CONFIGS["${service_name}_max_instances"]}
    local concurrency=${SERVICE_CONFIGS["${service_name}_concurrency"]}
    local timeout=${SERVICE_CONFIGS["${service_name}_timeout"]}
    
    # Image URL from Artifact Registry
    local image_url="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${service_name}:${VERSION}"
    
    echo_deploy "Using image: $image_url"
    
    # Create environment variables
    local env_vars="GCP_PROJECT_ID=${PROJECT_ID}"
    env_vars="${env_vars},GCP_REGION=${REGION}"
    env_vars="${env_vars},ARTIFACT_REGISTRY_URL=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"
    env_vars="${env_vars},SERVICE_VERSION=${VERSION}"
    env_vars="${env_vars},SERVICE_NAME=${service_name}"
    
    # Add service-specific environment variables
    case $service_name in
        "orchestrator")
            env_vars="${env_vars},CARLA_RUNNER_URL=http://carla-runner-instance:8080"
            env_vars="${env_vars},DREAMERV3_ENDPOINT_ID=dreamerv3-autonomous-driving-endpoint"
            env_vars="${env_vars},REPORTER_SERVICE_URL=https://reporter-${PROJECT_ID}.${REGION}.run.app"
            ;;
        "reporter")
            env_vars="${env_vars},BIGQUERY_DATASET=cars_with_a_life"
            env_vars="${env_vars},STORAGE_BUCKET=${PROJECT_ID}-results"
            ;;
    esac
    
    # Deploy to Cloud Run
    gcloud run deploy $service_name \
        --image $image_url \
        --platform managed \
        --region $REGION \
        --service-account $sa_email \
        --memory $memory \
        --cpu $cpu \
        --min-instances $min_instances \
        --max-instances $max_instances \
        --concurrency $concurrency \
        --timeout $timeout \
        --port 8080 \
        --set-env-vars "$env_vars" \
        --labels service=${service_name},version=${VERSION//[^a-zA-Z0-9]/-},component=cloud-run \
        --allow-unauthenticated \
        --execution-environment gen2 \
        --project $PROJECT_ID
    
    # Get service URL
    local service_url=$(gcloud run services describe $service_name \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.url)")
    
    echo_info "✓ $service_name deployed successfully"
    echo_info "Service URL: $service_url"
    
    # Store service URL for later use
    echo "$service_url" > "/tmp/${service_name}_url"
    
    return 0
}

# Configure traffic allocation and revisions
configure_traffic_allocation() {
    local service_name=$1
    
    echo_deploy "Configuring traffic allocation for $service_name..."
    
    # Get current revision
    local current_revision=$(gcloud run services describe $service_name \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.latestReadyRevisionName)")
    
    # Set 100% traffic to current revision
    gcloud run services update-traffic $service_name \
        --to-revisions=$current_revision=100 \
        --region=$REGION \
        --project=$PROJECT_ID
    
    echo_info "Traffic allocation configured for $service_name"
}

# Setup Cloud Run security
setup_security() {
    echo_deploy "Setting up Cloud Run security..."
    
    # Create IAM policy for service-to-service communication
    for service in "${!SERVICES[@]}"; do
        local sa_email="cloud-run-services@${PROJECT_ID}.iam.gserviceaccount.com"
        
        # Allow service account to invoke Cloud Run services
        gcloud run services add-iam-policy-binding $service \
            --member="serviceAccount:${sa_email}" \
            --role="roles/run.invoker" \
            --region=$REGION \
            --project=$PROJECT_ID
        
        echo_info "IAM policy configured for $service"
    done
    
    # Configure VPC connector if needed (for private networking)
    # This is optional and can be enabled for enhanced security
    echo_info "Security configuration completed"
}

# Create health check endpoints configuration
setup_health_checks() {
    echo_deploy "Setting up health check configuration..."
    
    # Create uptime checks for each service
    for service in "${!SERVICES[@]}"; do
        local service_url=$(cat "/tmp/${service}_url" 2>/dev/null || echo "")
        
        if [ -n "$service_url" ]; then
            cat > "/tmp/${service}-uptime-check.json" << EOF
{
  "displayName": "Cars with a Life - ${service} Health Check",
  "httpCheck": {
    "path": "/health",
    "port": 443,
    "useSsl": true,
    "validateSsl": true
  },
  "monitoredResource": {
    "type": "uptime_url",
    "labels": {
      "project_id": "$PROJECT_ID",
      "host": "$(echo $service_url | sed 's|https://||' | sed 's|/.*||')"
    }
  },
  "timeout": "10s",
  "period": "300s",
  "selectedRegions": ["USA", "EUROPE", "ASIA_PACIFIC"]
}
EOF
            
            gcloud monitoring uptime create \
                --config-from-file="/tmp/${service}-uptime-check.json" \
                --project=$PROJECT_ID \
                || echo_warn "Uptime check may already exist for $service"
            
            rm -f "/tmp/${service}-uptime-check.json"
        fi
    done
    
    echo_info "Health checks configured"
}

# Configure logging and monitoring
setup_logging_monitoring() {
    echo_deploy "Setting up logging and monitoring for Cloud Run services..."
    
    # Create log-based metrics for Cloud Run services
    gcloud logging metrics create cloud_run_request_count \
        --description="Cloud Run request count by service" \
        --log-filter='resource.type="cloud_run_revision" AND httpRequest.requestMethod!=""' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    gcloud logging metrics create cloud_run_error_rate \
        --description="Cloud Run error rate by service" \
        --log-filter='resource.type="cloud_run_revision" AND httpRequest.status>=400' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    gcloud logging metrics create cloud_run_latency \
        --description="Cloud Run request latency" \
        --log-filter='resource.type="cloud_run_revision" AND httpRequest.latency!=""' \
        --value-extractor='EXTRACT(httpRequest.latency)' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    echo_info "Logging and monitoring configured"
}

# Display deployment summary
display_summary() {
    local sa_email=$1
    
    echo_info "Cloud Run Services Deployment Summary"
    echo "====================================="
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Service Account: $sa_email"
    echo "Version: $VERSION"
    echo ""
    echo "Deployed Services:"
    
    for service in "${!SERVICES[@]}"; do
        local service_url=$(cat "/tmp/${service}_url" 2>/dev/null || echo "Not available")
        local memory=${SERVICE_CONFIGS["${service}_memory"]}
        local cpu=${SERVICE_CONFIGS["${service}_cpu"]}
        local min_instances=${SERVICE_CONFIGS["${service}_min_instances"]}
        local max_instances=${SERVICE_CONFIGS["${service}_max_instances"]}
        
        echo "  $service:"
        echo "    URL: $service_url"
        echo "    Resources: $memory RAM, $cpu CPU"
        echo "    Scaling: $min_instances-$max_instances instances"
        echo "    Image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${service}:${VERSION}"
    done
    
    echo ""
    echo "Useful commands:"
    echo "  List services: gcloud run services list --region=$REGION"
    echo "  View logs: gcloud run services logs read <service-name> --region=$REGION"
    echo "  Describe service: gcloud run services describe <service-name> --region=$REGION"
    echo "  Update traffic: gcloud run services update-traffic <service-name> --region=$REGION"
    
    # Clean up temporary files
    rm -f /tmp/*_url
}

# Main function
main() {
    echo_deploy "Starting Cloud Run services deployment..."
    
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
            --service)
                # Deploy specific service only
                local target_service="$2"
                if [[ -n "${SERVICES[$target_service]}" ]]; then
                    declare -A FILTERED_SERVICES
                    FILTERED_SERVICES[$target_service]=${SERVICES[$target_service]}
                    SERVICES=()
                    for key in "${!FILTERED_SERVICES[@]}"; do
                        SERVICES[$key]=${FILTERED_SERVICES[$key]}
                    done
                else
                    echo_error "Unknown service: $target_service"
                    exit 1
                fi
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --project PROJECT_ID      GCP Project ID"
                echo "  --region REGION           GCP Region"
                echo "  --version VERSION         Container version"
                echo "  --service SERVICE         Deploy specific service only"
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
    sa_email=$(create_service_account)
    
    # Deploy all services
    local failed_services=()
    for service in "${!SERVICES[@]}"; do
        if deploy_cloud_run_service "$service" "$sa_email"; then
            configure_traffic_allocation "$service"
            echo_info "✓ $service deployment completed"
        else
            echo_error "✗ Failed to deploy $service"
            failed_services+=("$service")
        fi
    done
    
    if [ ${#failed_services[@]} -gt 0 ]; then
        echo_error "Failed to deploy services: ${failed_services[*]}"
        exit 1
    fi
    
    setup_security
    setup_health_checks
    setup_logging_monitoring
    
    display_summary "$sa_email"
    
    echo_info "Cloud Run services deployment completed successfully!"
}

# Run main function
main "$@"