"""
Data models for evaluation metrics and reporting
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from .note_models import AutonomousNote, ValidationResult


class MetricType(str, Enum):
    LOCATION_ACCURACY = "location_accuracy"
    ACTION_ACCURACY = "action_accuracy"
    DESTINATION_ACCURACY = "destination_accuracy"
    VALIDATION_SUCCESS_RATE = "validation_success_rate"
    CONFIDENCE_SCORE = "confidence_score"
    OVERALL_SCORE = "overall_score"


class EvaluationMetric(BaseModel):
    """Individual evaluation metric"""
    metric_type: MetricType = Field(description="Type of metric")
    value: float = Field(description="Metric value")
    weight: float = Field(default=1.0, description="Metric weight in overall score")
    description: str = Field(description="Human-readable metric description")
    calculation_method: str = Field(description="Method used to calculate metric")


class ExperimentMetrics(BaseModel):
    """Complete metrics for an experiment"""
    experiment_id: str = Field(description="Experiment identifier")
    calculation_time: datetime = Field(default_factory=datetime.utcnow)
    total_notes: int = Field(description="Total number of notes generated")
    valid_notes: int = Field(description="Number of valid notes")
    
    # Individual metrics
    location_accuracy: float = Field(ge=0.0, le=1.0, description="Location accuracy score")
    action_accuracy: float = Field(ge=0.0, le=1.0, description="Action accuracy score")
    destination_accuracy: float = Field(ge=0.0, le=1.0, description="Destination accuracy score")
    validation_success_rate: float = Field(ge=0.0, le=1.0, description="Validation success rate")
    average_confidence: float = Field(ge=0.0, le=1.0, description="Average confidence score")
    overall_score: float = Field(ge=0.0, le=1.0, description="Overall performance score")
    
    # Detailed metrics
    metrics: List[EvaluationMetric] = Field(default_factory=list, description="Detailed metrics")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class GroundTruthData(BaseModel):
    """Ground truth data for comparison"""
    experiment_id: str = Field(description="Associated experiment ID")
    timestamp: datetime = Field(description="Ground truth timestamp")
    actual_location: str = Field(description="Actual vehicle location")
    actual_action: str = Field(description="Actual action taken")
    actual_destination: str = Field(description="Actual destination reached")
    map_verified: bool = Field(description="Whether data is map-verified")


class ComparisonResult(BaseModel):
    """Result of comparing note against ground truth"""
    note_id: str = Field(description="Note identifier")
    location_match: bool = Field(description="Location matches ground truth")
    action_match: bool = Field(description="Action matches ground truth")
    destination_match: bool = Field(description="Destination matches ground truth")
    location_similarity: float = Field(ge=0.0, le=1.0, description="Location similarity score")
    action_similarity: float = Field(ge=0.0, le=1.0, description="Action similarity score")
    destination_similarity: float = Field(ge=0.0, le=1.0, description="Destination similarity score")
    overall_accuracy: float = Field(ge=0.0, le=1.0, description="Overall accuracy score")


class EvaluationReport(BaseModel):
    """Complete evaluation report for an experiment"""
    experiment_id: str = Field(description="Experiment identifier")
    report_id: str = Field(description="Unique report identifier")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Summary statistics
    experiment_metrics: ExperimentMetrics = Field(description="Experiment-level metrics")
    note_comparisons: List[ComparisonResult] = Field(description="Individual note comparisons")
    
    # Performance breakdown
    performance_by_location: Dict[str, float] = Field(default_factory=dict)
    performance_by_action: Dict[str, float] = Field(default_factory=dict)
    performance_trends: Dict[str, List[float]] = Field(default_factory=dict)
    
    # Recommendations
    improvement_areas: List[str] = Field(default_factory=list)
    confidence_analysis: Dict[str, Any] = Field(default_factory=dict)
    
    # Storage references
    storage_path: Optional[str] = Field(default=None, description="Cloud Storage path")
    bigquery_table: Optional[str] = Field(default=None, description="BigQuery table reference")