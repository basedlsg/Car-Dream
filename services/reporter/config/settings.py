"""
Configuration settings for the Reporter Service
"""

import os
from typing import Optional


class Settings:
    """Application settings"""
    
    # Google Cloud settings
    PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT", "cars-with-life")
    DATASET_ID: str = os.getenv("BIGQUERY_DATASET", "cars_with_life")
    BUCKET_NAME: str = os.getenv("STORAGE_BUCKET", "cars-with-life-reports")
    
    # Service settings
    SERVICE_NAME: str = "reporter-service"
    SERVICE_VERSION: str = "1.0.0"
    PORT: int = int(os.getenv("PORT", "8080"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Pub/Sub settings
    PUBSUB_PROJECT_ID: str = os.getenv("PUBSUB_PROJECT_ID", PROJECT_ID)
    EXPERIMENT_TOPIC: str = os.getenv("EXPERIMENT_TOPIC", "experiment-lifecycle")
    EVALUATION_TOPIC: str = os.getenv("EVALUATION_TOPIC", "evaluation-events")
    
    # API settings
    API_TITLE: str = "Cars with Life - Reporter Service"
    API_DESCRIPTION: str = "Service for autonomous driving experiment reporting and evaluation"
    API_VERSION: str = SERVICE_VERSION
    
    # Performance settings
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "4"))
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "100"))
    
    # Validation settings
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
    VALIDATION_TIMEOUT: int = int(os.getenv("VALIDATION_TIMEOUT", "30"))


# Global settings instance
settings = Settings()