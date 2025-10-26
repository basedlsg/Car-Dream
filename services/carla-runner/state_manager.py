"""
Simulation state management and persistence for CARLA runner.
Handles state recovery, error handling, and health monitoring.
"""

import json
import logging
import os
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

import carla
from google.cloud import storage

logger = logging.getLogger(__name__)

class SimulationStatus(Enum):
    """Simulation status enumeration."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    CRASHED = "crashed"
    TERMINATED = "terminated"


@dataclass
class SimulationCheckpoint:
    """Simulation state checkpoint for recovery."""
    simulation_id: str
    timestamp: datetime
    vehicle_transform: Dict[str, float]
    vehicle_physics: Dict[str, Any]
    world_state: Dict[str, Any]
    weather_conditions: Dict[str, Any]
    traffic_state: Dict[str, Any]
    sensor_configs: Dict[str, Any]


@dataclass
class ErrorRecord:
    """Error record for tracking simulation issues."""
    timestamp: datetime
    simulation_id: str
    error_type: str
    error_message: str
    stack_trace: str
    recovery_attempted: bool
    recovery_successful: bool


class StateManager:
    """Manages simulation state persistence and recovery."""
    
    def __init__(self, storage_path: str = "/tmp/carla_state"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize GCS client for remote state backup
        try:
            self.gcs_client = storage.Client()
            self.bucket_name = os.environ.get('CARLA_STATE_BUCKET', 'carla-state-backup')
            self.bucket = self.gcs_client.bucket(self.bucket_name)
        except Exception as e:
            logger.warning(f"Could not initialize GCS for state backup: {e}")
            self.gcs_client = None
        
        self.checkpoints: Dict[str, SimulationCheckpoint] = {}
        self.error_history: List[ErrorRecord] = []
        
        # Load existing state if available
        self._load_state()
    
    def create_checkpoint(self, simulation_id: str, vehicle, world) -> bool:
        """Create a checkpoint of current simulation state."""
        try:
            # Get vehicle state
            transform = vehicle.get_transform()
            velocity = vehicle.get_velocity()
            acceleration = vehicle.get_acceleration()
            
            # Get world state
            weather = world.get_weather()
            
            # Create checkpoint
            checkpoint = SimulationCheckpoint(
                simulation_id=simulation_id,
                timestamp=datetime.now(),
                vehicle_transform={
                    "location": {
                        "x": transform.location.x,
                        "y": transform.location.y,
                        "z": transform.location.z
                    },
                    "rotation": {
                        "pitch": transform.rotation.pitch,
                        "yaw": transform.rotation.yaw,
                        "roll": transform.rotation.roll
                    }
                },
                vehicle_physics={
                    "velocity": {
                        "x": velocity.x,
                        "y": velocity.y,
                        "z": velocity.z
                    },
                    "acceleration": {
                        "x": acceleration.x,
                        "y": acceleration.y,
                        "z": acceleration.z
                    }
                },
                world_state={
                    "map_name": world.get_map().name,
                    "actors_count": len(world.get_actors())
                },
                weather_conditions={
                    "cloudiness": weather.cloudiness,
                    "precipitation": weather.precipitation,
                    "sun_altitude_angle": weather.sun_altitude_angle,
                    "wind_intensity": weather.wind_intensity
                },
                traffic_state={
                    "vehicle_count": len(world.get_actors().filter('vehicle.*')),
                    "pedestrian_count": len(world.get_actors().filter('walker.*'))
                },
                sensor_configs={}  # Will be populated by sensor manager
            )
            
            # Store checkpoint
            self.checkpoints[simulation_id] = checkpoint
            
            # Save to disk
            self._save_checkpoint(checkpoint)
            
            # Backup to GCS if available
            if self.gcs_client:
                self._backup_checkpoint_to_gcs(checkpoint)
            
            logger.info(f"Created checkpoint for simulation {simulation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint for {simulation_id}: {e}")
            return False
    
    def restore_checkpoint(self, simulation_id: str, world, vehicle_bp) -> Optional[carla.Actor]:
        """Restore simulation from checkpoint."""
        if simulation_id not in self.checkpoints:
            logger.warning(f"No checkpoint found for simulation {simulation_id}")
            return None
        
        try:
            checkpoint = self.checkpoints[simulation_id]
            
            # Restore vehicle position
            location = carla.Location(
                x=checkpoint.vehicle_transform["location"]["x"],
                y=checkpoint.vehicle_transform["location"]["y"],
                z=checkpoint.vehicle_transform["location"]["z"]
            )
            rotation = carla.Rotation(
                pitch=checkpoint.vehicle_transform["rotation"]["pitch"],
                yaw=checkpoint.vehicle_transform["rotation"]["yaw"],
                roll=checkpoint.vehicle_transform["rotation"]["roll"]
            )
            transform = carla.Transform(location, rotation)
            
            # Spawn vehicle at checkpoint position
            vehicle = world.spawn_actor(vehicle_bp, transform)
            
            # Restore weather conditions
            weather = carla.WeatherParameters(
                cloudiness=checkpoint.weather_conditions["cloudiness"],
                precipitation=checkpoint.weather_conditions["precipitation"],
                sun_altitude_angle=checkpoint.weather_conditions["sun_altitude_angle"],
                wind_intensity=checkpoint.weather_conditions["wind_intensity"]
            )
            world.set_weather(weather)
            
            logger.info(f"Restored simulation {simulation_id} from checkpoint")
            return vehicle
            
        except Exception as e:
            logger.error(f"Failed to restore checkpoint for {simulation_id}: {e}")
            return None
    
    def record_error(self, simulation_id: str, error_type: str, error_message: str, 
                    stack_trace: str = "") -> None:
        """Record an error for tracking and analysis."""
        error_record = ErrorRecord(
            timestamp=datetime.now(),
            simulation_id=simulation_id,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            recovery_attempted=False,
            recovery_successful=False
        )
        
        self.error_history.append(error_record)
        
        # Save error to disk
        self._save_error_record(error_record)
        
        logger.error(f"Recorded error for {simulation_id}: {error_type} - {error_message}")
    
    def get_error_history(self, simulation_id: Optional[str] = None, 
                         hours: int = 24) -> List[ErrorRecord]:
        """Get error history for analysis."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_errors = [
            error for error in self.error_history
            if error.timestamp >= cutoff_time and 
            (simulation_id is None or error.simulation_id == simulation_id)
        ]
        
        return filtered_errors
    
    def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> None:
        """Clean up old checkpoints to save storage space."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        to_remove = [
            sim_id for sim_id, checkpoint in self.checkpoints.items()
            if checkpoint.timestamp < cutoff_time
        ]
        
        for sim_id in to_remove:
            del self.checkpoints[sim_id]
            # Remove from disk
            checkpoint_file = self.storage_path / f"checkpoint_{sim_id}.pkl"
            if checkpoint_file.exists():
                checkpoint_file.unlink()
        
        logger.info(f"Cleaned up {len(to_remove)} old checkpoints")
    
    def _save_checkpoint(self, checkpoint: SimulationCheckpoint) -> None:
        """Save checkpoint to disk."""
        try:
            checkpoint_file = self.storage_path / f"checkpoint_{checkpoint.simulation_id}.pkl"
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(checkpoint, f)
        except Exception as e:
            logger.error(f"Failed to save checkpoint to disk: {e}")
    
    def _backup_checkpoint_to_gcs(self, checkpoint: SimulationCheckpoint) -> None:
        """Backup checkpoint to Google Cloud Storage."""
        try:
            blob_name = f"checkpoints/{checkpoint.simulation_id}_{checkpoint.timestamp.isoformat()}.json"
            blob = self.bucket.blob(blob_name)
            
            # Convert checkpoint to JSON
            checkpoint_data = asdict(checkpoint)
            checkpoint_data['timestamp'] = checkpoint.timestamp.isoformat()
            
            blob.upload_from_string(
                json.dumps(checkpoint_data, indent=2),
                content_type='application/json'
            )
            
            logger.debug(f"Backed up checkpoint to GCS: {blob_name}")
            
        except Exception as e:
            logger.warning(f"Failed to backup checkpoint to GCS: {e}")
    
    def _save_error_record(self, error_record: ErrorRecord) -> None:
        """Save error record to disk."""
        try:
            error_file = self.storage_path / "errors.jsonl"
            
            error_data = asdict(error_record)
            error_data['timestamp'] = error_record.timestamp.isoformat()
            
            with open(error_file, 'a') as f:
                f.write(json.dumps(error_data) + '\n')
                
        except Exception as e:
            logger.error(f"Failed to save error record: {e}")
    
    def _load_state(self) -> None:
        """Load existing state from disk."""
        try:
            # Load checkpoints
            for checkpoint_file in self.storage_path.glob("checkpoint_*.pkl"):
                try:
                    with open(checkpoint_file, 'rb') as f:
                        checkpoint = pickle.load(f)
                        self.checkpoints[checkpoint.simulation_id] = checkpoint
                except Exception as e:
                    logger.warning(f"Failed to load checkpoint {checkpoint_file}: {e}")
            
            # Load error history
            error_file = self.storage_path / "errors.jsonl"
            if error_file.exists():
                with open(error_file, 'r') as f:
                    for line in f:
                        try:
                            error_data = json.loads(line.strip())
                            error_data['timestamp'] = datetime.fromisoformat(error_data['timestamp'])
                            error_record = ErrorRecord(**error_data)
                            self.error_history.append(error_record)
                        except Exception as e:
                            logger.warning(f"Failed to load error record: {e}")
            
            logger.info(f"Loaded {len(self.checkpoints)} checkpoints and {len(self.error_history)} error records")
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")


class HealthMonitor:
    """Monitors CARLA simulation health and performance."""
    
    def __init__(self):
        self.metrics = {
            "carla_connection": True,
            "memory_usage": 0.0,
            "cpu_usage": 0.0,
            "gpu_usage": 0.0,
            "active_simulations": 0,
            "error_rate": 0.0,
            "last_check": datetime.now()
        }
        
        self.thresholds = {
            "memory_usage_max": 80.0,  # %
            "cpu_usage_max": 90.0,     # %
            "gpu_usage_max": 95.0,     # %
            "error_rate_max": 0.1      # errors per minute
        }
    
    def check_carla_connection(self, client) -> bool:
        """Check if CARLA server is responsive."""
        try:
            client.get_server_version()
            self.metrics["carla_connection"] = True
            return True
        except Exception as e:
            logger.error(f"CARLA connection check failed: {e}")
            self.metrics["carla_connection"] = False
            return False
    
    def check_resource_usage(self) -> Dict[str, float]:
        """Check system resource usage."""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics["cpu_usage"] = cpu_percent
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics["memory_usage"] = memory.percent
            
            # GPU usage (if nvidia-ml-py is available)
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                self.metrics["gpu_usage"] = gpu_util.gpu
            except ImportError:
                logger.debug("pynvml not available, skipping GPU monitoring")
            except Exception as e:
                logger.warning(f"GPU monitoring failed: {e}")
            
            return {
                "cpu_usage": self.metrics["cpu_usage"],
                "memory_usage": self.metrics["memory_usage"],
                "gpu_usage": self.metrics["gpu_usage"]
            }
            
        except ImportError:
            logger.warning("psutil not available, skipping resource monitoring")
            return {}
        except Exception as e:
            logger.error(f"Resource monitoring failed: {e}")
            return {}
    
    def calculate_error_rate(self, error_history: List[ErrorRecord]) -> float:
        """Calculate error rate from recent history."""
        if not error_history:
            return 0.0
        
        # Count errors in last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_errors = [
            error for error in error_history
            if error.timestamp >= one_hour_ago
        ]
        
        # Errors per minute
        error_rate = len(recent_errors) / 60.0
        self.metrics["error_rate"] = error_rate
        
        return error_rate
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        self.metrics["last_check"] = datetime.now()
        
        # Determine overall health
        issues = []
        
        if not self.metrics["carla_connection"]:
            issues.append("CARLA server not responding")
        
        if self.metrics["memory_usage"] > self.thresholds["memory_usage_max"]:
            issues.append(f"High memory usage: {self.metrics['memory_usage']:.1f}%")
        
        if self.metrics["cpu_usage"] > self.thresholds["cpu_usage_max"]:
            issues.append(f"High CPU usage: {self.metrics['cpu_usage']:.1f}%")
        
        if self.metrics["gpu_usage"] > self.thresholds["gpu_usage_max"]:
            issues.append(f"High GPU usage: {self.metrics['gpu_usage']:.1f}%")
        
        if self.metrics["error_rate"] > self.thresholds["error_rate_max"]:
            issues.append(f"High error rate: {self.metrics['error_rate']:.2f} errors/min")
        
        status = "healthy" if not issues else "degraded" if len(issues) < 3 else "unhealthy"
        
        return {
            "status": status,
            "metrics": self.metrics.copy(),
            "issues": issues,
            "thresholds": self.thresholds.copy()
        }