# 🚀 Cars with a Life - Manual Setup Guide

Since the Google Cloud CLI is experiencing connectivity issues, here's a **web-based approach** to set up your autonomous driving system.

## 🎯 Alternative Setup Methods

### Method 1: Google Cloud Console (Web Interface) - RECOMMENDED

#### Step 1: Create Project
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click "Select a project" → "New Project"
3. Name: `car-dream-[your-name]` or `car-dream-$(date +%s)`
4. Click "Create"

#### Step 2: Enable APIs
Go to [APIs & Services](https://console.cloud.google.com/apis/library) and enable:
- Compute Engine API
- Cloud Run API
- Cloud Build API
- Artifact Registry API
- Vertex AI API
- BigQuery API
- Cloud Storage API
- Pub/Sub API
- Cloud Scheduler API
- Monitoring API
- Logging API

#### Step 3: Create Storage Bucket
1. Go to [Cloud Storage](https://console.cloud.google.com/storage)
2. Click "Create Bucket"
3. Name: `car-dream-bucket`
4. Location: `us-central1`
5. Create folders: `models/cardreamer`

#### Step 4: Create Artifact Registry
1. Go to [Artifact Registry](https://console.cloud.google.com/artifacts)
2. Click "Create Repository"
3. Name: `car-dream-repository`
4. Format: Docker
5. Location: `us-central1`

#### Step 5: Deploy Services via Cloud Console
1. Go to [Cloud Run](https://console.cloud.google.com/run)
2. Click "Create Service"
3. Use the container images from your Dockerfiles
4. Configure each service (orchestrator, reporter, etc.)

### Method 2: Docker Desktop + Local Development

#### Step 1: Local Development Setup
```bash
# Build containers locally
docker build -f carla-runner_Dockerfile -t carla-runner:local .
docker build -f dreamer-service_Dockerfile -t dreamer-service:local .
docker build -f orchestrator_Dockerfile -t orchestrator:local .
docker build -f reporter_Dockerfile -t reporter:local .

# Run locally for testing
docker run -p 8080:8080 orchestrator:local
docker run -p 8081:8080 reporter:local
```

#### Step 2: Test Your System Locally
```bash
# Test orchestrator
curl -X POST 'http://localhost:8080/experiments' \
  -H 'Content-Type: application/json' \
  -d '{
    "experiment_id": "test-001",
    "name": "Local Test Experiment",
    "parameters": {
      "simulation_duration": 60,
      "weather_conditions": "clear"
    }
  }'

# Test reporter
curl 'http://localhost:8081/reports/test-001'
```

### Method 3: Alternative Cloud Providers

#### Option A: AWS Deployment
```bash
# Use AWS CLI instead
aws ecr create-repository --repository-name car-dream
aws ecs create-cluster --cluster-name car-dream-cluster
```

#### Option B: Azure Deployment
```bash
# Use Azure CLI instead
az acr create --name cardreamregistry --resource-group car-dream-rg
az container create --resource-group car-dream-rg --name car-dream-container
```

### Method 4: GitHub Actions CI/CD

Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy Car Dream
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to Google Cloud
        uses: google-github-actions/deploy-cloud-run@v0
        with:
          service: orchestrator
          image: gcr.io/${{ secrets.GCP_PROJECT }}/orchestrator:latest
```

## 🛠️ Local Development Workflow

### 1. Development Environment
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests locally
python -m pytest tests/
```

### 2. Container Development
```bash
# Build and test containers
docker-compose up --build

# Test individual services
docker run --rm -p 8080:8080 orchestrator:local
```

### 3. Integration Testing
```bash
# Run integration tests locally
./tests/run_local_tests.sh

# Test with mock services
./tests/run_mock_tests.sh
```

## 📊 Monitoring Without CLI

### Web-Based Monitoring
1. **Google Cloud Console**: https://console.cloud.google.com/monitoring
2. **Logs**: https://console.cloud.google.com/logs
3. **Billing**: https://console.cloud.google.com/billing

### Alternative Monitoring Tools
- **Grafana**: Self-hosted monitoring
- **Prometheus**: Metrics collection
- **DataDog**: Third-party monitoring
- **New Relic**: Application monitoring

## 🚀 Deployment Strategies

### Strategy 1: Manual Web Deployment
1. Use Google Cloud Console for all operations
2. Upload containers via web interface
3. Configure services through UI
4. Monitor via web dashboards

### Strategy 2: Infrastructure as Code (Terraform)
```hcl
# terraform/main.tf
resource "google_cloud_run_service" "orchestrator" {
  name     = "orchestrator"
  location = "us-central1"
  
  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/orchestrator:latest"
      }
    }
  }
}
```

### Strategy 3: Kubernetes Deployment
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orchestrator
  template:
    metadata:
      labels:
        app: orchestrator
    spec:
      containers:
      - name: orchestrator
        image: gcr.io/PROJECT_ID/orchestrator:latest
        ports:
        - containerPort: 8080
```

## 🧪 Testing Without CLI

### Local Testing Script
```bash
#!/bin/bash
# test-local.sh

echo "🧪 Testing Car Dream System Locally"

# Test orchestrator
echo "Testing orchestrator..."
curl -f http://localhost:8080/health || echo "❌ Orchestrator failed"

# Test reporter
echo "Testing reporter..."
curl -f http://localhost:8081/health || echo "❌ Reporter failed"

# Test experiment submission
echo "Testing experiment submission..."
curl -X POST http://localhost:8080/experiments \
  -H 'Content-Type: application/json' \
  -d '{"experiment_id": "test-001", "name": "Test"}' \
  && echo "✅ Experiment submission works" \
  || echo "❌ Experiment submission failed"

echo "🎉 Local testing complete!"
```

## 💡 Next Steps

1. **Choose your preferred method** from above
2. **Start with local development** to test your code
3. **Use web interfaces** for cloud deployment
4. **Set up monitoring** through web dashboards
5. **Implement CI/CD** with GitHub Actions

## 🆘 Getting Help

- **Google Cloud Console**: Use the web interface for all operations
- **Docker Desktop**: For local development and testing
- **GitHub Issues**: For code-related problems
- **Stack Overflow**: For technical questions

---

**Remember**: You don't need the CLI to build great software! Use the tools that work for you. 🚀

