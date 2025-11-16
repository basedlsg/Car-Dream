# Quick Fix Guide: BigQuery Timeout Issue

## TL;DR - Quick Fix

If you're experiencing BigQuery timeout errors, here's the fastest way to resolve it:

### Method 1: Use the Enhanced Script (Recommended)

```bash
export PROJECT_ID=your-project-id
./deploy/setup-bigquery.sh
```

The script now automatically:
- ✅ Retries failed operations up to 4 times
- ✅ Uses exponential backoff (2s, 4s, 8s, 16s delays)
- ✅ Extends timeout to 5 minutes
- ✅ Checks API enablement

### Method 2: Use Python Alternative (If Method 1 Fails)

```bash
pip install google-cloud-bigquery  # Usually already installed
export PROJECT_ID=your-project-id
python3 ./deploy/setup-bigquery-python.py
```

## What Was Fixed?

### Before (Problem)
```
BigQuery error in mk operation: Could not connect with BigQuery server due to:
TimeoutError(60, 'Operation timed out')
```

### After (Solution)

1. **Added Retry Logic**: Automatically retries 4 times with exponential backoff
2. **Increased Timeout**: 60s → 300s (5 minutes)
3. **Better Error Handling**: Clear messages and troubleshooting guidance
4. **Python Alternative**: Uses BigQuery Python client as fallback
5. **API Checks**: Ensures BigQuery API is enabled before operations

## Changes Made

### Files Modified:
- ✏️ `/deploy/setup-bigquery.sh` - Enhanced with retry logic and better error handling

### Files Created:
- ➕ `/deploy/setup-bigquery-python.py` - Python alternative implementation
- ➕ `/deploy/BIGQUERY_TIMEOUT_FIX.md` - Comprehensive troubleshooting guide
- ➕ `/deploy/QUICK_FIX_GUIDE.md` - This quick reference

## Verify the Fix

```bash
# Check if dataset was created
bq ls --project_id=$PROJECT_ID | grep cars_with_a_life

# Expected output:
# cars_with_a_life   US

# Check if tables were created
bq ls --project_id=$PROJECT_ID:cars_with_a_life

# Expected output:
# experiments
# autonomous_notes
# evaluation_metrics
```

## Still Having Issues?

### 1. Check Google Cloud Status
Visit: https://status.cloud.google.com/

### 2. Enable BigQuery API Manually
```bash
gcloud services enable bigquery.googleapis.com --project=$PROJECT_ID
```

### 3. Test Basic Connectivity
```bash
bq --project_id=$PROJECT_ID ls
```

### 4. Try Different Network
- Disconnect from VPN
- Use mobile hotspot
- Try from different location

### 5. Create Dataset Manually
Web Console: https://console.cloud.google.com/bigquery?project=$PROJECT_ID

1. Click "CREATE DATASET"
2. Dataset ID: `cars_with_a_life`
3. Location: `US (multiple regions in United States)`
4. Click "CREATE DATASET"

## Technical Details

### Retry Configuration
- **Max Retries**: 4 attempts
- **Initial Backoff**: 2 seconds
- **Backoff Multiplier**: 2x (exponential)
- **Total Max Wait**: ~30 seconds across all retries
- **Operation Timeout**: 300 seconds (5 minutes)

### Error Handling
The scripts now handle these error scenarios:
- ⏱️ Timeout errors (retries with backoff)
- 🔒 Permission errors (clear guidance)
- 🌐 Network errors (retry with exponential delay)
- ⚠️ API not enabled (attempts to enable)
- ✅ Resource already exists (continues safely)

## Example Output

### Successful Run
```
Setting up BigQuery and Cloud Storage for Cars with a Life...
Project ID: vertex-test-1-467818
Dataset: cars_with_a_life
Location: US
Ensuring BigQuery API is enabled...
BigQuery API enabled
Waiting for API to propagate...
Creating BigQuery dataset...
Attempt 1 of 4...
BigQuery dataset created: cars_with_a_life
Creating BigQuery tables from schema files...
Creating experiments table...
Attempt 1 of 4...
experiments table created successfully
...
Data infrastructure setup completed successfully!
```

### With Retry
```
Creating BigQuery dataset...
Attempt 1 of 4...
Command failed, retrying in 2s...
Attempt 2 of 4...
Command failed, retrying in 4s...
Attempt 3 of 4...
BigQuery dataset created: cars_with_a_life
```

## Prevention Tips

1. **Network Stability**: Use stable, fast internet connection
2. **API Warmup**: Wait 10-30 seconds after enabling APIs
3. **Avoid Rapid Calls**: Space out deployment attempts
4. **Check Status First**: Always check https://status.cloud.google.com/
5. **Use Python Client**: For critical operations, Python client is more reliable

## Related Documentation

- 📖 Full troubleshooting guide: `/deploy/BIGQUERY_TIMEOUT_FIX.md`
- 🔧 Enhanced bash script: `/deploy/setup-bigquery.sh`
- 🐍 Python alternative: `/deploy/setup-bigquery-python.py`

## Support Checklist

Before asking for help, please verify:
- [ ] Checked Google Cloud Status Dashboard
- [ ] Verified BigQuery API is enabled
- [ ] Tried both bash and Python scripts
- [ ] Tested basic `bq ls` command works
- [ ] Tried from different network/location
- [ ] Waited at least 10 minutes between attempts
- [ ] Checked project permissions

## One-Liner Solutions

```bash
# Quick deploy with new fixes
export PROJECT_ID=your-project-id && ./deploy/setup-bigquery.sh

# Python alternative one-liner
export PROJECT_ID=your-project-id && python3 ./deploy/setup-bigquery-python.py

# Check if BigQuery API is enabled
gcloud services list --enabled | grep bigquery

# Enable BigQuery API and wait
gcloud services enable bigquery.googleapis.com && sleep 10

# Manual dataset creation
bq mk --location=US --description="Cars with a Life dataset" $PROJECT_ID:cars_with_a_life
```

## Success Criteria

✅ Script completes without errors
✅ Dataset `cars_with_a_life` is created
✅ Three tables are created: experiments, autonomous_notes, evaluation_metrics
✅ Cloud Storage buckets are created
✅ IAM permissions are set

Run `bq ls --project_id=$PROJECT_ID:cars_with_a_life` to verify all tables exist.

---

**Last Updated**: 2025-10-31
**Version**: 2.0 (with retry logic and Python alternative)
