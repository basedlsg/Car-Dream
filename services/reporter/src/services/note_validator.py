"""
Note validation service
Validates autonomous notes against CARLA and nuScenes map data
"""

import logging
from typing import Dict, List, Optional, Set
import re

from ..models.note_models import (
    AutonomousNote, ValidationResult, ValidationStatus, MapReference
)


class NoteValidator:
    """Validates autonomous notes against map data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.carla_locations = self._load_carla_locations()
        self.nuscenes_locations = self._load_nuscenes_locations()
        self.valid_actions = self._load_valid_actions()
        
    def validate_note(self, note: AutonomousNote) -> ValidationResult:
        """
        Validate an autonomous note against map data
        
        Args:
            note: Autonomous note to validate
            
        Returns:
            Validation result with detailed feedback
        """
        try:
            # Validate individual components
            location_valid = self._validate_location(note.location, note.map_reference)
            action_valid = self._validate_action(note.action)
            destination_valid = self._validate_destination(note.destination, note.map_reference)
            
            # Check map data matches
            carla_match = self._check_carla_match(note)
            nuscenes_match = self._check_nuscenes_match(note)
            
            # Collect validation errors
            errors = []
            if not location_valid:
                errors.append(f"Invalid location: {note.location}")
            if not action_valid:
                errors.append(f"Invalid action: {note.action}")
            if not destination_valid:
                errors.append(f"Invalid destination: {note.destination}")
            if not carla_match:
                errors.append("Location not found in CARLA map data")
            if not nuscenes_match:
                errors.append("Location not found in nuScenes data")
            
            # Calculate overall validity and confidence
            is_valid = location_valid and action_valid and destination_valid
            confidence_score = self._calculate_validation_confidence(
                location_valid, action_valid, destination_valid, carla_match, nuscenes_match
            )
            
            # Update note validation status
            if is_valid and (carla_match or nuscenes_match):
                validation_status = ValidationStatus.VALID
            elif is_valid:
                validation_status = ValidationStatus.PARTIAL
            else:
                validation_status = ValidationStatus.INVALID
            
            # Update note status
            note.validation_status = validation_status
            
            result = ValidationResult(
                is_valid=is_valid,
                location_valid=location_valid,
                action_valid=action_valid,
                destination_valid=destination_valid,
                carla_map_match=carla_match,
                nuscenes_match=nuscenes_match,
                validation_errors=errors,
                confidence_score=confidence_score
            )
            
            self.logger.info(f"Validated note {note.note_id}: {validation_status.value}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error validating note {note.note_id}: {str(e)}")
            note.validation_status = ValidationStatus.INVALID
            raise
    
    def _validate_location(self, location: str, map_ref: MapReference) -> bool:
        """Validate location string format and content"""
        if not location or len(location.strip()) == 0:
            return False
        
        # Check for coordinate format
        coord_pattern = r"coordinates \([-+]?\d*\.?\d+, [-+]?\d*\.?\d+\)"
        if re.match(coord_pattern, location):
            return True
        
        # Check against known locations
        location_lower = location.lower()
        return (
            location_lower in self.carla_locations or 
            location_lower in self.nuscenes_locations or
            any(known in location_lower for known in self.carla_locations) or
            any(known in location_lower for known in self.nuscenes_locations)
        )
    
    def _validate_action(self, action: str) -> bool:
        """Validate action description"""
        if not action or len(action.strip()) == 0:
            return False
        
        action_lower = action.lower()
        return any(valid_action in action_lower for valid_action in self.valid_actions)
    
    def _validate_destination(self, destination: str, map_ref: MapReference) -> bool:
        """Validate destination description"""
        if not destination or len(destination.strip()) == 0:
            return False
        
        # Generic destinations are always valid
        generic_destinations = {"next waypoint", "destination", "target", "goal"}
        if destination.lower() in generic_destinations:
            return True
        
        # Check against known locations (same as location validation)
        return self._validate_location(destination, map_ref)
    
    def _check_carla_match(self, note: AutonomousNote) -> bool:
        """Check if note references match CARLA map data"""
        map_ref = note.map_reference
        
        # If map reference indicates CARLA map
        if map_ref.map_name and "town" in map_ref.map_name.lower():
            location_lower = note.location.lower()
            return any(carla_loc in location_lower for carla_loc in self.carla_locations)
        
        return False
    
    def _check_nuscenes_match(self, note: AutonomousNote) -> bool:
        """Check if note references match nuScenes data"""
        map_ref = note.map_reference
        
        # If map reference indicates nuScenes data
        if map_ref.map_name and ("nuscenes" in map_ref.map_name.lower() or "boston" in map_ref.map_name.lower() or "singapore" in map_ref.map_name.lower()):
            location_lower = note.location.lower()
            return any(nuscenes_loc in location_lower for nuscenes_loc in self.nuscenes_locations)
        
        return False
    
    def _calculate_validation_confidence(
        self, 
        location_valid: bool, 
        action_valid: bool, 
        destination_valid: bool,
        carla_match: bool,
        nuscenes_match: bool
    ) -> float:
        """Calculate validation confidence score"""
        # Weight different validation aspects
        weights = {
            'location': 0.3,
            'action': 0.2,
            'destination': 0.2,
            'carla_match': 0.15,
            'nuscenes_match': 0.15
        }
        
        score = 0.0
        if location_valid:
            score += weights['location']
        if action_valid:
            score += weights['action']
        if destination_valid:
            score += weights['destination']
        if carla_match:
            score += weights['carla_match']
        if nuscenes_match:
            score += weights['nuscenes_match']
        
        return score
    
    def _load_carla_locations(self) -> Set[str]:
        """Load known CARLA location names"""
        # Common CARLA locations and landmarks
        return {
            "intersection", "roundabout", "highway", "parking lot", "gas station",
            "bridge", "tunnel", "crosswalk", "traffic light", "stop sign",
            "spawn point", "waypoint", "junction", "lane", "sidewalk",
            "building", "road", "street", "avenue", "boulevard"
        }
    
    def _load_nuscenes_locations(self) -> Set[str]:
        """Load known nuScenes location names"""
        # Common nuScenes locations (Boston and Singapore)
        return {
            "boston", "singapore", "seaport", "downtown", "financial district",
            "marina bay", "orchard road", "changi", "jurong", "woodlands",
            "back bay", "cambridge", "somerville", "quincy", "newton",
            "intersection", "highway", "expressway", "mrt station", "bus stop"
        }
    
    def _load_valid_actions(self) -> Set[str]:
        """Load valid driving action descriptions"""
        return {
            "turned", "turn", "accelerated", "accelerate", "braked", "brake",
            "stopped", "stop", "continued", "proceed", "merged", "merge",
            "changed lanes", "lane change", "yielded", "yield", "parked", "park",
            "reversed", "reverse", "slowed", "slow", "sped up", "speed up",
            "overtook", "overtake", "followed", "follow", "waited", "wait"
        }
    
    def batch_validate_notes(self, notes: List[AutonomousNote]) -> List[ValidationResult]:
        """
        Validate a batch of autonomous notes
        
        Args:
            notes: List of notes to validate
            
        Returns:
            List of validation results
        """
        results = []
        for note in notes:
            try:
                result = self.validate_note(note)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to validate note {note.note_id}: {str(e)}")
                # Create failed validation result
                failed_result = ValidationResult(
                    is_valid=False,
                    location_valid=False,
                    action_valid=False,
                    destination_valid=False,
                    carla_map_match=False,
                    nuscenes_match=False,
                    validation_errors=[f"Validation failed: {str(e)}"],
                    confidence_score=0.0
                )
                results.append(failed_result)
        
        valid_count = sum(1 for r in results if r.is_valid)
        self.logger.info(f"Validated {len(notes)} notes: {valid_count} valid, {len(notes) - valid_count} invalid")
        
        return results