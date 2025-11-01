#!/bin/bash

# Start Xvfb for headless display
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99

# Download CARLA at runtime if not present (fallback if build-time download failed)
if [ ! -f "${CARLA_ROOT}/CarlaUE4.sh" ]; then
    echo "CARLA not found, downloading at runtime..."
    mkdir -p ${CARLA_ROOT}
    cd /tmp
    if curl -L --max-time 1800 --retry 5 --retry-delay 30 --location-trusted \
        -o CARLA_${CARLA_VERSION}.tar.gz \
        "https://carla-releases.s3.eu-west-3.amazonaws.com/Linux/CARLA_${CARLA_VERSION}.tar.gz"; then
        echo "CARLA download successful, extracting..."
        tar -xzf CARLA_${CARLA_VERSION}.tar.gz -C ${CARLA_ROOT} --strip-components=1
        rm CARLA_${CARLA_VERSION}.tar.gz
        chmod +x ${CARLA_ROOT}/CarlaUE4.sh
        echo "CARLA installation completed at runtime"
    else
        echo "ERROR: Failed to download CARLA at runtime. Please check network connectivity."
        exit 1
    fi
fi

# Initialize datasets if not already done
python3 /app/scripts/init_datasets.py

# Start CARLA server in headless mode
${CARLA_ROOT}/CarlaUE4.sh -carla-rpc-port=2000 -carla-streaming-port=2001 -opengl &

# Wait for CARLA to start
sleep 10

# Start the FastAPI service
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000