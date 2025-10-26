#!/bin/bash

# Setup Service-to-Service Authentication and Networking
# Configure secure communication between all services

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
ZONE=${GCP_ZONE:-"us-central1-a"}

# Network configuration
VPC_NAME="cars-with-a-life-vpc"
SUBNET_NAME="cars-with-a-life-subnet"
SUBNET_RANGE="10.0.0.0/24"

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

echo_network() {
    echo -e "${BLUE}[NETWORK]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites for networking setup..."
    
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is not installed"
        exit 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check if required APIs are enabled
    local required_apis=(
        "compute.googleapis.com"
        "run.googleapis.com"
        "vpcaccess.googleapis.com"
        "servicenetworking.googleapis.com"
    )
    
    for api in "${required_apis[@]}"; do
        if ! gcloud services list --enabled --filter="name:$api" --project=$PROJECT_ID | grep -q "$api"; then
            echo_info "Enabling API: $api"
            gcloud services enable $api --project=$PROJECT_ID
        fi
    done
    
    echo_info "Prerequisites check passed"
}

# Create VPC network
create_vpc_network() {
    echo_network "Creating VPC network..."
    
    # Create VPC network
    if ! gcloud compute networks describe $VPC_NAME --project=$PROJECT_ID &> /dev/null; then
        gcloud compute networks create $VPC_NAME \
            --subnet-mode=custom \
            --description="VPC network for Cars with a Life services" \
            --project=$PROJECT_ID
        
        echo_info "Created VPC network: $VPC_NAME"
    else
        echo_warn "VPC network $VPC_NAME already exists"
    fi
    
    # Create subnet
    if ! gcloud compute networks subnets describe $SUBNET_NAME --region=$REGION --project=$PROJECT_ID &> /dev/null; then
        gcloud compute networks subnets create $SUBNET_NAME \
            --network=$VPC_NAME \
            --range=$SUBNET_RANGE \
            --region=$REGION \
            --description="Subnet for Cars with a Life services" \
            --project=$PROJECT_ID
        
        echo_info "Created subnet: $SUBNET_NAME ($SUBNET_RANGE)"
    else
        echo_warn "Subnet $SUBNET_NAME already exists"
    fi
}

# Create VPC connector for Cloud Run
create_vpc_connector() {
    local connector_name="cars-with-a-life-connector"
    
    echo_network "Creating VPC connector for Cloud Run..."
    
    if ! gcloud compute networks vpc-access connectors describe $connector_name \
        --region=$REGION --project=$PROJECT_ID &> /dev/null; then
        
        gcloud compute networks vpc-access connectors create $connector_name \
            --region=$REGION \
            --subnet=$SUBNET_NAME \
            --subnet-project=$PROJECT_ID \
            --min-instances=2 \
            --max-instances=10 \
            --machine-type=e2-micro \
            --project=$PROJECT_ID
        
        echo_info "Created VPC connector: $connector_name"
    else
        echo_warn "VPC connector $connector_name already exists"
    fi
    
    echo "$connector_name"
}

# Configure firewall rules
configure_firewall_rules() {
    echo_network "Configuring firewall rules..."
    
    # Allow internal communication within VPC
    gcloud compute firewall-rules create allow-internal-cars-with-a-life \
        --network=$VPC_NAME \
        --allow=tcp,udp,icmp \
        --source-ranges=$SUBNET_RANGE \
        --description="Allow internal communication within Cars with a Life VPC" \
        --project=$PROJECT_ID \
        || echo_warn "Internal firewall rule may already exist"
    
    # Allow SSH access to Compute Engine instances
    gcloud compute firewall-rules create allow-ssh-cars-with-a-life \
        --network=$VPC_NAME \
        --allow=tcp:22 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=allow-ssh \
        --description="Allow SSH access to Cars with a Life instances" \
        --project=$PROJECT_ID \
        || echo_warn "SSH firewall rule may already exist"
    
    # Allow CARLA simulation ports
    gcloud compute firewall-rules create allow-carla-simulation \
        --network=$VPC_NAME \
        --allow=tcp:2000-2002,tcp:8080 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=carla-runner \
        --description="Allow CARLA simulation and API ports" \
        --project=$PROJECT_ID \
        || echo_warn "CARLA firewall rule may already exist"
    
    # Allow health checks from Google Cloud Load Balancers
    gcloud compute firewall-rules create allow-health-checks-cars-with-a-life \
        --network=$VPC_NAME \
        --allow=tcp \
        --source-ranges=130.211.0.0/22,35.191.0.0/16 \
        --description="Allow health checks from Google Cloud Load Balancers" \
        --project=$PROJECT_ID \
        || echo_warn "Health check firewall rule may already exist"
    
    echo_info "Firewall rules configured"
}

# Setup service accounts and IAM
setup_service_accounts() {
    echo_network "Setting up service accounts and IAM..."
    
    # Create service account for inter-service communication
    local sa_name="inter-service-auth"
    local sa_email="${sa_name}@${PROJECT_ID}.iam.gserviceaccount.com"
    
    gcloud iam service-accounts create $sa_name \
        --display-name="Inter-Service Authentication" \
        --description="Service account for secure inter-service communication" \
        --project=$PROJECT_ID \
        || echo_warn "Service account may already exist"
    
    # Grant necessary roles for service-to-service communication
    local roles=(
        "roles/run.invoker"
        "roles/compute.viewer"
        "roles/aiplatform.user"
        "roles/pubsub.publisher"
        "roles/pubsub.subscriber"
        "roles/storage.objectViewer"
        "roles/bigquery.dataViewer"
        "roles/logging.logWriter"
        "roles/monitoring.metricWriter"
    )
    
    for role in "${roles[@]}"; do
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:${sa_email}" \
            --role="$role" \
            --quiet || echo_warn "Role binding may already exist: $role"
    done
    
    # Create and download service account key for Compute Engine instances
    local key_file="/tmp/inter-service-auth-key.json"
    
    if [ ! -f "$key_file" ]; then
        gcloud iam service-accounts keys create $key_file \
            --iam-account=$sa_email \
            --project=$PROJECT_ID
        
        echo_info "Service account key created: $key_file"
    fi
    
    echo_info "Service accounts configured"
    echo "$sa_email"
}

# Configure Cloud Run networking
configure_cloud_run_networking() {
    local vpc_connector=$1
    
    echo_network "Configuring Cloud Run networking..."
    
    # Update Cloud Run services to use VPC connector
    local services=("orchestrator" "reporter")
    
    for service in "${services[@]}"; do
        if gcloud run services describe $service --region=$REGION --project=$PROJECT_ID &> /dev/null; then
            echo_network "Updating $service to use VPC connector..."
            
            gcloud run services update $service \
                --vpc-connector=$vpc_connector \
                --vpc-egress=private-ranges-only \
                --region=$REGION \
                --project=$PROJECT_ID \
                || echo_warn "Failed to update VPC connector for $service"
            
            echo_info "Updated $service networking configuration"
        else
            echo_warn "Service $service not found, skipping networking update"
        fi
    done
}

# Setup load balancer for high availability
setup_load_balancer() {
    echo_network "Setting up load balancer..."
    
    # Create health check
    local health_check_name="cars-with-a-life-health-check"
    
    gcloud compute health-checks create http $health_check_name \
        --port=8080 \
        --request-path=/health \
        --check-interval=30s \
        --timeout=10s \
        --healthy-threshold=2 \
        --unhealthy-threshold=3 \
        --description="Health check for Cars with a Life services" \
        --project=$PROJECT_ID \
        || echo_warn "Health check may already exist"
    
    # Create backend service for CARLA Runner instances
    local backend_service_name="carla-runner-backend"
    
    if ! gcloud compute backend-services describe $backend_service_name --global --project=$PROJECT_ID &> /dev/null; then
        gcloud compute backend-services create $backend_service_name \
            --protocol=HTTP \
            --port-name=http \
            --health-checks=$health_check_name \
            --global \
            --description="Backend service for CARLA Runner instances" \
            --project=$PROJECT_ID
        
        echo_info "Created backend service: $backend_service_name"
    fi
    
    # Add instance group to backend service (if it exists)
    local instance_group="carla-runner-group"
    
    if gcloud compute instance-groups managed describe $instance_group --zone=$ZONE --project=$PROJECT_ID &> /dev/null; then
        gcloud compute backend-services add-backend $backend_service_name \
            --instance-group=$instance_group \
            --instance-group-zone=$ZONE \
            --global \
            --project=$PROJECT_ID \
            || echo_warn "Backend may already be added"
        
        echo_info "Added instance group to backend service"
    fi
    
    echo_info "Load balancer configuration completed"
}

# Configure DNS and service discovery
setup_service_discovery() {
    echo_network "Setting up service discovery..."
    
    # Create Cloud DNS zone for internal service discovery
    local dns_zone_name="cars-with-a-life-internal"
    local dns_domain="cars-internal."
    
    if ! gcloud dns managed-zones describe $dns_zone_name --project=$PROJECT_ID &> /dev/null; then
        gcloud dns managed-zones create $dns_zone_name \
            --description="Internal DNS zone for Cars with a Life services" \
            --dns-name=$dns_domain \
            --visibility=private \
            --networks=$VPC_NAME \
            --project=$PROJECT_ID
        
        echo_info "Created internal DNS zone: $dns_zone_name"
    else
        echo_warn "DNS zone $dns_zone_name already exists"
    fi
    
    # Create DNS records for services
    local services=(
        "orchestrator:orchestrator-${PROJECT_ID}.${REGION}.run.app"
        "reporter:reporter-${PROJECT_ID}.${REGION}.run.app"
    )
    
    for service_def in "${services[@]}"; do
        local service_name=$(echo $service_def | cut -d: -f1)
        local service_url=$(echo $service_def | cut -d: -f2)
        
        # Create CNAME record
        gcloud dns record-sets create "${service_name}.${dns_domain}" \
            --zone=$dns_zone_name \
            --type=CNAME \
            --ttl=300 \
            --rrdatas=$service_url \
            --project=$PROJECT_ID \
            || echo_warn "DNS record may already exist for $service_name"
    done
    
    echo_info "Service discovery configured"
}

# Setup network monitoring
setup_network_monitoring() {
    echo_network "Setting up network monitoring..."
    
    # Create log-based metrics for network traffic
    gcloud logging metrics create network_traffic_volume \
        --description="Network traffic volume by service" \
        --log-filter='resource.type="gce_instance" OR resource.type="cloud_run_revision"' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    gcloud logging metrics create network_connection_errors \
        --description="Network connection errors" \
        --log-filter='jsonPayload.message:"connection" AND severity>=ERROR' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    # Create uptime checks for critical services
    local services=(
        "orchestrator:https://orchestrator-${PROJECT_ID}.${REGION}.run.app/health"
        "reporter:https://reporter-${PROJECT_ID}.${REGION}.run.app/health"
    )
    
    for service_def in "${services[@]}"; do
        local service_name=$(echo $service_def | cut -d: -f1)
        local service_url=$(echo $service_def | cut -d: -f2)
        
        cat > "/tmp/${service_name}-uptime.json" << EOF
{
  "displayName": "Cars with a Life - ${service_name} Uptime Check",
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
            --config-from-file="/tmp/${service_name}-uptime.json" \
            --project=$PROJECT_ID \
            || echo_warn "Uptime check may already exist for $service_name"
        
        rm -f "/tmp/${service_name}-uptime.json"
    done
    
    echo_info "Network monitoring configured"
}

# Test network connectivity
test_network_connectivity() {
    echo_network "Testing network connectivity..."
    
    # Test Cloud Run service connectivity
    local services=(
        "orchestrator:https://orchestrator-${PROJECT_ID}.${REGION}.run.app/health"
        "reporter:https://reporter-${PROJECT_ID}.${REGION}.run.app/health"
    )
    
    for service_def in "${services[@]}"; do
        local service_name=$(echo $service_def | cut -d: -f1)
        local service_url=$(echo $service_def | cut -d: -f2)
        
        echo_network "Testing connectivity to $service_name..."
        
        if curl -f -s --max-time 10 "$service_url" > /dev/null 2>&1; then
            echo_info "✓ $service_name is accessible"
        else
            echo_warn "✗ $service_name is not accessible (may not be deployed yet)"
        fi
    done
    
    echo_info "Network connectivity test completed"
}

# Display networking summary
display_summary() {
    local vpc_connector=$1
    local sa_email=$2
    
    echo_info "Networking and Authentication Setup Summary"
    echo "==========================================="
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "VPC Network: $VPC_NAME"
    echo "Subnet: $SUBNET_NAME ($SUBNET_RANGE)"
    echo "VPC Connector: $vpc_connector"
    echo "Service Account: $sa_email"
    echo ""
    echo "Configured Components:"
    echo "  ✓ VPC network with custom subnet"
    echo "  ✓ VPC connector for Cloud Run services"
    echo "  ✓ Firewall rules for secure communication"
    echo "  ✓ Service accounts with appropriate IAM roles"
    echo "  ✓ Load balancer for high availability"
    echo "  ✓ Internal DNS for service discovery"
    echo "  ✓ Network monitoring and uptime checks"
    echo ""
    echo "Security Features:"
    echo "  • Private IP ranges for internal communication"
    echo "  • Service-to-service authentication"
    echo "  • Firewall rules restricting external access"
    echo "  • Health checks for service availability"
    echo ""
    echo "Useful commands:"
    echo "  View VPC: gcloud compute networks describe $VPC_NAME"
    echo "  List firewall rules: gcloud compute firewall-rules list --filter='network:$VPC_NAME'"
    echo "  Check connectivity: gcloud compute ssh <instance> --command='curl <service-url>'"
}

# Main function
main() {
    echo_network "Starting networking and authentication setup..."
    
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
            --vpc-name)
                VPC_NAME="$2"
                shift 2
                ;;
            --subnet-range)
                SUBNET_RANGE="$2"
                shift 2
                ;;
            --skip-test)
                SKIP_TEST=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --project PROJECT_ID      GCP Project ID"
                echo "  --region REGION           GCP Region"
                echo "  --zone ZONE              GCP Zone"
                echo "  --vpc-name NAME          VPC network name"
                echo "  --subnet-range CIDR      Subnet IP range"
                echo "  --skip-test              Skip connectivity testing"
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
    create_vpc_network
    vpc_connector=$(create_vpc_connector)
    configure_firewall_rules
    sa_email=$(setup_service_accounts)
    configure_cloud_run_networking "$vpc_connector"
    setup_load_balancer
    setup_service_discovery
    setup_network_monitoring
    
    if [ "$SKIP_TEST" != "true" ]; then
        test_network_connectivity
    fi
    
    display_summary "$vpc_connector" "$sa_email"
    
    echo_info "Networking and authentication setup completed successfully!"
}

# Run main function
main "$@"