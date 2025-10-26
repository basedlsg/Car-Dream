# Cars with a Life - Integration and Performance Tests

This directory contains comprehensive end-to-end integration tests and performance tests for the Cars with a Life autonomous driving system.

## Test Structure

```
tests/
├── integration/
│   └── test_complete_workflow.py    # End-to-end workflow tests
├── performance_config.json          # Performance test configuration
├── requirements.txt                 # Python test dependencies
├── run_integration_tests.sh         # Main test runner script
└── README.md                        # This file
```

## Prerequisites

### System Requirements
- Python 3.8+
- Google Cloud SDK (gcloud)
- Active GCP project with Cars with a Life deployed
- Proper authentication (gcloud auth login)

### Environment Variables
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export ENVIRONMENT="development"  # or staging/production
```

### Service URLs (automatically detected)
- Orchestrator Service URL
- Reporter Service URL

## Running Tests

### Quick Start
```bash
# Run all integration tests
./tests/run_integration_tests.sh

# Run tests for specific environment
./tests/run_integration_tests.sh --environment staging --project my-project

# Run tests with custom timeout
./tests/run_integration_tests.sh --timeout 1800 --parallel
```

### Individual Test Components

#### 1. Complete Workflow Test
Tests the entire experiment lifecycle:
- Experiment submission
- CARLA simulation execution
- AI decision making
- Data storage and retrieval
- Report generation
- Metrics calculation

```bash
# Run directly with pytest
cd tests
pytest integration/test_complete_workflow.py::test_complete_workflow -v
```

#### 2. Error Handling Tests
Validates system resilience:
- Invalid input handling
- Service timeout management
- Recovery mechanisms
- Graceful degradation

```bash
pytest integration/test_complete_workflow.py::test_error_handling -v
```

#### 3. Performance Tests
Measures system performance:
- Concurrent experiment handling
- Response time validation
- Resource utilization
- Scalability limits

```bash
pytest integration/test_complete_workflow.py::test_performance -v
```

## Test Configuration

### Performance Thresholds
Edit `performance_config.json` to adjust test parameters:

```json
{
  "performance_thresholds": {
    "max_response_time_ms": 5000,
    "min_success_rate": 0.95,
    "max_error_rate": 0.05
  }
}
```

### Environment-Specific Settings
Tests automatically adapt to different environments:
- **Development**: Shorter timeouts, basic validation
- **Staging**: Full validation, performance testing
- **Production**: Read-only tests, monitoring validation

## Test Results

### Output Formats
- **Console**: Real-time test progress and results
- **JUnit XML**: `test-results-*/junit.xml` for CI/CD integration
- **HTML Report**: `test-results-*/report.html` for detailed analysis
- **Markdown Report**: `integration-test-report-*.md` for documentation

### Success Criteria
Tests pass when:
- ✅ All services are healthy and responsive
- ✅ Complete experiment workflow executes successfully
- ✅ Data is stored and retrieved correctly
- ✅ Performance meets defined thresholds
- ✅ Error handling works as expected

### Failure Investigation
When tests fail:
1. Check the generated HTML report for detailed error information
2. Review system health using `./deploy/health-check-automation.sh`
3. Examine service logs in Google Cloud Console
4. Verify resource utilization and scaling

## Continuous Integration

### GitHub Actions Example
```yaml
name: Integration Tests
on: [push, pull_request]
jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r tests/requirements.txt
      - name: Run integration tests
        run: ./tests/run_integration_tests.sh --environment staging
        env:
          GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_SA_KEY }}
```

### Jenkins Pipeline Example
```groovy
pipeline {
    agent any
    environment {
        GCP_PROJECT_ID = credentials('gcp-project-id')
        GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-service-account')
    }
    stages {
        stage('Integration Tests') {
            steps {
                sh './tests/run_integration_tests.sh --environment staging --parallel'
            }
            post {
                always {
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'test-results-*',
                        reportFiles: 'report.html',
                        reportName: 'Integration Test Report'
                    ])
                }
            }
        }
    }
}
```

## Monitoring and Alerting

### Test Metrics
The integration tests generate metrics that can be monitored:
- Test execution duration
- Success/failure rates
- Performance measurements
- Resource utilization during tests

### Automated Alerts
Set up alerts for:
- Test failures in CI/CD pipelines
- Performance degradation trends
- System availability issues
- Resource exhaustion during tests

## Troubleshooting

### Common Issues

#### Authentication Errors
```bash
# Re-authenticate with gcloud
gcloud auth login
gcloud auth application-default login
```

#### Service Unavailable
```bash
# Check service health
./deploy/health-check-automation.sh --check

# Verify service URLs
gcloud run services list --region=us-central1
```

#### Timeout Issues
```bash
# Increase test timeout
./tests/run_integration_tests.sh --timeout 3600

# Check system performance
gcloud monitoring dashboards list
```

#### Resource Constraints
```bash
# Scale up services temporarily
./deploy/incident-response/emergency-scale-up.sh

# Check resource utilization
gcloud compute instances list
gcloud run services describe orchestrator --region=us-central1
```

### Debug Mode
Enable verbose logging:
```bash
export PYTEST_VERBOSE=1
export LOG_LEVEL=DEBUG
./tests/run_integration_tests.sh
```

## Best Practices

### Test Development
- Write tests that are independent and can run in any order
- Use proper setup and teardown to avoid test pollution
- Include both positive and negative test cases
- Test error conditions and edge cases
- Keep tests focused and atomic

### Performance Testing
- Establish baseline performance metrics
- Test under realistic load conditions
- Monitor resource utilization during tests
- Include gradual load increase (ramp-up)
- Test system recovery after load

### Maintenance
- Run tests regularly (daily/weekly)
- Update test data and scenarios periodically
- Review and adjust performance thresholds
- Keep test dependencies up to date
- Document test failures and resolutions

## Contributing

### Adding New Tests
1. Create test files in appropriate subdirectories
2. Follow existing naming conventions
3. Include proper documentation and comments
4. Add test cases to the main test runner
5. Update this README with new test information

### Test Data Management
- Use unique identifiers for test data
- Clean up test data after execution
- Avoid using production data in tests
- Use realistic but synthetic test scenarios

## Support

For issues with the integration tests:
1. Check this documentation first
2. Review the generated test reports
3. Examine system logs and monitoring
4. Contact the development team with specific error details

---

**Note**: These tests validate the complete Cars with a Life system. Ensure all services are properly deployed and configured before running the integration test suite.