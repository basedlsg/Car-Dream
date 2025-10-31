#!/usr/bin/env python3
"""
Orchestrator Service for Cars with a Life
Simplified version for deployment
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from flask import Flask, request, jsonify
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
PROJECT_ID = os.environ.get('PROJECT_ID', 'vertex-test-1-467818')
REGION = os.environ.get('REGION', 'us-central1')
REPORTER_URL = os.environ.get('REPORTER_URL', 'https://reporter-964505076225.us-central1.run.app')

# In-memory storage for demo purposes
experiments = {}
experiment_counter = 0

class ExperimentManager:
    def __init__(self):
        self.experiments = {}
        self.counter = 0
    
    def create_experiment(self, config: dict) -> dict:
        self.counter += 1
        experiment_id = f"exp-{self.counter:03d}"
        
        experiment = {
            "experiment_id": experiment_id,
            "name": config.get("name", f"Experiment {self.counter}"),
            "description": config.get("description", ""),
            "parameters": config.get("parameters", {}),
            "status": "created",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "progress": 0,
            "metrics": {},
            "error_message": None
        }
        
        self.experiments[experiment_id] = experiment
        return experiment
    
    def get_experiment(self, experiment_id: str) -> Optional[dict]:
        return self.experiments.get(experiment_id)
    
    def list_experiments(self, status: Optional[str] = None, limit: int = 50) -> List[dict]:
        experiments = list(self.experiments.values())
        
        if status:
            experiments = [exp for exp in experiments if exp["status"] == status]
        
        return experiments[:limit]
    
    def start_experiment(self, experiment_id: str) -> bool:
        if experiment_id not in self.experiments:
            return False
        
        experiment = self.experiments[experiment_id]
        experiment["status"] = "running"
        experiment["started_at"] = datetime.utcnow().isoformat()
        experiment["updated_at"] = datetime.utcnow().isoformat()
        
        # Simulate experiment progress
        self._simulate_experiment_progress(experiment_id)
        
        return True
    
    def stop_experiment(self, experiment_id: str) -> bool:
        if experiment_id not in self.experiments:
            return False
        
        experiment = self.experiments[experiment_id]
        experiment["status"] = "completed"
        experiment["completed_at"] = datetime.utcnow().isoformat()
        experiment["updated_at"] = datetime.utcnow().isoformat()
        experiment["progress"] = 100
        
        # Generate sample metrics
        experiment["metrics"] = {
            "total_distance": 1500.5,
            "average_speed": 45.2,
            "collisions": 0,
            "traffic_violations": 0,
            "success_rate": 98.5,
            "ai_confidence": 0.87
        }
        
        return True
    
    def _simulate_experiment_progress(self, experiment_id: str):
        """Simulate experiment progress"""
        def update_progress():
            experiment = self.experiments.get(experiment_id)
            if experiment and experiment["status"] == "running":
                experiment["progress"] = min(experiment["progress"] + 10, 90)
                experiment["updated_at"] = datetime.utcnow().isoformat()
                
                if experiment["progress"] < 90:
                    # Schedule next update
                    asyncio.create_task(asyncio.sleep(2))
                    update_progress()
        
        # Start progress simulation
        asyncio.create_task(asyncio.sleep(1))
        update_progress()

# Initialize experiment manager
exp_manager = ExperimentManager()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "project_id": PROJECT_ID,
        "region": REGION
    })

@app.route('/experiment/start', methods=['POST'])
def start_experiment():
    """Start a new experiment"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Create experiment
        experiment = exp_manager.create_experiment(data)
        
        # Start experiment
        success = exp_manager.start_experiment(experiment["experiment_id"])
        
        if success:
            logger.info(f"Started experiment: {experiment['experiment_id']}")
            return jsonify({
                "experiment_id": experiment["experiment_id"],
                "status": experiment["status"],
                "message": "Experiment started successfully",
                "created_at": experiment["created_at"]
            }), 201
        else:
            return jsonify({"error": "Failed to start experiment"}), 500
            
    except Exception as e:
        logger.error(f"Error starting experiment: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/experiment/<experiment_id>/status', methods=['GET'])
def get_experiment_status(experiment_id: str):
    """Get experiment status"""
    experiment = exp_manager.get_experiment(experiment_id)
    
    if not experiment:
        return jsonify({"error": "Experiment not found"}), 404
    
    return jsonify({
        "experiment_id": experiment_id,
        "status": experiment["status"],
        "started_at": experiment.get("started_at"),
        "completed_at": experiment.get("completed_at"),
        "progress": experiment["progress"],
        "metrics": experiment["metrics"],
        "error_message": experiment["error_message"]
    })

@app.route('/experiment/<experiment_id>/stop', methods=['POST'])
def stop_experiment(experiment_id: str):
    """Stop an experiment"""
    success = exp_manager.stop_experiment(experiment_id)
    
    if success:
        logger.info(f"Stopped experiment: {experiment_id}")
        return jsonify({"message": "Experiment stopped successfully"})
    else:
        return jsonify({"error": "Experiment not found or already stopped"}), 404

@app.route('/experiments', methods=['GET'])
def list_experiments():
    """List experiments"""
    status = request.args.get('status')
    limit = int(request.args.get('limit', 50))
    
    experiments = exp_manager.list_experiments(status=status, limit=limit)
    
    return jsonify({
        "experiments": experiments,
        "count": len(experiments)
    })

@app.route('/scheduler/trigger', methods=['POST'])
def trigger_daily_experiment():
    """Trigger daily experiment (for Cloud Scheduler)"""
    try:
        # Create daily experiment configuration
        daily_config = {
            "name": f"Daily Experiment - {datetime.utcnow().strftime('%Y-%m-%d')}",
            "description": "Automated daily experiment",
            "parameters": {
                "simulation_duration": 300,
                "weather_conditions": "clear",
                "traffic_density": "medium",
                "scenario": "city_driving"
            }
        }
        
        # Create and start experiment
        experiment = exp_manager.create_experiment(daily_config)
        success = exp_manager.start_experiment(experiment["experiment_id"])
        
        if success:
            logger.info(f"Triggered daily experiment: {experiment['experiment_id']}")
            return jsonify({
                "message": "Daily experiment triggered successfully",
                "experiment_id": experiment["experiment_id"]
            })
        else:
            return jsonify({"error": "Failed to trigger daily experiment"}), 500
            
    except Exception as e:
        logger.error(f"Error triggering daily experiment: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        "service": "Cars with a Life - Orchestrator",
        "version": "1.0.0",
        "project_id": PROJECT_ID,
        "region": REGION,
        "endpoints": {
            "health": "/health",
            "start_experiment": "POST /experiment/start",
            "get_status": "GET /experiment/{id}/status",
            "stop_experiment": "POST /experiment/{id}/stop",
            "list_experiments": "GET /experiments",
            "trigger_daily": "POST /scheduler/trigger"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)


