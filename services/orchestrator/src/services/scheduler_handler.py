"""
Scheduler Handler Service
Handles Cloud Scheduler triggers for daily experiments
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Import shared schemas
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../shared'))
from schemas.experiment import ExperimentConfig, CarlaConfig, DreamerConfig

from config.settings import Settings

logger = logging.getLogger(__name__)


class SchedulerHandler:
    """Handles scheduled experiment triggers"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._healthy = True
        self._running = False
    
    async def start(self):
        """Start the scheduler handler"""
        try:
            self._running = True
            logger.info("Scheduler handler started")
        except Exception as e:
            logger.error(f"Failed to start scheduler handler: {str(e)}")
            self._healthy = False
            raise
    
    async def stop(self):
        """Stop the scheduler handler"""
        self._running = False
        logger.info("Scheduler handler stopped")
    
    def is_healthy(self) -> bool:
        """Check if the scheduler handler is healthy"""
        return self._healthy and self._running
    
    async def create_daily_experiment_config(self) -> ExperimentConfig:
        """Create configuration for daily scheduled experiment"""
        
        # Generate unique experiment ID with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        experiment_id = f"daily_experiment_{timestamp}"
        
        # Create CARLA configuration for daily experiment
        carla_config = CarlaConfig(
            town="Town01",  # Default town for daily experiments
            weather="ClearNoon",  # Consistent weather for comparison
            num_vehicles=50,  # Standard traffic density
            num_pedestrians=100,  # Standard pedestrian density
            simulation_time=600  # 10 minutes for daily experiments
        )
        
        # Create DreamerV3 configuration
        dreamer_config = DreamerConfig(
            model_path=self._get_latest_model_path(),
            batch_size=16,
            sequence_length=64,
            use_gpu=True
        )
        
        # Create experiment configuration
        experiment_config = ExperimentConfig(
            experiment_id=experiment_id,
            name=f"Daily Experiment - {datetime.utcnow().strftime('%Y-%m-%d')}",
            description="Automated daily experiment to evaluate AI driving performance",
            carla_config=carla_config,
            dreamer_config=dreamer_config,
            created_at=datetime.utcnow(),
            metadata={
                "trigger_type": "scheduled",
                "schedule": "daily",
                "automated": True,
                "experiment_series": "daily_evaluation"
            }
        )
        
        logger.info(f"Created daily experiment configuration: {experiment_id}")
        return experiment_config
    
    async def create_weekly_experiment_config(self) -> ExperimentConfig:
        """Create configuration for weekly comprehensive experiment"""
        
        # Generate unique experiment ID with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        experiment_id = f"weekly_experiment_{timestamp}"
        
        # Create more comprehensive CARLA configuration for weekly experiment
        carla_config = CarlaConfig(
            town="Town03",  # More complex town for weekly experiments
            weather="CloudyNoon",  # Different weather conditions
            num_vehicles=100,  # Higher traffic density
            num_pedestrians=200,  # Higher pedestrian density
            simulation_time=1800  # 30 minutes for comprehensive evaluation
        )
        
        # Create DreamerV3 configuration
        dreamer_config = DreamerConfig(
            model_path=self._get_latest_model_path(),
            batch_size=32,  # Larger batch size for weekly experiments
            sequence_length=128,  # Longer sequences for better evaluation
            use_gpu=True
        )
        
        # Create experiment configuration
        experiment_config = ExperimentConfig(
            experiment_id=experiment_id,
            name=f"Weekly Comprehensive Experiment - {datetime.utcnow().strftime('%Y-%m-%d')}",
            description="Weekly comprehensive experiment with complex scenarios",
            carla_config=carla_config,
            dreamer_config=dreamer_config,
            created_at=datetime.utcnow(),
            metadata={
                "trigger_type": "scheduled",
                "schedule": "weekly",
                "automated": True,
                "experiment_series": "weekly_comprehensive",
                "complexity_level": "high"
            }
        )
        
        logger.info(f"Created weekly experiment configuration: {experiment_id}")
        return experiment_config
    
    async def create_custom_experiment_config(
        self, 
        trigger_params: Dict[str, Any]
    ) -> ExperimentConfig:
        """Create configuration for custom scheduled experiment"""
        
        # Extract parameters from trigger
        experiment_template = trigger_params.get("experiment_template", "default")
        custom_params = trigger_params.get("parameters", {})
        
        # Generate unique experiment ID
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        experiment_id = f"custom_experiment_{timestamp}"
        
        # Create CARLA configuration based on template
        carla_config = self._create_carla_config_from_template(experiment_template, custom_params)
        
        # Create DreamerV3 configuration
        dreamer_config = DreamerConfig(
            model_path=custom_params.get("model_path", self._get_latest_model_path()),
            batch_size=custom_params.get("batch_size", 16),
            sequence_length=custom_params.get("sequence_length", 64),
            use_gpu=custom_params.get("use_gpu", True)
        )
        
        # Create experiment configuration
        experiment_config = ExperimentConfig(
            experiment_id=experiment_id,
            name=custom_params.get("name", f"Custom Experiment - {datetime.utcnow().strftime('%Y-%m-%d')}"),
            description=custom_params.get("description", "Custom scheduled experiment"),
            carla_config=carla_config,
            dreamer_config=dreamer_config,
            created_at=datetime.utcnow(),
            metadata={
                "trigger_type": "scheduled",
                "schedule": "custom",
                "automated": True,
                "experiment_template": experiment_template,
                "custom_parameters": custom_params
            }
        )
        
        logger.info(f"Created custom experiment configuration: {experiment_id}")
        return experiment_config
    
    def _create_carla_config_from_template(
        self, 
        template: str, 
        params: Dict[str, Any]
    ) -> CarlaConfig:
        """Create CARLA configuration from template"""
        
        templates = {
            "default": {
                "town": "Town01",
                "weather": "ClearNoon",
                "num_vehicles": 50,
                "num_pedestrians": 100,
                "simulation_time": 300
            },
            "complex": {
                "town": "Town03",
                "weather": "WetCloudyNoon",
                "num_vehicles": 100,
                "num_pedestrians": 200,
                "simulation_time": 600
            },
            "night": {
                "town": "Town02",
                "weather": "ClearSunset",
                "num_vehicles": 30,
                "num_pedestrians": 50,
                "simulation_time": 300
            },
            "rain": {
                "town": "Town01",
                "weather": "HardRainNoon",
                "num_vehicles": 40,
                "num_pedestrians": 80,
                "simulation_time": 300
            }
        }
        
        # Get template configuration
        template_config = templates.get(template, templates["default"])
        
        # Override with custom parameters
        config_params = {**template_config, **params}
        
        return CarlaConfig(
            town=config_params["town"],
            weather=config_params["weather"],
            num_vehicles=config_params["num_vehicles"],
            num_pedestrians=config_params["num_pedestrians"],
            simulation_time=config_params["simulation_time"]
        )
    
    def _get_latest_model_path(self) -> str:
        """Get the path to the latest trained model"""
        
        # In a real implementation, this would query the model registry
        # or check the latest model in storage
        default_model_path = "/models/dreamerv3/latest/model.pkl"
        
        # For now, return the default path
        # TODO: Implement actual model registry lookup
        return default_model_path
    
    async def validate_scheduler_trigger(self, trigger_data: Dict[str, Any]) -> bool:
        """Validate incoming scheduler trigger data"""
        
        required_fields = ["trigger_type"]
        
        for field in required_fields:
            if field not in trigger_data:
                logger.error(f"Missing required field in scheduler trigger: {field}")
                return False
        
        # Validate trigger type
        valid_trigger_types = ["daily", "weekly", "custom"]
        if trigger_data["trigger_type"] not in valid_trigger_types:
            logger.error(f"Invalid trigger type: {trigger_data['trigger_type']}")
            return False
        
        return True
    
    async def get_next_scheduled_experiments(self, hours_ahead: int = 24) -> list:
        """Get list of experiments scheduled in the next N hours"""
        
        # This would typically query a scheduling database
        # For now, return empty list as this is a placeholder
        # TODO: Implement actual scheduling database queries
        
        return []
    
    async def update_experiment_schedule(
        self, 
        schedule_id: str, 
        new_schedule: Dict[str, Any]
    ) -> bool:
        """Update an existing experiment schedule"""
        
        try:
            # TODO: Implement schedule update logic
            logger.info(f"Updated experiment schedule {schedule_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update experiment schedule {schedule_id}: {str(e)}")
            return False