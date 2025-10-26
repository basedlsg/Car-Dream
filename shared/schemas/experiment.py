"""
Shared data schemas for experiment configuration and results
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CarlaConfig(BaseModel):
    """CARLA simulation configuration"""
    town: str = Field(default="Town01", description="CARLA town to use")
    weather: str = Field(default="ClearNoon", description="Weather preset")
    num_vehicles: int = Field(default=50, description="Number of NPC vehicles")
    num_pedestrians: int = Field(default=100, description="Number of pedestrians")
    simulation_time: int = Field(default=300, description="Simulation time in seconds")


class DreamerConfig(BaseModel):
    """DreamerV3 model configuration"""
    model_path: str = Field(description="Path to trained model")
    batch_size: int = Field(default=16, description="Inference batch size")
    sequence_length: int = Field(default=64, description="Sequence length")
    use_gpu: bool = Field(default=True, description="Use GPU acceleration")


class ExperimentConfig(BaseModel):
    """Complete experiment configuration"""
    experiment_id: str = Field(description="Unique experiment identifier")
    name: str = Field(description="Human-readable experiment name")
    description: Optional[str] = Field(default=None, description="Experiment description")
    carla_config: CarlaConfig = Field(description="CARLA simulation settings")
    dreamer_config: DreamerConfig = Field(description="DreamerV3 model settings")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperimentResult(BaseModel):
    """Experiment execution results"""
    experiment_id: str = Field(description="Experiment identifier")
    status: ExperimentStatus = Field(description="Execution status")
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    metrics: Dict[str, float] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list, description="Paths to result artifacts")
    error_message: Optional[str] = Field(default=None)
    logs: List[
str] = Field(default_factory=list, description="Execution logs")