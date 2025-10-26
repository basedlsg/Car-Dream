#!/bin/bash

# Scheduler Management Utility for Cars with a Life
# This script provides utilities to manage Cloud Scheduler jobs

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
REGION=${REGION:-"us-central1"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display usage
usage() {
    echo -e "${BLUE}Usage: $0 [COMMAND] [OPTIONS]${NC}"
    echo ""
    echo "Commands:"
    echo "  list                    List all scheduler jobs"
    echo "  status                  Show status of all jobs"
    echo "  pause [JOB_NAME]        Pause a specific job or all jobs"
    echo "  resume [JOB_NAME]       Resume a specific job or all jobs"
    echo "  run [JOB_NAME]          Manually trigger a job"
    echo "  update-url [URL]        Update orchestrator URL for all jobs"
    echo "  logs [JOB_NAME]         Show recent logs for a job"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 pause daily-experiment-trigger"
    echo "  $0 update-url https://orchestrator-service-abc123.a.run.app"
    echo "  $0 run daily-experiment-trigger"
}

# Function to list all jobs
list_jobs() {
    echo -e "${YELLOW}Listing all scheduler jobs...${NC}"
    gcloud scheduler jobs list --location=$REGION --format="table(name,schedule,state,lastAttemptTime)"
}

# Function to show job status
show_status() {
    echo -e "${YELLOW}Scheduler jobs status:${NC}"
    gcloud scheduler jobs list --location=$REGION --format="table(name,state,lastAttemptTime,httpTarget.uri)"
}

# Function to pause jobs
pause_job() {
    local job_name=$1
    if [ -z "$job_name" ]; then
        echo -e "${YELLOW}Pausing all Cars with a Life scheduler jobs...${NC}"
        for job in daily-experiment-trigger weekly-comprehensive-evaluation experiment-monitoring; do
            gcloud scheduler jobs pause $job --location=$REGION || echo "Job $job may not exist"
        done
    else
        echo -e "${YELLOW}Pausing job: $job_name${NC}"
        gcloud scheduler jobs pause $job_name --location=$REGION
    fi
    echo -e "${GREEN}Job(s) paused successfully${NC}"
}

# Function to resume jobs
resume_job() {
    local job_name=$1
    if [ -z "$job_name" ]; then
        echo -e "${YELLOW}Resuming all Cars with a Life scheduler jobs...${NC}"
        for job in daily-experiment-trigger weekly-comprehensive-evaluation experiment-monitoring; do
            gcloud scheduler jobs resume $job --location=$REGION || echo "Job $job may not exist"
        done
    else
        echo -e "${YELLOW}Resuming job: $job_name${NC}"
        gcloud scheduler jobs resume $job_name --location=$REGION
    fi
    echo -e "${GREEN}Job(s) resumed successfully${NC}"
}

# Function to manually run a job
run_job() {
    local job_name=$1
    if [ -z "$job_name" ]; then
        echo -e "${RED}Error: Job name is required for manual execution${NC}"
        echo "Available jobs: daily-experiment-trigger, weekly-comprehensive-evaluation, experiment-monitoring"
        exit 1
    fi
    
    echo -e "${YELLOW}Manually triggering job: $job_name${NC}"
    gcloud scheduler jobs run $job_name --location=$REGION
    echo -e "${GREEN}Job triggered successfully${NC}"
}

# Function to update orchestrator URL
update_url() {
    local new_url=$1
    if [ -z "$new_url" ]; then
        echo -e "${RED}Error: New URL is required${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}Updating orchestrator URL to: $new_url${NC}"
    
    # Update daily experiment trigger
    gcloud scheduler jobs update http daily-experiment-trigger \
        --location=$REGION \
        --uri="$new_url/experiment/start"
    
    # Update weekly evaluation trigger
    gcloud scheduler jobs update http weekly-comprehensive-evaluation \
        --location=$REGION \
        --uri="$new_url/experiment/start"
    
    # Update monitoring job
    gcloud scheduler jobs update http experiment-monitoring \
        --location=$REGION \
        --uri="$new_url/monitoring/check"
    
    echo -e "${GREEN}All job URLs updated successfully${NC}"
}

# Function to show logs
show_logs() {
    local job_name=$1
    if [ -z "$job_name" ]; then
        echo -e "${RED}Error: Job name is required for logs${NC}"
        echo "Available jobs: daily-experiment-trigger, weekly-comprehensive-evaluation, experiment-monitoring"
        exit 1
    fi
    
    echo -e "${YELLOW}Showing recent logs for job: $job_name${NC}"
    gcloud logging read "resource.type=\"cloud_scheduler_job\" AND resource.labels.job_id=\"$job_name\"" \
        --limit=20 \
        --format="table(timestamp,severity,textPayload)" \
        --freshness=1d
}

# Main script logic
case "${1:-}" in
    "list")
        list_jobs
        ;;
    "status")
        show_status
        ;;
    "pause")
        pause_job "$2"
        ;;
    "resume")
        resume_job "$2"
        ;;
    "run")
        run_job "$2"
        ;;
    "update-url")
        update_url "$2"
        ;;
    "logs")
        show_logs "$2"
        ;;
    "help"|"-h"|"--help")
        usage
        ;;
    "")
        echo -e "${RED}Error: No command specified${NC}"
        usage
        exit 1
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$1'${NC}"
        usage
        exit 1
        ;;
esac