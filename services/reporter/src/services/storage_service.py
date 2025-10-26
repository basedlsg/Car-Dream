"""
Data storage and reporting service
Handles BigQuery integration and Cloud Storage for experiment data
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import os

from google.cloud import bigquery
from google.cloud import storage
from google.cloud.exceptions import NotFound

from ..models.note_models import AutonomousNote, ValidationResult
from ..models.evaluation_models import ExperimentMetrics, EvaluationReport


class StorageService:
    """Manages data storage to BigQuery and Cloud Storage"""
    
    def __init__(self, project_id: str, dataset_id: str = "cars_with_life", bucket_name: str = "cars-with-life-reports"):
        self.logger = logging.getLogger(__name__)
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.bucket_name = bucket_name
        
        # Initialize clients
        self.bq_client = bigquery.Client(project=project_id)
        self.storage_client = storage.Client(project=project_id)
        
        # Ensure dataset and bucket exist
        self._ensure_dataset_exists()
        self._ensure_bucket_exists()
    
    def store_experiment_metrics(self, metrics: ExperimentMetrics) -> str:
        """
        Store experiment metrics in BigQuery
        
        Args:
            metrics: Experiment metrics to store
            
        Returns:
            BigQuery table reference
        """
        try:
            table_id = f"{self.project_id}.{self.dataset_id}.experiment_metrics"
            
            # Prepare row data
            row_data = {
                "experiment_id": metrics.experiment_id,
                "calculation_time": metrics.calculation_time.isoformat(),
                "total_notes": metrics.total_notes,
                "valid_notes": metrics.valid_notes,
                "location_accuracy": metrics.location_accuracy,
                "action_accuracy": metrics.action_accuracy,
                "destination_accuracy": metrics.destination_accuracy,
                "validation_success_rate": metrics.validation_success_rate,
                "average_confidence": metrics.average_confidence,
                "overall_score": metrics.overall_score,
                "metadata": json.dumps(metrics.metadata)
            }
            
            # Insert row
            table = self.bq_client.get_table(table_id)
            errors = self.bq_client.insert_rows_json(table, [row_data])
            
            if errors:
                raise Exception(f"BigQuery insert errors: {errors}")
            
            self.logger.info(f"Stored experiment metrics for {metrics.experiment_id} in BigQuery")
            return table_id
            
        except Exception as e:
            self.logger.error(f"Error storing experiment metrics: {str(e)}")
            raise
    
    def store_autonomous_notes(self, notes: List[AutonomousNote], validation_results: List[ValidationResult]) -> str:
        """
        Store autonomous notes and validation results in BigQuery
        
        Args:
            notes: List of autonomous notes
            validation_results: List of validation results
            
        Returns:
            BigQuery table reference
        """
        try:
            table_id = f"{self.project_id}.{self.dataset_id}.autonomous_notes"
            
            if len(notes) != len(validation_results):
                raise ValueError("Notes and validation results must have same length")
            
            # Prepare row data
            rows_data = []
            for note, validation in zip(notes, validation_results):
                row_data = {
                    "note_id": note.note_id,
                    "experiment_id": note.experiment_id,
                    "timestamp": note.timestamp.isoformat(),
                    "location": note.location,
                    "action": note.action,
                    "destination": note.destination,
                    "confidence": note.confidence,
                    "validation_status": note.validation_status.value,
                    "raw_note": note.raw_note,
                    "location_valid": validation.location_valid,
                    "action_valid": validation.action_valid,
                    "destination_valid": validation.destination_valid,
                    "carla_map_match": validation.carla_map_match,
                    "nuscenes_match": validation.nuscenes_match,
                    "validation_confidence": validation.confidence_score,
                    "validation_errors": json.dumps(validation.validation_errors)
                }
                rows_data.append(row_data)
            
            # Insert rows
            table = self.bq_client.get_table(table_id)
            errors = self.bq_client.insert_rows_json(table, rows_data)
            
            if errors:
                raise Exception(f"BigQuery insert errors: {errors}")
            
            self.logger.info(f"Stored {len(notes)} autonomous notes in BigQuery")
            return table_id
            
        except Exception as e:
            self.logger.error(f"Error storing autonomous notes: {str(e)}")
            raise
    
    def store_evaluation_report(self, report: EvaluationReport) -> Dict[str, str]:
        """
        Store evaluation report in Cloud Storage and reference in BigQuery
        
        Args:
            report: Evaluation report to store
            
        Returns:
            Dictionary with storage paths
        """
        try:
            # Generate storage paths
            date_str = report.generated_at.strftime("%Y/%m/%d")
            report_filename = f"evaluation_report_{report.experiment_id}_{report.report_id}.json"
            storage_path = f"reports/{date_str}/{report_filename}"
            
            # Store report in Cloud Storage
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(storage_path)
            
            # Convert report to JSON
            report_json = report.model_dump_json(indent=2)
            blob.upload_from_string(report_json, content_type='application/json')
            
            # Update report with storage path
            report.storage_path = f"gs://{self.bucket_name}/{storage_path}"
            
            # Store report metadata in BigQuery
            table_id = f"{self.project_id}.{self.dataset_id}.evaluation_reports"
            report.bigquery_table = table_id
            
            row_data = {
                "report_id": report.report_id,
                "experiment_id": report.experiment_id,
                "generated_at": report.generated_at.isoformat(),
                "overall_score": report.experiment_metrics.overall_score,
                "total_notes": report.experiment_metrics.total_notes,
                "valid_notes": report.experiment_metrics.valid_notes,
                "storage_path": report.storage_path,
                "improvement_areas": json.dumps(report.improvement_areas)
            }
            
            table = self.bq_client.get_table(table_id)
            errors = self.bq_client.insert_rows_json(table, [row_data])
            
            if errors:
                raise Exception(f"BigQuery insert errors: {errors}")
            
            self.logger.info(f"Stored evaluation report {report.report_id} in Cloud Storage and BigQuery")
            
            return {
                "storage_path": report.storage_path,
                "bigquery_table": table_id
            }
            
        except Exception as e:
            self.logger.error(f"Error storing evaluation report: {str(e)}")
            raise
    
    def generate_daily_report(self, experiment_ids: List[str], report_date: date) -> str:
        """
        Generate and store daily summary report
        
        Args:
            experiment_ids: List of experiment IDs for the day
            report_date: Date for the report
            
        Returns:
            Cloud Storage path to the daily report
        """
        try:
            # Query experiment metrics for the day
            query = f"""
            SELECT 
                experiment_id,
                overall_score,
                total_notes,
                valid_notes,
                location_accuracy,
                action_accuracy,
                destination_accuracy,
                validation_success_rate,
                average_confidence
            FROM `{self.project_id}.{self.dataset_id}.experiment_metrics`
            WHERE experiment_id IN ({','.join([f"'{eid}'" for eid in experiment_ids])})
            ORDER BY calculation_time DESC
            """
            
            query_job = self.bq_client.query(query)
            results = query_job.result()
            
            # Aggregate daily statistics
            daily_stats = {
                "report_date": report_date.isoformat(),
                "total_experiments": len(experiment_ids),
                "experiments": [],
                "daily_averages": {},
                "performance_summary": {}
            }
            
            experiment_data = []
            for row in results:
                exp_data = {
                    "experiment_id": row.experiment_id,
                    "overall_score": row.overall_score,
                    "total_notes": row.total_notes,
                    "valid_notes": row.valid_notes,
                    "location_accuracy": row.location_accuracy,
                    "action_accuracy": row.action_accuracy,
                    "destination_accuracy": row.destination_accuracy,
                    "validation_success_rate": row.validation_success_rate,
                    "average_confidence": row.average_confidence
                }
                experiment_data.append(exp_data)
            
            daily_stats["experiments"] = experiment_data
            
            # Calculate daily averages
            if experiment_data:
                daily_stats["daily_averages"] = {
                    "overall_score": sum(exp["overall_score"] for exp in experiment_data) / len(experiment_data),
                    "location_accuracy": sum(exp["location_accuracy"] for exp in experiment_data) / len(experiment_data),
                    "action_accuracy": sum(exp["action_accuracy"] for exp in experiment_data) / len(experiment_data),
                    "destination_accuracy": sum(exp["destination_accuracy"] for exp in experiment_data) / len(experiment_data),
                    "validation_success_rate": sum(exp["validation_success_rate"] for exp in experiment_data) / len(experiment_data),
                    "average_confidence": sum(exp["average_confidence"] for exp in experiment_data) / len(experiment_data)
                }
                
                # Performance summary
                daily_stats["performance_summary"] = {
                    "best_experiment": max(experiment_data, key=lambda x: x["overall_score"])["experiment_id"],
                    "total_notes_generated": sum(exp["total_notes"] for exp in experiment_data),
                    "total_valid_notes": sum(exp["valid_notes"] for exp in experiment_data)
                }
            
            # Store daily report in Cloud Storage
            date_str = report_date.strftime("%Y/%m/%d")
            report_filename = f"daily_report_{report_date.strftime('%Y%m%d')}.json"
            storage_path = f"daily_reports/{date_str}/{report_filename}"
            
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(storage_path)
            blob.upload_from_string(json.dumps(daily_stats, indent=2), content_type='application/json')
            
            full_path = f"gs://{self.bucket_name}/{storage_path}"
            self.logger.info(f"Generated daily report for {report_date}: {full_path}")
            
            return full_path
            
        except Exception as e:
            self.logger.error(f"Error generating daily report: {str(e)}")
            raise
    
    def _ensure_dataset_exists(self):
        """Ensure BigQuery dataset exists"""
        try:
            dataset_ref = self.bq_client.dataset(self.dataset_id)
            self.bq_client.get_dataset(dataset_ref)
            self.logger.info(f"BigQuery dataset {self.dataset_id} exists")
        except NotFound:
            # Create dataset
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US"
            dataset = self.bq_client.create_dataset(dataset)
            self.logger.info(f"Created BigQuery dataset {self.dataset_id}")
        
        # Ensure tables exist
        self._ensure_tables_exist()
    
    def _ensure_bucket_exists(self):
        """Ensure Cloud Storage bucket exists"""
        try:
            bucket = self.storage_client.get_bucket(self.bucket_name)
            self.logger.info(f"Cloud Storage bucket {self.bucket_name} exists")
        except NotFound:
            # Create bucket
            bucket = self.storage_client.create_bucket(self.bucket_name)
            self.logger.info(f"Created Cloud Storage bucket {self.bucket_name}")
    
    def _ensure_tables_exist(self):
        """Ensure required BigQuery tables exist"""
        tables_schema = {
            "experiment_metrics": [
                bigquery.SchemaField("experiment_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("calculation_time", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("total_notes", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("valid_notes", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("location_accuracy", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("action_accuracy", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("destination_accuracy", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("validation_success_rate", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("average_confidence", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("overall_score", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("metadata", "STRING", mode="NULLABLE")
            ],
            "autonomous_notes": [
                bigquery.SchemaField("note_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("experiment_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("location", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("action", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("destination", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("confidence", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("validation_status", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("raw_note", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("location_valid", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("action_valid", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("destination_valid", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("carla_map_match", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("nuscenes_match", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("validation_confidence", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("validation_errors", "STRING", mode="NULLABLE")
            ],
            "evaluation_reports": [
                bigquery.SchemaField("report_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("experiment_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("generated_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("overall_score", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("total_notes", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("valid_notes", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("storage_path", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("improvement_areas", "STRING", mode="NULLABLE")
            ]
        }
        
        for table_name, schema in tables_schema.items():
            table_id = f"{self.project_id}.{self.dataset_id}.{table_name}"
            try:
                self.bq_client.get_table(table_id)
                self.logger.info(f"BigQuery table {table_name} exists")
            except NotFound:
                table = bigquery.Table(table_id, schema=schema)
                table = self.bq_client.create_table(table)
                self.logger.info(f"Created BigQuery table {table_name}")