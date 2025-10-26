"""
Database Manager
Handles experiment state persistence and data management
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, Column, String, DateTime, Text, Float, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Import shared schemas
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../shared'))
from schemas.experiment import ExperimentConfig, ExperimentResult, ExperimentStatus

logger = logging.getLogger(__name__)

Base = declarative_base()


class ExperimentRecord(Base):
    """Database model for experiment records"""
    __tablename__ = "experiments"
    
    experiment_id = Column(String(255), primary_key=True)
    name = Column(String(500))
    description = Column(Text)
    config_json = Column(JSON)
    status = Column(String(50))
    created_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    current_phase = Column(String(100))
    progress_percentage = Column(Float, default=0.0)
    metadata_json = Column(JSON)


class ExperimentMetrics(Base):
    """Database model for experiment metrics"""
    __tablename__ = "experiment_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(String(255))
    metric_name = Column(String(255))
    metric_value = Column(Float)
    timestamp = Column(DateTime)
    metadata_json = Column(JSON)


class ExperimentArtifacts(Base):
    """Database model for experiment artifacts"""
    __tablename__ = "experiment_artifacts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(String(255))
    artifact_type = Column(String(100))
    artifact_path = Column(String(1000))
    file_size = Column(Integer)
    created_at = Column(DateTime)
    metadata_json = Column(JSON)


class DatabaseManager:
    """Manages database operations for experiment data"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        self._healthy = True
    
    async def initialize(self):
        """Initialize database connection and create tables"""
        try:
            # Create engine
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_recycle=300
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # Create tables
            Base.metadata.create_all(bind=self.engine)
            
            logger.info("Database manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {str(e)}")
            self._healthy = False
            raise
    
    def is_healthy(self) -> bool:
        """Check if database manager is healthy"""
        return self._healthy and self.engine is not None
    
    async def store_experiment(self, config: ExperimentConfig, result: ExperimentResult):
        """Store experiment configuration and initial result"""
        
        try:
            session = self.SessionLocal()
            
            # Create experiment record
            experiment_record = ExperimentRecord(
                experiment_id=config.experiment_id,
                name=config.name,
                description=config.description,
                config_json=config.dict(),
                status=result.status.value,
                created_at=config.created_at,
                metadata_json=config.metadata
            )
            
            session.add(experiment_record)
            session.commit()
            session.close()
            
            logger.info(f"Stored experiment {config.experiment_id} in database")
            
        except SQLAlchemyError as e:
            logger.error(f"Database error storing experiment: {str(e)}")
            if session:
                session.rollback()
                session.close()
            raise
    
    async def get_experiment_config(self, experiment_id: str) -> Optional[ExperimentConfig]:
        """Get experiment configuration by ID"""
        
        try:
            session = self.SessionLocal()
            
            record = session.query(ExperimentRecord).filter(
                ExperimentRecord.experiment_id == experiment_id
            ).first()
            
            session.close()
            
            if record and record.config_json:
                return ExperimentConfig(**record.config_json)
            
            return None
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting experiment config: {str(e)}")
            if session:
                session.close()
            return None
    
    async def get_experiment_result(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Get experiment result by ID"""
        
        try:
            session = self.SessionLocal()
            
            record = session.query(ExperimentRecord).filter(
                ExperimentRecord.experiment_id == experiment_id
            ).first()
            
            session.close()
            
            if record:
                # Get metrics
                metrics = await self.get_experiment_metrics_dict(experiment_id)
                
                # Get artifacts
                artifacts = await self.get_experiment_artifacts_list(experiment_id)
                
                return ExperimentResult(
                    experiment_id=record.experiment_id,
                    status=ExperimentStatus(record.status),
                    started_at=record.started_at,
                    completed_at=record.completed_at,
                    metrics=metrics,
                    artifacts=artifacts,
                    error_message=record.error_message,
                    logs=[]  # TODO: Implement log storage
                )
            
            return None
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting experiment result: {str(e)}")
            if session:
                session.close()
            return None
    
    async def update_experiment_result(self, experiment_id: str, update_data: Dict[str, Any]):
        """Update experiment result"""
        
        try:
            session = self.SessionLocal()
            
            record = session.query(ExperimentRecord).filter(
                ExperimentRecord.experiment_id == experiment_id
            ).first()
            
            if record:
                for key, value in update_data.items():
                    if hasattr(record, key):
                        if key == "status" and isinstance(value, ExperimentStatus):
                            setattr(record, key, value.value)
                        else:
                            setattr(record, key, value)
                
                session.commit()
                logger.debug(f"Updated experiment {experiment_id} with {update_data}")
            
            session.close()
            
        except SQLAlchemyError as e:
            logger.error(f"Database error updating experiment result: {str(e)}")
            if session:
                session.rollback()
                session.close()
            raise
    
    async def update_experiment_phase(self, experiment_id: str, phase: str):
        """Update current experiment phase"""
        
        await self.update_experiment_result(experiment_id, {"current_phase": phase})
    
    async def update_experiment_progress(self, experiment_id: str, progress: float):
        """Update experiment progress percentage"""
        
        await self.update_experiment_result(experiment_id, {"progress_percentage": progress})
    
    async def get_experiment_progress(self, experiment_id: str) -> float:
        """Get experiment progress percentage"""
        
        try:
            session = self.SessionLocal()
            
            record = session.query(ExperimentRecord).filter(
                ExperimentRecord.experiment_id == experiment_id
            ).first()
            
            session.close()
            
            if record:
                return record.progress_percentage or 0.0
            
            return 0.0
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting experiment progress: {str(e)}")
            if session:
                session.close()
            return 0.0
    
    async def store_experiment_metrics(self, experiment_id: str, metrics: Dict[str, float]):
        """Store experiment metrics"""
        
        try:
            session = self.SessionLocal()
            
            timestamp = datetime.utcnow()
            
            for metric_name, metric_value in metrics.items():
                metric_record = ExperimentMetrics(
                    experiment_id=experiment_id,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    timestamp=timestamp
                )
                session.add(metric_record)
            
            session.commit()
            session.close()
            
            logger.debug(f"Stored {len(metrics)} metrics for experiment {experiment_id}")
            
        except SQLAlchemyError as e:
            logger.error(f"Database error storing experiment metrics: {str(e)}")
            if session:
                session.rollback()
                session.close()
            raise
    
    async def get_experiment_metrics_dict(self, experiment_id: str) -> Dict[str, float]:
        """Get experiment metrics as dictionary"""
        
        try:
            session = self.SessionLocal()
            
            metrics = session.query(ExperimentMetrics).filter(
                ExperimentMetrics.experiment_id == experiment_id
            ).all()
            
            session.close()
            
            # Return latest value for each metric
            metrics_dict = {}
            for metric in metrics:
                metrics_dict[metric.metric_name] = metric.metric_value
            
            return metrics_dict
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting experiment metrics: {str(e)}")
            if session:
                session.close()
            return {}
    
    async def store_experiment_artifact(self, experiment_id: str, artifact_info: Dict[str, Any]):
        """Store experiment artifact information"""
        
        try:
            session = self.SessionLocal()
            
            artifact_record = ExperimentArtifacts(
                experiment_id=experiment_id,
                artifact_type=artifact_info.get("type", "unknown"),
                artifact_path=artifact_info.get("path", ""),
                file_size=artifact_info.get("size", 0),
                created_at=datetime.utcnow(),
                metadata_json=artifact_info.get("metadata", {})
            )
            
            session.add(artifact_record)
            session.commit()
            session.close()
            
            logger.debug(f"Stored artifact for experiment {experiment_id}")
            
        except SQLAlchemyError as e:
            logger.error(f"Database error storing experiment artifact: {str(e)}")
            if session:
                session.rollback()
                session.close()
            raise
    
    async def get_experiment_artifacts_list(self, experiment_id: str) -> List[str]:
        """Get experiment artifacts as list of paths"""
        
        try:
            session = self.SessionLocal()
            
            artifacts = session.query(ExperimentArtifacts).filter(
                ExperimentArtifacts.experiment_id == experiment_id
            ).all()
            
            session.close()
            
            return [artifact.artifact_path for artifact in artifacts]
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting experiment artifacts: {str(e)}")
            if session:
                session.close()
            return []
    
    async def store_experiment_summary(self, experiment_id: str, summary: Dict[str, Any]):
        """Store experiment summary"""
        
        # Store summary as metadata update
        await self.update_experiment_result(
            experiment_id, 
            {"metadata_json": summary}
        )
    
    async def list_experiments(
        self, 
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ExperimentResult]:
        """List experiments with optional filtering"""
        
        try:
            session = self.SessionLocal()
            
            query = session.query(ExperimentRecord)
            
            if status:
                query = query.filter(ExperimentRecord.status == status)
            
            records = query.order_by(ExperimentRecord.created_at.desc()).offset(offset).limit(limit).all()
            
            session.close()
            
            # Convert to ExperimentResult objects
            results = []
            for record in records:
                metrics = await self.get_experiment_metrics_dict(record.experiment_id)
                artifacts = await self.get_experiment_artifacts_list(record.experiment_id)
                
                result = ExperimentResult(
                    experiment_id=record.experiment_id,
                    status=ExperimentStatus(record.status),
                    started_at=record.started_at,
                    completed_at=record.completed_at,
                    metrics=metrics,
                    artifacts=artifacts,
                    error_message=record.error_message,
                    logs=[]
                )
                results.append(result)
            
            return results
            
        except SQLAlchemyError as e:
            logger.error(f"Database error listing experiments: {str(e)}")
            if session:
                session.close()
            return []
    
    async def get_expired_experiments(self, cutoff_time: datetime) -> List[ExperimentResult]:
        """Get experiments older than cutoff time"""
        
        try:
            session = self.SessionLocal()
            
            records = session.query(ExperimentRecord).filter(
                ExperimentRecord.completed_at < cutoff_time
            ).all()
            
            session.close()
            
            # Convert to ExperimentResult objects
            results = []
            for record in records:
                result = ExperimentResult(
                    experiment_id=record.experiment_id,
                    status=ExperimentStatus(record.status),
                    started_at=record.started_at,
                    completed_at=record.completed_at,
                    metrics={},
                    artifacts=[],
                    error_message=record.error_message,
                    logs=[]
                )
                results.append(result)
            
            return results
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting expired experiments: {str(e)}")
            if session:
                session.close()
            return []
    
    async def archive_experiment(self, experiment_id: str):
        """Archive an experiment (placeholder for future implementation)"""
        
        # For now, just log the archival
        # In a real implementation, this might move data to cold storage
        logger.info(f"Archiving experiment {experiment_id}")
        
        # TODO: Implement actual archival logic