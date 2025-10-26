#!/bin/bash

# Deploy Compute Engine Resources with GPU and Monitoring
# Enhanced deployment for CARLA Runner with auto-scaling and monitoring

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
ZONE=${GCP_ZONE:-"us-central1-a"}
REPOSITORY_NAME="cars-with-a-life-repo"
VERSION=${BUILD_VERSION:-"latest"}

# Instance configuration
INSTANCE_NAME="carla-runner-instance"
MACHINE_TYPE="n1-standard-8"
GPU_TYPE="nvidia-tesla-t4"
GPU_COUNT=1
BOOT_DISK_SIZE="100GB"
BOOT_DISK_TYPE="pd-ssd"

# Auto-scaling configuration
MIN_INSTANCES=1
MAX_INSTANCES=3
TARGET_CPU_UTILIZATION=0.7

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
    echo_info "Checking prerequisites for Compute Engine deployment..."
    
    # Check if gcloud is installed and authenticated
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is not installed"
        exit 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check GPU quota
    local gpu_quota=$(gcloud compute project-info describe \
        --project=$PROJECT_ID \
        --format="value(quotas[metric=NVIDIA_T4_GPUS].limit)" 2>/dev/null || echo "0")
    
    if [ "$gpu_quota" -lt "$GPU_COUNT" ]; then
        echo_error "Insufficient GPU quota. Current: $gpu_quota, Required: $GPU_COUNT"
        echo_info "Request GPU quota increase in Cloud Console"
        exit 1
    fi
    
    echo_info "Prerequisites check passed"
}

# Create instance template for auto-scaling
create_instance_template() {
    local template_name="carla-runner-template-$(date +%Y%m%d-%H%M%S)"
    
    echo_deploy "Creating instance template: $template_name"
    
    # Image URL from Artifact Registry
    local image_url="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/carla-runner:${VERSION}"
    
    # Create startup script
    cat > /tmp/carla-startup-template.sh << EOF
#!/bin/bash

# CARLA Runner Startup Script for Instance Template
set -e

# Install logging agent
curl -sSO https://dl.google.com/cloudagents/add-logging-agent-repo.sh
sudo bash add-logging-agent-repo.sh --also-install

# Configure Docker for Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Install NVIDIA drivers for Container-Optimized OS
/opt/deeplearning/install-driver.sh

# Pull CARLA Runner image
docker pull $image_url

# Create logging configuration
sudo mkdir -p /etc/google-fluentd/config.d
cat > /tmp/carla-logs.conf << 'LOGCONF'
<source>
  @type tail
  format json
  path /var/log/carla-runner.log
  pos_file /var/lib/google-fluentd/pos/carla-runner.log.pos
  read_from_head true
  tag carla.runner
</source>
LOGCONF
sudo mv /tmp/carla-logs.conf /etc/google-fluentd/config.d/

# Restart logging agent
sudo systemctl restart google-fluentd

# Run CARLA Runner container with monitoring
docker run -d \
    --name carla-runner \
    --restart unless-stopped \
    --gpus all \
    -p 2000:2000 \
    -p 2001:2001 \
    -p 2002:2002 \
    -p 8080:8080 \
    -e GCP_PROJECT_ID=$PROJECT_ID \
    -e GCP_REGION=$REGION \
    -e INSTANCE_NAME=\$(curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name) \
    -e ZONE=\$(curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4) \
    -v /var/log:/var/log \
    --log-driver=json-file \
    --log-opt max-size=100m \
    --log-opt max-file=5 \
    $image_url

# Wait for container to start and create health check
sleep 30

# Create health check script
cat > /tmp/health-check.sh << 'HEALTHEOF'
#!/bin/bash
# Health check for CARLA Runner
if docker ps | grep -q carla-runner && curl -f -s http://localhost:8080/health > /dev/null; then
    echo "HEALTHY"
    exit 0
else
    echo "UNHEALTHY"
    exit 1
fi
HEALTHEOF

chmod +x /tmp/health-check.sh
sudo mv /tmp/health-check.sh /usr/local/bin/carla-health-check.sh

# Setup cron for health monitoring
echo "*/2 * * * * /usr/local/bin/carla-health-check.sh >> /var/log/carla-health.log 2>&1" | crontab -

# Signal startup completion
echo "CARLA Runner startup completed successfully" | logger -t carla-startup
EOF

    # Create instance template
    gcloud compute instance-templates create $template_name \
        --machine-type=$MACHINE_TYPE \
        --accelerator=type=$GPU_TYPE,count=$GPU_COUNT \
        --maintenance-policy=TERMINATE \
        --image-family=cos-gpu \
        --image-project=cos-cloud \
        --boot-disk-size=$BOOT_DISK_SIZE \
        --boot-disk-type=$BOOT_DISK_TYPE \
        --metadata-from-file startup-script=/tmp/carla-startup-template.sh \
        --scopes=https://www.googleapis.com/auth/cloud-platform \
        --tags=carla-runner \
        --labels=service=carla-runner,version=${VERSION//[^a-zA-Z0-9]/-} \
        --project=$PROJECT_ID
    
    echo_info "Instance template created: $template_name"
    echo "$template_name"
    
    # Clean up temporary files
    rm -f /tmp/carla-startup-template.sh
}

# Create managed instance group
create_managed_instance_group() {
    local template_name=$1
    local group_name="carla-runner-group"
    
    echo_deploy "Creating managed instance group: $group_name"
    
    # Create managed instance group
    gcloud compute instance-groups managed create $group_name \
        --template=$template_name \
        --size=$MIN_INSTANCES \
        --zone=$ZONE \
        --project=$PROJECT_ID
    
    # Configure auto-scaling
    gcloud compute instance-groups managed set-autoscaling $group_name \
        --zone=$ZONE \
        --min-num-replicas=$MIN_INSTANCES \
        --max-num-replicas=$MAX_INSTANCES \
        --target-cpu-utilization=$TARGET_CPU_UTILIZATION \
        --cool-down-period=300 \
        --project=$PROJECT_ID
    
    # Create health check
    gcloud compute health-checks create http carla-runner-health-check \
        --port=8080 \
        --request-path=/health \
        --check-interval=30s \
        --timeout=10s \
        --healthy-threshold=2 \
        --unhealthy-threshold=3 \
        --project=$PROJECT_ID \
        || echo_warn "Health check may already exist"
    
    # Set auto-healing
    gcloud compute instance-groups managed set-autohealing $group_name \
        --zone=$ZONE \
        --health-check=carla-runner-health-check \
        --initial-delay=300 \
        --project=$PROJECT_ID
    
    echo_info "Managed instance group created with auto-scaling and auto-healing"
}

# Setup monitoring and alerting
setup_monitoring() {
    echo_deploy "Setting up monitoring and alerting..."
    
    # Create log-based metrics
    gcloud logging metrics create carla_runner_errors \
        --description="CARLA Runner error count" \
        --log-filter='resource.type="gce_instance" AND labels.service="carla-runner" AND severity>=ERROR' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    gcloud logging metrics create carla_runner_health_checks \
        --description="CARLA Runner health check failures" \
        --log-filter='resource.type="gce_instance" AND labels.service="carla-runner" AND jsonPayload.message:"UNHEALTHY"' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    # Create alerting policy (requires Monitoring API)
    cat > /tmp/alert-policy.json << EOF
{
  "displayName": "CARLA Runner High Error Rate",
  "conditions": [
    {
      "displayName": "CARLA Runner error rate",
      "conditionThreshold": {
        "filter": "metric.type=\"logging.googleapis.com/user/carla_runner_errors\" resource.type=\"gce_instance\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 5,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_RATE"
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true
}
EOF
    
    # Note: Alerting policy creation requires additional setup
    echo_info "Monitoring metrics created. Configure alerting policies in Cloud Console if needed."
    
    rm -f /tmp/alert-policy.json
}

# Create firewall rules
create_firewall_rules() {
    echo_deploy "Creating firewall rules..."
    
    # CARLA simulation ports
    gcloud compute firewall-rules create allow-carla-simulation \
        --allow tcp:2000-2002 \
        --source-ranges 0.0.0.0/0 \
        --target-tags carla-runner \
        --description="Allow CARLA simulation ports" \
        --project=$PROJECT_ID \
        || echo_warn "Firewall rule may already exist"
    
    # Health check and API port
    gcloud compute firewall-rules create allow-carla-api \
        --allow tcp:8080 \
        --source-ranges 0.0.0.0/0 \
        --target-tags carla-runner \
        --description="Allow CARLA API and health check port" \
        --project=$PROJECT_ID \
        || echo_warn "Firewall rule may already exist"
    
    # Internal communication (for load balancer health checks)
    gcloud compute firewall-rules create allow-carla-internal \
        --allow tcp:8080 \
        --source-ranges 130.211.0.0/22,35.191.0.0/16 \
        --target-tags carla-runner \
        --description="Allow Google Cloud load balancer health checks" \
        --project=$PROJECT_ID \
        || echo_warn "Firewall rule may already exist"
}

# Display deployment summary
display_summary() {
    echo_info "Compute Engine Deployment Summary"
    echo "=================================="
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Zone: $ZONE"
    echo "Machine Type: $MACHINE_TYPE"
    echo "GPU: $GPU_TYPE x $GPU_COUNT"
    echo "Auto-scaling: $MIN_INSTANCES - $MAX_INSTANCES instances"
    echo "Image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/carla-runner:${VERSION}"
    echo ""
    echo "Useful commands:"
    echo "  List instances: gcloud compute instances list --filter='labels.service=carla-runner'"
    echo "  Check group status: gcloud compute instance-groups managed describe carla-runner-group --zone=$ZONE"
    echo "  View logs: gcloud logging read 'resource.type=\"gce_instance\" AND labels.service=\"carla-runner\"' --limit=50"
    echo "  SSH to instance: gcloud compute ssh <instance-name> --zone=$ZONE"
}

# Main function
main() {
    echo_deploy "Starting Compute Engine deployment for CARLA Runner..."
    
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
            --zone)
                ZONE="$2"
                shift 2
                ;;
            --version)
                VERSION="$2"
                shift 2
                ;;
            --min-instances)
                MIN_INSTANCES="$2"
                shift 2
                ;;
            --max-instances)
                MAX_INSTANCES="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --project PROJECT_ID      GCP Project ID"
                echo "  --region REGION           GCP Region"
                echo "  --zone ZONE              GCP Zone"
                echo "  --version VERSION        Container version"
                echo "  --min-instances NUM      Minimum instances (default: 1)"
                echo "  --max-instances NUM      Maximum instances (default: 3)"
                echo "  --help                   Show this help"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    check_prerequisites
    create_firewall_rules
    
    template_name=$(create_instance_template)
    create_managed_instance_group "$template_name"
    setup_monitoring
    
    display_summary
    
    echo_info "Compute Engine deployment completed successfully!"
}

# Run main function
main "$@"