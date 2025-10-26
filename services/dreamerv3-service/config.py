"""
Configuration settings for DreamerV3 service
"""

import os
from typing import Dict, Any, Optional
from pydantic import BaseSettings, Field


class ServiceConfig(BaseSettings):
    """Service configuration with environment variable support"""
    
    # Service settings
    service_name: str = Field(default="dreamerv3-service", env="SERVICE_NAME")
    service_version: str = Field(default="1.0.0", env="SERVICE_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    port: int = Field(default=8080, env="PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Model settings
    model_path: str = Field(default="/app/models/dreamerv3", env="MODEL_PATH")
    model_config_path: str = Field(default="/app/models/config.json", env="MODEL_CONFIG_PATH")
    model_type: str = Field(default="DreamerV3", env="MODEL_TYPE")
    
    # GCP settings
    gcp_project_id: Optional[str] = Field(default=None, env="GCP_PROJECT_ID")
    gcp_region: str = Field(default="us-central1", env="GCP_REGION")
    
    # Pub/Sub topics
    ai_decisions_topic: str = Field(default="ai-decisions", env="AI_DECISIONS_TOPIC")
    experiment_events_topic: str = Field(default="experiment-events", env="EXPERIMENT_EVENTS_TOPIC")
    model_metrics_topic: str = Field(default="model-metrics", env="MODEL_METRICS_TOPIC")
    
    # Performance settings
    max_batch_size: int = Field(default=50, env="MAX_BATCH_SIZE")
    prediction_timeout_seconds: int = Field(default=30, env="PREDICTION_TIMEOUT_SECONDS")
    health_check_interval_seconds: int = Field(default=60, env="HEALTH_CHECK_INTERVAL_SECONDS")
    
    # Decision engine settings
    safety_distance_threshold: float = Field(default=10.0, env="SAFETY_DISTANCE_THRESHOLD")
    emergency_brake_distance: float = Field(default=5.0, env="EMERGENCY_BRAKE_DISTANCE")
    lane_change_min_gap: float = Field(default=15.0, env="LANE_CHANGE_MIN_GAP")
    speed_limit_buffer: float = Field(default=0.9, env="SPEED_LIMIT_BUFFER")
    
    # Security settings
    enable_cors: bool = Field(default=True, env="ENABLE_CORS")
    allowed_origins: str = Field(default="*", env="ALLOWED_ORIGINS")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class DecisionWeights(BaseSettings):
    """Decision engine weights configuration"""
    
    safety: float = Field(default=0.4, env="WEIGHT_SAFETY")
    efficiency: float = Field(default=0.3, env="WEIGHT_EFFICIENCY")
    comfort: float = Field(default=0.2, env="WEIGHT_COMFORT")
    traffic_compliance: float = Field(default=0.1, env="WEIGHT_TRAFFIC_COMPLIANCE")
    
    def validate_weights(self) -> bool:
        """Validate that weights sum to 1.0"""
        total = self.safety + self.efficiency + self.comfort + self.traffic_compliance
        return abs(total - 1.0) < 0.01
    
    def normalize_weights(self) -> Dict[str, float]:
        """Normalize weights to sum to 1.0"""
        total = self.safety + self.efficiency + self.comfort + self.traffic_compliance
        if total == 0:
            # Equal weights if all are zero
            return {"safety": 0.25, "efficiency": 0.25, "comfort": 0.25, "traffic_compliance": 0.25}
        
        return {
            "safety": self.safety / total,
            "efficiency": self.efficiency / total,
            "comfort": self.comfort / total,
            "traffic_compliance": self.traffic_compliance / total
        }


# Global configuration instances
config = ServiceConfig()
decision_weights = DecisionWeights()


def get_config() -> ServiceConfig:
    """Get service configuration"""
    return config


def get_decision_weights() -> Dict[str, float]:
    """Get normalized decision weights"""
    return decision_weights.normalize_weights()


def update_config_from_dict(config_dict: Dict[str, Any]) -> None:
    """Update configuration from dictionary"""
    global config
    
    for key, value in config_dict.items():
        if hasattr(config, key):
            setattr(config, key, value)


def get_environment_config() -> Dict[str, Any]:
    """Get environment-specific configuration"""
    env = config.environment.lower()
    
    base_config = {
        "log_level": config.log_level,
        "enable_debug": False,
        "enable_metrics": True,
        "enable_pubsub": True
    }
    
    if env == "development":
        return {
            **base_config,
            "log_level": "DEBUG",
            "enable_debug": True,
            "enable_pubsub": False  # Disable Pub/Sub in development
        }
    elif env == "testing":
        return {
            **base_config,
            "log_level": "WARNING",
            "enable_metrics": False,
            "enable_pubsub": False
        }
    elif env == "production":
        return {
            **base_config,
            "log_level": "INFO",
            "enable_debug": False
        }
    else:
        return base_config


def validate_config() -> bool:
    """Validate configuration settings"""
    try:
        # Check required settings for production
        if config.environment == "production":
            if not config.gcp_project_id:
                raise ValueError("GCP_PROJECT_ID is required in production")
        
        # Validate decision weights
        if not decision_weights.validate_weights():
            print("Warning: Decision weights do not sum to 1.0, will be normalized")
        
        # Validate numeric ranges
        if config.max_batch_size <= 0 or config.max_batch_size > 1000:
            raise ValueError("MAX_BATCH_SIZE must be between 1 and 1000")
        
        if config.prediction_timeout_seconds <= 0:
            raise ValueError("PREDICTION_TIMEOUT_SECONDS must be positive")
        
        return True
        
    except Exception as e:
        print(f"Configuration validation failed: {e}")
        return False