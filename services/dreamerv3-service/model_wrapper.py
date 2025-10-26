"""
DreamerV3/CarDreamer model wrapper for autonomous driving predictions
"""

import os
import json
import logging
import asyncio
import traceback
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path

from schemas import SimulationState, DrivingAction, PredictionResponse, ActionType
from utils import load_model_config, validate_simulation_state

logger = logging.getLogger(__name__)


class DreamerModelWrapper:
    """
    Wrapper for DreamerV3/CarDreamer model providing REST API interface
    """
    
    def __init__(self):
        self.model = None
        self.model_config = None
        self.model_version = None
        self.model_type = "DreamerV3"
        self.is_initialized = False
        self.last_prediction_time = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Model paths from environment
        self.model_path = os.getenv("MODEL_PATH", "/app/models/dreamerv3")
        self.config_path = os.getenv("MODEL_CONFIG_PATH", "/app/models/config.json")
        
        logger.info(f"Initializing DreamerModelWrapper on device: {self.device}")
    
    async def initialize(self) -> bool:
        """
        Initialize the model with error handling
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("Loading model configuration...")
            self.model_config = await self._load_config()
            
            logger.info("Loading DreamerV3 model...")
            self.model = await self._load_model()
            
            logger.info("Validating model...")
            await self._validate_model()
            
            self.is_initialized = True
            logger.info("Model initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Model initialization failed: {e}")
            logger.error(traceback.format_exc())
            self.is_initialized = False
            return False
    
    async def _load_config(self) -> Dict[str, Any]:
        """Load model configuration from file"""
        try:
            config = load_model_config(self.config_path)
            self.model_version = config.get("version", "unknown")
            return config
        except Exception as e:
            logger.error(f"Failed to load model config: {e}")
            # Return default config if file not found
            return {
                "version": "1.0.0",
                "input_shape": [64, 64, 3],
                "sequence_length": 50,
                "action_space": 7,
                "batch_size": 1
            }
    
    async def _load_model(self):
        """Load the DreamerV3 model from checkpoint"""
        try:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model path not found: {self.model_path}")
            
            # Load model checkpoint
            checkpoint_path = os.path.join(self.model_path, "model.pt")
            if os.path.exists(checkpoint_path):
                logger.info(f"Loading model from checkpoint: {checkpoint_path}")
                checkpoint = torch.load(checkpoint_path, map_location=self.device)
                
                # Create model architecture (simplified for demo)
                model = DreamerV3Model(
                    input_shape=self.model_config["input_shape"],
                    action_space=self.model_config["action_space"],
                    sequence_length=self.model_config["sequence_length"]
                )
                
                model.load_state_dict(checkpoint["model_state_dict"])
                model.to(self.device)
                model.eval()
                
                return model
            else:
                # Create dummy model for demonstration
                logger.warning("No checkpoint found, creating dummy model")
                return DummyDreamerModel(self.device)
                
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            # Fallback to dummy model
            return DummyDreamerModel(self.device)
    
    async def _validate_model(self):
        """Validate model is working correctly"""
        try:
            # Create dummy input for validation
            dummy_state = self._create_dummy_simulation_state()
            
            # Run test prediction
            with torch.no_grad():
                prediction = await self._run_inference(dummy_state)
            
            if prediction is None:
                raise ValueError("Model validation failed - no prediction returned")
            
            logger.info("Model validation successful")
            
        except Exception as e:
            logger.error(f"Model validation failed: {e}")
            raise
    
    def _create_dummy_simulation_state(self) -> SimulationState:
        """Create dummy simulation state for testing"""
        return SimulationState(
            vehicle_position=[0.0, 0.0, 0.0],
            vehicle_velocity=[10.0, 0.0, 0.0],
            vehicle_rotation=[0.0, 0.0, 0.0],
            camera_data=np.random.rand(64, 64, 3).tolist(),
            lidar_data=np.random.rand(100, 3).tolist(),
            nearby_vehicles=[],
            traffic_lights=[],
            road_waypoints=[],
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def predict(self, simulation_state: SimulationState, context: Optional[Dict] = None) -> PredictionResponse:
        """
        Generate driving action prediction from simulation state
        
        Args:
            simulation_state: Current CARLA simulation state
            context: Optional context information
            
        Returns:
            PredictionResponse with driving action and confidence
        """
        if not self.is_ready():
            raise RuntimeError("Model not ready for prediction")
        
        try:
            # Validate input state
            validate_simulation_state(simulation_state)
            
            # Run model inference
            action, confidence = await self._run_inference(simulation_state, context)
            
            # Update last prediction time
            self.last_prediction_time = datetime.utcnow().isoformat()
            
            return PredictionResponse(
                action=action,
                confidence=confidence,
                model_version=self.model_version,
                timestamp=self.last_prediction_time,
                processing_time_ms=self._calculate_processing_time()
            )
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise
    
    async def _run_inference(self, simulation_state: SimulationState, context: Optional[Dict] = None) -> Tuple[DrivingAction, float]:
        """
        Run model inference on simulation state
        
        Args:
            simulation_state: Current simulation state
            context: Optional context
            
        Returns:
            Tuple of (DrivingAction, confidence_score)
        """
        try:
            # Preprocess simulation state
            model_input = self._preprocess_state(simulation_state)
            
            # Run model forward pass
            with torch.no_grad():
                output = self.model(model_input)
            
            # Postprocess output to driving action
            action, confidence = self._postprocess_output(output)
            
            return action, confidence
            
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise
    
    def _preprocess_state(self, state: SimulationState) -> torch.Tensor:
        """Preprocess simulation state for model input"""
        try:
            # Convert camera data to tensor
            camera_tensor = torch.tensor(state.camera_data, dtype=torch.float32)
            camera_tensor = camera_tensor.permute(2, 0, 1)  # HWC to CHW
            camera_tensor = camera_tensor.unsqueeze(0)  # Add batch dimension
            
            # Normalize to [0, 1] if needed
            if camera_tensor.max() > 1.0:
                camera_tensor = camera_tensor / 255.0
            
            return camera_tensor.to(self.device)
            
        except Exception as e:
            logger.error(f"Preprocessing failed: {e}")
            raise
    
    def _postprocess_output(self, output: torch.Tensor) -> Tuple[DrivingAction, float]:
        """Postprocess model output to driving action"""
        try:
            # Convert output to numpy
            output_np = output.cpu().numpy().flatten()
            
            # Extract action components (simplified mapping)
            throttle = float(np.clip(output_np[0], 0.0, 1.0))
            brake = float(np.clip(output_np[1], 0.0, 1.0))
            steering = float(np.clip(output_np[2], -1.0, 1.0))
            
            # Determine action type based on outputs
            if brake > 0.5:
                action_type = ActionType.BRAKE
            elif throttle > 0.3:
                action_type = ActionType.ACCELERATE
            elif abs(steering) > 0.2:
                action_type = ActionType.TURN_LEFT if steering < 0 else ActionType.TURN_RIGHT
            else:
                action_type = ActionType.MAINTAIN_SPEED
            
            # Calculate confidence (simplified)
            confidence = float(np.max(np.abs(output_np[:3])))
            
            action = DrivingAction(
                action_type=action_type,
                throttle=throttle,
                brake=brake,
                steering=steering,
                gear=1,
                hand_brake=False
            )
            
            return action, confidence
            
        except Exception as e:
            logger.error(f"Postprocessing failed: {e}")
            raise
    
    def _calculate_processing_time(self) -> float:
        """Calculate processing time in milliseconds"""
        # Simplified - would track actual timing in production
        return 50.0
    
    async def update_model(self, model_path: str) -> bool:
        """
        Update model with new checkpoint
        
        Args:
            model_path: Path to new model checkpoint
            
        Returns:
            bool: True if update successful
        """
        try:
            logger.info(f"Updating model from: {model_path}")
            
            # Backup current model
            old_model = self.model
            
            # Load new model
            self.model_path = model_path
            new_model = await self._load_model()
            
            # Validate new model
            self.model = new_model
            await self._validate_model()
            
            logger.info("Model update successful")
            return True
            
        except Exception as e:
            logger.error(f"Model update failed: {e}")
            # Restore old model
            self.model = old_model
            return False
    
    async def cleanup(self):
        """Cleanup model resources"""
        try:
            if self.model:
                del self.model
                self.model = None
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Model cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    def is_ready(self) -> bool:
        """Check if model is ready for predictions"""
        return self.is_initialized and self.model is not None
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def get_version(self) -> str:
        """Get model version"""
        return self.model_version or "unknown"
    
    def get_model_type(self) -> str:
        """Get model type"""
        return self.model_type
    
    def get_capabilities(self) -> List[str]:
        """Get model capabilities"""
        return [
            "autonomous_driving",
            "action_prediction",
            "world_modeling",
            "real_time_inference"
        ]
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get memory usage statistics"""
        if torch.cuda.is_available():
            return {
                "gpu_allocated_mb": torch.cuda.memory_allocated() / 1024 / 1024,
                "gpu_cached_mb": torch.cuda.memory_reserved() / 1024 / 1024
            }
        return {"cpu_usage": "unknown"}
    
    def get_last_prediction_time(self) -> Optional[str]:
        """Get timestamp of last prediction"""
        return self.last_prediction_time


class DreamerV3Model(nn.Module):
    """
    Simplified DreamerV3 model architecture for demonstration
    """
    
    def __init__(self, input_shape: List[int], action_space: int, sequence_length: int):
        super().__init__()
        
        self.input_shape = input_shape
        self.action_space = action_space
        self.sequence_length = sequence_length
        
        # Encoder
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 32, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(64, 128, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((4, 4)),
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 512)
        )
        
        # Action head
        self.action_head = nn.Sequential(
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, action_space)
        )
    
    def forward(self, x):
        features = self.encoder(x)
        actions = self.action_head(features)
        return actions


class DummyDreamerModel:
    """
    Dummy model for testing when real model is not available
    """
    
    def __init__(self, device):
        self.device = device
    
    def __call__(self, x):
        # Return dummy action predictions
        batch_size = x.shape[0]
        return torch.randn(batch_size, 7, device=self.device)
    
    def eval(self):
        pass
    
    def to(self, device):
        self.device = device
        return self