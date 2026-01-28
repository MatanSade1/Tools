# Recent Improvements to Real-Time Alerts Infrastructure (November 2025)

## Connection Error Handling (Nov 25, 2025 - 9:30 IST Incident)

**Issue:** Service crashed with `SystemExit: 1` when Mixpanel Export API connection was aborted during streaming.

**Fixes Applied:**
- Enhanced error handling for all streaming operations (`iter_lines()` calls)
- Added retry logic (up to 2 retries) with exponential backoff for transient connection errors
- Improved logging with progress tracking during streaming
- Applied fixes to all three streaming functions:
  - `count_distinct_users_export_api()`
  - `fetch_mixpanel_events()`
  - `fetch_total_active_users_from_mixpanel()`

**Impact:** Service now gracefully handles connection errors instead of crashing, automatically retries on transient failures, and returns partial results when possible.

## Timeout Configuration (Nov 25, 2025 - 11:45 IST Incident)

**Issue:** Service was killed by Cloud Run when Mixpanel API stalled before sending first byte, causing `SystemExit: 1` during connection establishment.

**Fixes Applied:**
- Implemented separate connect and read timeouts for Mixpanel API calls
- Connect timeout: 15 seconds (configurable via `MIXPANEL_CONNECT_TIMEOUT`)
- Read timeout: 180 seconds (configurable via `MIXPANEL_READ_TIMEOUT`)
- Prevents Cloud Run worker from being killed during connection stalls

**Impact:** Faster failure detection on connection issues, allowing retry logic to handle transient problems before Cloud Run timeout.

## Alert Logic Bug Fix (Nov 25, 2025)

**Issue:** Alerts were not being sent when Mixpanel API call succeeded. Alert sending logic was incorrectly placed inside exception handler, only executing on API failures.

**Fixes Applied:**
- Moved alert sending logic outside exception block
- Alerts now fire correctly when distinct user count exceeds threshold, regardless of API call path
- Cooldown mechanism and alert sending now execute for both success and fallback scenarios

**Impact:** Alerts now correctly trigger when thresholds are exceeded, fixing issue where `purchase_successful` events with 33+ distinct users weren't alerting despite threshold of 2.0.

## Memory Configuration Updates

### First Update (Nov 25, 2025)
**Issue:** Service was occasionally hitting memory limit errors: "Memory limit of 488 MiB exceeded with 495 MiB used"

**Fix Applied:**
- Increased memory allocation from 512MB to 1024MB (1GB)
- Provides sufficient headroom for processing large Mixpanel Export API responses
- Prevents memory-related crashes during peak event processing

**Impact:** Service now has adequate memory to handle large event streams without hitting memory limits.

### Second Update (Dec 8, 2025)
**Issue:** Service exceeded memory limit again: "Memory limit of 1024 MiB exceeded with 1035 MiB used" at 2025-12-08 03:45:02 GMT

**Fix Applied:**
- Increased memory allocation from 1024MB to 2048MB (2GB)
- Increased CPU allocation from default to 2 CPUs (required for 2GB memory)
- Provides 100% headroom buffer for peak processing loads

**Impact:** Service now has sufficient memory (2GB) and CPU (2 cores) to handle large event streams and memory-intensive operations without hitting limits.

## Additional Environment Variables

- `RT_MP_CONFIG_SHEETS_ID`: Google Sheets spreadsheet ID for configuration (optional)
- `RT_MP_CONFIG_SHEETS_RANGE`: Sheet range to read (default: `Sheet1!A:Z`)
- `RT_MP_VALIDATION_ALERT_RECIPIENTS`: Comma-separated list of recipients for validation error notifications
- `MIXPANEL_CONNECT_TIMEOUT`: Connect timeout in seconds (default: 15)
- `MIXPANEL_READ_TIMEOUT`: Read timeout in seconds (default: 180)

## Updated Troubleshooting Section

- **No alerts sent:** Check Slack webhook URL and channel permissions
- **Timeout errors:** Usually caused by prefix matching (fetching all events) or Mixpanel API connection stalls (now handled with retry logic)
- **Authentication errors:** Verify Mixpanel API credentials
- **Missing events:** Check event names match exactly (case-sensitive)
- **Connection errors:** System now automatically retries up to 2 times with exponential backoff
- **Alerts not firing:** Verify threshold comparison logic (alerts fire when distinct users > threshold)

