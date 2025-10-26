#!/bin/bash

# Artifact Registry Setup Script
# Creates repositories and configures Docker authentication

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
REPOSITORY_NAME="cars-with-a-life-repo"

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
    
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is not installed"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        echo_error "Docker is not installed"
        exit 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    echo_info "Prerequisites check passed"
}

# Enable Artifact Registry API
enable_apis() {
    echo_info "Enabling Artifact Registry API..."
    
    gcloud services enable artifactregistry.googleapis.com \
        --project=$PROJECT_ID
    
    echo_info "Artifact Registry API enabled"
}

# Create Artifact Registry repository
create_repository() {
    echo_info "Creating Artifact Registry repository..."
    
    # Check if repository exists
    if gcloud artifacts repositories describe $REPOSITORY_NAME \
        --location=$REGION \
        --project=$PROJECT_ID &> /dev/null; then
        echo_warn "Repository $REPOSITORY_NAME already exists"
    else
        gcloud artifacts repositories create $REPOSITORY_NAME \
            --repository-format=docker \
            --location=$REGION \
            --description="Cars with a Life container images" \
            --project=$PROJECT_ID
        
        echo_info "Repository created: $REPOSITORY_NAME"
    fi
}

# Configure Docker authentication
configure_docker_auth() {
    echo_info "Configuring Docker authentication for Artifact Registry..."
    
    gcloud auth configure-docker ${REGION}-docker.pkg.dev \
        --quiet \
        --project=$PROJECT_ID
    
    echo_info "Docker authentication configured"
}

# Create IAM bindings for service accounts
setup_iam_permissions() {
    echo_info "Setting up IAM permissions for Artifact Registry..."
    
    # Get project number
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
    
    # Grant Cloud Build service account access to Artifact Registry
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
        --role="roles/artifactregistry.writer" \
        --quiet || echo_warn "IAM binding may already exist"
    
    # Grant Compute Engine default service account access to pull images
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --role="roles/artifactregistry.reader" \
        --quiet || echo_warn "IAM binding may already exist"
    
    # Grant Cloud Run service account access to pull images
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --role="roles/artifactregistry.reader" \
        --quiet || echo_warn "IAM binding may already exist"
    
    echo_info "IAM permissions configured"
}

# Display repository information
display_info() {
    echo_info "Artifact Registry setup completed!"
    echo ""
    echo "Repository Details:"
    echo "  Name: $REPOSITORY_NAME"
    echo "  Location: $REGION"
    echo "  Format: Docker"
    echo "  URL: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"
    echo ""
    echo "To push images, use:"
    echo "  docker tag <local-image> ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/<image-name>:<tag>"
    echo "  docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/<image-name>:<tag>"
}

# Main function
main() {
    echo_info "Setting up Artifact Registry for Cars with a Life..."
    
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
            --repository)
                REPOSITORY_NAME="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [--project PROJECT_ID] [--region REGION] [--repository REPO_NAME]"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    check_prerequisites
    enable_apis
    create_repository
    configure_docker_auth
    setup_iam_permissions
    display_info
}

# Export repository URL for other scripts
export ARTIFACT_REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"

# Run main function
main "$@"