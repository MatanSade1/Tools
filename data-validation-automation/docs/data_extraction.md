# Data Extraction Component (create_csv.py)

## Overview
The data extraction component is responsible for efficiently retrieving and sampling game event data from BigQuery. It implements intelligent sampling strategies to handle large datasets while maintaining statistical significance.

## Key Features

### 1. Intelligent Sampling
- Uses FARM_FINGERPRINT for deterministic sampling
- Adjusts sampling rate based on data volume
- Maintains data distribution across time periods
- Targets approximately 2M rows per version

### 2. Version Management
- Supports explicit version comparison (e.g., 0.3615 vs 0.3621)
- Handles version float comparisons
- Maintains data integrity across versions

### 3. Memory Optimization
- Chunk-based processing
- Streaming data transfer
- Efficient memory management
- Progress tracking and statistics

## Implementation Details

### Sampling Logic
```python
def calculate_sampling_denominator(total_rows: int, target_rows: int) -> int:
    """Calculate sampling rate to achieve target row count."""
    return math.ceil(total_rows / target_rows)
```

### BigQuery Query Structure
```sql
WITH OldVersionSample AS (
    SELECT *, '{old_version}' as source_version
    FROM `{project}.{dataset}.{table}`
    WHERE version_float = {old_version}
      AND MOD(ABS(FARM_FINGERPRINT(CAST(res_timestamp AS STRING))), {old_denominator}) = 0
    LIMIT {TARGET_SAMPLE_SIZE}
)
```

## Usage Examples

### 1. Basic Extraction
```python
from create_csv import extract_data_from_bigquery

# Extract data for two versions
df = extract_data_from_bigquery('0.3615', '0.3621')
```

### 2. Custom Configuration
```python
# Configure custom sampling
TARGET_SAMPLE_SIZE = 1000000  # Adjust target sample size
```

## Performance Considerations

### Memory Usage
- Streaming data transfer using BigQuery Storage API
- Chunk-based processing (default 10,000 rows)
- Automatic memory cleanup

### Processing Speed
- Parallel query execution
- Optimized sampling strategy
- Progress tracking with ETA

## Error Handling

### Common Issues
1. **BigQuery Connection**
   ```python
   try:
       client = bigquery.Client(credentials=credentials)
   except Exception as e:
       logging.error(f"BigQuery connection failed: {e}")
   ```

2. **Version Validation**
   ```python
   if not is_valid_version_format(version):
       raise ValueError(f"Invalid version format: {version}")
   ```

3. **Memory Management**
   ```python
   # Chunk processing with cleanup
   for chunk in pd.read_csv(..., chunksize=CHUNK_SIZE):
       process_chunk(chunk)
       gc.collect()  # Force garbage collection
   ```

## Configuration Options

### BigQuery Settings
```json
{
    "project_id": "your-project",
    "dataset_id": "your-dataset",
    "table_id": "your-table",
    "service_account_path": "path/to/credentials.json"
}
```

### Sampling Parameters
```python
SAMPLING_CONFIG = {
    "target_size": 2000000,  # Target rows per version
    "min_sample_rate": 0.001, # Minimum sampling rate
    "max_sample_rate": 1.0    # Maximum sampling rate
}
```

## Best Practices

1. **Version Management**
   - Always validate version formats
   - Use float comparison for versions
   - Handle version conflicts gracefully

2. **Data Quality**
   - Validate column presence
   - Check data types
   - Monitor sampling distribution

3. **Resource Management**
   - Monitor memory usage
   - Implement timeout handling
   - Clean up temporary resources

## Integration Points

### Input
- BigQuery credentials
- Version numbers
- Configuration parameters

### Output
- Sampled DataFrames
- CSV files
- Execution statistics

## Monitoring and Logging

### Metrics Tracked
- Rows processed
- Processing speed
- Memory usage
- Query execution time

### Log Format
```python
logging.info(f"""
Data extraction completed:
- Retrieved {len(df):,} total rows
- Old version ({old_version}): {old_count:,} rows
- New version ({new_version}): {new_count:,} rows
- Duration: {duration}
- Speed: {speed:.2f} rows/second
""")
``` 