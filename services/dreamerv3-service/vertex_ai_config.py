"""
Vertex AI custom prediction service configuration
"""

import os
import json
import logging
from typing import Dict, Any, List
from google.cloud import aiplatform
from google.cloud.aiplatform import gapic as aip

logger = logging.getLogger(__name__)


class VertexAIPredictor:
    """
    Custom prediction service for Vertex AI deployment
    """
    
    def __init__(self):
        """Initialize the predictor"""
        self.model = None
        self.model_wrapper = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for Vertex AI"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    def load(self, artifacts_uri: str) -> None:
        """
        Load model artifacts from Cloud Storage
        
        Args:
            artifacts_uri: URI to model artifacts in Cloud Storage
        """
        try:
            logger.info(f"Loading model from artifacts URI: {artifacts_uri}")
            
            # Import here to avoid circular imports
            from model_wrapper import DreamerModelWrapper
            
            # Initialize model wrapper
            self.model_wrapper = DreamerModelWrapper()
            
            # Set model path from artifacts URI
            if artifacts_uri.startswith("gs://"):
                # Download model from Cloud Storage
                self._download_model_artifacts(artifacts_uri)
            else:
                # Use local path
                os.environ["MODEL_PATH"] = artifacts_uri
            
            # Initialize model asynchronously (simplified for Vertex AI)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(self.model_wrapper.initialize())
            
            if not success:
                raise RuntimeError("Failed to initialize model")
            
            logger.info("Model loaded successfully for Vertex AI")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def _download_model_artifacts(self, artifacts_uri: str):
        """Download model artifacts from Cloud Storage"""
        try:
            from google.cloud import storage
            
            # Parse GCS URI
            if not artifacts_uri.startswith("gs://"):
                raise ValueError("Invalid GCS URI")
            
            uri_parts = artifacts_uri[5:].split("/", 1)
            bucket_name = uri_parts[0]
            prefix = uri_parts[1] if len(uri_parts) > 1 else ""
            
            # Download artifacts
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            
            local_model_path = "/app/models"
            os.makedirs(local_model_path, exist_ok=True)
            
            # Download all files with the prefix
            blobs = bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                local_file_path = os.path.join(
                    local_model_path, 
                    os.path.basename(blob.name)
                )
                blob.download_to_filename(local_file_path)
                logger.info(f"Downloaded {blob.name} to {local_file_path}")
            
            # Set environment variable for model path
            os.environ["MODEL_PATH"] = local_model_path
            
        except Exception as e:
            logger.error(f"Failed to download model artifacts: {e}")
            raise
    
    def predict(self, instances: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Make predictions on input instances
        
        Args:
            instances: List of input instances for prediction
            
        Returns:
            Dictionary with predictions
        """
        try:
            if not self.model_wrapper or not self.model_wrapper.is_ready():
                raise RuntimeError("Model not ready for prediction")
            
            predictions = []
            
            for instance in instances:
                # Convert instance to SimulationState
                simulation_state = self._convert_instance_to_state(instance)
                
                # Run prediction (simplified synchronous version)
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                prediction = loop.run_until_complete(
                    self.model_wrapper.predict(simulation_state)
                )
                
                # Convert prediction to Vertex AI format
                vertex_prediction = self._convert_prediction_to_vertex_format(prediction)
                predictions.append(vertex_prediction)
            
            return {"predictions": predictions}
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise
    
    def _convert_instance_to_state(self, instance: Dict[str, Any]):
        """Convert Vertex AI instance to SimulationState"""
        from schemas import SimulationState
        
        try:
            # Extract required fields from instance
            return SimulationState(
                vehicle_position=instance.get("vehicle_position", [0.0, 0.0, 0.0]),
                vehicle_velocity=instance.get("vehicle_velocity", [0.0, 0.0, 0.0]),
                vehicle_rotation=instance.get("vehicle_rotation", [0.0, 0.0, 0.0]),
                camera_data=instance.get("camera_data", [[[0.0]]]),
                lidar_data=instance.get("lidar_data", [[0.0, 0.0, 0.0]]),
                nearby_vehicles=instance.get("nearby_vehicles", []),
                traffic_lights=instance.get("traffic_lights", []),
                road_waypoints=instance.get("road_waypoints", []),
                timestamp=instance.get("timestamp", ""),
                weather=instance.get("weather"),
                time_of_day=instance.get("time_of_day")
            )
        except Exception as e:
            logger.error(f"Failed to convert instance to state: {e}")
            raise
    
    def _convert_prediction_to_vertex_format(self, prediction) -> Dict[str, Any]:
        """Convert PredictionResponse to Vertex AI format"""
        try:
            return {
                "action": {
                    "action_type": prediction.action.action_type,
                    "throttle": prediction.action.throttle,
                    "brake": prediction.action.brake,
                    "steering": prediction.action.steering,
                    "gear": prediction.action.gear,
                    "hand_brake": prediction.action.hand_brake
                },
                "confidence": prediction.confidence,
                "model_version": prediction.model_version,
                "timestamp": prediction.timestamp,
                "processing_time_ms": prediction.processing_time_ms
            }
        except Exception as e:
            logger.error(f"Failed to convert prediction to Vertex format: {e}")
            raise


class VertexAIHealthChecker:
    """
    Health check service for Vertex AI deployment
    """
    
    def __init__(self, predictor: VertexAIPredictor):
        self.predictor = predictor
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check
        
        Returns:
            Health status information
        """
        try:
            status = {
                "status": "healthy",
                "model_loaded": False,
                "model_ready": False,
                "timestamp": "2024-01-01T00:00:00Z"
            }
            
            if self.predictor.model_wrapper:
                status["model_loaded"] = self.predictor.model_wrapper.is_loaded()
                status["model_ready"] = self.predictor.model_wrapper.is_ready()
                
                if status["model_ready"]:
                    status["model_version"] = self.predictor.model_wrapper.get_version()
                    status["capabilities"] = self.predictor.model_wrapper.get_capabilities()
            
            # Set overall status
            if not status["model_ready"]:
                status["status"] = "unhealthy"
            
            return status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2024-01-01T00:00:00Z"
            }


def create_vertex_ai_deployment_config() -> Dict[str, Any]:
    """
    Create Vertex AI deployment configuration
    
    Returns:
        Deployment configuration dictionary
    """
    return {
        "display_name": "dreamerv3-autonomous-driving",
        "description": "DreamerV3 model for autonomous driving decisions",
        "predict_schemata": {
            "instance_schema_uri": "gs://your-bucket/schemas/instance_schema.json",
            "prediction_schema_uri": "gs://your-bucket/schemas/prediction_schema.json"
        },
        "container_spec": {
            "image_uri": "gcr.io/your-project/dreamerv3-service:latest",
            "command": ["python", "main.py"],
            "args": [],
            "env": [
                {"name": "MODEL_PATH", "value": "/app/models"},
                {"name": "LOG_LEVEL", "value": "INFO"},
                {"name": "PORT", "value": "8080"}
            ],
            "ports": [{"container_port": 8080}],
            "predict_route": "/predict",
            "health_route": "/health"
        },
        "machine_spec": {
            "machine_type": "n1-standard-4",
            "accelerator_type": "NVIDIA_TESLA_T4",
            "accelerator_count": 1
        },
        "min_replica_count": 1,
        "max_replica_count": 10,
        "traffic_split": {"0": 100},
        "explanation_spec": {
            "parameters": {
                "sampled_shapley_attribution": {
                    "path_count": 10
                }
            },
            "metadata": {
                "inputs": {
                    "camera_data": {
                        "input_tensor_name": "camera_data",
                        "encoding": "IDENTITY",
                        "modality": "image"
                    }
                },
                "outputs": {
                    "action": {
                        "output_tensor_name": "action"
                    }
                }
            }
        }
    }


def deploy_to_vertex_ai(
    project_id: str,
    region: str,
    model_display_name: str,
    image_uri: str,
    model_artifacts_uri: str
) -> str:
    """
    Deploy model to Vertex AI
    
    Args:
        project_id: GCP project ID
        region: Deployment region
        model_display_name: Display name for the model
        image_uri: Container image URI
        model_artifacts_uri: URI to model artifacts
        
    Returns:
        Deployed model resource name
    """
    try:
        # Initialize Vertex AI
        aiplatform.init(project=project_id, location=region)
        
        # Create model
        model = aiplatform.Model.upload(
            display_name=model_display_name,
            artifact_uri=model_artifacts_uri,
            serving_container_image_uri=image_uri,
            serving_container_predict_route="/predict",
            serving_container_health_route="/health",
            serving_container_ports=[8080],
            description="DreamerV3 autonomous driving model"
        )
        
        logger.info(f"Model uploaded: {model.resource_name}")
        
        # Deploy model to endpoint
        endpoint = aiplatform.Endpoint.create(
            display_name=f"{model_display_name}-endpoint"
        )
        
        deployed_model = model.deploy(
            endpoint=endpoint,
            machine_type="n1-standard-4",
            accelerator_type="NVIDIA_TESLA_T4",
            accelerator_count=1,
            min_replica_count=1,
            max_replica_count=10,
            traffic_percentage=100
        )
        
        logger.info(f"Model deployed to endpoint: {endpoint.resource_name}")
        
        return endpoint.resource_name
        
    except Exception as e:
        logger.error(f"Deployment to Vertex AI failed: {e}")
        raise