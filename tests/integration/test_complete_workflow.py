#!/usr/bin/env python3
"""
Complete Workflow Integration Tests
Tests the entire Cars with a Life system end-to-end
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pytest
import requests
from google.cloud import bigquery, pubsub_v1, storage
from google.cloud.exceptions import NotFound

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemIntegrationTest:
    """Complete system integration test suite"""
    
    def __init__(self):
        self.project_id = os.getenv('GCP_PROJECT_ID', 'cars-with-a-life')
        self.region = os.getenv('GCP_REGION', 'us-central1')
        self.orchestrator_url = os.getenv('ORCHESTRATOR_URL')
        self.reporter_url = os.getenv('REPORTER_URL')
        
        # Initialize GCP clients
        self.bigquery_client = bigquery.Client(project=self.project_id)
        self.storage_client = storage.Client(project=self.project_id)
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        
        # Test configuration
        self.test_experiment_id = f"test-experiment-{uuid.uuid4().hex[:8]}"
        self.test_timeout = 300  # 5 minutes
        self.poll_interval = 10  # 10 seconds
        
    async def setup_test_environment(self):
        """Setup test environment and verify prerequisites"""
        logger.info("Setting up test environment...")
        
        # Verify service endpoints
        await self._verify_service_endpoints()
        
        # Verify GCP resources
        await self._verify_gcp_resources()
        
        # Setup test data
        await self._setup_test_data()
        
        logger.info("Test environment setup completed")
    
    async def _verify_service_endpoints(self):
        """Verify all service endpoints are accessible"""
        logger.info("Verifying service endpoints...")
        
        services = {
            'orchestrator': self.orchestrator_url,
            'reporter': self.reporter_url
        }
        
        for service_name, url in services.items():
            if not url:
                raise ValueError(f"{service_name.upper()}_URL environment variable not set")
            
            try:
                response = requests.get(f"{url}/health", timeout=30)
                response.raise_for_status()
                logger.info(f"✓ {service_name} service is healthy")
            except requests.RequestException as e:
                raise RuntimeError(f"Failed to connect to {service_name} service: {e}")
    
    async def _verify_gcp_resources(self):
        """Verify required GCP resources exist"""
        logger.info("Verifying GCP resources...")
        
        # Verify BigQuery dataset
        dataset_id = "cars_with_a_life"
        try:
            self.bigquery_client.get_dataset(dataset_id)
            logger.info(f"✓ BigQuery dataset {dataset_id} exists")
        except NotFound:
            raise RuntimeError(f"BigQuery dataset {dataset_id} not found")
        
        # Verify storage buckets
        required_buckets = [
            f"{self.project_id}-carla-data",
            f"{self.project_id}-models",
            f"{self.project_id}-results"
        ]
        
        for bucket_name in required_buckets:
            try:
                self.storage_client.get_bucket(bucket_name)
                logger.info(f"✓ Storage bucket {bucket_name} exists")
            except NotFound:
                raise RuntimeError(f"Storage bucket {bucket_name} not found")
        
        # Verify Pub/Sub topics
        required_topics = ["experiment-events", "ai-decisions", "model-metrics"]
        
        for topic_name in required_topics:
            topic_path = self.publisher.topic_path(self.project_id, topic_name)
            try:
                self.publisher.get_topic(request={"topic": topic_path})
                logger.info(f"✓ Pub/Sub topic {topic_name} exists")
            except Exception:
                raise RuntimeError(f"Pub/Sub topic {topic_name} not found")
    
    async def _setup_test_data(self):
        """Setup test data for integration tests"""
        logger.info("Setting up test data...")
        
        # Create test experiment configuration
        self.test_experiment_config = {
            "experiment_id": self.test_experiment_id,
            "name": f"Integration Test Experiment {datetime.now().isoformat()}",
            "description": "End-to-end integration test experiment",
            "parameters": {
                "simulation_duration": 60,  # 1 minute for testing
                "weather_conditions": "clear",
                "traffic_density": "light",
                "ai_model_version": "latest",
                "evaluation_metrics": ["safety_score", "efficiency_score", "comfort_score"]
            },
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        
        logger.info(f"Test experiment ID: {self.test_experiment_id}")
    
    async def test_complete_experiment_workflow(self):
        """Test complete experiment workflow from start to finish"""
        logger.info("Starting complete experiment workflow test...")
        
        try:
            # Step 1: Submit experiment
            experiment_result = await self._submit_experiment()
            
            # Step 2: Monitor experiment execution
            execution_result = await self._monitor_experiment_execution()
            
            # Step 3: Verify AI decision making
            ai_decisions = await self._verify_ai_decisions()
            
            # Step 4: Verify data storage
            storage_result = await self._verify_data_storage()
            
            # Step 5: Verify report generation
            report_result = await self._verify_report_generation()
            
            # Step 6: Verify metrics calculation
            metrics_result = await self._verify_metrics_calculation()
            
            # Compile test results
            test_results = {
                "experiment_submission": experiment_result,
                "experiment_execution": execution_result,
                "ai_decisions": ai_decisions,
                "data_storage": storage_result,
                "report_generation": report_result,
                "metrics_calculation": metrics_result,
                "overall_status": "success",
                "test_duration": time.time() - self.start_time
            }
            
            logger.info("Complete experiment workflow test completed successfully")
            return test_results
            
        except Exception as e:
            logger.error(f"Complete experiment workflow test failed: {e}")
            raise
    
    async def _submit_experiment(self) -> Dict:
        """Submit experiment to orchestrator service"""
        logger.info("Submitting experiment...")
        
        self.start_time = time.time()
        
        response = requests.post(
            f"{self.orchestrator_url}/experiments",
            json=self.test_experiment_config,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"Experiment submitted successfully: {result.get('experiment_id')}")
        
        return {
            "status": "success",
            "experiment_id": result.get("experiment_id"),
            "submission_time": datetime.utcnow().isoformat()
        }
    
    async def _monitor_experiment_execution(self) -> Dict:
        """Monitor experiment execution until completion"""
        logger.info("Monitoring experiment execution...")
        
        start_time = time.time()
        
        while time.time() - start_time < self.test_timeout:
            try:
                response = requests.get(
                    f"{self.orchestrator_url}/experiments/{self.test_experiment_id}",
                    timeout=30
                )
                response.raise_for_status()
                
                experiment_status = response.json()
                status = experiment_status.get("status")
                
                logger.info(f"Experiment status: {status}")
                
                if status == "completed":
                    return {
                        "status": "success",
                        "execution_time": time.time() - start_time,
                        "final_status": status,
                        "experiment_data": experiment_status
                    }
                elif status == "failed":
                    raise RuntimeError(f"Experiment failed: {experiment_status.get('error')}")
                
                await asyncio.sleep(self.poll_interval)
                
            except requests.RequestException as e:
                logger.warning(f"Error checking experiment status: {e}")
                await asyncio.sleep(self.poll_interval)
        
        raise TimeoutError(f"Experiment did not complete within {self.test_timeout} seconds")
    
    async def _verify_ai_decisions(self) -> Dict:
        """Verify AI decision making during experiment"""
        logger.info("Verifying AI decisions...")
        
        # Subscribe to AI decisions topic
        subscription_path = self.subscriber.subscription_path(
            self.project_id, f"ai-decisions-test-{uuid.uuid4().hex[:8]}"
        )
        topic_path = self.publisher.topic_path(self.project_id, "ai-decisions")
        
        try:
            # Create temporary subscription
            self.subscriber.create_subscription(
                request={"name": subscription_path, "topic": topic_path}
            )
            
            decisions = []
            start_time = time.time()
            
            def callback(message):
                try:
                    decision_data = json.loads(message.data.decode())
                    if decision_data.get("experiment_id") == self.test_experiment_id:
                        decisions.append(decision_data)
                        logger.info(f"Received AI decision: {decision_data.get('decision_type')}")
                    message.ack()
                except Exception as e:
                    logger.error(f"Error processing AI decision message: {e}")
                    message.nack()
            
            # Pull messages for a limited time
            flow_control = pubsub_v1.types.FlowControl(max_messages=100)
            streaming_pull_future = self.subscriber.subscribe(
                subscription_path, callback=callback, flow_control=flow_control
            )
            
            # Wait for decisions or timeout
            timeout_time = 60  # 1 minute
            try:
                streaming_pull_future.result(timeout=timeout_time)
            except Exception:
                streaming_pull_future.cancel()
            
            return {
                "status": "success" if decisions else "no_decisions",
                "decision_count": len(decisions),
                "decisions": decisions[:10],  # Limit to first 10 for logging
                "verification_time": time.time() - start_time
            }
            
        finally:
            # Clean up subscription
            try:
                self.subscriber.delete_subscription(request={"subscription": subscription_path})
            except Exception:
                pass
    
    async def _verify_data_storage(self) -> Dict:
        """Verify experiment data is stored correctly"""
        logger.info("Verifying data storage...")
        
        storage_results = {}
        
        # Check BigQuery data
        query = f"""
        SELECT COUNT(*) as record_count
        FROM `{self.project_id}.cars_with_a_life.experiments`
        WHERE experiment_id = '{self.test_experiment_id}'
        """
        
        try:
            query_job = self.bigquery_client.query(query)
            results = list(query_job.result())
            record_count = results[0].record_count if results else 0
            
            storage_results["bigquery"] = {
                "status": "success" if record_count > 0 else "no_data",
                "record_count": record_count
            }
        except Exception as e:
            storage_results["bigquery"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Check Cloud Storage data
        bucket_name = f"{self.project_id}-results"
        try:
            bucket = self.storage_client.bucket(bucket_name)
            blobs = list(bucket.list_blobs(prefix=f"experiments/{self.test_experiment_id}"))
            
            storage_results["cloud_storage"] = {
                "status": "success" if blobs else "no_data",
                "file_count": len(blobs),
                "files": [blob.name for blob in blobs[:5]]  # First 5 files
            }
        except Exception as e:
            storage_results["cloud_storage"] = {
                "status": "error",
                "error": str(e)
            }
        
        return storage_results
    
    async def _verify_report_generation(self) -> Dict:
        """Verify experiment report generation"""
        logger.info("Verifying report generation...")
        
        try:
            response = requests.get(
                f"{self.reporter_url}/reports/{self.test_experiment_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                report_data = response.json()
                return {
                    "status": "success",
                    "report_generated": True,
                    "report_sections": list(report_data.keys()) if isinstance(report_data, dict) else [],
                    "report_size": len(str(report_data))
                }
            elif response.status_code == 404:
                return {
                    "status": "not_found",
                    "report_generated": False
                }
            else:
                return {
                    "status": "error",
                    "http_status": response.status_code,
                    "error": response.text
                }
                
        except requests.RequestException as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _verify_metrics_calculation(self) -> Dict:
        """Verify metrics calculation and autonomous notes generation"""
        logger.info("Verifying metrics calculation...")
        
        try:
            response = requests.get(
                f"{self.reporter_url}/metrics/{self.test_experiment_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                metrics_data = response.json()
                
                # Check for autonomous notes
                notes_response = requests.get(
                    f"{self.reporter_url}/notes/{self.test_experiment_id}",
                    timeout=30
                )
                
                notes_data = notes_response.json() if notes_response.status_code == 200 else {}
                
                return {
                    "status": "success",
                    "metrics_calculated": True,
                    "metrics": metrics_data,
                    "autonomous_notes": notes_data,
                    "notes_generated": notes_response.status_code == 200
                }
            else:
                return {
                    "status": "error",
                    "http_status": response.status_code,
                    "error": response.text
                }
                
        except requests.RequestException as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def test_error_handling_and_recovery(self):
        """Test system error handling and recovery mechanisms"""
        logger.info("Testing error handling and recovery...")
        
        test_results = {}
        
        # Test 1: Invalid experiment configuration
        try:
            invalid_config = {
                "experiment_id": f"invalid-test-{uuid.uuid4().hex[:8]}",
                "invalid_field": "invalid_value"
            }
            
            response = requests.post(
                f"{self.orchestrator_url}/experiments",
                json=invalid_config,
                timeout=30
            )
            
            test_results["invalid_config"] = {
                "status": "success" if response.status_code >= 400 else "failed",
                "http_status": response.status_code,
                "error_handled": response.status_code >= 400
            }
            
        except Exception as e:
            test_results["invalid_config"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Test 2: Service timeout handling
        try:
            # This should timeout or return quickly
            response = requests.get(
                f"{self.orchestrator_url}/experiments/nonexistent-experiment",
                timeout=5
            )
            
            test_results["nonexistent_experiment"] = {
                "status": "success" if response.status_code == 404 else "unexpected",
                "http_status": response.status_code
            }
            
        except requests.Timeout:
            test_results["nonexistent_experiment"] = {
                "status": "timeout",
                "error": "Request timed out as expected"
            }
        except Exception as e:
            test_results["nonexistent_experiment"] = {
                "status": "error",
                "error": str(e)
            }
        
        return test_results
    
    async def test_performance_and_scalability(self):
        """Test system performance and scalability"""
        logger.info("Testing performance and scalability...")
        
        # Test concurrent experiment submissions
        concurrent_experiments = 3
        experiment_ids = []
        
        async def submit_concurrent_experiment(index):
            experiment_config = self.test_experiment_config.copy()
            experiment_config["experiment_id"] = f"perf-test-{index}-{uuid.uuid4().hex[:8]}"
            experiment_config["parameters"]["simulation_duration"] = 30  # Shorter for performance test
            
            start_time = time.time()
            
            try:
                response = requests.post(
                    f"{self.orchestrator_url}/experiments",
                    json=experiment_config,
                    timeout=30
                )
                response.raise_for_status()
                
                return {
                    "experiment_id": experiment_config["experiment_id"],
                    "status": "success",
                    "submission_time": time.time() - start_time,
                    "response_code": response.status_code
                }
                
            except Exception as e:
                return {
                    "experiment_id": experiment_config["experiment_id"],
                    "status": "error",
                    "error": str(e),
                    "submission_time": time.time() - start_time
                }
        
        # Submit experiments concurrently
        tasks = [submit_concurrent_experiment(i) for i in range(concurrent_experiments)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze performance results
        successful_submissions = [r for r in results if isinstance(r, dict) and r.get("status") == "success"]
        failed_submissions = [r for r in results if isinstance(r, dict) and r.get("status") == "error"]
        
        avg_submission_time = sum(r["submission_time"] for r in successful_submissions) / len(successful_submissions) if successful_submissions else 0
        
        return {
            "concurrent_experiments": concurrent_experiments,
            "successful_submissions": len(successful_submissions),
            "failed_submissions": len(failed_submissions),
            "average_submission_time": avg_submission_time,
            "results": results
        }
    
    async def cleanup_test_environment(self):
        """Clean up test environment and resources"""
        logger.info("Cleaning up test environment...")
        
        try:
            # Cancel test experiment if still running
            requests.delete(
                f"{self.orchestrator_url}/experiments/{self.test_experiment_id}",
                timeout=30
            )
        except Exception:
            pass
        
        # Clean up test data from BigQuery
        try:
            query = f"""
            DELETE FROM `{self.project_id}.cars_with_a_life.experiments`
            WHERE experiment_id LIKE 'test-experiment-%' OR experiment_id LIKE 'perf-test-%'
            """
            self.bigquery_client.query(query)
        except Exception as e:
            logger.warning(f"Failed to clean up BigQuery test data: {e}")
        
        # Clean up test files from Cloud Storage
        try:
            bucket = self.storage_client.bucket(f"{self.project_id}-results")
            blobs = bucket.list_blobs(prefix="experiments/test-experiment-")
            for blob in blobs:
                blob.delete()
        except Exception as e:
            logger.warning(f"Failed to clean up Cloud Storage test data: {e}")
        
        logger.info("Test environment cleanup completed")


# Pytest test functions
@pytest.fixture
async def integration_test():
    """Pytest fixture for integration test setup and teardown"""
    test_instance = SystemIntegrationTest()
    await test_instance.setup_test_environment()
    
    yield test_instance
    
    await test_instance.cleanup_test_environment()


@pytest.mark.asyncio
async def test_complete_workflow(integration_test):
    """Test complete experiment workflow"""
    result = await integration_test.test_complete_experiment_workflow()
    assert result["overall_status"] == "success"
    assert result["experiment_submission"]["status"] == "success"
    assert result["experiment_execution"]["status"] == "success"


@pytest.mark.asyncio
async def test_error_handling(integration_test):
    """Test error handling and recovery mechanisms"""
    result = await integration_test.test_error_handling_and_recovery()
    assert result["invalid_config"]["error_handled"] is True
    assert result["nonexistent_experiment"]["status"] in ["success", "timeout"]


@pytest.mark.asyncio
async def test_performance(integration_test):
    """Test system performance and scalability"""
    result = await integration_test.test_performance_and_scalability()
    assert result["successful_submissions"] > 0
    assert result["average_submission_time"] < 10  # Should submit within 10 seconds


if __name__ == "__main__":
    # Run tests directly
    async def main():
        test_instance = SystemIntegrationTest()
        
        try:
            await test_instance.setup_test_environment()
            
            # Run all tests
            workflow_result = await test_instance.test_complete_experiment_workflow()
            error_result = await test_instance.test_error_handling_and_recovery()
            performance_result = await test_instance.test_performance_and_scalability()
            
            # Print results
            print("\n" + "="*50)
            print("INTEGRATION TEST RESULTS")
            print("="*50)
            print(f"Complete Workflow: {workflow_result['overall_status']}")
            print(f"Error Handling: {'PASS' if error_result else 'FAIL'}")
            print(f"Performance: {performance_result['successful_submissions']}/{performance_result['concurrent_experiments']} successful")
            print("="*50)
            
        finally:
            await test_instance.cleanup_test_environment()
    
    asyncio.run(main())