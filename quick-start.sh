#!/bin/bash

# 🚀 Cars with a Life - Quick Start Script
# Interactive deployment script for autonomous driving system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    local missing_tools=()
    
    # Check required tools
    if ! command_exists gcloud; then
        missing_tools+=("Google Cloud SDK (gcloud)")
    fi
    
    if ! command_exists docker; then
        missing_tools+=("Docker Desktop")
    fi
    
    if ! command_exists terraform; then
        missing_tools+=("Terraform")
    fi
    
    if ! command_exists python3; then
        missing_tools+=("Python 3.8+")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing required tools:"
        for tool in "${missing_tools[@]}"; do
            echo "  - $tool"
        done
        echo ""
        echo "Please install missing tools and run this script again."
        echo "See the README for installation instructions."
        exit 1
    fi
    
    print_success "All prerequisites are installed!"
}

# Function to get user input
get_user_input() {
    print_status "Gathering deployment configuration..."
    
    # Project ID
    if [ -z "$PROJECT_ID" ]; then
        read -p "Enter your GCP Project ID (or press Enter to auto-generate): " PROJECT_ID
        if [ -z "$PROJECT_ID" ]; then
            PROJECT_ID="car-dream-$(date +%s)"
            print_warning "Auto-generated Project ID: $PROJECT_ID"
        fi
    fi
    
    # Region
    if [ -z "$REGION" ]; then
        read -p "Enter region (default: us-central1): " REGION
        REGION=${REGION:-us-central1}
    fi
    
    # Environment
    if [ -z "$ENVIRONMENT" ]; then
        echo "Select environment:"
        echo "1) development"
        echo "2) staging"
        echo "3) production"
        read -p "Enter choice (1-3, default: 1): " env_choice
        case $env_choice in
            2) ENVIRONMENT="staging" ;;
            3) ENVIRONMENT="production" ;;
            *) ENVIRONMENT="development" ;;
        esac
    fi
    
    # Notification email
    read -p "Enter notification email (optional): " NOTIFICATION_EMAIL
    
    # Slack webhook
    read -p "Enter Slack webhook URL (optional): " SLACK_WEBHOOK
    
    print_success "Configuration gathered!"
}

# Function to set up GCP project
setup_gcp_project() {
    print_status "Setting up GCP project..."
    
    # Set project
    gcloud config set project "$PROJECT_ID"
    
    # Enable required APIs
    print_status "Enabling required APIs..."
    gcloud services enable \
        compute.googleapis.com \
        run.googleapis.com \
        cloudbuild.googleapis.com \
        artifactregistry.googleapis.com \
        aiplatform.googleapis.com \
        bigquery.googleapis.com \
        storage.googleapis.com \
        pubsub.googleapis.com \
        cloudscheduler.googleapis.com \
        monitoring.googleapis.com \
        logging.googleapis.com \
        --project="$PROJECT_ID"
    
    # Create service account
    print_status "Creating service account..."
    gcloud iam service-accounts create car-dream-sa \
        --display-name="Car Dream Service Account" \
        --description="Service account for Car Dream autonomous driving system" \
        --project="$PROJECT_ID" || true
    
    # Grant necessary permissions
    print_status "Granting permissions..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:car-dream-sa@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/editor"
    
    print_success "GCP project setup complete!"
}

# Function to configure authentication
setup_authentication() {
    print_status "Setting up authentication..."
    
    # Check if already authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_status "Please authenticate with Google Cloud..."
        gcloud auth login
    fi
    
    # Set up application default credentials
    gcloud auth application-default login
    
    print_success "Authentication setup complete!"
}

# Function to deploy infrastructure
deploy_infrastructure() {
    print_status "Deploying infrastructure with Terraform..."
    
    # Create terraform directory if it doesn't exist
    mkdir -p infrastructure/terraform
    
    # Initialize terraform
    cd infrastructure/terraform
    terraform init || {
        print_error "Terraform initialization failed"
        exit 1
    }
    
    # Plan deployment
    terraform plan \
        -var="project_id=$PROJECT_ID" \
        -var="region=$REGION" \
        -var="environment=$ENVIRONMENT" \
        -var="notification_email=$NOTIFICATION_EMAIL" \
        -var="slack_webhook=$SLACK_WEBHOOK"
    
    # Apply deployment
    terraform apply -auto-approve \
        -var="project_id=$PROJECT_ID" \
        -var="region=$REGION" \
        -var="environment=$ENVIRONMENT" \
        -var="notification_email=$NOTIFICATION_EMAIL" \
        -var="slack_webhook=$SLACK_WEBHOOK"
    
    cd ../..
    print_success "Infrastructure deployment complete!"
}

# Function to build and push containers
build_containers() {
    print_status "Building and pushing containers..."
    
    # Build CARLA runner
    print_status "Building CARLA runner container..."
    docker build -f carla-runner_Dockerfile -t "gcr.io/$PROJECT_ID/carla-runner:latest" .
    docker push "gcr.io/$PROJECT_ID/carla-runner:latest"
    
    # Build Dreamer service
    print_status "Building Dreamer service container..."
    docker build -f dreamer-service_Dockerfile -t "gcr.io/$PROJECT_ID/dreamer-service:latest" .
    docker push "gcr.io/$PROJECT_ID/dreamer-service:latest"
    
    # Build Orchestrator
    print_status "Building Orchestrator container..."
    docker build -f orchestrator_Dockerfile -t "gcr.io/$PROJECT_ID/orchestrator:latest" .
    docker push "gcr.io/$PROJECT_ID/orchestrator:latest"
    
    # Build Reporter
    print_status "Building Reporter container..."
    docker build -f reporter_Dockerfile -t "gcr.io/$PROJECT_ID/reporter:latest" .
    docker push "gcr.io/$PROJECT_ID/reporter:latest"
    
    print_success "Container build and push complete!"
}

# Function to deploy services
deploy_services() {
    print_status "Deploying services..."
    
    # Deploy using the existing deploy script
    ./deploy.sh --environment "$ENVIRONMENT" --project "$PROJECT_ID"
    
    print_success "Services deployment complete!"
}

# Function to run health checks
run_health_checks() {
    print_status "Running health checks..."
    
    # Run health check script if it exists
    if [ -f "./deploy/health-check-automation.sh" ]; then
        ./deploy/health-check-automation.sh --check --project "$PROJECT_ID"
    else
        print_warning "Health check script not found, running basic checks..."
        
        # Basic health checks
        print_status "Checking Cloud Run services..."
        gcloud run services list --region="$REGION" --project="$PROJECT_ID"
        
        print_status "Checking compute instances..."
        gcloud compute instances list --project="$PROJECT_ID"
    fi
    
    print_success "Health checks complete!"
}

# Function to provide service URLs and next steps
provide_next_steps() {
    print_success "🎉 Deployment Complete!"
    echo ""
    echo "📊 Service URLs:"
    echo "  Cloud Console: https://console.cloud.google.com/home/dashboard?project=$PROJECT_ID"
    echo "  Monitoring: https://console.cloud.google.com/monitoring/dashboards?project=$PROJECT_ID"
    echo "  Logs: https://console.cloud.google.com/logs/query?project=$PROJECT_ID"
    echo ""
    
    # Get service URLs
    print_status "Getting service URLs..."
    ORCHESTRATOR_URL=$(gcloud run services describe orchestrator --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)" 2>/dev/null || echo "Not deployed")
    REPORTER_URL=$(gcloud run services describe reporter --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)" 2>/dev/null || echo "Not deployed")
    
    echo "🚀 Service Endpoints:"
    echo "  Orchestrator: $ORCHESTRATOR_URL"
    echo "  Reporter: $REPORTER_URL"
    echo ""
    
    echo "🧪 Next Steps:"
    echo "  1. Test your system:"
    echo "     curl -X POST '$ORCHESTRATOR_URL/experiments' \\"
    echo "       -H 'Content-Type: application/json' \\"
    echo "       -d '{\"experiment_id\": \"test-001\", \"name\": \"My First Experiment\"}'"
    echo ""
    echo "  2. Monitor your system:"
    echo "     gcloud logging tail 'resource.type=\"cloud_run_revision\"' --project=$PROJECT_ID"
    echo ""
    echo "  3. Run integration tests:"
    echo "     ./tests/run_integration_tests.sh --project $PROJECT_ID"
    echo ""
    echo "💰 Cost Management:"
    echo "  - Set up billing alerts in the Cloud Console"
    echo "  - Monitor usage in the Billing dashboard"
    echo "  - Use './deploy/incident-response/emergency-scale-up.sh' to scale up"
    echo "  - Use 'gcloud compute instances stop --all' to scale down"
    echo ""
    echo "📖 For more information, see:"
    echo "  - DEPLOYMENT_GUIDE.md for detailed instructions"
    echo "  - deploy/operational-runbook.md for operations"
    echo "  - tests/README.md for testing"
}

# Main execution
main() {
    echo "🚀 Cars with a Life - Quick Start"
    echo "=================================="
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Get user input
    get_user_input
    
    # Confirm deployment
    echo ""
    print_warning "Deployment Configuration:"
    echo "  Project ID: $PROJECT_ID"
    echo "  Region: $REGION"
    echo "  Environment: $ENVIRONMENT"
    echo "  Notification Email: ${NOTIFICATION_EMAIL:-Not set}"
    echo "  Slack Webhook: ${SLACK_WEBHOOK:-Not set}"
    echo ""
    
    read -p "Proceed with deployment? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        print_status "Deployment cancelled."
        exit 0
    fi
    
    echo ""
    print_status "Starting deployment... This will take 20-30 minutes."
    echo ""
    
    # Execute deployment steps
    setup_gcp_project
    setup_authentication
    deploy_infrastructure
    build_containers
    deploy_services
    run_health_checks
    provide_next_steps
    
    print_success "🎉 Cars with a Life deployment complete!"
}

# Run main function
main "$@"