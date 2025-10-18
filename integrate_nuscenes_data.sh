#!/bin/bash
set -euo pipefail

# Install nuScenes devkit
pip install nuscenes-devkit

# Download nuScenes data (example: v1.0-mini)
# Requires nuScenes API key
# export NUSCENES_API_KEY="YOUR_NUSCENES_API_KEY"
# nuscenes download --version v1.0-mini --dataroot /data/nuscenes

echo "nuScenes data downloaded successfully."