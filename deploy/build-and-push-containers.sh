#!/bin/bash

# Build and Push All Containers to Artifact Registry
# Automated container versioning and tagging system

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
REPOSITORY_NAME="cars-with-a-life-repo"
ARTIFACT_REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"

# Version management
VERSION=${BUILD_VERSION:-$(date +%Y%m%d-%H%M%S)}
GIT_COMMIT=${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")}
BUILD_NUMBER=${BUILD_NUMBER:-"local"}

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

echo_build() {
    echo -e "${BLUE}[BUILD]${NC} $1"
}

# Service definitions
declare -A SERVICES=(
    ["carla-runner"]="services/carla-runner"
    ["dreamerv3-service"]="services/dreamerv3-service"
    ["orchestrator"]="services/orchestrator"
    ["reporter"]="services/reporter"
)

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        echo_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is not installed"
        exit 1
    fi
    
    # Check if authenticated with gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check if Artifact Registry is configured
    if ! gcloud artifacts repositories describe $REPOSITORY_NAME \
        --location=$REGION \
        --project=$PROJECT_ID &> /dev/null; then
        echo_error "Artifact Registry repository not found. Run './deploy/setup-artifact-registry.sh' first"
        exit 1
    fi
    
    echo_info "Prerequisites check passed"
}

# Generate image tags
generate_tags() {
    local service_name=$1
    local base_url="${ARTIFACT_REGISTRY_URL}/${service_name}"
    
    echo "${base_url}:${VERSION}"
    echo "${base_url}:${GIT_COMMIT}"
    echo "${base_url}:latest"
    
    # Add build number tag if available
    if [ "$BUILD_NUMBER" != "local" ]; then
        echo "${base_url}:build-${BUILD_NUMBER}"
    fi
}

# Build single service
build_service() {
    local service_name=$1
    local service_path=$2
    
    echo_build "Building $service_name..."
    
    # Check if Dockerfile exists
    if [ ! -f "$service_path/Dockerfile" ]; then
        echo_error "Dockerfile not found in $service_path"
        return 1
    fi
    
    # Generate tags
    local tags=($(generate_tags $service_name))
    local primary_tag=${tags[0]}
    
    # Build image with primary tag
    echo_build "Building image: $primary_tag"
    docker build -t "$primary_tag" "$service_path"
    
    # Tag with additional tags
    for tag in "${tags[@]:1}"; do
        echo_build "Tagging: $tag"
        docker tag "$primary_tag" "$tag"
    done
    
    echo_info "Built $service_name successfully"
    return 0
}

# Push single service
push_service() {
    local service_name=$1
    
    echo_build "Pushing $service_name..."
    
    # Generate tags and push all
    local tags=($(generate_tags $service_name))
    
    for tag in "${tags[@]}"; do
        echo_build "Pushing: $tag"
        docker push "$tag"
    done
    
    echo_info "Pushed $service_name successfully"
}

# Build all services
build_all_services() {
    echo_info "Building all services..."
    
    local failed_services=()
    
    for service_name in "${!SERVICES[@]}"; do
        service_path=${SERVICES[$service_name]}
        
        if build_service "$service_name" "$service_path"; then
            echo_info "✓ $service_name built successfully"
        else
            echo_error "✗ Failed to build $service_name"
            failed_services+=("$service_name")
        fi
    done
    
    if [ ${#failed_services[@]} -gt 0 ]; then
        echo_error "Failed to build services: ${failed_services[*]}"
        return 1
    fi
    
    echo_info "All services built successfully"
}

# Push all services
push_all_services() {
    echo_info "Pushing all services to Artifact Registry..."
    
    local failed_services=()
    
    for service_name in "${!SERVICES[@]}"; do
        if push_service "$service_name"; then
            echo_info "✓ $service_name pushed successfully"
        else
            echo_error "✗ Failed to push $service_name"
            failed_services+=("$service_name")
        fi
    done
    
    if [ ${#failed_services[@]} -gt 0 ]; then
        echo_error "Failed to push services: ${failed_services[*]}"
        return 1
    fi
    
    echo_info "All services pushed successfully"
}

# Validate pushed images
validate_images() {
    echo_info "Validating pushed images..."
    
    for service_name in "${!SERVICES[@]}"; do
        local image_url="${ARTIFACT_REGISTRY_URL}/${service_name}:${VERSION}"
        
        echo_build "Validating: $image_url"
        
        if gcloud artifacts docker images describe "$image_url" \
            --project=$PROJECT_ID &> /dev/null; then
            echo_info "✓ $service_name image validated"
        else
            echo_error "✗ Failed to validate $service_name image"
            return 1
        fi
    done
    
    echo_info "All images validated successfully"
}

# Generate deployment manifest
generate_deployment_manifest() {
    local manifest_file="deployment-manifest-${VERSION}.json"
    
    echo_info "Generating deployment manifest: $manifest_file"
    
    cat > "$manifest_file" << EOF
{
  "version": "$VERSION",
  "git_commit": "$GIT_COMMIT",
  "build_number": "$BUILD_NUMBER",
  "build_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "project_id": "$PROJECT_ID",
  "region": "$REGION",
  "repository": "$REPOSITORY_NAME",
  "images": {
EOF
    
    local first=true
    for service_name in "${!SERVICES[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$manifest_file"
        fi
        
        local image_url="${ARTIFACT_REGISTRY_URL}/${service_name}:${VERSION}"
        echo "    \"$service_name\": \"$image_url\"" >> "$manifest_file"
    done
    
    cat >> "$manifest_file" << EOF
  }
}
EOF
    
    echo_info "Deployment manifest generated: $manifest_file"
}

# Cleanup old images (optional)
cleanup_old_images() {
    local keep_count=${KEEP_IMAGE_COUNT:-10}
    
    echo_info "Cleaning up old images (keeping $keep_count most recent)..."
    
    for service_name in "${!SERVICES[@]}"; do
        echo_build "Cleaning up $service_name images..."
        
        # List images and delete old ones
        gcloud artifacts docker images list \
            "${ARTIFACT_REGISTRY_URL}/${service_name}" \
            --sort-by="~CREATE_TIME" \
            --format="value(IMAGE)" \
            --limit=1000 \
            --project=$PROJECT_ID | \
        tail -n +$((keep_count + 1)) | \
        while read image; do
            if [ -n "$image" ]; then
                echo_build "Deleting old image: $image"
                gcloud artifacts docker images delete "$image" \
                    --quiet \
                    --project=$PROJECT_ID || echo_warn "Failed to delete $image"
            fi
        done
    done
    
    echo_info "Cleanup completed"
}

# Display build summary
display_summary() {
    echo_info "Build and Push Summary"
    echo "=========================="
    echo "Version: $VERSION"
    echo "Git Commit: $GIT_COMMIT"
    echo "Build Number: $BUILD_NUMBER"
    echo "Project: $PROJECT_ID"
    echo "Repository: $ARTIFACT_REGISTRY_URL"
    echo ""
    echo "Built Images:"
    
    for service_name in "${!SERVICES[@]}"; do
        local image_url="${ARTIFACT_REGISTRY_URL}/${service_name}:${VERSION}"
        echo "  $service_name: $image_url"
    done
    
    echo ""
    echo "To deploy these images, use the generated deployment manifest or update your deployment scripts."
}

# Main function
main() {
    echo_info "Starting container build and push process..."
    
    # Parse command line arguments
    local build_only=false
    local push_only=false
    local cleanup=false
    local services_to_build=()
    
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
            --build-only)
                build_only=true
                shift
                ;;
            --push-only)
                push_only=true
                shift
                ;;
            --cleanup)
                cleanup=true
                shift
                ;;
            --service)
                services_to_build+=("$2")
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --project PROJECT_ID    GCP Project ID"
                echo "  --region REGION         GCP Region"
                echo "  --version VERSION       Build version"
                echo "  --build-only           Only build, don't push"
                echo "  --push-only            Only push, don't build"
                echo "  --cleanup              Cleanup old images after push"
                echo "  --service SERVICE      Build specific service only"
                echo "  --help                 Show this help"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Update Artifact Registry URL with potentially updated values
    ARTIFACT_REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"
    
    check_prerequisites
    
    # Handle specific services
    if [ ${#services_to_build[@]} -gt 0 ]; then
        echo_info "Building specific services: ${services_to_build[*]}"
        declare -A FILTERED_SERVICES
        for service in "${services_to_build[@]}"; do
            if [[ -n "${SERVICES[$service]}" ]]; then
                FILTERED_SERVICES[$service]=${SERVICES[$service]}
            else
                echo_error "Unknown service: $service"
                exit 1
            fi
        done
        SERVICES=()
        for key in "${!FILTERED_SERVICES[@]}"; do
            SERVICES[$key]=${FILTERED_SERVICES[$key]}
        done
    fi
    
    # Execute build/push based on options
    if [ "$push_only" = true ]; then
        push_all_services
        validate_images
    elif [ "$build_only" = true ]; then
        build_all_services
    else
        build_all_services
        push_all_services
        validate_images
    fi
    
    generate_deployment_manifest
    
    if [ "$cleanup" = true ]; then
        cleanup_old_images
    fi
    
    display_summary
    
    echo_info "Container build and push process completed successfully!"
}

# Run main function
main "$@"