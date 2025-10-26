#!/bin/bash

# Scheduler Monitoring and Alerting Setup for Cars with a Life
# This script creates monitoring and alerting for scheduled jobs

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
REGION=${REGION:-"us-central1"}
NOTIFICATION_EMAIL=${NOTIFICATION_EMAIL:-""}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up scheduler monitoring and alerting...${NC}"

# Validate required environment variables
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID is not set${NC}"
    exit 1
fi

if [ -z "$NOTIFICATION_EMAIL" ]; then
    echo -e "${YELLOW}Warning: NOTIFICATION_EMAIL not set. Alerting will be configured but notifications disabled.${NC}"
fi

echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Notification Email: $NOTIFICATION_EMAIL"

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com

# Create notification channel if email is provided
NOTIFICATION_CHANNEL=""
if [ -n "$NOTIFICATION_EMAIL" ]; then
    echo -e "${YELLOW}Creating notification channel...${NC}"
    
    # Create notification channel
    cat > /tmp/notification-channel.json << EOF
{
  "type": "email",
  "displayName": "Cars with a Life Alerts",
  "description": "Email notifications for scheduler failures",
  "labels": {
    "email_address": "$NOTIFICATION_EMAIL"
  },
  "enabled": true
}
EOF

    NOTIFICATION_CHANNEL=$(gcloud alpha monitoring channels create --channel-content-from-file=/tmp/notification-channel.json --format="value(name)")
    rm /tmp/notification-channel.json
    echo -e "${GREEN}Created notification channel: $NOTIFICATION_CHANNEL${NC}"
fi

# Create alerting policy for scheduler job failures
echo -e "${YELLOW}Creating alerting policy for scheduler failures...${NC}"

cat > /tmp/scheduler-alert-policy.json << EOF
{
  "displayName": "Scheduler Job Failures",
  "documentation": {
    "content": "Alert when Cloud Scheduler jobs fail for Cars with a Life experiments",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Scheduler job failure rate",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_scheduler_job\" AND log_name=\"projects/$PROJECT_ID/logs/cloudscheduler.googleapis.com%2Fexecutions\" AND severity=\"ERROR\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_RATE",
            "crossSeriesReducer": "REDUCE_SUM"
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true
EOF

if [ -n "$NOTIFICATION_CHANNEL" ]; then
    cat >> /tmp/scheduler-alert-policy.json << EOF
,
  "notificationChannels": [
    "$NOTIFICATION_CHANNEL"
  ]
EOF
fi

cat >> /tmp/scheduler-alert-policy.json << EOF
}
EOF

gcloud alpha monitoring policies create --policy-from-file=/tmp/scheduler-alert-policy.json
rm /tmp/scheduler-alert-policy.json

# Create alerting policy for experiment duration anomalies
echo -e "${YELLOW}Creating alerting policy for experiment duration anomalies...${NC}"

cat > /tmp/duration-alert-policy.json << EOF
{
  "displayName": "Experiment Duration Anomalies",
  "documentation": {
    "content": "Alert when experiments take unusually long to complete",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Long running experiments",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"orchestrator-service\" AND metric.type=\"run.googleapis.com/request_latencies\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 3600000,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_PERCENTILE_95",
            "crossSeriesReducer": "REDUCE_MEAN"
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true
EOF

if [ -n "$NOTIFICATION_CHANNEL" ]; then
    cat >> /tmp/duration-alert-policy.json << EOF
,
  "notificationChannels": [
    "$NOTIFICATION_CHANNEL"
  ]
EOF
fi

cat >> /tmp/duration-alert-policy.json << EOF
}
EOF

gcloud alpha monitoring policies create --policy-from-file=/tmp/duration-alert-policy.json
rm /tmp/duration-alert-policy.json

# Create custom dashboard for scheduler monitoring
echo -e "${YELLOW}Creating monitoring dashboard...${NC}"

cat > /tmp/scheduler-dashboard.json << EOF
{
  "displayName": "Cars with a Life - Scheduler Monitoring",
  "mosaicLayout": {
    "tiles": [
      {
        "width": 6,
        "height": 4,
        "widget": {
          "title": "Scheduler Job Success Rate",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_scheduler_job\" AND log_name=\"projects/$PROJECT_ID/logs/cloudscheduler.googleapis.com%2Fexecutions\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": ["resource.labels.job_id"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Executions per second",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "widget": {
          "title": "Experiment Duration",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"orchestrator-service\" AND metric.type=\"run.googleapis.com/request_latencies\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_PERCENTILE_95",
                      "crossSeriesReducer": "REDUCE_MEAN"
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Duration (ms)",
              "scale": "LINEAR"
            }
          }
        }
      }
    ]
  }
}
EOF

gcloud monitoring dashboards create --config-from-file=/tmp/scheduler-dashboard.json
rm /tmp/scheduler-dashboard.json

echo -e "${GREEN}Scheduler monitoring and alerting setup completed successfully!${NC}"
echo ""
echo "Created monitoring resources:"
echo "  - Alerting policy for scheduler job failures"
echo "  - Alerting policy for experiment duration anomalies"
echo "  - Custom dashboard for scheduler monitoring"
if [ -n "$NOTIFICATION_EMAIL" ]; then
    echo "  - Email notification channel: $NOTIFICATION_EMAIL"
fi
echo ""
echo "View monitoring dashboard at: https://console.cloud.google.com/monitoring/dashboards"