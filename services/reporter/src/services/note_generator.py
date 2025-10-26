"""
Autonomous note generation service
Implements note generation from simulation data and AI decisions
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import uuid

from ..models.note_models import (
    SimulationData, AIDecision, AutonomousNote, ValidationStatus,
    MapReference, ValidationResult
)


class NoteGenerator:
    """Generates autonomous driving notes from simulation and AI data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def generate_note(
        self, 
        simulation_data: SimulationData, 
        ai_decision: AIDecision,
        experiment_id: str
    ) -> AutonomousNote:
        """
        Generate an autonomous note from simulation data and AI decision
        
        Args:
            simulation_data: Current simulation state
            ai_decision: AI decision and action data
            experiment_id: Associated experiment identifier
            
        Returns:
            Generated autonomous note
        """
        try:
            # Generate note ID
            note_id = str(uuid.uuid4())
            
            # Extract location information
            location = self._extract_location(simulation_data)
            
            # Format action description
            action = self._format_action(ai_decision)
            
            # Extract destination
            destination = self._extract_destination(ai_decision, simulation_data)
            
            # Generate the formatted note text
            raw_note = f"At {location}, did {action} to reach {destination}"
            
            # Calculate confidence score
            confidence = self._calculate_confidence(simulation_data, ai_decision)
            
            # Create autonomous note
            note = AutonomousNote(
                note_id=note_id,
                experiment_id=experiment_id,
                timestamp=simulation_data.timestamp,
                location=location,
                action=action,
                destination=destination,
                confidence=confidence,
                validation_status=ValidationStatus.PENDING,
                map_reference=simulation_data.map_reference,
                raw_note=raw_note
            )
            
            self.logger.info(f"Generated note {note_id}: {raw_note}")
            return note
            
        except Exception as e:
            self.logger.error(f"Error generating note: {str(e)}")
            raise
    
    def _extract_location(self, simulation_data: SimulationData) -> str:
        """Extract and format location information"""
        # Use current location if available, otherwise use coordinates
        if simulation_data.current_location:
            return simulation_data.current_location
        
        # Format coordinates as location
        pos = simulation_data.vehicle_position
        return f"coordinates ({pos.latitude:.4f}, {pos.longitude:.4f})"
    
    def _format_action(self, ai_decision: AIDecision) -> str:
        """Format AI decision into human-readable action"""
        action_type = ai_decision.action_type.lower()
        
        # Map action types to human-readable descriptions
        action_mappings = {
            "turn_left": "turned left",
            "turn_right": "turned right",
            "go_straight": "continued straight",
            "accelerate": "accelerated",
            "brake": "braked",
            "stop": "stopped",
            "lane_change_left": "changed lanes to the left",
            "lane_change_right": "changed lanes to the right",
            "merge": "merged into traffic",
            "yield": "yielded to traffic",
            "park": "parked",
            "reverse": "reversed"
        }
        
        # Use mapped action or fall back to description
        if action_type in action_mappings:
            return action_mappings[action_type]
        elif ai_decision.action_description:
            return ai_decision.action_description.lower()
        else:
            return action_type
    
    def _extract_destination(self, ai_decision: AIDecision, simulation_data: SimulationData) -> str:
        """Extract destination information"""
        # Use AI decision target if available
        if ai_decision.target_destination:
            return ai_decision.target_destination
        
        # Use nearby POIs as potential destinations
        if simulation_data.nearby_pois:
            return simulation_data.nearby_pois[0]  # Use closest POI
        
        # Default to generic destination
        return "next waypoint"
    
    def _calculate_confidence(self, simulation_data: SimulationData, ai_decision: AIDecision) -> float:
        """Calculate overall confidence score for the note"""
        # Base confidence from AI decision
        base_confidence = ai_decision.confidence
        
        # Adjust based on data quality
        location_quality = 1.0 if simulation_data.current_location else 0.8
        poi_quality = 1.0 if simulation_data.nearby_pois else 0.7
        action_quality = 1.0 if ai_decision.action_description else 0.8
        
        # Calculate weighted confidence
        confidence = base_confidence * location_quality * poi_quality * action_quality
        
        return min(confidence, 1.0)  # Cap at 1.0
    
    def batch_generate_notes(
        self, 
        simulation_sequence: List[SimulationData],
        decision_sequence: List[AIDecision],
        experiment_id: str
    ) -> List[AutonomousNote]:
        """
        Generate notes for a sequence of simulation steps
        
        Args:
            simulation_sequence: List of simulation states
            decision_sequence: List of AI decisions
            experiment_id: Associated experiment identifier
            
        Returns:
            List of generated autonomous notes
        """
        if len(simulation_sequence) != len(decision_sequence):
            raise ValueError("Simulation and decision sequences must have same length")
        
        notes = []
        for sim_data, ai_decision in zip(simulation_sequence, decision_sequence):
            try:
                note = self.generate_note(sim_data, ai_decision, experiment_id)
                notes.append(note)
            except Exception as e:
                self.logger.error(f"Failed to generate note for timestamp {sim_data.timestamp}: {str(e)}")
                continue
        
        self.logger.info(f"Generated {len(notes)} notes for experiment {experiment_id}")
        return notes