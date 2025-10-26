"""
Data models for autonomous note generation and validation
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"
    PARTIAL = "partial"


class Coordinates(BaseModel):
    """Geographic coordinates"""
    latitude: float = Field(description="Latitude coordinate")
    longitude: float = Field(description="Longitude coordinate")
    altitude: Optional[float] = Field(default=0.0, description="Altitude in meters")


class Vector3D(BaseModel):
    """3D vector for velocity, acceleration, etc."""
    x: float = Field(description="X component")
    y: float = Field(description="Y component")
    z: float = Field(description="Z component")


class MapReference(BaseModel):
    """Reference to map data for validation"""
    map_name: str = Field(description="Name of the map (CARLA or nuScenes)")
    poi_id: Optional[str] = Field(default=None, description="Point of Interest identifier")
    road_id: Optional[str] = Field(default=None, description="Road identifier")
    lane_id: Optional[str] = Field(default=None, description="Lane identifier")


class SimulationData(BaseModel):
    """Simulation state data from CARLA"""
    timestamp: datetime = Field(description="Simulation timestamp")
    vehicle_position: Coordinates = Field(description="Vehicle position")
    vehicle_velocity: Vector3D = Field(description="Vehicle velocity")
    current_location: str = Field(description="Current location description")
    nearby_pois: List[str] = Field(description="Nearby points of interest")
    map_reference: MapReference = Field(description="Map reference data")


class AIDecision(BaseModel):
    """AI decision data from DreamerV3"""
    action_type: str = Field(description="Type of action taken")
    action_description: str = Field(description="Human-readable action description")
    target_destination: str = Field(description="Intended destination")
    confidence: float = Field(ge=0.0, le=1.0, description="Decision confidence score")
    reasoning: Optional[str] = Field(default=None, description="AI reasoning for decision")


class AutonomousNote(BaseModel):
    """Generated autonomous driving note"""
    note_id: str = Field(description="Unique note identifier")
    experiment_id: str = Field(description="Associated experiment ID")
    timestamp: datetime = Field(description="Note generation timestamp")
    location: str = Field(description="Location where action occurred")
    action: str = Field(description="Action taken by the vehicle")
    destination: str = Field(description="Target destination")
    confidence: float = Field(ge=0.0, le=1.0, description="Note confidence score")
    validation_status: ValidationStatus = Field(description="Validation result")
    map_reference: MapReference = Field(description="Map validation reference")
    raw_note: str = Field(description="Generated note in required format")


class ValidationResult(BaseModel):
    """Note validation results"""
    is_valid: bool = Field(description="Overall validation status")
    location_valid: bool = Field(description="Location accuracy validation")
    action_valid: bool = Field(description="Action validity validation")
    destination_valid: bool = Field(description="Destination accuracy validation")
    carla_map_match: bool = Field(description="CARLA map data match")
    nuscenes_match: bool = Field(description="nuScenes data match")
    validation_errors: List[str] = Field(default_factory=list, description="Validation error messages")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Overall validation confidence")