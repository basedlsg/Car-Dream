#!/usr/bin/env bash

# Autonomous Remediation for Cars with a Life
# - Detects and fixes common deployment drifts automatically
# - Safe, idempotent, and non-destructive where possible

set -euo pipefail

# Defaults (override with flags or env)
PROJECT_ID=${GCP_PROJECT_ID:-"vertex-test-1-467818"}
REGION=${GCP_REGION:-"us-central1"}
ZONE=${GCP_ZONE:-"us-central1-a"}

# Resources expected by the system
declare -A CLOUD_RUN_SERVICES=(
  ["orchestrator"]="/health"
  ["reporter"]="/health"
)

COMPUTE_INSTANCES=(
  "carla-runner-instance"
)

PUBSUB_TOPICS=(
  "experiment-events"
  "ai-decisions"
  "model-metrics"
)

BUCKETS=(
  "${PROJECT_ID}-carla-data"
  "${PROJECT_ID}-models"
  "${PROJECT_ID}-results"
)

BQ_DATASET="cars_with_a_life"
BQ_TABLE_SQL_DIR="$(cd "$(dirname "$0")" && pwd)/schemas"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info(){ echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn(){ echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err(){ echo -e "${RED}[ERROR]${NC} $1"; }
log_step(){ echo -e "${BLUE}[STEP]${NC} $1"; }

ensure_project_access(){
  if ! gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
    log_err "Cannot access project $PROJECT_ID. Set GCP credentials and project."
    exit 1
  fi
}

ensure_cloud_run_ready(){
  local service=$1
  local status
  status=$(gcloud run services describe "$service" \
    --region="$REGION" --project="$PROJECT_ID" \
    --format="value(status.conditions[0].status)" 2>/dev/null || true)

  if [[ -z "$status" ]]; then
    log_warn "Cloud Run service $service not found in $REGION. Skipping create (managed elsewhere)."
    return 0
  fi

  if [[ "$status" != "True" ]]; then
    log_warn "Cloud Run $service not ready (status=$status). Triggering a no-op update to refresh."
    gcloud run services update "$service" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1 || true
  fi

  # Hit health endpoint if available
  local url
  url=$(gcloud run services describe "$service" --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)" 2>/dev/null || true)
  if [[ -n "$url" ]]; then
    curl -fsS --max-time 10 "$url/health" >/dev/null 2>&1 || log_warn "Health check failed for $service"
  fi
}

ensure_compute_instance_running(){
  local instance=$1
  local status
  status=$(gcloud compute instances describe "$instance" --zone="$ZONE" --project="$PROJECT_ID" --format="value(status)" 2>/dev/null || true)
  if [[ -z "$status" ]]; then
    log_warn "Compute instance $instance not found. Skipping create (managed by IaC)."
    return 0
  fi
  if [[ "$status" != "RUNNING" ]]; then
    log_step "Starting instance $instance"
    gcloud compute instances start "$instance" --zone="$ZONE" --project="$PROJECT_ID" >/dev/null 2>&1 || log_warn "Failed to start $instance"
  fi
}

ensure_pubsub_topic(){
  local topic=$1
  if ! gcloud pubsub topics describe "$topic" --project="$PROJECT_ID" >/dev/null 2>&1; then
    log_step "Creating Pub/Sub topic $topic"
    gcloud pubsub topics create "$topic" --project="$PROJECT_ID" >/dev/null 2>&1 || log_warn "Failed to create topic $topic"
  fi
}

ensure_bucket(){
  local bucket=$1
  # Prefer gcloud storage (faster control-plane)
  if ! gcloud storage buckets list --project="$PROJECT_ID" --format="value(name)" | grep -qx "$bucket"; then
    log_step "Creating bucket gs://$bucket in $REGION"
    gcloud storage buckets create "gs://$bucket" --project="$PROJECT_ID" --location="$REGION" >/dev/null 2>&1 || log_warn "Failed to create bucket $bucket"
  fi
}

ensure_bigquery_dataset(){
  if ! bq --project_id="$PROJECT_ID" ls | awk '{print $1}' | grep -qx "$BQ_DATASET"; then
    log_step "Creating BigQuery dataset $BQ_DATASET"
    # Use retries to mitigate transient timeouts
    local attempts=0
    local max_attempts=5
    until bq --project_id="$PROJECT_ID" mk "$BQ_DATASET" >/dev/null 2>&1; do
      attempts=$((attempts+1))
      if (( attempts >= max_attempts )); then
        log_warn "Dataset creation timed out after $attempts attempts. Continuing."
        break
      fi
      sleep 5
    done
  fi
}

ensure_bigquery_tables(){
  # Create tables from SQL files if dataset exists
  if ! bq --project_id="$PROJECT_ID" ls | awk '{print $1}' | grep -qx "$BQ_DATASET"; then
    log_warn "Dataset $BQ_DATASET not present; skipping table creation."
    return 0
  fi
  local created_any=false
  for sql in "$BQ_TABLE_SQL_DIR"/*.sql; do
    [[ -e "$sql" ]] || continue
    local table
    table=$(basename "$sql" .sql)
    if ! bq --project_id="$PROJECT_ID" show -t ${BQ_DATASET}.${table} >/dev/null 2>&1; then
      log_step "Creating table ${BQ_DATASET}.${table} from $(basename "$sql")"
      if bq --project_id="$PROJECT_ID" query --use_legacy_sql=false < "$sql" >/dev/null 2>&1; then
        created_any=true
      else
        log_warn "Failed to create table ${BQ_DATASET}.${table} (will not fail script)"
      fi
    fi
  done
  $created_any && log_info "BigQuery tables ensured from $BQ_TABLE_SQL_DIR"
}

run_once(){
  ensure_project_access

  # Cloud Run
  for svc in "${!CLOUD_RUN_SERVICES[@]}"; do
    ensure_cloud_run_ready "$svc"
  done

  # Compute
  for inst in "${COMPUTE_INSTANCES[@]}"; do
    ensure_compute_instance_running "$inst"
  done

  # Pub/Sub
  for t in "${PUBSUB_TOPICS[@]}"; do
    ensure_pubsub_topic "$t"
  done

  # Storage
  for b in "${BUCKETS[@]}"; do
    ensure_bucket "$b"
  done

  # BigQuery
  ensure_bigquery_dataset
  ensure_bigquery_tables

  log_info "Autonomous remediation pass completed."
}

usage(){
  cat <<EOF
Usage: $0 [--project ID] [--region REGION] [--zone ZONE] [--continuous SECONDS]

Runs autonomous remediation to ensure required resources exist and are healthy.

Options:
  --project ID        GCP project ID (default: $PROJECT_ID)
  --region REGION     GCP region (default: $REGION)
  --zone ZONE         GCP zone (default: $ZONE)
  --continuous N      Run in a loop every N seconds
  --help              Show this help
EOF
}

main(){
  local interval=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project) PROJECT_ID="$2"; shift 2;;
      --region) REGION="$2"; shift 2;;
      --zone) ZONE="$2"; shift 2;;
      --continuous) interval="$2"; shift 2;;
      --help) usage; exit 0;;
      *) log_err "Unknown option: $1"; usage; exit 1;;
    esac
  done

  if [[ -n "$interval" ]]; then
    log_info "Starting autonomous remediation loop (every ${interval}s)"
    while true; do
      run_once || true
      sleep "$interval"
    done
  else
    run_once
  fi
}

main "$@"


