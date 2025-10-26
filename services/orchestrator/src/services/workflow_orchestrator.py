"""
Workflow Orchestrator
Handles complete experiment execution workflow with error handling and recovery
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum

# Import shared schemas
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../shared'))
from schemas.experiment import ExperimentConfig, ExperimentStatus

from config.settings import Settings
from services.service_client import ServiceClient
from services.pubsub_handler import PubSubHandler
from services.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class WorkflowPhase(str, Enum):
    """Experiment workflow phases"""
    INITIALIZATION = "initialization"
    CARLA_SETUP = "carla_setup"
    DREAMER_SETUP = "dreamer_setup"
    SIMULATION_EXECUTION = "simulation_execution"
    RESULT_PROCESSING = "result_processing"
    CLEANUP = "cleanup"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowState:
    """Represents the current state of an experiment workflow"""
    
    def __init__(self, experiment_id: str, config: ExperimentConfig):
        self.experiment_id = experiment_id
        self.config = config
        self.current_phase = WorkflowPhase.INITIALIZATION
        self.phase_start_time = datetime.utcnow()
        self.total_start_time = datetime.utcnow()
        self.carla_session_id: Optional[str] = None
        self.dreamer_session_id: Optional[str] = None
        self.error_count = 0
        self.retry_count = 0
        self.phase_data: Dict[str, Any] = {}
        self.metrics: Dict[str, float] = {}
        self.artifacts: List[str] = []
        self.is_cancelled = False


class WorkflowOrchestrator:
    """Orchestrates complete experiment workflows"""
    
    def __init__(
        self, 
        settings: Settings,
        service_client: ServiceClient,
        pubsub_handler: PubSubHandler,
        db_manager: DatabaseManager
    ):
        self.settings = settings
        self.service_client = service_client
        self.pubsub_handler = pubsub_handler
        self.db_manager = db_manager
        self.active_workflows: Dict[str, WorkflowState] = {}
        self._healthy = True
    
    def is_healthy(self) -> bool:
        """Check if workflow orchestrator is healthy"""
        return self._healthy
    
    async def execute_experiment_workflow(self, experiment_id: str, config: ExperimentConfig):
        """Execute complete experiment workflow"""
        
        # Create workflow state
        workflow_state = WorkflowState(experiment_id, config)
        self.active_workflows[experiment_id] = workflow_state
        
        try:
            logger.info(f"Starting experiment workflow for {experiment_id}")
            
            # Execute workflow phases
            await self._execute_initialization_phase(workflow_state)
            await self._execute_carla_setup_phase(workflow_state)
            await self._execute_dreamer_setup_phase(workflow_state)
            await self._execute_simulation_phase(workflow_state)
            await self._execute_result_processing_phase(workflow_state)
            await self._execute_cleanup_phase(workflow_state)
            
            # Mark as completed
            workflow_state.current_phase = WorkflowPhase.COMPLETED
            await self._update_workflow_phase(workflow_state)
            
            logger.info(f"Experiment workflow completed for {experiment_id}")
            
        except Exception as e:
            logger.error(f"Experiment workflow failed for {experiment_id}: {str(e)}")
            workflow_state.current_phase = WorkflowPhase.FAILED
            await self._handle_workflow_failure(workflow_state, str(e))
            
        finally:
            # Remove from active workflows
            if experiment_id in self.active_workflows:
                del self.active_workflows[experiment_id]
    
    async def _execute_initialization_phase(self, state: WorkflowState):
        """Execute initialization phase"""
        
        state.current_phase = WorkflowPhase.INITIALIZATION
        await self._update_workflow_phase(state)
        
        try:
            # Validate experiment configuration
            await self._validate_experiment_config(state.config)
            
            # Initialize workflow resources
            await self._initialize_workflow_resources(state)
            
            # Publish initialization event
            await self.pubsub_handler.publish_experiment_event(
                state.experiment_id,
                "workflow_phase_started",
                {"phase": WorkflowPhase.INITIALIZATION.value}
            )
            
            logger.info(f"Initialization phase completed for {state.experiment_id}")
            
        except Exception as e:
            await self._handle_phase_error(state, "initialization", e)
            raise
    
    async def _execute_carla_setup_phase(self, state: WorkflowState):
        """Execute CARLA setup phase"""
        
        state.current_phase = WorkflowPhase.CARLA_SETUP
        await self._update_workflow_phase(state)
        
        try:
            # Initialize CARLA simulation
            carla_result = await self.service_client.initialize_carla_simulation(
                state.config.carla_config.dict()
            )
            
            state.carla_session_id = carla_result.get("session_id")
            state.phase_data["carla_initialization"] = carla_result
            
            # Verify CARLA is ready
            await self._verify_carla_readiness(state)
            
            # Publish setup completion event
            await self.pubsub_handler.publish_experiment_event(
                state.experiment_id,
                "carla_setup_completed",
                {"session_id": state.carla_session_id}
            )
            
            logger.info(f"CARLA setup phase completed for {state.experiment_id}")
            
        except Exception as e:
            await self._handle_phase_error(state, "carla_setup", e)
            raise
    
    async def _execute_dreamer_setup_phase(self, state: WorkflowState):
        """Execute DreamerV3 setup phase"""
        
        state.current_phase = WorkflowPhase.DREAMER_SETUP
        await self._update_workflow_phase(state)
        
        try:
            # Initialize DreamerV3 model
            dreamer_result = await self.service_client.initialize_dreamer_model(
                state.config.dreamer_config.dict()
            )
            
            state.dreamer_session_id = dreamer_result.get("session_id")
            state.phase_data["dreamer_initialization"] = dreamer_result
            
            # Verify DreamerV3 is ready
            await self._verify_dreamer_readiness(state)
            
            # Publish setup completion event
            await self.pubsub_handler.publish_experiment_event(
                state.experiment_id,
                "dreamer_setup_completed",
                {"session_id": state.dreamer_session_id}
            )
            
            logger.info(f"DreamerV3 setup phase completed for {state.experiment_id}")
            
        except Exception as e:
            await self._handle_phase_error(state, "dreamer_setup", e)
            raise
    
    async def _execute_simulation_phase(self, state: WorkflowState):
        """Execute main simulation phase"""
        
        state.current_phase = WorkflowPhase.SIMULATION_EXECUTION
        await self._update_workflow_phase(state)
        
        try:
            # Start CARLA simulation
            await self.service_client.start_carla_simulation(state.carla_session_id)
            
            # Execute simulation loop
            simulation_results = await self._run_simulation_loop(state)
            
            state.phase_data["simulation_results"] = simulation_results
            state.metrics.update(simulation_results.get("metrics", {}))
            state.artifacts.extend(simulation_results.get("artifacts", []))
            
            # Publish simulation completion event
            await self.pubsub_handler.publish_experiment_event(
                state.experiment_id,
                "simulation_completed",
                {"results_summary": simulation_results.get("summary", {})}
            )
            
            logger.info(f"Simulation phase completed for {state.experiment_id}")
            
        except Exception as e:
            await self._handle_phase_error(state, "simulation_execution", e)
            raise
    
    async def _execute_result_processing_phase(self, state: WorkflowState):
        """Execute result processing phase"""
        
        state.current_phase = WorkflowPhase.RESULT_PROCESSING
        await self._update_workflow_phase(state)
        
        try:
            # Process simulation results
            processed_results = await self._process_simulation_results(state)
            
            # Store results in database
            await self.db_manager.store_experiment_metrics(
                state.experiment_id, 
                state.metrics
            )
            
            # Store artifacts
            for artifact in state.artifacts:
                await self.db_manager.store_experiment_artifact(
                    state.experiment_id,
                    {"path": artifact, "type": "simulation_output"}
                )
            
            # Generate and store summary
            summary = await self._generate_experiment_summary(state)
            await self.db_manager.store_experiment_summary(state.experiment_id, summary)
            
            # Submit results to reporter service (if available)
            await self.service_client.submit_experiment_results(
                state.experiment_id,
                processed_results
            )
            
            # Publish processing completion event
            await self.pubsub_handler.publish_experiment_event(
                state.experiment_id,
                "result_processing_completed",
                {"summary": summary}
            )
            
            logger.info(f"Result processing phase completed for {state.experiment_id}")
            
        except Exception as e:
            await self._handle_phase_error(state, "result_processing", e)
            raise
    
    async def _execute_cleanup_phase(self, state: WorkflowState):
        """Execute cleanup phase"""
        
        state.current_phase = WorkflowPhase.CLEANUP
        await self._update_workflow_phase(state)
        
        try:
            # Stop CARLA simulation
            if state.carla_session_id:
                await self.service_client.stop_carla_simulation(state.carla_session_id)
            
            # Release DreamerV3 resources
            if state.dreamer_session_id:
                await self.service_client.release_dreamer_session(state.dreamer_session_id)
            
            # Clean up temporary files and resources
            await self._cleanup_temporary_resources(state)
            
            # Publish cleanup completion event
            await self.pubsub_handler.publish_experiment_event(
                state.experiment_id,
                "cleanup_completed",
                {}
            )
            
            logger.info(f"Cleanup phase completed for {state.experiment_id}")
            
        except Exception as e:
            # Log cleanup errors but don't fail the workflow
            logger.warning(f"Cleanup phase had errors for {state.experiment_id}: {str(e)}")
    
    async def _run_simulation_loop(self, state: WorkflowState) -> Dict[str, Any]:
        """Run the main simulation loop"""
        
        simulation_results = {
            "metrics": {},
            "events": [],
            "artifacts": [],
            "summary": {}
        }
        
        simulation_time = state.config.carla_config.simulation_time
        start_time = datetime.utcnow()
        step_count = 0
        
        logger.info(f"Starting simulation loop for {simulation_time} seconds")
        
        while (datetime.utcnow() - start_time).seconds < simulation_time:
            # Check for cancellation
            if state.is_cancelled:
                logger.info(f"Simulation cancelled for {state.experiment_id}")
                break
            
            try:
                # Get current simulation state
                sim_state = await self.service_client.get_simulation_state(state.carla_session_id)
                
                # Send state to DreamerV3 for decision making
                ai_decision = await self.service_client.get_ai_decision(
                    state.dreamer_session_id,
                    sim_state
                )
                
                # Apply AI decision to simulation
                await self.service_client.apply_simulation_action(
                    state.carla_session_id,
                    ai_decision
                )
                
                # Collect metrics
                step_metrics = await self.service_client.get_simulation_metrics(state.carla_session_id)
                simulation_results["metrics"].update(step_metrics)
                
                # Update progress
                progress = ((datetime.utcnow() - start_time).seconds / simulation_time) * 100
                await self.db_manager.update_experiment_progress(state.experiment_id, progress)
                
                step_count += 1
                
                # Small delay to prevent overwhelming the services
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in simulation step {step_count}: {str(e)}")
                state.error_count += 1
                
                # If too many errors, abort simulation
                if state.error_count > 10:
                    raise Exception(f"Too many simulation errors ({state.error_count})")
                
                # Continue with next step
                continue
        
        # Calculate final metrics
        total_time = (datetime.utcnow() - start_time).total_seconds()
        simulation_results["summary"] = {
            "total_steps": step_count,
            "total_time_seconds": total_time,
            "steps_per_second": step_count / total_time if total_time > 0 else 0,
            "error_count": state.error_count
        }
        
        logger.info(f"Simulation loop completed: {step_count} steps in {total_time:.2f} seconds")
        
        return simulation_results
    
    async def _validate_experiment_config(self, config: ExperimentConfig):
        """Validate experiment configuration"""
        
        # Check required fields
        if not config.experiment_id:
            raise ValueError("Experiment ID is required")
        
        if not config.carla_config:
            raise ValueError("CARLA configuration is required")
        
        if not config.dreamer_config:
            raise ValueError("DreamerV3 configuration is required")
        
        # Validate CARLA config
        if config.carla_config.simulation_time <= 0:
            raise ValueError("Simulation time must be positive")
        
        # Validate DreamerV3 config
        if not config.dreamer_config.model_path:
            raise ValueError("DreamerV3 model path is required")
    
    async def _initialize_workflow_resources(self, state: WorkflowState):
        """Initialize workflow-specific resources"""
        
        # Create temporary directories if needed
        # Initialize logging for this experiment
        # Set up monitoring
        pass
    
    async def _verify_carla_readiness(self, state: WorkflowState):
        """Verify CARLA simulation is ready"""
        
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Check CARLA health
                health_status = await self.service_client.check_service_health("carla-runner")
                
                if health_status.get("status") == "healthy":
                    return True
                
                logger.warning(f"CARLA not ready, attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(retry_delay)
                
            except Exception as e:
                logger.warning(f"CARLA readiness check failed: {str(e)}")
                await asyncio.sleep(retry_delay)
        
        raise Exception("CARLA simulation failed to become ready")
    
    async def _verify_dreamer_readiness(self, state: WorkflowState):
        """Verify DreamerV3 model is ready"""
        
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Check DreamerV3 health
                health_status = await self.service_client.check_service_health("dreamerv3-service")
                
                if health_status.get("status") == "healthy":
                    return True
                
                logger.warning(f"DreamerV3 not ready, attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(retry_delay)
                
            except Exception as e:
                logger.warning(f"DreamerV3 readiness check failed: {str(e)}")
                await asyncio.sleep(retry_delay)
        
        raise Exception("DreamerV3 model failed to become ready")
    
    async def _process_simulation_results(self, state: WorkflowState) -> Dict[str, Any]:
        """Process simulation results"""
        
        simulation_data = state.phase_data.get("simulation_results", {})
        
        processed_results = {
            "experiment_id": state.experiment_id,
            "raw_metrics": simulation_data.get("metrics", {}),
            "processed_metrics": {},
            "performance_scores": {},
            "artifacts": state.artifacts,
            "processing_timestamp": datetime.utcnow().isoformat()
        }
        
        # Calculate derived metrics
        raw_metrics = simulation_data.get("metrics", {})
        
        # Example processing (customize based on actual metrics)
        if "collision_count" in raw_metrics and "total_distance" in raw_metrics:
            processed_results["performance_scores"]["safety_score"] = (
                1.0 - (raw_metrics["collision_count"] / max(raw_metrics["total_distance"], 1))
            )
        
        return processed_results
    
    async def _generate_experiment_summary(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate experiment summary"""
        
        total_duration = (datetime.utcnow() - state.total_start_time).total_seconds()
        
        summary = {
            "experiment_id": state.experiment_id,
            "total_duration_seconds": total_duration,
            "phases_completed": [phase.value for phase in WorkflowPhase if phase != WorkflowPhase.FAILED],
            "error_count": state.error_count,
            "retry_count": state.retry_count,
            "metrics_count": len(state.metrics),
            "artifacts_count": len(state.artifacts),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return summary
    
    async def _cleanup_temporary_resources(self, state: WorkflowState):
        """Clean up temporary resources"""
        
        # Clean up temporary files
        # Release memory resources
        # Close connections
        pass
    
    async def _update_workflow_phase(self, state: WorkflowState):
        """Update workflow phase in database"""
        
        await self.db_manager.update_experiment_phase(
            state.experiment_id,
            state.current_phase.value
        )
        
        state.phase_start_time = datetime.utcnow()
    
    async def _handle_phase_error(self, state: WorkflowState, phase: str, error: Exception):
        """Handle phase-specific errors"""
        
        state.error_count += 1
        error_message = f"Error in {phase} phase: {str(error)}"
        
        logger.error(f"Phase error for {state.experiment_id}: {error_message}")
        
        # Publish error event
        await self.pubsub_handler.publish_experiment_event(
            state.experiment_id,
            "workflow_phase_error",
            {
                "phase": phase,
                "error_message": error_message,
                "error_count": state.error_count
            }
        )
        
        # Attempt recovery if possible
        if state.retry_count < self.settings.max_retries:
            state.retry_count += 1
            logger.info(f"Attempting retry {state.retry_count} for {state.experiment_id}")
            
            # Add retry delay
            await asyncio.sleep(self.settings.retry_delay)
            
            # For some phases, we might be able to retry
            # This would need phase-specific retry logic
        
        # Update database with error
        await self.db_manager.update_experiment_result(
            state.experiment_id,
            {"error_message": error_message}
        )
    
    async def _handle_workflow_failure(self, state: WorkflowState, error_message: str):
        """Handle complete workflow failure"""
        
        logger.error(f"Workflow failed for {state.experiment_id}: {error_message}")
        
        # Update database
        await self.db_manager.update_experiment_result(
            state.experiment_id,
            {
                "status": ExperimentStatus.FAILED,
                "error_message": error_message,
                "completed_at": datetime.utcnow()
            }
        )
        
        # Publish failure event
        await self.pubsub_handler.publish_experiment_event(
            state.experiment_id,
            "workflow_failed",
            {"error_message": error_message}
        )
        
        # Attempt cleanup
        try:
            await self._execute_cleanup_phase(state)
        except Exception as cleanup_error:
            logger.error(f"Cleanup after failure also failed: {str(cleanup_error)}")
    
    async def cancel_workflow(self, experiment_id: str) -> bool:
        """Cancel a running workflow"""
        
        if experiment_id in self.active_workflows:
            workflow_state = self.active_workflows[experiment_id]
            workflow_state.is_cancelled = True
            
            logger.info(f"Workflow cancellation requested for {experiment_id}")
            
            # Publish cancellation event
            await self.pubsub_handler.publish_experiment_event(
                experiment_id,
                "workflow_cancelled",
                {"phase": workflow_state.current_phase.value}
            )
            
            return True
        
        return False
    
    def get_workflow_status(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get current workflow status"""
        
        if experiment_id in self.active_workflows:
            state = self.active_workflows[experiment_id]
            
            return {
                "experiment_id": experiment_id,
                "current_phase": state.current_phase.value,
                "phase_start_time": state.phase_start_time.isoformat(),
                "total_start_time": state.total_start_time.isoformat(),
                "error_count": state.error_count,
                "retry_count": state.retry_count,
                "is_cancelled": state.is_cancelled
            }
        
        return None