"""
API routes for the Reporter Service
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
from datetime import date
import logging

from ..models.note_models import SimulationData, AIDecision, AutonomousNote
from ..models.evaluation_models import ExperimentMetrics, EvaluationReport, GroundTruthData
from ..services.reporter_service import ReporterService
from ...config.settings import settings

# Initialize router and service
router = APIRouter()
reporter_service = ReporterService(
    project_id=settings.PROJECT_ID,
    dataset_id=settings.DATASET_ID,
    bucket_name=settings.BUCKET_NAME
)
logger = logging.getLogger(__name__)


@router.post("/notes/generate", response_model=Dict[str, Any])
async def generate_note(
    simulation_data: SimulationData,
    ai_decision: AIDecision,
    experiment_id: str,
    validate: bool = True
):
    """Generate an autonomous note from simulation data and AI decision"""
    try:
        result = await reporter_service.generate_single_note(
            simulation_data, ai_decision, experiment_id, validate
        )
        return result
    except Exception as e:
        logger.error(f"Error generating note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments/{experiment_id}/process", response_model=EvaluationReport)
async def process_experiment(
    experiment_id: str,
    simulation_sequence: List[SimulationData],
    decision_sequence: List[AIDecision],
    ground_truth: Optional[List[GroundTruthData]] = None,
    background_tasks: BackgroundTasks = None
):
    """Process complete experiment data and generate evaluation report"""
    try:
        if len(simulation_sequence) != len(decision_sequence):
            raise HTTPException(
                status_code=400, 
                detail="Simulation and decision sequences must have same length"
            )
        
        report = await reporter_service.process_experiment_data(
            experiment_id, simulation_sequence, decision_sequence, ground_truth
        )
        return report
    except Exception as e:
        logger.error(f"Error processing experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments/{experiment_id}/metrics", response_model=ExperimentMetrics)
async def calculate_metrics(
    experiment_id: str,
    notes: List[AutonomousNote],
    validation_results: List[Dict[str, Any]]
):
    """Calculate performance metrics for an experiment"""
    try:
        # Convert validation results from dict to ValidationResult objects
        from ..models.note_models import ValidationResult
        validation_objs = [ValidationResult(**vr) for vr in validation_results]
        
        metrics = await reporter_service.calculate_experiment_performance(
            experiment_id, notes, validation_objs
        )
        return metrics
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/daily", response_model=Dict[str, str])
async def generate_daily_report(
    experiment_ids: List[str],
    report_date: date
):
    """Generate daily summary report for multiple experiments"""
    try:
        storage_path = await reporter_service.generate_daily_summary(
            experiment_ids, report_date
        )
        return {"storage_path": storage_path}
    except Exception as e:
        logger.error(f"Error generating daily report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments/{experiment_id}/summary", response_model=Dict[str, Any])
async def get_experiment_summary(experiment_id: str):
    """Get summary statistics for an experiment"""
    try:
        summary = reporter_service.get_experiment_summary(experiment_id)
        return summary
    except Exception as e:
        logger.error(f"Error getting experiment summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notes/validate-format", response_model=Dict[str, bool])
async def validate_note_format(note_text: str):
    """Validate that a note follows the required format"""
    try:
        is_valid = reporter_service.validate_note_format(note_text)
        return {"is_valid": is_valid}
    except Exception as e:
        logger.error(f"Error validating note format: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION
    }