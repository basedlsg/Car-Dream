#!/bin/bash

# Environment Configuration Management Script
# Manages environment-specific configurations for Cars with a Life deployment

set -e

# Configuration directory
CONFIG_DIR="deploy/configs"
TEMPLATE_DIR="deploy/templates"

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

echo_config() {
    echo -e "${BLUE}[CONFIG]${NC} $1"
}

# Environment configurations
declare -A ENVIRONMENT_CONFIGS=(
    # Development environment
    ["development_project_suffix"]="dev"
    ["development_machine_type"]="e2-standard-4"
    ["development_gpu_type"]="nvidia-tesla-t4"
    ["development_gpu_count"]="1"
    ["development_disk_size"]="100"
    ["development_min_instances"]="1"
    ["development_max_instances"]="3"
    ["development_cloud_run_memory"]="2Gi"
    ["development_cloud_run_cpu"]="2"
    ["development_cloud_run_concurrency"]="50"
    ["development_monitoring_level"]="basic"
    ["development_backup_retention_days"]="7"
    ["development_log_retention_days"]="30"
    ["development_enable_autoscaling"]="true"
    ["development_enable_preemptible"]="true"
    
    # Staging environment
    ["staging_project_suffix"]="staging"
    ["staging_machine_type"]="n1-standard-8"
    ["staging_gpu_type"]="nvidia-tesla-t4"
    ["staging_gpu_count"]="1"
    ["staging_disk_size"]="200"
    ["staging_min_instances"]="1"
    ["staging_max_instances"]="5"
    ["staging_cloud_run_memory"]="4Gi"
    ["staging_cloud_run_cpu"]="2"
    ["staging_cloud_run_concurrency"]="100"
    ["staging_monitoring_level"]="full"
    ["staging_backup_retention_days"]="14"
    ["staging_log_retention_days"]="60"
    ["staging_enable_autoscaling"]="true"
    ["staging_enable_preemptible"]="false"
    
    # Production environment
    ["production_project_suffix"]="prod"
    ["production_machine_type"]="n1-standard-16"
    ["production_gpu_type"]="nvidia-tesla-v100"
    ["production_gpu_count"]="2"
    ["production_disk_size"]="500"
    ["production_min_instances"]="2"
    ["production_max_instances"]="10"
    ["production_cloud_run_memory"]="8Gi"
    ["production_cloud_run_cpu"]="4"
    ["production_cloud_run_concurrency"]="200"
    ["production_monitoring_level"]="full"
    ["production_backup_retention_days"]="30"
    ["production_log_retention_days"]="90"
    ["production_enable_autoscaling"]="true"
    ["production_enable_preemptible"]="false"
)

# Create configuration directories
create_config_directories() {
    echo_config "Creating configuration directories..."
    
    mkdir -p "$CONFIG_DIR"/{development,staging,production}
    mkdir -p "$TEMPLATE_DIR"
    
    echo_info "Configuration directories created"
}

# Generate environment-specific configuration file
generate_environment_config() {
    local environment=$1
    local output_file="$CONFIG_DIR/$environment/config.env"
    
    echo_config "Generating configuration for environment: $environment"
    
    # Create environment configuration file
    cat > "$output_file" << EOF
# Cars with a Life - $environment Environment Configuration
# Generated on $(date)

# Environment identification
ENVIRONMENT=$environment
PROJECT_SUFFIX=${ENVIRONMENT_CONFIGS["${environment}_project_suffix"]}

# Compute resources
MACHINE_TYPE=${ENVIRONMENT_CONFIGS["${environment}_machine_type"]}
GPU_TYPE=${ENVIRONMENT_CONFIGS["${environment}_gpu_type"]}
GPU_COUNT=${ENVIRONMENT_CONFIGS["${environment}_gpu_count"]}
DISK_SIZE_GB=${ENVIRONMENT_CONFIGS["${environment}_disk_size"]}

# Scaling configuration
MIN_INSTANCES=${ENVIRONMENT_CONFIGS["${environment}_min_instances"]}
MAX_INSTANCES=${ENVIRONMENT_CONFIGS["${environment}_max_instances"]}
ENABLE_AUTOSCALING=${ENVIRONMENT_CONFIGS["${environment}_enable_autoscaling"]}
ENABLE_PREEMPTIBLE=${ENVIRONMENT_CONFIGS["${environment}_enable_preemptible"]}

# Cloud Run configuration
CLOUD_RUN_MEMORY=${ENVIRONMENT_CONFIGS["${environment}_cloud_run_memory"]}
CLOUD_RUN_CPU=${ENVIRONMENT_CONFIGS["${environment}_cloud_run_cpu"]}
CLOUD_RUN_CONCURRENCY=${ENVIRONMENT_CONFIGS["${environment}_cloud_run_concurrency"]}

# Monitoring and logging
MONITORING_LEVEL=${ENVIRONMENT_CONFIGS["${environment}_monitoring_level"]}
BACKUP_RETENTION_DAYS=${ENVIRONMENT_CONFIGS["${environment}_backup_retention_days"]}
LOG_RETENTION_DAYS=${ENVIRONMENT_CONFIGS["${environment}_log_retention_days"]}

# Feature flags (environment-specific)
ENABLE_DEBUG_LOGGING=$( [ "$environment" = "development" ] && echo "true" || echo "false" )
ENABLE_PERFORMANCE_MONITORING=$( [ "$environment" != "development" ] && echo "true" || echo "false" )
ENABLE_COST_OPTIMIZATION=$( [ "$environment" = "production" ] && echo "true" || echo "false" )

# Resource limits
MAX_EXPERIMENT_DURATION_MINUTES=$( [ "$environment" = "development" ] && echo "30" || echo "60" )
MAX_CONCURRENT_EXPERIMENTS=$( [ "$environment" = "production" ] && echo "5" || echo "2" )

# Security settings
REQUIRE_SSL=true
ENABLE_IAM_CONDITIONS=$( [ "$environment" = "production" ] && echo "true" || echo "false" )
ENABLE_VPC_FIREWALL=$( [ "$environment" != "development" ] && echo "true" || echo "false" )
EOF
    
    echo_info "Configuration file created: $output_file"
}

# Generate Terraform variables file
generate_terraform_vars() {
    local environment=$1
    local output_file="$CONFIG_DIR/$environment/terraform.tfvars"
    
    echo_config "Generating Terraform variables for environment: $environment"
    
    cat > "$output_file" << EOF
# Cars with a Life - $environment Environment Terraform Variables
# Generated on $(date)

environment = "$environment"
project_suffix = "${ENVIRONMENT_CONFIGS["${environment}_project_suffix"]}"

# Compute configuration
machine_type = "${ENVIRONMENT_CONFIGS["${environment}_machine_type"]}"
gpu_type = "${ENVIRONMENT_CONFIGS["${environment}_gpu_type"]}"
gpu_count = ${ENVIRONMENT_CONFIGS["${environment}_gpu_count"]}
disk_size_gb = ${ENVIRONMENT_CONFIGS["${environment}_disk_size"]}

# Scaling configuration
min_instances = ${ENVIRONMENT_CONFIGS["${environment}_min_instances"]}
max_instances = ${ENVIRONMENT_CONFIGS["${environment}_max_instances"]}
enable_autoscaling = ${ENVIRONMENT_CONFIGS["${environment}_enable_autoscaling"]}
enable_preemptible = ${ENVIRONMENT_CONFIGS["${environment}_enable_preemptible"]}

# Monitoring configuration
monitoring_level = "${ENVIRONMENT_CONFIGS["${environment}_monitoring_level"]}"
backup_retention_days = ${ENVIRONMENT_CONFIGS["${environment}_backup_retention_days"]}
log_retention_days = ${ENVIRONMENT_CONFIGS["${environment}_log_retention_days"]}

# Network configuration
enable_vpc_firewall = $( [ "$environment" != "development" ] && echo "true" || echo "false" )
enable_private_google_access = true

# Labels
labels = {
  environment = "$environment"
  project = "cars-with-a-life"
  managed-by = "terraform"
  cost-center = "research"
}
EOF
    
    echo_info "Terraform variables file created: $output_file"
}

# Generate Cloud Run service configuration
generate_cloud_run_config() {
    local environment=$1
    local service_name=$2
    local output_file="$CONFIG_DIR/$environment/cloud-run-${service_name}.yaml"
    
    echo_config "Generating Cloud Run configuration for $service_name in $environment"
    
    local memory=${ENVIRONMENT_CONFIGS["${environment}_cloud_run_memory"]}
    local cpu=${ENVIRONMENT_CONFIGS["${environment}_cloud_run_cpu"]}
    local concurrency=${ENVIRONMENT_CONFIGS["${environment}_cloud_run_concurrency"]}
    local min_instances=${ENVIRONMENT_CONFIGS["${environment}_min_instances"]}
    local max_instances=${ENVIRONMENT_CONFIGS["${environment}_max_instances"]}
    
    cat > "$output_file" << EOF
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: $service_name
  labels:
    environment: $environment
    service: $service_name
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      labels:
        environment: $environment
        service: $service_name
      annotations:
        autoscaling.knative.dev/minScale: "$min_instances"
        autoscaling.knative.dev/maxScale: "$max_instances"
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/execution-environment: gen2
    spec:
      containerConcurrency: $concurrency
      timeoutSeconds: 900
      containers:
      - image: PLACEHOLDER_IMAGE_URL
        resources:
          limits:
            cpu: $cpu
            memory: $memory
        env:
        - name: ENVIRONMENT
          value: $environment
        - name: SERVICE_NAME
          value: $service_name
        - name: LOG_LEVEL
          value: $( [ "$environment" = "development" ] && echo "DEBUG" || echo "INFO" )
        ports:
        - containerPort: 8080
EOF
    
    echo_info "Cloud Run configuration created: $output_file"
}

# Generate monitoring configuration
generate_monitoring_config() {
    local environment=$1
    local output_file="$CONFIG_DIR/$environment/monitoring.json"
    
    echo_config "Generating monitoring configuration for environment: $environment"
    
    local monitoring_level=${ENVIRONMENT_CONFIGS["${environment}_monitoring_level"]}
    
    cat > "$output_file" << EOF
{
  "environment": "$environment",
  "monitoring_level": "$monitoring_level",
  "alerting": {
    "enabled": $( [ "$monitoring_level" = "full" ] && echo "true" || echo "false" ),
    "notification_channels": {
      "email": {
        "enabled": true,
        "addresses": ["admin@cars-with-a-life-${environment}.com"]
      },
      "slack": {
        "enabled": $( [ "$environment" != "development" ] && echo "true" || echo "false" ),
        "webhook_url": "PLACEHOLDER_SLACK_WEBHOOK"
      }
    }
  },
  "metrics": {
    "custom_metrics_enabled": $( [ "$monitoring_level" = "full" ] && echo "true" || echo "false" ),
    "log_based_metrics_enabled": true,
    "uptime_checks_enabled": $( [ "$environment" != "development" ] && echo "true" || echo "false" )
  },
  "dashboards": {
    "system_overview": true,
    "performance_metrics": $( [ "$monitoring_level" = "full" ] && echo "true" || echo "false" ),
    "cost_analysis": $( [ "$environment" = "production" ] && echo "true" || echo "false" )
  },
  "log_retention": {
    "days": ${ENVIRONMENT_CONFIGS["${environment}_log_retention_days"]},
    "export_to_bigquery": $( [ "$environment" = "production" ] && echo "true" || echo "false" )
  }
}
EOF
    
    echo_info "Monitoring configuration created: $output_file"
}

# Validate environment configuration
validate_environment_config() {
    local environment=$1
    
    echo_config "Validating configuration for environment: $environment"
    
    local config_file="$CONFIG_DIR/$environment/config.env"
    
    if [ ! -f "$config_file" ]; then
        echo_error "Configuration file not found: $config_file"
        return 1
    fi
    
    # Source the configuration
    source "$config_file"
    
    # Validate required variables
    local required_vars=(
        "ENVIRONMENT"
        "MACHINE_TYPE"
        "GPU_TYPE"
        "MIN_INSTANCES"
        "MAX_INSTANCES"
        "CLOUD_RUN_MEMORY"
        "CLOUD_RUN_CPU"
    )
    
    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo_error "Missing required configuration variables: ${missing_vars[*]}"
        return 1
    fi
    
    # Validate resource limits
    if [ "$MIN_INSTANCES" -gt "$MAX_INSTANCES" ]; then
        echo_error "MIN_INSTANCES ($MIN_INSTANCES) cannot be greater than MAX_INSTANCES ($MAX_INSTANCES)"
        return 1
    fi
    
    # Validate GPU configuration
    if [ "$GPU_COUNT" -lt 1 ] || [ "$GPU_COUNT" -gt 4 ]; then
        echo_error "GPU_COUNT ($GPU_COUNT) must be between 1 and 4"
        return 1
    fi
    
    echo_info "Configuration validation passed for environment: $environment"
    return 0
}

# Load environment configuration
load_environment_config() {
    local environment=$1
    local config_file="$CONFIG_DIR/$environment/config.env"
    
    if [ ! -f "$config_file" ]; then
        echo_error "Configuration file not found: $config_file"
        echo_info "Run: $0 --generate --environment $environment"
        return 1
    fi
    
    echo_config "Loading configuration for environment: $environment"
    source "$config_file"
    
    echo_info "Configuration loaded successfully"
    
    # Export key variables for use by other scripts
    export ENVIRONMENT
    export MACHINE_TYPE
    export GPU_TYPE
    export GPU_COUNT
    export MIN_INSTANCES
    export MAX_INSTANCES
    export CLOUD_RUN_MEMORY
    export CLOUD_RUN_CPU
    export MONITORING_LEVEL
}

# Display environment configuration
display_environment_config() {
    local environment=$1
    
    echo_config "Configuration for environment: $environment"
    echo "=============================================="
    
    local config_file="$CONFIG_DIR/$environment/config.env"
    
    if [ ! -f "$config_file" ]; then
        echo_error "Configuration file not found: $config_file"
        return 1
    fi
    
    # Display configuration in a formatted way
    source "$config_file"
    
    echo "Environment: $ENVIRONMENT"
    echo "Project Suffix: $PROJECT_SUFFIX"
    echo ""
    echo "Compute Resources:"
    echo "  Machine Type: $MACHINE_TYPE"
    echo "  GPU Type: $GPU_TYPE"
    echo "  GPU Count: $GPU_COUNT"
    echo "  Disk Size: ${DISK_SIZE_GB}GB"
    echo ""
    echo "Scaling:"
    echo "  Min Instances: $MIN_INSTANCES"
    echo "  Max Instances: $MAX_INSTANCES"
    echo "  Autoscaling: $ENABLE_AUTOSCALING"
    echo "  Preemptible: $ENABLE_PREEMPTIBLE"
    echo ""
    echo "Cloud Run:"
    echo "  Memory: $CLOUD_RUN_MEMORY"
    echo "  CPU: $CLOUD_RUN_CPU"
    echo "  Concurrency: $CLOUD_RUN_CONCURRENCY"
    echo ""
    echo "Monitoring:"
    echo "  Level: $MONITORING_LEVEL"
    echo "  Backup Retention: ${BACKUP_RETENTION_DAYS} days"
    echo "  Log Retention: ${LOG_RETENTION_DAYS} days"
}

# Main function
main() {
    local action=""
    local environment=""
    local service_name=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --generate)
                action="generate"
                shift
                ;;
            --validate)
                action="validate"
                shift
                ;;
            --load)
                action="load"
                shift
                ;;
            --display)
                action="display"
                shift
                ;;
            --environment)
                environment="$2"
                shift 2
                ;;
            --service)
                service_name="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Actions:"
                echo "  --generate               Generate configuration files"
                echo "  --validate               Validate configuration files"
                echo "  --load                   Load configuration for use by other scripts"
                echo "  --display                Display configuration"
                echo ""
                echo "Options:"
                echo "  --environment ENV        Target environment (development|staging|production)"
                echo "  --service SERVICE        Target service for Cloud Run config generation"
                echo "  --help                   Show this help"
                echo ""
                echo "Examples:"
                echo "  $0 --generate --environment development"
                echo "  $0 --validate --environment production"
                echo "  $0 --display --environment staging"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Validate required parameters
    if [ -z "$action" ]; then
        echo_error "Action is required. Use --help for usage information."
        exit 1
    fi
    
    if [ -z "$environment" ]; then
        echo_error "Environment is required. Use --environment option."
        exit 1
    fi
    
    # Validate environment
    case $environment in
        "development"|"staging"|"production")
            ;;
        *)
            echo_error "Invalid environment: $environment. Must be one of: development, staging, production"
            exit 1
            ;;
    esac
    
    # Execute action
    case $action in
        "generate")
            create_config_directories
            generate_environment_config "$environment"
            generate_terraform_vars "$environment"
            generate_monitoring_config "$environment"
            
            # Generate Cloud Run configs for known services
            local services=("orchestrator" "reporter")
            for service in "${services[@]}"; do
                generate_cloud_run_config "$environment" "$service"
            done
            
            echo_info "All configuration files generated for environment: $environment"
            ;;
        "validate")
            validate_environment_config "$environment"
            ;;
        "load")
            load_environment_config "$environment"
            ;;
        "display")
            display_environment_config "$environment"
            ;;
        *)
            echo_error "Unknown action: $action"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"