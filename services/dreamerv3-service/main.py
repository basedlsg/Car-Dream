"""
DreamerV3/CarDreamer model service for autonomous driving decisions
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from model_wrapper import DreamerModelWrapper
from schemas import SimulationState, DrivingAction, PredictionRequest, PredictionResponse
from utils import setup_logging, health_check_model
from decision_engine import DecisionEngine, DecisionContext
from pubsub_client import pubsub_client
from health_check import health_checker

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global instances
model_wrapper: Optional[DreamerModelWrapper] = None
decision_engine: Optional[DecisionEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for model loading/cleanup"""
    global model_wrapper, decision_engine
    
    try:
        logger.info("Initializing DreamerV3 model service...")
        
        # Initialize model wrapper
        model_wrapper = DreamerModelWrapper()
        await model_wrapper.initialize()
        
        # Initialize decision engine
        decision_engine = DecisionEngine()
        
        logger.info("Model service initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize model service: {e}")
        raise
    finally:
        if model_wrapper:
            await model_wrapper.cleanup()
        
        if pubsub_client:
            pubsub_client.close()
            
        logger.info("Model service cleanup completed")


# FastAPI application
app = FastAPI(
    title="DreamerV3 Service",
    description="AI world model service for autonomous driving decisions",
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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return health_checker.get_basic_health(model_wrapper)


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check endpoint"""
    return health_checker.get_detailed_health(model_wrapper)


@app.get("/readiness")
async def readiness_probe():
    """Kubernetes readiness probe"""
    return health_checker.get_readiness_probe(model_wrapper)


@app.get("/liveness")
async def liveness_probe():
    """Kubernetes liveness probe"""
    return health_checker.get_liveness_probe()


@app.get("/model/status")
async def get_model_status():
    """Get detailed model status information"""
    if not model_wrapper:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    return {
        "model_version": model_wrapper.get_version(),
        "model_type": model_wrapper.get_model_type(),
        "is_loaded": model_wrapper.is_loaded(),
        "is_ready": model_wrapper.is_ready(),
        "capabilities": model_wrapper.get_capabilities(),
        "memory_usage": model_wrapper.get_memory_usage(),
        "last_prediction_time": model_wrapper.get_last_prediction_time()
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict_action(request: PredictionRequest, background_tasks: BackgroundTasks):
    """
    Generate driving actions based on simulation state
    
    Args:
        request: Prediction request containing simulation state and context
        background_tasks: FastAPI background tasks for async operations
    
    Returns:
        PredictionResponse with driving actions and confidence scores
    """
    if not model_wrapper or not model_wrapper.is_ready():
        raise HTTPException(status_code=503, detail="Model not ready")
    
    if not decision_engine:
        raise HTTPException(status_code=503, detail="Decision engine not ready")
    
    start_time = datetime.utcnow()
    is_error = False
    
    try:
        logger.info(f"Processing prediction request for simulation {request.simulation_id}")
        
        # Process simulation state with decision engine
        processed_state, risk_score = decision_engine.process_simulation_state(
            request.simulation_state,
            context=request.context
        )
        
        # Generate raw prediction using model wrapper
        raw_prediction = await model_wrapper.predict(
            simulation_state=request.simulation_state,
            context=request.context
        )
        
        # Enhance prediction with decision logic
        enhanced_prediction = decision_engine.enhance_prediction(
            raw_prediction,
            processed_state,
            context=request.context
        )
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        enhanced_prediction.processing_time_ms = processing_time
        
        # Background tasks for logging and publishing
        background_tasks.add_task(
            log_and_publish_prediction,
            request.simulation_id,
            request.context.get("experiment_id", "unknown") if request.context else "unknown",
            enhanced_prediction,
            request.simulation_state,
            processing_time
        )
        
        # Record metrics
        health_checker.record_request(processing_time, is_error=False)
        
        return enhanced_prediction
        
    except Exception as e:
        is_error = True
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        health_checker.record_request(processing_time, is_error=True)
        
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.post("/model/update")
async def update_model(model_path: str):
    """
    Update the model with a new version
    
    Args:
        model_path: Path to the new model file
    
    Returns:
        Update status information
    """
    if not model_wrapper:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    try:
        logger.info(f"Updating model from path: {model_path}")
        
        success = await model_wrapper.update_model(model_path)
        
        if success:
            return {
                "status": "success",
                "message": "Model updated successfully",
                "new_version": model_wrapper.get_version(),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail="Model update failed")
            
    except Exception as e:
        logger.error(f"Model update failed: {e}")
        raise HTTPException(status_code=500, detail=f"Model update failed: {str(e)}")


@app.post("/predict/batch")
async def predict_batch_actions(
    requests: List[PredictionRequest], 
    background_tasks: BackgroundTasks
):
    """
    Generate driving actions for multiple simulation states
    
    Args:
        requests: List of prediction requests
        background_tasks: FastAPI background tasks
    
    Returns:
        List of prediction responses
    """
    if not model_wrapper or not model_wrapper.is_ready():
        raise HTTPException(status_code=503, detail="Model not ready")
    
    if not decision_engine:
        raise HTTPException(status_code=503, detail="Decision engine not ready")
    
    if len(requests) > 50:  # Limit batch size
        raise HTTPException(status_code=400, detail="Batch size too large (max 50)")
    
    try:
        logger.info(f"Processing batch prediction request with {len(requests)} items")
        
        predictions = []
        
        for request in requests:
            # Process each request individually
            start_time = datetime.utcnow()
            
            # Process simulation state
            processed_state, risk_score = decision_engine.process_simulation_state(
                request.simulation_state,
                context=request.context
            )
            
            # Generate prediction
            raw_prediction = await model_wrapper.predict(
                simulation_state=request.simulation_state,
                context=request.context
            )
            
            # Enhance prediction
            enhanced_prediction = decision_engine.enhance_prediction(
                raw_prediction,
                processed_state,
                context=request.context
            )
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            enhanced_prediction.processing_time_ms = processing_time
            
            predictions.append(enhanced_prediction)
            
            # Background logging for each prediction
            background_tasks.add_task(
                log_and_publish_prediction,
                request.simulation_id,
                request.context.get("experiment_id", "unknown") if request.context else "unknown",
                enhanced_prediction,
                request.simulation_state,
                processing_time
            )
        
        return {"predictions": predictions, "batch_size": len(predictions)}
        
    except Exception as e:
        logger.error(f"Batch prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")


@app.post("/experiment/start")
async def start_experiment(experiment_data: Dict[str, Any]):
    """
    Signal the start of a new experiment
    
    Args:
        experiment_data: Experiment configuration and metadata
    
    Returns:
        Experiment start confirmation
    """
    try:
        experiment_id = experiment_data.get("experiment_id", "unknown")
        
        logger.info(f"Starting experiment: {experiment_id}")
        
        # Publish experiment start event
        await pubsub_client.publish_experiment_event(
            experiment_id=experiment_id,
            event_type="experiment_started",
            event_data=experiment_data,
            metadata={
                "service": "dreamerv3-service",
                "model_version": model_wrapper.get_version() if model_wrapper else "unknown"
            }
        )
        
        return {
            "status": "started",
            "experiment_id": experiment_id,
            "timestamp": datetime.utcnow().isoformat(),
            "model_version": model_wrapper.get_version() if model_wrapper else "unknown"
        }
        
    except Exception as e:
        logger.error(f"Failed to start experiment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start experiment: {str(e)}")


@app.post("/experiment/complete")
async def complete_experiment(completion_data: Dict[str, Any]):
    """
    Signal the completion of an experiment
    
    Args:
        completion_data: Experiment completion data and results
    
    Returns:
        Experiment completion confirmation
    """
    try:
        experiment_id = completion_data.get("experiment_id", "unknown")
        
        logger.info(f"Completing experiment: {experiment_id}")
        
        # Publish experiment completion event
        await pubsub_client.publish_experiment_event(
            experiment_id=experiment_id,
            event_type="experiment_completed",
            event_data=completion_data,
            metadata={
                "service": "dreamerv3-service",
                "model_version": model_wrapper.get_version() if model_wrapper else "unknown"
            }
        )
        
        return {
            "status": "completed",
            "experiment_id": experiment_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to complete experiment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete experiment: {str(e)}")


async def log_and_publish_prediction(
    simulation_id: str, 
    experiment_id: str,
    prediction: PredictionResponse,
    simulation_state: SimulationState,
    processing_time_ms: float
):
    """Background task to log and publish prediction for monitoring"""
    try:
        # Log prediction locally
        logger.info(f"Prediction for simulation {simulation_id}: "
                   f"action={prediction.action.action_type}, "
                   f"confidence={prediction.confidence:.3f}, "
                   f"processing_time={processing_time_ms:.1f}ms")
        
        # Publish to Pub/Sub
        await pubsub_client.publish_ai_decision(
            simulation_id=simulation_id,
            experiment_id=experiment_id,
            prediction=prediction,
            simulation_state=simulation_state,
            processing_time_ms=processing_time_ms
        )
        
        # Publish model metrics periodically
        if hasattr(log_and_publish_prediction, 'call_count'):
            log_and_publish_prediction.call_count += 1
        else:
            log_and_publish_prediction.call_count = 1
        
        # Publish metrics every 100 predictions
        if log_and_publish_prediction.call_count % 100 == 0:
            await publish_model_metrics()
            
    except Exception as e:
        logger.error(f"Failed to log and publish prediction: {e}")


async def publish_model_metrics():
    """Publish model performance metrics"""
    try:
        if not model_wrapper:
            return
        
        metrics = {
            "predictions_count": getattr(log_and_publish_prediction, 'call_count', 0),
            "avg_processing_time_ms": health_checker._calculate_avg_response_time(),
            "error_rate_percent": health_checker._calculate_error_rate(),
            "memory_usage_mb": health_checker._get_memory_usage() or 0.0,
            "uptime_seconds": health_checker._get_service_metrics().uptime_seconds
        }
        
        # Add model-specific metrics
        if model_wrapper.is_loaded():
            model_memory = model_wrapper.get_memory_usage()
            if isinstance(model_memory, dict):
                metrics.update(model_memory)
        
        await pubsub_client.publish_model_metrics(
            model_version=model_wrapper.get_version(),
            metrics=metrics
        )
        
    except Exception as e:
        logger.error(f"Failed to publish model metrics: {e}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )