# Cars with a Life - Complete Deployment Guide

This guide will walk you through deploying the entire Cars with a Life autonomous driving system on Google Cloud Platform, from initial setup to running experiments.

## 📋 Prerequisites

### Required Tools
- **Google Cloud SDK** (gcloud CLI)
- **Docker Desktop**
- **Terraform** (v1.0+)
- **Python 3.8+**
- **Git**
- **kubectl** (for Kubernetes management)

### System Requirements
- **macOS/Linux/Windows** with WSL2
- **8GB+ RAM** (16GB recommended)
- **50GB+ free disk space**
- **Stable internet connection**

## 💰 Cost Estimation

**Expected Monthly Costs (Development Environment):**
- Compute Engine (CARLA Runner): ~$150-300/month
- Cloud Run Services: ~$20-50/month
- Vertex AI: ~$100-200/month
- Storage & BigQuery: ~$10-30/month
- Networking & Monitoring: ~$20-40/month

**Total Estimated Cost: $300-620/month**

> ⚠️ **Cost Warning**: This system uses GPU instances and AI services. Monitor your usage closely and set up billing alerts.

## 🚀 Step-by-Step Deployment

### Phase 1: Google Cloud Platform Setup

#### 1.1 Install Google Cloud SDK

**macOS (using Homebrew):**
```bash
brew install --cask google-cloud-sdk
```

**Linux:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**Windows:**
Download and install from: https://cloud.google.com/sdk/docs/install

#### 1.2 Create GCP Project

```bash
# Authenticate with Google Cloud
gcloud auth login

# Create a new project (replace with your preferred project ID)
export PROJECT_ID="cars-with-a-life-$(date +%Y%m%d)"
gcloud projects create $PROJECT_ID --name="Cars with a Life"

# Set the project as default
gcloud config set project $PROJECT_ID

# Enable billing (you'll need to link a billing account)
echo "⚠️  Enable billing for project $PROJECT_ID in the GCP Console"
echo "   https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
```

#### 1.3 Set Up Authentication

```bash
# Create a service account for deployment
gcloud iam service-accounts create cars-deployment \
    --display-name="Cars with a Life Deployment" \
    --description="Service account for deploying Cars with a Life system"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:cars-deployment@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/owner"

# Create and download service account key
gcloud iam service-accounts keys create ~/cars-deployment-key.json \
    --iam-account=cars-deployment@$PROJECT_ID.iam.gserviceaccount.com

# Set up application default credentials
export GOOGLE_APPLICATION_CREDENTIALS=~/cars-deployment-key.json
gcloud auth application-default login
```

#### 1.4 Enable Required APIs

```bash
# Enable all required Google Cloud APIs
gcloud services enable \
    compute.googleapis.com \
    run.googleapis.com \
    aiplatform.googleapis.com \
    storage.googleapis.com \
    pubsub.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    bigquery.googleapis.com \
    cloudscheduler.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com \
    cloudresourcemanager.googleapis.com
```

### Phase 2: Environment Configuration

#### 2.1 Set Environment Variables

```bash
# Core configuration
export GCP_PROJECT_ID=$PROJECT_ID
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"
export ENVIRONMENT="development"

# Optional: Notification settings
export NOTIFICATION_EMAIL="your-email@example.com"
export SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"

# Save to your shell profile
echo "export GCP_PROJECT_ID=$PROJECT_ID" >> ~/.bashrc
echo "export GCP_REGION=us-central1" >> ~/.bashrc
echo "export GCP_ZONE=us-central1-a" >> ~/.bashrc
echo "export ENVIRONMENT=development" >> ~/.bashrc
```

#### 2.2 Generate Environment Configuration

```bash
# Generate environment-specific configurations
./deploy/environment-config.sh --generate --environment development
./deploy/environment-config.sh --validate --environment development
./deploy/environment-config.sh --display --environment development
```

### Phase 3: Infrastructure Deployment

#### 3.1 Initialize Terraform

```bash
# Navigate to Terraform directory
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Create terraform.tfvars file
cat > terraform.tfvars << EOF
project_id = "$GCP_PROJECT_ID"
region = "$GCP_REGION"
zone = "$GCP_ZONE"
environment = "$ENVIRONMENT"
machine_type = "e2-standard-4"
gpu_type = "nvidia-tesla-t4"
gpu_count = 1
disk_size_gb = 100
min_instances = 1
max_instances = 3
EOF

# Plan the deployment
terraform plan -var-file=terraform.tfvars

# Apply the infrastructure (this will create resources and incur costs)
terraform apply -var-file=terraform.tfvars
```

#### 3.2 Run Master Deployment Script

```bash
# Return to project root
cd ../..

# Run the complete deployment (this is the main deployment command)
./deploy/deploy.sh --environment development --project $GCP_PROJECT_ID --region $GCP_REGION
```

**What this script does:**
1. ✅ Sets up Artifact Registry
2. ✅ Builds and pushes all container images
3. ✅ Deploys infrastructure with Terraform
4. ✅ Sets up networking and authentication
5. ✅ Creates Pub/Sub topics and subscriptions
6. ✅ Sets up BigQuery datasets and tables
7. ✅ Deploys Compute Engine instances (CARLA Runner)
8. ✅ Deploys Vertex AI endpoints (DreamerV3)
9. ✅ Deploys Cloud Run services (Orchestrator & Reporter)
10. ✅ Sets up comprehensive monitoring
11. ✅ Configures automated scheduling
12. ✅ Validates entire deployment

### Phase 4: Verification and Testing

#### 4.1 Run Health Checks

```bash
# Comprehensive system health check
./deploy/health-check-automation.sh --check --project $GCP_PROJECT_ID --region $GCP_REGION

# Continuous monitoring (optional)
./deploy/health-check-automation.sh --continuous --interval 60
```

#### 4.2 Run Integration Tests

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run complete integration test suite
./tests/run_integration_tests.sh --environment development --project $GCP_PROJECT_ID
```

#### 4.3 Verify Services

```bash
# Get service URLs
ORCHESTRATOR_URL=$(gcloud run services describe orchestrator \
    --region=$GCP_REGION --project=$GCP_PROJECT_ID \
    --format="value(status.url)")

REPORTER_URL=$(gcloud run services describe reporter \
    --region=$GCP_REGION --project=$GCP_PROJECT_ID \
    --format="value(status.url)")

echo "🚀 Services deployed successfully!"
echo "Orchestrator: $ORCHESTRATOR_URL"
echo "Reporter: $REPORTER_URL"

# Test service endpoints
curl "$ORCHESTRATOR_URL/health"
curl "$REPORTER_URL/health"
```

### Phase 5: Running Your First Experiment

#### 5.1 Submit an Experiment

```bash
# Create a test experiment
curl -X POST "$ORCHESTRATOR_URL/experiments" \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_id": "test-experiment-001",
    "name": "First Test Experiment",
    "description": "Testing the complete pipeline",
    "parameters": {
      "simulation_duration": 120,
      "weather_conditions": "clear",
      "traffic_density": "light",
      "ai_model_version": "latest"
    }
  }'
```

#### 5.2 Monitor Experiment Progress

```bash
# Check experiment status
curl "$ORCHESTRATOR_URL/experiments/test-experiment-001"

# View logs
gcloud logging read 'resource.type="cloud_run_revision"' --limit=50 --project=$GCP_PROJECT_ID

# Monitor in real-time
gcloud logging tail 'resource.type="cloud_run_revision"' --project=$GCP_PROJECT_ID
```

#### 5.3 View Results

```bash
# Get experiment report
curl "$REPORTER_URL/reports/test-experiment-001"

# Get metrics
curl "$REPORTER_URL/metrics/test-experiment-001"

# Get autonomous notes
curl "$REPORTER_URL/notes/test-experiment-001"
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### Issue: "Permission denied" errors
```bash
# Re-authenticate
gcloud auth login
gcloud auth application-default login

# Check project permissions
gcloud projects get-iam-policy $GCP_PROJECT_ID
```

#### Issue: "Quota exceeded" errors
```bash
# Check quotas
gcloud compute project-info describe --project=$GCP_PROJECT_ID

# Request quota increases in GCP Console:
# https://console.cloud.google.com/iam-admin/quotas
```

#### Issue: Container build failures
```bash
# Check Docker is running
docker info

# Rebuild specific service
./deploy/build-and-push-containers.sh --service orchestrator --project $GCP_PROJECT_ID
```

#### Issue: Services not responding
```bash
# Check service status
gcloud run services list --region=$GCP_REGION --project=$GCP_PROJECT_ID

# View service logs
gcloud run services logs read orchestrator --region=$GCP_REGION --project=$GCP_PROJECT_ID

# Restart services
gcloud run services update orchestrator --region=$GCP_REGION --project=$GCP_PROJECT_ID
```

#### Issue: High costs
```bash
# Check current usage
gcloud billing budgets list --billing-account=YOUR_BILLING_ACCOUNT

# Scale down for development
./deploy/incident-response/emergency-scale-down.sh

# Stop all services temporarily
gcloud run services update orchestrator --no-traffic --region=$GCP_REGION --project=$GCP_PROJECT_ID
gcloud compute instances stop carla-runner-instance --zone=$GCP_ZONE --project=$GCP_PROJECT_ID
```

## 📊 Monitoring and Operations

### Access Monitoring Dashboards

```bash
# Open monitoring dashboards
echo "📊 Monitoring Dashboard:"
echo "https://console.cloud.google.com/monitoring/dashboards?project=$GCP_PROJECT_ID"

echo "📋 Cloud Console:"
echo "https://console.cloud.google.com/home/dashboard?project=$GCP_PROJECT_ID"

echo "🔍 Logs Explorer:"
echo "https://console.cloud.google.com/logs/query?project=$GCP_PROJECT_ID"
```

### Set Up Alerts

```bash
# Configure email notifications
./deploy/setup-monitoring.sh --email $NOTIFICATION_EMAIL --project $GCP_PROJECT_ID --region $GCP_REGION

# Set up Slack notifications (if webhook provided)
./deploy/setup-monitoring.sh --slack-webhook $SLACK_WEBHOOK --project $GCP_PROJECT_ID --region $GCP_REGION
```

## 🛑 Cleanup and Cost Management

### Temporary Shutdown (Preserve Data)

```bash
# Stop compute instances
gcloud compute instances stop carla-runner-instance --zone=$GCP_ZONE --project=$GCP_PROJECT_ID

# Scale down Cloud Run to zero
gcloud run services update orchestrator --no-traffic --region=$GCP_REGION --project=$GCP_PROJECT_ID
gcloud run services update reporter --no-traffic --region=$GCP_REGION --project=$GCP_PROJECT_ID
```

### Complete Cleanup (Delete Everything)

```bash
# ⚠️ WARNING: This will delete ALL resources and data
# Run Terraform destroy
cd infrastructure/terraform
terraform destroy -var-file=terraform.tfvars -auto-approve

# Delete remaining resources
gcloud projects delete $GCP_PROJECT_ID
```

## 📚 Additional Resources

### Documentation
- [Google Cloud Documentation](https://cloud.google.com/docs)
- [CARLA Simulator Documentation](https://carla.readthedocs.io/)
- [DreamerV3 Paper](https://arxiv.org/abs/2301.04104)

### Monitoring and Debugging
- **Cloud Console**: https://console.cloud.google.com
- **Monitoring**: https://console.cloud.google.com/monitoring
- **Logs**: https://console.cloud.google.com/logs
- **Billing**: https://console.cloud.google.com/billing

### Support Commands

```bash
# Get deployment status
./deploy/deployment-validator.sh --validate --project $GCP_PROJECT_ID --region $GCP_REGION

# Emergency procedures
./deploy/incident-response/restart-carla-runner.sh
./deploy/incident-response/emergency-scale-up.sh

# Health monitoring
./deploy/health-check-automation.sh --check --project $GCP_PROJECT_ID --region $GCP_REGION
```

## 🎯 Next Steps

After successful deployment:

1. **🔬 Run Experiments**: Submit various experiment configurations
2. **📈 Monitor Performance**: Use the monitoring dashboards
3. **🔧 Optimize Costs**: Adjust instance sizes and scaling policies
4. **🚀 Scale Up**: Move to staging/production environments
5. **🤖 Customize AI**: Train custom DreamerV3 models
6. **📊 Analyze Results**: Use the autonomous notes and metrics

## ⚠️ Important Notes

- **Costs**: Monitor your GCP billing dashboard regularly
- **Security**: Keep your service account keys secure
- **Backups**: Important data is stored in BigQuery and Cloud Storage
- **Updates**: Regularly update the system using the deployment scripts
- **Support**: Check the operational runbook in `deploy/operational-runbook.md`

---

**🎉 Congratulations!** You now have a fully deployed Cars with a Life autonomous driving system running on Google Cloud Platform. The system is ready to run experiments, generate insights, and help advance autonomous driving research.

For ongoing operations, refer to the operational runbook and monitoring dashboards. Happy experimenting! 🚗🤖