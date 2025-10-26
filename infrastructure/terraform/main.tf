terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP Zone"
  type        = string
  default     = "us-central1-a"
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "compute.googleapis.com",
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "cloudbuild.googleapis.com"
  ])
  
  service = each.value
  disable_on_destroy = false
}

# Storage buckets
resource "google_storage_bucket" "carla_data" {
  name     = "${var.project_id}-carla-data"
  location = var.region
  
  uniform_bucket_level_access = true
  
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "models" {
  name     = "${var.project_id}-models"
  location = var.region
  
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "results" {
  name     = "${var.project_id}-results"
  location = var.region
  
  uniform_bucket_level_access = true
  
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# Pub/Sub topics
resource "google_pubsub_topic" "experiment_events" {
  name = "experiment-events"
}

resource "google_pubsub_subscription" "experiment_events_sub" {
  name  = "experiment-events-subscription"
  topic = google_pubsub_topic.experiment_events.name
  
  ack_deadline_seconds = 20
}

# Outputs
output "carla_data_bucket" {
  value = google_storage_bucket.carla_data.name
}

output "models_bucket" {
  value = google_storage_bucket.models.name
}

output "results_bucket" {
  value = google_storage_bucket.results.name
}