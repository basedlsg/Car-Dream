"""
Evaluation metrics calculation service
Calculates accuracy metrics and performance scores for autonomous notes
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid
import statistics
from difflib import SequenceMatcher

from ..models.note_models import AutonomousNote, ValidationResult
from ..models.evaluation_models import (
    ExperimentMetrics, EvaluationMetric, MetricType, GroundTruthData,
    ComparisonResult, EvaluationReport
)


class MetricsCalculator:
    """Calculates evaluation metrics for autonomous driving notes"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def calculate_experiment_metrics(
        self, 
        notes: List[AutonomousNote],
        validation_results: List[ValidationResult],
        experiment_id: str
    ) -> ExperimentMetrics:
        """
        Calculate comprehensive metrics for an experiment
        
        Args:
            notes: List of generated autonomous notes
            validation_results: List of validation results
            experiment_id: Experiment identifier
            
        Returns:
            Complete experiment metrics
        """
        try:
            if len(notes) != len(validation_results):
                raise ValueError("Notes and validation results must have same length")
            
            total_notes = len(notes)
            valid_notes = sum(1 for result in validation_results if result.is_valid)
            
            # Calculate individual accuracy metrics
            location_accuracy = self._calculate_location_accuracy(validation_results)
            action_accuracy = self._calculate_action_accuracy(validation_results)
            destination_accuracy = self._calculate_destination_accuracy(validation_results)
            
            # Calculate validation success rate
            validation_success_rate = valid_notes / total_notes if total_notes > 0 else 0.0
            
            # Calculate average confidence
            average_confidence = statistics.mean([note.confidence for note in notes]) if notes else 0.0
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(
                location_accuracy, action_accuracy, destination_accuracy, 
                validation_success_rate, average_confidence
            )
            
            # Create detailed metrics
            detailed_metrics = [
                EvaluationMetric(
                    metric_type=MetricType.LOCATION_ACCURACY,
                    value=location_accuracy,
                    weight=0.3,
                    description="Accuracy of location identification",
                    calculation_method="validation_based"
                ),
                EvaluationMetric(
                    metric_type=MetricType.ACTION_ACCURACY,
                    value=action_accuracy,
                    weight=0.25,
                    description="Accuracy of action description",
                    calculation_method="validation_based"
                ),
                EvaluationMetric(
                    metric_type=MetricType.DESTINATION_ACCURACY,
                    value=destination_accuracy,
                    weight=0.25,
                    description="Accuracy of destination identification",
                    calculation_method="validation_based"
                ),
                EvaluationMetric(
                    metric_type=MetricType.VALIDATION_SUCCESS_RATE,
                    value=validation_success_rate,
                    weight=0.1,
                    description="Rate of successful note validation",
                    calculation_method="count_based"
                ),
                EvaluationMetric(
                    metric_type=MetricType.CONFIDENCE_SCORE,
                    value=average_confidence,
                    weight=0.1,
                    description="Average confidence in generated notes",
                    calculation_method="average"
                )
            ]
            
            metrics = ExperimentMetrics(
                experiment_id=experiment_id,
                total_notes=total_notes,
                valid_notes=valid_notes,
                location_accuracy=location_accuracy,
                action_accuracy=action_accuracy,
                destination_accuracy=destination_accuracy,
                validation_success_rate=validation_success_rate,
                average_confidence=average_confidence,
                overall_score=overall_score,
                metrics=detailed_metrics,
                metadata={
                    "calculation_version": "1.0",
                    "notes_processed": total_notes,
                    "validation_method": "map_based"
                }
            )
            
            self.logger.info(f"Calculated metrics for experiment {experiment_id}: overall_score={overall_score:.3f}")
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating experiment metrics: {str(e)}")
            raise
    
    def compare_with_ground_truth(
        self,
        notes: List[AutonomousNote],
        ground_truth: List[GroundTruthData]
    ) -> List[ComparisonResult]:
        """
        Compare notes against ground truth data
        
        Args:
            notes: Generated autonomous notes
            ground_truth: Ground truth data for comparison
            
        Returns:
            List of comparison results
        """
        try:
            # Match notes with ground truth by timestamp
            matched_pairs = self._match_notes_with_ground_truth(notes, ground_truth)
            
            comparison_results = []
            for note, gt_data in matched_pairs:
                result = self._compare_note_with_ground_truth(note, gt_data)
                comparison_results.append(result)
            
            self.logger.info(f"Compared {len(comparison_results)} notes with ground truth")
            return comparison_results
            
        except Exception as e:
            self.logger.error(f"Error comparing with ground truth: {str(e)}")
            raise
    
    def generate_evaluation_report(
        self,
        experiment_id: str,
        notes: List[AutonomousNote],
        validation_results: List[ValidationResult],
        ground_truth: Optional[List[GroundTruthData]] = None
    ) -> EvaluationReport:
        """
        Generate comprehensive evaluation report
        
        Args:
            experiment_id: Experiment identifier
            notes: Generated autonomous notes
            validation_results: Validation results
            ground_truth: Optional ground truth data
            
        Returns:
            Complete evaluation report
        """
        try:
            # Calculate experiment metrics
            experiment_metrics = self.calculate_experiment_metrics(
                notes, validation_results, experiment_id
            )
            
            # Compare with ground truth if available
            note_comparisons = []
            if ground_truth:
                note_comparisons = self.compare_with_ground_truth(notes, ground_truth)
            
            # Analyze performance patterns
            performance_by_location = self._analyze_performance_by_location(notes, validation_results)
            performance_by_action = self._analyze_performance_by_action(notes, validation_results)
            performance_trends = self._analyze_performance_trends(notes, validation_results)
            
            # Generate improvement recommendations
            improvement_areas = self._identify_improvement_areas(experiment_metrics, validation_results)
            
            # Analyze confidence patterns
            confidence_analysis = self._analyze_confidence_patterns(notes, validation_results)
            
            report = EvaluationReport(
                experiment_id=experiment_id,
                report_id=str(uuid.uuid4()),
                experiment_metrics=experiment_metrics,
                note_comparisons=note_comparisons,
                performance_by_location=performance_by_location,
                performance_by_action=performance_by_action,
                performance_trends=performance_trends,
                improvement_areas=improvement_areas,
                confidence_analysis=confidence_analysis
            )
            
            self.logger.info(f"Generated evaluation report {report.report_id} for experiment {experiment_id}")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating evaluation report: {str(e)}")
            raise
    
    def _calculate_location_accuracy(self, validation_results: List[ValidationResult]) -> float:
        """Calculate location accuracy from validation results"""
        if not validation_results:
            return 0.0
        
        valid_locations = sum(1 for result in validation_results if result.location_valid)
        return valid_locations / len(validation_results)
    
    def _calculate_action_accuracy(self, validation_results: List[ValidationResult]) -> float:
        """Calculate action accuracy from validation results"""
        if not validation_results:
            return 0.0
        
        valid_actions = sum(1 for result in validation_results if result.action_valid)
        return valid_actions / len(validation_results)
    
    def _calculate_destination_accur     
   
        if denominator == 0:
            return 0.0
        
        return numerator / denominator