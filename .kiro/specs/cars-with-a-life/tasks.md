# Implementation Plan

- [x] 1. Set up project structure and core infrastructure
  - Create directory structure for all microservices and deployment configurations
  - Set up Docker configuration files for each service component
  - Create base Python requirements and dependency management files
  - Initialize Google Cloud deployment scripts and configuration templates
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 2. Implement CARLA Runner service
  - [x] 2.1 Create CARLA Docker container with headless configuration
    - Write Dockerfile for CARLA simulator with GPU support and headless setup
    - Configure CARLA to load preexisting datasets (CARLA maps, OSM, nuScenes)
    - Implement dataset initialization scripts for automatic data loading
    - _Requirements: 1.1, 1.2, 1.4, 1.5_
  
  - [x] 2.2 Implement CARLA REST API wrapper
    - Create FastAPI service to expose CARLA simulation controls
    - Implement endpoints for simulation start, state retrieval, action execution, and cleanup
    - Add Pub/Sub event publishing for simulation lifecycle events
    - _Requirements: 1.3, 3.2_
  
  - [x] 2.3 Add simulation state management and error handling
    - Implement simulation state persistence and recovery mechanisms
    - Create error handling for CARLA crashes and resource exhaustion
    - Add health check endpoints and monitoring capabilities
    - _Requirements: 1.1, 1.3_

- [x] 3. Implement DreamerV3 Service for Vertex AI
  - [x] 3.1 Create DreamerV3/CarDreamer model wrapper
    - Implement REST API wrapper for DreamerV3 or CarDreamer model
    - Create model loading and initialization logic with error handling
    - Add prediction endpoint that accepts CARLA simulation data
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [x] 3.2 Implement Vertex AI deployment configuration
    - Create Docker container for model service with all dependencies
    - Write Vertex AI custom prediction service configuration
    - Implement model health checks and status reporting endpoints
    - _Requirements: 2.1, 2.5_
  
  - [x] 3.3 Add model decision logic and communication
    - Implement decision-making logic that processes simulation state
    - Create response formatting for driving actions and confidence scores
    - Add Pub/Sub integration for AI decision events
    - _Requirements: 2.2, 2.3, 3.2_

- [x] 4. Implement Orchestrator Service
  - [x] 4.1 Create experiment coordination logic
    - Implement FastAPI service for experiment lifecycle management
    - Create experiment configuration handling and validation
    - Add Cloud Scheduler trigger handling for daily experiments
    - _Requirements: 3.1, 3.3, 5.5_
  
  - [x] 4.2 Implement component communication and coordination
    - Create service clients for CARLA Runner and DreamerV3 Service
    - Implement Pub/Sub event handling and message routing
    - Add experiment state management and progress tracking
    - _Requirements: 3.2, 3.3_
  
  - [x] 4.3 Add experiment workflow orchestration
    - Implement complete experiment execution workflow
    - Create error handling and recovery mechanisms for failed experiments
    - Add experiment cleanup and resource management
    - _Requirements: 3.1, 3.3_

- [x] 5. Implement Reporter Service
  - [x] 5.1 Create autonomous note generation logic
    - Implement note generation from simulation data and AI decisions
    - Create note formatting in "At [place], did [action] to reach [next POI]" format
    - Add note validation against CARLA and nuScenes map data
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [x] 5.2 Implement evaluation metrics calculation
    - Create metrics calculation for location, action, and destination accuracy
    - Implement evaluation algorithms that compare notes against ground truth
    - Add confidence scoring and validation success rate calculations
    - _Requirements: 5.1, 5.4_
  
  - [x] 5.3 Add data storage and reporting capabilities
    - Implement BigQuery integration for metrics and experiment data storage
    - Create Cloud Storage integration for experiment artifacts and reports
    - Add daily report generation and automated storage workflows
    - _Requirements: 5.2, 5.3_

- [x] 6. Implement Google Cloud infrastructure deployment
  - [x] 6.1 Create Artifact Registry and container deployment
    - Write scripts to build and push all Docker images to Artifact Registry
    - Create automated container versioning and tagging system
    - Implement deployment validation and rollback mechanisms
    - _Requirements: 6.1, 6.2_
  
  - [x] 6.2 Deploy Compute Engine and Vertex AI resources
    - Create Compute Engine instance deployment for CARLA Runner with GPU
    - Implement Vertex AI model endpoint deployment and configuration
    - Add resource monitoring and auto-scaling configuration
    - _Requirements: 6.1, 6.3_
  
  - [x] 6.3 Configure Cloud Run services and messaging
    - Deploy Orchestrator and Reporter services to Cloud Run
    - Create Pub/Sub topics, subscriptions, and push configurations
    - Implement service-to-service authentication and networking
    - _Requirements: 6.1, 6.3_

- [x] 7. Implement data infrastructure and scheduling
  - [x] 7.1 Create BigQuery schemas and Cloud Storage setup
    - Implement BigQuery dataset creation with experiments, notes, and metrics tables
    - Create Cloud Storage buckets for experiment artifacts and reports
    - Add data retention policies and access control configurations
    - _Requirements: 5.2, 5.3, 6.4_
  
  - [x] 7.2 Configure Cloud Scheduler and automation
    - Create Cloud Scheduler jobs for daily experiment triggers
    - Implement automated experiment scheduling with configurable parameters
    - Add monitoring and alerting for scheduled job failures
    - _Requirements: 3.1, 5.5, 6.4_

- [x] 8. Implement end-to-end integration and validation
  - [x] 8.1 Create complete deployment automation
    - Write master deployment script that orchestrates all infrastructure setup
    - Implement environment-specific configuration management
    - Add deployment validation and health check automation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [x] 8.2 Add system monitoring and operational tools
    - Implement comprehensive logging and monitoring across all services
    - Create operational dashboards for experiment tracking and system health
    - Add automated alerting for system failures and performance issues
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [x] 8.3 Create integration tests for complete workflow
    - Write end-to-end tests that validate complete experiment execution
    - Create test scenarios for error handling and recovery mechanisms
    - Add performance tests for system scalability and resource utilization
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1_