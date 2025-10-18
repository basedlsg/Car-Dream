#!/bin/bash
set -euo pipefail

# Set the project ID
# Replace [YOUR_PROJECT_ID] with your Google Cloud project ID
PROJECT_ID=[YOUR_PROJECT_ID]

# Set the bucket name
# Replace [YOUR_BUCKET_NAME] with your Google Cloud bucket name
BUCKET_NAME=[YOUR_BUCKET_NAME]

# Check if the project ID and bucket name are set
if [ -z "$PROJECT_ID" ] || [ -z "$BUCKET_NAME" ]; then
  echo "Please set the PROJECT_ID and BUCKET_NAME environment variables."
  exit 1
fi

# Set the region
REGION=us-central1

# Create Artifact Registry repository
gcloud artifacts repositories create car-dream-repository --repository-format=docker --location=$REGION --project=$PROJECT_ID

# Build and push Docker images
docker build -t carla-runner carla-runner_Dockerfile
docker tag carla-runner us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/carla-runner:latest
gcloud docker push us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/carla-runner:latest

docker build -t orchestrator orchestrator_Dockerfile
docker tag orchestrator us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/orchestrator:latest
docker push us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/orchestrator:latest

docker build -t reporter reporter_Dockerfile
docker tag reporter us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/reporter:latest
docker push us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/reporter:latest

docker build -t dreamer-service dreamer-service_Dockerfile
docker tag dreamer-service us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/dreamer-service:latest
docker push us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/dreamer-service:latest

# Upload the model to GCS
gsutil cp -r models gs://$BUCKET_NAME/

# Deploy Vertex AI model and endpoint
gcloud ai models upload --region=$REGION --display-name="CarDreamer Model" --container-image-uri=us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/dreamer-service:latest --artifact-uri=gs://$BUCKET_NAME/models/cardreamer --project=$PROJECT_ID
MODEL_ID=$(gcloud ai models list --region=$REGION --project=$PROJECT_ID --filter="displayName:CarDreamer Model" --format="value(name)")
gcloud ai endpoints create --region=$REGION --display-name="CarDreamer Endpoint" --project=$PROJECT_ID
ENDPOINT_ID=$(gcloud ai endpoints list --region=$REGION --project=$PROJECT_ID --filter="displayName:CarDreamer Endpoint" --format="value(name)")
gcloud ai endpoints deploy-model --region=$REGION --endpoint=$ENDPOINT_ID --model=$MODEL_ID --project=$PROJECT_ID

# Deploy Cloud Run services
gcloud run deploy orchestrator --image=us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/orchestrator:latest --region=$REGION --platform-managed --allow-unauthenticated --project=$PROJECT_ID
ORCHESTRATOR_URL=$(gcloud run services describe orchestrator --region=$REGION --platform-managed --format="value(status.url)" --project=$PROJECT_ID)
gcloud run deploy reporter --image=us-docker.pkg.dev/$PROJECT_ID/car-dream-repository/reporter:latest --region=$REGION --platform-managed --allow-unauthenticated --project=$PROJECT_ID
REPORTER_URL=$(gcloud run services describe reporter --region=$REGION --platform-managed --format="value(status.url)" --project=$PROJECT_ID)

# Create Pub/Sub topic and subscription
gcloud pubsub topics create car-events --project=$PROJECT_ID
gcloud pubsub subscriptions create car-events-subscription --topic=car-events --push-endpoint=$REPORTER_URL/receive_event --project=$PROJECT_ID

# Create BigQuery dataset and table
bq mk --dataset --location=$REGION --project=$PROJECT_ID car_dream
bq mk --table --schema=bigquery_schema.json $PROJECT_ID:car_dream.car_events

# Create Cloud Scheduler job
gcloud scheduler jobs create http daily-car-dream-job --schedule="0 0 * * *" --http-method=POST --uri=$ORCHESTRATOR_URL/trigger --time-zone=UTC --project=$PROJECT_ID

echo "CarDream deployment completed successfully."