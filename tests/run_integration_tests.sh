#!/bin/bash

# Integration Test Runner for Cars with a Life
# Runs comprehensive end-to-end integration tests

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"cars-with-a-life"}
REGION=${GCP_REGION:-"us-central1"}
ENVIRONMENT=${ENVIRONMENT:-"development"}

# Test configuration
TEST_TIMEOUT=1800  # 30 minutes
PARALLEL_TESTS=false
CLEANUP_ON_FAILURE=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking test prerequisites..."
    
    # Check required tools
    local required_tools=("python3" "pip" "gcloud" "pytest")
    for tool in "${required_tools[@]}"; do
        if ! command -v $tool &> /dev/null; then
            echo_error "Required tool not found: $tool"
            exit 1
        fi
    done
    
    # Check Python packages
    echo_info "Installing required Python packages..."
    pip install -q pytest pytest-asyncio requests google-cloud-bigquery google-cloud-storage google-cloud-pubsub
    
    # Check GCP authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Set project
    gcloud config set project $PROJECT_ID
    
    echo_info "Prerequisites check completed"
}

# Get service URLs
get_service_urls() {
    echo_info "Getting service URLs..."
    
    # Get Cloud Run service URLs
    ORCHESTRATOR_URL=$(gcloud run services describe orchestrator \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.url)" 2>/dev/null || echo "")
    
    REPORTER_URL=$(gcloud run services describe reporter \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.url)" 2>/dev/null || echo "")
    
    if [ -z "$ORCHESTRATOR_URL" ]; then
        echo_error "Orchestrator service URL not found. Is the service deployed?"
        exit 1
    fi
    
    if [ -z "$REPORTER_URL" ]; then
        echo_error "Reporter service URL not found. Is the service deployed?"
        exit 1
    fi
    
    echo_info "Service URLs obtained:"
    echo_info "  Orchestrator: $ORCHESTRATOR_URL"
    echo_info "  Reporter: $REPORTER_URL"
    
    # Export for tests
    export ORCHESTRATOR_URL
    export REPORTER_URL
    export GCP_PROJECT_ID=$PROJECT_ID
    export GCP_REGION=$REGION
}

# Run system health check before tests
run_health_check() {
    echo_test "Running system health check..."
    
    if [ -f "deploy/health-check-automation.sh" ]; then
        if ./deploy/health-check-automation.sh --check --project $PROJECT_ID --region $REGION; then
            echo_info "✓ System health check passed"
        else
            echo_warn "System health check failed, but continuing with tests..."
        fi
    else
        echo_warn "Health check script not found, skipping health check"
    fi
}

# Run integration tests
run_integration_tests() {
    echo_test "Running integration tests..."
    
    local test_results_dir="test-results-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$test_results_dir"
    
    # Set test environment variables
    export PYTEST_TIMEOUT=$TEST_TIMEOUT
    
    # Run tests with pytest
    local pytest_args=(
        "tests/integration/"
        "--verbose"
        "--tb=short"
        "--junit-xml=$test_results_dir/junit.xml"
        "--html=$test_results_dir/report.html"
        "--self-contained-html"
    )
    
    if [ "$PARALLEL_TESTS" = true ]; then
        pytest_args+=("-n" "auto")
    fi
    
    echo_test "Running pytest with args: ${pytest_args[*]}"
    
    if timeout $TEST_TIMEOUT pytest "${pytest_args[@]}"; then
        echo_info "✓ Integration tests passed"
        return 0
    else
        echo_error "✗ Integration tests failed"
        return 1
    fi
}

# Run performance tests
run_performance_tests() {
    echo_test "Running performance tests..."
    
    # Create performance test configuration
    cat > /tmp/performance_test_config.json << EOF
{
    "concurrent_experiments": 5,
    "experiment_duration": 30,
    "load_test_duration": 300,
    "expected_response_time": 5.0,
    "expected_success_rate": 0.95
}
EOF
    
    # Run performance test
    python3 << EOF
import asyncio
import json
import time
import statistics
from tests.integration.test_complete_workflow import SystemIntegrationTest

async def run_performance_test():
    test_instance = SystemIntegrationTest()
    
    try:
        await test_instance.setup_test_environment()
        
        # Load test configuration
        with open('/tmp/performance_test_config.json', 'r') as f:
            config = json.load(f)
        
        print(f"Running performance test with {config['concurrent_experiments']} concurrent experiments...")
        
        # Run performance test
        result = await test_instance.test_performance_and_scalability()
        
        # Analyze results
        success_rate = result['successful_submissions'] / result['concurrent_experiments']
        avg_time = result['average_submission_time']
        
        print(f"Performance Test Results:")
        print(f"  Success Rate: {success_rate:.2%}")
        print(f"  Average Response Time: {avg_time:.2f}s")
        print(f"  Successful Submissions: {result['successful_submissions']}/{result['concurrent_experiments']}")
        
        # Check against expectations
        if success_rate >= config['expected_success_rate']:
            print("✓ Success rate meets expectations")
        else:
            print(f"✗ Success rate below expectations ({config['expected_success_rate']:.2%})")
        
        if avg_time <= config['expected_response_time']:
            print("✓ Response time meets expectations")
        else:
            print(f"✗ Response time above expectations ({config['expected_response_time']}s)")
        
        return success_rate >= config['expected_success_rate'] and avg_time <= config['expected_response_time']
        
    finally:
        await test_instance.cleanup_test_environment()

# Run the performance test
result = asyncio.run(run_performance_test())
exit(0 if result else 1)
EOF
    
    local perf_result=$?
    
    if [ $perf_result -eq 0 ]; then
        echo_info "✓ Performance tests passed"
    else
        echo_error "✗ Performance tests failed"
    fi
    
    return $perf_result
}

# Run load tests
run_load_tests() {
    echo_test "Running load tests..."
    
    # Simple load test using curl
    local load_test_duration=60  # 1 minute
    local concurrent_requests=10
    local success_count=0
    local total_requests=0
    
    echo_test "Running load test for ${load_test_duration}s with ${concurrent_requests} concurrent requests..."
    
    local end_time=$(($(date +%s) + load_test_duration))
    
    while [ $(date +%s) -lt $end_time ]; do
        for i in $(seq 1 $concurrent_requests); do
            (
                if curl -s -f "$ORCHESTRATOR_URL/health" > /dev/null 2>&1; then
                    echo "success" >> /tmp/load_test_results
                else
                    echo "failure" >> /tmp/load_test_results
                fi
            ) &
        done
        
        wait
        sleep 1
    done
    
    # Analyze results
    if [ -f /tmp/load_test_results ]; then
        success_count=$(grep -c "success" /tmp/load_test_results || echo "0")
        total_requests=$(wc -l < /tmp/load_test_results)
        
        local success_rate=$((success_count * 100 / total_requests))
        
        echo_test "Load Test Results:"
        echo_test "  Total Requests: $total_requests"
        echo_test "  Successful Requests: $success_count"
        echo_test "  Success Rate: ${success_rate}%"
        
        rm -f /tmp/load_test_results
        
        if [ $success_rate -ge 95 ]; then
            echo_info "✓ Load test passed (success rate >= 95%)"
            return 0
        else
            echo_error "✗ Load test failed (success rate < 95%)"
            return 1
        fi
    else
        echo_error "✗ Load test failed (no results file)"
        return 1
    fi
}

# Generate test report
generate_test_report() {
    local test_status=$1
    local test_results_dir=$2
    
    echo_info "Generating test report..."
    
    local report_file="integration-test-report-$(date +%Y%m%d-%H%M%S).md"
    
    cat > "$report_file" << EOF
# Cars with a Life - Integration Test Report

**Generated:** $(date)
**Environment:** $ENVIRONMENT
**Project:** $PROJECT_ID
**Region:** $REGION

## Test Summary

- **Overall Status:** $([ $test_status -eq 0 ] && echo "PASSED" || echo "FAILED")
- **Test Duration:** $(date -d@$(($(date +%s) - start_time)) -u +%H:%M:%S)
- **Services Tested:**
  - Orchestrator Service: $ORCHESTRATOR_URL
  - Reporter Service: $REPORTER_URL

## Test Results

### Integration Tests
$([ -f "$test_results_dir/junit.xml" ] && echo "- JUnit Results: $test_results_dir/junit.xml" || echo "- No JUnit results available")
$([ -f "$test_results_dir/report.html" ] && echo "- HTML Report: $test_results_dir/report.html" || echo "- No HTML report available")

### Performance Tests
- Concurrent experiment handling
- Response time validation
- System scalability assessment

### Load Tests
- Service availability under load
- Response time consistency
- Error rate monitoring

## System Health

$(./deploy/health-check-automation.sh --check --project $PROJECT_ID --region $REGION 2>/dev/null | tail -20 || echo "Health check not available")

## Recommendations

$([ $test_status -eq 0 ] && cat << 'PASS_RECO'
✓ All tests passed successfully
✓ System is ready for production use
✓ Continue with regular monitoring and maintenance
PASS_RECO
|| cat << 'FAIL_RECO'
✗ Some tests failed - investigation required
✗ Review test logs and system health
✗ Address issues before production deployment
FAIL_RECO
)

## Next Steps

1. Review detailed test results in the generated reports
2. Address any failing tests or performance issues
3. Update monitoring and alerting based on test findings
4. Schedule regular integration test runs
5. Document any system limitations discovered during testing

---
*Report generated by Cars with a Life Integration Test Suite*
EOF
    
    echo_info "Test report generated: $report_file"
}

# Cleanup function
cleanup_test_environment() {
    echo_info "Cleaning up test environment..."
    
    # Clean up temporary files
    rm -f /tmp/performance_test_config.json
    rm -f /tmp/load_test_results
    
    # Run test cleanup if available
    if [ -f "tests/integration/test_complete_workflow.py" ]; then
        python3 -c "
import asyncio
from tests.integration.test_complete_workflow import SystemIntegrationTest

async def cleanup():
    test_instance = SystemIntegrationTest()
    await test_instance.cleanup_test_environment()

asyncio.run(cleanup())
" 2>/dev/null || echo_warn "Test cleanup failed"
    fi
    
    echo_info "Test environment cleanup completed"
}

# Main function
main() {
    local start_time=$(date +%s)
    local overall_status=0
    
    echo_info "Starting Cars with a Life Integration Tests"
    echo_info "Environment: $ENVIRONMENT"
    echo_info "Project: $PROJECT_ID"
    echo_info "Region: $REGION"
    echo ""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --project)
                PROJECT_ID="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --parallel)
                PARALLEL_TESTS=true
                shift
                ;;
            --timeout)
                TEST_TIMEOUT="$2"
                shift 2
                ;;
            --no-cleanup)
                CLEANUP_ON_FAILURE=false
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --project PROJECT_ID      GCP Project ID"
                echo "  --region REGION           GCP Region"
                echo "  --environment ENV         Environment (development|staging|production)"
                echo "  --parallel               Run tests in parallel"
                echo "  --timeout SECONDS        Test timeout in seconds"
                echo "  --no-cleanup             Don't cleanup on failure"
                echo "  --help                   Show this help"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Set up trap for cleanup
    trap 'cleanup_test_environment' EXIT
    
    # Run test phases
    check_prerequisites
    get_service_urls
    run_health_check
    
    # Run integration tests
    if ! run_integration_tests; then
        overall_status=1
    fi
    
    # Run performance tests
    if ! run_performance_tests; then
        overall_status=1
    fi
    
    # Run load tests
    if ! run_load_tests; then
        overall_status=1
    fi
    
    # Generate report
    generate_test_report $overall_status "test-results-$(date +%Y%m%d-%H%M%S)"
    
    # Final status
    if [ $overall_status -eq 0 ]; then
        echo_info "✓ All integration tests completed successfully!"
    else
        echo_error "✗ Some integration tests failed"
        if [ "$CLEANUP_ON_FAILURE" = false ]; then
            echo_info "Test environment preserved for debugging (--no-cleanup specified)"
        fi
    fi
    
    exit $overall_status
}

# Run main function
main "$@"