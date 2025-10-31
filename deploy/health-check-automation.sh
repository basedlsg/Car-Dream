#!/usr/bin/env bash

# Health Check Automation Script
# Comprehensive health monitoring and validation for all system components

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
ZONE=${GCP_ZONE:-"us-central1-a"}

# Health check settings
HEALTH_CHECK_TIMEOUT=30
HEALTH_CHECK_INTERVAL=10
MAX_RETRY_ATTEMPTS=5
PARALLEL_CHECKS=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

echo_health() {
    echo -e "${BLUE}[HEALTH]${NC} $1"
}

echo_check() {
    echo -e "${PURPLE}[CHECK]${NC} $1"
}

# Service definitions with health check endpoints
declare -A CLOUD_RUN_SERVICES=(
    ["orchestrator"]="/health"
    ["reporter"]="/health"
)

declare -A COMPUTE_INSTANCES=(
    ["carla-runner-instance"]="8080"
)

declare -A VERTEX_AI_ENDPOINTS=(
    ["dreamerv3-autonomous-driving-endpoint"]="predict"
)

declare -A PUBSUB_TOPICS=(
    ["experiment-events"]="subscription"
    ["ai-decisions"]="subscription"
    ["model-metrics"]="subscription"
)

declare -A STORAGE_BUCKETS=(
    ["${PROJECT_ID}-carla-data"]="read"
    ["${PROJECT_ID}-models"]="read"
    ["${PROJECT_ID}-results"]="write"
)

# Health check results tracking
declare -A HEALTH_RESULTS=()
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# Log health check event
log_health_event() {
    local component=$1
    local status=$2
    local message=$3
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    echo "{\"timestamp\":\"$timestamp\",\"component\":\"$component\",\"status\":\"$status\",\"message\":\"$message\"}" >> "health-check-$(date +%Y%m%d).log"
}

# Generic health check with retry logic
perform_health_check() {
    local component=$1
    local check_function=$2
    local max_attempts=${3:-$MAX_RETRY_ATTEMPTS}
    
    echo_check "Checking health of: $component"
    
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if [ $attempt -gt 1 ]; then
            echo_check "Retry attempt $attempt/$max_attempts for $component"
            sleep $HEALTH_CHECK_INTERVAL
        fi
        
        if $check_function "$component"; then
            echo_info "✓ $component is healthy"
            HEALTH_RESULTS["$component"]="HEALTHY"
            log_health_event "$component" "healthy" "Health check passed"
            ((PASSED_CHECKS++))
            return 0
        fi
        
        ((attempt++))
    done
    
    echo_error "✗ $component is unhealthy after $max_attempts attempts"
    HEALTH_RESULTS["$component"]="UNHEALTHY"
    log_health_event "$component" "unhealthy" "Health check failed after $max_attempts attempts"
    ((FAILED_CHECKS++))
    return 1
}

# Cloud Run service health check
check_cloud_run_health() {
    local service_name=$1
    local health_endpoint=${CLOUD_RUN_SERVICES[$service_name]}
    
    # Get service URL
    local service_url=$(gcloud run services describe $service_name \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.url)" 2>/dev/null)
    
    if [ -z "$service_url" ]; then
        echo_error "Service $service_name not found"
        return 1
    fi
    
    # Check service status
    local service_status=$(gcloud run services describe $service_name \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.conditions[0].status)" 2>/dev/null)
    
    if [ "$service_status" != "True" ]; then
        echo_error "Service $service_name is not ready. Status: $service_status"
        return 1
    fi
    
    # Health endpoint check
    local health_url="${service_url}${health_endpoint}"
    local response=$(curl -f -s --max-time $HEALTH_CHECK_TIMEOUT "$health_url" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Parse health response if it's JSON
        if echo "$response" | jq . >/dev/null 2>&1; then
            local status=$(echo "$response" | jq -r '.status // "unknown"')
            local version=$(echo "$response" | jq -r '.version // "unknown"')
            echo_health "$service_name status: $status, version: $version"
        fi
        return 0
    else
        echo_error "Health endpoint $health_url is not responding"
        return 1
    fi
}

# Compute Engine instance health check
check_compute_instance_health() {
    local instance_name=$1
    local port=${COMPUTE_INSTANCES[$instance_name]}
    
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
    
    # Port connectivity and health endpoint check
    if timeout $HEALTH_CHECK_TIMEOUT bash -c "</dev/tcp/$external_ip/$port" 2>/dev/null; then
        # Try to get health information from the service
        local health_response=$(curl -f -s --max-time $HEALTH_CHECK_TIMEOUT "http://$external_ip:$port/health" 2>/dev/null || echo "")
        
        if [ -n "$health_response" ]; then
            echo_health "$instance_name health response: $health_response"
        fi
        
        return 0
    else
        echo_error "Port $port is not accessible on $instance_name ($external_ip)"
        return 1
    fi
}

# Vertex AI endpoint health check
check_vertex_ai_health() {
    local endpoint_name=$1
    
    # Get endpoint ID
    local endpoint_id=$(gcloud ai endpoints list \
        --region=$REGION \
        --filter="displayName:${endpoint_name}" \
        --format="value(name)" \
        --project=$PROJECT_ID | head -1)
    
    if [ -z "$endpoint_id" ]; then
        echo_error "Vertex AI endpoint $endpoint_name not found"
        return 1
    fi
    
    # Check endpoint status and deployed models
    local deployed_models=$(gcloud ai endpoints describe $endpoint_id \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(deployedModels[].displayName)" 2>/dev/null)
    
    if [ -z "$deployed_models" ]; then
        echo_error "No models deployed to endpoint $endpoint_name"
        return 1
    fi
    
    echo_health "$endpoint_name has deployed models: $deployed_models"
    
    # Test prediction capability with a simple request
    local test_prediction=$(gcloud ai endpoints predict $endpoint_id \
        --region=$REGION \
        --json-request='{"instances": [{"test": true}]}' \
        --project=$PROJECT_ID 2>/dev/null || echo "")
    
    if [ -n "$test_prediction" ]; then
        echo_health "$endpoint_name prediction test successful"
        return 0
    else
        echo_warn "$endpoint_name prediction test failed (may be expected for some models)"
        return 0  # Don't fail on prediction test as it may require specific input format
    fi
}

# Pub/Sub health check
check_pubsub_health() {
    local topic_name=$1
    
    # Check if topic exists
    if ! gcloud pubsub topics describe $topic_name --project=$PROJECT_ID &>/dev/null; then
        echo_error "Pub/Sub topic $topic_name not found"
        return 1
    fi
    
    # Check subscriptions
    local subscription_count=$(gcloud pubsub subscriptions list \
        --filter="topic:projects/$PROJECT_ID/topics/$topic_name" \
        --project=$PROJECT_ID \
        --format="value(name)" | wc -l)
    
    if [ $subscription_count -eq 0 ]; then
        echo_warn "Topic $topic_name has no subscriptions"
    else
        echo_health "$topic_name has $subscription_count subscription(s)"
    fi
    
    # Test message publishing
    local test_message="{\"test\": true, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
    if gcloud pubsub topics publish $topic_name \
        --message="$test_message" \
        --project=$PROJECT_ID &>/dev/null; then
        echo_health "$topic_name message publishing test successful"
        return 0
    else
        echo_error "$topic_name message publishing test failed"
        return 1
    fi
}

# Storage bucket health check
check_storage_health() {
    local bucket_name=$1
    local access_type=${STORAGE_BUCKETS[$bucket_name]}
    
    # Check if bucket exists
    if ! gsutil ls -b gs://$bucket_name &>/dev/null; then
        echo_error "Storage bucket gs://$bucket_name not found"
        return 1
    fi
    
    # Test read access
    local object_count=$(gsutil ls gs://$bucket_name | wc -l)
    echo_health "Bucket gs://$bucket_name contains $object_count objects"
    
    # Test write access if required
    if [ "$access_type" = "write" ]; then
        local test_file="/tmp/health-check-$(date +%s).txt"
        echo "Health check test file created at $(date)" > "$test_file"
        
        if gsutil cp "$test_file" "gs://$bucket_name/health-checks/" &>/dev/null; then
            echo_health "Write test successful for gs://$bucket_name"
            gsutil rm "gs://$bucket_name/health-checks/$(basename $test_file)" &>/dev/null || true
        else
            echo_error "Write test failed for gs://$bucket_name"
            rm -f "$test_file"
            return 1
        fi
        
        rm -f "$test_file"
    fi
    
    return 0
}

# BigQuery health check
check_bigquery_health() {
    local dataset_id="cars_with_a_life"
    
    echo_check "Checking BigQuery dataset: $dataset_id"
    
    # Check if dataset exists
    if ! bq show --dataset --project_id=$PROJECT_ID $dataset_id &>/dev/null; then
        echo_error "BigQuery dataset $dataset_id not found"
        return 1
    fi
    
    # List tables
    local table_count=$(bq ls --project_id=$PROJECT_ID $dataset_id | grep -c "TABLE" || echo "0")
    echo_health "Dataset $dataset_id contains $table_count tables"
    
    # Test query execution
    local test_query="SELECT 1 as health_check"
    if bq query --use_legacy_sql=false --project_id=$PROJECT_ID "$test_query" &>/dev/null; then
        echo_health "BigQuery query test successful"
        return 0
    else
        echo_error "BigQuery query test failed"
        return 1
    fi
}

# Network connectivity health check
check_network_health() {
    echo_check "Checking network connectivity"
    
    # Test external connectivity
    if ping -c 3 8.8.8.8 &>/dev/null; then
        echo_health "External network connectivity: OK"
    else
        echo_error "External network connectivity: FAILED"
        return 1
    fi
    
    # Test Google Cloud API connectivity
    if gcloud projects describe $PROJECT_ID &>/dev/null; then
        echo_health "Google Cloud API connectivity: OK"
    else
        echo_error "Google Cloud API connectivity: FAILED"
        return 1
    fi
    
    return 0
}

# Run all health checks
run_comprehensive_health_check() {
    echo_health "Starting comprehensive health check..."
    echo_health "Project: $PROJECT_ID"
    echo_health "Region: $REGION"
    echo_health "Timestamp: $(date)"
    echo ""
    
    # Initialize counters
    TOTAL_CHECKS=0
    PASSED_CHECKS=0
    FAILED_CHECKS=0
    
    # Network health check
    ((TOTAL_CHECKS++))
    perform_health_check "network" check_network_health
    
    # BigQuery health check
    ((TOTAL_CHECKS++))
    perform_health_check "bigquery" check_bigquery_health
    
    # Cloud Run services
    for service in "${!CLOUD_RUN_SERVICES[@]}"; do
        ((TOTAL_CHECKS++))
        perform_health_check "cloud-run-$service" check_cloud_run_health "$service"
    done
    
    # Compute Engine instances
    for instance in "${!COMPUTE_INSTANCES[@]}"; do
        ((TOTAL_CHECKS++))
        perform_health_check "compute-$instance" check_compute_instance_health "$instance"
    done
    
    # Vertex AI endpoints
    for endpoint in "${!VERTEX_AI_ENDPOINTS[@]}"; do
        ((TOTAL_CHECKS++))
        perform_health_check "vertex-ai-$endpoint" check_vertex_ai_health "$endpoint"
    done
    
    # Pub/Sub topics
    for topic in "${!PUBSUB_TOPICS[@]}"; do
        ((TOTAL_CHECKS++))
        perform_health_check "pubsub-$topic" check_pubsub_health "$topic"
    done
    
    # Storage buckets
    for bucket in "${!STORAGE_BUCKETS[@]}"; do
        ((TOTAL_CHECKS++))
        perform_health_check "storage-$bucket" check_storage_health "$bucket"
    done
    
    # Display results
    display_health_summary
    
    # Return appropriate exit code
    if [ $FAILED_CHECKS -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# Display health check summary
display_health_summary() {
    echo ""
    echo_health "Health Check Summary"
    echo "===================="
    echo "Total Checks: $TOTAL_CHECKS"
    echo "Passed: $PASSED_CHECKS"
    echo "Failed: $FAILED_CHECKS"
    echo "Success Rate: $(( PASSED_CHECKS * 100 / TOTAL_CHECKS ))%"
    echo ""
    
    if [ $FAILED_CHECKS -gt 0 ]; then
        echo_error "Failed Components:"
        for component in "${!HEALTH_RESULTS[@]}"; do
            if [ "${HEALTH_RESULTS[$component]}" = "UNHEALTHY" ]; then
                echo "  ✗ $component"
            fi
        done
        echo ""
    fi
    
    echo_info "Healthy Components:"
    for component in "${!HEALTH_RESULTS[@]}"; do
        if [ "${HEALTH_RESULTS[$component]}" = "HEALTHY" ]; then
            echo "  ✓ $component"
        fi
    done
    
    echo ""
    echo "Health check log: health-check-$(date +%Y%m%d).log"
}

# Generate health check report
generate_health_report() {
    local report_file="health-report-$(date +%Y%m%d-%H%M%S).json"
    
    echo_health "Generating health check report: $report_file"
    
    cat > "$report_file" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "project_id": "$PROJECT_ID",
  "region": "$REGION",
  "zone": "$ZONE",
  "summary": {
    "total_checks": $TOTAL_CHECKS,
    "passed_checks": $PASSED_CHECKS,
    "failed_checks": $FAILED_CHECKS,
    "success_rate": $(( PASSED_CHECKS * 100 / TOTAL_CHECKS ))
  },
  "components": {
EOF
    
    local first=true
    for component in "${!HEALTH_RESULTS[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$report_file"
        fi
        
        echo "    \"$component\": \"${HEALTH_RESULTS[$component]}\"" >> "$report_file"
    done
    
    cat >> "$report_file" << EOF
  },
  "recommendations": [
EOF
    
    # Add recommendations based on failed checks
    local recommendations=()
    for component in "${!HEALTH_RESULTS[@]}"; do
        if [ "${HEALTH_RESULTS[$component]}" = "UNHEALTHY" ]; then
            case $component in
                *cloud-run*)
                    recommendations+=("\"Check Cloud Run service logs and configuration\"")
                    ;;
                *compute*)
                    recommendations+=("\"Verify Compute Engine instance status and network connectivity\"")
                    ;;
                *vertex-ai*)
                    recommendations+=("\"Check Vertex AI endpoint deployment and model status\"")
                    ;;
                *pubsub*)
                    recommendations+=("\"Verify Pub/Sub topic configuration and permissions\"")
                    ;;
                *storage*)
                    recommendations+=("\"Check Cloud Storage bucket permissions and network access\"")
                    ;;
            esac
        fi
    done
    
    # Add general recommendations
    if [ $FAILED_CHECKS -gt 0 ]; then
        recommendations+=("\"Review deployment logs for error details\"")
        recommendations+=("\"Check IAM permissions and service account configurations\"")
        recommendations+=("\"Verify network connectivity and firewall rules\"")
    fi
    
    # Output recommendations
    local first=true
    for rec in "${recommendations[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$report_file"
        fi
        echo "    $rec" >> "$report_file"
    done
    
    cat >> "$report_file" << EOF
  ]
}
EOF
    
    echo_info "Health check report generated: $report_file"
}

# Main function
main() {
    local action="check"
    local component=""
    local continuous=false
    local interval=300  # 5 minutes
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --check)
                action="check"
                shift
                ;;
            --component)
                component="$2"
                shift 2
                ;;
            --continuous)
                continuous=true
                shift
                ;;
            --interval)
                interval="$2"
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
            --zone)
                ZONE="$2"
                shift 2
                ;;
            --timeout)
                HEALTH_CHECK_TIMEOUT="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Actions:"
                echo "  --check                  Run health checks (default)"
                echo ""
                echo "Options:"
                echo "  --component COMPONENT    Check specific component only"
                echo "  --continuous             Run continuous health monitoring"
                echo "  --interval SECONDS       Interval for continuous monitoring (default: 300)"
                echo "  --project PROJECT_ID     GCP Project ID"
                echo "  --region REGION          GCP Region"
                echo "  --zone ZONE             GCP Zone"
                echo "  --timeout SECONDS        Health check timeout (default: 30)"
                echo "  --help                   Show this help"
                echo ""
                echo "Examples:"
                echo "  $0 --check"
                echo "  $0 --component cloud-run-orchestrator"
                echo "  $0 --continuous --interval 60"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Validate project access
    if ! gcloud projects describe $PROJECT_ID &>/dev/null; then
        echo_error "Cannot access project $PROJECT_ID. Check project ID and authentication."
        exit 1
    fi
    
    # Execute action
    case $action in
        "check")
            if [ -n "$component" ]; then
                echo_health "Running health check for component: $component"
                # Component-specific health check logic would go here
                echo_warn "Component-specific checks not yet implemented"
            else
                if [ "$continuous" = true ]; then
                    echo_health "Starting continuous health monitoring (interval: ${interval}s)"
                    while true; do
                        run_comprehensive_health_check
                        generate_health_report
                        echo_health "Next check in ${interval} seconds..."
                        sleep $interval
                    done
                else
                    run_comprehensive_health_check
                    generate_health_report
                fi
            fi
            ;;
        *)
            echo_error "Unknown action: $action"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"