"""
Service Client
Handles HTTP communication with CARLA Runner and DreamerV3 Service
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import aiohttp
import json

from config.settings import Settings

logger = logging.getLogger(__name__)


class ServiceClient:
    """Client for communicating with other services"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session: Optional[aiohttp.ClientSession] = None
        self._healthy = True
        
        # Service endpoints
        self.carla_runner_url = settings.carla_runner_url
        self.dreamerv3_service_url = settings.dreamerv3_service_url
        self.reporter_service_url = settings.reporter_service_url
    
    async def initialize(self):
        """Initialize the service client"""
        try:
            # Create aiohttp session with timeout
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Verify service connectivity
            await self._verify_service_connectivity()
            
            logger.info("Service client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize service client: {str(e)}")
            self._healthy = False
            raise
    
    async def close(self):
        """Close the service client"""
        if self.session:
            await self.session.close()
    
    def is_healthy(self) -> bool:
        """Check if the service client is healthy"""
        return self._healthy and self.session is not None
    
    async def _verify_service_connectivity(self):
        """Verify connectivity to all services"""
        
        services = {
            "carla-runner": self.carla_runner_url,
            "dreamerv3-service": self.dreamerv3_service_url
        }
        
        for service_name, url in services.items():
            if url:  # Only check if URL is configured
                try:
                    await self._health_check(url)
                    logger.info(f"Successfully connected to {service_name}")
                except Exception as e:
                    logger.warning(f"Could not connect to {service_name}: {str(e)}")
    
    async def _health_check(self, base_url: str) -> bool:
        """Perform health check on a service"""
        
        try:
            async with self.session.get(f"{base_url}/health") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Health check failed for {base_url}: {str(e)}")
            return False
    
    # CARLA Runner Service Methods
    
    async def initialize_carla_simulation(self, carla_config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize CARLA simulation"""
        
        try:
            url = f"{self.carla_runner_url}/simulation/initialize"
            
            payload = {
                "config": carla_config,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"CARLA simulation initialized: {result.get('session_id')}")
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to initialize CARLA simulation: {error_text}")
                    
        except Exception as e:
            logger.error(f"Error initializing CARLA simulation: {str(e)}")
            raise
    
    async def start_carla_simulation(self, session_id: str) -> bool:
        """Start CARLA simulation"""
        
        try:
            url = f"{self.carla_runner_url}/simulation/{session_id}/start"
            
            async with self.session.post(url) as response:
                if response.status == 200:
                    logger.info(f"CARLA simulation {session_id} started")
                    return True
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to start CARLA simulation: {error_text}")
                    
        except Exception as e:
            logger.error(f"Error starting CARLA simulation: {str(e)}")
            raise
    
    async def stop_carla_simulation(self, session_id: str) -> bool:
        """Stop CARLA simulation"""
        
        try:
            url = f"{self.carla_runner_url}/simulation/{session_id}/stop"
            
            async with self.session.post(url) as response:
                if response.status == 200:
                    logger.info(f"CARLA simulation {session_id} stopped")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to stop CARLA simulation: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error stopping CARLA simulation: {str(e)}")
            return False
    
    async def get_simulation_state(self, session_id: str) -> Dict[str, Any]:
        """Get current simulation state"""
        
        try:
            url = f"{self.carla_runner_url}/simulation/{session_id}/state"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    state = await response.json()
                    return state
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to get simulation state: {error_text}")
                    
        except Exception as e:
            logger.error(f"Error getting simulation state: {str(e)}")
            raise
    
    async def apply_simulation_action(self, session_id: str, action: Dict[str, Any]) -> bool:
        """Apply action to simulation"""
        
        try:
            url = f"{self.carla_runner_url}/simulation/{session_id}/action"
            
            payload = {
                "action": action,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to apply simulation action: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error applying simulation action: {str(e)}")
            return False
    
    async def get_simulation_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get simulation metrics"""
        
        try:
            url = f"{self.carla_runner_url}/simulation/{session_id}/metrics"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    metrics = await response.json()
                    return metrics
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to get simulation metrics: {error_text}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error getting simulation metrics: {str(e)}")
            return {}
    
    # DreamerV3 Service Methods
    
    async def initialize_dreamer_model(self, dreamer_config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize DreamerV3 model"""
        
        try:
            url = f"{self.dreamerv3_service_url}/model/initialize"
            
            payload = {
                "config": dreamer_config,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"DreamerV3 model initialized: {result.get('session_id')}")
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to initialize DreamerV3 model: {error_text}")
                    
        except Exception as e:
            logger.error(f"Error initializing DreamerV3 model: {str(e)}")
            raise
    
    async def get_ai_decision(self, session_id: str, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI decision from DreamerV3 model"""
        
        try:
            url = f"{self.dreamerv3_service_url}/model/{session_id}/predict"
            
            payload = {
                "state_data": state_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    decision = await response.json()
                    return decision
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to get AI decision: {error_text}")
                    
        except Exception as e:
            logger.error(f"Error getting AI decision: {str(e)}")
            raise
    
    async def release_dreamer_session(self, session_id: str) -> bool:
        """Release DreamerV3 session resources"""
        
        try:
            url = f"{self.dreamerv3_service_url}/model/{session_id}/release"
            
            async with self.session.post(url) as response:
                if response.status == 200:
                    logger.info(f"DreamerV3 session {session_id} released")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to release DreamerV3 session: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error releasing DreamerV3 session: {str(e)}")
            return False
    
    # Reporter Service Methods (if available)
    
    async def submit_experiment_results(self, experiment_id: str, results: Dict[str, Any]) -> bool:
        """Submit experiment results to reporter service"""
        
        if not self.reporter_service_url:
            logger.info("Reporter service not configured, skipping result submission")
            return True
        
        try:
            url = f"{self.reporter_service_url}/results/submit"
            
            payload = {
                "experiment_id": experiment_id,
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Experiment results submitted for {experiment_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to submit experiment results: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error submitting experiment results: {str(e)}")
            return False
    
    # Generic service communication methods
    
    async def send_service_command(
        self, 
        service_url: str, 
        endpoint: str, 
        method: str = "POST",
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send generic command to a service"""
        
        try:
            url = f"{service_url}/{endpoint.lstrip('/')}"
            
            if method.upper() == "GET":
                async with self.session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        raise Exception(f"Service command failed: {error_text}")
            
            elif method.upper() == "POST":
                async with self.session.post(url, json=payload) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        raise Exception(f"Service command failed: {error_text}")
            
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
        except Exception as e:
            logger.error(f"Error sending service command: {str(e)}")
            raise
    
    async def check_service_health(self, service_name: str) -> Dict[str, Any]:
        """Check health of a specific service"""
        
        service_urls = {
            "carla-runner": self.carla_runner_url,
            "dreamerv3-service": self.dreamerv3_service_url,
            "reporter-service": self.reporter_service_url
        }
        
        service_url = service_urls.get(service_name)
        if not service_url:
            return {"status": "unknown", "error": "Service URL not configured"}
        
        try:
            start_time = datetime.utcnow()
            
            async with self.session.get(f"{service_url}/health") as response:
                end_time = datetime.utcnow()
                response_time = (end_time - start_time).total_seconds() * 1000
                
                if response.status == 200:
                    health_data = await response.json()
                    return {
                        "status": "healthy",
                        "response_time_ms": response_time,
                        "details": health_data
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "response_time_ms": response_time,
                        "error": f"HTTP {response.status}"
                    }
                    
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }