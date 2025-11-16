#!/bin/bash
set -e

# Startup script for CARLA Runner Compute Engine instance
REGION=${REGION:-us-central1}
PROJECT_ID=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/project/project-id)
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/cars-with-a-life-repo/carla-runner:latest"

# Install NVIDIA drivers for Ubuntu
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/compute-gpu-installation/main/linux/install_gpu_driver.py --output install_gpu_driver.py
python3 install_gpu_driver.py

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER || true

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Configure Docker for Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Stop any existing container
docker stop carla-runner || true
docker rm carla-runner || true

# Pull and run CARLA Runner container
docker pull $IMAGE_URL

# Run container with GPU support
docker run -d \
    --name carla-runner \
    --gpus all \
    -p 2000:2000 \
    -p 2001:2001 \
    -p 2002:2002 \
    -p 8080:8080 \
    --restart unless-stopped \
    -e GCP_PROJECT_ID=$PROJECT_ID \
    -e GCP_REGION=$REGION \
    $IMAGE_URL

echo "CARLA Runner container started successfully"