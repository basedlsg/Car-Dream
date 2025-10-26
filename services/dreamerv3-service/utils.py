"""
Utility functions for DreamerV3 service
"""

import os
import json
import logging
import sys
from typing import Dict, Any
from pathlib import Path

from schemas import SimulationState


def setup_logging():
    """Setup logging configuration"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("/app/logs/dreamerv3.log") if os.path.exists("/app/logs") else logging.NullHandler()
        ]
    )


def load_model_config(config_path: str) -> Dict[str, Any]:
    """
    Load model configuration from JSON file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dict containing model configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Model config not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Validate required fields
        required_fields = ["version", "input_shape", "action_space"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")
        
        return config
        
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in config file: {e}")


def validate_simulation_state(state: SimulationState) -> bool:
    """
    Validate simulation state data
    
    Args:
        state: SimulationState to validate
        
    Returns:
        bool: True if valid
        
    Raises:
        ValueError: If validation fails
    """
    try:
        # Validate vehicle position
        if len(state.vehicle_position) != 3:
            raise ValueError("Vehicle position must have 3 coordinates")
        
        # Validate vehicle velocity
        if len(state.vehicle_velocity) != 3:
            raise ValueError("Vehicle velocity must have 3 components")
        
        # Validate vehicle rotation
        if len(state.vehicle_rotation) != 3:
            raise ValueError("Vehicle rotation must have 3 components")
        
        # Validate camera data dimensions
        if not state.camera_data:
            raise ValueError("Camera data cannot be empty")
        
        camera_height = len(state.camera_data)
        camera_width = len(state.camera_data[0]) if camera_height > 0 else 0
        camera_channels = len(state.camera_data[0][0]) if camera_width > 0 else 0
        
        if camera_channels != 3:
            raise ValueError("Camera data must have 3 channels (RGB)")
        
        # Validate LiDAR data
        if state.lidar_data:
            for point in state.lidar_data:
                if len(point) != 3:
                    raise ValueError("LiDAR points must have 3 coordinates")
        
        # Validate nearby vehicles
        for vehicle in state.nearby_vehicles:
            if len(vehicle.position) != 3:
                raise ValueError("Vehicle position must have 3 coordinates")
            if len(vehicle.velocity) != 3:
                raise ValueError("Vehicle velocity must have 3 components")
        
        # Validate traffic lights
        for light in state.traffic_lights:
            if len(light.position) != 3:
                raise ValueError("Traffic light position must have 3 coordinates")
            if light.state not in ["red", "yellow", "green", "unknown"]:
                raise ValueError("Invalid traffic light state")
        
        # Validate waypoints
        for waypoint in state.road_waypoints:
            if len(waypoint.position) != 3:
                raise ValueError("Waypoint position must have 3 coordinates")
            if len(waypoint.rotation) != 3:
                raise ValueError("Waypoint rotation must have 3 components")
        
        return True
        
    except Exception as e:
        raise ValueError(f"Simulation state validation failed: {e}")


def health_check_model(model) -> Dict[str, Any]:
    """
    Perform health check on model
    
    Args:
        model: Model instance to check
        
    Returns:
        Dict with health check results
    """
    try:
        health_info = {
            "model_loaded": model is not None,
            "model_ready": False,
            "error": None
        }
        
        if model is not None:
            # Check if model has required methods
            required_methods = ["forward", "eval"]
            for method in required_methods:
                if not hasattr(model, method):
                    health_info["error"] = f"Model missing required method: {method}"
                    return health_info
            
            health_info["model_ready"] = True
        
        return health_info
        
    except Exception as e:
        return {
            "model_loaded": False,
            "model_ready": False,
            "error": str(e)
        }


def create_model_directories():
    """Create necessary directories for model service"""
    directories = [
        "/app/models",
        "/app/logs",
        "/app/checkpoints",
        "/app/temp"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def format_memory_usage(bytes_used: int) -> str:
    """
    Format memory usage in human-readable format
    
    Args:
        bytes_used: Memory usage in bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_used < 1024.0:
            return f"{bytes_used:.1f} {unit}"
        bytes_used /= 1024.0
    return f"{bytes_used:.1f} PB"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file operations
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace unsafe characters
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    
    for char in unsafe_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')
    
    # Ensure filename is not empty
    if not sanitized:
        sanitized = "unnamed_file"
    
    return sanitized


def calculate_distance_3d(point1: list, point2: list) -> float:
    """
    Calculate 3D Euclidean distance between two points
    
    Args:
        point1: First point [x, y, z]
        point2: Second point [x, y, z]
        
    Returns:
        Distance between points
    """
    if len(point1) != 3 or len(point2) != 3:
        raise ValueError("Points must have 3 coordinates")
    
    return ((point1[0] - point2[0]) ** 2 + 
            (point1[1] - point2[1]) ** 2 + 
            (point1[2] - point2[2]) ** 2) ** 0.5


def normalize_angle(angle: float) -> float:
    """
    Normalize angle to [-π, π] range
    
    Args:
        angle: Angle in radians
        
    Returns:
        Normalized angle
    """
    import math
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def get_environment_info() -> Dict[str, Any]:
    """
    Get environment information for debugging
    
    Returns:
        Dict with environment details
    """
    import platform
    import psutil
    
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "memory_total_gb": psutil.virtual_memory().total / (1024**3),
        "disk_usage_gb": psutil.disk_usage('/').total / (1024**3),
        "environment_variables": {
            key: value for key, value in os.environ.items() 
            if key.startswith(('MODEL_', 'GCP_', 'LOG_'))
        }
    }