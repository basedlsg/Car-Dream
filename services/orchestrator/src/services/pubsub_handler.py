""
"
Pub/Sub Handler Service
Handles Pub/Sub event processing and message routing between components
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.message import Message

from config.settings import Settings

logger = logging.getLogger(__name__)


class PubSubHandler:
    """Handles Pub/Sub messaging and event routing"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.publisher = None
        self.subscriber = None
        self.subscription_futures = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self._healthy = True
        self._running = False
    
    async def start(self):
        """Start the Pub/Sub handler"""
        try:
            # Initialize Pub/Sub clients
            self.publisher = pubsub_v1.PublisherClient()
            self.subscriber = pubsub_v1.SubscriberClient()
            
            # Register message handlers
            self._register_message_handlers()
            
            # Start subscriptions
            await self._start_subscriptions()
            
            self._running = True
            logger.info("Pub/Sub handler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Pub/Sub handler: {str(e)}")
            self._healthy = False
            raise
    
    async def stop(self):
        """Stop the Pub/Sub handler"""
        try:
            # Cancel all subscription futures
            for future in self.subscription_futures.values():
                future.cancel()
            
            self._running = False
            logger.info("Pub/Sub handler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping Pub/Sub handler: {str(e)}")
    
    def is_healthy(self) -> bool:
        """Check if the Pub/Sub handler is healthy"""
        return self._healthy and self._running
    
    def _register_message_handlers(self):
        """Register message handlers for different event types"""
        
        self.message_handlers = {
            "experiment_lifecycle": self._handle_experiment_lifecycle_event,
            "simulation_events": self._handle_simulation_event,
            "ai_decisions": self._handle_ai_decision_event,
            "evaluation_events": self._handle_evaluation_event,
            "system_events": self._handle_system_event
        }
    
    async def _start_subscriptions(self):
        """Start Pub/Sub subscriptions"""
        
        # Subscribe to orchestrator events
        subscription_path = self.subscriber.subscription_path(
            self.settings.pubsub_project_id,
            self.settings.orchestrator_subscription
        )
        
        # Start subscription in executor
        future = self.executor.submit(
            self.subscriber.subscribe,
            subscription_path,
            callback=self._message_callback,
            flow_control=pubsub_v1.types.FlowControl(max_messages=100)
        )
        
        self.subscription_futures["orchestrator"] = future
        logger.info(f"Started subscription: {subscription_path}")
    
    def _message_callback(self, message: Message):
        """Callback for processing Pub/Sub messages"""
        
        try:
            # Parse message data
            message_data = json.loads(message.data.decode('utf-8'))
            message_attributes = dict(message.attributes)
            
            # Get event type from attributes
            event_type = message_attributes.get('event_type', 'unknown')
            
            # Route message to appropriate handler
            handler = self.message_handlers.get(event_type)
            if handler:
                # Process message asynchronously
                asyncio.create_task(handler(message_data, message_attributes))
            else:
                logger.warning(f"No handler found for event type: {event_type}")
            
            # Acknowledge message
            message.ack()
            
        except Exception as e:
            logger.error(f"Error processing Pub/Sub message: {str(e)}")
            message.nack()
    
    async def _handle_experiment_lifecycle_event(self, data: Dict[str, Any], attributes: Dict[str, str]):
        """Handle experiment lifecycle events"""
        
        event_subtype = attributes.get('event_subtype', '')
        experiment_id = data.get('experiment_id', '')
        
        logger.info(f"Processing experiment lifecycle event: {event_subtype} for {experiment_id}")
        
        if event_subtype == "experiment_started":
            await self._handle_experiment_started(data)
        elif event_subtype == "experiment_completed":
            await self._handle_experiment_completed(data)
        elif event_subtype == "experiment_failed":
            await self._handle_experiment_failed(data)
        elif event_subtype == "experiment_cancelled":
            await self._handle_experiment_cancelled(data)
        else:
            logger.warning(f"Unknown experiment lifecycle event: {event_subtype}")
    
    async def _handle_simulation_event(self, data: Dict[str, Any], attributes: Dict[str, str]):
        """Handle simulation events from CARLA Runner"""
        
        event_subtype = attributes.get('event_subtype', '')
        experiment_id = data.get('experiment_id', '')
        
        logger.info(f"Processing simulation event: {event_subtype} for {experiment_id}")
        
        if event_subtype == "simulation_state_update":
            await self._handle_simulation_state_update(data)
        elif event_subtype == "collision_detected":
            await self._handle_collision_event(data)
        elif event_subtype == "traffic_violation":
            await self._handle_traffic_violation(data)
        elif event_subtype == "simulation_metrics":
            await self._handle_simulation_metrics(data)
        else:
            logger.warning(f"Unknown simulation event: {event_subtype}")
    
    async def _handle_ai_decision_event(self, data: Dict[str, Any], attributes: Dict[str, str]):
        """Handle AI decision events from DreamerV3 Service"""
        
        event_subtype = attributes.get('event_subtype', '')
        experiment_id = data.get('experiment_id', '')
        
        logger.info(f"Processing AI decision event: {event_subtype} for {experiment_id}")
        
        if event_subtype == "decision_made":
            await self._handle_ai_decision_made(data)
        elif event_subtype == "model_inference_complete":
            await self._handle_model_inference_complete(data)
        elif event_subtype == "decision_error":
            await self._handle_ai_decision_error(data)
        else:
            logger.warning(f"Unknown AI decision event: {event_subtype}")
    
    async def _handle_evaluation_event(self, data: Dict[str, Any], attributes: Dict[str, str]):
        """Handle evaluation events"""
        
        event_subtype = attributes.get('event_subtype', '')
        experiment_id = data.get('experiment_id', '')
        
        logger.info(f"Processing evaluation event: {event_subtype} for {experiment_id}")
        
        if event_subtype == "metrics_calculated":
            await self._handle_metrics_calculated(data)
        elif event_subtype == "performance_threshold_reached":
            await self._handle_performance_threshold(data)
        else:
            logger.warning(f"Unknown evaluation event: {event_subtype}")
    
    async def _handle_system_event(self, data: Dict[str, Any], attributes: Dict[str, str]):
        """Handle system-level events"""
        
        event_subtype = attributes.get('event_subtype', '')
        
        logger.info(f"Processing system event: {event_subtype}")
        
        if event_subtype == "service_health_check":
            await self._handle_service_health_check(data)
        elif event_subtype == "resource_usage_alert":
            await self._handle_resource_usage_alert(data)
        else:
            logger.warning(f"Unknown system event: {event_subtype}")
    
    # Event handler implementations
    
    async def _handle_experiment_started(self, data: Dict[str, Any]):
        """Handle experiment started event"""
        experiment_id = data.get('experiment_id')
        logger.info(f"Experiment {experiment_id} has started")
        # Additional orchestration logic can be added here
    
    async def _handle_experiment_completed(self, data: Dict[str, Any]):
        """Handle experiment completed event"""
        experiment_id = data.get('experiment_id')
        logger.info(f"Experiment {experiment_id} has completed")
        # Trigger post-experiment processing
    
    async def _handle_experiment_failed(self, data: Dict[str, Any]):
        """Handle experiment failed event"""
        experiment_id = data.get('experiment_id')
        error_message = data.get('error_message', 'Unknown error')
        logger.error(f"Experiment {experiment_id} failed: {error_message}")
        # Trigger failure recovery procedures
    
    async def _handle_experiment_cancelled(self, data: Dict[str, Any]):
        """Handle experiment cancelled event"""
        experiment_id = data.get('experiment_id')
        logger.info(f"Experiment {experiment_id} was cancelled")
        # Cleanup resources
    
    async def _handle_simulation_state_update(self, data: Dict[str, Any]):
        """Handle simulation state update"""
        experiment_id = data.get('experiment_id')
        state_data = data.get('state_data', {})
        # Forward state to AI decision service if needed
        logger.debug(f"Simulation state update for {experiment_id}")
    
    async def _handle_collision_event(self, data: Dict[str, Any]):
        """Handle collision detection event"""
        experiment_id = data.get('experiment_id')
        collision_data = data.get('collision_data', {})
        logger.warning(f"Collision detected in experiment {experiment_id}: {collision_data}")
        # Record collision for analysis
    
    async def _handle_traffic_violation(self, data: Dict[str, Any]):
        """Handle traffic violation event"""
        experiment_id = data.get('experiment_id')
        violation_data = data.get('violation_data', {})
        logger.warning(f"Traffic violation in experiment {experiment_id}: {violation_data}")
        # Record violation for analysis
    
    async def _handle_simulation_metrics(self, data: Dict[str, Any]):
        """Handle simulation metrics update"""
        experiment_id = data.get('experiment_id')
        metrics = data.get('metrics', {})
        logger.debug(f"Simulation metrics for {experiment_id}: {metrics}")
        # Store metrics for real-time monitoring
    
    async def _handle_ai_decision_made(self, data: Dict[str, Any]):
        """Handle AI decision made event"""
        experiment_id = data.get('experiment_id')
        decision_data = data.get('decision_data', {})
        logger.debug(f"AI decision made for {experiment_id}")
        # Forward decision to simulation if needed
    
    async def _handle_model_inference_complete(self, data: Dict[str, Any]):
        """Handle model inference completion"""
        experiment_id = data.get('experiment_id')
        inference_time = data.get('inference_time_ms', 0)
        logger.debug(f"Model inference completed for {experiment_id} in {inference_time}ms")
    
    async def _handle_ai_decision_error(self, data: Dict[str, Any]):
        """Handle AI decision error"""
        experiment_id = data.get('experiment_id')
        error_message = data.get('error_message', 'Unknown error')
        logger.error(f"AI decision error in experiment {experiment_id}: {error_message}")
        # Implement fallback decision logic
    
    async def _handle_metrics_calculated(self, data: Dict[str, Any]):
        """Handle metrics calculation completion"""
        experiment_id = data.get('experiment_id')
        metrics = data.get('metrics', {})
        logger.info(f"Metrics calculated for experiment {experiment_id}")
    
    async def _handle_performance_threshold(self, data: Dict[str, Any]):
        """Handle performance threshold reached"""
        experiment_id = data.get('experiment_id')
        threshold_type = data.get('threshold_type', 'unknown')
        logger.info(f"Performance threshold '{threshold_type}' reached for experiment {experiment_id}")
    
    async def _handle_service_health_check(self, data: Dict[str, Any]):
        """Handle service health check event"""
        service_name = data.get('service_name', 'unknown')
        health_status = data.get('health_status', 'unknown')
        logger.debug(f"Health check for {service_name}: {health_status}")
    
    async def _handle_resource_usage_alert(self, data: Dict[str, Any]):
        """Handle resource usage alert"""
        resource_type = data.get('resource_type', 'unknown')
        usage_percent = data.get('usage_percent', 0)
        logger.warning(f"Resource usage alert: {resource_type} at {usage_percent}%")
    
    # Publishing methods
    
    async def publish_experiment_event(
        self, 
        experiment_id: str, 
        event_subtype: str, 
        data: Dict[str, Any]
    ):
        """Publish experiment lifecycle event"""
        
        topic_path = self.publisher.topic_path(
            self.settings.pubsub_project_id,
            self.settings.experiment_lifecycle_topic
        )
        
        message_data = {
            "experiment_id": experiment_id,
            "timestamp": datetime.utcnow().isoformat(),
            **data
        }
        
        attributes = {
            "event_type": "experiment_lifecycle",
            "event_subtype": event_subtype,
            "source": "orchestrator"
        }
        
        await self._publish_message(topic_path, message_data, attributes)
    
    async def publish_coordination_event(
        self, 
        target_service: str, 
        action: str, 
        data: Dict[str, Any]
    ):
        """Publish coordination event to target service"""
        
        # Determine appropriate topic based on target service
        topic_name = self._get_service_topic(target_service)
        topic_path = self.publisher.topic_path(
            self.settings.pubsub_project_id,
            topic_name
        )
        
        message_data = {
            "target_service": target_service,
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            **data
        }
        
        attributes = {
            "event_type": "coordination",
            "target_service": target_service,
            "source": "orchestrator"
        }
        
        await self._publish_message(topic_path, message_data, attributes)
    
    async def _publish_message(
        self, 
        topic_path: str, 
        data: Dict[str, Any], 
        attributes: Dict[str, str]
    ):
        """Publish message to Pub/Sub topic"""
        
        try:
            message_json = json.dumps(data)
            message_bytes = message_json.encode('utf-8')
            
            # Publish message
            future = self.publisher.publish(topic_path, message_bytes, **attributes)
            message_id = future.result()
            
            logger.debug(f"Published message {message_id} to {topic_path}")
            
        except Exception as e:
            logger.error(f"Failed to publish message to {topic_path}: {str(e)}")
            raise
    
    def _get_service_topic(self, service_name: str) -> str:
        """Get appropriate topic for target service"""
        
        service_topics = {
            "carla-runner": self.settings.simulation_events_topic,
            "dreamerv3-service": self.settings.ai_decisions_topic,
            "reporter-service": self.settings.evaluation_events_topic
        }
        
        return service_topics.get(service_name, self.settings.experiment_lifecycle_topic)