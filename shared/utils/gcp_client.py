"""
Google Cloud Platform client utilities
"""

import os
from google.cloud import storage, pubsub_v1, compute_v1
from google.cloud.exceptions import NotFound
from typing import Optional


class GCPClient:
    """Unified GCP client for common operations"""
    
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.getenv('GCP_PROJECT_ID')
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID must be set")
        
        self.storage_client = storage.Client(project=self.project_id)
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        self.compute_client = compute_v1.InstancesClient()
    
    def upload_to_bucket(self, bucket_name: str, source_path: str, destination_path: str) -> str:
        """Upload file to Cloud Storage bucket"""
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_path)
        blob.upload_from_filename(source_path)
        return f"gs://{bucket_name}/{destination_path}"
    
    def download_from_bucket(self, bucket_name: str, source_path: str, destination_path: str):
        """Download file from Cloud Storage bucket"""
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(source_path)
        blob.download_to_filename(destination_path)
    
    def publish_message(self, topic_name: str, message: bytes, **attributes):
        """Publish message to Pub/Sub topic"""
        topic_path = self.publisher.topic_path(self.project_id, topic_name)
        future = self.publisher.publish(topic_path, message, **attributes)
        return future.result()
    
    def get_instance_status(self, zone: str, instance_name: str) -> str:
        """Get Compute Engine instance status"""
        try:
            instance = self.compute_client.get(
                project=self.project_id,
                zone=zone,
                instance=instance_name
            )
            return instance.status
        except NotFound:
            return "NOT_FOUND"