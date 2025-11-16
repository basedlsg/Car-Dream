# BigQuery Timeout Issue - Fix Documentation

## Problem Summary

The BigQuery dataset creation was failing with timeout errors:

```
BigQuery error in mk operation: Could not connect with BigQuery server due to:
TimeoutError(60, 'Operation timed out')
```

This issue prevented the `cars_with_a_life` dataset from being created, blocking the deployment process.

## Root Causes

The timeout can occur due to several reasons:

1. **Transient GCP Issues**: Google Cloud occasionally experiences regional or global service delays
2. **Network Connectivity**: Firewall rules, VPN configurations, or corporate proxies may interfere
3. **API Propagation Delays**: Newly enabled APIs or freshly created projects may need time to propagate
4. **Default Timeout Too Short**: The default 60-second timeout may be insufficient for complex operations
5. **Rate Limiting**: Rapid successive API calls can trigger throttling

## Solutions Implemented

### 1. Enhanced Shell Script (`setup-bigquery.sh`)

**Improvements made:**

- ✅ **Exponential Backoff Retry Logic**: Automatically retries failed operations with increasing delays (2s, 4s, 8s, 16s)
- ✅ **Maximum 4 Retry Attempts**: Follows GCP best practices for network operations
- ✅ **Increased Timeouts**: Extended timeout from 60s to 300s (5 minutes)
- ✅ **API Enablement Check**: Ensures BigQuery API is enabled before attempting operations
- ✅ **Better Error Messages**: Provides clear troubleshooting guidance on failure
- ✅ **Idempotent Operations**: Safe to run multiple times without side effects

**Key changes:**

```bash
# Retry configuration
MAX_RETRIES=4
INITIAL_BACKOFF=2
BQ_TIMEOUT=300  # 5 minutes

# Retry function with exponential backoff
retry_with_backoff() {
    local max_attempts=$1
    shift
    local command=("$@")
    local attempt=1
    local backoff=$INITIAL_BACKOFF

    while [ $attempt -le $max_attempts ]; do
        if "${command[@]}"; then
            return 0
        fi
        if [ $attempt -lt $max_attempts ]; then
            sleep $backoff
            backoff=$((backoff * 2))
        fi
        attempt=$((attempt + 1))
    done
    return 1
}
```

**Operations with retry logic:**

- BigQuery dataset creation
- BigQuery table creation
- Cloud Storage bucket creation
- IAM policy binding

### 2. Python Alternative Script (`setup-bigquery-python.py`)

Created a Python-based alternative using the BigQuery Python client library, which provides:

- ✅ **Native Retry Mechanism**: Uses Google's built-in retry logic
- ✅ **Better Timeout Control**: Fine-grained control over API call timeouts
- ✅ **Enhanced Error Handling**: More detailed error messages and exceptions
- ✅ **Direct API Access**: Bypasses potential CLI tool issues

**Features:**

- Exponential backoff with configurable parameters
- Custom retry predicates for specific error types
- 5-minute default timeout per operation
- Comprehensive error messages with troubleshooting steps

**Usage:**

```bash
# Set project ID
export PROJECT_ID=your-project-id

# Run Python script
python3 deploy/setup-bigquery-python.py
```

**Requirements:**

```bash
pip install google-cloud-bigquery
```

## Usage Instructions

### Option 1: Enhanced Shell Script (Recommended First)

```bash
cd /path/to/Car-Dream
export PROJECT_ID=your-project-id

# Run the improved script
./deploy/setup-bigquery.sh
```

The script will:
1. Check if BigQuery API is enabled
2. Attempt to create the dataset with retry logic
3. Create tables with retry logic
4. Set up Cloud Storage buckets with retry logic
5. Configure IAM permissions

### Option 2: Python Alternative (If Shell Script Fails)

If the shell script continues to timeout after multiple retries:

```bash
# Ensure you have the required library
pip install google-cloud-bigquery

# Set project ID
export PROJECT_ID=your-project-id

# Run Python alternative
python3 deploy/setup-bigquery-python.py
```

## Troubleshooting Steps

If you continue to experience timeout issues:

### 1. Check Google Cloud Service Status

Visit https://status.cloud.google.com/ to check for ongoing incidents affecting BigQuery.

### 2. Verify API Enablement

```bash
# Check if BigQuery API is enabled
gcloud services list --enabled --filter="name:bigquery.googleapis.com"

# Enable if not already enabled
gcloud services enable bigquery.googleapis.com --project=your-project-id
```

### 3. Test Basic Connectivity

```bash
# Test if you can list datasets
bq --project_id=your-project-id ls

# Test if you can reach BigQuery API
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  https://bigquery.googleapis.com/bigquery/v2/projects/your-project-id/datasets
```

### 4. Check Network Configuration

- **Corporate VPN/Proxy**: Try disconnecting from VPN or switching networks
- **Firewall Rules**: Ensure outbound HTTPS to `*.googleapis.com` is allowed
- **DNS Issues**: Try using Google's DNS (8.8.8.8) temporarily

### 5. Verify Permissions

```bash
# Check your permissions
gcloud projects get-iam-policy your-project-id --flatten="bindings[].members" \
  --filter="bindings.members:user:your-email@example.com"
```

Required roles:
- `roles/bigquery.admin` or `roles/bigquery.dataEditor`
- `roles/storage.admin` or `roles/storage.objectAdmin`

### 6. Try Manual Creation

If automated scripts fail, try creating the dataset manually:

**Via Cloud Console:**
1. Go to https://console.cloud.google.com/bigquery?project=your-project-id
2. Click "CREATE DATASET"
3. Set Dataset ID: `cars_with_a_life`
4. Set Location: `US (multiple regions in United States)`
5. Click "CREATE DATASET"

**Via gcloud:**
```bash
bq mk --location=US --description="Dataset for Cars with a Life autonomous driving experiments" \
  your-project-id:cars_with_a_life
```

### 7. Check Quota and Limits

```bash
# Check quota usage
gcloud compute project-info describe --project=your-project-id
```

Visit https://console.cloud.google.com/iam-admin/quotas?project=your-project-id

## Testing the Fix

After applying the fixes, test the deployment:

```bash
# Full test
./deploy/setup-bigquery.sh

# If that fails, try Python alternative
python3 ./deploy/setup-bigquery-python.py

# Verify dataset was created
bq ls --project_id=your-project-id | grep cars_with_a_life

# Verify tables were created
bq ls --project_id=your-project-id:cars_with_a_life
```

Expected output:
```
 datasetId          location
 cars_with_a_life   US
```

## Performance Improvements

The enhanced scripts provide:

- **Faster Recovery**: Automatic retry reduces manual intervention
- **Better Reliability**: Handles transient errors gracefully
- **Clearer Feedback**: Detailed progress and error messages
- **Flexibility**: Two different approaches (shell and Python)

## Monitoring and Logging

The scripts now provide detailed logging:

```
[YELLOW] Attempt 1 of 4...
[GREEN] BigQuery API enabled
[YELLOW] Waiting for API to propagate...
[YELLOW] Creating BigQuery dataset...
[YELLOW] Dataset not found, creating with retry logic...
[GREEN] BigQuery dataset created: cars_with_a_life
```

## Best Practices

1. **Always Check Status First**: Visit status.cloud.google.com before debugging
2. **Use Retry Logic**: Network operations should always have retry mechanisms
3. **Increase Timeouts Gradually**: Start with 2-5 minutes for GCP operations
4. **Monitor Rate Limits**: Avoid rapid successive API calls
5. **Use Python Client**: When CLI tools fail, Python clients often work better

## Related Files

- `/deploy/setup-bigquery.sh` - Enhanced shell script with retry logic
- `/deploy/setup-bigquery-python.py` - Python alternative implementation
- `/deploy/schemas/*.sql` - BigQuery table schemas
- `/deploy/deploy.sh` - Main deployment orchestrator

## Support

If issues persist after trying all troubleshooting steps:

1. Check Google Cloud Status Dashboard
2. Review Google Cloud Audit Logs
3. Contact Google Cloud Support with:
   - Project ID
   - Error messages
   - Steps taken
   - Network configuration details

## Version History

- **v1.0** (Initial): Basic dataset creation without retry logic
- **v2.0** (Current): Added exponential backoff, increased timeouts, Python alternative

## Additional Resources

- [Google Cloud Status Dashboard](https://status.cloud.google.com/)
- [BigQuery API Reference](https://cloud.google.com/bigquery/docs/reference/rest)
- [BigQuery Python Client](https://googleapis.dev/python/bigquery/latest/)
- [Exponential Backoff Best Practices](https://cloud.google.com/iot/docs/how-tos/exponential-backoff)
