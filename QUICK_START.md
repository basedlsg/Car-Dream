# 🚀 Cars with a Life - Quick Start

Get your autonomous driving system up and running in minutes!

## 🎯 One-Command Deployment

```bash
./quick-start.sh
```

This interactive script will:
- ✅ Check all prerequisites
- ✅ Set up your GCP project
- ✅ Configure authentication
- ✅ Deploy the entire system
- ✅ Run health checks
- ✅ Provide service URLs and next steps

## 📋 Before You Start

### Required Tools
Make sure you have these installed:
- **Google Cloud SDK** (`gcloud`)
- **Docker Desktop**
- **Terraform**
- **Python 3.8+**

### Quick Installation (macOS)
```bash
# Install via Homebrew
brew install --cask google-cloud-sdk
brew install --cask docker
brew install terraform
brew install python@3.9
```

### Quick Installation (Linux)
```bash
# Google Cloud SDK
curl https://sdk.cloud.google.com | bash

# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Terraform
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

## 💰 Cost Awareness

**Expected Monthly Costs:**
- Development: ~$300-620/month
- Staging: ~$800-1200/month  
- Production: ~$1500-3000/month

> ⚠️ **Important**: This system uses GPU instances and AI services. Set up billing alerts!

## 🚀 Deployment Steps

### Step 1: Run Quick Start
```bash
./quick-start.sh
```

The script will ask you for:
- **Project ID** (or auto-generate one)
- **Region** (default: us-central1)
- **Environment** (development/staging/production)
- **Notification email** (optional)
- **Slack webhook** (optional)

### Step 2: Wait for Deployment
The deployment takes **20-30 minutes** and includes:
- 🏗️ Infrastructure setup (Terraform)
- 🐳 Container builds and pushes
- ☁️ Cloud services deployment
- 🤖 AI model deployment
- 📊 Monitoring setup
- ✅ Health validation

### Step 3: Test Your System
```bash
# Run integration tests
./tests/run_integration_tests.sh --project YOUR_PROJECT_ID

# Submit a test experiment
curl -X POST 'YOUR_ORCHESTRATOR_URL/experiments' \
  -H 'Content-Type: application/json' \
  -d '{
    "experiment_id": "test-001",
    "name": "My First Experiment",
    "parameters": {
      "simulation_duration": 60,
      "weather_conditions": "clear"
    }
  }'
```

## 🎛️ What Gets Deployed

### Core Services
- **🎮 CARLA Runner**: Simulation environment on GPU instances
- **🧠 DreamerV3 AI**: Decision-making AI on Vertex AI
- **🎯 Orchestrator**: Experiment management (Cloud Run)
- **📊 Reporter**: Results and analytics (Cloud Run)

### Infrastructure
- **🗄️ BigQuery**: Data warehouse for experiments
- **💾 Cloud Storage**: File storage for results
- **📡 Pub/Sub**: Real-time messaging
- **📈 Monitoring**: Dashboards and alerts
- **⏰ Scheduler**: Automated experiments

### Networking & Security
- **🔒 VPC**: Secure networking
- **🛡️ IAM**: Access control
- **🔑 Service Accounts**: Secure authentication
- **🚪 Load Balancers**: Traffic management

## 📊 Monitoring Your System

### Access Dashboards
```bash
# Your project URLs (replace YOUR_PROJECT_ID)
echo "Cloud Console: https://console.cloud.google.com/home/dashboard?project=YOUR_PROJECT_ID"
echo "Monitoring: https://console.cloud.google.com/monitoring/dashboards?project=YOUR_PROJECT_ID"
echo "Logs: https://console.cloud.google.com/logs/query?project=YOUR_PROJECT_ID"
```

### Health Checks
```bash
# Run comprehensive health check
./deploy/health-check-automation.sh --check --project YOUR_PROJECT_ID

# Continuous monitoring
./deploy/health-check-automation.sh --continuous --interval 300
```

## 🧪 Running Experiments

### Submit an Experiment
```bash
curl -X POST 'YOUR_ORCHESTRATOR_URL/experiments' \
  -H 'Content-Type: application/json' \
  -d '{
    "experiment_id": "highway-test-001",
    "name": "Highway Driving Test",
    "description": "Testing autonomous driving on highway scenarios",
    "parameters": {
      "simulation_duration": 300,
      "weather_conditions": "clear",
      "traffic_density": "medium",
      "scenario": "highway_merge",
      "ai_model_version": "latest"
    }
  }'
```

### Monitor Progress
```bash
# Check experiment status
curl 'YOUR_ORCHESTRATOR_URL/experiments/highway-test-001'

# View real-time logs
gcloud logging tail 'resource.type="cloud_run_revision"' --project=YOUR_PROJECT_ID
```

### Get Results
```bash
# Get experiment report
curl 'YOUR_REPORTER_URL/reports/highway-test-001'

# Get performance metrics
curl 'YOUR_REPORTER_URL/metrics/highway-test-001'

# Get AI-generated insights
curl 'YOUR_REPORTER_URL/notes/highway-test-001'
```

## 🛠️ Management Commands

### Scale Services
```bash
# Scale up for heavy workloads
./deploy/incident-response/emergency-scale-up.sh

# Scale down to save costs
gcloud compute instances stop carla-runner-instance --zone=YOUR_ZONE --project=YOUR_PROJECT_ID
gcloud run services update orchestrator --no-traffic --region=YOUR_REGION --project=YOUR_PROJECT_ID
```

### Update Deployment
```bash
# Redeploy with latest changes
./deploy/deploy.sh --environment development --project YOUR_PROJECT_ID

# Deploy to staging
./deploy/deploy.sh --environment staging --project YOUR_PROJECT_ID
```

### Backup and Recovery
```bash
# Create deployment snapshot
./deploy/deployment-validator.sh --snapshot --project YOUR_PROJECT_ID

# Rollback if needed
./deploy/deployment-validator.sh --rollback --service orchestrator --project YOUR_PROJECT_ID
```

## 🚨 Troubleshooting

### Common Issues

**Authentication Errors:**
```bash
gcloud auth login
gcloud auth application-default login
```

**Service Not Responding:**
```bash
# Check service status
gcloud run services list --region=YOUR_REGION --project=YOUR_PROJECT_ID

# View logs
gcloud run services logs read orchestrator --region=YOUR_REGION --project=YOUR_PROJECT_ID
```

**High Costs:**
```bash
# Check billing
gcloud billing budgets list --billing-account=YOUR_BILLING_ACCOUNT

# Emergency shutdown
gcloud compute instances stop --all --project=YOUR_PROJECT_ID
```

### Get Help
- 📖 **Full Guide**: See `DEPLOYMENT_GUIDE.md`
- 🔧 **Operations**: See `deploy/operational-runbook.md`
- 🧪 **Testing**: See `tests/README.md`
- 🐛 **Issues**: Check service logs and monitoring dashboards

## 🧹 Cleanup

### Temporary Shutdown (Keep Data)
```bash
# Stop compute instances
gcloud compute instances stop carla-runner-instance --zone=YOUR_ZONE --project=YOUR_PROJECT_ID

# Scale down Cloud Run
gcloud run services update orchestrator --no-traffic --region=YOUR_REGION --project=YOUR_PROJECT_ID
gcloud run services update reporter --no-traffic --region=YOUR_REGION --project=YOUR_PROJECT_ID
```

### Complete Cleanup (Delete Everything)
```bash
# ⚠️ WARNING: This deletes ALL resources and data
cd infrastructure/terraform
terraform destroy -auto-approve
gcloud projects delete YOUR_PROJECT_ID
```

## 🎉 Success!

Once deployed, you'll have:
- ✅ **Fully automated** autonomous driving experiments
- ✅ **AI-powered** decision making and insights
- ✅ **Comprehensive** monitoring and alerting
- ✅ **Scalable** cloud infrastructure
- ✅ **Production-ready** system

**Ready to revolutionize autonomous driving research!** 🚗🤖

---

*Need help? Check the full documentation or create an issue in the repository.*