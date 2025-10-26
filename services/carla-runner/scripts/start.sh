#!/bin/bash

# Start Xvfb for headless display
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99

# Initialize datasets if not already done
python3 /app/scripts/init_datasets.py

# Start CARLA server in headless mode
${CARLA_ROOT}/CarlaUE4.sh -carla-rpc-port=2000 -carla-streaming-port=2001 -opengl &

# Wait for CARLA to start
sleep 10

# Start the FastAPI service
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000