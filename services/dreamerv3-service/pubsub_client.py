"""
Pub/Sub client for publishing AI decision events and metrics
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.publisher.futures import Future

from schemas import AIDecisionEvent, PredictionResponse, SimulationState

logger = logging.getLogger(__name__)


class PubSubClient:
    """
    Google Cloud Pub/Sub client for publishing AI decision events
    """
    
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.publisher = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Topic names
        self.topics = {
            "ai_decisions": os.getenv("AI_DECISIONS_TOPIC", "ai-decisions"),
            "experiment_events": os.getenv("EXPERIMENT_EVENTS_TOPIC", "experiment-events"),
            "model_metrics": os.getenv("MODEL_METRICS_TOPIC", "model-metrics")
        }
        
        # Initialize publisher
        self._initialize_publisher()
    
    def _initialize_publisher(self):
        """Initialize Pub/Sub publisher client"""
        try:
            if not self.project_id:
                logger.warning("GCP_PROJECT_ID not set, Pub/Sub publishing disabled")
                return
            
            self.publisher = pubsub_v1.PublisherClient()
            logger.info("Pub/Sub publisher initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Pub/Sub publisher: {e}")
            self.publisher = None
    
    async def publish_ai_decision(
        self, 
        simulation_id: str,
        experiment_id: str,
        prediction: PredictionResponse,
        simulation_state: SimulationState,
        processing_time_ms: float
    ) -> bool:
        """
        Publish AI decision event to Pub/Sub
        
        Args:
            simulation_id: Simulation identifier
            experiment_id: Experiment identifier  
            prediction: AI prediction response
            simulation_state: Current simulation state
            processing_time_ms: Processing time in milliseconds
            
        Returns:
            bool: True if published successfully
        """
        if not self.publisher:
            logger.warning("Pub/Sub publisher not available")
            return False
        
        try:
            # Create AI decision event
            event = AIDecisionEvent(
                simulation_id=simulation_id,
                experiment_id=experiment_id,
                timestamp=datetime.utcnow().isoformat(),
                action=prediction.action,
                confidence=prediction.confidence,
                model_version=prediction.model_version,
                vehicle_position=simulation_state.vehicle_position,
                vehicle_velocity=simulation_state.vehicle_velocity,
                nearby_vehicles_count=len(simulation_state.nearby_vehicles),
                traffic_light_state=self._get_current_traffic_light_state(simulation_state),
                processing_time_ms=processing_time_ms,
                memory_usage_mb=self._get_memory_usage()
            )
            
            # Publish event asynchronously
            success = await self._publish_message(
                self.topics["ai_decisions"],
                event.dict(),
                {
                    "simulation_id": simulation_id,
                    "experiment_id": experiment_id,
                    "action_type": prediction.action.action_type,
                    "confidence": str(prediction.confidence)
                }
            )
            
            if success:
                logger.debug(f"Published AI decision event for simulation {simulation_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to publish AI decision event: {e}")
            return False
    
    async def publish_experiment_event(
        self,
        experiment_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Publish experiment event to Pub/Sub
        
        Args:
            experiment_id: Experiment identifier
            event_type: Type of event (started, completed, failed, etc.)
            event_data: Event-specific data
            metadata: Optional metadata attributes
            
        Returns:
            bool: True if published successfully
        """
        if not self.publisher:
            logger.warning("Pub/Sub publisher not available")
            return False
        
        try:
            event = {
                "experiment_id": experiment_id,
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": event_data,
                "source": "dreamerv3-service"
            }
            
            attributes = {
                "experiment_id": experiment_id,
                "event_type": event_type,
                **(metadata or {})
            }
            
            success = await self._publish_message(
                self.topics["experiment_events"],
                event,
                attributes
            )
            
            if success:
                logger.debug(f"Published experiment event: {event_type} for {experiment_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to publish experiment event: {e}")
            return False
    
    async def publish_model_metrics(
        self,
        model_version: str,
        metrics: Dict[str, float],
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Publish model performance metrics to Pub/Sub
        
        Args:
            model_version: Model version identifier
            metrics: Performance metrics dictionary
            metadata: Optional metadata attributes
            
        Returns:
            bool: True if published successfully
        """
        if not self.publisher:
            logger.warning("Pub/Sub publisher not available")
            return False
        
        try:
            event = {
                "model_version": model_version,
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": metrics,
                "source": "dreamerv3-service"
            }
            
            attributes = {
                "model_version": model_version,
                "metric_type": "performance",
                **(metadata or {})
            }
            
            success = await self._publish_message(
                self.topics["model_metrics"],
                event,
                attributes
            )
            
            if success:
                logger.debug(f"Published model metrics for version {model_version}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to publish model metrics: {e}")
            return False
    
    async def _publish_message(
        self,
        topic_name: str,
        message_data: Dict[str, Any],
        attributes: Dict[str, str]
    ) -> bool:
        """
        Publish message to specified topic
        
        Args:
            topic_name: Pub/Sub topic name
            message_data: Message data dictionary
            attributes: Message attributes
            
        Returns:
            bool: True if published successfully
        """
        try:
            topic_path = self.publisher.topic_path(self.project_id, topic_name)
            
            # Convert message to JSON bytes
            message_json = json.dumps(message_data, default=str)
            message_bytes = message_json.encode('utf-8')
            
            # Publish message asynchronously
            loop = asyncio.get_event_loop()
            future = await loop.run_in_executor(
                self.executor,
                lambda: self.publisher.publish(
                    topic_path,
                    message_bytes,
                    **attributes
                )
            )
            
            # Wait for publish to complete
            message_id = await loop.run_in_executor(
                self.executor,
                future.result
            )
            
            logger.debug(f"Message published to {topic_name} with ID: {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish message to {topic_name}: {e}")
            return False
    
    def _get_current_traffic_light_state(self, simulation_state: SimulationState) -> Optional[str]:
        """Get current traffic light state from simulation"""
        try:
            if not simulation_state.traffic_lights:
                return None
            
            # Find closest traffic light
            ego_position = simulation_state.vehicle_position
            closest_light = None
            min_distance = float('inf')
            
            for light in simulation_state.traffic_lights:
                distance = ((light.position[0] - ego_position[0]) ** 2 + 
                           (light.position[1] - ego_position[1]) ** 2) ** 0.5
                
                if distance < min_distance:
                    min_distance = distance
                    closest_light = light
            
            return closest_light.state if closest_light else None
            
        except Exception as e:
            logger.error(f"Failed to get traffic light state: {e}")
            return None
    
    def _get_memory_usage(self) -> Optional[float]:
        """Get current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            return round(memory_mb, 2)
        except Exception:
            return None
    
    async def publish_batch_events(
        self,
        events: list,
        topic_name: str,
        batch_size: int = 100
    ) -> int:
        """
        Publish multiple events in batches
        
        Args:
            events: List of event dictionaries
            topic_name: Target topic name
            batch_size: Number of events per batch
            
        Returns:
            int: Number of successfully published events
        """
        if not self.publisher or not events:
            return 0
        
        try:
            published_count = 0
            
            # Process events in batches
            for i in range(0, len(events), batch_size):
                batch = events[i:i + batch_size]
                
                # Publish batch concurrently
                tasks = []
                for event in batch:
                    task = self._publish_message(
                        topic_name,
                        event.get("data", {}),
                        event.get("attributes", {})
                    )
                    tasks.append(task)
                
                # Wait for batch to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count successful publishes
                for result in results:
                    if result is True:
                        published_count += 1
                    elif isinstance(result, Exception):
                        logger.error(f"Batch publish error: {result}")
            
            logger.info(f"Published {published_count}/{len(events)} events to {topic_name}")
            return published_count
            
        except Exception as e:
            logger.error(f"Failed to publish batch events: {e}")
            return 0
    
    def close(self):
        """Close Pub/Sub client and cleanup resources"""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)
            
            if self.publisher:
                # Publisher client doesn't need explicit closing
                self.publisher = None
            
            logger.info("Pub/Sub client closed successfully")
            
        except Exception as e:
            logger.error(f"Failed to close Pub/Sub client: {e}")


# Global Pub/Sub client instance
pubsub_client = PubSubClient()