#!/usr/bin/env python3
"""
Simple Orchestrator Service for Cars with a Life
A lightweight version that can be deployed quickly
"""

import os
import json
import logging
from flask import Flask, request, jsonify
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# In-memory storage for demo purposes
experiments = {}
experiment_counter = 0

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    })

@app.route('/experiments', methods=['GET'])
def list_experiments():
    """List all experiments"""
    return jsonify({
        "experiments": list(experiments.values()),
        "count": len(experiments)
    })

@app.route('/experiments', methods=['POST'])
def create_experiment():
    """Create a new experiment"""
    global experiment_counter
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        experiment_counter += 1
        experiment_id = f"exp-{experiment_counter:03d}"
        
        experiment = {
            "experiment_id": experiment_id,
            "name": data.get("name", f"Experiment {experiment_counter}"),
            "description": data.get("description", ""),
            "parameters": data.get("parameters", {}),
            "status": "created",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        experiments[experiment_id] = experiment
        
        logger.info(f"Created experiment: {experiment_id}")
        
        return jsonify(experiment), 201
        
    except Exception as e:
        logger.error(f"Error creating experiment: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/experiments/<experiment_id>', methods=['GET'])
def get_experiment(experiment_id):
    """Get a specific experiment"""
    if experiment_id not in experiments:
        return jsonify({"error": "Experiment not found"}), 404
    
    return jsonify(experiments[experiment_id])

@app.route('/experiments/<experiment_id>/start', methods=['POST'])
def start_experiment(experiment_id):
    """Start an experiment"""
    if experiment_id not in experiments:
        return jsonify({"error": "Experiment not found"}), 404
    
    experiments[experiment_id]["status"] = "running"
    experiments[experiment_id]["updated_at"] = datetime.utcnow().isoformat()
    experiments[experiment_id]["started_at"] = datetime.utcnow().isoformat()
    
    logger.info(f"Started experiment: {experiment_id}")
    
    return jsonify(experiments[experiment_id])

@app.route('/experiments/<experiment_id>/stop', methods=['POST'])
def stop_experiment(experiment_id):
    """Stop an experiment"""
    if experiment_id not in experiments:
        return jsonify({"error": "Experiment not found"}), 404
    
    experiments[experiment_id]["status"] = "completed"
    experiments[experiment_id]["updated_at"] = datetime.utcnow().isoformat()
    experiments[experiment_id]["completed_at"] = datetime.utcnow().isoformat()
    
    logger.info(f"Stopped experiment: {experiment_id}")
    
    return jsonify(experiments[experiment_id])

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        "service": "Cars with a Life - Orchestrator",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "experiments": "/experiments",
            "create_experiment": "POST /experiments",
            "get_experiment": "GET /experiments/{id}",
            "start_experiment": "POST /experiments/{id}/start",
            "stop_experiment": "POST /experiments/{id}/stop"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

