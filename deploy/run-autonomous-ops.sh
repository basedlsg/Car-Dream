#!/usr/bin/env bash

set -euo pipefail

PROJECT_ID=${GCP_PROJECT_ID:-"vertex-test-1-467818"}
REGION=${GCP_REGION:-"us-central1"}
ZONE=${GCP_ZONE:-"us-central1-a"}
INTERVAL=${AUTONOMOUS_INTERVAL_SECONDS:-300}

ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"

echo "[AUTONOMOUS] Project: $PROJECT_ID | Region: $REGION | Zone: $ZONE | Interval: ${INTERVAL}s"

# One pass of health + remediation
run_cycle(){
  echo "[AUTONOMOUS] Running health check..."
  "${ROOT_DIR}/deploy/health-check-automation.sh" --check --project "$PROJECT_ID" --region "$REGION" || true

  echo "[AUTONOMOUS] Running remediation..."
  "${ROOT_DIR}/deploy/auto-remediation.sh" --project "$PROJECT_ID" --region "$REGION" --zone "$ZONE" || true
}

if [[ "${1:-}" == "--once" ]]; then
  run_cycle
  exit 0
fi

echo "[AUTONOMOUS] Starting continuous health + remediation every ${INTERVAL}s"
while true; do
  run_cycle
  echo "[AUTONOMOUS] Sleeping ${INTERVAL}s"
  sleep "$INTERVAL"
done


