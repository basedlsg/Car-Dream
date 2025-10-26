"""
Data schemas for DreamerV3 service
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class ActionType(str, Enum):
    """Driving action types"""
    ACCELERATE = "accelerate"
    BRAKE = "brake"
    MAINTAIN_SPEED = "maintain_speed"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    LANE_CHANGE_LEFT = "lane_change_left"
    LANE_CHANGE_RIGHT = "lane_change_right"
    STOP = "stop"


class VehicleInfo(BaseModel):
    """Information about nearby vehicles"""
    id: str = Field(description="Vehicle identifier")
    position: List[float] = Field(description="Vehicle position [x, y, z]")
    velocity: List[float] = Field(description="Vehicle velocity [x, y, z]")
    rotation: List[float] = Field(description="Vehicle rotation [roll, pitch, yaw]")
    distance: float = Field(description="Distance from ego vehicle")
    relative_velocity: List[float] = Field(description="Relative velocity")


class TrafficLight(BaseModel):
    """Traffic light information"""
    id: str = Field(description="Traffic light identifier")
    position: List[float] = Field(description="Traffic light position")
    state: str = Field(description="Traffic light state (red, yellow, green)")
    distance: float = Field(description="Distance from ego vehicle")


class Waypoint(BaseModel):
    """Road waypoint information"""
    position: List[float] = Field(description="Waypoint position [x, y, z]")
    rotation: List[float] = Field(description="Waypoint rotation [roll, pitch, yaw]")
    lane_id: int = Field(description="Lane identifier")
    road_id: int = Field(description="Road identifier")
    is_junction: bool = Field(default=False, description="Is waypoint in junction")


class SimulationState(BaseModel):
    """Complete simulation state from CARLA"""
    # Ego vehicle state
    vehicle_position: List[float] = Field(description="Ego vehicle position [x, y, z]")
    vehicle_velocity: List[float] = Field(description="Ego vehicle velocity [x, y, z]")
    vehicle_rotation: List[float] = Field(description="Ego vehicle rotation [roll, pitch, yaw]")
    
    # Sensor data
    camera_data: List[List[List[float]]] = Field(description="RGB camera image data")
    lidar_data: List[List[float]] = Field(description="LiDAR point cloud data")
    
    # Environment information
    nearby_vehicles: List[VehicleInfo] = Field(default_factory=list, description="Nearby vehicles")
    traffic_lights: List[TrafficLight] = Field(default_factory=list, description="Visible traffic lights")
    road_waypoints: List[Waypoint] = Field(default_factory=list, description="Road waypoints")
    
    # Metadata
    timestamp: str = Field(description="Simulation timestamp")
    weather: Optional[str] = Field(default=None, description="Weather conditions")
    time_of_day: Optional[str] = Field(default=None, description="Time of day")


class DrivingAction(BaseModel):
    """Driving action output from model"""
    action_type: ActionType = Field(description="Type of driving action")
    throttle: float = Field(ge=0.0, le=1.0, description="Throttle value [0-1]")
    brake: float = Field(ge=0.0, le=1.0, description="Brake value [0-1]")
    steering: float = Field(ge=-1.0, le=1.0, description="Steering value [-1 to 1]")
    gear: int = Field(default=1, description="Gear selection")
    hand_brake: bool = Field(default=False, description="Hand brake engaged")


class PredictionRequest(BaseModel):
    """Request for driving action prediction"""
    simulation_id: str = Field(description="Simulation identifier")
    simulation_state: SimulationState = Field(description="Current simulation state")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    model_version: Optional[str] = Field(default=None, description="Requested model version")


class PredictionResponse(BaseModel):
    """Response with driving action prediction"""
    action: DrivingAction = Field(description="Predicted driving action")
    confidence: float = Field(ge=0.0, le=1.0, description="Prediction confidence [0-1]")
    model_version: str = Field(description="Model version used")
    timestamp: str = Field(description="Prediction timestamp")
    processing_time_ms: float = Field(description="Processing time in milliseconds")
    
    # Optional additional information
    alternative_actions: Optional[List[DrivingAction]] = Field(default=None, description="Alternative actions")
    reasoning: Optional[str] = Field(default=None, description="Model reasoning")
    risk_assessment: Optional[Dict[str, float]] = Field(default=None, description="Risk scores")


class ModelStatus(BaseModel):
    """Model status information"""
    model_version: str = Field(description="Current model version")
    model_type: str = Field(description="Model type (DreamerV3, CarDreamer)")
    is_loaded: bool = Field(description="Is model loaded")
    is_ready: bool = Field(description="Is model ready for predictions")
    capabilities: List[str] = Field(description="Model capabilities")
    memory_usage: Dict[str, float] = Field(description="Memory usage statistics")
    last_prediction_time: Optional[str] = Field(description="Last prediction timestamp")


class HealthStatus(BaseModel):
    """Service health status"""
    status: str = Field(description="Health status (healthy, unhealthy)")
    model_loaded: bool = Field(description="Is model loaded")
    model_version: str = Field(description="Current model version")
    timestamp: str = Field(description="Health check timestamp")
    uptime_seconds: Optional[float] = Field(description="Service uptime in seconds")
    
    
class AIDecisionEvent(BaseModel):
    """AI decision event for Pub/Sub publishing"""
    simulation_id: str = Field(description="Simulation identifier")
    experiment_id: str = Field(description="Experiment identifier")
    timestamp: str = Field(description="Event timestamp")
    action: DrivingAction = Field(description="AI driving action")
    confidence: float = Field(description="Action confidence")
    model_version: str = Field(description="Model version")
    
    # Context information
    vehicle_position: List[float] = Field(description="Vehicle position when decision made")
    vehicle_velocity: List[float] = Field(description="Vehicle velocity")
    nearby_vehicles_count: int = Field(description="Number of nearby vehicles")
    traffic_light_state: Optional[str] = Field(description="Current traffic light state")
    
    # Performance metrics
    processing_time_ms: float = Field(description="Decision processing time")
    memory_usage_mb: Optional[float] = Field(description="Memory usage during decision")