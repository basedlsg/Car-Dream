# Setup and Deploy CarDream

Follow these steps to set up and deploy the CarDream system:

## Prerequisites

*   Google Cloud SDK installed and configured
*   Docker installed
*   nuScenes API key (if using nuScenes dataset)

## Setup

1.  **Authenticate with Google Cloud SDK:**

    Follow the instructions in [setup_auth.md](setup_auth.md) to authenticate with Google Cloud SDK and set the Gemini API key.

2.  **Create Artifact Registry repository:**

    ```bash
    gcloud artifacts repositories create car-dream-repository --repository-format=docker --location=us-central1
    ```

3.  **Build and push Docker images:**

    ```bash
    docker build -t carla-runner carla-runner_Dockerfile
    docker tag carla-runner us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/carla-runner:latest
    docker push us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/carla-runner:latest

    docker build -t orchestrator orchestrator_Dockerfile
    docker tag orchestrator us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/orchestrator:latest
    docker push us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/orchestrator:latest

    docker build -t reporter reporter_Dockerfile
    docker tag reporter us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/reporter:latest
    docker push us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/reporter:latest

    docker build -t dreamer-service dreamer-service_Dockerfile
    docker tag dreamer-service us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/dreamer-service:latest
    docker push us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/dreamer-service:latest
    ```

4.  **Deploy Vertex AI model and endpoint:**

    ```bash
    gcloud ai models upload --region=us-central1 --display-name="CarDreamer Model" --container-image-uri=us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/dreamer-service:latest --artifact-uri=gs://[YOUR_BUCKET]/models/cardreamer
    gcloud ai endpoints create --region=us-central1 --display-name="CarDreamer Endpoint"
    gcloud ai endpoints deploy-model --region=us-central1 --endpoint=[YOUR_ENDPOINT_ID] --model=[YOUR_MODEL_ID]
    ```

5.  **Deploy Cloud Run services:**

    ```bash
    gcloud run deploy orchestrator --image=us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/orchestrator:latest --region=us-central1 --platform-managed --allow-unauthenticated
    gcloud run deploy reporter --image=us-docker.pkg.dev/[YOUR_PROJECT]/car-dream-repository/reporter:latest --region=us-central1 --platform-managed --allow-unauthenticated
    ```

6.  **Create Pub/Sub topic and subscription:**

    ```bash
    gcloud pubsub topics create car-events
    gcloud pubsub subscriptions create car-events-subscription --topic=car-events --push-endpoint=[YOUR_REPORTER_URL]/receive_event
    ```

7.  **Create BigQuery table:**

    ```bash
    bq mk --table --schema=bigquery_schema.json [YOUR_PROJECT]:car_dream.car_events
    ```

8.  **Create Cloud Scheduler job:**

    ```bash
    gcloud scheduler jobs create http daily-car-dream-job --schedule="0 0 * * *" --http-method=POST --uri=[YOUR_ORCHESTRATOR_URL]/trigger --time-zone=UTC
    ```

9.  **Integrate datasets:**

    ```bash
    bash integrate_carla_maps.sh
    bash integrate_osm_data.sh
    bash integrate_nuscenes_data.sh
    ```

**Note:** Replace `[YOUR_PROJECT]`, `[YOUR_BUCKET]`, `[YOUR_ENDPOINT_ID]`, `[YOUR_MODEL_ID]`, `[YOUR_REPORTER_URL]`, and `[YOUR_ORCHESTRATOR_URL]` with your Google Cloud project ID, bucket name, endpoint ID, model ID, reporter URL, and orchestrator URL, respectively.