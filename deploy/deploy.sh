#!/bin/bash

# Cars with a Life - Master Deployment Automation Script
# Complete deployment orchestration with environment-specific configuration management
# and comprehensive validation and health check automation

set -e

# Configuration with environment-specific defaults
ENVIRONMENT=${ENVIRONMENT:-"development"}
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life-${ENVIRONMENT}"}
REGION=${GCP_REGION:-"us-central1"}
ZONE=${GCP_ZONE:-"us-central1-a"}
VERSION=${BUILD_VERSION:-$(date +%Y%m%d-%H%M%S)}

# Environment-specific configurations
declare -A ENV_CONFIGS=(
    ["development_min_instances"]="1"
    ["development_max_instances"]="3"
    ["development_machine_type"]="e2-standard-4"
    ["development_gpu_type"]="nvidia-tesla-t4"
    ["development_gpu_count"]="1"
    ["development_disk_size"]="100GB"
    ["development_enable_monitoring"]="basic"
    ["development_backup_retention"]="7d"
    
    ["staging_min_instances"]="1"
    ["staging_max_instances"]="5"
    ["staging_machine_type"]="n1-standard-8"
    ["staging_gpu_type"]="nvidia-tesla-t4"
    ["staging_gpu_count"]="1"
    ["staging_disk_size"]="200GB"
    ["staging_enable_monitoring"]="full"
    ["staging_backup_retention"]="14d"
    
    ["production_min_instances"]="2"
    ["production_max_instances"]="10"
    ["production_machine_type"]="n1-standard-16"
    ["production_gpu_type"]="nvidia-tesla-v100"
    ["production_gpu_count"]="2"
    ["production_disk_size"]="500GB"
    ["production_enable_monitoring"]="full"
    ["production_backup_retention"]="30d"
)

# Deployment phases
DEPLOYMENT_PHASES=(
    "prerequisites"
    "infrastructure"
    "services"
    "validation"
    "monitoring"
)

# Rollback configuration
ENABLE_ROLLBACK=${ENABLE_ROLLBACK:-"true"}
ROLLBACK_ON_FAILURE=${ROLLBACK_ON_FAILURE:-"true"}
DEPLOYMENT_TIMEOUT=${DEPLOYMENT_TIMEOUT:-"3600"}  # 1 hour

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
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

echo_deploy() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

echo_phase() {
    echo -e "${PURPLE}[PHASE]${NC} $1"
}

echo_validate() {
    echo -e "${CYAN}[VALIDATE]${NC} $1"
}

# Logging functions
log_deployment_event() {
    local event_type=$1
    local message=$2
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    echo "{\"timestamp\":\"$timestamp\",\"environment\":\"$ENVIRONMENT\",\"event\":\"$event_type\",\"message\":\"$message\"}" >> "deployment-${VERSION}.log"
}

# Environment configuration functions
get_env_config() {
    local config_key="${ENVIRONMENT}_$1"
    echo "${ENV_CONFIGS[$config_key]:-$2}"  # Return default if not found
}

validate_environment() {
    echo_phase "Validating environment configuration: $ENVIRONMENT"
    
    case $ENVIRONMENT in
        "development"|"staging"|"production")
            echo_info "Environment '$ENVIRONMENT' is valid"
            ;;
        *)
            echo_error "Invalid environment: $ENVIRONMENT. Must be one of: development, staging, production"
            exit 1
            ;;
    esac
    
    # Validate required environment variables
    local required_vars=("PROJECT_ID" "REGION" "ZONE")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo_error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    log_deployment_event "environment_validated" "Environment $ENVIRONMENT validated successfully"
}

# Prerequisites validation
validate_prerequisites() {
    echo_phase "Validating deployment prerequisites"
    
    local missing_tools=()
    
    # Check required tools
    local required_tools=("gcloud" "docker" "terraform" "kubectl" "bq" "gsutil")
    for tool in "${required_tools[@]}"; do
        if ! command -v $tool &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo_error "Missing required tools: ${missing_tools[*]}"
        echo_info "Please install the missing tools and try again"
        exit 1
    fi
    
    # Check gcloud authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        echo_error "Docker daemon is not running"
        exit 1
    fi
    
    # Validate project access
    if ! gcloud projects describe $PROJECT_ID &> /dev/null; then
        echo_error "Cannot access project $PROJECT_ID. Check project ID and permissions."
        exit 1
    fi
    
    echo_info "All prerequisites validated successfully"
    log_deployment_event "prerequisites_validated" "All deployment prerequisites validated"
}

# Deployment phase tracking
start_deployment_phase() {
    local phase_name=$1
    echo_phase "Starting deployment phase: $phase_name"
    log_deployment_event "phase_started" "Deployment phase '$phase_name' started"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "/tmp/phase_${phase_name}_start"
}

complete_deployment_phase() {
    local phase_name=$1
    local start_time=$(cat "/tmp/phase_${phase_name}_start" 2>/dev/null || echo "")
    local end_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    if [ -n "$start_time" ]; then
        local duration=$(($(date -d "$end_time" +%s) - $(date -d "$start_time" +%s)))
        echo_phase "Completed deployment phase: $phase_name (${duration}s)"
        log_deployment_event "phase_completed" "Deployment phase '$phase_name' completed in ${duration}s"
    else
        echo_phase "Completed deployment phase: $phase_name"
        log_deployment_event "phase_completed" "Deployment phase '$phase_name' completed"
    fi
    
    rm -f "/tmp/phase_${phase_name}_start"
}

# Enhanced error handling with rollback capability
handle_deployment_error() {
    local exit_code=$1
    local phase=$2
    local error_message=$3
    
    echo_error "Deployment failed in phase '$phase': $error_message"
    log_deployment_event "deployment_failed" "Phase '$phase' failed: $error_message"
    
    if [ "$ROLLBACK_ON_FAILURE" = "true" ] && [ "$ENABLE_ROLLBACK" = "true" ]; then
        echo_warn "Initiating automatic rollback..."
        initiate_rollback "$phase"
    fi
    
    cleanup_deployment
    exit $exit_code
}

# Rollback functionality
initiate_rollback() {
    local failed_phase=$1
    
    echo_warn "Rolling back deployment from phase: $failed_phase"
    log_deployment_event "rollback_started" "Rollback initiated from phase '$failed_phase'"
    
    # Rollback based on the phase that failed
    case $failed_phase in
        "services")
            echo_warn "Rolling back service deployments..."
            ./deploy/deployment-validator.sh --rollback --service orchestrator --project $PROJECT_ID --region $REGION || true
            ./deploy/deployment-validator.sh --rollback --service reporter --project $PROJECT_ID --region $REGION || true
            ./deploy/deployment-validator.sh --rollback --service carla-runner-instance --project $PROJECT_ID --region $REGION || true
            ;;
        "infrastructure")
            echo_warn "Rolling back infrastructure changes..."
            cd infrastructure/terraform
            terraform destroy -auto-approve -var="project_id=$PROJECT_ID" -var="region=$REGION" -var="zone=$ZONE" || true
            cd ../..
            ;;
        *)
            echo_warn "Manual rollback may be required for phase: $failed_phase"
            ;;
    esac
    
    log_deployment_event "rollback_completed" "Rollback completed for phase '$failed_phase'"
}

# Cleanup function
cleanup_deployment() {
    echo_info "Cleaning up deployment artifacts..."
    rm -f /tmp/phase_*_start
    rm -f /tmp/*_channel_id
    rm -f /tmp/*-alert.json
    rm -f /tmp/*_url
}

# Deployment timeout handler
setup_deployment_timeout() {
    if [ "$DEPLOYMENT_TIMEOUT" -gt 0 ]; then
        (
            sleep $DEPLOYMENT_TIMEOUT
            echo_error "Deployment timeout reached (${DEPLOYMENT_TIMEOUT}s)"
            log_deployment_event "deployment_timeout" "Deployment exceeded timeout of ${DEPLOYMENT_TIMEOUT}s"
            kill -TERM $$ 2>/dev/null || true
        ) &
        TIMEOUT_PID=$!
        trap "kill $TIMEOUT_PID 2>/dev/null || true" EXIT
    fi
}

# Deploy prerequisites phase
deploy_prerequisites() {
    start_deployment_phase "prerequisites"
    
    echo_deploy "Setting up deployment prerequisites..."
    
    # Set project
    gcloud config set project $PROJECT_ID
    
    # Enable required APIs with retry logic
    echo_info "Enabling required APIs..."
    local apis=(
        "compute.googleapis.com"
        "run.googleapis.com"
        "aiplatform.googleapis.com"
        "storage.googleapis.com"
        "pubsub.googleapis.com"
        "cloudbuild.googleapis.com"
        "artifactregistry.googleapis.com"
        "bigquery.googleapis.com"
        "cloudscheduler.googleapis.com"
        "monitoring.googleapis.com"
        "logging.googleapis.com"
        "cloudresourcemanager.googleapis.com"
    )
    
    for api in "${apis[@]}"; do
        echo_info "Enabling $api..."
        if ! gcloud services enable $api --project=$PROJECT_ID; then
            handle_deployment_error 1 "prerequisites" "Failed to enable API: $api"
        fi
    done
    
    # Setup Artifact Registry
    echo_deploy "Setting up Artifact Registry..."
    if ! ./deploy/setup-artifact-registry.sh --project $PROJECT_ID --region $REGION; then
        handle_deployment_error 1 "prerequisites" "Failed to setup Artifact Registry"
    fi
    
    # Build and push all containers
    echo_deploy "Building and pushing containers..."
    local build_args="--project $PROJECT_ID --region $REGION --version $VERSION"
    
    # Add environment-specific build optimizations
    if [ "$ENVIRONMENT" = "development" ]; then
        build_args="$build_args --cleanup"  # Clean up old images in dev
    fi
    
    if ! ./deploy/build-and-push-containers.sh $build_args; then
        handle_deployment_error 1 "prerequisites" "Failed to build and push containers"
    fi
    
    complete_deployment_phase "prerequisites"
}

# Deploy infrastructure phase
deploy_infrastructure() {
    start_deployment_phase "infrastructure"
    
    echo_deploy "Deploying infrastructure components..."
    
    # Create deployment snapshot before infrastructure changes
    if [ "$ENABLE_ROLLBACK" = "true" ]; then
        echo_deploy "Creating pre-deployment snapshot..."
        ./deploy/deployment-validator.sh --snapshot --project $PROJECT_ID --region $REGION || echo_warn "Snapshot creation failed (may be first deployment)"
    fi
    
    # Deploy infrastructure using Terraform with environment-specific variables
    echo_deploy "Deploying infrastructure with Terraform..."
    cd infrastructure/terraform
    
    # Initialize Terraform
    if ! terraform init; then
        cd ../..
        handle_deployment_error 1 "infrastructure" "Terraform initialization failed"
    fi
    
    # Create terraform variables file with environment-specific values
    cat > terraform.tfvars << EOF
project_id = "$PROJECT_ID"
region = "$REGION"
zone = "$ZONE"
environment = "$ENVIRONMENT"
machine_type = "$(get_env_config "machine_type" "e2-standard-4")"
gpu_type = "$(get_env_config "gpu_type" "nvidia-tesla-t4")"
gpu_count = $(get_env_config "gpu_count" "1")
disk_size = "$(get_env_config "disk_size" "100GB")"
min_instances = $(get_env_config "min_instances" "1")
max_instances = $(get_env_config "max_instances" "3")
EOF
    
    # Plan and apply
    if ! terraform plan -var-file=terraform.tfvars; then
        cd ../..
        handle_deployment_error 1 "infrastructure" "Terraform planning failed"
    fi
    
    if ! terraform apply -auto-approve -var-file=terraform.tfvars; then
        cd ../..
        handle_deployment_error 1 "infrastructure" "Terraform apply failed"
    fi
    
    cd ../..
    
    # Setup networking and authentication
    echo_deploy "Setting up networking and authentication..."
    if ! ./deploy/setup-networking.sh --project $PROJECT_ID --region $REGION --zone $ZONE; then
        handle_deployment_error 1 "infrastructure" "Failed to setup networking"
    fi
    
    # Setup Pub/Sub messaging infrastructure
    echo_deploy "Setting up Pub/Sub messaging..."
    if ! ./deploy/setup-pubsub.sh --project $PROJECT_ID --region $REGION; then
        handle_deployment_error 1 "infrastructure" "Failed to setup Pub/Sub"
    fi
    
    # Setup data infrastructure (BigQuery and Cloud Storage)
    echo_deploy "Setting up data infrastructure..."
    if ! ./deploy/setup-bigquery.sh --project $PROJECT_ID --region $REGION; then
        handle_deployment_error 1 "infrastructure" "Failed to setup BigQuery"
    fi
    
    complete_deployment_phase "infrastructure"
}

# Deploy services phase
deploy_services() {
    start_deployment_phase "services"
    
    echo_deploy "Deploying application services..."
    
    # Deploy Compute Engine resources with monitoring
    echo_deploy "Deploying Compute Engine resources..."
    local compute_args="--project $PROJECT_ID --region $REGION --zone $ZONE --version $VERSION"
    compute_args="$compute_args --machine-type $(get_env_config "machine_type" "e2-standard-4")"
    compute_args="$compute_args --gpu-type $(get_env_config "gpu_type" "nvidia-tesla-t4")"
    
    if ! ./deploy/deploy-compute-resources.sh $compute_args; then
        handle_deployment_error 1 "services" "Failed to deploy Compute Engine resources"
    fi
    
    # Deploy Vertex AI resources with auto-scaling
    echo_deploy "Deploying Vertex AI resources..."
    if ! ./deploy/deploy-vertex-ai.sh --project $PROJECT_ID --region $REGION --version $VERSION; then
        handle_deployment_error 1 "services" "Failed to deploy Vertex AI resources"
    fi
    
    # Deploy Cloud Run services with advanced configuration
    echo_deploy "Deploying Cloud Run services..."
    if ! ./deploy/deploy-cloud-run-services.sh --project $PROJECT_ID --region $REGION --version $VERSION; then
        handle_deployment_error 1 "services" "Failed to deploy Cloud Run services"
    fi
    
    complete_deployment_phase "services"
}

# Validation phase
deploy_validation() {
    start_deployment_phase "validation"
    
    echo_deploy "Running comprehensive deployment validation..."
    
    # Wait for services to be ready
    echo_validate "Waiting for services to initialize..."
    sleep 30
    
    # Run deployment validation with retries
    local validation_attempts=3
    local attempt=1
    
    while [ $attempt -le $validation_attempts ]; do
        echo_validate "Validation attempt $attempt/$validation_attempts..."
        
        if ./deploy/deployment-validator.sh --validate --project $PROJECT_ID --region $REGION; then
            echo_info "✓ Deployment validation passed"
            break
        else
            if [ $attempt -eq $validation_attempts ]; then
                handle_deployment_error 1 "validation" "Deployment validation failed after $validation_attempts attempts"
            else
                echo_warn "Validation attempt $attempt failed, retrying in 30 seconds..."
                sleep 30
                ((attempt++))
            fi
        fi
    done
    
    complete_deployment_phase "validation"
}

# Monitoring phase
deploy_monitoring() {
    start_deployment_phase "monitoring"
    
    echo_deploy "Setting up monitoring and operational tools..."
    
    # Setup comprehensive monitoring and auto-scaling
    local monitoring_level=$(get_env_config "enable_monitoring" "basic")
    local monitoring_args="--project $PROJECT_ID --region $REGION --zone $ZONE"
    
    if [ "$monitoring_level" = "full" ]; then
        monitoring_args="$monitoring_args --email ${NOTIFICATION_EMAIL:-admin@${PROJECT_ID}.com}"
        if [ -n "$SLACK_WEBHOOK" ]; then
            monitoring_args="$monitoring_args --slack-webhook $SLACK_WEBHOOK"
        fi
    fi
    
    if ! ./deploy/setup-monitoring.sh $monitoring_args; then
        handle_deployment_error 1 "monitoring" "Failed to setup monitoring"
    fi
    
    # Setup Cloud Scheduler for automated experiments
    echo_deploy "Setting up Cloud Scheduler..."
    if ! ./deploy/setup-scheduler.sh --project $PROJECT_ID --region $REGION; then
        handle_deployment_error 1 "monitoring" "Failed to setup Cloud Scheduler"
    fi
    
    # Setup scheduler monitoring and alerting
    echo_deploy "Setting up scheduler monitoring..."
    if ! ./deploy/setup-scheduler-monitoring.sh --project $PROJECT_ID --region $REGION; then
        handle_deployment_error 1 "monitoring" "Failed to setup scheduler monitoring"
    fi
    
    complete_deployment_phase "monitoring"
}

# Main deployment orchestration
run_deployment() {
    echo_deploy "Cars with a Life - Master Deployment Automation"
    echo "=================================================="
    echo "Environment: $ENVIRONMENT"
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Zone: $ZONE"
    echo "Version: $VERSION"
    echo "Rollback Enabled: $ENABLE_ROLLBACK"
    echo ""
    
    log_deployment_event "deployment_started" "Master deployment started for environment $ENVIRONMENT"
    
    # Setup deployment timeout
    setup_deployment_timeout
    
    # Execute deployment phases
    for phase in "${DEPLOYMENT_PHASES[@]}"; do
        case $phase in
            "prerequisites")
                deploy_prerequisites
                ;;
            "infrastructure")
                deploy_infrastructure
                ;;
            "services")
                deploy_services
                ;;
            "validation")
                deploy_validation
                ;;
            "monitoring")
                deploy_monitoring
                ;;
        esac
    done
    
    # Final deployment summary
    display_deployment_summary
    
    log_deployment_event "deployment_completed" "Master deployment completed successfully"
    cleanup_deployment
}

# Display comprehensive deployment summary
display_deployment_summary() {
    echo_info "Deployment completed successfully!"
    echo ""
    echo "Deployment Summary:"
    echo "=================="
    echo "Environment: $ENVIRONMENT"
    echo "Version: $VERSION"
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Deployment Log: deployment-${VERSION}.log"
    echo ""
    echo "Deployed Components:"
    echo "  ✓ Infrastructure (Terraform)"
    echo "  ✓ CARLA Runner (Compute Engine)"
    echo "  ✓ DreamerV3 Service (Vertex AI)"
    echo "  ✓ Orchestrator Service (Cloud Run)"
    echo "  ✓ Reporter Service (Cloud Run)"
    echo "  ✓ Data Infrastructure (BigQuery, Cloud Storage)"
    echo "  ✓ Messaging (Pub/Sub)"
    echo "  ✓ Monitoring and Alerting"
    echo "  ✓ Automated Scheduling"
    echo ""
    echo "Environment Configuration:"
    echo "  Machine Type: $(get_env_config "machine_type" "e2-standard-4")"
    echo "  GPU Type: $(get_env_config "gpu_type" "nvidia-tesla-t4")"
    echo "  Scaling: $(get_env_config "min_instances" "1")-$(get_env_config "max_instances" "3") instances"
    echo "  Monitoring: $(get_env_config "enable_monitoring" "basic")"
    echo "  Backup Retention: $(get_env_config "backup_retention" "7d")"
    echo ""
    echo "Useful Commands:"
    echo "  Validate: ./deploy/deployment-validator.sh --validate --project $PROJECT_ID --region $REGION"
    echo "  Rollback: ./deploy/deployment-validator.sh --rollback --service <service-name> --project $PROJECT_ID --region $REGION"
    echo "  Monitor: gcloud logging read 'resource.type=\"cloud_run_revision\"' --project $PROJECT_ID --limit 50"
    echo "  Dashboard: https://console.cloud.google.com/monitoring/dashboards?project=$PROJECT_ID"
    echo ""
    echo "Next Steps:"
    echo "  1. Verify all services are healthy in the Cloud Console"
    echo "  2. Run a test experiment to validate end-to-end functionality"
    echo "  3. Configure any additional monitoring or alerting as needed"
    echo "  4. Review the deployment log for detailed information"
}# Main func
tion
main() {
    echo_info "Cars with a Life - Master Deployment Automation"
    
    # Parse command line arguments
    local dry_run=false
    local skip_validation=false
    local force_deploy=false
    local target_phases=()
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --environment)
                ENVIRONMENT="$2"
                PROJECT_ID="${GCP_PROJECT_ID:-"cars-with-a-life-${ENVIRONMENT}"}"
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
            --version)
                VERSION="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --skip-validation)
                skip_validation=true
                shift
                ;;
            --force)
                force_deploy=true
                shift
                ;;
            --no-rollback)
                ENABLE_ROLLBACK="false"
                ROLLBACK_ON_FAILURE="false"
                shift
                ;;
            --timeout)
                DEPLOYMENT_TIMEOUT="$2"
                shift 2
                ;;
            --phase)
                target_phases+=("$2")
                shift 2
                ;;
            --notification-email)
                NOTIFICATION_EMAIL="$2"
                shift 2
                ;;
            --slack-webhook)
                SLACK_WEBHOOK="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Environment Options:"
                echo "  --environment ENV         Deployment environment (development|staging|production)"
                echo "  --project PROJECT_ID      GCP Project ID (overrides environment default)"
                echo "  --region REGION           GCP Region (default: us-central1)"
                echo "  --zone ZONE              GCP Zone (default: us-central1-a)"
                echo "  --version VERSION         Build version (default: timestamp)"
                echo ""
                echo "Deployment Options:"
                echo "  --dry-run                Show what would be deployed without executing"
                echo "  --skip-validation        Skip deployment validation phase"
                echo "  --force                  Force deployment even if validation fails"
                echo "  --no-rollback           Disable automatic rollback on failure"
                echo "  --timeout SECONDS        Deployment timeout in seconds (default: 3600)"
                echo "  --phase PHASE            Deploy specific phase only (can be repeated)"
                echo ""
                echo "Notification Options:"
                echo "  --notification-email EMAIL  Email for deployment notifications"
                echo "  --slack-webhook URL         Slack webhook for notifications"
                echo ""
                echo "Available Phases: ${DEPLOYMENT_PHASES[*]}"
                echo ""
                echo "Examples:"
                echo "  $0 --environment development"
                echo "  $0 --environment production --notification-email admin@company.com"
                echo "  $0 --phase infrastructure --phase services"
                echo "  $0 --dry-run --environment staging"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                echo_info "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Handle target phases
    if [ ${#target_phases[@]} -gt 0 ]; then
        echo_info "Deploying specific phases: ${target_phases[*]}"
        DEPLOYMENT_PHASES=("${target_phases[@]}")
    fi
    
    # Skip validation phase if requested
    if [ "$skip_validation" = true ]; then
        DEPLOYMENT_PHASES=(${DEPLOYMENT_PHASES[@]/validation})
    fi
    
    # Validate environment and prerequisites
    validate_environment
    validate_prerequisites
    
    # Dry run mode
    if [ "$dry_run" = true ]; then
        echo_info "DRY RUN MODE - No actual deployment will be performed"
        echo ""
        echo "Deployment Plan:"
        echo "==============="
        echo "Environment: $ENVIRONMENT"
        echo "Project: $PROJECT_ID"
        echo "Region: $REGION"
        echo "Zone: $ZONE"
        echo "Version: $VERSION"
        echo "Phases: ${DEPLOYMENT_PHASES[*]}"
        echo ""
        echo "Environment Configuration:"
        for config in machine_type gpu_type min_instances max_instances enable_monitoring; do
            echo "  $config: $(get_env_config "$config" "default")"
        done
        echo ""
        echo "Use the same command without --dry-run to execute the deployment"
        exit 0
    fi
    
    # Confirmation for production deployments
    if [ "$ENVIRONMENT" = "production" ] && [ "$force_deploy" != true ]; then
        echo_warn "You are about to deploy to PRODUCTION environment"
        echo_warn "Project: $PROJECT_ID"
        echo_warn "This will affect live systems and users"
        echo ""
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            echo_info "Deployment cancelled by user"
            exit 0
        fi
    fi
    
    # Execute deployment
    run_deployment
}

# Set up signal handlers for graceful shutdown
trap 'handle_deployment_error 130 "interrupted" "Deployment interrupted by user"; exit 130' INT TERM

# Run main function
main "$@"