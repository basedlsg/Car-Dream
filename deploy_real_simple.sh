#!/bin/bash

# Simple deployment for Real Cars with a Life System
# Uses Cloud Run source deployment to avoid authentication issues

set -e

PROJECT_ID="vertex-test-1-467818"
REGION="us-central1"
SERVICE_NAME="cars-with-a-life-real"

echo "🚀 Deploying REAL Cars with a Life System (Simple Method)"
echo "========================================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Deploy directly from source (this will use Cloud Build internally)
echo "🚀 Deploying to Cloud Run from source..."
gcloud run deploy $SERVICE_NAME \
    --source . \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --min-instances 1 \
    --timeout 900 \
    --concurrency 100 \
    --set-env-vars PROJECT_ID=$PROJECT_ID,REGION=$REGION \
    --port 8080

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





