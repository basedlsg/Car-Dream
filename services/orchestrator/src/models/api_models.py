"""
API models for the Orchestrator Service
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

# Import shared schemas
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../shared'))
from schemas.experiment import ExperimentConfig, ExperimentStatus


class ExperimentRequest(BaseModel):
    """Request to start a new experiment"""
    config: ExperimentConfig = Field(description="Experiment configuration")
    priority: int = Field(default=1, description="Experiment priority (1-10)")
    tags: List[str] = Field(default_factory=list, description="Experiment tags")


class ExperimentResponse(BaseModel):
    """Response after creating an experiment"""
    experiment_id: str = Field(description="Unique experiment identifier")
    status: ExperimentStatus = Field(description="Current experiment status")
    message: str = Field(description="Response message")
    created_at: datetime = Field(description="Experiment creation timestamp")


class ExperimentStatusResponse(BaseModel):
    """Detailed experiment status response"""
    experiment_id: str = Field(description="Experiment identifier")
    status: ExperimentStatus = Field(description="Current status")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    progress: float = Field(default=0.0, description="Progress percentage (0-100)")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Current metrics")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    current_phase: Optional[str] = Field(default=None, description="Current execution phase")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(description="Overall service status")
    timestamp: datetime = Field(description="Health check timestamp")
    version: str = Field(description="Service version")
    services: Dict[str, bool] = Field(description="Status of dependent services")


class ComponentStatus(str, Enum):
    """Component status enumeration"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServiceHealth(BaseModel):
    """Individual service health status"""
    name: str = Field(description="Service name")
    status: ComponentStatus = Field(description="Service status")
    last_check: datetime = Field(description="Last health check timestamp")
    response_time_ms: Optional[float] = Field(default=None, description="Response time in milliseconds")
    error_message: Optional[str] = Field(default=None, description="Error message if unhealthy")


class ExperimentProgress(BaseModel):
    """Detailed experiment progress information"""
    experiment_id: str = Field(description="Experiment identifier")
    phase: str = Field(description="Current execution phase")
    progress_percentage: float = Field(description="Overall progress (0-100)")
    phase_progress: float = Field(description="Current phase progress (0-100)")
    estimated_completion: Optional[datetime] = Field(default=None, description="Estimated completion time")
    phases_completed: List[str] = Field(default_factory=list, description="Completed phases")
    current_step: Optional[str] = Field(default=None, description="Current step description")


class ExperimentMetrics(BaseModel):
    """Real-time experiment metrics"""
    experiment_id: str = Field(description="Experiment identifier")
    timestamp: datetime = Field(description="Metrics timestamp")
    simulation_fps: Optional[float] = Field(default=None, description="Simulation FPS")
    ai_inference_time: Optional[float] = Field(default=None, description="AI inference time (ms)")
    memory_usage_mb: Optional[float] = Field(default=None, description="Memory usage in MB")
    cpu_usage_percent: Optional[float] = Field(default=None, description="CPU usage percentage")
    gpu_usage_percent: Optional[float] = Field(default=None, description="GPU usage percentage")
    custom_metrics: Dict[str, float] = Field(default_factory=dict, description="Custom metrics")


class SchedulerTriggerRequest(BaseModel):
    """Request from Cloud Scheduler to trigger experiments"""
    trigger_type: str = Field(description="Type of trigger (daily, weekly, etc.)")
    experiment_template: Optional[str] = Field(default=None, description="Experiment template to use")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters")


class ExperimentListRequest(BaseModel):
    """Request parameters for listing experiments"""
    status: Optional[ExperimentStatus] = Field(default=None, description="Filter by status")
    start_date: Optional[datetime] = Field(default=None, description="Filter experiments after this date")
    end_date: Optional[datetime] = Field(default=None, description="Filter experiments before this date")
    tags: List[str] = Field(default_factory=list, description="Filter by tags")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(default=0, ge=0, description="Number of results to skip")


class ExperimentStopRequest(BaseModel):
    """Request to stop an experiment"""
    reason: Optional[str] = Field(default=None, description="Reason for stopping")
    force: bool = Field(default=False, description="Force stop without cleanup")


class PubSubMessage(BaseModel):
    """Pub/Sub message structure"""
    message_id: str = Field(description="Message ID")
    publish_time: datetime = Field(description="Message publish time")
    data: Dict[str, Any] = Field(description="Message data")
    attributes: Dict[str, str] = Field(default_factory=dict, description="Message attributes")


class ComponentCommunicationRequest(BaseModel):
    """Request for inter-component communication"""
    target_service: str = Field(description="Target service name")
    action: str = Field(description="Action to perform")
    payload: Dict[str, Any] = Field(description="Request payload")
    timeout_seconds: int = Field(default=30, description="Request timeout")


class ComponentCommunicationResponse(BaseModel):
    """Response from inter-component communication"""
    success: bool = Field(description="Whether the request was successful")
    response_data: Dict[str, Any] = Field(default_factory=dict, description="Response data")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    response_time_ms: float = Field(description="Response time in milliseconds")