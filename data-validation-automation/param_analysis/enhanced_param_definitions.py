"""
Enhanced parameter definitions with specific validation rules based on analysis.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import re
import json

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

class ParameterValidator:
    """Base class for parameter validators."""
    def validate(self, value: Any) -> bool:
        raise NotImplementedError

class IsoTimestampValidator(ParameterValidator):
    """Validator for ISO format timestamps."""
    def __init__(self, max_date: str = "2027-05-17T15:59:59+00:00", require_timezone: bool = False):
        self.max_date = datetime.fromisoformat(max_date)
        self.require_timezone = require_timezone
        self.iso_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:?\d{2}|Z)?$')
    
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            if not self.iso_pattern.match(value):
                return False
            
            # Convert space separator to T for ISO format
            if ' ' in value:
                value = value.replace(' ', 'T')
            
            # Handle timezone
            has_timezone = any(x in value for x in ['+', '-', 'Z'])
            if self.require_timezone and not has_timezone:
                return False
            
            # Parse the datetime
            try:
                if has_timezone:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                else:
                    # For timestamps without timezone, parse without timezone first
                    dt = datetime.fromisoformat(value)
            except ValueError:
                return False
            
            # Compare with max_date
            if has_timezone:
                return dt <= self.max_date
            else:
                # For timestamps without timezone, compare the naive datetime parts
                return dt <= self.max_date.replace(tzinfo=None)
            
        except (ValueError, TypeError):
            return False

class UnixTimestampSecondsValidator(ParameterValidator):
    """Validator for Unix timestamps in seconds."""
    def __init__(self, max_date: str = "2027-05-17T15:59:59+00:00"):
        self.max_timestamp = int(datetime.fromisoformat(max_date).timestamp())
    
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, (int, float)):
                return False
            # Should be a reasonable timestamp in seconds (2020-2030)
            if not (1577836800 <= float(value) <= 1893456000):
                return False
            return float(value) <= self.max_timestamp
        except (ValueError, TypeError):
            return False

class UnixTimestampMillisValidator(ParameterValidator):
    """Validator for Unix timestamps in milliseconds."""
    def __init__(self, max_date: str = "2027-05-17T15:59:59+00:00"):
        self.max_timestamp = int(datetime.fromisoformat(max_date).timestamp() * 1000)
    
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, (int, float)):
                return False
            # Should be a reasonable timestamp in milliseconds (2020-2030)
            if not (1577836800000 <= float(value) <= 1893456000000):
                return False
            return float(value) <= self.max_timestamp
        except (ValueError, TypeError):
            return False

class ListValidator(ParameterValidator):
    """Validator for list fields."""
    def __init__(self, item_validator: Optional[ParameterValidator] = None, 
                 allowed_values: Optional[List[str]] = None,
                 allow_any: bool = False):
        self.item_validator = item_validator
        self.allowed_values = set(allowed_values) if allowed_values else None
        self.allow_any = allow_any
    
    def validate(self, value: Any) -> bool:
        try:
            if isinstance(value, str):
                items = value.split(',')
            elif isinstance(value, list):
                items = value
            else:
                return False
            
            if self.allow_any:
                return True
            
            if self.allowed_values:
                return all(item.strip() in self.allowed_values for item in items)
            
            if self.item_validator:
                return all(self.item_validator.validate(item) for item in items)
            
            return True
        except:
            return False

class JsonValidator(ParameterValidator):
    """Validator for JSON fields with schema validation."""
    def __init__(self, schema: Dict):
        self.schema = schema
    
    def validate(self, value: Any) -> bool:
        try:
            if isinstance(value, str):
                data = json.loads(value)
            else:
                data = value
            
            return self._validate_schema(data, self.schema)
        except:
            return False
    
    def _validate_schema(self, data: Any, schema: Dict) -> bool:
        # Implement schema validation logic here
        # This is a placeholder - we'll implement specific schemas
        return True

class RangeValidator(ParameterValidator):
    """Validator for numeric ranges."""
    def __init__(self, min_value: Optional[Union[int, float]] = None,
                 max_value: Optional[Union[int, float]] = None,
                 allow_mean: bool = True,
                 allow_null: bool = False):
        self.min_value = min_value
        self.max_value = max_value
        self.allow_mean = allow_mean
        self.allow_null = allow_null
    
    def validate(self, value: Any) -> bool:
        try:
            # Handle null values
            if value is None or (isinstance(value, str) and value.strip().lower() in ['null', 'none', '']):
                return self.allow_null
            
            # Try to convert to numeric
            num_value = float(value)
            
            # Check range constraints
            if self.min_value is not None and num_value < self.min_value:
                return False
            if self.max_value is not None and num_value > self.max_value:
                return False
            return True
        except (ValueError, TypeError):
            return False

class FormatValidator(ParameterValidator):
    """Validator for string formats."""
    def __init__(self, pattern: str):
        self.pattern = re.compile(pattern)
    
    def validate(self, value: Any) -> bool:
        try:
            return bool(self.pattern.match(str(value)))
        except:
            return False

class CurrencyIdValidator(ParameterValidator):
    """Validator for currency IDs that can be either strings or numbers."""
    def __init__(self, allowed_strings: Optional[List[str]] = None):
        self.allowed_strings = set(allowed_strings) if allowed_strings else None
    
    def validate(self, value: Any) -> bool:
        try:
            if isinstance(value, (int, float)):
                return True
            if isinstance(value, str) and self.allowed_strings:
                return value in self.allowed_strings
            return False
        except:
            return False

class NumericIdValidator(ParameterValidator):
    """Validator for IDs that can be either integers or decimals."""
    def validate(self, value: Any) -> bool:
        try:
            if isinstance(value, (int, float)):
                # Convert to float and check if it's a whole number
                float_val = float(value)
                return float_val.is_integer() and float_val >= 0
            elif isinstance(value, str):
                # Try to convert string to float and check if it's a whole number
                float_val = float(value)
                return float_val.is_integer() and float_val >= 0
            return False
        except (ValueError, TypeError):
            return False

class ClientTimestampValidator(ParameterValidator):
    """Validator for client timestamps in milliseconds with decimal precision."""
    def __init__(self, max_date: str = "2027-05-17T15:59:59+00:00"):
        self.max_timestamp = int(datetime.fromisoformat(max_date).timestamp() * 1000)
    
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, (int, float, str)):
                return False
            
            # Convert to float and validate format (milliseconds with optional decimal)
            float_val = float(value)
            
            # Should be a reasonable timestamp in milliseconds (2020-2030)
            if not (1577836800000 <= float_val <= 1893456000000):
                return False
                
            # Check decimal precision (up to 2 decimal places)
            str_val = str(float_val)
            if '.' in str_val:
                decimals = len(str_val.split('.')[1])
                if decimals > 2:
                    return False
            
            return float_val <= self.max_timestamp
        except (ValueError, TypeError):
            return False

class ClickOnScreenValidator(ParameterValidator):
    """Validator for click on screen events with specific JSON structure."""
    def validate(self, value: Any) -> bool:
        try:
            if isinstance(value, str):
                data = json.loads(value)
            else:
                data = value
                
            if not isinstance(data, list):
                return False
                
            # Each item should have the required structure
            for item in data:
                if not isinstance(item, dict):
                    return False
                    
                # Check for required fields and types
                if 'tap_count' in item:
                    if not isinstance(item['tap_count'], int):
                        return False
                elif 'target_path' in item and 'timestamp' in item and 'x' in item and 'y' in item:
                    if not isinstance(item['target_path'], str):
                        return False
                    if not isinstance(item['timestamp'], (int, float)):
                        return False
                    if not isinstance(item['x'], (int, float)):
                        return False
                    if not isinstance(item['y'], (int, float)):
                        return False
                elif 'threshold' in item:
                    if not isinstance(item['threshold'], (int, float)):
                        return False
                else:
                    return False
            
            return True
        except:
            return False

class ActiveSegmentsValidator(ParameterValidator):
    """Validator for active segments with specific JSON structure."""
    def validate(self, value: Any) -> bool:
        try:
            if isinstance(value, str):
                data = json.loads(value)
            else:
                data = value
                
            if not isinstance(data, list):
                return False
                
            # Each item should have the required structure
            for item in data:
                if not isinstance(item, dict):
                    return False
                    
                # Check for required fields
                required_fields = {'config_id', 'config_segment', 'config_type', 'liveops_id', 'liveops_segment'}
                if not all(field in item for field in required_fields):
                    return False
                    
                # Validate field types
                if not isinstance(item['config_id'], int):
                    return False
                if not isinstance(item['config_segment'], str):
                    return False
                if not isinstance(item['config_type'], str):
                    return False
                if not isinstance(item['liveops_id'], int):
                    return False
                if not isinstance(item['liveops_segment'], str):
                    return False
            
            return True
        except:
            return False

class RewardCenterValidator(ParameterValidator):
    """Validator for reward center list with numeric reward IDs."""
    def validate(self, value: Any) -> bool:
        try:
            if isinstance(value, str):
                data = json.loads(value)
            else:
                data = value
                
            if not isinstance(data, list):
                return False
                
            # Each item should be a positive integer (reward ID)
            for item in data:
                if not isinstance(item, (int, float)):
                    return False
                # Must be a positive integer
                if item <= 0 or not float(item).is_integer():
                    return False
            
            return True
        except:
            return False

class TransactionIdValidator(ParameterValidator):
    """Validator for transaction IDs (e.g., Google Play Store transaction IDs)."""
    def validate(self, value: Any) -> bool:
        try:
            # Must be a string
            if not isinstance(value, str):
                return False
            
            # Cannot be empty string
            if value.strip() == "":
                return False
            
            # Must contain only valid characters for transaction IDs
            # Allow alphanumeric, dots, hyphens, underscores
            if not re.match(r'^[A-Za-z0-9\.\-_]+$', value):
                return False
            
            # Should have reasonable length (transaction IDs are typically long)
            if len(value) < 5:  # Too short to be a real transaction ID
                return False
            
            return True
        except:
            return False

class CountryCodeValidator(ParameterValidator):
    """Validator for ISO country codes."""
    def __init__(self, allowed_codes: Optional[List[str]] = None):
        # Default to common country codes if none provided
        self.allowed_codes = set(allowed_codes) if allowed_codes else set()
    
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            
            # Country codes should be 2 characters and uppercase
            code = value.strip().upper()
            
            if len(code) != 2:
                return False
            
            # Check if it's in the allowed codes set
            return code in self.allowed_codes
        except:
            return False

class FixedSetValidator(ParameterValidator):
    """Validator for values that must be in a specific set of allowed values."""
    def __init__(self, allowed_values: List[str], allow_null: bool = False):
        self.allowed_values = set(allowed_values)
        self.allow_null = allow_null
    
    def validate(self, value: Any) -> bool:
        try:
            # Handle null values
            if value is None or (isinstance(value, str) and value.strip().lower() in ['null', 'none', '']):
                return self.allow_null
            
            # Convert boolean values to string (handles True/False from CSV)
            if isinstance(value, bool):
                # Check both capitalized and lowercase versions to handle 'True'/'False' and 'true'/'false'
                bool_str_lower = str(value).lower()
                bool_str_capitalized = str(value)  # Python bool converts to 'True'/'False'
                # Check if either version is in allowed values
                if bool_str_lower in self.allowed_values or bool_str_capitalized in self.allowed_values:
                    return True
                return False
            # Convert numeric values to string (handles float/int from CSV)
            elif isinstance(value, float):
                # If float represents a whole number (e.g., 0.0, 1.0), try both int and float string representations
                if value.is_integer():
                    int_str = str(int(value))
                    float_str = str(value)
                    # Check both representations to handle cases where allowed_values has "399.0" but value is 399.0
                    return int_str in self.allowed_values or float_str in self.allowed_values
                else:
                    value = str(value)
            elif isinstance(value, int):
                value = str(value)
            
            if not isinstance(value, str):
                return False
            
            # Normalize string values that represent whole numbers (e.g., "0.0" -> "0", "1.0" -> "1")
            value_stripped = value.strip()
            try:
                # Try to parse as float
                float_val = float(value_stripped)
                # If it's a whole number, check both the original string and the integer string representation
                if float_val.is_integer():
                    int_str = str(int(float_val))
                    # Check both the original string and the integer representation
                    if value_stripped in self.allowed_values or int_str in self.allowed_values:
                        return True
            except (ValueError, TypeError):
                pass  # Not a numeric string, continue with normal check
            
            # Check if the value is in the allowed set
            return value_stripped in self.allowed_values
        except:
            return False

class NonEmptyStringValidator(ParameterValidator):
    """Validator for strings that must not be empty."""
    def validate(self, value: Any) -> bool:
        try:
            # Must be a string
            if not isinstance(value, str):
                return False
            # Must not be empty after stripping whitespace
            return len(value.strip()) > 0
        except:
            return False

class RealmPathValidator(ParameterValidator):
    """Validator for MongoDB Realm database file paths (Android and iOS)."""
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            
            # Android pattern: /data/user/{user_id}/com.peerplay.megamerge/files/mongodb-realm/{realm-id}/{hex-id}/{filename}.realm
            android_pattern = r'^/data/user/\d+/com\.peerplay\.megamerge/files/mongodb-realm/[a-zA-Z0-9\-_]+/[a-f0-9]{24}/[a-zA-Z0-9_]+\.realm$'
            
            # iOS pattern: /var/mobile/Containers/Data/Application/{UUID}/Documents/mongodb-realm/{realm-id}/{hex-id}/{filename}.realm
            ios_pattern = r'^/var/mobile/Containers/Data/Application/[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}/Documents/mongodb-realm/[a-zA-Z0-9\-_]+/[a-f0-9]{24}/[a-zA-Z0-9_]+\.realm$'
            
            # macOS pattern: /Users/{username}/Library/Application Support/{app}/mongodb-realm/{realm-id}/{hex-id}/{filename}.realm
            macos_pattern = r'^/Users/[^/]+/Library/Application Support/[^/]+/mongodb-realm/[a-zA-Z0-9\-_]+/[a-f0-9]{24}/[a-zA-Z0-9_]+\.realm$'
            
            return bool(re.match(android_pattern, value)) or bool(re.match(ios_pattern, value)) or bool(re.match(macos_pattern, value))
        except:
            return False

class VersionHashValidator(ParameterValidator):
    """Validator for version hashes (MD5 format)."""
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            
            # Must be exactly 32 characters (MD5 hash length)
            if len(value) != 32:
                return False
            
            # Must contain only lowercase hexadecimal characters
            pattern = r'^[a-f0-9]{32}$'
            return bool(re.match(pattern, value))
        except:
            return False

class StickersStateValidator(ParameterValidator):
    """Validator for stickers state in format current/total."""
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            
            # Must contain exactly one slash
            if value.count('/') != 1:
                return False
            
            # Split by slash
            parts = value.split('/')
            if len(parts) != 2:
                return False
            
            current_str, total_str = parts
            
            # Both parts must be non-empty
            if not current_str or not total_str:
                return False
            
            # Both parts must be valid integers
            try:
                current = int(current_str)
                total = int(total_str)
            except ValueError:
                return False
            
            # Both must be non-negative
            if current < 0 or total < 0:
                return False
            
            # Current should not exceed total (logical constraint)
            if current > total:
                return False
            
            # Total should be positive (you can't have 0 total stickers)
            if total == 0:
                return False
            
            return True
        except:
            return False

class ReceivedStickersListValidator(ParameterValidator):
    """Validator for received stickers list in JSON format."""
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            
            # Must be valid JSON
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return False
            
            # Must be a list/array
            if not isinstance(parsed, list):
                return False
            
            # Validate each item in the array
            for item in parsed:
                if not isinstance(item, str):
                    return False
                
                # Must contain exactly one colon
                if item.count(':') != 1:
                    return False
                
                # Split by colon
                parts = item.split(':', 1)
                if len(parts) != 2:
                    return False
                
                slot_name, data = parts
                slot_name = slot_name.strip()
                data = data.strip()
                
                # Slot name must start with 'slot_' followed by a number
                if not slot_name.startswith('slot_'):
                    return False
                
                slot_num = slot_name[5:]  # Remove 'slot_' prefix
                if not slot_num.isdigit():
                    return False
                
                # Data must have 3 or 4 comma-separated values (supports both formats)
                values = [v.strip() for v in data.split(',')]
                if len(values) not in [3, 4]:
                    return False
                
                # First value must be a positive integer (sticker ID)
                try:
                    sticker_id = int(values[0])
                    if sticker_id <= 0:
                        return False
                except ValueError:
                    return False
                
                # Second value must be a non-negative integer (count)
                try:
                    count = int(values[1])
                    if count < 0:
                        return False
                except ValueError:
                    return False
                
                # Third value can be a boolean OR "regular"
                if len(values) == 3:
                    # Original format: slot_1: 8, 2, True
                    if values[2] not in ['True', 'False']:
                        return False
                elif len(values) == 4:
                    # New format: slot_1: 18, 2, regular, True
                    if values[2] != 'regular':
                        return False
                    if values[3] not in ['True', 'False']:
                        return False
            
            return True
        except:
            return False

class PackRaritiesWeightsValidator(ParameterValidator):
    """Validator for pack rarities weights in JSON format."""
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            
            # Must be valid JSON
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return False
            
            # Must be a list/array
            if not isinstance(parsed, list):
                return False
            
            # Validate each item in the array
            for item in parsed:
                if not isinstance(item, str):
                    return False
                
                # Must contain exactly one colon
                if item.count(':') != 1:
                    return False
                
                # Split by colon
                parts = item.split(':', 1)
                if len(parts) != 2:
                    return False
                
                key, value_str = parts
                key = key.strip()
                value_str = value_str.strip()
                
                # Key must match slot_X_rarity_Y or slot_X_missing_probability pattern
                if not (key.startswith('slot_') and ('_rarity_' in key or '_missing_probability' in key)):
                    return False
                
                # Value must be a valid number (0 or 1 typically)
                try:
                    val = float(value_str)
                    if val < 0 or val > 1:
                        return False
                except ValueError:
                    return False
            
            return True
        except:
            return False

class AndroidOsVersionValidator(ParameterValidator):
    """Validator for Android OS version strings that start with 'Android OS ' or match X.Y.Z or X.Y format or specific version strings."""
    def __init__(self):
        # Specific allowed version strings
        self.allowed_versions = {"26.1", "26.2", "18.7.2", "18.6.2", "18.5", "26.0.1", "18.4.1", "15.7.1"}
        # Pattern for X.Y.Z format where X, Y, Z are numbers
        self.version_pattern_xyz = re.compile(r'^\d+\.\d+\.\d+$')
        # Pattern for X.Y format where X, Y are numbers
        self.version_pattern_xy = re.compile(r'^\d+\.\d+$')
    
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            value = value.strip()
            # Check if it's a specific allowed version
            if value in self.allowed_versions:
                return True
            # Check if it matches X.Y.Z format (where X, Y, Z are numbers)
            if self.version_pattern_xyz.match(value):
                return True
            # Check if it matches X.Y format (where X, Y are numbers)
            if self.version_pattern_xy.match(value):
                return True
            # Check if it starts with "Android OS "
            if value.startswith("Android OS "):
                return True
            # Check if it starts with "Mac OS X " (e.g., "Mac OS X 15.7.2")
            if value.startswith("Mac OS X "):
                return True
            return False
        except:
            return False

class InterruptedValidator(ParameterValidator):
    """Validator for interrupted parameter that treats 1.0 as 0.0."""
    def __init__(self):
        self.allowed_values = {'1', '0'}
    
    def validate(self, value: Any) -> bool:
        try:
            if value is None:
                return False
            
            # Convert 1.0 to 0.0 (treat 1.0 as 0.0)
            if isinstance(value, float) and value == 1.0:
                value = 0.0
            
            # Convert to string for comparison
            if isinstance(value, (int, float)):
                if value.is_integer() if isinstance(value, float) else True:
                    value = str(int(value))
                else:
                    value = str(value)
            elif not isinstance(value, str):
                return False
            
            return value.strip() in self.allowed_values
        except:
            return False

class FractionValidator(ParameterValidator):
    """Validator for values in X/Y format (e.g., "1/5") with configurable ranges for numerator and denominator."""
    def __init__(self, min_numerator: Optional[int] = None, max_numerator: Optional[int] = None,
                 min_denominator: Optional[int] = None, max_denominator: Optional[int] = None,
                 allow_null: bool = False):
        self.min_numerator = min_numerator
        self.max_numerator = max_numerator
        self.min_denominator = min_denominator
        self.max_denominator = max_denominator
        self.allow_null = allow_null
        # Pattern to match X/Y format where X and Y are integers
        self.fraction_pattern = re.compile(r'^(\d+)/(\d+)$')
    
    def validate(self, value: Any) -> bool:
        try:
            if value is None or (isinstance(value, str) and value.strip().lower() in ['null', 'none', '']):
                return self.allow_null
            
            if not isinstance(value, str):
                return False
            
            value = value.strip()
            
            # Match the X/Y pattern
            match = self.fraction_pattern.match(value)
            if not match:
                return False
            
            # Extract numerator and denominator
            numerator = int(match.group(1))
            denominator = int(match.group(2))
            
            # Validate numerator range
            if self.min_numerator is not None and numerator < self.min_numerator:
                return False
            if self.max_numerator is not None and numerator > self.max_numerator:
                return False
            
            # Validate denominator range
            if self.min_denominator is not None and denominator < self.min_denominator:
                return False
            if self.max_denominator is not None and denominator > self.max_denominator:
                return False
            
            return True
        except (ValueError, TypeError, AttributeError):
            return False

class TimeValidator(ParameterValidator):
    """Validator for time/timestamp fields that converts to timestamp and checks if between current_date - 5 to current_date + 1."""
    def __init__(self):
        self.iso_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:?\d{2}|Z)?$')
    
    def validate(self, value: Any) -> bool:
        try:
            if value is None:
                return False
            
            current_date = datetime.now()
            min_date = current_date - timedelta(days=5)
            max_date = current_date + timedelta(days=1)
            
            # Try to parse as timestamp
            dt = None
            
            # Check if it's a numeric timestamp (unix seconds or milliseconds)
            if isinstance(value, (int, float)):
                # Try as milliseconds first (larger numbers)
                if value > 1e12:
                    dt = datetime.fromtimestamp(value / 1000)
                else:
                    dt = datetime.fromtimestamp(value)
            elif isinstance(value, str):
                value = value.strip()
                # Try ISO format
                if self.iso_pattern.match(value):
                    try:
                        # Convert space separator to T for ISO format
                        if ' ' in value:
                            value = value.replace(' ', 'T')
                        # Handle timezone
                        has_timezone = any(x in value for x in ['+', '-', 'Z'])
                        if has_timezone:
                            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        else:
                            dt = datetime.fromisoformat(value)
                    except (ValueError, TypeError):
                        pass
                
                # Try as numeric string (unix timestamp)
                if dt is None:
                    try:
                        num_value = float(value)
                        if num_value > 1e12:
                            dt = datetime.fromtimestamp(num_value / 1000)
                        else:
                            dt = datetime.fromtimestamp(num_value)
                    except (ValueError, TypeError):
                        return False
            
            if dt is None:
                return False
            
            # Check if within range (current_date - 5 to current_date + 1)
            # For timezone-aware datetimes, convert to naive for comparison
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            
            return min_date <= dt <= max_date
        except (ValueError, TypeError, AttributeError, OSError):
            return False

class TimeValidatorNoConvert(ParameterValidator):
    """Validator for time/timestamp fields that are already timestamps (no conversion needed)."""
    def validate(self, value: Any) -> bool:
        try:
            if value is None:
                return False
            
            current_date = datetime.now()
            min_date = current_date - timedelta(days=5)
            max_date = current_date + timedelta(days=1)
            
            # Value should already be a timestamp (numeric)
            if not isinstance(value, (int, float)):
                # Try to convert string to number
                if isinstance(value, str):
                    value = float(value.strip())
                else:
                    return False
            
            # Convert timestamp to datetime
            if value > 1e12:
                # Milliseconds
                dt = datetime.fromtimestamp(value / 1000)
            else:
                # Seconds
                dt = datetime.fromtimestamp(value)
            
            # Check if within range
            return min_date <= dt <= max_date
        except (ValueError, TypeError, OSError):
            return False

class PresentedOffersStringValidator(ParameterValidator):
    """Validator for presented_offers_string - JSON array where each record must have sku, original_price, currency, type."""
    def __init__(self):
        # SKU pattern (same as sku parameter)
        self.sku_pattern = re.compile(r'^[A-Za-z0-9\._]+$')
        # Currency allowed values (same as currency parameter)
        self.allowed_currencies = {
            'AED', 'AUD', 'BDT', 'BGN', 'BRL', 'CAD', 'CHF', 'CLP', 'CNY', 'COP',
            'CRC', 'CZK', 'DKK', 'DZD', 'EGP', 'EUR', 'GBP', 'GEL', 'GHS', 'HKD',
            'HUF', 'IDR', 'ILS', 'INR', 'IQD', 'JOD', 'JPY', 'KES', 'KRW', 'KWD',
            'KZT', 'LKR', 'MAD', 'MMK', 'MXN', 'MYR', 'NGN', 'NOK', 'NZD', 'PEN',
            'PHP', 'PKR', 'PLN', 'QAR', 'RON', 'RSD', 'RUB', 'SAR', 'SEK', 'SGD',
            'THB', 'TRY', 'TWD', 'UAH', 'USD', 'VND', 'ZAR'
        }
        # Type allowed values
        self.allowed_types = {'Paid', 'Free'}
    
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            
            value = value.strip()
            if not value:
                return False
            
            # Parse JSON
            data = json.loads(value)
            if not isinstance(data, list):
                return False
            
            # Validate each record in the array
            for record in data:
                if not isinstance(record, dict):
                    return False
                
                # Check required fields
                if 'sku' not in record:
                    return False
                if 'original_price' not in record:
                    return False
                if 'currency' not in record:
                    return False
                if 'type' not in record:
                    return False
                
                # Validate sku (pattern: A-Za-z0-9._)
                sku = record['sku']
                if not isinstance(sku, str) or not self.sku_pattern.match(sku):
                    return False
                
                # Validate original_price (can be string number or null)
                original_price = record['original_price']
                if original_price is not None:
                    if isinstance(original_price, str):
                        # Try to parse as float to validate it's a valid number
                        try:
                            float(original_price)
                        except (ValueError, TypeError):
                            return False
                    elif not isinstance(original_price, (int, float)):
                        return False
                
                # Validate currency (must be in allowed set or null)
                currency = record['currency']
                if currency is not None and currency not in self.allowed_currencies:
                    return False
                
                # Validate type (must be "Paid" or "Free")
                type_val = record['type']
                if not isinstance(type_val, str) or type_val not in self.allowed_types:
                    return False
            
            return True
        except (json.JSONDecodeError, TypeError, AttributeError, KeyError):
            return False

class HexadecimalValidator(ParameterValidator):
    """Validator for hexadecimal strings of 4-10 characters."""
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            value = value.strip()
            # Check length (4-10 chars) and hexadecimal pattern
            if not (4 <= len(value) <= 10):
                return False
            return bool(re.match(r'^[0-9a-fA-F]+$', value))
        except:
            return False

class DecimalTimestampValidator(ParameterValidator):
    """Validator for timestamps with decimal precision (e.g., 1764473446766.58)."""
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, (int, float, str)):
                return False
            # Convert to float and check if it's a reasonable timestamp in milliseconds
            float_val = float(value)
            # Should be a reasonable timestamp in milliseconds (2020-2030)
            return 1577836800000 <= float_val <= 1893456000000
        except (ValueError, TypeError):
            return False

class UuidValidator(ParameterValidator):
    """Validator for UUID format strings."""
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            # UUID pattern: 8-4-4-4-12 hex characters separated by hyphens
            # Example: e8c54a5c-460f-4e2c-ba55-b48621816430
            uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
            return bool(re.match(uuid_pattern, value.lower()))
        except:
            return False

# Shared allowed values for item IDs (used by item_id_1-5 and goal_item_id parameters)
# Based on the existing range validator for item_id_1 (0-100000) plus additional IDs
ITEM_ID_ALLOWED_VALUES = [str(i) for i in range(0, 100001)]  # 0 to 100000
# Add additional item IDs
ITEM_ID_ALLOWED_VALUES.extend(['7410', '7411', '7412', '7413', '7414', '7415', '7416', '7417', '7420', '7421', '7422', '7423', '7424', '7425', '7426', '7427'])

# Shared allowed values for item ID names (used by item_id_1_name-5_name and goal_item_id_name parameters)
ITEM_ID_NAME_ALLOWED_VALUES = [
    'item_id_name', 'Action Slate', 'Ticket', 'Beach-Tini', 'Fresh Cocoa Beans', 'Blue One-Piece',
    'Rainbow Shades', 'Single Scoop', 'Tea Leaf', 'Big Paper Cup', 'Milk Cooler', 'Cheese Cube',
    'Greeting Card', 'Message in Bottle', 'Pink Cup Of Tea With Sugar', 'Glass Tea Pot', 'Low Pumps',
    'Boombox', 'Pocket Player', 'Simple Pin', 'Triple Scoop', 'Packs_rarity_Five', 'Burger Meal',
    'Burger Feast', 'Bee Comb', 'Pancakes a la Mode', 'Milk', 'Packs_rarity_Two', 'Golden Tea Set',
    'Spin Toy', 'Headphones', 'Flaming Ring', 'Main Stage', 'Mixing Bowl', 'Crown', "Mermaids Shell",
    'Gold Stilettos', 'Herbal Tea', 'Shoe Box', 'Squeaky Duck', 'Knitted Scarf', 'Poodle Pup',
    'Gladiator Sandals', 'Pink Bikini', 'Basic Swimsuit Set', 'Ingredient Bowl', 'Empty Teapot',
    'Colorful Kaftan', 'White Wedges', 'Flower Clip', 'Ring', 'Canned Food', 'Festive Maracas',
    'Steaming Teapot', 'Large Chest', 'Fancy Beef', 'Chocolate Chip', "Master's Coat", 'Choco-Chip Cookie',
    'Chew Rope', 'Double Scoop', 'cash', 'Bread Oven', 'Island Tea', 'Ice Cream Cake', 'Sliced Bread',
    'Small Mixer', 'Bow Platforms', 'Grocery Crate', 'Resort Slides', 'Unicorn Cake', 'Comb',
    'Cup Of Tea With Plant', 'Toy Box', 'Cocoa Powder', 'Tea Apparatus', 'Deluxe Wellington',
    'Box of Truffles', 'Golden Pumps', 'Coco-Colada', 'Island Punch', 'Banana Split', 'Barbell Rack', 'Hoagie',
    'Magic Stone', 'Triple Golden Cake', 'Blue Long-Sleeve Set', 'Sunny Heels', 'Purple Stilettos',
    'Rottie Pup', 'Chocolate Truffle', 'Dolphin Photo', 'Paper Flower', 'Newspaper', 'Royal Tea Set',
    'Gold Shinny Dress', 'Bread Flour', 'Glass of Red', 'Retro Yellows', 'White Kaftan', 'Plated Cup of Tea',
    'Waffles a la Mode', 'Sundae', 'Tea Plant', 'Entry Ticket', 'Flamingo Shades', 'Tea Pot Generator',
    'Bowl Of Tea', 'Ice Cream Bucket', 'Underwater Camera', 'Hot Dog', 'Paper Cup', 'Luxury Gold Shades',
    'Movie Recorder', 'Rainbow Heels', 'Trick Hat', 'Green Cup Of Tea', 'Empty Tea Pot', 'Round Bed',
    'Red Velvet Cake', 'Truffle Duo', 'Star Target', 'Cheddar Wedge', 'Golden Fascinator', 'Frosty Brew',
    'Credits', 'Green Clip', "Mermaids Tears", 'Deluxe Rainbow Shades', 'Emerald Tea Set', 'Ruby Tea Set',
    'Cinema Reel', 'Beach Bag', 'Clownfish Photo', 'Medium Fridge', 'Fried Chicken Bucket', 'Empty Glass',
    'Designer Slides', 'Toast and Jam', 'Bread Dough', "Collectors' DVD", 'Purple Tee', 'Tea Time',
    'Mermaid Trident', 'Hair Treasure', 'Simple Collar', 'Empty Bowl', 'Color Balls', 'Circus Tent',
    'Packs_rarity_Three', 'Elegant Bow', 'Berry Brain Freeze', 'Blue Boardshorts', 'Short Shorts',
    'Club Sandwich', 'Cream', 'Yellow Fancy One-Piece', 'Soft Serve', 'Drinks Crate', 'Tea Bowl',
    'Classic Popcorn', 'Unbaked Bread', 'Pineapple Shades', 'Tea Bag', 'Leaf Cluster', 'Album Pack 2',
    'Tea Infuser', 'Walking Set', 'Digital Pet', 'Mobile Phone', 'Leopard Loafers', 'Mix Tape',
    'Rock Guitar', 'Gold Trumpet', 'Pink Shades', 'Watermelon Cocktail', 'Woven Heels', 'Fancy Tea Time',
    'Deluxe Dog', 'Red Stilettos', 'Wedding Cake', 'Punch Bowl', 'Pearl', 'Tea & Treats', 'Ball Rope',
    'Blue Tang Photo', 'VIP Carpet', 'Tambourine', 'Moorish Idol Photo', 'Juice', 'Glass Teapot',
    'Lemonade Stand', 'Ear Buds', 'Fluffy Pup', 'Full Bowl', '100 Credits', 'Food Bag', 'Wired Headset',
    'Fresh Mozzarella', 'credits', 'Album Pack 1', 'White Dress', 'Digital Camera', 'Pool Slides',
    'Stage Mic', 'Cup Of Tea With Cookie', 'Tablet', 'Packs_rarity_Four', 'Fancy Clasp', 'Yellow Long-Sleeve',
    'Triple Triple Hamburger', 'Unmixed Dough', 'Heart Shades', 'Rolling Pin', 'Red Slingbacks',
    'Prime Tomahawk', 'Bookmark', 'White Sandals', 'Corgi Pup', 'Swiss Slices', 'Pitcher of Punch',
    'Burger', 'One Rose', "Mermaids Scale", 'Shaped Loaves', 'Punch Fountain', 'Bow Pumps',
    'Crystal Star Shades', 'Luxury Bed', 'Meal Set', 'Cruise Magazine', 'PB&J', 'Golden Award',
    'Sport Tank', 'Knot Slides', 'Mermaid Star', 'Deluxe Sundae', 'Big Bone', 'Golden Pup',
    'Gourmet Meal', 'Smart Watch', 'Dried Cacao Beans', 'Magazine', 'Diamond Heels', 'Show Cannon',
    'Laptop', 'Lava Lamp', 'Purple Fancy Set', 'Beach Flops', 'Summer Spritzer', 'Buckle Sandals',
    'Spiced Tea', 'Square Bed', 'Large Mixer', 'Dog House', 'Cup Of Tea', 'Sporty Pink One-Piece',
    'Tea Date', "Director's Seat", 'Mirror', 'Credit', 'Shepherd Pup', 'Small Chest',
    'Strawberry', 'Strawberry Shake', 'Gym Basics', 'Packs_rarity_One', 'VR Headset',
    'Golden Champagne Tower', 'Gym Station', 'Jump Rope', 'item_id_name', 'credits', 'cash',
    'Yellow Long-Sleeve', 'Yellow Fancy One-Piece', 'Woven Heels', 'Wired Headset', 'White Wedges',
    'White Sandals', 'White Kaftan', 'White Dress', 'Wedding Cake', 'Watermelon Cocktail',
    'Walking Set', 'Waffles a la Mode', 'VIP Carpet', 'Unmixed Dough', 'Unicorn Cake',
    'Underwater Camera', 'Unbaked Bread', 'Truffle Duo', 'Triple Triple Hamburger', 'Triple Scoop',
    'Triple Golden Cake', 'Trick Hat', 'Toy Box', 'Toast and Jam', 'Ticket', 'Tea Time',
    'Tea Pot Generator', 'Tea Plant', 'Tea Leaf', 'Tea Infuser', 'Tea Date', 'Tea Bowl',
    'Tea Bag', 'Tea Apparatus', 'Tea & Treats', 'Tambourine', 'Tablet', 'Swiss Slices',
    'Sunny Heels', 'Sundae', 'Summer Spritzer', 'Steaming Teapot', 'Star Target', 'Stage Mic',
    'Squeaky Duck', 'Square Bed', 'Sporty Pink One-Piece', 'Sport Tank', 'Spin Toy', 'Spiced Tea',
    'Soft Serve', 'Smart Watch', 'Small Mixer', 'Small Chest', 'Sliced Bread', 'Single Scoop',
    'Simple Pin', 'Simple Collar', 'Show Cannon', 'Short Shorts', 'Shoe Box', 'Shepherd Pup',
    'Shaped Loaves', 'Ruby Tea Set', 'Royal Tea Set', 'Round Bed', 'Rottie Pup', 'Rolling Pin',
    'Rock Guitar', 'Ring', 'Retro Yellows', 'Resort Slides', 'Red Velvet Cake', 'Red Stilettos',
    'Red Slingbacks', 'Rainbow Shades', 'Rainbow Heels', 'Purple Tee', 'Purple Stilettos',
    'Purple Fancy Set', 'Punch Fountain', 'Punch Bowl', 'Prime Tomahawk', 'Pool Slides',
    'Poodle Pup', 'Pocket Player', 'Platform Flops', 'Plated Cup of Tea', 'Pitcher of Punch',
    'Pink Shades', 'Pink Cup Of Tea With Sugar', 'Pink Bikini', 'Pineapple Shades', 'Pearl',
    'Paper Flower', 'Paper Cup', 'Pancakes a la Mode', 'Packs_rarity_Two', 'Packs_rarity_Three',
    'Packs_rarity_Four', 'Packs_rarity_Five', 'PB&J', 'One Rose', 'Newspaper', 'Movie Recorder',
    'Moorish Idol Photo', 'Mobile Phone', 'Mixing Bowl', 'Mix Tape', 'Mirror', 'Milk Cooler',
    'Milk', 'Message in Bottle', "Mermaids Tears", "Mermaids Shell", "Mermaids Scale",
    'Mermaid Trident', 'Mermaid Star', 'Medium Fridge', 'Meal Set', "Master's Coat", 'Main Stage',
    'Magic Stone', 'Magazine', 'Luxury Gold Shades', 'Luxury Bed', 'Low Pumps', 'Leopard Loafers',
    'Lemonade Stand', 'Leaf Cluster', 'Lava Lamp', 'Large Mixer', 'Large Chest', 'Laptop',
    'Knot Slides', 'Knitted Scarf', 'Juice', 'Island Tea', 'Island Punch', 'Ingredient Bowl',
    'Ice Cream Cake', 'Ice Cream Bucket', 'Hot Dog', 'Hoagie', 'Herbal Tea', 'Heart Shades',
    'Headphones', 'Hair Treasure', 'Grocery Crate', 'Greeting Card', 'Green Cup Of Tea',
    'Green Clip', 'Gourmet Meal', 'Golden Tea Set', 'Golden Pup', 'Golden Pumps',
    'Golden Fascinator', 'Golden Award', 'Gold Trumpet', 'Gold Stilettos', 'Gold Shinny Dress',
    'Glass of Red', 'Glass Teapot', 'Glass Tea Pot', 'Gladiator Sandals', 'Full Bowl',
    'Frosty Brew', 'Fried Chicken Bucket', 'Fresh Mozzarella', 'Fresh Cocoa Beans', 'Food Bag',
    'Fluffy Pup', 'Flower Clip', 'Flamingo Shades', 'Flaming Ring', 'Festive Maracas',
    'Fancy Tea Time', 'Fancy Clasp', 'Fancy Beef', 'Entry Ticket', 'Empty Teapot',
    'Empty Tea Pot', 'Empty Glass', 'Empty Bowl', 'Emerald Tea Set', 'Elegant Bow',
    'Ear Buds', 'Drinks Crate', 'Dried Cacao Beans', 'Double Scoop', 'Dolphin Photo',
    'Dog House', "Director's Seat", 'Digital Pet', 'Digital Camera', 'Diamond Heels',
    'Designer Slides', 'Deluxe Wellington', 'Deluxe Sundae', 'Deluxe Rainbow Shades',
    'Deluxe Dog', 'Cup Of Tea With Plant', 'Cup Of Tea With Cookie', 'Cup Of Tea',
    'Crystal Star Shades', 'Cruise Magazine', 'Crown', 'Credits', 'Credit', 'Cream',
    'Corgi Pup', 'Comb', 'Colorful Kaftan', 'Color Balls', "Collectors' DVD",
    'Cocoa Powder', 'Coco-Colada', 'Club Sandwich', 'Clownfish Photo', 'Classic Popcorn',
    'Circus Tent', 'Cinema Reel', 'Chocolate Truffle', 'Chocolate Chip', 'Choco-Chip Cookie',
    'Chew Rope', 'Cheese Cube', 'Cheddar Wedge', 'Canned Food', 'Burger Meal', 'Burger Feast',
    'Burger', 'Buckle Sandals', 'Bread Oven', 'Bread Flour', 'Bread Dough', 'Box of Truffles',
    'Bowl Of Tea', 'Bow Pumps', 'Bow Platforms', 'Boombox', 'Bookmark', 'Blue Tang Photo',
    'Blue One-Piece', 'Blue Long-Sleeve Set', 'Blue Boardshorts', 'Big Paper Cup', 'Big Bone',
    'Berry Brain Freeze', 'Bee Comb', 'Beach-Tini', 'Beach Flops', 'Beach Bag',
    'Basic Swimsuit Set', 'Banana Split', 'Ball Rope', 'Album Pack 2', 'Album Pack 1',
    'Action Slate', '100 Credits',
    # Additional item names
    'Frosty Flake', 'Cozy Beanie', 'Snug Mittens', 'Fuzzy Boots', 'Silver Skates', 'Festive Sweater', 'Classic Toboggan', 'Jolly Snowman',
    'Gift Tag', 'Christmas Card', 'Gift Wrap Roll', 'Christmas Stocking', 'Toy Train', 'Rocking Horse', 'Gift Box', "Santa's Toy Sack",
    'Croquembouche'
]

# Define specific validators for different parameter types
VALIDATORS = {
    # ISO format timestamps (with timezone required)
    'eoc_end_time': FormatValidator(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),
    'flowers_end_time': FormatValidator(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),
    'recipes_end_time': IsoTimestampValidator(require_timezone=True),
    'purchase_date': FormatValidator(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),
    'mp_date_partition': IsoTimestampValidator(require_timezone=True),
    
    # OS version validation
    'mp_os_version': AndroidOsVersionValidator(),
    
    # Hexadecimal ID validation (4-10 chars)
    'mp_insert_id': HexadecimalValidator(),
    
    # ISO format timestamps (YYYY-MM-DDTHH:MM:SS format without timezone)
    'timed_board_task_end_time': FormatValidator(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),
    
    # Unix timestamp (milliseconds)
    'server_timestamp_numeric': UnixTimestampMillisValidator(),
    
    # Unix timestamp (seconds) - with decimal precision support
    'updated_timestamp': DecimalTimestampValidator(),
    'original_timestamp': DecimalTimestampValidator(),
    
    # List fields with updated allowed values and any-value lists
    'live_ops_segment_id': ListValidator(allow_any=True),
    'segment_id': ListValidator(allow_any=True),
    'server_segments': ListValidator(),
    'firebase_segments': ListValidator(),
    'eoc_tournament_segment_id': ListValidator(),
    'eoc_room_user_ids': ListValidator(item_validator=ListValidator()),
    'bot_rooms_numbers': ListValidator(item_validator=ListValidator()),
    'sale_packages': ListValidator(),
    'game_board': ListValidator(),
    
    # Numeric ranges with updated constraints
    'flowers_balance': RangeValidator(min_value=0),
    'metapoint_balance': RangeValidator(min_value=0, allow_mean=False),
    'eoc_points_balance': RangeValidator(min_value=0, allow_mean=False),
    'credit_balance': RangeValidator(allow_mean=False),
    'ui_credit_balance': RangeValidator(allow_mean=False),
    'item_quantity_1': RangeValidator(min_value=0, max_value=100000),
    'item_quantity_2': RangeValidator(min_value=0, max_value=100000),
    'item_quantity_3': RangeValidator(min_value=0, max_value=100000),
    'item_quantity_4': RangeValidator(min_value=0, max_value=100000),
    'item_quantity_5': RangeValidator(min_value=0, max_value=100000),
    'semi_locked_tiles': RangeValidator(min_value=0, max_value=22),
    'goal_currency_quantity_1': RangeValidator(),
    'goal_currency_quantity_2': RangeValidator(),
    'goal_reward_item_quantity_1': RangeValidator(),
    'goal_reward_item_quantity_2': RangeValidator(),
    
    # Currency IDs that can be strings or numbers
    'goal_currency_id_1': CurrencyIdValidator(allowed_strings=['Credits', 'MetaPoints', 'Stars']),
    'goal_currency_id_2': CurrencyIdValidator(allowed_strings=['Credits', 'MetaPoints', 'Stars']),
    
    # Other numeric ranges
    'click_id': RangeValidator(),
    'harvest_cooldown': RangeValidator(),
    'algo_task_value_input': RangeValidator(),
    'algo_task_value_output': RangeValidator(),
    'algo_task_difficulty_factor': RangeValidator(),
    'algo_item_order_values_input': ListValidator(),
    
    # Format validators for IDs and versions
    'timed_task_id': NumericIdValidator(),
    'timed_board_task_event_id': NumericIdValidator(),
    'missions_event_id': NumericIdValidator(),
    'live_ops_id': NumericIdValidator(),
    'flowers_event_id': NumericIdValidator(),
    
    # Recipes event ID validation (1-200, no null)
    'recipes_event_id': RangeValidator(min_value=1, max_value=200, allow_null=False),
    
    # FTUE description validation (descriptive text pattern including semicolons, plus signs, and commas)
    'ftue_description': FormatValidator(pattern=r"^[A-Za-z0-9\s,\.'\-;+]+$"),
    
    # Price original string validation (international price formats with various currencies)
    'price_original_string': FormatValidator(pattern=r"^[^\r\n]*[\d\u0660-\u0669\u06F0-\u06F9]+[^\r\n]*$"),
    
    # Exception name validation (allows exception names and stack traces with various characters)
    'exception_name': FormatValidator(pattern=r"^[\s\S]+$"),
    
    # Area within code validation (code location patterns like ClassName.MethodName)
    'area_within_the_code': FormatValidator(pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"),
    
    # Price validation (handles various formats: integers, decimals with dots or commas, quoted or unquoted)
    'price': FormatValidator(pattern=r'^(\d+([.,]\d+)?|"\d+([.,]\d+)?")$'),
    'mp_app_version_string': FormatValidator(r'^[0-9]+\.[0-9]+(\.[0-9]+)?$'),
    'version_float': FormatValidator(r'^[0-9]+\.[0-9]+$'),
    'google_order_number': FormatValidator(r'^[A-Za-z0-9\-\.]+$'),
    
    # MP event name validation (fixed set of allowed event names)
    'mp_event_name': FixedSetValidator(allowed_values=[
        'mp_event_name', 'technical_application_paused', 'scapes_tasks_new_chapter', 'click_tooltip_info',
        'purchase_successful', 'click_sell_board_item', 'impression_game-startup_load-dynamic-textures',
        'click_rewarded_video_inside_ad', 'purchase_failed', 'click_exit_album_screen', 'impression_ftue_flow3_step6',
        'race_bots_request', 'impression_album_screen', 'impression_ftue_flow3_step5', 'click_privacy_popup_agree',
        'impression_ship_animation_started', 'purchase_verification_approval', 'impression_joker_are_you_sure',
        'impression_recipes_popup', 'impression_ftue_flow1_step3', 'impression_ftue_flow11_step1',
        'impression_error_init_game_server', 'dfs_delta_processing_failure', 'fetch_timestamp_error',
        'extra_mode_time_out', 'click_support_link', 'impression_server_heartbeat_failure',
        'impression_error_scape_task_complete', 'impression_game-startup_firebase-init-offline',
        'impression_user_network_disconnected', 'impression_game-startup_game-pre-initialize-for-editor',
        'fetch_ntp_timestamp_negative_value_error', 'realm_client_reset_discard_unsynced_changes',
        'realm_client_reset_completed', 'impression_info', 'flowers_milestone_started', 'rewards_flowers',
        'rewards_scape_task', 'bubble_disappear', 'impression_missions_popup', 'impression_offer_popup',
        'impression_game-startup_mobile-monitoring-initialize', 'move_to_background', 'impression_dialog',
        'impression_promo_popup', 'timed_board_task_started', 'impression_ftue_flow12_step0',
        'user_state_sent_to_server', 'click_missions_badge_board', 'click_promo_popup_badge',
        'impression_ftue_flow10_step6', 'race_bots_respond_locally', 'purchase_transaction_approval_sent',
        'click_att_approve', 'impression_ftue_flow8_step0', 'click_store_button_board_map', 'click_modes_minus',
        'impression_eoc_popup', 'impression_ftue_flow10_step4', 'impression_ftue_flow12_step4', 'rewards_eoc',
        'click_mode_boost_button', 'impression_error_firebase_init_remote_config',
        'impression_process_purchase_invalid_receipt', 'click_Youtube_badge_link', 'click_TikTok_badge_link',
        'impression_error_realm_init_game', 'purchase_verification_timeout', 'click_scapes_tasks_go_button',
        'impression_album_pack_received', 'click_board_button_scapes', 'impression_scapes', 'impression_store',
        'rewarded_video_revenue', 'impression_ftue_flow2_step0',
        'impression_error_gap_between_real_and_ui_credit_balances', 'impression_ftue_flow1_step14',
        'click_modes_plus', 'rewards_timed_task', 'impression_intro_video_end', 'impression_ftue_flow1_step9',
        'impression_ftue_flow3_step7', 'dfs_delta_application_failure', 'rewards_album_set_completion',
        'impression_error_firebase_fetch_and_activate_remote_config', 'impression_how_to_play',
        'impression_game-startup_game-pre-initialize-offline', 'technical_purchase_logic_initialized',
        'dfs_delta_load_failure', 'impression_disco_popup', 'click_privacy_popup_link_policy_button',
        'impression_error_generator_was_not_found', 'impression_error_persistence_storage',
        'impression_race_all_sprints_won', 'impression_eoc_how_to_play', 'recipes_event_milestone_ended',
        'impression_error_reset_harvest_system_timers', 'rewards_recipes', 'impression_error_game_pre_initialize_task',
        'impression_error_initialize_user_state_task', 'impression_game-startup_firebase-init',
        'click_board_tasks_go', 'impression_game-startup_persistence-storage-initialize',
        'board_tasks_task_ready', 'click_promo_popup_c2a', 'impression_ftue_flow8_step2',
        'impression_ftue_flow10_step5', 'impression_ftue_flow1_step11', 'new_version_detected',
        'impression_no_connection', 'impression_ftue_flow2_step4', 'impression_settings',
        'click_timed_board_task_recompletion', 'rewards_rewarded_video', 'click_in_race_how_to_play',
        'impression_ftue_flow6_step0', 'algo_board_tasks_cooldown_finished', 'impression_ftue_flow10_step0',
        'click_in_race_name_edit', 'impression_ftue_flow1_step7', 'impression_ftue_flow1_step13',
        'impression_something_went_wrong_popup', 'click_mode_boost_stop', 'impression_ftue_flow3_step8',
        'impression_ftue_flow11_step2', 'impression_restore_with_local_user_state', 'impression_liveops_not_found_3002',
        'click_disco_badge', 'impression_liveops_not_found_3447', 'ghost_board_task_was_deleted',
        'click_bubble_purchase', 'missions_task_completion', 'impression_game-startup_user-init',
        'impression_game-startup_sentry-initialize', 'back_from_background',
        'impression_game-startup_game-view-initialize', 'low_memory', 'impression_album_pack_open_started',
        'impression_game-startup_hide-loading-plate', 'rewards_sell_board_item',
        'impression_game-startup_smartlook-init', 'algo_board_tasks_cooldown_started',
        'impression_error_exception_detected', 'impression_game-startup_game-pre-initialize',
        'impression_mass_compensation_reward_popup', 'impression_game-startup_smartlook-start-recording',
        'impression_timed_board_task_recompletion', 'click_album_badge_lobby', 'click_rolling_offer_collect',
        'impression_ftue_flow9_step0', 'impression_game-startup_show-native-notifications-permissions',
        'impression_ftue_flow7_step1', 'impression_ftue_flow1_step12', 'impression_ftue_flow12_step2',
        'impression_ftue_flow1_step10', 'impression_http_exception', 'click_race_badge', 'missions_total_completion',
        'http_request_retry_get_race_bots', 'impression_ftue_flow7_step0', 'impression_ftue_flow5_step2',
        'impression_att', 'impression_firebase_config_update_listener', 'rewards_self_collectable',
        'impression_ftue_flow14_step1', 'impression_error_harvest', 'impression_error_duplicate_config_entity',
        'click_eoc_lobby_badge', 'impression_network_reachability_not_reachable',
        'impression_error_update_remote_configs', 'recipes_milestone_started', 'store_init_sucessfull', 'impression_liveops_not_found_3444',
        'click_disco_spin_free', 'algo_ceb_reset', 'board_tasks_new_task',
        'impression_game-startup_notifications-manager-initialize', 'dynamic_configuration_realm_changed',
        'impression_game-startup_facebook-init', 'loading_completed', 'rewarded_video_revenue_from_impression_data',
        'technical_game_configurations_loaded', 'click_offer_badge', 'race_end', 'impression_album_set_screen',
        'click_intro_video_skip', 'impression_game-startup_wait-agreement', 'impression_ship_animation_end',
        'click_in_race_pop_up', 'impression_ftue_flow9_step1', 'click_settings_scapes',
        'impression_race_how_to_play', 'click_missions_badge_lobby', 'impression_game-startup_show-att-popup',
        'impression_error_server_sync_player_state', 'impression_privacy', 'click_eoc_go_board',
        'impression_purchase_failed_no_purchase_data',
        'impression_error_gap_between_real_and_ui_meta_point_balances', 'removed_bubbles_from_feature_data',
        'click_disco_info_button', 'impression_error_wait_for_click_reward_task',
        'impression_error_purchase_successful', 'impression_liveops_not_found_3441',
        'impression_liveops_not_found_3451', 'merge', 'impression_game-startup_check-login-balance',
        'scapes_tasks_cash_deducted', 'impression_game-startup_open-saved-game', 'impression_splash_screen',
        'impression_game-startup_update-ship-state', 'race_bots_respond',
        'impression_game-startup_update-remote-configs', 'impression_intro_video_started',
        'impression_ftue_flow10_step3', 'impression_ftue_flow6_step1', 'impression_ftue_flow8_step1',
        'click_credits_meter_board_map', 'impression_ftue_flow3_step0', 'click_something_went_wrong',
        'impression_ftue_flow2_step1', 'rewards_store', 'connection_to_server_db_fail', 'force_popup',
        'impression_push_native', 'click_joker_are_you_sure', 'impression_ftue_flow3_step4',
        'impression_error_store_package_unavailable', 'impression_ftue_flow2_step5', 'rewards_race',
        'impression_ftue_flow5_step0', 'user_state_sent_to_server_failed', 'impression_ftue_flow12_step3',
        'click_timed_task_go', 'purchase_verification_request', 'click_push_native_dont_allow',
        'impression_error_realm_authentication_failed', 'impression_game-startup_game-server-boot-offline',
        'impression_disco_info', 'impression_race_times_up', 'technical_reset_content_entity_cache',
        'purchase_ignore_duplicate_processing', 'rewards_disco', 'click_recipes_item_info',
        'impression_race_badge', 'impression_board', 'impression_first_time_offer_popup',
        'click_first_time_offer_badge', 'raid_click', 'impression_item_info_popup', 'dfs_no_valid_delta_found',
        'rewards_rolling_offer_collect', 'race_rank_change', 'purchase_native_popup_impression',
        'impression_ftue_flow2_step2', 'impression_ftue_flow2_step3', 'click_store_button_scapes_map',
        'impression_ftue_flow1_step0', 'click_push_native_allow', 'impression_ftue_flow3_step3',
        'impression_ftue_flow10_step2', 'impression_ftue_flow1_step8', 'impression_ftue_flow12_step1',
        'impression_ftue_flow1_step6', 'impression_error_server_service_init_attempt', 'click_sticker',
        'purchase_click', 'click_in_race_avatar_edit', 'impression_ftue_flow7_step2', 'rewards_missions_total',
        'album_set_completion', 'impression_ftue_flow11_step3', 'impression_ftue_flow14_step0',
        'click_info_how_to_play', 'race_bots_timeout', 'impression_flowers_popup', 'click_in_race_times_up',
        'disco_spin_start', 'impression_game-startup_mmp-initialize', 'click_ship_animation_skipped',
        'click_rewarded_video', 'impression_firebase_init_remote_config', 'technical_application_unpaused',
        'impression_game-startup_game-server-boot', 'click_promo_popup_close', 'algo_board_tasks_cooldown_removed',
        'impression_album_pack_open_completed', 'dynamic_configuration_loaded', 'application_quit',
        'rewards_board_task', 'fetch_game_server_timestamp_error', 'impression_race_preparatory_popup',
        'impression_ftue_flow3_step2', 'click_in_race_preparatory_popup', 'race_start', 'click_reward_center',
        'impression_error_firebase_config_update_listener', 'impression_ftue_flow1_step2',
        'impression_ftue_flow11_step4', 'impression_ftue_flow1_step5', 'impression_race_name_edit',
        'impression_rating_prompt', 'authentication_token_was_refreshed', 'click_credits_meter_scapes_map',
        'click_Reddit_badge_link', 'dfs_invalid_delta_state', 'impression_ftue_flow11_step0',
        'click_Facebook_badge_link', 'impression_race_avatar_edit', 'eoc_event_started',
        'impression_game-startup_smartlook-stop-recording', 'click_in_race_all_sprints_won', 'disco_spin_end',
        'impression_error_purchase_ad_mon_reward_successful', 'impression_error_sync_user_state_to_server_task',
        'fetch_ntp_timestamp_error', 'generation', 'impression_firebase_fetch_and_activate_remote_config',
        'rewards_missions_task', 'rewards_harvest_collect', 'click_scapes_button_board', 'click_harvest_collect',
        'impression_game-startup_addressable-load-chapter-dependency', 'impression_store_rewarded_video',
        'click_dialog_exit', 'impression_ftue_flow1_step1', 'impression_race_popup', 'impression_album_popup',
        'impression_ftue_flow1_step4', 'impression_ftue_flow3_step1', 'click_settings_board',
        'impression_ftue_flow5_step1', 'impression_ftue_flow10_step1', 'impression_server_connection_failure',
        'start_validating_user_state', 'timed_board_task_item_collect', 'impression_restore_user_state_by_device_id',
        'click_att_disapprove', 'rewards_mass_compensation', 'rewarded_video_store_interrupted',
        'internet_connection_not_reachable', 'click_Instagram_badge_link', 'impression_error_null_pointer_detected',
        'impression_disco_odds_information', 'flowers_milestone_ended', 'impression_http_error_server_api'
    ]),
    'mc_operation_id': FormatValidator(r'^[A-Za-z0-9\-]+$'),
    'idfa': FormatValidator(r'^[A-Za-z0-9\-]+$'),
    'login_id': RangeValidator(),
    
    # Price and revenue fields
    'price_original': RangeValidator(min_value=0),
    'price_usd': RangeValidator(min_value=0),
    'revenue': RangeValidator(min_value=0),
    'lifetimerevenue': RangeValidator(min_value=0),
    
    # Other IDs and fields with updated patterns
    'auctionid': FormatValidator(r'^[A-Za-z0-9\-\._]+$'),
    'purchase_id': TransactionIdValidator(),
    'merged_items': ListValidator(),
    'generated_items': ListValidator(),
    'mc_operation_status': FormatValidator(r'^[A-Za-z0-9_]+$'),
    'res_liveops_date': FormatValidator(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$'),
    'sku': FormatValidator(r'^[A-Za-z0-9\._]+$'),
    'title': FormatValidator(r'^[A-Za-z0-9\s\-_]+$'),
    'tracker_name': FormatValidator(r'^[A-Za-z0-9_]+$'),
    
    # Time/Timestamp validators (convert to timestamp and check current_date - 5 to current_date + 1)
    'res_timestamp': TimeValidator(),
    'time': TimeValidator(),  # Changed from TimeValidatorNoConvert - time parameter receives ISO format strings
    'timestamp_client': TimeValidator(),
    'mp_mp_api_timestamp_ms': TimeValidator(),
    'mp_processing_time_ms': TimeValidator(),
    
    # Timestamp source validation (fixed set)
    'timestamp_source': FixedSetValidator(allowed_values=['game_server', 'client', 'ntp_server']),
    
    # User/Device identifier validators
    'distinct_id': FormatValidator(pattern=r'^.{24}$'),
    'user_id': FormatValidator(pattern=r'^.{24}$'),
    'device_id': FormatValidator(pattern=r'^.{32}$|^.{36}$'),
    'gaid': FormatValidator(pattern=r'^.{36}$'),
    'mp_distinct_id_before_identity': FormatValidator(pattern=r'^.{24}$'),
    
    # Race request validators
    'race_request_board_level': RangeValidator(min_value=1, max_value=10, allow_null=False),
    'race_request_board_cycle': RangeValidator(min_value=1, max_value=100, allow_null=False),
    'click_on_screen': ClickOnScreenValidator(),
    'active_segments': ActiveSegmentsValidator(),
    'reward_center': RewardCenterValidator(),
    
    # Battery level validation (0-100, allows null)
    'batter_level': RangeValidator(min_value=0, max_value=100, allow_null=True),
    
    # Scapes task ID validation (1-2000, no null)
    'scapes_task_id': RangeValidator(min_value=1, max_value=2000, allow_null=False),
    'scape_task_id': RangeValidator(min_value=1, max_value=543, allow_null=False),
    
    # Screen dimensions validation (200-5000, no null)
    'mp_screen_width': RangeValidator(min_value=200, max_value=5000, allow_null=False),
    'mp_screen_height': RangeValidator(min_value=200, max_value=5000, allow_null=False),
    
    # Screen DPI validation (45-1000, no null)
    'mp_screen_dpi': RangeValidator(min_value=45, max_value=1000, allow_null=False),
    
    # City name validation (allows letters, spaces, apostrophes (regular and curly), hyphens, commas, parentheses, forward slashes, and accented characters)
    # Includes specific patterns: "Tracadie–Sheila", "Burgdorf, Hanover", "L'Aquila", "'Aiea", "Rotenburg (Wümme)", "Al 'Arīsh", "Dällikon / Dällikon (Dorf)"
    'mp_city': FormatValidator(pattern=r"^[A-Za-z\u00C0-\u017F\u0100-\u024F\u1E00-\u1EFF\u2013\u2018\u2019\s'\-\.(),/]+$"),
    
    # Model name validation (allows letters, numbers, spaces, parentheses, commas, forward slashes, plus signs, and various characters)
    # Includes patterns like "motorola moto g stylus (XT2115DL)", "INFINIX MOBILITY LIMITED Infinix X682B", "iPhone17,4", "samsung SM-G980F/DS", "Wingtech Celero5G+", "Wingtech REVVL V+ 5G", "Tinno Celero3 5G+"
    'mp_model': FormatValidator(pattern=r"^[A-Za-z0-9\s()\-_.,/+]+$"),
    
    # Region name validation (allows letters, spaces, apostrophes, hyphens, forward slashes, and accented characters)
    # Includes specific patterns: "Baladiyat ad Dawhah", "Đồng Nai Province"
    'mp_region': FormatValidator(pattern=r"^[A-Za-z\u00C0-\u017F\u0100-\u024F\u1E00-\u1EFF\s'\-\.,/]+$"),
    
    # Country code validation (ISO 3166-1 alpha-2 codes - all 249 country codes + XK)
    'mp_country_code': FixedSetValidator(allowed_values=[
        'AD', 'AE', 'AF', 'AG', 'AI', 'AL', 'AM', 'AO', 'AQ', 'AR',
        'AS', 'AT', 'AU', 'AW', 'AX', 'AZ', 'BA', 'BB', 'BD', 'BE',
        'BF', 'BG', 'BH', 'BI', 'BJ', 'BL', 'BM', 'BN', 'BO', 'BQ',
        'BR', 'BS', 'BT', 'BV', 'BW', 'BY', 'BZ', 'CA', 'CC', 'CD',
        'CF', 'CG', 'CH', 'CI', 'CK', 'CL', 'CM', 'CN', 'CO', 'CR',
        'CU', 'CV', 'CW', 'CX', 'CY', 'CZ', 'DE', 'DJ', 'DK', 'DM',
        'DO', 'DZ', 'EC', 'EE', 'EG', 'EH', 'ER', 'ES', 'ET', 'FI',
        'FJ', 'FK', 'FM', 'FO', 'FR', 'GA', 'GB', 'GD', 'GE', 'GF',
        'GG', 'GH', 'GI', 'GL', 'GM', 'GN', 'GP', 'GQ', 'GR', 'GS',
        'GT', 'GU', 'GW', 'GY', 'HK', 'HM', 'HN', 'HR', 'HT', 'HU',
        'ID', 'IE', 'IL', 'IM', 'IN', 'IO', 'IQ', 'IR', 'IS', 'IT',
        'JE', 'JM', 'JO', 'JP', 'KE', 'KG', 'KH', 'KI', 'KM', 'KN',
        'KP', 'KR', 'KW', 'KY', 'KZ', 'LA', 'LB', 'LC', 'LI', 'LK',
        'LR', 'LS', 'LT', 'LU', 'LV', 'LY', 'MA', 'MC', 'MD', 'ME',
        'MF', 'MG', 'MH', 'MK', 'ML', 'MM', 'MN', 'MO', 'MP', 'MQ',
        'MR', 'MS', 'MT', 'MU', 'MV', 'MW', 'MX', 'MY', 'MZ', 'NA',
        'NC', 'NE', 'NF', 'NG', 'NI', 'NL', 'NO', 'NP', 'NR', 'NU',
        'NZ', 'OM', 'PA', 'PE', 'PF', 'PG', 'PH', 'PK', 'PL', 'PM',
        'PN', 'PR', 'PS', 'PT', 'PW', 'PY', 'QA', 'RE', 'RO', 'RS',
        'RU', 'RW', 'SA', 'SB', 'SC', 'SD', 'SE', 'SG', 'SH', 'SI',
        'SJ', 'SK', 'SL', 'SM', 'SN', 'SO', 'SR', 'SS', 'ST', 'SV',
        'SX', 'SY', 'SZ', 'TC', 'TD', 'TF', 'TG', 'TH', 'TJ', 'TK',
        'TL', 'TM', 'TN', 'TO', 'TR', 'TT', 'TV', 'TW', 'TZ', 'UA',
        'UG', 'UM', 'US', 'UY', 'UZ', 'VA', 'VC', 'VE', 'VG', 'VI',
        'VN', 'VU', 'WF', 'WS', 'XE', 'XK', 'YE', 'YT', 'ZA', 'ZM', 'ZW'
    ]),
    
    # Locked tiles validation (0-64, no null)
    'locked_tiles': RangeValidator(min_value=0, max_value=64, allow_null=False),
    
    # Bubble item ID validation (100-10000, no null)
    'bubble_item_id': RangeValidator(min_value=100, max_value=10000, allow_null=False),
    
    # Bubble cost validation (0-100000, no null)
    'bubble_cost': RangeValidator(min_value=0, max_value=100000, allow_null=False),
    
    # Offer ID validation (0-10000, no null)
    'offer_id': RangeValidator(min_value=0, max_value=10000, allow_null=False),
    
    # Sub offer ID validation (0-30, no null)
    'sub_offer_id': RangeValidator(min_value=0, max_value=30, allow_null=False),
    
    # FCM token validation (must not be empty string)
    'fcm_token': NonEmptyStringValidator(),
    
    # Realm path validation (MongoDB Realm database file paths)
    'realm_path': RealmPathValidator(),
    
    # Realm file size validation (4MB to 12MB in bytes)
    'realm_file_size': RangeValidator(min_value=4000000, max_value=12000000, allow_null=False),
    
    # Version hash validation (MD5 hash format)
    'version_hash': VersionHashValidator(),
    
    # Stickers state validation (current/total format)
    'stickers_state': StickersStateValidator(),
    
    
    # Currency validation (fixed set of allowed currency codes)
    'currency': FixedSetValidator(allowed_values=[
        'AED', 'AUD', 'BDT', 'BGN', 'BRL', 'CAD', 'CHF', 'CLP', 'CNY', 'COP',
        'CRC', 'CZK', 'DKK', 'DZD', 'EGP', 'EUR', 'GBP', 'GEL', 'GHS', 'HKD',
        'HUF', 'IDR', 'ILS', 'INR', 'IQD', 'JOD', 'JPY', 'KES', 'KRW', 'KWD',
        'KZT', 'LKR', 'MAD', 'MMK', 'MXN', 'MYR', 'NGN', 'NOK', 'NZD', 'PEN',
        'PHP', 'PKR', 'PLN', 'QAR', 'RON', 'RSD', 'RUB', 'SAR', 'SEK', 'SGD',
        'THB', 'TRY', 'TWD', 'UAH', 'USD', 'VND', 'ZAR'
    ]),
    
    # Set ID validation (1-100, no null)
    'set_id': RangeValidator(min_value=1, max_value=100, allow_null=False),
    
    # Album duplicates count validation (0-10000, no null)
    'album_duplicates_count': RangeValidator(min_value=0, max_value=10000, allow_null=False),
    
    # Cash deducted validation (1-10000, no null)
    'cash_deducted': RangeValidator(min_value=1, max_value=10000, allow_null=False),
    
    # Memory total validation (0-2000, no null)
    'memory_total': RangeValidator(min_value=0, max_value=2000, allow_null=False),
    
    # Memory mono validation (0-1000, no null)
    'memory_mono': RangeValidator(min_value=0, max_value=1000, allow_null=False),
    
    # Memory allocated validation (0-1000, no null)
    'memory_allocated': RangeValidator(min_value=0, max_value=1000, allow_null=False),
    
    # Memory GFX validation (0-1000, no null)
    'memory_gfx': RangeValidator(min_value=0, max_value=1000, allow_null=False),
    
    # Package ID validation (100-201299, no null)
    'package_id': RangeValidator(min_value=100, max_value=201299, allow_null=False),
    
    # Item name validation (pattern-based to allow any reasonable item name including Packs_rarity format)
    'item_name': FormatValidator(pattern=r"^[A-Za-z0-9\s'\-&\.\(\)_]+$"),
    
    # Item ID name validation (shared fixed set for all item_id_X_name and goal_item_id_name parameters)
    'item_id_1_name': FixedSetValidator(allowed_values=ITEM_ID_NAME_ALLOWED_VALUES),
    'item_id_2_name': FixedSetValidator(allowed_values=ITEM_ID_NAME_ALLOWED_VALUES),
    'item_id_3_name': FixedSetValidator(allowed_values=ITEM_ID_NAME_ALLOWED_VALUES),
    'item_id_4_name': FixedSetValidator(allowed_values=ITEM_ID_NAME_ALLOWED_VALUES),
    'item_id_5_name': FixedSetValidator(allowed_values=ITEM_ID_NAME_ALLOWED_VALUES),
    
    # Item ID validation (1-100000, no null)
    'item_id': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    
    # Free tiles validation (0-64, no null)
    'free_tiles': RangeValidator(min_value=0, max_value=64, allow_null=False),
    
    # Dialog ID validation (10000-1010000, no null)
    'dialog_id': RangeValidator(min_value=10000, max_value=1010000, allow_null=False),
    
    # Goal item ID validation (shared fixed set for all goal_item_id parameters)
    'goal_item_id': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    'goal_item_id_1': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    'goal_item_id_2': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    'goal_item_id_3': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    'goal_item_id_4': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    'goal_item_id_5': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    
    # Goal item ID name validation (shared fixed set)
    'goal_item_id_name': FixedSetValidator(allowed_values=ITEM_ID_NAME_ALLOWED_VALUES),
    
    # Goal reward item ID validation (1-100000, no null)
    'goal_reward_item_id_1': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    'goal_reward_item_id_2': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    
    # FPS validation (-1 to 130, no null) - all FPS parameters allow -1 as special value
    'fps_min': RangeValidator(min_value=-1, max_value=130, allow_null=False),
    'fps_average': RangeValidator(min_value=-1, max_value=130, allow_null=False),
    'fps_current': RangeValidator(min_value=-1, max_value=130, allow_null=False),
    
    # Item level validation (0-20, no null)
    'item_level': RangeValidator(min_value=0, max_value=20, allow_null=False),
    'item_id_1_level': RangeValidator(min_value=0, max_value=20, allow_null=False),
    'item_id_2_level': RangeValidator(min_value=0, max_value=20, allow_null=False),
    
    # Item chain validation (0-10000, no null)
    'item_id_result_chain': RangeValidator(min_value=0, max_value=10000, allow_null=False),
    'item_id_2_chain': RangeValidator(min_value=0, max_value=10000, allow_null=False),
    'item_id_1_chain': RangeValidator(min_value=0, max_value=10000, allow_null=False),
    
    # Video time validation (1-300, no null) - time in seconds
    'video_time': RangeValidator(min_value=1, max_value=300, allow_null=False),
    
    # End of Chapter user rank validation (1-20, no null)
    'eoc_user_rank': RangeValidator(min_value=1, max_value=20, allow_null=False),
    
    # Cycle validation (1-100, no null)
    'cycle': RangeValidator(min_value=1, max_value=100, allow_null=False),
    
    # Store item type validation (fixed set of allowed values)
    'store_item_type': FixedSetValidator(allowed_values=[
        "FirstTimeOffer", "AdMonReward", "SpecialOfferCredits", "Credits", "PersonalOffer"
    ]),
    
    # Package type validation (fixed set of allowed values)
    'package_type': FixedSetValidator(allowed_values=[
        'Credits', 'DiscoWheel', 'FirstTimeOffer', 'PersonalOffer', 'SpecialOfferCredits'
    ]),
    
    # Store item ID validation (100-109999, no null) - same range as package_id
    'store_item_id': RangeValidator(min_value=100, max_value=109999, allow_null=False),
    
    # Purchase funnel ID validation (UUID format)
    'purchase_funnel_id': UuidValidator(),
    
    # Effort validation (1-3000, no null)
    'effort': RangeValidator(min_value=1, max_value=3000, allow_null=False),
    
    # Pack ID validation (60000-80000, no null)
    'pack_id': RangeValidator(min_value=60000, max_value=80000, allow_null=False),
    
    # Pick tier validation (fixed set of allowed values)
    'pick_tier': FixedSetValidator(allowed_values=[
        "Five", "Four", "One", "Three", "Two"
    ]),
    
    # Received stickers list validation (JSON array with slot pattern)
    'received_stickers_list': ReceivedStickersListValidator(),
    
    # Set stickers list validation (JSON array with sticker data pattern)
    'set_stickers_list': FormatValidator(pattern=r'^\[\"(\d+: \'count:\'\d+, rarity_id:\d+\"(,\")?)+\]$'),
    
    # Album state validation (JSON array with album page pattern)
    # Supports empty arrays [] and empty pages like "5:"
    'album_state': FormatValidator(pattern=r'^\[\]$|^\[(\"(\d+:( \d+(, \d+)*)?)\",?)*\]$'),
    
    # Item ID validation (shared fixed set for all item_id parameters)
    'item_id_1': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    'item_id_2': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    'item_id_3': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    'item_id_4': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    'item_id_5': FixedSetValidator(allowed_values=ITEM_ID_ALLOWED_VALUES, allow_null=False),
    
    # Output ID validation (same as item_id_1) - range 1-100000, no null
    'output_id': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    
    # Output ID name validation (pattern-based to allow any reasonable item name including Packs_rarity format)
    'output_id_name': FormatValidator(pattern=r"^[A-Za-z0-9\s'\-&\.\(\)_]+$"),
    
    # Item name self collectable validation (shared fixed set with item names, includes "100 Credits")
    'item_name_self_collectable': FixedSetValidator(allowed_values=ITEM_ID_NAME_ALLOWED_VALUES),
    
    # Album event ID validation (0-20, no null)
    'album_event_id': RangeValidator(min_value=0, max_value=20, allow_null=False),
    
    # OS validation (fixed set including MacOSX and Apple)
    'mp_os': FixedSetValidator(allowed_values=[
        "Android", "iOS", "MacOSX", "Windows", "Linux", "WebGL", "Apple"
    ]),
    
    # Device validation (fixed set including OSXPlayer and IPhonePlayer)
    'mp_device': FixedSetValidator(allowed_values=[
        "iPhone", "iPad", "Android", "OSXPlayer", "WindowsPlayer", "LinuxPlayer", "WebGLPlayer", "IPhonePlayer"
    ]),
    
    # Chapter validation (1-118, allow null)
    'chapter': RangeValidator(min_value=1, max_value=118, allow_null=True),
    'theoretical_chapter': RangeValidator(min_value=1, max_value=120, allow_null=True),
    
    # Active tasks count validation (1-25, no null)
    'active_tasks_count': RangeValidator(min_value=1, max_value=25, allow_null=False),
    
    # Delta credits validation (-200 to 0, no null)
    'delta_credits': RangeValidator(min_value=-200, max_value=0, allow_null=False),
    
    # Pack rarities weights validation (JSON array with slot_X_rarity pattern)
    'pack_rarities_weights': PackRaritiesWeightsValidator(),
    
    # Turbo tips remaining time validation (HH.MM:SS:MS format)
    'turbo_tips_remaining_time': FormatValidator(pattern=r'^\d{2}\.\d{2}:\d{2}:\d{2}$'),
    
    # Reason validation (supports various error/reason formats)
    'reason': FormatValidator(pattern=r'^[A-Za-z0-9\s\-_,:\[\]\(\)\.\/"]+$'),
    
    # Reward destination validation (fixed set for reward_destination_1-5)
    'reward_destination_1': FixedSetValidator(allowed_values=['balance', 'reward_center', 'album']),
    'reward_destination_2': FixedSetValidator(allowed_values=['balance', 'reward_center', 'album']),
    'reward_destination_3': FixedSetValidator(allowed_values=['balance', 'reward_center', 'album']),
    'reward_destination_4': FixedSetValidator(allowed_values=['balance', 'reward_center', 'album']),
    'reward_destination_5': FixedSetValidator(allowed_values=['balance', 'reward_center', 'album']),
    
    # Range validators for various parameters
    'number_of_events': RangeValidator(min_value=1, max_value=50, allow_null=False),
    'eoc_event_id': RangeValidator(min_value=1, max_value=100, allow_null=False),
    'item_sale_cost': RangeValidator(min_value=0, max_value=15, allow_null=False),
    'player_room_number': RangeValidator(min_value=1, max_value=10, allow_null=False),
    'ad_mon_event_id': RangeValidator(min_value=0, max_value=3, allow_null=False),
    
    # Object name validation (pattern for class names like "Common.Model.Item.EmbeddedItemData")
    'object_name': FormatValidator(pattern=r'^[A-Za-z0-9_\.]+$'),
    
    # Entity type validation (fixed set)
    'entity_type': FixedSetValidator(allowed_values=[
        'TimedBoardTaskFeatureConfigData', 'StoreItemData', 'SeriesData', 'RecipesData',
        'PromoFeatureConfigData', 'PersonalOfferConfigData', 'MissionsConfigData',
        'LocalizationData', 'LiveOpsData', 'ItemData', 'GoalData',
        'FusionFairFeatureConfigData', 'FlowersFeatureConfigData', 'DiscoConfigData',
        'AlbumPackConfigData'
    ]),
    
    # URL validation (pattern for various URL formats)
    'url': FormatValidator(pattern=r'^https?://[^\s]+$'),
    
    # Inner exception message validation (allows various error message formats)
    'inner_exception_message': FormatValidator(pattern=r'^[\s\S]+$'),
    
    # Request ID validation (UUID format)
    'request_id': UuidValidator(),
    
    # Range validators for CEB and memory parameters
    'ctv': RangeValidator(min_value=100, max_value=100000, allow_null=False),
    'ceb_before_reset': RangeValidator(min_value=0, max_value=50000, allow_null=False),
    'algo_ceb': RangeValidator(min_value=0, max_value=50000, allow_null=False),
    'total_memory_size': RangeValidator(min_value=1741.0, max_value=23406.0, allow_null=False),
    'counter_per_session_mp_side': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    'counter_per_session_game_side': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    
    # Race leaderboard validation (JSON array pattern)
    'race_leaderboard': FormatValidator(pattern=r'^\[.*\]$'),
    
    # Race-related range validators
    'race_event_remaining_time': RangeValidator(min_value=0, max_value=1000000, allow_null=False),
    'race_board_cycle': RangeValidator(min_value=1, max_value=100, allow_null=False),
    'race_previous_rank': RangeValidator(min_value=1, max_value=5, allow_null=False),
    
    # Location validation (fixed set)
    'location': FixedSetValidator(allowed_values=[
        'location', 'race_preparatory_popup', 'race_popup', 'first_race_in_event', 'Lobby', 'Board'
    ]),
    
    # Race points string validation (pattern like "21/45", "63/75")
    'race_points_string': FormatValidator(pattern=r'^\d+/\d+$'),
    
    # CTA name validation (fixed set)
    'cta_name': FixedSetValidator(allowed_values=[
        'join', 'info', 'go_to_board', 'continue_later', 'close', 'avatar_edit', 'approve'
    ]),
    
    # Generator name validation (fixed set)
    'generator_name': FixedSetValidator(allowed_values=[
        'Beach Bag', 'Bread Oven', 'Dog House', 'Drinks Crate', 'Food Bag', 'Grocery Crate',
        'Haunted Music Box', 'Ice Cream Bucket', 'Large Chest', 'Medium Chest', 'Medium Fridge',
        'Milk Cooler', 'Pastry Oven', 'Shoe Box', 'Small Chest', 'Steaming Teapot', 'Tea Plant',
        'Tea Pot', 'Tea Pot Generator', 'Toy Box', 'Underwater Camera', 'Grocery Bag', 'Recycle Bin'
    ]),
    
    # Generator ID validation (fixed set of float values)
    'generator_id': FixedSetValidator(allowed_values=[
        '299.0', '399.0', '505.0', '599.0', '692.0', '699.0', '781.0', '788.0', '1807.0',
        '2100.0', '2553.0', '2559.0', '3201.0', '3202.0', '3203.0', '5109.0', '5199.0',
        '5299.0', '5499.0', '7337.0', '498.0', '2542.0', '2557.0'
    ]),
    
    # Generator capacity left validation (range 0-20)
    'generator_capacity_left': RangeValidator(min_value=0, max_value=20, allow_null=False),
    
    # Generator capacity allowed validation (range 1-20)
    'generator_capacity_allowed': RangeValidator(min_value=1, max_value=20, allow_null=False),
    
    # Algo active tasks count validation (range 1-10)
    'algo_active_tasks_count': RangeValidator(min_value=1, max_value=10, allow_null=False),
    
    # Delta credits validation (range -400 to 0)
    'delta_credits': RangeValidator(min_value=-400, max_value=0, allow_null=False),
    
    # Is joker validation (fixed set: 0, 1)
    'is_joker': FixedSetValidator(allowed_values=['0', '1']),
    
    # Is event completed validation (fixed set: 0, 1)
    'is_event_completed': FixedSetValidator(allowed_values=['0', '1']),
    
    # Is EOC lobby badge validation (fixed set: 0, 1)
    'is_eoc_lobby_badge': FixedSetValidator(allowed_values=['0', '1']),
    
    # Is spawner validation (fixed set: 0, 1)
    'is_spawner': FixedSetValidator(allowed_values=['0', '1']),
    
    # Is counter validation (fixed set: True, False - no null)
    'is_counter': FixedSetValidator(allowed_values=['True', 'False'], allow_null=False),
    'interrupted_boolean': FixedSetValidator(allowed_values=['True', 'False'], allow_null=False),
    
    # Is offline validation (fixed set: True, False)
    'is_offline': FixedSetValidator(allowed_values=['True', 'False']),
    
    # Bubble index validation (range 0-40)
    'bubble_index': RangeValidator(min_value=0, max_value=40, allow_null=False),
    
    # Exception type validation (fixed set)
    'exception_type': FixedSetValidator(allowed_values=[
        'AppException', 'Exception', 'FileNotFoundException', 'FirebaseException', 'IOException',
        'InvalidOperationException', 'InvalidSignatureException', 'JsonReaderException',
        'MessagePackSerializationException', 'NullReferenceException', 'RealmException',
        'RealmInvalidDatabaseException', 'RealmInvalidTransactionException', 'SocketException',
        'TargetInvocationException', 'TypeInitializationException'
    ]),
    
    # Failure description product ID validation (pattern for product IDs like com.peerplay.mergecruise.credits799)
    'failure_description_product_id': FormatValidator(pattern=r'^com\.peerplay\.mergecruise\.(fto\d+|credits\d+)$'),
    
    # Failure description reason validation (fixed set)
    'failure_description_reason': FixedSetValidator(allowed_values=['DuplicateTransaction', 'PurchasingUnavailable', 'Unknown', 'UserCancelled']),
    
    # Click on screen raid validation (JSON array with tap_count, target_path, timestamp, x, y, threshold)
    'click_on_screen_raid': FormatValidator(pattern=r'^\[.*\]$'),
    
    # Dropped item validation (JSON array with connected_id, drop_id, coordinates, timestamp)
    'dropped_item': FormatValidator(pattern=r'^\[.*\]$'),
    
    # Transaction ID validation (numeric strings or alphanumeric with dots and dashes)
    'transaction_id': FormatValidator(pattern=r'^[\d\w\-\.]+$'),
    
    # Source validation (updated fixed set)
    'source': FixedSetValidator(allowed_values=[
        'race_preparatory_popup', 'race_popup', 'ftue', 'TimedBoardTask', 'Reel',
        'Race', 'PersonalOffer', 'Missions', 'MassCompensation', 'Disco',
        'StoreVisitNoPurchase', 'PostPurchaseIAP'
    ]),
    
    # Received stickers list validation (JSON array with slot patterns like "slot_1: 175, 3, missing, False")
    'received_stickers_list': FormatValidator(pattern=r'^\[.*\]$'),
    
    # Pack rarities weights validation (JSON array with slot_*_rarity patterns)
    'pack_rarities_weights': FormatValidator(pattern=r'^\[.*\]$'),
    
    # Entry reason validation (fixed set)
    'entry_reason': FixedSetValidator(allowed_values=[
        'FeatureStart', 'SetCompletion', 'ClickOnSet', 'ClickOnBadge'
    ]),
    
    # Memory mono validation (range 1-20000)
    'memory_mono': RangeValidator(min_value=1, max_value=20000, allow_null=False),
    
    # GPU total memory size validation (range 1-20000)
    'gpu_total_memory_size': RangeValidator(min_value=1, max_value=20000, allow_null=False),
    
    # Is turbo tip jar validation (fixed set: 0, 1)
    'is_turbo_tip_jar': FixedSetValidator(allowed_values=['0', '1']),
    
    # Trigger for state saving validation (fixed set)
    'trigger_for_state_saving': FixedSetValidator(allowed_values=[
        'ChapterCompleted', 'PurchaseCompleted', 'AppRatingCompleted', 'LoginCompleted'
    ]),
    
    # File name validation (pattern for delta file names like delta_6919c56373244644bf73dac1_1764698748888.json)
    'file_name': FormatValidator(pattern=r'^delta_[a-f0-9]+_\d+\.json$'),
    
    # PO array rewards validation (JSON array with reward patterns like "1: type: None, price: 2,99...")
    'po_array_rewards': FormatValidator(pattern=r'^\[.*\]$'),
    
    # Board tasks info validation (JSON array with task patterns like "8025.ti", "8024.ti")
    'board_tasks_info': FormatValidator(pattern=r'^\[.*\]$'),
    
    # Board task trigger validation (fixed set)
    'board_task_trigger': FixedSetValidator(allowed_values=['Algo', 'FTUE', 'FallBack', 'Injections', 'None']),
    
    # No RV reason validation (text strings like "AdMon is not active.")
    'no_rv_reason': FormatValidator(pattern=r'^.+$'),
    
    # Race segment ID validation (pattern for segment IDs)
    'race_segment_id': FormatValidator(pattern=r'^(Group\d+|default)$'),
    
    # Delta JSON length validation (range 70-100000)
    'delta_json_length': RangeValidator(min_value=70, max_value=100000, allow_null=False),
    
    # Race rank validation (fixed set: 1-5)
    'race_rank': FixedSetValidator(allowed_values=['1', '2', '3', '4', '5']),
    
    # Popup name validation (fixed set)
    'popup_name': FixedSetValidator(allowed_values=[
        'AlbumPopup', 'DiscoPartyPopup', 'FlowersCompletePopup', 'FlowersEndPopup',
        'FlowersProgressPopup', 'FusionFairCompletePopup', 'FusionFairEndPopup',
        'FusionFairProgressPopup', 'MissionsPopup', 'PersonalOffer', 'PersonalOfferRolling',
        'PersonalOfferTriple', 'Profile', 'PromoPopup', 'Race', 'RaceReStart', 'RaceStart',
        'TournamentLeaderboardPopup', 'TutorialDiscoPopup', 'TutorialRacePopup'
    ]),
    
    # Effort validation (range 1-6000)
    'effort': RangeValidator(min_value=1, max_value=6000, allow_null=False),
    
    # Status code numeric validation (range 0-1000)
    'status_code_numeric': RangeValidator(min_value=0, max_value=1000, allow_null=False),
    
    # Sticker ID validation (range 101-198)
    'sticker_id': RangeValidator(min_value=101, max_value=300, allow_null=False),
    
    # Stream queue cleared validation (pattern for comma-separated popup names)
    'stream_queue_cleared': FormatValidator(pattern=r'^[A-Za-z0-9\s,]+$'),
    
    # Avatar name validation (fixed set)
    'avatar_name': FixedSetValidator(allowed_values=[
        'Waitress', 'VacationGuy', 'VacationGrandpa', 'TyrellIdle_Frame', 'TravelGirl',
        'SmartSchoolGirl', 'SmartMan2', 'SmartMan1', 'SmartGirl', 'SchoolGirl',
        'RedheadOnVacation', 'PatryGuy', 'Parrot', 'Mateo_idle_frame', 'Kara_Emotion_idle_frame',
        'HippyGuy2', 'HippyGuy', 'HawaiBeauty', 'Ginder', 'FunnyMan', 'ExplorerGirl',
        'Elsa_IdleFrame', 'CuteNany', 'CurlyHairedGirl', 'CoolGuy', 'Chris_idle_frame',
        'CaptainHamilton_idle_frame', 'BlondeGuy', 'BlondeGirl2', 'BlondeGirl',
        'Bianca_idle_frame', 'Benny_idle_frame'
    ]),
    
    # Is answer invalid validation (fixed set: true, false)
    'is_answer_invalid': FixedSetValidator(allowed_values=['true', 'false']),
    
    # End reason validation (fixed set)
    'end_reason': FixedSetValidator(allowed_values=['win', 'time_out', 'lose']),
    
    # Bots config found validation (fixed set: 0, 1)
    'bots_config_found': FixedSetValidator(allowed_values=['0', '1']),
    
    # Ad impression ID validation (range 0-300)
    'ad_impression_id': RangeValidator(min_value=0, max_value=300, allow_null=False),
    
    # Is race lobby badge validation (fixed set: 0, 1)
    'is_race_lobby_badge': FixedSetValidator(allowed_values=['0', '1']),
    
    # Is disco lobby badge validation (fixed set: 0, 1)
    'is_disco_lobby_badge': FixedSetValidator(allowed_values=['0', '1']),
    
    # Race live ops ID validation (range 1-5000)
    'race_live_ops_id': RangeValidator(min_value=1, max_value=5000, allow_null=False),
    
    # Race board level validation (range 1-10)
    'race_board_level': RangeValidator(min_value=1, max_value=10, allow_null=False),
    
    # Source version validation (same as version_float)
    'source_version': FormatValidator(r'^[0-9]+\.[0-9]+$'),
    
    # Tasks left validation (fixed set: 0.0 to 7.0)
    'tasks_left': FixedSetValidator(allowed_values=['0.0', '1.0', '2.0', '3.0', '4.0', '5.0', '6.0', '7.0']),
    
    # Offer type validation (fixed set)
    'offer_type': FixedSetValidator(allowed_values=['Triple', 'None', 'Disco', 'Single', 'Rolling']),
    
    # Interrupted validation (fixed set: 1 or 0, treat 1.0 as 0.0)
    'interrupted': InterruptedValidator(),
    
    # Rewards frenzy total validation (range 1-1000)
    'rewards_frenzy_total': RangeValidator(min_value=1, max_value=1000, allow_null=False),
    
    # Published to/from validation (macOS path format)
    'published_to': FormatValidator(pattern=r'^/Users/[^/]+/Library/Application Support/[^/]+/mongodb-realm/[a-zA-Z0-9\-_]+/[a-f0-9]{24}/[a-zA-Z0-9_]+\.realm$'),
    'published_from': FormatValidator(pattern=r'^/Users/[^/]+/Library/Application Support/[^/]+/mongodb-realm/[a-zA-Z0-9\-_]+/[a-f0-9]{24}/[a-zA-Z0-9_]+\.realm$'),
    
    # Published date validation (pattern: 2025-12-16T19:14:19)
    'published_date': FormatValidator(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),
    
    # Product ID validation (3 capital letters only)
    'product_id': FormatValidator(pattern=r'^[A-Z]{3}$'),
    
    
    # Restore type validation (fixed set)
    'restore_type': FixedSetValidator(allowed_values=['restore_from_local', 'regular_restore', 'from_offline_mode']),
    
    # CTA name validation (updated with new values)
    'cta_name': FixedSetValidator(allowed_values=[
        'join', 'info', 'go_to_board', 'continue_later', 'close', 'avatar_edit', 'approve'
    ]),
    
    # Spin type validation (updated with new values)
    'spin_type': FixedSetValidator(allowed_values=['Paid', 'Free']),
    
    # Disco tiles validation (JSON array format)
    'disco_tiles': FormatValidator(pattern=r'^\[.*\]$'),
    
    # Disco spin funnel UID validation (24-character hex string)
    'disco_spin_funnel_uid': FormatValidator(pattern=r'^[a-f0-9]{24}$'),
    
    # EOC leaderboard ID string validation (24-character hex string)
    'eoc_leaderboard_id_string': FormatValidator(pattern=r'^[a-f0-9]{24}$'),
    
    # Disco segment ID validation (patterns: default,disco_8, default,disco_7, default, default,disco_ftd_pack)
    'disco_segment_id': FormatValidator(pattern=r'^(default|default,disco_\d+|default,disco_ftd_pack)$'),
    
    # Disco event remaining time validation (range 0-100000)
    'disco_event_remaining_time': RangeValidator(min_value=0, max_value=100000, allow_null=False),
    
    # Animation type validation (fixed set)
    'animation_type': FixedSetValidator(allowed_values=['regular', 'near_win', 'near_miss']),
    
    # Disco tiles won validation (range 0-12)
    'disco_tiles_won': RangeValidator(min_value=0, max_value=12, allow_null=False),
    
    # Presented offers validation (JSON array format)
    'presented_offers': FormatValidator(pattern=r'^\[.*\]$'),
    
    # Presented offers string validation (dedicated validator with required fields)
    'presented_offers_string': PresentedOffersStringValidator(),
    
    # Payment platform validation (fixed set)
    'payment_platform': FixedSetValidator(allowed_values=['apple', 'stash', 'googleplay']),
    
    # Is fallback purchase flow validation (fixed set: 1, 0, treat 1.0/0.0 as 1/0)
    'is_fallback_purchase_flow': FixedSetValidator(allowed_values=['1', '0']),
    
    # Is DP enabled numeric validation (fixed set: 1, 0, treat 1.0/0.0 as 1/0)
    'is_dp_enabled_numeric': FixedSetValidator(allowed_values=['1', '0']),
    
    # Is DP enabled validation (fixed set: True, False)
    'is_dp_enabled': FixedSetValidator(allowed_values=['True', 'False']),
    
    # Checkout link validation (URL pattern)
    'checkout_link': FormatValidator(pattern=r'^https?://[^\s]+$'),
    
    # Cooldown validation (non-negative numeric)
    'cooldown': RangeValidator(min_value=0, allow_null=False),
    
    # Checkout ID validation (pattern: numeric strings, UUIDs, or long alphanumeric strings with dots and underscores)
    # Examples: "2000001084536447", "b6c4b490-4a9e-42a5-88d6-97e2145826fe", "loinecjnpgdknnloimnfjijc.AO-J1OxHw4BzNQ9KYMhsW0KshSDCiCaeuSeJzIMVEpZ_2coUJyk65g2VsQ1lMyaSZm74It7gpKVYPWtySycCse-H9IdeREdXU1Sx_rdiGD0BuAOjfZlIKxE"
    'checkout_id': FormatValidator(pattern=r'^[\d\w\-\._]+$'),
    
    # Failure reason validation (pattern: PurchasingUnavailable)
    'failure_reason': FormatValidator(pattern=r'^PurchasingUnavailable$'),
    
    # Provider type validation (fixed set: Store, Stash)
    'provider_type': FixedSetValidator(allowed_values=['Store', 'Stash']),
    
    # Cap state validation (range 1-5)
    'cap_state': RangeValidator(min_value=1, max_value=5, allow_null=False),
    
    # Cap remaining time validation (range 1-10000)
    'cap_remaining_time': RangeValidator(min_value=1, max_value=10000, allow_null=False),
}

def validate_parameter(param_name: str, value: Any) -> bool:
    """
    Validate a parameter value using the appropriate validator.
    
    Args:
        param_name: Name of the parameter to validate
        value: Value to validate
        
    Returns:
        bool: True if validation passes, False otherwise
    """
    validator = VALIDATORS.get(param_name)
    if validator:
        return validator.validate(value)
    return True  # If no validator defined, assume valid 