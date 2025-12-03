# Parameter Analysis Module

## Overview
This module contains the core functionality for analyzing and validating game data parameters. It includes tools for initial data analysis, parameter type detection, validation rule definition, and review processes.

## Components

### 1. Parameter Analyzer (`param_analyzer.py`)

#### Purpose
Analyzes raw game data to detect parameter patterns and constraints.

#### Key Classes
- `ParameterAnalyzer`
  - Methods:
    - `load_data()`: Loads CSV data
    - `analyze_parameters()`: Performs parameter analysis
    - `detect_parameter_type()`: Determines parameter type
    - `generate_validation_rules()`: Creates initial validation rules

#### Special Handling
- `distinct_id`: Length and pattern analysis
- Time fields: Format detection
- Numeric fields: Range and distribution analysis

### 2. Parameter Definitions (`param_definitions.py`)

#### Base Parameter Types
- `ParameterType` (Enum)
  - `FIXED_SET`
  - `CONSTRAINED_RANGE`

#### Parameter Classes
- `ParameterDefinition`
- `FixedSetParameter`
- `ConstrainedRangeParameter`

### 3. Enhanced Parameter Definitions (`enhanced_param_definitions.py`)

#### Validator Base Class
```python
class ParameterValidator:
    def validate(self, value: Any) -> bool:
        raise NotImplementedError
```

#### Timestamp Validators
1. `IsoTimestampValidator`
   - Strict ISO format validation
   - Timezone handling
   - Max date enforcement

2. `UnixTimestampSecondsValidator`
   - Integer/float validation
   - Range checking (2020-2030)
   - Max date enforcement

3. `UnixTimestampMillisValidator`
   - Similar to seconds validator
   - Adjusted for millisecond scale

#### List Validators
```python
class ListValidator:
    def __init__(self, item_validator=None, allowed_values=None):
        ...
```
- Handles both string and list inputs
- Optional value restrictions
- Nested validation support

#### JSON Validators
```python
class JsonValidator:
    def __init__(self, schema: Dict):
        ...
```
- Schema-based validation
- Nested structure support
- Type checking

#### Range Validators
```python
class RangeValidator:
    def __init__(self, min_value=None, max_value=None, allow_mean=True, allow_null=False):
        ...
```
- Numeric range validation with optional min/max constraints
- Null value handling (configurable)
- Mean calculation control
- Type conversion handling
- Examples:
  - `RangeValidator(min_value=0, max_value=100, allow_null=True)` for battery level (0-100% or null)
  - `RangeValidator(min_value=100, max_value=10000, allow_null=False)` for bubble item IDs (100-10000, no nulls)
  - `RangeValidator(min_value=0, max_value=30, allow_null=False)` for sub offer IDs (0-30, no nulls)
  - `RangeValidator(min_value=1, max_value=100, allow_null=False)` for set IDs (1-100, no nulls)
  - `RangeValidator(min_value=0, max_value=10000, allow_null=False)` for album duplicates count (0-10000, no nulls)
  - `RangeValidator(min_value=1, max_value=10000, allow_null=False)` for cash deducted (1-10000, no nulls)
  - `RangeValidator(min_value=0, max_value=2000, allow_null=False)` for memory total in MB (0-2000, no nulls)
  - `RangeValidator(min_value=0, max_value=1000, allow_null=False)` for memory mono in MB (0-1000, no nulls)
  - `RangeValidator(min_value=0, max_value=1000, allow_null=False)` for memory allocated in MB (0-1000, no nulls)
  - `RangeValidator(min_value=0, max_value=1000, allow_null=False)` for memory GFX in MB (0-1000, no nulls)
  - `RangeValidator(min_value=0)` for quantities (≥0, no nulls)
  - `RangeValidator(max_value=1000)` for scores (≤1000, no nulls)
  - `NonEmptyStringValidator()` for FCM tokens and other required string fields
  - `RealmPathValidator()` for MongoDB Realm database file paths
  - `VersionHashValidator()` for MD5 version hashes

#### Format Validators
```python
class FormatValidator:
    def __init__(self, pattern: str):
        ...
```
- Regex-based validation
- String format checking
- Type safety

#### Transaction ID Validators
```python
class TransactionIdValidator:
    def validate(self, value: Any) -> bool:
        ...
```
- Validates Google Play Store transaction IDs
- Rejects empty strings and invalid characters
- Ensures minimum length requirements
- Supports alphanumeric, dots, hyphens, underscores

#### Non-Empty String Validators
```python
class NonEmptyStringValidator:
    def validate(self, value: Any) -> bool:
        ...
```
- Validates that values are non-empty strings
- Rejects None, numbers, booleans, and other non-string types
- Rejects empty strings and whitespace-only strings
- Used for tokens, IDs, and other string fields that must have content

#### Realm Path Validators
```python
class RealmPathValidator:
    def validate(self, value: Any) -> bool:
        ...
```
- Validates MongoDB Realm database file paths
- Enforces specific path structure for Peerplay app
- Validates hex ID format (24 characters)
- Ensures .realm file extension
- Pattern: `/data/user/0/com.peerplay.megamerge/files/mongodb-realm/{realm-id}/{hex-id}/{filename}.realm`

#### Version Hash Validators
```python
class VersionHashValidator:
    def validate(self, value: Any) -> bool:
        ...
```
- Validates MD5 hash format for version identifiers
- Exactly 32 characters in length
- Lowercase hexadecimal characters only (0-9, a-f)
- Used for version control and build identification
- Example: `c76ec6b0f8ad4dfbb360c2301f3407c6`

### 4. Review System

#### Comment Structure Generator (`create_comment_structure.py`)
- Creates markdown-based review format
- Organizes parameters by usage frequency
- Provides structured comment template

#### Comment Extractor (`extract_comments.py`)
- Parses markdown comments
- Extracts validation requirements
- Helps track review progress

## Validation Rules

### Time Field Rules
```python
VALIDATORS = {
    'time': IsoTimestampValidator(),
    'res_timestamp': UnixTimestampMillisValidator(),
    'updated_timestamp': UnixTimestampSecondsValidator(),
    ...
}
```

### List Field Rules
```python
VALIDATORS = {
    'live_ops_segment_id': ListValidator(
        allowed_values=['default', 'store_ftd', ...]
    ),
    'bot_rooms_numbers': ListValidator(
        item_validator=ListValidator()
    ),
    ...
}
```

### JSON Structure Rules
```python
VALIDATORS = {
    'merged_items': JsonValidator({
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {...}
        }
    }),
    ...
}
```

## Usage Examples

### Running Analysis
```python
analyzer = ParameterAnalyzer('game_data.csv')
analyzer.load_data()
definitions = analyzer.analyze_parameters()
```

### Validating Parameters
```python
from enhanced_param_definitions import validate_parameter

# Validate ISO timestamp
is_valid = validate_parameter('time', '2025-04-23T13:13:26+00:00')

# Validate list
is_valid = validate_parameter('server_segments', ['segment1', 'segment2'])

# Validate JSON
is_valid = validate_parameter('merged_items', {...})
```

### Reviewing Parameters
```bash
# Generate review structure
python create_comment_structure.py

# Extract comments after review
python extract_comments.py
```

## Error Handling
- All validators include comprehensive error checking
- Type safety enforced throughout
- Validation failures return False rather than raising exceptions
- Detailed logging available for debugging 