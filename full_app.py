from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
import os
import json
import logging
from typing import List, Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cars with a Life - Autonomous Driving System",
    description="AI-powered autonomous driving experiment management and reporting system",
    version="1.0.0"
)

# In-memory storage (for demo purposes)
experiments = {}
reports = {}
experiment_counter = 0

# Pydantic models
class ExperimentRequest(BaseModel):
    name: str
    description: Optional[str] = "Autonomous driving experiment"
    parameters: Optional[Dict[str, Any]] = {}

class ExperimentResponse(BaseModel):
    experiment_id: str
    status: str
    message: str
    created_at: str
    metrics: Optional[Dict[str, Any]] = None

class ExperimentStatus(BaseModel):
    experiment_id: str
    name: str
    description: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int
    metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class ReportResponse(BaseModel):
    report_id: str
    experiment_id: str
    created_at: str
    status: str
    summary: Dict[str, Any]
    ai_insights: List[str]
    recommendations: List[str]

@app.get("/")
def root():
    return {
        "message": "Welcome to Cars with a Life - Autonomous Driving System",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "start_experiment": "/experiment/start",
            "experiment_status": "/experiment/{experiment_id}/status",
            "list_experiments": "/experiments",
            "list_reports": "/reports",
            "get_report": "/reports/{experiment_id}",
            "get_metrics": "/metrics/{experiment_id}",
            "get_notes": "/notes/{experiment_id}",
            "docs": "/docs"
        }
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "cars-with-a-life",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_id": os.getenv("PROJECT_ID", "vertex-test-1-467818"),
        "region": os.getenv("REGION", "us-central1"),
        "version": "1.0.0"
    }

@app.post("/experiment/start", response_model=ExperimentResponse)
def start_experiment(request: ExperimentRequest):
    """Start a new autonomous driving experiment"""
    global experiment_counter
    
    try:
        experiment_counter += 1
        experiment_id = f"exp-{experiment_counter:03d}"
        created_at = datetime.now(timezone.utc).isoformat()
        
        # Simulate experiment execution
        logger.info(f"Starting experiment {experiment_id}: {request.name}")
        
        # Simulate metrics based on parameters
        simulation_duration = request.parameters.get("simulation_duration", 300)
        weather_condition = request.parameters.get("weather", "clear")
        traffic_density = request.parameters.get("traffic_density", "medium")
        
        # Generate realistic metrics
        base_distance = simulation_duration * 0.5  # km per second
        weather_multiplier = {"clear": 1.0, "rainy": 0.8, "foggy": 0.6, "snowy": 0.4}.get(weather_condition, 1.0)
        traffic_multiplier = {"low": 1.2, "medium": 1.0, "high": 0.8}.get(traffic_density, 1.0)
        
        metrics = {
            "total_distance": round(base_distance * weather_multiplier * traffic_multiplier, 2),
            "average_speed": round(45.2 * weather_multiplier * traffic_multiplier, 1),
            "collisions": 0 if weather_condition == "clear" else 1,
            "traffic_violations": 0 if traffic_density == "low" else 1,
            "success_rate": round(98.5 * weather_multiplier, 1),
            "ai_confidence": round(0.87 * weather_multiplier, 2),
            "simulation_duration": simulation_duration,
            "weather_condition": weather_condition,
            "traffic_density": traffic_density
        }
        
        # Store experiment data
        experiment_data = {
            "experiment_id": experiment_id,
            "name": request.name,
            "description": request.description,
            "parameters": request.parameters,
            "status": "completed",
            "created_at": created_at,
            "started_at": created_at,
            "completed_at": created_at,
            "progress": 100,
            "metrics": metrics,
            "error_message": None
        }
        experiments[experiment_id] = experiment_data
        
        # Generate AI insights and recommendations
        ai_insights = [
            f"The autonomous vehicle demonstrated {'excellent' if weather_condition == 'clear' else 'good'} performance in {weather_condition} conditions.",
            f"AI model showed {'high' if metrics['ai_confidence'] > 0.8 else 'moderate'} confidence in decision-making ({metrics['ai_confidence']*100:.1f}%).",
            f"Traffic density was {traffic_density}, resulting in {'optimal' if traffic_density == 'low' else 'acceptable'} navigation performance.",
            f"Safety metrics: {metrics['collisions']} collisions, {metrics['traffic_violations']} traffic violations detected."
        ]
        
        recommendations = [
            f"Test in more challenging {weather_condition} conditions for robustness validation.",
            "Implement additional safety checks for edge cases in high-traffic scenarios." if traffic_density == "high" else "Consider testing in higher traffic density scenarios.",
            "Expand training data for diverse weather conditions." if weather_condition != "clear" else "Continue testing in various weather conditions.",
            "Fine-tune AI model parameters for improved confidence scores." if metrics['ai_confidence'] < 0.9 else "AI confidence is optimal, focus on edge case testing."
        ]
        
        # Create report
        report_data = {
            "report_id": f"report-{experiment_id}",
            "experiment_id": experiment_id,
            "created_at": created_at,
            "status": "completed",
            "summary": {
                "total_distance": metrics["total_distance"],
                "average_speed": metrics["average_speed"],
                "collisions": metrics["collisions"],
                "traffic_violations": metrics["traffic_violations"],
                "success_rate": metrics["success_rate"]
            },
            "ai_insights": ai_insights,
            "recommendations": recommendations
        }
        reports[experiment_id] = report_data
        
        logger.info(f"Experiment {experiment_id} completed successfully")
        
        return ExperimentResponse(
            experiment_id=experiment_id,
            status="completed",
            message="Experiment completed successfully",
            created_at=created_at,
            metrics=metrics
        )
        
    except Exception as e:
        logger.error(f"Error starting experiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/experiment/{experiment_id}/status", response_model=ExperimentStatus)
def get_experiment_status(experiment_id: str):
    """Get experiment status and progress"""
    if experiment_id not in experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    return ExperimentStatus(**experiments[experiment_id])

@app.get("/experiments")
def list_experiments(status: Optional[str] = None):
    """List experiments with optional filtering"""
    filtered_experiments = [
        exp for exp in experiments.values()
        if status is None or exp['status'] == status
    ]
    return {
        "count": len(filtered_experiments),
        "experiments": filtered_experiments
    }

@app.get("/reports")
def list_reports():
    """List all reports"""
    return {
        "count": len(reports),
        "reports": list(reports.values())
    }

@app.get("/reports/{experiment_id}", response_model=ReportResponse)
def get_report(experiment_id: str):
    """Get experiment report"""
    if experiment_id not in reports:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return ReportResponse(**reports[experiment_id])

@app.get("/metrics/{experiment_id}")
def get_metrics(experiment_id: str):
    """Get experiment metrics"""
    if experiment_id not in experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    return {
        "experiment_id": experiment_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": experiments[experiment_id]["metrics"]
    }

@app.get("/notes/{experiment_id}")
def get_notes(experiment_id: str):
    """Get AI-generated insights and recommendations"""
    if experiment_id not in reports:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {
        "experiment_id": experiment_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ai_insights": reports[experiment_id]["ai_insights"],
        "recommendations": reports[experiment_id]["recommendations"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)



