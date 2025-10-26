"""
Configuration settings for the Orchestrator Service
"""

import os
from typing import Dict, Any
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings"""
    
    # Service configuration
    service_name: str = Field(default="orchestrator-service")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)
    
    # Google Cloud configuration
    project_id: str = Field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    region: str = Field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_REGION", "us-central1"))
    
    # Pub/Sub configuration
    pubsub_project_id: str = Field(default_factory=lambda: os.getenv("PUBSUB_PROJECT_ID", ""))
    experiment_lifecycle_topic: str = Field(default="experiment-lifecycle")
    simulation_events_topic: str = Field(default="simulation-events")
    ai_decisions_topic: str = Field(default="ai-decisions")
    evaluation_events_topic: str = Field(default="evaluation-events")
    
    # Subscription names
    orchestrator_subscription: str = Field(default="orchestrator-events-sub")
    
    # Service endpoints
    carla_runner_url: str = Field(default_factory=lambda: os.getenv("CARLA_RUNNER_URL", "http://carla-runner:8080"))
    dreamerv3_service_url: str = Field(default_factory=lambda: os.getenv("DREAMERV3_SERVICE_URL", ""))
    reporter_service_url: str = Field(default_factory=lambda: os.getenv("REPORTER_SERVICE_URL", ""))
    
    # Vertex AI configuration
    vertex_ai_endpoint: str = Field(default_factory=lambda: os.getenv("VERTEX_AI_ENDPOINT", ""))
    vertex_ai_project: str = Field(default_factory=lambda: os.getenv("VERTEX_AI_PROJECT", ""))
    vertex_ai_location: str = Field(default_factory=lambda: os.getenv("VERTEX_AI_LOCATION", "us-central1"))
    
    # Database configuration (for experiment state persistence)
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///experiments.db"))
    
    # Experiment defaults
    default_experiment_timeout: int = Field(default=3600)  # 1 hour
    max_concurrent_experiments: int = Field(default=5)
    experiment_cleanup_interval: int = Field(default=300)  # 5 minutes
    
    # Cloud Scheduler configuration
    scheduler_service_account: str = Field(default_factory=lambda: os.getenv("SCHEDULER_SERVICE_ACCOUNT", ""))
    daily_experiment_schedule: str = Field(default="0 9 * * *")  # 9 AM daily
    
    # Retry configuration
    max_retries: int = Field(default=3)
    retry_delay: int = Field(default=30)  # seconds
    
    # Logging configuration
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def get_pubsub_topics(self) -> Dict[str, str]:
        """Get all Pub/Sub topic names"""
        return {
            "experiment_lifecycle": self.experiment_lifecycle_topic,
            "simulation_events": self.simulation_events_topic,
            "ai_decisions": self.ai_decisions_topic,
            "evaluation_events": self.evaluation_events_topic
        }
    
    def get_service_endpoints(self) -> Dict[str, str]:
        """Get all service endpoint URLs"""
        return {
            "carla_runner": self.carla_runner_url,
            "dreamerv3_service": self.dreamerv3_service_url,
            "reporter_service": self.reporter_service_url
        }
    
    def validate_required_settings(self) -> bool:
        """Validate that all required settings are present"""
        required_fields = [
            "project_id",
            "pubsub_project_id",
            "carla_runner_url",
            "dreamerv3_service_url"
        ]
        
        for field in required_fields:
            if not getattr(self, field):
                raise ValueError(f"Required setting '{field}' is not configured")
        
        return True