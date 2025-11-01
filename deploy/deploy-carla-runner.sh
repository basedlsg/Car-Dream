#!/bin/bash

# Deploy CARLA Runner to Compute Engine with GPU using Artifact Registry

set -e

PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
ZONE=${GCP_ZONE:-"us-central1-a"}
INSTANCE_NAME="carla-runner-instance"
REPOSITORY_NAME="cars-with-a-life-repo"
VERSION=${BUILD_VERSION:-"latest"}

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

echo_info "Deploying CARLA Runner to Compute Engine..."

# Image URL from Artifact Registry
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/carla-runner:${VERSION}"

echo_info "Using image: $IMAGE_URL"

# Verify image exists in Artifact Registry
if ! gcloud artifacts docker images describe "$IMAGE_URL" --project=$PROJECT_ID &> /dev/null; then
    echo_error "Image not found in Artifact Registry: $IMAGE_URL"
    echo_info "Please run './deploy/build-and-push-containers.sh' first"
    exit 1
fi

# Create startup script that uses Artifact Registry image
cat > /tmp/carla-startup.sh << EOF
#!/bin/bash

# CARLA Runner Startup Script for Compute Engine
set -e

# Configure Docker for Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Install NVIDIA drivers
/opt/deeplearning/install-driver.sh

# Pull and run CARLA Runner container
docker pull $IMAGE_URL

# Stop any existing container
docker stop carla-runner || true
docker rm carla-runner || true

# Run CARLA Runner container
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
    -v /var/log:/var/log \
    $IMAGE_URL

# Wait for container to start
sleep 30

# Check if container is running
if docker ps | grep -q carla-runner; then
    echo "CARLA Runner container started successfully"
else
    echo "Failed to start CARLA Runner container"
    docker logs carla-runner
    exit 1
fi
EOF

# Create GPU-enabled Compute Engine instance
echo_info "Creating Compute Engine instance with GPU..."

gcloud compute instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --machine-type=n1-standard-8 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --maintenance-policy=TERMINATE \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=100GB \
    --boot-disk-type=pd-ssd \
    --metadata-from-file startup-script=/tmp/carla-startup.sh \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --tags=carla-runner \
    --labels=service=carla-runner,version=${VERSION//[^a-zA-Z0-9]/-} \
    || echo_warn "Instance may already exist"

# Create firewall rule for CARLA ports
echo_info "Creating firewall rules..."

gcloud compute firewall-rules create allow-carla-ports \
    --allow tcp:2000-2002,tcp:8080 \
    --source-ranges 0.0.0.0/0 \
    --target-tags carla-runner \
    --description="Allow CARLA simulation and API ports" \
    || echo_warn "Firewall rule may already exist"

# Wait for instance to be ready
echo_info "Waiting for instance to be ready..."
sleep 10
for i in {1..30}; do
    STATUS=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format="value(status)" 2>/dev/null || echo "")
    if [ "$STATUS" = "RUNNING" ]; then
        echo_info "Instance is running"
        break
    fi
    echo_info "Waiting for instance... ($i/30)"
    sleep 5
done

# Get instance IP for validation
INSTANCE_IP=$(gcloud compute instances describe $INSTANCE_NAME \
    --zone=$ZONE \
    --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

echo_info "CARLA Runner deployment completed!"
echo_info "Instance: $INSTANCE_NAME"
echo_info "External IP: $INSTANCE_IP"
echo_info "Image: $IMAGE_URL"
echo ""
echo_info "To check status:"
echo "  gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE"
echo "  gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='docker logs carla-runner'"

# Clean up temporary files
rm -f /tmp/carla-startup.sh