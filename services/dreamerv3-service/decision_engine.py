"""
Decision-making logic for autonomous driving using DreamerV3 model
"""

import logging
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass

from schemas import (
    SimulationState, DrivingAction, ActionType, VehicleInfo, 
    TrafficLight, Waypoint, PredictionResponse
)
from utils import calculate_distance_3d, normalize_angle

logger = logging.getLogger(__name__)


@dataclass
class DecisionContext:
    """Context information for decision making"""
    simulation_id: str
    experiment_id: str
    current_speed: float
    target_speed: float
    safety_margin: float
    risk_tolerance: float
    traffic_compliance: bool
    emergency_mode: bool


class DecisionEngine:
    """
    Advanced decision-making engine that processes simulation state
    and generates contextual driving actions
    """
    
    def __init__(self):
        self.safety_distance_threshold = 10.0  # meters
        self.speed_limit_buffer = 0.9  # 90% of speed limit
        self.emergency_brake_distance = 5.0  # meters
        self.lane_change_min_gap = 15.0  # meters
        
        # Decision weights
        self.weights = {
            "safety": 0.4,
            "efficiency": 0.3,
            "comfort": 0.2,
            "traffic_compliance": 0.1
        }
    
    def process_simulation_state(
        self, 
        simulation_state: SimulationState, 
        context: Optional[DecisionContext] = None
    ) -> Tuple[Dict[str, Any], float]:
        """
        Process simulation state and generate decision context
        
        Args:
            simulation_state: Current CARLA simulation state
            context: Optional decision context
            
        Returns:
            Tuple of (processed_state_dict, risk_score)
        """
        try:
            # Extract ego vehicle information
            ego_position = simulation_state.vehicle_position
            ego_velocity = simulation_state.vehicle_velocity
            ego_rotation = simulation_state.vehicle_rotation
            
            # Calculate current speed
            current_speed = np.linalg.norm(ego_velocity)
            
            # Analyze nearby vehicles
            vehicle_analysis = self._analyze_nearby_vehicles(
                ego_position, ego_velocity, simulation_state.nearby_vehicles
            )
            
            # Analyze traffic lights
            traffic_analysis = self._analyze_traffic_lights(
                ego_position, simulation_state.traffic_lights
            )
            
            # Analyze road waypoints
            road_analysis = self._analyze_road_waypoints(
                ego_position, ego_rotation, simulation_state.road_waypoints
            )
            
            # Calculate risk assessment
            risk_score = self._calculate_risk_score(
                vehicle_analysis, traffic_analysis, road_analysis, current_speed
            )
            
            # Create processed state
            processed_state = {
                "ego_vehicle": {
                    "position": ego_position,
                    "velocity": ego_velocity,
                    "rotation": ego_rotation,
                    "speed": current_speed
                },
                "environment": {
                    "nearby_vehicles": vehicle_analysis,
                    "traffic_lights": traffic_analysis,
                    "road_info": road_analysis,
                    "weather": simulation_state.weather,
                    "time_of_day": simulation_state.time_of_day
                },
                "risk_assessment": {
                    "overall_risk": risk_score,
                    "collision_risk": vehicle_analysis.get("collision_risk", 0.0),
                    "traffic_violation_risk": traffic_analysis.get("violation_risk", 0.0)
                },
                "timestamp": simulation_state.timestamp
            }
            
            return processed_state, risk_score
            
        except Exception as e:
            logger.error(f"Failed to process simulation state: {e}")
            raise
    
    def _analyze_nearby_vehicles(
        self, 
        ego_position: List[float], 
        ego_velocity: List[float], 
        nearby_vehicles: List[VehicleInfo]
    ) -> Dict[str, Any]:
        """Analyze nearby vehicles for collision risk and lane information"""
        try:
            analysis = {
                "total_count": len(nearby_vehicles),
                "closest_vehicle_distance": float('inf'),
                "vehicles_in_lane": [],
                "vehicles_left_lane": [],
                "vehicles_right_lane": [],
                "collision_risk": 0.0,
                "lane_change_safe": {"left": True, "right": True}
            }
            
            for vehicle in nearby_vehicles:
                distance = calculate_distance_3d(ego_position, vehicle.position)
                
                # Update closest vehicle
                if distance < analysis["closest_vehicle_distance"]:
                    analysis["closest_vehicle_distance"] = distance
                
                # Determine relative lane position (simplified)
                relative_y = vehicle.position[1] - ego_position[1]
                
                vehicle_info = {
                    "id": vehicle.id,
                    "distance": distance,
                    "relative_velocity": vehicle.relative_velocity,
                    "position": vehicle.position
                }
                
                if abs(relative_y) < 2.0:  # Same lane
                    analysis["vehicles_in_lane"].append(vehicle_info)
                elif relative_y < -2.0:  # Left lane
                    analysis["vehicles_left_lane"].append(vehicle_info)
                elif relative_y > 2.0:  # Right lane
                    analysis["vehicles_right_lane"].append(vehicle_info)
                
                # Check collision risk
                if distance < self.safety_distance_threshold:
                    # Calculate time to collision
                    relative_speed = np.linalg.norm(vehicle.relative_velocity)
                    if relative_speed > 0:
                        ttc = distance / relative_speed
                        if ttc < 3.0:  # Less than 3 seconds
                            analysis["collision_risk"] = max(
                                analysis["collision_risk"], 
                                1.0 - (ttc / 3.0)
                            )
                
                # Check lane change safety
                if distance < self.lane_change_min_gap:
                    if relative_y < -2.0:  # Vehicle in left lane
                        analysis["lane_change_safe"]["left"] = False
                    elif relative_y > 2.0:  # Vehicle in right lane
                        analysis["lane_change_safe"]["right"] = False
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze nearby vehicles: {e}")
            return {"total_count": 0, "collision_risk": 0.5}
    
    def _analyze_traffic_lights(
        self, 
        ego_position: List[float], 
        traffic_lights: List[TrafficLight]
    ) -> Dict[str, Any]:
        """Analyze traffic lights for compliance requirements"""
        try:
            analysis = {
                "total_count": len(traffic_lights),
                "closest_light": None,
                "closest_distance": float('inf'),
                "violation_risk": 0.0,
                "should_stop": False,
                "can_proceed": True
            }
            
            for light in traffic_lights:
                distance = calculate_distance_3d(ego_position, light.position)
                
                if distance < analysis["closest_distance"]:
                    analysis["closest_distance"] = distance
                    analysis["closest_light"] = {
                        "id": light.id,
                        "state": light.state,
                        "distance": distance,
                        "position": light.position
                    }
                
                # Determine action based on light state and distance
                if distance < 50.0:  # Within influence range
                    if light.state == "red":
                        analysis["should_stop"] = True
                        analysis["can_proceed"] = False
                        if distance < 10.0:  # Too close to stop safely
                            analysis["violation_risk"] = 0.8
                    elif light.state == "yellow":
                        if distance < 20.0:  # Too close to stop
                            analysis["can_proceed"] = True
                        else:
                            analysis["should_stop"] = True
                            analysis["violation_risk"] = 0.3
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze traffic lights: {e}")
            return {"total_count": 0, "violation_risk": 0.0}
    
    def _analyze_road_waypoints(
        self, 
        ego_position: List[float], 
        ego_rotation: List[float], 
        waypoints: List[Waypoint]
    ) -> Dict[str, Any]:
        """Analyze road waypoints for path planning"""
        try:
            analysis = {
                "total_waypoints": len(waypoints),
                "current_lane_id": None,
                "current_road_id": None,
                "is_in_junction": False,
                "path_curvature": 0.0,
                "recommended_speed": 30.0,  # Default speed limit
                "lane_center_offset": 0.0
            }
            
            if not waypoints:
                return analysis
            
            # Find closest waypoint
            closest_waypoint = None
            min_distance = float('inf')
            
            for waypoint in waypoints:
                distance = calculate_distance_3d(ego_position, waypoint.position)
                if distance < min_distance:
                    min_distance = distance
                    closest_waypoint = waypoint
            
            if closest_waypoint:
                analysis["current_lane_id"] = closest_waypoint.lane_id
                analysis["current_road_id"] = closest_waypoint.road_id
                analysis["is_in_junction"] = closest_waypoint.is_junction
                
                # Calculate lane center offset
                waypoint_y = closest_waypoint.position[1]
                ego_y = ego_position[1]
                analysis["lane_center_offset"] = ego_y - waypoint_y
                
                # Estimate path curvature from nearby waypoints
                if len(waypoints) >= 3:
                    analysis["path_curvature"] = self._calculate_path_curvature(waypoints[:3])
                
                # Adjust recommended speed based on curvature and junction
                if analysis["is_in_junction"]:
                    analysis["recommended_speed"] = 15.0
                elif abs(analysis["path_curvature"]) > 0.1:
                    analysis["recommended_speed"] = 20.0
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze road waypoints: {e}")
            return {"total_waypoints": 0, "recommended_speed": 30.0}
    
    def _calculate_path_curvature(self, waypoints: List[Waypoint]) -> float:
        """Calculate path curvature from waypoints"""
        try:
            if len(waypoints) < 3:
                return 0.0
            
            # Simple curvature calculation using three points
            p1 = np.array(waypoints[0].position[:2])  # x, y only
            p2 = np.array(waypoints[1].position[:2])
            p3 = np.array(waypoints[2].position[:2])
            
            # Calculate vectors
            v1 = p2 - p1
            v2 = p3 - p2
            
            # Calculate angle between vectors
            if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
                return 0.0
            
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            angle = np.arccos(cos_angle)
            
            # Normalize to [-1, 1] range
            curvature = (angle - np.pi/2) / (np.pi/2)
            
            return float(curvature)
            
        except Exception as e:
            logger.error(f"Failed to calculate path curvature: {e}")
            return 0.0
    
    def _calculate_risk_score(
        self, 
        vehicle_analysis: Dict[str, Any], 
        traffic_analysis: Dict[str, Any], 
        road_analysis: Dict[str, Any], 
        current_speed: float
    ) -> float:
        """Calculate overall risk score"""
        try:
            risk_factors = []
            
            # Collision risk from nearby vehicles
            collision_risk = vehicle_analysis.get("collision_risk", 0.0)
            risk_factors.append(collision_risk * self.weights["safety"])
            
            # Traffic violation risk
            violation_risk = traffic_analysis.get("violation_risk", 0.0)
            risk_factors.append(violation_risk * self.weights["traffic_compliance"])
            
            # Speed risk (too fast for conditions)
            recommended_speed = road_analysis.get("recommended_speed", 30.0)
            if current_speed > recommended_speed * 1.2:
                speed_risk = (current_speed - recommended_speed) / recommended_speed
                risk_factors.append(min(speed_risk, 1.0) * self.weights["safety"])
            
            # Junction risk
            if road_analysis.get("is_in_junction", False):
                risk_factors.append(0.3 * self.weights["safety"])
            
            # Lane offset risk
            lane_offset = abs(road_analysis.get("lane_center_offset", 0.0))
            if lane_offset > 1.0:  # More than 1 meter from center
                offset_risk = min(lane_offset / 2.0, 1.0)
                risk_factors.append(offset_risk * self.weights["comfort"])
            
            # Calculate weighted average
            total_risk = sum(risk_factors)
            return min(total_risk, 1.0)
            
        except Exception as e:
            logger.error(f"Failed to calculate risk score: {e}")
            return 0.5  # Default moderate risk
    
    def enhance_prediction(
        self, 
        raw_prediction: PredictionResponse, 
        processed_state: Dict[str, Any], 
        context: Optional[DecisionContext] = None
    ) -> PredictionResponse:
        """
        Enhance raw model prediction with decision logic
        
        Args:
            raw_prediction: Raw prediction from model
            processed_state: Processed simulation state
            context: Optional decision context
            
        Returns:
            Enhanced prediction with safety and logic adjustments
        """
        try:
            # Start with raw prediction
            enhanced_action = DrivingAction(
                action_type=raw_prediction.action.action_type,
                throttle=raw_prediction.action.throttle,
                brake=raw_prediction.action.brake,
                steering=raw_prediction.action.steering,
                gear=raw_prediction.action.gear,
                hand_brake=raw_prediction.action.hand_brake
            )
            
            enhanced_confidence = raw_prediction.confidence
            reasoning_parts = []
            
            # Apply safety overrides
            risk_assessment = processed_state.get("risk_assessment", {})
            overall_risk = risk_assessment.get("overall_risk", 0.0)
            
            # Emergency braking override
            collision_risk = risk_assessment.get("collision_risk", 0.0)
            if collision_risk > 0.7:
                enhanced_action.action_type = ActionType.BRAKE
                enhanced_action.brake = 1.0
                enhanced_action.throttle = 0.0
                enhanced_confidence = 0.9
                reasoning_parts.append("Emergency braking due to collision risk")
            
            # Traffic light compliance
            traffic_info = processed_state.get("environment", {}).get("traffic_lights", {})
            if traffic_info.get("should_stop", False):
                if enhanced_action.action_type in [ActionType.ACCELERATE, ActionType.MAINTAIN_SPEED]:
                    enhanced_action.action_type = ActionType.BRAKE
                    enhanced_action.brake = min(enhanced_action.brake + 0.3, 1.0)
                    enhanced_action.throttle = max(enhanced_action.throttle - 0.5, 0.0)
                    reasoning_parts.append("Stopping for traffic light")
            
            # Speed limit compliance
            current_speed = processed_state.get("ego_vehicle", {}).get("speed", 0.0)
            road_info = processed_state.get("environment", {}).get("road_info", {})
            recommended_speed = road_info.get("recommended_speed", 30.0)
            
            if current_speed > recommended_speed * 1.1:  # 10% over limit
                if enhanced_action.action_type == ActionType.ACCELERATE:
                    enhanced_action.action_type = ActionType.MAINTAIN_SPEED
                    enhanced_action.throttle = max(enhanced_action.throttle - 0.2, 0.0)
                    reasoning_parts.append("Reducing speed for compliance")
            
            # Lane keeping assistance
            lane_offset = road_info.get("lane_center_offset", 0.0)
            if abs(lane_offset) > 0.5:  # More than 0.5m from center
                correction_factor = min(abs(lane_offset) / 2.0, 0.3)
                if lane_offset > 0:  # Too far right, steer left
                    enhanced_action.steering = max(enhanced_action.steering - correction_factor, -1.0)
                else:  # Too far left, steer right
                    enhanced_action.steering = min(enhanced_action.steering + correction_factor, 1.0)
                reasoning_parts.append("Lane keeping correction")
            
            # Smooth steering adjustments
            if abs(enhanced_action.steering) > 0.8:
                enhanced_action.steering = np.sign(enhanced_action.steering) * 0.8
                reasoning_parts.append("Limiting steering for stability")
            
            # Adjust confidence based on risk
            if overall_risk > 0.5:
                enhanced_confidence = enhanced_confidence * (1.0 - overall_risk * 0.3)
            
            # Create enhanced prediction response
            enhanced_prediction = PredictionResponse(
                action=enhanced_action,
                confidence=enhanced_confidence,
                model_version=raw_prediction.model_version,
                timestamp=raw_prediction.timestamp,
                processing_time_ms=raw_prediction.processing_time_ms,
                reasoning=" | ".join(reasoning_parts) if reasoning_parts else None,
                risk_assessment={
                    "overall_risk": overall_risk,
                    "collision_risk": collision_risk,
                    "traffic_violation_risk": risk_assessment.get("traffic_violation_risk", 0.0)
                }
            )
            
            return enhanced_prediction
            
        except Exception as e:
            logger.error(f"Failed to enhance prediction: {e}")
            # Return original prediction if enhancement fails
            return raw_prediction