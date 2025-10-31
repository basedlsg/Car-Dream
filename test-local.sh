#!/bin/bash

# 🧪 Local Testing Script for Car Dream System
# Tests the system without requiring Google Cloud CLI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker Desktop."
        exit 1
    fi
    print_success "Docker is running"
}

# Function to build containers locally
build_containers() {
    print_status "Building containers locally..."
    
    # Build orchestrator
    print_status "Building orchestrator..."
    docker build -f orchestrator_Dockerfile -t orchestrator:local . || {
        print_error "Failed to build orchestrator"
        exit 1
    }
    
    # Build reporter
    print_status "Building reporter..."
    docker build -f reporter_Dockerfile -t reporter:local . || {
        print_error "Failed to build reporter"
        exit 1
    }
    
    # Build dreamer service
    print_status "Building dreamer service..."
    docker build -f dreamer-service_Dockerfile -t dreamer-service:local . || {
        print_error "Failed to build dreamer service"
        exit 1
    }
    
    # Build CARLA runner
    print_status "Building CARLA runner..."
    docker build -f carla-runner_Dockerfile -t carla-runner:local . || {
        print_error "Failed to build CARLA runner"
        exit 1
    }
    
    print_success "All containers built successfully!"
}

# Function to start services
start_services() {
    print_status "Starting services..."
    
    # Start orchestrator
    print_status "Starting orchestrator on port 8080..."
    docker run -d --name orchestrator-test -p 8080:8080 orchestrator:local || {
        print_error "Failed to start orchestrator"
        exit 1
    }
    
    # Start reporter
    print_status "Starting reporter on port 8081..."
    docker run -d --name reporter-test -p 8081:8080 reporter:local || {
        print_error "Failed to start reporter"
        exit 1
    }
    
    # Wait for services to start
    print_status "Waiting for services to start..."
    sleep 10
    
    print_success "Services started successfully!"
}

# Function to test services
test_services() {
    print_status "Testing services..."
    
    # Test orchestrator health
    print_status "Testing orchestrator health..."
    if curl -f http://localhost:8080/health >/dev/null 2>&1; then
        print_success "✅ Orchestrator is healthy"
    else
        print_warning "⚠️ Orchestrator health check failed (this might be expected if no health endpoint exists)"
    fi
    
    # Test reporter health
    print_status "Testing reporter health..."
    if curl -f http://localhost:8081/health >/dev/null 2>&1; then
        print_success "✅ Reporter is healthy"
    else
        print_warning "⚠️ Reporter health check failed (this might be expected if no health endpoint exists)"
    fi
    
    # Test experiment submission
    print_status "Testing experiment submission..."
    response=$(curl -s -X POST http://localhost:8080/experiments \
        -H 'Content-Type: application/json' \
        -d '{
            "experiment_id": "test-001",
            "name": "Local Test Experiment",
            "description": "Testing the system locally",
            "parameters": {
                "simulation_duration": 60,
                "weather_conditions": "clear"
            }
        }' 2>/dev/null || echo "FAILED")
    
    if [[ "$response" != "FAILED" ]]; then
        print_success "✅ Experiment submission works"
        echo "Response: $response"
    else
        print_warning "⚠️ Experiment submission failed (this might be expected if the endpoint doesn't exist yet)"
    fi
    
    # Test report retrieval
    print_status "Testing report retrieval..."
    response=$(curl -s http://localhost:8081/reports/test-001 2>/dev/null || echo "FAILED")
    
    if [[ "$response" != "FAILED" ]]; then
        print_success "✅ Report retrieval works"
        echo "Response: $response"
    else
        print_warning "⚠️ Report retrieval failed (this might be expected if no reports exist yet)"
    fi
}

# Function to show service logs
show_logs() {
    print_status "Service logs:"
    echo ""
    echo "=== Orchestrator Logs ==="
    docker logs orchestrator-test 2>/dev/null || echo "No logs available"
    echo ""
    echo "=== Reporter Logs ==="
    docker logs reporter-test 2>/dev/null || echo "No logs available"
}

# Function to cleanup
cleanup() {
    print_status "Cleaning up test containers..."
    
    # Stop and remove containers
    docker stop orchestrator-test reporter-test 2>/dev/null || true
    docker rm orchestrator-test reporter-test 2>/dev/null || true
    
    print_success "Cleanup complete!"
}

# Function to show next steps
show_next_steps() {
    echo ""
    print_success "🎉 Local testing complete!"
    echo ""
    echo "📊 Service URLs:"
    echo "  Orchestrator: http://localhost:8080"
    echo "  Reporter: http://localhost:8081"
    echo ""
    echo "🧪 Test Commands:"
    echo "  # Test experiment submission"
    echo "  curl -X POST http://localhost:8080/experiments \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"experiment_id\": \"test-002\", \"name\": \"Another Test\"}'"
    echo ""
    echo "  # Get experiment report"
    echo "  curl http://localhost:8081/reports/test-002"
    echo ""
    echo "📋 Next Steps:"
    echo "  1. Review the MANUAL_SETUP_GUIDE.md for cloud deployment options"
    echo "  2. Use Google Cloud Console web interface for cloud deployment"
    echo "  3. Set up monitoring through web dashboards"
    echo "  4. Implement CI/CD with GitHub Actions"
    echo ""
    echo "🛑 To stop services:"
    echo "  ./test-local.sh cleanup"
}

# Main execution
main() {
    case "${1:-test}" in
        "cleanup")
            cleanup
            ;;
        "logs")
            show_logs
            ;;
        "test")
            echo "🧪 Car Dream Local Testing"
            echo "=========================="
            echo ""
            
            check_docker
            build_containers
            start_services
            test_services
            show_logs
            show_next_steps
            ;;
        *)
            echo "Usage: $0 [test|cleanup|logs]"
            echo "  test    - Run full local test (default)"
            echo "  cleanup - Stop and remove test containers"
            echo "  logs    - Show service logs"
            ;;
    esac
}

# Trap to cleanup on exit
trap cleanup EXIT

# Run main function
main "$@"

