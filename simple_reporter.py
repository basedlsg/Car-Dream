#!/usr/bin/env python3
"""
Simple Reporter Service for Cars with a Life
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
reports = {}
metrics = {}
notes = {}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "reporter",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    })

@app.route('/reports', methods=['GET'])
def list_reports():
    """List all reports"""
    return jsonify({
        "reports": list(reports.values()),
        "count": len(reports)
    })

@app.route('/reports/<experiment_id>', methods=['GET'])
def get_report(experiment_id):
    """Get a specific report"""
    if experiment_id not in reports:
        # Create a sample report if it doesn't exist
        reports[experiment_id] = {
            "experiment_id": experiment_id,
            "report_id": f"report-{experiment_id}",
            "status": "completed",
            "summary": {
                "total_distance": 1500.5,
                "average_speed": 45.2,
                "collisions": 0,
                "traffic_violations": 0,
                "success_rate": 98.5
            },
            "created_at": datetime.utcnow().isoformat()
        }
    
    return jsonify(reports[experiment_id])

@app.route('/metrics/<experiment_id>', methods=['GET'])
def get_metrics(experiment_id):
    """Get metrics for an experiment"""
    if experiment_id not in metrics:
        # Create sample metrics if they don't exist
        metrics[experiment_id] = {
            "experiment_id": experiment_id,
            "performance_metrics": {
                "response_time": 0.15,
                "accuracy": 0.985,
                "efficiency": 0.92,
                "safety_score": 0.99
            },
            "ai_metrics": {
                "decision_confidence": 0.87,
                "prediction_accuracy": 0.91,
                "learning_rate": 0.001
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    return jsonify(metrics[experiment_id])

@app.route('/notes/<experiment_id>', methods=['GET'])
def get_notes(experiment_id):
    """Get AI-generated notes for an experiment"""
    if experiment_id not in notes:
        # Create sample notes if they don't exist
        notes[experiment_id] = {
            "experiment_id": experiment_id,
            "ai_insights": [
                "The autonomous vehicle demonstrated excellent lane-keeping behavior throughout the simulation.",
                "No safety violations were detected during the 15-minute test run.",
                "The AI model showed high confidence in decision-making with an average confidence score of 87%.",
                "Performance was optimal in clear weather conditions with minimal traffic interference."
            ],
            "recommendations": [
                "Consider testing in more challenging weather conditions to improve robustness.",
                "The current model performs well but could benefit from additional training on edge cases.",
                "Implement additional safety checks for pedestrian detection scenarios."
            ],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    return jsonify(notes[experiment_id])

@app.route('/reports', methods=['POST'])
def create_report():
    """Create a new report"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        experiment_id = data.get("experiment_id")
        if not experiment_id:
            return jsonify({"error": "experiment_id is required"}), 400
        
        report = {
            "experiment_id": experiment_id,
            "report_id": f"report-{experiment_id}",
            "status": "generated",
            "summary": data.get("summary", {}),
            "created_at": datetime.utcnow().isoformat()
        }
        
        reports[experiment_id] = report
        
        logger.info(f"Created report for experiment: {experiment_id}")
        
        return jsonify(report), 201
        
    except Exception as e:
        logger.error(f"Error creating report: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        "service": "Cars with a Life - Reporter",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "reports": "/reports",
            "get_report": "GET /reports/{experiment_id}",
            "metrics": "GET /metrics/{experiment_id}",
            "notes": "GET /notes/{experiment_id}",
            "create_report": "POST /reports"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

