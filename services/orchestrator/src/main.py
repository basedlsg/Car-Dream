"""
Orchestrator Service - Main FastAPI Application
Coordinates experiment execution across CARLA Runner and DreamerV3 Service
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config.settings import Settings
from services.experiment_manager import ExperimentManager
from services.pubsub_handler import PubSubHandler
from services.scheduler_handler import SchedulerHandler
from services.workflow_orchestrator import WorkflowOrchestrator
from services.service_client import ServiceClient
from services.database_manager import DatabaseManager
from models.api_models import (
    ExperimentRequest,
    ExperimentResponse,
    ExperimentStatusResponse,
    HealthResponse
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
experiment_manager: Optional[ExperimentManager] = None
pubsub_handler: Optional[PubSubHandler] = None
scheduler_handler: Optional[SchedulerHandler] = None
workflow_orchestrator: Optional[WorkflowOrchestrator] = None
service_client: Optional[ServiceClient] = None
db_manager: Optional[DatabaseManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    global experiment_manager, pubsub_handler, scheduler_handler, workflow_orchestrator, service_client, db_manager
    
    logger.info("Starting Orchestrator Service...")
    
    # Initialize settings
    settings = Settings()
    settings.validate_required_settings()
    
    # Initialize core services
    db_manager = DatabaseManager(settings.database_url)
    service_client = ServiceClient(settings)
    pubsub_handler = PubSubHandler(settings)
    scheduler_handler = SchedulerHandler(settings)
    
    # Initialize workflow orchestrator
    workflow_orchestrator = WorkflowOrchestrator(
        settings, service_client, pubsub_handler, db_manager
    )
    
    # Initialize experiment manager with workflow orchestrator
    experiment_manager = ExperimentManager(settings)
    experiment_manager.workflow_orchestrator = workflow_orchestrator
    
    # Initialize all services
    await db_manager.initialize()
    await service_client.initialize()
    await experiment_manager.initialize()
    
    # Start background services
    await pubsub_handler.start()
    await scheduler_handler.start()
    
    logger.info("Orchestrator Service started successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Orchestrator Service...")
    if pubsub_handler:
        await pubsub_handler.stop()
    if scheduler_handler:
        await scheduler_handler.stop()
    if service_client:
        await service_client.close()
    logger.info("Orchestrator Service stopped")


# Create FastAPI app
app = FastAPI(
    title="Orchestrator Service",
    description="Coordinates autonomous driving experiments across CARLA and DreamerV3",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        services={
            "experiment_manager": experiment_manager.is_healthy() if experiment_manager else False,
            "pubsub_handler": pubsub_handler.is_healthy() if pubsub_handler else False,
            "scheduler_handler": scheduler_handler.is_healthy() if scheduler_handler else False,
            "workflow_orchestrator": workflow_orchestrator.is_healthy() if workflow_orchestrator else False,
            "service_client": service_client.is_healthy() if service_client else False,
            "database_manager": db_manager.is_healthy() if db_manager else False
        }
    )


@app.post("/experiment/start", response_model=ExperimentResponse)
async def start_experiment(
    request: ExperimentRequest,
    background_tasks: BackgroundTasks
):
    """Start a new experiment"""
    if not experiment_manager:
        raise HTTPException(status_code=500, detail="Experiment manager not initialized")
    
    try:
        # Create experiment
        experiment = await experiment_manager.create_experiment(request.config)
        
        # Start experiment in background
        background_tasks.add_task(
            experiment_manager.execute_experiment,
            experiment.experiment_id
        )
        
        logger.info(f"Started experiment {experiment.experiment_id}")
        
        return ExperimentResponse(
            experiment_id=experiment.experiment_id,
            status=experiment.status,
            message="Experiment started successfully",
            created_at=experiment.created_at
        )
        
    except Exception as e:
        logger.error(f"Failed to start experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start experiment: {str(e)}")


@app.get("/experiment/{experiment_id}/status", response_model=ExperimentStatusResponse)
async def get_experiment_status(experiment_id: str):
    """Get experiment status and progress"""
    if not experiment_manager:
        raise HTTPException(status_code=500, detail="Experiment manager not initialized")
    
    try:
        result = await experiment_manager.get_experiment_status(experiment_id)
        if not result:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        return ExperimentStatusResponse(
            experiment_id=experiment_id,
            status=result.status,
            started_at=result.started_at,
            completed_at=result.completed_at,
            progress=await experiment_manager.get_experiment_progress(experiment_id),
            metrics=result.metrics,
            error_message=result.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get experiment status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get experiment status: {str(e)}")


@app.post("/experiment/{experiment_id}/stop")
async def stop_experiment(experiment_id: str):
    """Stop a running experiment"""
    if not experiment_manager:
        raise HTTPException(status_code=500, detail="Experiment manager not initialized")
    
    try:
        success = await experiment_manager.stop_experiment(experiment_id)
        if not success:
            raise HTTPException(status_code=404, detail="Experiment not found or already stopped")
        
        logger.info(f"Stopped experiment {experiment_id}")
        
        return {"message": "Experiment stopped successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop experiment: {str(e)}")


@app.get("/experiments", response_model=List[ExperimentStatusResponse])
async def list_experiments(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List experiments with optional filtering"""
    if not experiment_manager:
        raise HTTPException(status_code=500, detail="Experiment manager not initialized")
    
    try:
        experiments = await experiment_manager.list_experiments(
            status=status,
            limit=limit,
            offset=offset
        )
        
        return [
            ExperimentStatusResponse(
                experiment_id=exp.experiment_id,
                status=exp.status,
                started_at=exp.started_at,
                completed_at=exp.completed_at,
                progress=await experiment_manager.get_experiment_progress(exp.experiment_id),
                metrics=exp.metrics,
                error_message=exp.error_message
            )
            for exp in experiments
        ]
        
    except Exception as e:
        logger.error(f"Failed to list experiments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list experiments: {str(e)}")


@app.post("/scheduler/trigger")
async def trigger_daily_experiment(background_tasks: BackgroundTasks):
    """Endpoint for Cloud Scheduler to trigger daily experiments"""
    if not scheduler_handler:
        raise HTTPException(status_code=500, detail="Scheduler handler not initialized")
    
    try:
        # Create daily experiment configuration
        experiment_config = await scheduler_handler.create_daily_experiment_config()
        
        # Start experiment
        experiment = await experiment_manager.create_experiment(experiment_config)
        background_tasks.add_task(
            experiment_manager.execute_experiment,
            experiment.experiment_id
        )
        
        logger.info(f"Triggered daily experiment {experiment.experiment_id}")
        
        return {
            "message": "Daily experiment triggered successfully",
            "experiment_id": experiment.experiment_id
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger daily experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger daily experiment: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        reload=False
    )