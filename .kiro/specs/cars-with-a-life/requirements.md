# Requirements Document

## Introduction

The "Cars with a Life" system is a fully cloud-based autonomous vehicle experiment platform that combines CARLA simulation, DreamerV3/CarDreamer world models, and comprehensive data collection and analysis capabilities. The system orchestrates daily autonomous driving experiments, generates human-readable driving notes, validates them against map data, and produces automated evaluation reports.

## Glossary

- **CARLA_Simulator**: Open-source autonomous driving simulator running headless on Google Cloud Compute Engine GPU
- **DreamerV3_Service**: World model AI service (DreamerV3 or CarDreamer) deployed as REST API on Vertex AI
- **Orchestrator_Service**: Cloud Run microservice that manages daily experiment execution and coordination
- **Reporter_Service**: Cloud Run microservice responsible for logging outputs and generating evaluation reports
- **Experiment_Pipeline**: Complete workflow from simulation initialization to report generation
- **Autonomous_Note**: Short textual description of driving actions in format "At [place], did [action] to reach [next POI]"
- **POI**: Point of Interest in the driving environment
- **Evaluation_Metrics**: Accuracy measurements for location, action, and destination predictions
- **Cloud_Infrastructure**: Google Cloud Platform services including Compute Engine, Vertex AI, Cloud Run, Pub/Sub, BigQuery, and Cloud Storage

## Requirements

### Requirement 1

**User Story:** As a researcher, I want the system to run CARLA simulation in a cloud environment, so that I can conduct autonomous driving experiments without local hardware constraints.

#### Acceptance Criteria

1. THE CARLA_Simulator SHALL run headless on Google Cloud Compute Engine GPU instances
2. THE CARLA_Simulator SHALL initialize with preexisting datasets including CARLA maps, OSM data, and nuScenes data
3. THE CARLA_Simulator SHALL provide simulation data to the DreamerV3_Service via network interface
4. THE CARLA_Simulator SHALL execute without requiring user-collected training data
5. THE CARLA_Simulator SHALL be containerized using Docker for consistent deployment

### Requirement 2

**User Story:** As a researcher, I want AI-driven world model services deployed on Vertex AI, so that I can leverage advanced machine learning capabilities for autonomous driving decision-making.

#### Acceptance Criteria

1. THE DreamerV3_Service SHALL be deployed as a REST API endpoint on Vertex AI
2. THE DreamerV3_Service SHALL accept simulation data from CARLA_Simulator
3. THE DreamerV3_Service SHALL return driving decisions and actions via HTTP responses
4. WHERE CarDreamer is selected, THE DreamerV3_Service SHALL implement CarDreamer-specific functionality
5. THE DreamerV3_Service SHALL be containerized and uploaded to Artifact Registry

### Requirement 3

**User Story:** As a researcher, I want orchestrated microservices to manage experiment workflows, so that daily autonomous driving experiments run automatically without manual intervention.

#### Acceptance Criteria

1. THE Orchestrator_Service SHALL coordinate daily experiment execution via Cloud Scheduler triggers
2. THE Orchestrator_Service SHALL communicate with all system components using Pub/Sub messaging
3. THE Orchestrator_Service SHALL manage experiment lifecycle from initialization to completion
4. THE Reporter_Service SHALL collect experiment outputs and generate evaluation reports
5. THE Orchestrator_Service SHALL be deployed on Cloud Run with appropriate scaling configuration

### Requirement 4

**User Story:** As a researcher, I want the system to generate human-readable driving notes, so that I can understand the autonomous vehicle's decision-making process in natural language.

#### Acceptance Criteria

1. THE Experiment_Pipeline SHALL generate Autonomous_Notes in the format "At [place], did [action] to reach [next POI]"
2. THE Experiment_Pipeline SHALL validate Autonomous_Notes against CARLA map data
3. THE Experiment_Pipeline SHALL validate Autonomous_Notes against nuScenes dataset references
4. THE Autonomous_Note SHALL contain accurate location, action, and destination information
5. THE Experiment_Pipeline SHALL store validated notes for evaluation processing

### Requirement 5

**User Story:** As a researcher, I want automated evaluation and reporting capabilities, so that I can assess system performance and track improvements over time.

#### Acceptance Criteria

1. THE Reporter_Service SHALL calculate Evaluation_Metrics for location accuracy, action accuracy, and destination accuracy
2. THE Reporter_Service SHALL generate daily reports and store them in BigQuery
3. THE Reporter_Service SHALL save experiment artifacts to Cloud Storage
4. THE Reporter_Service SHALL provide automated metric collection without manual data processing
5. THE Experiment_Pipeline SHALL execute evaluation workflows on a daily schedule via Cloud Scheduler

### Requirement 6

**User Story:** As a developer, I want complete deployment automation and infrastructure-as-code, so that I can deploy and manage the entire system using only CLI commands.

#### Acceptance Criteria

1. THE Cloud_Infrastructure SHALL be deployable using only Google Cloud SDK CLI commands
2. THE Cloud_Infrastructure SHALL include Dockerfiles for all service components
3. THE Cloud_Infrastructure SHALL provide deployment scripts for Artifact Registry, Vertex AI, Cloud Run, Pub/Sub, BigQuery, and Cloud Scheduler
4. THE Cloud_Infrastructure SHALL include BigQuery table schemas and Pub/Sub topic configurations
5. THE Cloud_Infrastructure SHALL be reproducible without placeholder values or manual configuration steps