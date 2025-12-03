# Parameter Analysis Component (param_analysis/)

## Overview
The parameter analysis module provides tools for analyzing game data parameters, detecting patterns, and generating validation rules. It consists of several interconnected components that work together to provide comprehensive parameter analysis and validation capabilities.

## Module Structure

```
param_analysis/
├── __init__.py
├── param_analyzer.py        # Core analysis logic
├── param_definitions.py     # Parameter type definitions
├── enhanced_param_definitions.py  # Advanced validators
├── param_validators.py      # Validation implementations
└── utils.py                # Utility functions
```

## Core Components

### 1. Parameter Analyzer (param_analyzer.py)

#### Purpose
Analyzes data parameters to detect patterns, types, and constraints.

#### Key Features
```python
class ParameterAnalyzer:
    """
    Analyzes parameters in game data to detect patterns and generate rules.
    
    Features:
    - Automatic type detection
    - Pattern recognition
    - Constraint analysis
    - Rule generation
    """
    
    def analyze_column(self, column: str) -> Dict[str, Any]:
        """
        Analyzes a single column to determine its characteristics.
        
        Returns:
        {
            'type': detected_type,
            'patterns': found_patterns,
            'constraints': value_constraints,
            'statistics': basic_stats
        }
        """
```

### 2. Parameter Definitions (param_definitions.py)

#### Base Parameter Types
```python
class ParameterType:
    """Base class for parameter types."""
    
    def validate(self, value: Any) -> bool:
        """Base validation method."""
        raise NotImplementedError

class NumericParameter(ParameterType):
    """Handles numeric parameters with range constraints."""
    
    def __init__(self, min_value: float = None, max_value: float = None):
        self.min_value = min_value
        self.max_value = max_value

class StringParameter(ParameterType):
    """Handles string parameters with pattern matching."""
    
    def __init__(self, pattern: str = None, allowed_values: Set[str] = None):
        self.pattern = pattern
        self.allowed_values = allowed_values
```

### 3. Enhanced Validators (enhanced_param_definitions.py)

#### Specialized Validators
```python
class TimestampClientValidator(ParameterType):
    """
    Validates timestamp_client field with millisecond precision.
    
    Format: Unix timestamp in milliseconds with optional decimal places
    Example: 1577836800000.123
    """

class ClickOnScreenValidator(ParameterType):
    """
    Validates click_on_screen events with structured JSON.
    
    Schema:
    {
        "tap_count": int,
        "target_path": str,
        "coordinates": {"x": float, "y": float}
    }
    """

class ActiveSegmentsValidator(ParameterType):
    """
    Validates active_segments configuration.
    
    Format: List of segment identifiers with specific constraints
    Example: ["segment_1", "segment_2"]
    """
```

## Analysis Process

### 1. Type Detection
```python
def detect_parameter_type(values: pd.Series) -> str:
    """
    Detects parameter type based on value patterns.
    
    Detection Logic:
    1. Check numeric patterns
    2. Check timestamp patterns
    3. Check JSON structures
    4. Check list structures
    5. Default to string
    """
```

### 2. Pattern Recognition
```python
def recognize_patterns(values: pd.Series) -> List[str]:
    """
    Identifies common patterns in parameter values.
    
    Pattern Types:
    - Numeric ranges
    - Date/time formats
    - String formats
    - JSON structures
    - List structures
    """
```

### 3. Constraint Analysis
```python
def analyze_constraints(values: pd.Series) -> Dict[str, Any]:
    """
    Analyzes value constraints and limitations.
    
    Constraints:
    - Value ranges
    - String lengths
    - Allowed values
    - Required fields
    - Format restrictions
    """
```

## Usage Examples

### 1. Basic Analysis
```python
from param_analysis.param_analyzer import ParameterAnalyzer

analyzer = ParameterAnalyzer('game_data.csv')
results = analyzer.analyze()
```

### 2. Custom Validation
```python
from param_analysis.enhanced_param_definitions import CustomValidator

validator = CustomValidator(
    pattern=r'^[A-Z0-9]+$',
    min_length=8,
    max_length=16
)
```

## Performance Optimization

### 1. Memory Management
```python
def analyze_large_dataset(file_path: str, chunk_size: int = 10000):
    """
    Analyzes large datasets in chunks to manage memory usage.
    
    Strategy:
    1. Process in chunks
    2. Aggregate results
    3. Generate final analysis
    """
```

### 2. Caching
```python
@lru_cache(maxsize=1000)
def validate_complex_pattern(value: str) -> bool:
    """Caches results of expensive pattern validation."""
    return complex_pattern_matching(value)
```

## Integration

### 1. Input Formats
- CSV files
- Pandas DataFrames
- JSON structures
- Custom data sources

### 2. Output Formats
```python
class AnalysisResult:
    """Structured analysis results."""
    
    def to_json(self) -> str:
        """Export results as JSON."""
        
    def to_markdown(self) -> str:
        """Generate markdown report."""
        
    def to_html(self) -> str:
        """Generate HTML report."""
```

## Best Practices

### 1. Type Detection
- Use comprehensive type checking
- Handle edge cases
- Consider mixed types
- Validate assumptions

### 2. Pattern Recognition
- Use efficient regex patterns
- Cache common patterns
- Handle invalid formats
- Document patterns

### 3. Constraint Analysis
- Validate range boundaries
- Check for outliers
- Document constraints
- Handle exceptions

## Configuration

### 1. Analysis Settings
```json
{
    "analysis": {
        "sample_size": 10000,
        "confidence_level": 0.95,
        "pattern_threshold": 0.8,
        "cache_size": 1000
    }
}
```

### 2. Validation Rules
```json
{
    "validators": {
        "timestamp_client": {
            "type": "timestamp",
            "format": "unix_ms",
            "range": [1577836800000, 1893456000000]
        },
        "click_on_screen": {
            "type": "json",
            "required_fields": ["tap_count", "target_path"]
        }
    }
}
```

## Error Handling

### Common Issues
1. **Type Mismatches**
   - Invalid data types
   - Mixed type columns
   - Conversion errors

2. **Pattern Failures**
   - Invalid formats
   - Incomplete patterns
   - Regex timeouts

3. **Memory Issues**
   - Large datasets
   - Complex patterns
   - Resource constraints

## Monitoring and Logging

### Metrics Tracked
- Processing time
- Memory usage
- Pattern matches
- Error rates
- Cache hits/misses

### Log Format
```python
logging.info(f"""
Analysis completed:
- Processed: {processed_count:,} values
- Patterns found: {pattern_count}
- Memory used: {memory_usage:.2f} MB
- Duration: {duration}
""") 