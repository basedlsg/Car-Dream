#!/bin/bash

# Cloud Scheduler Setup Script for Cars with a Life
# This script creates Cloud Scheduler jobs for automated experiment execution

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
REGION=${REGION:-"us-central1"}
ORCHESTRATOR_URL=${ORCHESTRATOR_URL:-""}
SCHEDULER_SERVICE_ACCOUNT="scheduler-service@${PROJECT_ID}.iam.gserviceaccount.com"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Cloud Scheduler for Cars with a Life...${NC}"

# Validate required environment variables
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID is not set${NC}"
    exit 1
fi

if [ -z "$ORCHESTRATOR_URL" ]; then
    echo -e "${YELLOW}Warning: ORCHESTRATOR_URL not set. You'll need to update scheduler jobs manually after deployment.${NC}"
    ORCHESTRATOR_URL="https://orchestrator-service-PLACEHOLDER.a.run.app"
fi

echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Orchestrator URL: $ORCHESTRATOR_URL"

# Enable Cloud Scheduler API
echo -e "${YELLOW}Enabling Cloud Scheduler API...${NC}"
gcloud services enable cloudscheduler.googleapis.com

# Create service account for scheduler if it doesn't exist
echo -e "${YELLOW}Creating scheduler service account...${NC}"
if ! gcloud iam service-accounts describe "$SCHEDULER_SERVICE_ACCOUNT" >/dev/null 2>&1; then
    gcloud iam service-accounts create scheduler-service \
        --display-name="Cloud Scheduler Service Account" \
        --description="Service account for automated experiment scheduling"
    echo -e "${GREEN}Created scheduler service account${NC}"
else
    echo -e "${YELLOW}Scheduler service account already exists${NC}"
fi

# Grant necessary permissions to scheduler service account
echo -e "${YELLOW}Setting up IAM permissions...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SCHEDULER_SERVICE_ACCOUNT" \
    --role="roles/run.invoker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SCHEDULER_SERVICE_ACCOUNT" \
    --role="roles/pubsub.publisher"

# Create daily experiment job
echo -e "${YELLOW}Creating daily experiment scheduler job...${NC}"
gcloud scheduler jobs create http daily-experiment-trigger \
    --location=$REGION \
    --schedule="0 9 * * *" \
    --time-zone="America/New_York" \
    --uri="$ORCHESTRATOR_URL/experiment/start" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --body='{
        "experiment_config": {
            "scenario_name": "daily_autonomous_drive",
            "map_name": "Town01",
            "duration_minutes": 30,
            "weather_conditions": {
                "cloudiness": 20,
                "precipitation": 0,
                "sun_altitude_angle": 45
            },
            "evaluation_criteria": [
                "location_accuracy",
                "action_accuracy", 
                "destination_accuracy"
            ],
            "ai_model_version": "latest"
        }
    }' \
    --oidc-service-account-email="$SCHEDULER_SERVICE_ACCOUNT" \
    --description="Daily automated experiment execution at 9 AM EST" || echo "Job may already exist"

# Create weekly comprehensive evaluation job
echo -e "${YELLOW}Creating weekly evaluation scheduler job...${NC}"
gcloud scheduler jobs create http weekly-comprehensive-evaluation \
    --location=$REGION \
    --schedule="0 10 * * 0" \
    --time-zone="America/New_York" \
    --uri="$ORCHESTRATOR_URL/experiment/start" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --body='{
        "experiment_config": {
            "scenario_name": "comprehensive_evaluation",
            "map_name": "Town02",
            "duration_minutes": 60,
            "weather_conditions": {
                "cloudiness": 50,
                "precipitation": 30,
                "sun_altitude_angle": 30
            },
            "evaluation_criteria": [
                "location_accuracy",
                "action_accuracy",
                "destination_accuracy",
                "safety_metrics",
                "efficiency_metrics"
            ],
            "ai_model_version": "latest"
        }
    }' \
    --oidc-service-account-email="$SCHEDULER_SERVICE_ACCOUNT" \
    --description="Weekly comprehensive evaluation on Sundays at 10 AM EST" || echo "Job may already exist"

# Create monitoring job for failed experiments
echo -e "${YELLOW}Creating monitoring scheduler job...${NC}"
gcloud scheduler jobs create http experiment-monitoring \
    --location=$REGION \
    --schedule="*/30 * * * *" \
    --time-zone="America/New_York" \
    --uri="$ORCHESTRATOR_URL/monitoring/check" \
    --http-method=GET \
    --oidc-service-account-email="$SCHEDULER_SERVICE_ACCOUNT" \
    --description="Monitor experiment status every 30 minutes" || echo "Job may already exist"

echo -e "${GREEN}Cloud Scheduler setup completed successfully!${NC}"
echo ""
echo "Created scheduler jobs:"
echo "  - daily-experiment-trigger: Daily at 9 AM EST"
echo "  - weekly-comprehensive-evaluation: Sundays at 10 AM EST"
echo "  - experiment-monitoring: Every 30 minutes"
echo ""
echo "Service Account: $SCHEDULER_SERVICE_ACCOUNT"
echo ""
if [[ "$ORCHESTRATOR_URL" == *"PLACEHOLDER"* ]]; then
    echo -e "${YELLOW}IMPORTANT: Update scheduler job URLs after deploying orchestrator service:${NC}"
    echo "  gcloud scheduler jobs update http daily-experiment-trigger --location=$REGION --uri=<ACTUAL_ORCHESTRATOR_URL>/experiment/start"
    echo "  gcloud scheduler jobs update http weekly-comprehensive-evaluation --location=$REGION --uri=<ACTUAL_ORCHESTRATOR_URL>/experiment/start"
    echo "  gcloud scheduler jobs update http experiment-monitoring --location=$REGION --uri=<ACTUAL_ORCHESTRATOR_URL>/monitoring/check"
fi