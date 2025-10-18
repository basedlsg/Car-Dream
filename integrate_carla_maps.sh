#!/bin/bash
set -euo pipefail

# Download CARLA maps
wget https://carla-releases.s3.eu-west-3.amazonaws.com/Linux/Maps_0.9.13.tar.gz

# Extract CARLA maps
tar -xzf Maps_0.9.13.tar.gz

# Move CARLA maps to the CARLA root directory
mv Maps /opt/carla/

echo "CARLA maps integrated successfully."