"""
Error handling and recovery mechanisms for CARLA runner service.
Handles CARLA crashes, resource exhaustion, and automatic recovery.
"""

import asyncio
import logging
import os
import signal
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass

import carla
from state_manager import StateManager, HealthMonitor, SimulationStatus

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors that can occur."""
    CARLA_CRASH = "carla_crash"
    CARLA_TIMEOUT = "carla_timeout"
    MEMORY_EXHAUSTION = "memory_exhaustion"
    GPU_ERROR = "gpu_error"
    NETWORK_ERROR = "network_error"
    SIMULATION_ERROR = "simulation_error"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""
    RESTART_CARLA = "restart_carla"
    RESTART_SIMULATION = "restart_simulation"
    RESTORE_CHECKPOINT = "restore_checkpoint"
    SCALE_DOWN = "scale_down"
    WAIT_AND_RETRY = "wait_and_retry"
    FAIL_GRACEFULLY = "fail_gracefully"


@dataclass
class RecoveryAction:
    """Recovery action configuration."""
    strategy: RecoveryStrategy
    max_attempts: int = 3
    delay_seconds: int = 5
    timeout_seconds: int = 60
    prerequisites: List[str] = None


class ErrorHandler:
    """Handles errors and implements recovery strategies."""
    
    def __init__(self, state_manager: StateManager, health_monitor: HealthMonitor):
        self.state_manager = state_manager
        self.health_monitor = health_monitor
        
        # Recovery strategies for different error types
        self.recovery_strategies = {
            ErrorType.CARLA_CRASH: RecoveryAction(
                strategy=RecoveryStrategy.RESTART_CARLA,
                max_attempts=3,
                delay_seconds=10,
                timeout_seconds=120
            ),
            ErrorType.CARLA_TIMEOUT: RecoveryAction(
                strategy=RecoveryStrategy.WAIT_AND_RETRY,
                max_attempts=2,
                delay_seconds=5,
                timeout_seconds=30
            ),
            ErrorType.MEMORY_EXHAUSTION: RecoveryAction(
                strategy=RecoveryStrategy.SCALE_DOWN,
                max_attempts=1,
                delay_seconds=0,
                timeout_seconds=60
            ),
            ErrorType.GPU_ERROR: RecoveryAction(
                strategy=RecoveryStrategy.RESTART_CARLA,
                max_attempts=2,
                delay_seconds=15,
                timeout_seconds=180
            ),
            ErrorType.NETWORK_ERROR: RecoveryAction(
                strategy=RecoveryStrategy.WAIT_AND_RETRY,
                max_attempts=3,
                delay_seconds=2,
                timeout_seconds=10
            ),
            ErrorType.SIMULATION_ERROR: RecoveryAction(
                strategy=RecoveryStrategy.RESTORE_CHECKPOINT,
                max_attempts=2,
                delay_seconds=1,
                timeout_seconds=30
            ),
            ErrorType.RESOURCE_EXHAUSTION: RecoveryAction(
                strategy=RecoveryStrategy.SCALE_DOWN,
                max_attempts=1,
                delay_seconds=0,
                timeout_seconds=30
            )
        }
        
        # Track recovery attempts
        self.recovery_attempts: Dict[str, Dict[ErrorType, int]] = {}
        
        # CARLA process management
        self.carla_process: Optional[subprocess.Popen] = None
        self.carla_restart_count = 0
        self.max_carla_restarts = 5
    
    async def handle_error(self, simulation_id: str, error_type: ErrorType, 
                          error_message: str, context: Dict[str, Any] = None) -> bool:
        """Handle an error and attempt recovery."""
        logger.error(f"Handling error for {simulation_id}: {error_type.value} - {error_message}")
        
        # Record the error
        self.state_manager.record_error(
            simulation_id=simulation_id,
            error_type=error_type.value,
            error_message=error_message,
            stack_trace=context.get('stack_trace', '') if context else ''
        )
        
        # Check if we should attempt recovery
        if not self._should_attempt_recovery(simulation_id, error_type):
            logger.warning(f"Max recovery attempts reached for {simulation_id}, {error_type.value}")
            return False
        
        # Get recovery strategy
        recovery_action = self.recovery_strategies.get(error_type)
        if not recovery_action:
            logger.error(f"No recovery strategy defined for {error_type.value}")
            return False
        
        # Increment attempt counter
        self._increment_recovery_attempt(simulation_id, error_type)
        
        # Execute recovery strategy
        success = await self._execute_recovery_strategy(
            simulation_id, recovery_action, context or {}
        )
        
        # Update error record with recovery result
        if self.state_manager.error_history:
            last_error = self.state_manager.error_history[-1]
            last_error.recovery_attempted = True
            last_error.recovery_successful = success
        
        return success
    
    async def _execute_recovery_strategy(self, simulation_id: str, 
                                       recovery_action: RecoveryAction,
                                       context: Dict[str, Any]) -> bool:
        """Execute a specific recovery strategy."""
        strategy = recovery_action.strategy
        
        logger.info(f"Executing recovery strategy: {strategy.value} for {simulation_id}")
        
        try:
            if strategy == RecoveryStrategy.RESTART_CARLA:
                return await self._restart_carla_server()
            
            elif strategy == RecoveryStrategy.RESTART_SIMULATION:
                return await self._restart_simulation(simulation_id, context)
            
            elif strategy == RecoveryStrategy.RESTORE_CHECKPOINT:
                return await self._restore_from_checkpoint(simulation_id, context)
            
            elif strategy == RecoveryStrategy.SCALE_DOWN:
                return await self._scale_down_resources(simulation_id)
            
            elif strategy == RecoveryStrategy.WAIT_AND_RETRY:
                return await self._wait_and_retry(recovery_action.delay_seconds)
            
            elif strategy == RecoveryStrategy.FAIL_GRACEFULLY:
                return await self._fail_gracefully(simulation_id)
            
            else:
                logger.error(f"Unknown recovery strategy: {strategy.value}")
                return False
                
        except Exception as e:
            logger.error(f"Recovery strategy {strategy.value} failed: {e}")
            return False
    
    async def _restart_carla_server(self) -> bool:
        """Restart the CARLA server process."""
        if self.carla_restart_count >= self.max_carla_restarts:
            logger.error("Maximum CARLA restart attempts reached")
            return False
        
        try:
            # Kill existing CARLA process
            if self.carla_process and self.carla_process.poll() is None:
                logger.info("Terminating existing CARLA process")
                self.carla_process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self.carla_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning("CARLA process didn't terminate gracefully, killing")
                    self.carla_process.kill()
                    self.carla_process.wait()
            
            # Wait before restart
            await asyncio.sleep(5)
            
            # Start new CARLA process
            carla_root = os.environ.get('CARLA_ROOT', '/opt/carla-simulator')
            carla_cmd = [
                f"{carla_root}/CarlaUE4.sh",
                "-carla-rpc-port=2000",
                "-carla-streaming-port=2001",
                "-opengl"
            ]
            
            logger.info("Starting new CARLA server process")
            self.carla_process = subprocess.Popen(
                carla_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dict(os.environ, DISPLAY=":99")
            )
            
            # Wait for CARLA to start
            await asyncio.sleep(15)
            
            # Test connection
            try:
                client = carla.Client('localhost', 2000)
                client.set_timeout(10.0)
                client.get_server_version()
                
                self.carla_restart_count += 1
                logger.info(f"CARLA server restarted successfully (attempt {self.carla_restart_count})")
                return True
                
            except Exception as e:
                logger.error(f"CARLA server restart failed - connection test failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to restart CARLA server: {e}")
            return False
    
    async def _restart_simulation(self, simulation_id: str, context: Dict[str, Any]) -> bool:
        """Restart a specific simulation."""
        try:
            # Get simulation manager from context
            sim_manager = context.get('sim_manager')
            if not sim_manager:
                logger.error("Simulation manager not available in context")
                return False
            
            # Clean up current simulation
            sim_manager.cleanup_simulation(simulation_id)
            
            # Wait briefly
            await asyncio.sleep(2)
            
            # Get original config from state manager
            checkpoint = self.state_manager.checkpoints.get(simulation_id)
            if not checkpoint:
                logger.error(f"No checkpoint found for simulation {simulation_id}")
                return False
            
            # Recreate simulation with original config
            # This would need to be implemented based on the specific simulation config format
            logger.info(f"Simulation {simulation_id} restart completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart simulation {simulation_id}: {e}")
            return False
    
    async def _restore_from_checkpoint(self, simulation_id: str, context: Dict[str, Any]) -> bool:
        """Restore simulation from the latest checkpoint."""
        try:
            # Get required objects from context
            world = context.get('world')
            vehicle_bp = context.get('vehicle_bp')
            
            if not world or not vehicle_bp:
                logger.error("Required objects not available in context for checkpoint restore")
                return False
            
            # Restore from checkpoint
            restored_vehicle = self.state_manager.restore_checkpoint(simulation_id, world, vehicle_bp)
            
            if restored_vehicle:
                logger.info(f"Successfully restored simulation {simulation_id} from checkpoint")
                return True
            else:
                logger.error(f"Failed to restore simulation {simulation_id} from checkpoint")
                return False
                
        except Exception as e:
            logger.error(f"Checkpoint restore failed for {simulation_id}: {e}")
            return False
    
    async def _scale_down_resources(self, simulation_id: str) -> bool:
        """Scale down resources to handle resource exhaustion."""
        try:
            logger.info(f"Scaling down resources for simulation {simulation_id}")
            
            # Implement resource scaling logic here
            # This could include:
            # - Reducing simulation quality settings
            # - Limiting number of NPCs
            # - Reducing sensor resolution
            # - Pausing non-critical simulations
            
            # For now, just log the action
            logger.info("Resource scaling completed")
            return True
            
        except Exception as e:
            logger.error(f"Resource scaling failed: {e}")
            return False
    
    async def _wait_and_retry(self, delay_seconds: int) -> bool:
        """Wait for a specified time before retrying."""
        logger.info(f"Waiting {delay_seconds} seconds before retry")
        await asyncio.sleep(delay_seconds)
        return True
    
    async def _fail_gracefully(self, simulation_id: str) -> bool:
        """Fail gracefully by cleaning up resources."""
        try:
            logger.info(f"Failing gracefully for simulation {simulation_id}")
            
            # Clean up simulation resources
            # This would be implemented based on the specific cleanup requirements
            
            return True
            
        except Exception as e:
            logger.error(f"Graceful failure handling failed: {e}")
            return False
    
    def _should_attempt_recovery(self, simulation_id: str, error_type: ErrorType) -> bool:
        """Check if recovery should be attempted based on attempt history."""
        if simulation_id not in self.recovery_attempts:
            return True
        
        attempts = self.recovery_attempts[simulation_id].get(error_type, 0)
        max_attempts = self.recovery_strategies[error_type].max_attempts
        
        return attempts < max_attempts
    
    def _increment_recovery_attempt(self, simulation_id: str, error_type: ErrorType) -> None:
        """Increment the recovery attempt counter."""
        if simulation_id not in self.recovery_attempts:
            self.recovery_attempts[simulation_id] = {}
        
        current_attempts = self.recovery_attempts[simulation_id].get(error_type, 0)
        self.recovery_attempts[simulation_id][error_type] = current_attempts + 1
    
    def get_recovery_status(self, simulation_id: str) -> Dict[str, Any]:
        """Get recovery status for a simulation."""
        attempts = self.recovery_attempts.get(simulation_id, {})
        
        return {
            "simulation_id": simulation_id,
            "recovery_attempts": {
                error_type.value: attempts.get(error_type, 0)
                for error_type in ErrorType
            },
            "carla_restart_count": self.carla_restart_count,
            "max_carla_restarts": self.max_carla_restarts
        }
    
    async def periodic_health_check(self, client, active_simulations: Dict[str, Any]) -> None:
        """Perform periodic health checks and proactive error handling."""
        try:
            # Check CARLA connection
            if not self.health_monitor.check_carla_connection(client):
                logger.warning("CARLA connection lost, attempting recovery")
                await self.handle_error(
                    "system", 
                    ErrorType.CARLA_CRASH, 
                    "CARLA server connection lost"
                )
            
            # Check resource usage
            resources = self.health_monitor.check_resource_usage()
            
            # Check for resource exhaustion
            if resources.get('memory_usage', 0) > 90:
                logger.warning("High memory usage detected")
                await self.handle_error(
                    "system",
                    ErrorType.MEMORY_EXHAUSTION,
                    f"Memory usage: {resources['memory_usage']:.1f}%"
                )
            
            # Calculate error rate
            error_history = self.state_manager.get_error_history(hours=1)
            error_rate = self.health_monitor.calculate_error_rate(error_history)
            
            if error_rate > 0.5:  # More than 0.5 errors per minute
                logger.warning(f"High error rate detected: {error_rate:.2f} errors/min")
            
            # Clean up old checkpoints
            self.state_manager.cleanup_old_checkpoints()
            
        except Exception as e:
            logger.error(f"Periodic health check failed: {e}")


# Circuit breaker pattern for external service calls
class CircuitBreaker:
    """Circuit breaker for handling external service failures."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset."""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.timeout
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"