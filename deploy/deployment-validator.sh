#!/usr/bin/env bash

# Deployment Validation and Rollback Script
# Validates deployments and provides rollback mechanisms

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
ZONE=${GCP_ZONE:-"us-central1-a"}
REPOSITORY_NAME="cars-with-a-life-repo"
ARTIFACT_REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"

# Validation settings
HEALTH_CHECK_TIMEOUT=300  # 5 minutes
HEALTH_CHECK_INTERVAL=10  # 10 seconds
MAX_RETRY_ATTEMPTS=3

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

echo_validate() {
    echo -e "${BLUE}[VALIDATE]${NC} $1"
}

# Service definitions with their validation endpoints
declare -A CLOUD_RUN_SERVICES=(
    ["orchestrator"]="/health"
    ["reporter"]="/health"
)

declare -A COMPUTE_INSTANCES=(
    ["carla-runner-instance"]="2000"
)

# Validate Cloud Run service
validate_cloud_run_service() {
    local service_name=$1
    local health_endpoint=$2
    
    echo_validate "Validating Cloud Run service: $service_name"
    
    # Get service URL
    local service_url=$(gcloud run services describe $service_name \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.url)" 2>/dev/null)
    
    if [ -z "$service_url" ]; then
        echo_error "Service $service_name not found or not deployed"
        return 1
    fi
    
    echo_validate "Service URL: $service_url"
    
    # Check service status
    local service_status=$(gcloud run services describe $service_name \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.conditions[0].status)" 2>/dev/null)
    
    if [ "$service_status" != "True" ]; then
        echo_error "Service $service_name is not ready. Status: $service_status"
        return 1
    fi
    
    # Health check with retry
    local attempt=1
    local health_url="${service_url}${health_endpoint}"
    
    while [ $attempt -le $MAX_RETRY_ATTEMPTS ]; do
        echo_validate "Health check attempt $attempt/$MAX_RETRY_ATTEMPTS: $health_url"
        
        if curl -f -s --max-time 30 "$health_url" > /dev/null 2>&1; then
            echo_info "✓ $service_name health check passed"
            return 0
        fi
        
        echo_warn "Health check failed, retrying in $HEALTH_CHECK_INTERVAL seconds..."
        sleep $HEALTH_CHECK_INTERVAL
        ((attempt++))
    done
    
    echo_error "✗ $service_name health check failed after $MAX_RETRY_ATTEMPTS attempts"
    return 1
}

# Validate Compute Engine instance
validate_compute_instance() {
    local instance_name=$1
    local port=$2
    
    echo_validate "Validating Compute Engine instance: $instance_name"
    
    # Check instance status
    local instance_status=$(gcloud compute instances describe $instance_name \
        --zone=$ZONE \
        --project=$PROJECT_ID \
        --format="value(status)" 2>/dev/null)
    
    if [ "$instance_status" != "RUNNING" ]; then
        echo_error "Instance $instance_name is not running. Status: $instance_status"
        return 1
    fi
    
    # Get external IP
    local external_ip=$(gcloud compute instances describe $instance_name \
        --zone=$ZONE \
        --project=$PROJECT_ID \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)" 2>/dev/null)
    
    if [ -z "$external_ip" ]; then
        echo_error "No external IP found for instance $instance_name"
        return 1
    fi
    
    echo_validate "Instance IP: $external_ip"
    
    # Port connectivity check
    local attempt=1
    while [ $attempt -le $MAX_RETRY_ATTEMPTS ]; do
        echo_validate "Port connectivity check attempt $attempt/$MAX_RETRY_ATTEMPTS: $external_ip:$port"
        
        if timeout 10 bash -c "</dev/tcp/$external_ip/$port" 2>/dev/null; then
            echo_info "✓ $instance_name port $port is accessible"
            return 0
        fi
        
        echo_warn "Port check failed, retrying in $HEALTH_CHECK_INTERVAL seconds..."
        sleep $HEALTH_CHECK_INTERVAL
        ((attempt++))
    done
    
    echo_error "✗ $instance_name port $port is not accessible after $MAX_RETRY_ATTEMPTS attempts"
    return 1
}

# Validate Vertex AI endpoint
validate_vertex_ai_endpoint() {
    local model_display_name="dreamerv3-autonomous-driving"
    
    echo_validate "Validating Vertex AI endpoint..."
    
    # Get endpoint ID
    local endpoint_id=$(gcloud ai endpoints list \
        --region=$REGION \
        --filter="displayName:${model_display_name}-endpoint" \
        --format="value(name)" \
        --project=$PROJECT_ID | head -1)
    
    if [ -z "$endpoint_id" ]; then
        echo_error "Vertex AI endpoint not found"
        return 1
    fi
    
    echo_validate "Endpoint ID: $endpoint_id"
    
    # Check endpoint status
    local endpoint_status=$(gcloud ai endpoints describe $endpoint_id \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(deployedModels[0].displayName)" 2>/dev/null)
    
    if [ -z "$endpoint_status" ]; then
        echo_error "No model deployed to endpoint"
        return 1
    fi
    
    echo_info "✓ Vertex AI endpoint is active with deployed model"
    return 0
}

# Validate Pub/Sub topics and subscriptions
validate_pubsub() {
    echo_validate "Validating Pub/Sub topics and subscriptions..."
    
    local topics=("experiment-events" "ai-decisions" "model-metrics")
    
    for topic in "${topics[@]}"; do
        if gcloud pubsub topics describe $topic --project=$PROJECT_ID &> /dev/null; then
            echo_info "✓ Topic $topic exists"
        else
            echo_error "✗ Topic $topic not found"
            return 1
        fi
    done
    
    # Check for at least one subscription per topic
    for topic in "${topics[@]}"; do
        local sub_count=$(gcloud pubsub subscriptions list \
            --filter="topic:projects/$PROJECT_ID/topics/$topic" \
            --project=$PROJECT_ID \
            --format="value(name)" | wc -l)
        
        if [ $sub_count -gt 0 ]; then
            echo_info "✓ Topic $topic has $sub_count subscription(s)"
        else
            echo_warn "Topic $topic has no subscriptions"
        fi
    done
    
    return 0
}

# Validate storage buckets
validate_storage() {
    echo_validate "Validating Cloud Storage buckets..."
    
    local buckets=("${PROJECT_ID}-carla-data" "${PROJECT_ID}-models" "${PROJECT_ID}-results")
    
    for bucket in "${buckets[@]}"; do
        if gsutil ls -b gs://$bucket &> /dev/null; then
            echo_info "✓ Bucket gs://$bucket exists"
        else
            echo_error "✗ Bucket gs://$bucket not found"
            return 1
        fi
    done
    
    return 0
}

# Validate BigQuery dataset and tables
validate_bigquery() {
    echo_validate "Validating BigQuery dataset and tables..."
    
    local dataset_id="cars_with_a_life"
    
    # Check if dataset exists
    if bq show --dataset --project_id=$PROJECT_ID $dataset_id &> /dev/null; then
        echo_info "✓ BigQuery dataset $dataset_id exists"
    else
        echo_error "✗ BigQuery dataset $dataset_id not found"
        return 1
    fi
    
    # Check required tables
    local tables=("experiments" "autonomous_notes" "evaluation_metrics")
    
    for table in "${tables[@]}"; do
        if bq show --table --project_id=$PROJECT_ID ${dataset_id}.${table} &> /dev/null; then
            echo_info "✓ Table ${dataset_id}.${table} exists"
        else
            echo_warn "Table ${dataset_id}.${table} not found (may be created on first use)"
        fi
    done
    
    return 0
}

# Run comprehensive validation
run_full_validation() {
    echo_info "Starting comprehensive deployment validation..."
    
    local validation_results=()
    
    # Validate Cloud Run services
    for service in "${!CLOUD_RUN_SERVICES[@]}"; do
        if validate_cloud_run_service "$service" "${CLOUD_RUN_SERVICES[$service]}"; then
            validation_results+=("✓ Cloud Run: $service")
        else
            validation_results+=("✗ Cloud Run: $service")
        fi
    done
    
    # Validate Compute Engine instances
    for instance in "${!COMPUTE_INSTANCES[@]}"; do
        if validate_compute_instance "$instance" "${COMPUTE_INSTANCES[$instance]}"; then
            validation_results+=("✓ Compute Engine: $instance")
        else
            validation_results+=("✗ Compute Engine: $instance")
        fi
    done
    
    # Validate Vertex AI
    if validate_vertex_ai_endpoint; then
        validation_results+=("✓ Vertex AI: endpoint")
    else
        validation_results+=("✗ Vertex AI: endpoint")
    fi
    
    # Validate Pub/Sub
    if validate_pubsub; then
        validation_results+=("✓ Pub/Sub: topics and subscriptions")
    else
        validation_results+=("✗ Pub/Sub: topics and subscriptions")
    fi
    
    # Validate Storage
    if validate_storage; then
        validation_results+=("✓ Cloud Storage: buckets")
    else
        validation_results+=("✗ Cloud Storage: buckets")
    fi
    
    # Validate BigQuery
    if validate_bigquery; then
        validation_results+=("✓ BigQuery: dataset and tables")
    else
        validation_results+=("✗ BigQuery: dataset and tables")
    fi
    
    # Display results
    echo_info "Validation Results:"
    echo "==================="
    for result in "${validation_results[@]}"; do
        echo "$result"
    done
    
    # Check if any validation failed
    local failed_count=$(printf '%s\n' "${validation_results[@]}" | grep -c "✗" || true)
    
    if [ $failed_count -gt 0 ]; then
        echo_error "$failed_count validation(s) failed"
        return 1
    else
        echo_info "All validations passed successfully!"
        return 0
    fi
}

# Rollback Cloud Run service
rollback_cloud_run_service() {
    local service_name=$1
    local target_revision=$2
    
    echo_info "Rolling back Cloud Run service: $service_name"
    
    if [ -z "$target_revision" ]; then
        # Get previous revision
        target_revision=$(gcloud run revisions list \
            --service=$service_name \
            --region=$REGION \
            --project=$PROJECT_ID \
            --format="value(metadata.name)" \
            --limit=2 | tail -1)
    fi
    
    if [ -z "$target_revision" ]; then
        echo_error "No previous revision found for $service_name"
        return 1
    fi
    
    echo_info "Rolling back to revision: $target_revision"
    
    gcloud run services update-traffic $service_name \
        --to-revisions=$target_revision=100 \
        --region=$REGION \
        --project=$PROJECT_ID
    
    echo_info "Rollback completed for $service_name"
}

# Rollback Compute Engine instance
rollback_compute_instance() {
    local instance_name=$1
    local snapshot_name=$2
    
    echo_info "Rolling back Compute Engine instance: $instance_name"
    
    if [ -z "$snapshot_name" ]; then
        # Get latest snapshot
        snapshot_name=$(gcloud compute snapshots list \
            --filter="sourceDisk:$instance_name" \
            --sort-by="~creationTimestamp" \
            --format="value(name)" \
            --project=$PROJECT_ID \
            --limit=1)
    fi
    
    if [ -z "$snapshot_name" ]; then
        echo_error "No snapshot found for $instance_name"
        return 1
    fi
    
    echo_info "Rolling back to snapshot: $snapshot_name"
    
    # Stop instance
    gcloud compute instances stop $instance_name \
        --zone=$ZONE \
        --project=$PROJECT_ID
    
    # Create new disk from snapshot
    local new_disk_name="${instance_name}-rollback-$(date +%Y%m%d-%H%M%S)"
    gcloud compute disks create $new_disk_name \
        --source-snapshot=$snapshot_name \
        --zone=$ZONE \
        --project=$PROJECT_ID
    
    # Detach current disk and attach new one
    local current_disk=$(gcloud compute instances describe $instance_name \
        --zone=$ZONE \
        --project=$PROJECT_ID \
        --format="value(disks[0].deviceName)")
    
    gcloud compute instances detach-disk $instance_name \
        --disk=$current_disk \
        --zone=$ZONE \
        --project=$PROJECT_ID
    
    gcloud compute instances attach-disk $instance_name \
        --disk=$new_disk_name \
        --boot \
        --zone=$ZONE \
        --project=$PROJECT_ID
    
    # Start instance
    gcloud compute instances start $instance_name \
        --zone=$ZONE \
        --project=$PROJECT_ID
    
    echo_info "Rollback completed for $instance_name"
}

# Create deployment snapshot
create_deployment_snapshot() {
    local snapshot_name="deployment-snapshot-$(date +%Y%m%d-%H%M%S)"
    
    echo_info "Creating deployment snapshot: $snapshot_name"
    
    # Create snapshots for Compute Engine instances
    for instance in "${!COMPUTE_INSTANCES[@]}"; do
        local disk_name=$(gcloud compute instances describe $instance \
            --zone=$ZONE \
            --project=$PROJECT_ID \
            --format="value(disks[0].source)" | sed 's|.*/||')
        
        gcloud compute disks snapshot $disk_name \
            --snapshot-names="${snapshot_name}-${instance}" \
            --zone=$ZONE \
            --project=$PROJECT_ID &
    done
    
    # Wait for all snapshots to complete
    wait
    
    # Save Cloud Run service revisions
    local manifest_file="rollback-manifest-${snapshot_name}.json"
    echo "{" > "$manifest_file"
    echo "  \"snapshot_name\": \"$snapshot_name\"," >> "$manifest_file"
    echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$manifest_file"
    echo "  \"cloud_run_revisions\": {" >> "$manifest_file"
    
    local first=true
    for service in "${!CLOUD_RUN_SERVICES[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$manifest_file"
        fi
        
        local current_revision=$(gcloud run services describe $service \
            --region=$REGION \
            --project=$PROJECT_ID \
            --format="value(status.latestReadyRevisionName)" 2>/dev/null)
        
        echo "    \"$service\": \"$current_revision\"" >> "$manifest_file"
    done
    
    echo "  }," >> "$manifest_file"
    echo "  \"compute_snapshots\": {" >> "$manifest_file"
    
    first=true
    for instance in "${!COMPUTE_INSTANCES[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$manifest_file"
        fi
        
        echo "    \"$instance\": \"${snapshot_name}-${instance}\"" >> "$manifest_file"
    done
    
    echo "  }" >> "$manifest_file"
    echo "}" >> "$manifest_file"
    
    echo_info "Deployment snapshot created: $snapshot_name"
    echo_info "Rollback manifest saved: $manifest_file"
}

# Main function
main() {
    echo_info "Deployment Validator and Rollback Tool"
    
    local action="validate"
    local service_name=""
    local target_revision=""
    local snapshot_name=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --validate)
                action="validate"
                shift
                ;;
            --rollback)
                action="rollback"
                shift
                ;;
            --snapshot)
                action="snapshot"
                shift
                ;;
            --service)
                service_name="$2"
                shift 2
                ;;
            --revision)
                target_revision="$2"
                shift 2
                ;;
            --snapshot-name)
                snapshot_name="$2"
                shift 2
                ;;
            --project)
                PROJECT_ID="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Actions:"
                echo "  --validate              Run deployment validation (default)"
                echo "  --rollback              Rollback deployment"
                echo "  --snapshot              Create deployment snapshot"
                echo ""
                echo "Options:"
                echo "  --service SERVICE       Target specific service for rollback"
                echo "  --revision REVISION     Target revision for Cloud Run rollback"
                echo "  --snapshot-name NAME    Target snapshot for Compute Engine rollback"
                echo "  --project PROJECT_ID    GCP Project ID"
                echo "  --region REGION         GCP Region"
                echo "  --help                  Show this help"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    case $action in
        "validate")
            run_full_validation
            ;;
        "rollback")
            if [ -n "$service_name" ]; then
                if [[ -n "${CLOUD_RUN_SERVICES[$service_name]}" ]]; then
                    rollback_cloud_run_service "$service_name" "$target_revision"
                elif [[ -n "${COMPUTE_INSTANCES[$service_name]}" ]]; then
                    rollback_compute_instance "$service_name" "$snapshot_name"
                else
                    echo_error "Unknown service: $service_name"
                    exit 1
                fi
            else
                echo_error "Service name required for rollback. Use --service option."
                exit 1
            fi
            ;;
        "snapshot")
            create_deployment_snapshot
            ;;
        *)
            echo_error "Unknown action: $action"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"