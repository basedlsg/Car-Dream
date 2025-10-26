"
""
Experiment Manager Service
Handles experiment lifecycle management, coordination, and state tracking
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor

# Import shared schemas
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../shared'))
from schemas.experiment import ExperimentConfig, ExperimentResult, ExperimentStatus

from config.settings import Settings
from services.database_manager import DatabaseManager
from services.service_client import ServiceClient

logger = logging.getLogger(__name__)


class ExperimentManager:
    """Manages experiment lifecycle and coordination"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.active_experiments: Dict[str, asyncio.Task] = {}
        self.executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_experiments)
        self._healthy = True
        self.workflow_orchestrator = None  # Will be set by main.py
        
    async def initialize(self):
        """Initialize the experiment manager"""
        try:
            if not self.workflow_orchestrator:
                raise ValueError("Workflow orchestrator not set")
            logger.info("Experiment manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize experiment manager: {str(e)}")
            self._healthy = False
            raise
    
    def is_healthy(self) -> bool:
        """Check if the experiment manager is healthy"""
        return self._healthy and self.workflow_orchestrator is not None
    
    async def create_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """Create a new experiment"""
        try:
            # Generate unique experiment ID if not provided
            if not config.experiment_id:
                config.experiment_id = str(uuid.uuid4())
            
            # Create experiment result record
            result = ExperimentResult(
                experiment_id=config.experiment_id,
                status=ExperimentStatus.PENDING,
                created_at=datetime.utcnow()
            )
            
            # Store in database through workflow orchestrator
            await self.workflow_orchestrator.db_manager.store_experiment(config, result)
            
            logger.info(f"Created experiment {config.experiment_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create experiment: {str(e)}")
            raise
    
    async def execute_experiment(self, experiment_id: str) -> None:
        """Execute an experiment workflow"""
        try:
            # Get experiment configuration
            config = await self.workflow_orchestrator.db_manager.get_experiment_config(experiment_id)
            if not config:
                raise ValueError(f"Experiment {experiment_id} not found")
            
            # Update status to running
            await self.update_experiment_status(experiment_id, ExperimentStatus.RUNNING)
            
            # Execute experiment using workflow orchestrator
            await self.workflow_orchestrator.execute_experiment_workflow(experiment_id, config)
            
        except Exception as e:
            logger.error(f"Experiment {experiment_id} failed: {str(e)}")
            await self.update_experiment_status(
                experiment_id, 
                ExperimentStatus.FAILED,
                error_message=str(e)
            )
        finally:
            # Remove from active experiments
            if experiment_id in self.active_experiments:
                del self.active_experiments[experiment_id]
    

    
    async def update_experiment_status(
        self, 
        experiment_id: str, 
        status: ExperimentStatus,
        error_message: Optional[str] = None
    ):
        """Update experiment status"""
        
        update_data = {"status": status}
        
        if status == ExperimentStatus.RUNNING:
            update_data["started_at"] = datetime.utcnow()
        elif status in [ExperimentStatus.COMPLETED, ExperimentStatus.FAILED, ExperimentStatus.CANCELLED]:
            update_data["completed_at"] = datetime.utcnow()
        
        if error_message:
            update_data["error_message"] = error_message
        
        await self.workflow_orchestrator.db_manager.update_experiment_result(experiment_id, update_data)
    
    async def update_experiment_progress(self, experiment_id: str, progress: float):
        """Update experiment progress percentage"""
        await self.workflow_orchestrator.db_manager.update_experiment_progress(experiment_id, progress)
    
    async def get_experiment_status(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Get current experiment status"""
        return await self.workflow_orchestrator.db_manager.get_experiment_result(experiment_id)
    
    async def get_experiment_progress(self, experiment_id: str) -> float:
        """Get experiment progress percentage"""
        return await self.workflow_orchestrator.db_manager.get_experiment_progress(experiment_id)
    
    async def stop_experiment(self, experiment_id: str) -> bool:
        """Stop a running experiment"""
        
        # Try to cancel through workflow orchestrator first
        workflow_cancelled = await self.workflow_orchestrator.cancel_workflow(experiment_id)
        
        if experiment_id in self.active_experiments:
            # Cancel the experiment task
            task = self.active_experiments[experiment_id]
            task.cancel()
            
            # Update status
            await self.update_experiment_status(experiment_id, ExperimentStatus.CANCELLED)
            
            logger.info(f"Stopped experiment {experiment_id}")
            return True
        
        return workflow_cancelled
    
    async def list_experiments(
        self, 
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ExperimentResult]:
        """List experiments with optional filtering"""
        return await self.workflow_orchestrator.db_manager.list_experiments(status, limit, offset)
    
    async def cleanup_expired_experiments(self):
        """Clean up expired experiments"""
        
        try:
            # Get experiments older than cleanup interval
            cutoff_time = datetime.utcnow() - timedelta(seconds=self.settings.experiment_cleanup_interval)
            expired_experiments = await self.workflow_orchestrator.db_manager.get_expired_experiments(cutoff_time)
            
            for experiment in expired_experiments:
                if experiment.status in [ExperimentStatus.COMPLETED, ExperimentStatus.FAILED]:
                    await self.workflow_orchestrator.db_manager.archive_experiment(experiment.experiment_id)
                    logger.info(f"Archived expired experiment {experiment.experiment_id}")
            
        except Exception as e:
            logger.error(f"Error during experiment cleanup: {str(e)}")