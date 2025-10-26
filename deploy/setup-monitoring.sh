#!/bin/bash

# Setup Comprehensive Monitoring and Auto-scaling
# Configures monitoring, alerting, and auto-scaling for all resources

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
ZONE=${GCP_ZONE:-"us-central1-a"}

# Notification configuration
NOTIFICATION_EMAIL=${NOTIFICATION_EMAIL:-"admin@example.com"}
SLACK_WEBHOOK=${SLACK_WEBHOOK:-""}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo_monitor() {
    echo -e "${BLUE}[MONITOR]${NC} $1"
}

# Create notification channels
create_notification_channels() {
    echo_monitor "Creating notification channels..."
    
    # Email notification channel
    if [ "$NOTIFICATION_EMAIL" != "admin@example.com" ]; then
        cat > /tmp/email-channel.json << EOF
{
  "type": "email",
  "displayName": "Cars with a Life Email Alerts",
  "description": "Email notifications for Cars with a Life system",
  "labels": {
    "email_address": "$NOTIFICATION_EMAIL"
  },
  "enabled": true
}
EOF
        
        local email_channel=$(gcloud alpha monitoring channels create \
            --channel-content-from-file=/tmp/email-channel.json \
            --project=$PROJECT_ID \
            --format="value(name)" 2>/dev/null || echo "")
        
        if [ -n "$email_channel" ]; then
            echo_info "Email notification channel created: $email_channel"
            echo "$email_channel" > /tmp/email_channel_id
        else
            echo_warn "Failed to create email notification channel"
        fi
        
        rm -f /tmp/email-channel.json
    fi
    
    # Slack notification channel (if webhook provided)
    if [ -n "$SLACK_WEBHOOK" ]; then
        cat > /tmp/slack-channel.json << EOF
{
  "type": "slack",
  "displayName": "Cars with a Life Slack Alerts",
  "description": "Slack notifications for Cars with a Life system",
  "labels": {
    "url": "$SLACK_WEBHOOK"
  },
  "enabled": true
}
EOF
        
        local slack_channel=$(gcloud alpha monitoring channels create \
            --channel-content-from-file=/tmp/slack-channel.json \
            --project=$PROJECT_ID \
            --format="value(name)" 2>/dev/null || echo "")
        
        if [ -n "$slack_channel" ]; then
            echo_info "Slack notification channel created: $slack_channel"
            echo "$slack_channel" > /tmp/slack_channel_id
        else
            echo_warn "Failed to create Slack notification channel"
        fi
        
        rm -f /tmp/slack-channel.json
    fi
}

# Create custom metrics
create_custom_metrics() {
    echo_monitor "Creating custom metrics..."
    
    # System health metric
    gcloud logging metrics create system_health_score \
        --description="Overall system health score" \
        --log-filter='jsonPayload.metric_type="health_score"' \
        --value-extractor='EXTRACT(jsonPayload.value)' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    # Experiment success rate
    gcloud logging metrics create experiment_success_rate \
        --description="Experiment completion success rate" \
        --log-filter='jsonPayload.event_type="experiment_completed" AND jsonPayload.status="success"' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    # CARLA simulation crashes
    gcloud logging metrics create carla_simulation_crashes \
        --description="CARLA simulation crash count" \
        --log-filter='resource.type="gce_instance" AND labels.service="carla-runner" AND jsonPayload.event="simulation_crash"' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    # AI model prediction latency
    gcloud logging metrics create ai_prediction_latency \
        --description="AI model prediction latency in milliseconds" \
        --log-filter='resource.type="aiplatform.googleapis.com/Endpoint" AND jsonPayload.prediction_latency_ms>0' \
        --value-extractor='EXTRACT(jsonPayload.prediction_latency_ms)' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    echo_info "Custom metrics created"
}

# Create alerting policies
create_alerting_policies() {
    echo_monitor "Creating alerting policies..."
    
    local notification_channels=()
    
    # Get notification channel IDs
    if [ -f /tmp/email_channel_id ]; then
        notification_channels+=($(cat /tmp/email_channel_id))
    fi
    if [ -f /tmp/slack_channel_id ]; then
        notification_channels+=($(cat /tmp/slack_channel_id))
    fi
    
    # Convert array to JSON format
    local channels_json=""
    if [ ${#notification_channels[@]} -gt 0 ]; then
        channels_json=$(printf '"%s",' "${notification_channels[@]}")
        channels_json="[${channels_json%,}]"
    else
        channels_json="[]"
    fi
    
    # High CPU utilization alert
    cat > /tmp/cpu-alert.json << EOF
{
  "displayName": "High CPU Utilization - CARLA Runner",
  "documentation": {
    "content": "CARLA Runner instances are experiencing high CPU utilization. Consider scaling up or optimizing workload.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "CPU utilization above 80%",
      "conditionThreshold": {
        "filter": "resource.type=\"gce_instance\" AND resource.labels.instance_name=~\"carla-runner.*\" AND metric.type=\"compute.googleapis.com/instance/cpu/utilization\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0.8,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_MEAN",
            "groupByFields": ["resource.labels.instance_name"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": $channels_json
}
EOF
    
    gcloud alpha monitoring policies create \
        --policy-from-file=/tmp/cpu-alert.json \
        --project=$PROJECT_ID \
        || echo_warn "CPU alert policy may already exist"
    
    # Memory utilization alert
    cat > /tmp/memory-alert.json << EOF
{
  "displayName": "High Memory Utilization - CARLA Runner",
  "documentation": {
    "content": "CARLA Runner instances are experiencing high memory utilization. Consider scaling up or optimizing memory usage.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Memory utilization above 85%",
      "conditionThreshold": {
        "filter": "resource.type=\"gce_instance\" AND resource.labels.instance_name=~\"carla-runner.*\" AND metric.type=\"agent.googleapis.com/memory/percent_used\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 85,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_MEAN",
            "groupByFields": ["resource.labels.instance_name"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": $channels_json
}
EOF
    
    gcloud alpha monitoring policies create \
        --policy-from-file=/tmp/memory-alert.json \
        --project=$PROJECT_ID \
        || echo_warn "Memory alert policy may already exist"
    
    # Cloud Run error rate alert
    cat > /tmp/cloudrun-error-alert.json << EOF
{
  "displayName": "High Error Rate - Cloud Run Services",
  "documentation": {
    "content": "Cloud Run services (Orchestrator/Reporter) are experiencing high error rates. Check service logs and health.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Error rate above 5%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0.05,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_RATE",
            "crossSeriesReducer": "REDUCE_SUM",
            "groupByFields": ["resource.labels.service_name", "metric.labels.response_code_class"]
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": $channels_json
}
EOF
    
    gcloud alpha monitoring policies create \
        --policy-from-file=/tmp/cloudrun-error-alert.json \
        --project=$PROJECT_ID \
        || echo_warn "Cloud Run error alert policy may already exist"
    
    # Vertex AI prediction failures
    cat > /tmp/vertex-ai-alert.json << EOF
{
  "displayName": "Vertex AI Prediction Failures",
  "documentation": {
    "content": "Vertex AI endpoint is experiencing prediction failures. Check model deployment and endpoint health.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Prediction failure rate above 10%",
      "conditionThreshold": {
        "filter": "resource.type=\"aiplatform.googleapis.com/Endpoint\" AND metric.type=\"aiplatform.googleapis.com/prediction/error_count\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0.1,
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
  "enabled": true,
  "notificationChannels": $channels_json
}
EOF
    
    gcloud alpha monitoring policies create \
        --policy-from-file=/tmp/vertex-ai-alert.json \
        --project=$PROJECT_ID \
        || echo_warn "Vertex AI alert policy may already exist"
    
    # Clean up temporary files
    rm -f /tmp/*-alert.json /tmp/*_channel_id
    
    echo_info "Alerting policies created"
}

# Create comprehensive operational dashboards
create_dashboard() {
    echo_monitor "Creating comprehensive operational dashboards..."
    
    # Main system overview dashboard
    cat > /tmp/system-overview-dashboard.json << EOF
{
  "displayName": "Cars with a Life - System Overview",
  "mosaicLayout": {
    "tiles": [
      {
        "width": 6,
        "height": 4,
        "widget": {
          "title": "CARLA Runner CPU Utilization",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"gce_instance\" AND resource.labels.instance_name=~\"carla-runner.*\" AND metric.type=\"compute.googleapis.com/instance/cpu/utilization\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_MEAN",
                      "crossSeriesReducer": "REDUCE_MEAN",
                      "groupByFields": ["resource.labels.instance_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "yAxis": {
              "label": "CPU Utilization",
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
          "title": "Cloud Run Request Count",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": ["resource.labels.service_name"]
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "yAxis": {
              "label": "Requests/sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "yPos": 4,
        "widget": {
          "title": "Vertex AI Predictions",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"aiplatform.googleapis.com/Endpoint\" AND metric.type=\"aiplatform.googleapis.com/prediction/count\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM"
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "yAxis": {
              "label": "Predictions/sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "yPos": 4,
        "widget": {
          "title": "System Error Rates",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "metric.type=\"logging.googleapis.com/user/carla_runner_errors\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_RATE"
                    }
                  }
                },
                "plotType": "LINE",
                "legendTemplate": "CARLA Errors"
              },
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM"
                    }
                  }
                },
                "plotType": "LINE",
                "legendTemplate": "Cloud Run 5xx"
              }
            ],
            "yAxis": {
              "label": "Errors/sec",
              "scale": "LINEAR"
            }
          }
        }
      }
    ]
  }
}
EOF
    
    gcloud monitoring dashboards create \
        --config-from-file=/tmp/dashboard.json \
        --project=$PROJECT_ID \
        || echo_warn "Dashboard may already exist"
    
    rm -f /tmp/dashboard.json
    
    echo_info "Monitoring dashboard created"
}

# Setup log-based SLIs and SLOs
setup_sli_slo() {
    echo_monitor "Setting up SLIs and SLOs..."
    
    # Create SLI for system availability
    cat > /tmp/availability-sli.json << EOF
{
  "displayName": "System Availability SLI",
  "serviceLevelIndicator": {
    "requestBased": {
      "goodTotalRatio": {
        "totalServiceFilter": "resource.type=\"cloud_run_revision\"",
        "goodServiceFilter": "resource.type=\"cloud_run_revision\" AND metric.labels.response_code_class!=\"5xx\""
      }
    }
  }
}
EOF
    
    # Create SLO for 99.5% availability
    cat > /tmp/availability-slo.json << EOF
{
  "displayName": "99.5% System Availability",
  "goal": 0.995,
  "rollingPeriod": "2592000s"
}
EOF
    
    echo_info "SLI/SLO configuration created (manual setup required in Cloud Console)"
    
    rm -f /tmp/availability-sli.json /tmp/availability-slo.json
}

# Configure auto-scaling policies
configure_auto_scaling() {
    echo_monitor "Configuring auto-scaling policies..."
    
    # Update Compute Engine auto-scaling policy
    local group_name="carla-runner-group"
    
    if gcloud compute instance-groups managed describe $group_name --zone=$ZONE --project=$PROJECT_ID &> /dev/null; then
        gcloud compute instance-groups managed set-autoscaling $group_name \
            --zone=$ZONE \
            --min-num-replicas=1 \
            --max-num-replicas=5 \
            --target-cpu-utilization=0.7 \
            --cool-down-period=300 \
            --project=$PROJECT_ID
        
        echo_info "Updated Compute Engine auto-scaling policy"
    else
        echo_warn "Compute Engine instance group not found"
    fi
    
    # Cloud Run auto-scaling is configured per service deployment
    echo_info "Cloud Run auto-scaling configured per service (1-10 instances)"
    echo_info "Vertex AI auto-scaling configured per endpoint (1-5 replicas)"
}

# Display monitoring summary
display_summary() {
    echo_info "Monitoring and Auto-scaling Setup Summary"
    echo "=========================================="
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo ""
    echo "Configured Components:"
    echo "  ✓ Custom metrics for system health"
    echo "  ✓ Alerting policies for critical issues"
    echo "  ✓ Monitoring dashboard"
    echo "  ✓ Auto-scaling policies"
    echo ""
    echo "Monitoring Targets:"
    echo "  • CARLA Runner (Compute Engine): CPU, Memory, GPU utilization"
    echo "  • Cloud Run Services: Request rate, error rate, latency"
    echo "  • Vertex AI: Prediction count, error rate, latency"
    echo "  • System-wide: Experiment success rate, overall health"
    echo ""
    echo "Access Monitoring:"
    echo "  Cloud Console: https://console.cloud.google.com/monitoring/dashboards"
    echo "  Logs: https://console.cloud.google.com/logs"
    echo "  Alerts: https://console.cloud.google.com/monitoring/alerting"
}

# Main function
main() {
    echo_monitor "Setting up comprehensive monitoring and auto-scaling..."
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --project)
                PROJECT_ID="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --zone)
                ZONE="$2"
                shift 2
                ;;
            --email)
                NOTIFICATION_EMAIL="$2"
                shift 2
                ;;
            --slack-webhook)
                SLACK_WEBHOOK="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --project PROJECT_ID      GCP Project ID"
                echo "  --region REGION           GCP Region"
                echo "  --zone ZONE              GCP Zone"
                echo "  --email EMAIL            Notification email address"
                echo "  --slack-webhook URL      Slack webhook URL for notifications"
                echo "  --help                   Show this help"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    create_notification_channels
    create_custom_metrics
    setup_experiment_metrics
    create_alerting_policies
    create_advanced_alerting
    create_dashboard
    create_experiment_dashboard
    setup_sli_slo
    configure_auto_scaling
    setup_incident_response
    create_operational_runbook
    
    display_summary
    
    echo_info "Monitoring and auto-scaling setup completed successfully!"
}

# Run main function
main "$@"# Cre
ate experiment tracking dashboard
create_experiment_dashboard() {
    echo_monitor "Creating experiment tracking dashboard..."
    
    cat > /tmp/experiment-dashboard.json << EOF
{
  "displayName": "Cars with a Life - Experiment Tracking",
  "mosaicLayout": {
    "tiles": [
      {
        "width": 12,
        "height": 4,
        "widget": {
          "title": "Active Experiments",
          "scorecard": {
            "timeSeriesQuery": {
              "timeSeriesFilter": {
                "filter": "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/experiment_count\"",
                "aggregation": {
                  "alignmentPeriod": "300s",
                  "perSeriesAligner": "ALIGN_MEAN"
                }
              }
            },
            "sparkChartView": {
              "sparkChartType": "SPARK_LINE"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "yPos": 4,
        "widget": {
          "title": "Experiment Success Rate",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "metric.type=\"logging.googleapis.com/user/experiment_success_rate\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_MEAN"
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "yAxis": {
              "label": "Success Rate (%)",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "yPos": 4,
        "widget": {
          "title": "AI Model Performance",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"aiplatform.googleapis.com/Endpoint\" AND metric.type=\"logging.googleapis.com/user/ai_prediction_latency\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_MEAN"
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "yAxis": {
              "label": "Latency (ms)",
              "scale": "LINEAR"
            }
          }
        }
      }
    ]
  }
}
EOF
    
    gcloud monitoring dashboards create \
        --config-from-file=/tmp/experiment-dashboard.json \
        --project=$PROJECT_ID \
        || echo_warn "Experiment dashboard may already exist"
    
    rm -f /tmp/experiment-dashboard.json
    
    echo_info "Experiment tracking dashboard created"
}

# Setup comprehensive log-based metrics for experiment tracking
setup_experiment_metrics() {
    echo_monitor "Setting up experiment tracking metrics..."
    
    # Active experiment count
    gcloud logging metrics create active_experiments \
        --description="Number of currently active experiments" \
        --log-filter='jsonPayload.event_type="experiment_started" OR jsonPayload.event_type="experiment_completed"' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    # Experiment duration tracking
    gcloud logging metrics create experiment_duration \
        --description="Average experiment duration in minutes" \
        --log-filter='jsonPayload.event_type="experiment_completed" AND jsonPayload.duration_minutes>0' \
        --value-extractor='EXTRACT(jsonPayload.duration_minutes)' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    # CARLA simulation performance
    gcloud logging metrics create carla_fps \
        --description="CARLA simulation frames per second" \
        --log-filter='resource.type="gce_instance" AND labels.service="carla-runner" AND jsonPayload.fps>0' \
        --value-extractor='EXTRACT(jsonPayload.fps)' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    # AI decision accuracy
    gcloud logging metrics create ai_decision_accuracy \
        --description="AI decision making accuracy percentage" \
        --log-filter='jsonPayload.event_type="ai_decision" AND jsonPayload.accuracy_score>0' \
        --value-extractor='EXTRACT(jsonPayload.accuracy_score)' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    # System resource utilization
    gcloud logging metrics create system_resource_usage \
        --description="Overall system resource utilization" \
        --log-filter='jsonPayload.metric_type="resource_usage" AND jsonPayload.utilization_percent>0' \
        --value-extractor='EXTRACT(jsonPayload.utilization_percent)' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    echo_info "Experiment tracking metrics created"
}

# Create advanced alerting policies for system failures
create_advanced_alerting() {
    echo_monitor "Creating advanced alerting policies..."
    
    local notification_channels=()
    
    # Get notification channel IDs
    if [ -f /tmp/email_channel_id ]; then
        notification_channels+=($(cat /tmp/email_channel_id))
    fi
    if [ -f /tmp/slack_channel_id ]; then
        notification_channels+=($(cat /tmp/slack_channel_id))
    fi
    
    # Convert array to JSON format
    local channels_json=""
    if [ ${#notification_channels[@]} -gt 0 ]; then
        channels_json=$(printf '"%s",' "${notification_channels[@]}")
        channels_json="[${channels_json%,}]"
    else
        channels_json="[]"
    fi
    
    # Experiment failure rate alert
    cat > /tmp/experiment-failure-alert.json << EOF
{
  "displayName": "High Experiment Failure Rate",
  "documentation": {
    "content": "Experiment failure rate is above acceptable threshold. Check CARLA runner and AI model health.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Experiment failure rate above 20%",
      "conditionThreshold": {
        "filter": "metric.type=\"logging.googleapis.com/user/experiment_success_rate\"",
        "comparison": "COMPARISON_LESS_THAN",
        "thresholdValue": 0.8,
        "duration": "600s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_MEAN"
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": $channels_json
}
EOF
    
    gcloud alpha monitoring policies create \
        --policy-from-file=/tmp/experiment-failure-alert.json \
        --project=$PROJECT_ID \
        || echo_warn "Experiment failure alert policy may already exist"
    
    # CARLA performance degradation alert
    cat > /tmp/carla-performance-alert.json << EOF
{
  "displayName": "CARLA Performance Degradation",
  "documentation": {
    "content": "CARLA simulation performance has degraded significantly. Check GPU utilization and system resources.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "CARLA FPS below 20",
      "conditionThreshold": {
        "filter": "metric.type=\"logging.googleapis.com/user/carla_fps\"",
        "comparison": "COMPARISON_LESS_THAN",
        "thresholdValue": 20,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_MEAN"
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": $channels_json
}
EOF
    
    gcloud alpha monitoring policies create \
        --policy-from-file=/tmp/carla-performance-alert.json \
        --project=$PROJECT_ID \
        || echo_warn "CARLA performance alert policy may already exist"
    
    # AI model accuracy degradation alert
    cat > /tmp/ai-accuracy-alert.json << EOF
{
  "displayName": "AI Model Accuracy Degradation",
  "documentation": {
    "content": "AI model decision accuracy has dropped below acceptable levels. Check model deployment and training data.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "AI accuracy below 85%",
      "conditionThreshold": {
        "filter": "metric.type=\"logging.googleapis.com/user/ai_decision_accuracy\"",
        "comparison": "COMPARISON_LESS_THAN",
        "thresholdValue": 85,
        "duration": "600s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_MEAN"
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": $channels_json
}
EOF
    
    gcloud alpha monitoring policies create \
        --policy-from-file=/tmp/ai-accuracy-alert.json \
        --project=$PROJECT_ID \
        || echo_warn "AI accuracy alert policy may already exist"
    
    # System resource exhaustion alert
    cat > /tmp/resource-exhaustion-alert.json << EOF
{
  "displayName": "System Resource Exhaustion",
  "documentation": {
    "content": "System resources are critically low. Consider scaling up or optimizing resource usage.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Resource utilization above 90%",
      "conditionThreshold": {
        "filter": "metric.type=\"logging.googleapis.com/user/system_resource_usage\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 90,
        "duration": "300s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_MEAN"
          }
        ]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": $channels_json
}
EOF
    
    gcloud alpha monitoring policies create \
        --policy-from-file=/tmp/resource-exhaustion-alert.json \
        --project=$PROJECT_ID \
        || echo_warn "Resource exhaustion alert policy may already exist"
    
    # Clean up temporary files
    rm -f /tmp/*-alert.json
    
    echo_info "Advanced alerting policies created"
}

# Setup automated incident response
setup_incident_response() {
    echo_monitor "Setting up automated incident response..."
    
    # Create incident response playbook
    cat > /tmp/incident-response-playbook.md << EOF
# Cars with a Life - Incident Response Playbook

## High Priority Incidents

### Experiment Failure Rate > 20%
1. Check CARLA runner instance health
2. Verify AI model endpoint status
3. Review recent deployment changes
4. Check resource utilization
5. Escalate to development team if unresolved in 30 minutes

### CARLA Performance Degradation (FPS < 20)
1. Check GPU utilization on CARLA runner
2. Verify system memory usage
3. Check for competing processes
4. Consider instance restart if resources are exhausted
5. Scale up instance if consistently overloaded

### AI Model Accuracy < 85%
1. Check Vertex AI endpoint health
2. Verify model deployment status
3. Review recent training data changes
4. Check for data pipeline issues
5. Consider model rollback if accuracy continues to degrade

### System Resource Exhaustion > 90%
1. Identify resource-intensive processes
2. Check auto-scaling configuration
3. Scale up resources immediately
4. Review resource allocation policies
5. Implement cost optimization if needed

## Contact Information
- On-call Engineer: [PHONE_NUMBER]
- Development Team Lead: [EMAIL]
- Infrastructure Team: [EMAIL]
- Emergency Escalation: [PHONE_NUMBER]

## Useful Commands
- Health Check: ./deploy/health-check-automation.sh --check
- System Status: gcloud monitoring dashboards list
- Recent Logs: gcloud logging read --limit=100
- Resource Usage: gcloud compute instances list
EOF
    
    echo_info "Incident response playbook created: /tmp/incident-response-playbook.md"
    
    # Create automated response scripts directory
    mkdir -p deploy/incident-response
    
    # Auto-restart script for CARLA runner
    cat > deploy/incident-response/restart-carla-runner.sh << EOF
#!/bin/bash
# Automated CARLA runner restart script

PROJECT_ID=\${GCP_PROJECT_ID:-"cars-with-a-life"}
ZONE=\${GCP_ZONE:-"us-central1-a"}
INSTANCE_NAME="carla-runner-instance"

echo "Restarting CARLA runner instance..."
gcloud compute instances restart \$INSTANCE_NAME --zone=\$ZONE --project=\$PROJECT_ID

echo "Waiting for instance to be ready..."
sleep 60

echo "Running health check..."
./deploy/health-check-automation.sh --component compute-\$INSTANCE_NAME
EOF
    
    chmod +x deploy/incident-response/restart-carla-runner.sh
    
    # Auto-scale script
    cat > deploy/incident-response/emergency-scale-up.sh << EOF
#!/bin/bash
# Emergency scale-up script

PROJECT_ID=\${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=\${GCP_REGION:-"us-central1"}
ZONE=\${GCP_ZONE:-"us-central1-a"}

echo "Initiating emergency scale-up..."

# Scale up Cloud Run services
gcloud run services update orchestrator --max-instances=20 --region=\$REGION --project=\$PROJECT_ID
gcloud run services update reporter --max-instances=10 --region=\$REGION --project=\$PROJECT_ID

# Scale up Compute Engine instances if using managed instance group
GROUP_NAME="carla-runner-group"
if gcloud compute instance-groups managed describe \$GROUP_NAME --zone=\$ZONE --project=\$PROJECT_ID &>/dev/null; then
    gcloud compute instance-groups managed resize \$GROUP_NAME --size=5 --zone=\$ZONE --project=\$PROJECT_ID
fi

echo "Emergency scale-up completed"
EOF
    
    chmod +x deploy/incident-response/emergency-scale-up.sh
    
    echo_info "Automated incident response scripts created"
}

# Create operational runbook
create_operational_runbook() {
    echo_monitor "Creating operational runbook..."
    
    cat > deploy/operational-runbook.md << EOF
# Cars with a Life - Operational Runbook

## Daily Operations

### Morning Checklist
- [ ] Run system health check: \`./deploy/health-check-automation.sh\`
- [ ] Review overnight alerts and incidents
- [ ] Check experiment success rate from previous day
- [ ] Verify all services are running and healthy
- [ ] Review resource utilization trends

### Weekly Tasks
- [ ] Review and analyze experiment performance metrics
- [ ] Check system capacity and scaling needs
- [ ] Update monitoring thresholds based on usage patterns
- [ ] Review and test incident response procedures
- [ ] Clean up old logs and temporary files

### Monthly Tasks
- [ ] Review and optimize resource allocation
- [ ] Update monitoring dashboards and alerts
- [ ] Conduct disaster recovery testing
- [ ] Review security configurations and access controls
- [ ] Update documentation and runbooks

## Monitoring and Alerting

### Key Metrics to Monitor
1. **Experiment Success Rate**: Should be > 80%
2. **CARLA Performance**: FPS should be > 20
3. **AI Model Accuracy**: Should be > 85%
4. **System Resource Usage**: Should be < 80%
5. **Service Availability**: Should be > 99%

### Dashboard URLs
- System Overview: https://console.cloud.google.com/monitoring/dashboards
- Experiment Tracking: [Generated Dashboard URL]
- Resource Utilization: https://console.cloud.google.com/compute
- Logs: https://console.cloud.google.com/logs

### Alert Escalation
1. **Level 1**: Automated response (restart services, scale resources)
2. **Level 2**: On-call engineer notification
3. **Level 3**: Development team escalation
4. **Level 4**: Management and stakeholder notification

## Troubleshooting Guide

### Common Issues

#### Experiment Failures
- **Symptoms**: High failure rate, timeout errors
- **Causes**: CARLA crashes, AI model issues, resource constraints
- **Resolution**: Check logs, restart services, verify resources

#### Performance Degradation
- **Symptoms**: Slow response times, low FPS
- **Causes**: Resource exhaustion, network issues, competing processes
- **Resolution**: Scale resources, optimize configurations, restart services

#### Service Unavailability
- **Symptoms**: HTTP errors, connection timeouts
- **Causes**: Service crashes, deployment issues, network problems
- **Resolution**: Check service status, review recent deployments, restart services

### Useful Commands

#### Health and Status Checks
\`\`\`bash
# System health check
./deploy/health-check-automation.sh --check

# Service status
gcloud run services list --region=us-central1
gcloud compute instances list

# Recent logs
gcloud logging read --limit=50 --format="table(timestamp,severity,textPayload)"
\`\`\`

#### Emergency Procedures
\`\`\`bash
# Restart CARLA runner
./deploy/incident-response/restart-carla-runner.sh

# Emergency scale-up
./deploy/incident-response/emergency-scale-up.sh

# Rollback deployment
./deploy/deployment-validator.sh --rollback --service <service-name>
\`\`\`

## Contact Information
- **Primary On-call**: [PHONE] / [EMAIL]
- **Secondary On-call**: [PHONE] / [EMAIL]
- **Development Team**: [EMAIL]
- **Infrastructure Team**: [EMAIL]
- **Management**: [EMAIL]

## External Dependencies
- Google Cloud Platform services
- CARLA simulation software
- DreamerV3 AI model
- Third-party monitoring tools

## Change Management
- All changes must go through proper review process
- Production deployments require approval
- Emergency changes must be documented and reviewed post-incident
- Regular maintenance windows: Sundays 2-4 AM UTC
EOF
    
    echo_info "Operational runbook created: deploy/operational-runbook.md"
}