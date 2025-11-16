#!/bin/bash

# Start Xvfb for headless display
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99

# Download CARLA at runtime if not present
if [ ! -f "${CARLA_ROOT}/CarlaUE4.sh" ]; then
    echo "CARLA not found, downloading at runtime (this may take 10-30 minutes)..."
    mkdir -p ${CARLA_ROOT}
    cd /tmp
    
    # Try multiple CARLA download URLs
    CARLA_URLS=(
        "https://github.com/carla-simulator/carla/releases/download/${CARLA_VERSION}/CARLA_${CARLA_VERSION}.tar.gz"
        "https://carla-releases.s3.eu-west-3.amazonaws.com/Linux/CARLA_${CARLA_VERSION}.tar.gz"
        "https://dist.carla.org/carla-archive/Linux/CARLA_${CARLA_VERSION}.tar.gz"
    )
    
    DOWNLOADED=0
    for url in "${CARLA_URLS[@]}"; do
        echo "Attempting download from: $url"
        if curl -L --max-time 1800 --retry 3 --retry-delay 30 --fail --silent --show-error \
            -o CARLA_${CARLA_VERSION}.tar.gz \
            "$url" 2>&1 | grep -q "error\|Error\|ERROR"; then
            echo "Download failed from $url, trying next..."
            rm -f CARLA_${CARLA_VERSION}.tar.gz
            continue
        fi
        
        # Verify it's a valid gzip file
        if file CARLA_${CARLA_VERSION}.tar.gz | grep -q "gzip"; then
            echo "Valid CARLA archive downloaded, extracting..."
            tar -xzf CARLA_${CARLA_VERSION}.tar.gz -C ${CARLA_ROOT} --strip-components=1
            rm CARLA_${CARLA_VERSION}.tar.gz
            chmod +x ${CARLA_ROOT}/CarlaUE4.sh 2>/dev/null || true
            echo "CARLA installation completed at runtime"
            DOWNLOADED=1
            break
        else
            echo "Downloaded file is not a valid gzip archive, trying next URL..."
            rm -f CARLA_${CARLA_VERSION}.tar.gz
        fi
    done
    
    if [ $DOWNLOADED -eq 0 ]; then
        echo "ERROR: Failed to download CARLA from all available sources."
        echo "Please manually download CARLA ${CARLA_VERSION} and mount it, or check network connectivity."
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