#!/bin/bash

set -euo pipefail

PROJECT_ID="vertex-test-1-467818"
REGION="us-central1"
ZONE="us-central1-a"
INSTANCE_NAME="cars-with-a-life-vm"
MACHINE_TYPE="e2-standard-2"
NETWORK_TAG="cars-with-a-life"
PORT="8080"

echo "==> Setting project"
gcloud config set project "$PROJECT_ID" >/dev/null

echo "==> Ensuring firewall rule tcp:${PORT} exists"
if ! gcloud compute firewall-rules describe allow-cars-with-a-life-${PORT} >/dev/null 2>&1; then
  gcloud compute firewall-rules create allow-cars-with-a-life-${PORT} \
    --allow tcp:${PORT} \
    --target-tags ${NETWORK_TAG} \
    --description "Allow HTTP traffic on ${PORT} for Cars with a Life"
else
  echo "Firewall rule already exists"
fi

echo "==> Creating VM ${INSTANCE_NAME} in ${ZONE}"
# Write startup script to a temp file to avoid metadata quoting issues
STARTUP_FILE="/tmp/cars-startup.sh"
cat > "$STARTUP_FILE" <<'EOF'
#!/bin/bash
set -euo pipefail
apt-get update -y
apt-get install -y python3 python3-venv python3-pip

APP_DIR=/opt/cars
mkdir -p "$APP_DIR"
cd "$APP_DIR"

cat > requirements.txt <<REQ
fastapi==0.111.0
uvicorn[standard]==0.30.1
pydantic==2.8.2
REQ

cat > app.py <<'PY'
from fastapi import FastAPI
from datetime import datetime, timezone
import os

app = FastAPI(title="Cars with a Life - VM")

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "cars-with-a-life-vm",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_id": os.getenv("PROJECT_ID", "unknown"),
        "region": os.getenv("REGION", "unknown")
    }
PY

python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt

# Run app without systemd to avoid service issues; log to file
export PROJECT_ID="vertex-test-1-467818"
export REGION="us-central1"
nohup ${APP_DIR}/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8080 > /var/log/cars.log 2>&1 &
EOF

# Create the VM with metadata startup-script
if ! gcloud compute instances describe "$INSTANCE_NAME" --zone "$ZONE" >/dev/null 2>&1; then
  gcloud compute instances create "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --scopes=cloud-platform \
    --tags="$NETWORK_TAG" \
    --metadata-from-file=startup-script="$STARTUP_FILE" \
    --image-family=debian-12 \
    --image-project=debian-cloud
else
  echo "VM already exists; updating startup script and restarting service"
  gcloud compute instances add-metadata "$INSTANCE_NAME" --zone "$ZONE" \
    --metadata-from-file=startup-script="$STARTUP_FILE"
  gcloud compute instances reset "$INSTANCE_NAME" --zone "$ZONE"
fi

echo "==> Waiting for external IP"
for i in {1..30}; do
  IP=$(gcloud compute instances describe "$INSTANCE_NAME" --zone "$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
  if [[ -n "$IP" ]]; then
    break
  fi
  sleep 2
done

if [[ -z "${IP:-}" ]]; then
  echo "Failed to obtain external IP" >&2
  exit 1
fi

echo "==> VM External IP: ${IP}"
echo "==> Health URL: http://${IP}:8080/health"

# Quick health check from this machine (may fail if egress blocked)
set +e
curl -sS --max-time 10 "http://${IP}:8080/health" || true
