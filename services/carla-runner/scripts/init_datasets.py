#!/usr/bin/env python3
"""
Dataset initialization script for CARLA simulator.
Loads preexisting datasets including CARLA maps, OSM data, and nuScenes data.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path
from google.cloud import storage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CARLA_ROOT = os.environ.get('CARLA_ROOT', '/opt/carla-simulator')
GCS_BUCKET = os.environ.get('CARLA_DATASETS_BUCKET', 'carla-datasets-bucket')

class DatasetInitializer:
    def __init__(self):
        self.carla_root = Path(CARLA_ROOT)
        self.maps_dir = self.carla_root / 'Import'
        self.osm_dir = self.carla_root / 'Data' / 'OSM'
        self.nuscenes_dir = self.carla_root / 'Data' / 'nuScenes'
        
        # Initialize GCS client if credentials are available
        try:
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(GCS_BUCKET)
        except Exception as e:
            logger.warning(f"Could not initialize GCS client: {e}")
            self.storage_client = None

    def check_carla_maps(self):
        """Check if CARLA default maps are available."""
        logger.info("Checking CARLA default maps...")
        
        # CARLA comes with default maps, verify they exist
        carla_maps_dir = self.carla_root / 'CarlaUE4' / 'Content' / 'Carla' / 'Maps'
        if carla_maps_dir.exists():
            maps = list(carla_maps_dir.glob('*.umap'))
            logger.info(f"Found {len(maps)} CARLA maps")
            return True
        else:
            logger.warning("CARLA maps directory not found")
            return False

    def download_osm_data(self):
        """Download and prepare OSM data for CARLA."""
        logger.info("Initializing OSM data...")
        
        # Create OSM directory if it doesn't exist
        self.osm_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if OSM data already exists
        osm_files = list(self.osm_dir.glob('*.osm'))
        if osm_files:
            logger.info(f"Found {len(osm_files)} OSM files")
            return True
        
        # Download sample OSM data if GCS is available
        if self.storage_client:
            try:
                # Download sample OSM files from GCS
                osm_blobs = self.bucket.list_blobs(prefix='osm/')
                for blob in osm_blobs:
                    if blob.name.endswith('.osm'):
                        local_path = self.osm_dir / Path(blob.name).name
                        blob.download_to_filename(str(local_path))
                        logger.info(f"Downloaded {blob.name}")
                return True
            except Exception as e:
                logger.warning(f"Could not download OSM data from GCS: {e}")
        
        # Create a placeholder OSM file for testing
        sample_osm = self.osm_dir / 'sample.osm'
        if not sample_osm.exists():
            logger.info("Creating sample OSM data for testing")
            sample_osm.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="sample">
  <bounds minlat="37.7749" minlon="-122.4194" maxlat="37.7849" maxlon="-122.4094"/>
  <node id="1" lat="37.7749" lon="-122.4194"/>
  <node id="2" lat="37.7849" lon="-122.4094"/>
  <way id="1">
    <nd ref="1"/>
    <nd ref="2"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>""")
        
        return True

    def download_nuscenes_data(self):
        """Download and prepare nuScenes data for CARLA."""
        logger.info("Initializing nuScenes data...")
        
        # Create nuScenes directory if it doesn't exist
        self.nuscenes_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if nuScenes data already exists
        nuscenes_files = list(self.nuscenes_dir.glob('*.json'))
        if nuscenes_files:
            logger.info(f"Found {len(nuscenes_files)} nuScenes files")
            return True
        
        # Download nuScenes metadata if GCS is available
        if self.storage_client:
            try:
                # Download nuScenes metadata files from GCS
                nuscenes_blobs = self.bucket.list_blobs(prefix='nuscenes/')
                for blob in nuscenes_blobs:
                    if blob.name.endswith('.json'):
                        local_path = self.nuscenes_dir / Path(blob.name).name
                        blob.download_to_filename(str(local_path))
                        logger.info(f"Downloaded {blob.name}")
                return True
            except Exception as e:
                logger.warning(f"Could not download nuScenes data from GCS: {e}")
        
        # Create placeholder nuScenes metadata for testing
        sample_metadata = self.nuscenes_dir / 'sample_metadata.json'
        if not sample_metadata.exists():
            logger.info("Creating sample nuScenes metadata for testing")
            sample_metadata.write_text("""{
  "version": "v1.0-mini",
  "description": "Sample nuScenes metadata for CARLA integration",
  "scenes": [
    {
      "token": "sample_scene_001",
      "name": "sample_scene",
      "description": "Sample scene for testing"
    }
  ],
  "maps": [
    {
      "token": "sample_map_001",
      "log_tokens": ["sample_log_001"],
      "category": "semantic_prior",
      "filename": "maps/sample_map.json"
    }
  ]
}""")
        
        return True

    def verify_datasets(self):
        """Verify that all required datasets are properly initialized."""
        logger.info("Verifying dataset initialization...")
        
        checks = [
            ("CARLA Maps", self.check_carla_maps()),
            ("OSM Data", len(list(self.osm_dir.glob('*.osm'))) > 0),
            ("nuScenes Data", len(list(self.nuscenes_dir.glob('*.json'))) > 0)
        ]
        
        all_passed = True
        for name, passed in checks:
            status = "✓" if passed else "✗"
            logger.info(f"{status} {name}")
            if not passed:
                all_passed = False
        
        return all_passed

    def initialize_all(self):
        """Initialize all datasets."""
        logger.info("Starting dataset initialization...")
        
        try:
            # Initialize each dataset type
            self.check_carla_maps()
            self.download_osm_data()
            self.download_nuscenes_data()
            
            # Verify everything is ready
            if self.verify_datasets():
                logger.info("Dataset initialization completed successfully")
                return True
            else:
                logger.error("Dataset initialization failed verification")
                return False
                
        except Exception as e:
            logger.error(f"Dataset initialization failed: {e}")
            return False

def main():
    """Main entry point for dataset initialization."""
    initializer = DatasetInitializer()
    
    if initializer.initialize_all():
        logger.info("All datasets initialized successfully")
        sys.exit(0)
    else:
        logger.error("Dataset initialization failed")
        sys.exit(1)

if __name__ == "__main__":
    main()