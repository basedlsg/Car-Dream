"""
Health check and status reporting endpoints for DreamerV3 service
"""

import os
import time
import psutil
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ServiceMetrics:
    """Service performance metrics"""
    cpu_usage_percent: float
    memory_usage_mb: float
    memory_usage_percent: float
    disk_usage_percent: float
    uptime_seconds: float
    request_count: int
    error_count: int
    avg_response_time_ms: float


class HealthChecker:
    """
    Comprehensive health checker for DreamerV3 service
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.response_times = []
        self.max_response_times = 1000  # Keep last 1000 response times
        
    def get_basic_health(self, model_wrapper=None) -> Dict[str, Any]:
        """
        Get basic health status
        
        Args:
            model_wrapper: Optional model wrapper instance
            
        Returns:
            Basic health information
        """
        try:
            current_time = datetime.utcnow()
            uptime = time.time() - self.start_time
            
            health_status = {
                "status": "healthy",
                "timestamp": current_time.isoformat(),
                "uptime_seconds": uptime,
                "service_version": os.getenv("SERVICE_VERSION", "1.0.0"),
                "environment": os.getenv("ENVIRONMENT", "development")
            }
            
            # Add model status if available
            if model_wrapper:
                health_status.update({
                    "model_loaded": model_wrapper.is_loaded(),
                    "model_ready": model_wrapper.is_ready(),
                    "model_version": model_wrapper.get_version()
                })
                
                # Set status based on model readiness
                if not model_wrapper.is_ready():
                    health_status["status"] = "degraded"
            else:
                health_status.update({
                    "model_loaded": False,
                    "model_ready": False,
                    "status": "unhealthy"
                })
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_detailed_health(self, model_wrapper=None) -> Dict[str, Any]:
        """
        Get detailed health and performance metrics
        
        Args:
            model_wrapper: Optional model wrapper instance
            
        Returns:
            Detailed health information
        """
        try:
            basic_health = self.get_basic_health(model_wrapper)
            
            # Get system metrics
            metrics = self._get_system_metrics()
            
            # Get service metrics
            service_metrics = self._get_service_metrics()
            
            # Combine all information
            detailed_health = {
                **basic_health,
                "system_metrics": {
                    "cpu_usage_percent": metrics.cpu_usage_percent,
                    "memory_usage_mb": metrics.memory_usage_mb,
                    "memory_usage_percent": metrics.memory_usage_percent,
                    "disk_usage_percent": metrics.disk_usage_percent
                },
                "service_metrics": {
                    "request_count": service_metrics.request_count,
                    "error_count": service_metrics.error_count,
                    "error_rate_percent": self._calculate_error_rate(),
                    "avg_response_time_ms": service_metrics.avg_response_time_ms,
                    "uptime_seconds": service_metrics.uptime_seconds
                }
            }
            
            # Add model-specific metrics if available
            if model_wrapper and model_wrapper.is_loaded():
                detailed_health["model_metrics"] = {
                    "memory_usage": model_wrapper.get_memory_usage(),
                    "capabilities": model_wrapper.get_capabilities(),
                    "last_prediction_time": model_wrapper.get_last_prediction_time()
                }
            
            # Determine overall health status
            detailed_health["status"] = self._determine_overall_status(
                detailed_health, model_wrapper
            )
            
            return detailed_health
            
        except Exception as e:
            logger.error(f"Detailed health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _get_system_metrics(self) -> ServiceMetrics:
        """Get system performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_mb = memory.used / (1024 * 1024)
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Uptime
            uptime = time.time() - self.start_time
            
            return ServiceMetrics(
                cpu_usage_percent=cpu_percent,
                memory_usage_mb=memory_mb,
                memory_usage_percent=memory_percent,
                disk_usage_percent=disk_percent,
                uptime_seconds=uptime,
                request_count=self.request_count,
                error_count=self.error_count,
                avg_response_time_ms=self._calculate_avg_response_time()
            )
            
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return ServiceMetrics(0, 0, 0, 0, 0, 0, 0, 0)
    
    def _get_service_metrics(self) -> ServiceMetrics:
        """Get service-specific metrics"""
        return ServiceMetrics(
            cpu_usage_percent=0,  # Not used in service metrics
            memory_usage_mb=0,    # Not used in service metrics
            memory_usage_percent=0,  # Not used in service metrics
            disk_usage_percent=0,    # Not used in service metrics
            uptime_seconds=time.time() - self.start_time,
            request_count=self.request_count,
            error_count=self.error_count,
            avg_response_time_ms=self._calculate_avg_response_time()
        )
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def _calculate_error_rate(self) -> float:
        """Calculate error rate percentage"""
        if self.request_count == 0:
            return 0.0
        return (self.error_count / self.request_count) * 100
    
    def _determine_overall_status(self, health_data: Dict[str, Any], model_wrapper=None) -> str:
        """
        Determine overall health status based on various metrics
        
        Args:
            health_data: Health data dictionary
            model_wrapper: Model wrapper instance
            
        Returns:
            Overall status string
        """
        try:
            # Check model status
            if model_wrapper and not model_wrapper.is_ready():
                return "unhealthy"
            
            # Check system metrics
            system_metrics = health_data.get("system_metrics", {})
            
            # High CPU usage
            if system_metrics.get("cpu_usage_percent", 0) > 90:
                return "degraded"
            
            # High memory usage
            if system_metrics.get("memory_usage_percent", 0) > 90:
                return "degraded"
            
            # High disk usage
            if system_metrics.get("disk_usage_percent", 0) > 95:
                return "degraded"
            
            # High error rate
            service_metrics = health_data.get("service_metrics", {})
            if service_metrics.get("error_rate_percent", 0) > 10:
                return "degraded"
            
            # High response time
            if service_metrics.get("avg_response_time_ms", 0) > 5000:
                return "degraded"
            
            return "healthy"
            
        except Exception as e:
            logger.error(f"Failed to determine overall status: {e}")
            return "unknown"
    
    def record_request(self, response_time_ms: float, is_error: bool = False):
        """
        Record request metrics
        
        Args:
            response_time_ms: Response time in milliseconds
            is_error: Whether the request resulted in an error
        """
        try:
            self.request_count += 1
            
            if is_error:
                self.error_count += 1
            
            # Add response time
            self.response_times.append(response_time_ms)
            
            # Keep only recent response times
            if len(self.response_times) > self.max_response_times:
                self.response_times = self.response_times[-self.max_response_times:]
                
        except Exception as e:
            logger.error(f"Failed to record request metrics: {e}")
    
    def get_readiness_probe(self, model_wrapper=None) -> Dict[str, Any]:
        """
        Kubernetes readiness probe endpoint
        
        Args:
            model_wrapper: Model wrapper instance
            
        Returns:
            Readiness status
        """
        try:
            ready = True
            reasons = []
            
            # Check if model is ready
            if model_wrapper:
                if not model_wrapper.is_loaded():
                    ready = False
                    reasons.append("model_not_loaded")
                
                if not model_wrapper.is_ready():
                    ready = False
                    reasons.append("model_not_ready")
            else:
                ready = False
                reasons.append("model_wrapper_not_initialized")
            
            # Check system resources
            try:
                memory = psutil.virtual_memory()
                if memory.percent > 95:
                    ready = False
                    reasons.append("high_memory_usage")
            except:
                pass
            
            return {
                "ready": ready,
                "reasons": reasons,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Readiness probe failed: {e}")
            return {
                "ready": False,
                "reasons": ["probe_error"],
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_liveness_probe(self) -> Dict[str, Any]:
        """
        Kubernetes liveness probe endpoint
        
        Returns:
            Liveness status
        """
        try:
            # Simple liveness check - service is alive if it can respond
            return {
                "alive": True,
                "uptime_seconds": time.time() - self.start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Liveness probe failed: {e}")
            return {
                "alive": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global health checker instance
health_checker = HealthChecker()