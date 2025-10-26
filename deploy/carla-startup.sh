#!/bin/bash

# Startup script for CARLA Runner Compute Engine instance

# Install Docker and NVIDIA drivers
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Configure Docker to use gcloud as credential helper
gcloud auth configure-docker

# Pull and run CARLA Runner container
PROJECT_ID=$(curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/project/project-id)
docker pull gcr.io/$PROJECT_ID/carla-runner

# Run container with GPU support
docker run -d \
    --name carla-runner \
    --gpus all \
    -p 2000:2000 \
    -p 2001:2001 \
    -p 2002:2002 \
    --restart unless-stopped \
    gcr.io/$PROJECT_ID/carla-runner

echo "CARLA Runner container started successfully"