"""
Main reporter service
Orchestrates note generation, validation, metrics calculation, and storage
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import asyncio

from ..models.note_models import SimulationData, AIDecision, AutonomousNote, ValidationResult
from ..models.evaluation_models import ExperimentMetrics, EvaluationReport, GroundTruthData
from .note_generator import NoteGenerator
from .note_validator import NoteValidator
from .metrics_calculator import MetricsCalculator
from .storage_service import StorageService


class ReporterService:
    """Main service for autonomous driving experiment reporting"""
    
    def __init__(self, project_id: str, dataset_id: str = "cars_with_life", bucket_name: str = "cars-with-life-reports"):
        self.logger = logging.getLogger(__name__)
        
        # Initialize service components
        self.note_generator = NoteGenerator()
        self.note_validator = NoteValidator()
        self.metrics_calculator = MetricsCalculator()
        self.storage_service = StorageService(project_id, dataset_id, bucket_name)
        
        self.logger.info("Reporter service initialized")
    
    async def process_experiment_data(
        self,
        experiment_id: str,
        simulation_sequence: List[SimulationData],
        decision_sequence: List[AIDecision],
        ground_truth: Optional[List[GroundTruthData]] = None
    ) -> EvaluationReport:
        """
        Process complete experiment data and generate evaluation report
        
        Args:
            experiment_id: Experiment identifier
            simulation_sequence: List of simulation states
            decision_sequence: List of AI decisions
            ground_truth: Optional ground truth data for comparison
            
        Returns:
            Complete evaluation report
        """
        try:
            self.logger.info(f"Processing experiment data for {experiment_id}")
            
            # Step 1: Generate autonomous notes
            notes = self.note_generator.batch_generate_notes(
                simulation_sequence, decision_sequence, experiment_id
            )
            
            # Step 2: Validate notes
            validation_results = self.note_validator.batch_validate_notes(notes)
            
            # Step 3: Calculate metrics
            experiment_metrics = self.metrics_calculator.calculate_experiment_metrics(
                notes, validation_results, experiment_id
            )
            
            # Step 4: Generate evaluation report
            evaluation_report = self.metrics_calculator.generate_evaluation_report(
                experiment_id, notes, validation_results, ground_truth
            )
            
            # Step 5: Store data
            await self._store_experiment_data(notes, validation_results, experiment_metrics, evaluation_report)
            
            self.logger.info(f"Completed processing experiment {experiment_id}")
            return evaluation_report
            
        except Exception as e:
            self.logger.error(f"Error processing experiment data: {str(e)}")
            raise
    
    async def generate_single_note(
        self,
        simulation_data: SimulationData,
        ai_decision: AIDecision,
        experiment_id: str,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Generate and optionally validate a single autonomous note
        
        Args:
            simulation_data: Current simulation state
            ai_decision: AI decision data
            experiment_id: Experiment identifier
            validate: Whether to validate the note
            
        Returns:
            Dictionary with note and validation result
        """
        try:
            # Generate note
            note = self.note_generator.generate_note(simulation_data, ai_decision, experiment_id)
            
            result = {"note": note}
            
            # Validate if requested
            if validate:
                validation_result = self.note_validator.validate_note(note)
                result["validation"] = validation_result
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating single note: {str(e)}")
            raise
    
    async def calculate_experiment_performance(
        self,
        experiment_id: str,
        notes: List[AutonomousNote],
        validation_results: List[ValidationResult]
    ) -> ExperimentMetrics:
        """
        Calculate performance metrics for an experiment
        
        Args:
            experiment_id: Experiment identifier
            notes: List of autonomous notes
            validation_results: List of validation results
            
        Returns:
            Experiment performance metrics
        """
        try:
            metrics = self.metrics_calculator.calculate_experiment_metrics(
                notes, validation_results, experiment_id
            )
            
            # Store metrics
            await asyncio.get_event_loop().run_in_executor(
                None, self.storage_service.store_experiment_metrics, metrics
            )
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating experiment performance: {str(e)}")
            raise
    
    async def generate_daily_summary(self, experiment_ids: List[str], report_date: date) -> str:
        """
        Generate daily summary report for multiple experiments
        
        Args:
            experiment_ids: List of experiment IDs for the day
            report_date: Date for the report
            
        Returns:
            Cloud Storage path to the daily report
        """
        try:
            storage_path = await asyncio.get_event_loop().run_in_executor(
                None, self.storage_service.generate_daily_report, experiment_ids, report_date
            )
            
            self.logger.info(f"Generated daily summary for {len(experiment_ids)} experiments")
            return storage_path
            
        except Exception as e:
            self.logger.error(f"Error generating daily summary: {str(e)}")
            raise
    
    async def _store_experiment_data(
        self,
        notes: List[AutonomousNote],
        validation_results: List[ValidationResult],
        experiment_metrics: ExperimentMetrics,
        evaluation_report: EvaluationReport
    ):
        """Store all experiment data to BigQuery and Cloud Storage"""
        try:
            # Store in parallel for better performance
            tasks = [
                asyncio.get_event_loop().run_in_executor(
                    None, self.storage_service.store_autonomous_notes, notes, validation_results
                ),
                asyncio.get_event_loop().run_in_executor(
                    None, self.storage_service.store_experiment_metrics, experiment_metrics
                ),
                asyncio.get_event_loop().run_in_executor(
                    None, self.storage_service.store_evaluation_report, evaluation_report
                )
            ]
            
            await asyncio.gather(*tasks)
            self.logger.info("Successfully stored all experiment data")
            
        except Exception as e:
            self.logger.error(f"Error storing experiment data: {str(e)}")
            raise
    
    def get_experiment_summary(self, experiment_id: str) -> Dict[str, Any]:
        """
        Get summary statistics for an experiment
        
        Args:
            experiment_id: Experiment identifier
            
        Returns:
            Dictionary with experiment summary
        """
        try:
            # This would typically query BigQuery for stored data
            # For now, return a placeholder structure
            return {
                "experiment_id": experiment_id,
                "status": "completed",
                "summary": "Experiment summary would be retrieved from BigQuery"
            }
            
        except Exception as e:
            self.logger.error(f"Error getting experiment summary: {str(e)}")
            raise
    
    def validate_note_format(self, note_text: str) -> bool:
        """
        Validate that a note follows the required format
        
        Args:
            note_text: Note text to validate
            
        Returns:
            True if format is valid
        """
        try:
            # Check for required format: "At [place], did [action] to reach [destination]"
            import re
            pattern = r"^At .+, did .+ to reach .+$"
            return bool(re.match(pattern, note_text))
            
        except Exception as e:
            self.logger.error(f"Error validating note format: {str(e)}")
            return False