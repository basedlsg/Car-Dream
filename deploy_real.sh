#!/bin/bash

# Deploy Real Cars with a Life System
# No simulations - actual data persistence

set -e

PROJECT_ID="vertex-test-1-467818"
REGION="us-central1"
SERVICE_NAME="cars-with-a-life-real"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying REAL Cars with a Life System"
echo "=========================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Set project
echo "📋 Setting GCP project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable run.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Create BigQuery dataset
echo "🗄️  Creating BigQuery dataset..."
bq mk --dataset --location=US ${PROJECT_ID}:cars_with_a_life || echo "Dataset may already exist"

# Create Cloud Storage bucket
echo "📦 Creating Cloud Storage bucket..."
gsutil mb gs://${PROJECT_ID}-cars-data || echo "Bucket may already exist"

# Create Pub/Sub topic
echo "📡 Creating Pub/Sub topic..."
gcloud pubsub topics create experiment-events || echo "Topic may already exist"

# Build and push container
echo "🐳 Building and pushing container..."
gcloud builds submit --tag $IMAGE_NAME .

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --min-instances 1 \
    --timeout 900 \
    --concurrency 100 \
    --set-env-vars PROJECT_ID=$PROJECT_ID,REGION=$REGION

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo "✅ REAL SYSTEM DEPLOYED SUCCESSFULLY!"
echo "======================================"
echo "Service URL: $SERVICE_URL"
echo "Health Check: $SERVICE_URL/health"
echo "API Docs: $SERVICE_URL/docs"
echo ""
echo "🎯 This is a REAL system with:"
echo "   ✅ BigQuery data persistence"
echo "   ✅ Cloud Storage integration"
echo "   ✅ Pub/Sub event streaming"
echo "   ✅ Real data processing"
echo "   ✅ No simulations!"
echo ""
echo "🚀 Ready for production use!"





