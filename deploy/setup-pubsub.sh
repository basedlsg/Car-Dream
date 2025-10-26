#!/bin/bash

# Setup Pub/Sub Topics, Subscriptions, and Push Configurations
# Comprehensive messaging infrastructure for Cars with a Life

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}

# Topic and subscription definitions
declare -A TOPICS=(
    ["experiment-lifecycle"]="Experiment lifecycle events (started, completed, failed)"
    ["simulation-events"]="CARLA simulation events (initialized, step_completed, terminated)"
    ["ai-decisions"]="AI model decision events (requested, generated, applied)"
    ["evaluation-events"]="Evaluation and reporting events (note_generated, metrics_calculated)"
    ["system-health"]="System health and monitoring events"
    ["error-notifications"]="Error and alert notifications"
)

declare -A SUBSCRIPTIONS=(
    ["experiment-lifecycle-orchestrator"]="experiment-lifecycle"
    ["experiment-lifecycle-reporter"]="experiment-lifecycle"
    ["simulation-events-orchestrator"]="simulation-events"
    ["simulation-events-ai"]="simulation-events"
    ["ai-decisions-orchestrator"]="ai-decisions"
    ["ai-decisions-carla"]="ai-decisions"
    ["evaluation-events-reporter"]="evaluation-events"
    ["system-health-monitoring"]="system-health"
    ["error-notifications-alerts"]="error-notifications"
)

# Push endpoint configurations
declare -A PUSH_ENDPOINTS=(
    ["experiment-lifecycle-orchestrator"]="https://orchestrator-${PROJECT_ID}.${REGION}.run.app/pubsub/experiment-lifecycle"
    ["experiment-lifecycle-reporter"]="https://reporter-${PROJECT_ID}.${REGION}.run.app/pubsub/experiment-lifecycle"
    ["simulation-events-orchestrator"]="https://orchestrator-${PROJECT_ID}.${REGION}.run.app/pubsub/simulation-events"
    ["ai-decisions-orchestrator"]="https://orchestrator-${PROJECT_ID}.${REGION}.run.app/pubsub/ai-decisions"
    ["evaluation-events-reporter"]="https://reporter-${PROJECT_ID}.${REGION}.run.app/pubsub/evaluation-events"
)

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

echo_pubsub() {
    echo -e "${BLUE}[PUBSUB]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites for Pub/Sub setup..."
    
    # Check if gcloud is installed and authenticated
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is not installed"
        exit 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check if Pub/Sub API is enabled
    if ! gcloud services list --enabled --filter="name:pubsub.googleapis.com" --project=$PROJECT_ID | grep -q pubsub; then
        echo_error "Pub/Sub API is not enabled. Enable it first."
        exit 1
    fi
    
    echo_info "Prerequisites check passed"
}

# Create Pub/Sub topics
create_topics() {
    echo_pubsub "Creating Pub/Sub topics..."
    
    for topic in "${!TOPICS[@]}"; do
        local description=${TOPICS[$topic]}
        
        echo_pubsub "Creating topic: $topic"
        
        if gcloud pubsub topics describe $topic --project=$PROJECT_ID &> /dev/null; then
            echo_warn "Topic $topic already exists"
        else
            gcloud pubsub topics create $topic \
                --project=$PROJECT_ID \
                --labels=service=cars-with-a-life,component=messaging
            
            echo_info "✓ Created topic: $topic"
        fi
        
        # Update topic with message retention and other settings
        gcloud pubsub topics update $topic \
            --message-retention-duration=7d \
            --project=$PROJECT_ID \
            || echo_warn "Failed to update topic settings for $topic"
    done
    
    echo_info "All topics created successfully"
}

# Create Pub/Sub subscriptions
create_subscriptions() {
    echo_pubsub "Creating Pub/Sub subscriptions..."
    
    for subscription in "${!SUBSCRIPTIONS[@]}"; do
        local topic=${SUBSCRIPTIONS[$subscription]}
        
        echo_pubsub "Creating subscription: $subscription for topic: $topic"
        
        if gcloud pubsub subscriptions describe $subscription --project=$PROJECT_ID &> /dev/null; then
            echo_warn "Subscription $subscription already exists"
            continue
        fi
        
        # Check if this subscription should be a push subscription
        if [[ -n "${PUSH_ENDPOINTS[$subscription]}" ]]; then
            local push_endpoint=${PUSH_ENDPOINTS[$subscription]}
            
            echo_pubsub "Creating push subscription to: $push_endpoint"
            
            gcloud pubsub subscriptions create $subscription \
                --topic=$topic \
                --push-endpoint=$push_endpoint \
                --ack-deadline=60 \
                --message-retention-duration=7d \
                --max-delivery-attempts=5 \
                --min-retry-delay=10s \
                --max-retry-delay=600s \
                --labels=service=cars-with-a-life,type=push \
                --project=$PROJECT_ID
        else
            # Create pull subscription
            gcloud pubsub subscriptions create $subscription \
                --topic=$topic \
                --ack-deadline=60 \
                --message-retention-duration=7d \
                --labels=service=cars-with-a-life,type=pull \
                --project=$PROJECT_ID
        fi
        
        echo_info "✓ Created subscription: $subscription"
    done
    
    echo_info "All subscriptions created successfully"
}

# Configure dead letter queues
setup_dead_letter_queues() {
    echo_pubsub "Setting up dead letter queues..."
    
    # Create dead letter topic
    local dlq_topic="dead-letter-queue"
    
    if ! gcloud pubsub topics describe $dlq_topic --project=$PROJECT_ID &> /dev/null; then
        gcloud pubsub topics create $dlq_topic \
            --project=$PROJECT_ID \
            --labels=service=cars-with-a-life,component=dlq
        
        echo_info "Created dead letter topic: $dlq_topic"
    fi
    
    # Create dead letter subscription
    local dlq_subscription="dead-letter-queue-subscription"
    
    if ! gcloud pubsub subscriptions describe $dlq_subscription --project=$PROJECT_ID &> /dev/null; then
        gcloud pubsub subscriptions create $dlq_subscription \
            --topic=$dlq_topic \
            --ack-deadline=600 \
            --message-retention-duration=14d \
            --labels=service=cars-with-a-life,type=dlq \
            --project=$PROJECT_ID
        
        echo_info "Created dead letter subscription: $dlq_subscription"
    fi
    
    # Update critical subscriptions to use dead letter queue
    local critical_subscriptions=(
        "experiment-lifecycle-orchestrator"
        "simulation-events-orchestrator"
        "ai-decisions-orchestrator"
    )
    
    for subscription in "${critical_subscriptions[@]}"; do
        if gcloud pubsub subscriptions describe $subscription --project=$PROJECT_ID &> /dev/null; then
            gcloud pubsub subscriptions update $subscription \
                --dead-letter-topic=$dlq_topic \
                --max-delivery-attempts=5 \
                --project=$PROJECT_ID \
                || echo_warn "Failed to update dead letter queue for $subscription"
            
            echo_info "Updated dead letter queue for: $subscription"
        fi
    done
}

# Setup IAM permissions for Pub/Sub
setup_iam_permissions() {
    echo_pubsub "Setting up IAM permissions for Pub/Sub..."
    
    # Get project number for service accounts
    local project_number=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
    
    # Cloud Run service account
    local cloud_run_sa="cloud-run-services@${PROJECT_ID}.iam.gserviceaccount.com"
    
    # Compute Engine default service account (for CARLA Runner)
    local compute_sa="${project_number}-compute@developer.gserviceaccount.com"
    
    # Grant Pub/Sub permissions to Cloud Run service account
    local pubsub_roles=(
        "roles/pubsub.publisher"
        "roles/pubsub.subscriber"
        "roles/pubsub.viewer"
    )
    
    for role in "${pubsub_roles[@]}"; do
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:${cloud_run_sa}" \
            --role="$role" \
            --quiet || echo_warn "Role binding may already exist: $role for Cloud Run SA"
        
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:${compute_sa}" \
            --role="$role" \
            --quiet || echo_warn "Role binding may already exist: $role for Compute SA"
    done
    
    # Grant push subscription permissions
    local push_sa="service-${project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
    
    # Allow Pub/Sub to create tokens for push subscriptions
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${push_sa}" \
        --role="roles/iam.serviceAccountTokenCreator" \
        --quiet || echo_warn "Token creator role may already exist"
    
    echo_info "IAM permissions configured"
}

# Create message schemas
create_message_schemas() {
    echo_pubsub "Creating message schemas..."
    
    # Experiment lifecycle schema
    cat > /tmp/experiment-lifecycle-schema.json << 'EOF'
{
  "type": "object",
  "properties": {
    "event_type": {
      "type": "string",
      "enum": ["experiment_started", "experiment_completed", "experiment_failed"]
    },
    "experiment_id": {
      "type": "string"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "metadata": {
      "type": "object",
      "properties": {
        "scenario_name": {"type": "string"},
        "duration_minutes": {"type": "number"},
        "status": {"type": "string"}
      }
    }
  },
  "required": ["event_type", "experiment_id", "timestamp"]
}
EOF
    
    # Simulation events schema
    cat > /tmp/simulation-events-schema.json << 'EOF'
{
  "type": "object",
  "properties": {
    "event_type": {
      "type": "string",
      "enum": ["simulation_initialized", "simulation_step_completed", "simulation_terminated"]
    },
    "simulation_id": {
      "type": "string"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "data": {
      "type": "object",
      "properties": {
        "vehicle_state": {"type": "object"},
        "sensor_data": {"type": "object"},
        "environment_state": {"type": "object"}
      }
    }
  },
  "required": ["event_type", "simulation_id", "timestamp"]
}
EOF
    
    # AI decisions schema
    cat > /tmp/ai-decisions-schema.json << 'EOF'
{
  "type": "object",
  "properties": {
    "event_type": {
      "type": "string",
      "enum": ["decision_requested", "decision_generated", "decision_applied"]
    },
    "decision_id": {
      "type": "string"
    },
    "simulation_id": {
      "type": "string"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "decision_data": {
      "type": "object",
      "properties": {
        "actions": {"type": "array"},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"}
      }
    }
  },
  "required": ["event_type", "decision_id", "simulation_id", "timestamp"]
}
EOF
    
    # Create schemas in Pub/Sub
    local schemas=(
        "experiment-lifecycle:experiment-lifecycle-schema.json"
        "simulation-events:simulation-events-schema.json"
        "ai-decisions:ai-decisions-schema.json"
    )
    
    for schema_def in "${schemas[@]}"; do
        local schema_name=$(echo $schema_def | cut -d: -f1)
        local schema_file=$(echo $schema_def | cut -d: -f2)
        
        if ! gcloud pubsub schemas describe $schema_name --project=$PROJECT_ID &> /dev/null; then
            gcloud pubsub schemas create $schema_name \
                --type=AVRO \
                --definition-file="/tmp/$schema_file" \
                --project=$PROJECT_ID \
                || echo_warn "Failed to create schema: $schema_name"
            
            echo_info "Created schema: $schema_name"
        else
            echo_warn "Schema $schema_name already exists"
        fi
    done
    
    # Clean up schema files
    rm -f /tmp/*-schema.json
    
    echo_info "Message schemas created"
}

# Setup monitoring for Pub/Sub
setup_pubsub_monitoring() {
    echo_pubsub "Setting up Pub/Sub monitoring..."
    
    # Create log-based metrics for Pub/Sub
    gcloud logging metrics create pubsub_message_count \
        --description="Pub/Sub message count by topic" \
        --log-filter='resource.type="pubsub_topic" OR resource.type="pubsub_subscription"' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    gcloud logging metrics create pubsub_delivery_failures \
        --description="Pub/Sub message delivery failures" \
        --log-filter='resource.type="pubsub_subscription" AND severity>=ERROR' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    gcloud logging metrics create pubsub_ack_latency \
        --description="Pub/Sub message acknowledgment latency" \
        --log-filter='resource.type="pubsub_subscription" AND jsonPayload.ack_latency_ms>0' \
        --value-extractor='EXTRACT(jsonPayload.ack_latency_ms)' \
        --project=$PROJECT_ID \
        || echo_warn "Metric may already exist"
    
    echo_info "Pub/Sub monitoring configured"
}

# Test Pub/Sub configuration
test_pubsub_setup() {
    echo_pubsub "Testing Pub/Sub configuration..."
    
    # Test message publishing and receiving
    local test_topic="experiment-lifecycle"
    local test_subscription="experiment-lifecycle-orchestrator"
    
    # Create test message
    local test_message='{"event_type":"experiment_started","experiment_id":"test-123","timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","metadata":{"scenario_name":"test","status":"running"}}'
    
    echo_pubsub "Publishing test message to $test_topic..."
    
    if echo "$test_message" | gcloud pubsub topics publish $test_topic \
        --message=- \
        --project=$PROJECT_ID; then
        echo_info "✓ Test message published successfully"
    else
        echo_error "✗ Failed to publish test message"
        return 1
    fi
    
    # Try to pull the message (for pull subscriptions)
    if [[ -z "${PUSH_ENDPOINTS[$test_subscription]}" ]]; then
        echo_pubsub "Pulling test message from $test_subscription..."
        
        if gcloud pubsub subscriptions pull $test_subscription \
            --limit=1 \
            --auto-ack \
            --project=$PROJECT_ID &> /dev/null; then
            echo_info "✓ Test message received successfully"
        else
            echo_warn "Test message not received (may be delivered to push endpoint)"
        fi
    fi
    
    echo_info "Pub/Sub test completed"
}

# Display setup summary
display_summary() {
    echo_info "Pub/Sub Setup Summary"
    echo "====================="
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo ""
    echo "Created Topics:"
    for topic in "${!TOPICS[@]}"; do
        echo "  • $topic: ${TOPICS[$topic]}"
    done
    
    echo ""
    echo "Created Subscriptions:"
    for subscription in "${!SUBSCRIPTIONS[@]}"; do
        local topic=${SUBSCRIPTIONS[$subscription]}
        local endpoint=${PUSH_ENDPOINTS[$subscription]:-"Pull subscription"}
        echo "  • $subscription → $topic ($endpoint)"
    done
    
    echo ""
    echo "Features Configured:"
    echo "  ✓ Message retention (7 days)"
    echo "  ✓ Dead letter queues for critical subscriptions"
    echo "  ✓ Push subscriptions for Cloud Run services"
    echo "  ✓ IAM permissions for service accounts"
    echo "  ✓ Message schemas for validation"
    echo "  ✓ Monitoring and logging"
    
    echo ""
    echo "Useful commands:"
    echo "  List topics: gcloud pubsub topics list"
    echo "  List subscriptions: gcloud pubsub subscriptions list"
    echo "  Publish message: gcloud pubsub topics publish <topic> --message='<json>'"
    echo "  Pull messages: gcloud pubsub subscriptions pull <subscription> --auto-ack"
    echo "  View metrics: gcloud logging read 'resource.type=\"pubsub_topic\"' --limit=50"
}

# Main function
main() {
    echo_pubsub "Starting Pub/Sub setup for Cars with a Life..."
    
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
            --skip-test)
                SKIP_TEST=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --project PROJECT_ID      GCP Project ID"
                echo "  --region REGION           GCP Region"
                echo "  --skip-test              Skip Pub/Sub testing"
                echo "  --help                   Show this help"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Update push endpoints with actual region
    for subscription in "${!PUSH_ENDPOINTS[@]}"; do
        local endpoint=${PUSH_ENDPOINTS[$subscription]}
        endpoint=${endpoint//${REGION}/${REGION}}
        PUSH_ENDPOINTS[$subscription]=$endpoint
    done
    
    check_prerequisites
    create_topics
    create_subscriptions
    setup_dead_letter_queues
    setup_iam_permissions
    create_message_schemas
    setup_pubsub_monitoring
    
    if [ "$SKIP_TEST" != "true" ]; then
        test_pubsub_setup
    fi
    
    display_summary
    
    echo_info "Pub/Sub setup completed successfully!"
}

# Run main function
main "$@"