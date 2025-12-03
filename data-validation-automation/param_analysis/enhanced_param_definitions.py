"""
Enhanced parameter definitions with specific validation rules based on analysis.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
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
    def __init__(self, allowed_values: List[str]):
        self.allowed_values = set(allowed_values)
    
    def validate(self, value: Any) -> bool:
        try:
            if not isinstance(value, str):
                return False
            
            # Check if the value is in the allowed set
            return value.strip() in self.allowed_values
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
            
            return bool(re.match(android_pattern, value)) or bool(re.match(ios_pattern, value))
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

# Define specific validators for different parameter types
VALIDATORS = {
    # ISO format timestamps (with timezone required)
    'time': IsoTimestampValidator(require_timezone=True),
    'eoc_end_time': FormatValidator(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),
    'flowers_end_time': IsoTimestampValidator(require_timezone=True),
    'recipes_end_time': IsoTimestampValidator(require_timezone=True),
    'purchase_date': FormatValidator(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),
    
    # ISO format timestamps (YYYY-MM-DDTHH:MM:SS format without timezone)
    'timed_board_task_end_time': FormatValidator(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),
    
    # Unix timestamp (milliseconds)
    'res_timestamp': UnixTimestampMillisValidator(),
    'mp_mp_api_timestamp_ms': UnixTimestampMillisValidator(),
    'mp_processing_time_ms': UnixTimestampMillisValidator(),
    'server_timestamp_numeric': UnixTimestampMillisValidator(),
    
    # Unix timestamp (seconds)
    'updated_timestamp': UnixTimestampSecondsValidator(),
    'original_timestamp': UnixTimestampSecondsValidator(),
    
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
    'item_quantity_1': RangeValidator(min_value=0),
    'item_quantity_2': RangeValidator(min_value=0),
    'item_quantity_3': RangeValidator(min_value=0),
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
    
    # FTUE description validation (descriptive text pattern including semicolons)
    'ftue_description': FormatValidator(pattern=r"^[A-Za-z0-9\s,\.'\-;]+$"),
    
    # Price original string validation (international price formats with various currencies)
    'price_original_string': FormatValidator(pattern=r"^[^\r\n]*[\d\u0660-\u0669\u06F0-\u06F9]+[^\r\n]*$"),
    
    # Exception name validation (allows exception names and stack traces with various characters)
    'exception_name': FormatValidator(pattern=r"^[\s\S]+$"),
    
    # Area within code validation (code location patterns like ClassName.MethodName)
    'area_within_the_code': FormatValidator(pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"),
    
    # Price validation (handles various formats: integers, decimals with dots, quoted decimals with commas)
    'price': FormatValidator(pattern=r'^(\d+(\.\d+)?|"\d+(,\d+)?")$'),
    'mp_app_version_string': FormatValidator(r'^[0-9]+\.[0-9]+(\.[0-9]+)?$'),
    'version_float': FormatValidator(r'^[0-9]+\.[0-9]+$'),
    'google_order_number': FormatValidator(r'^[A-Za-z0-9\-\.]+$'),
    'mc_operation_id': FormatValidator(r'^[A-Za-z0-9\-]+$'),
    'idfa': FormatValidator(r'^[A-Za-z0-9\-]+$'),
    'distinct_id': FormatValidator(r'^[A-Za-z0-9\-]+$'),
    'mp_distinct_id_before_identity': FormatValidator(r'^[A-Za-z0-9\-]+$'),
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
    
    'timestamp_client': ClientTimestampValidator(),
    'click_on_screen': ClickOnScreenValidator(),
    'active_segments': ActiveSegmentsValidator(),
    'reward_center': RewardCenterValidator(),
    
    # Battery level validation (0-100, allows null)
    'batter_level': RangeValidator(min_value=0, max_value=100, allow_null=True),
    
    # Scapes task ID validation (1-2000, no null)
    'scapes_task_id': RangeValidator(min_value=1, max_value=2000, allow_null=False),
    'scape_task_id': RangeValidator(min_value=1, max_value=2000, allow_null=False),
    
    # Screen dimensions validation (200-5000, no null)
    'mp_screen_width': RangeValidator(min_value=200, max_value=5000, allow_null=False),
    'mp_screen_height': RangeValidator(min_value=200, max_value=5000, allow_null=False),
    
    # Screen DPI validation (50-1000, no null)
    'mp_screen_dpi': RangeValidator(min_value=50, max_value=1000, allow_null=False),
    
    # City name validation (allows letters, spaces, apostrophes, hyphens, and accented characters)
    'mp_city': FormatValidator(pattern=r"^[A-Za-z\u00C0-\u017F\u0100-\u024F\s'\-\.]+$"),
    
    # Region name validation (allows letters, spaces, apostrophes, hyphens, and accented characters)
    'mp_region': FormatValidator(pattern=r"^[A-Za-z\u00C0-\u017F\u0100-\u024F\s'\-\.,]+$"),
    
    # Country code validation (ISO 3166-1 alpha-2 codes - all 249 country codes)
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
        'VN', 'VU', 'WF', 'WS', 'YE', 'YT', 'ZA', 'ZM', 'ZW'
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
    
    # Sticker ID validation (1-100, no null)
    'sticker_id': RangeValidator(min_value=1, max_value=100, allow_null=False),
    
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
    
    # Package ID validation (100-109999, no null)
    'package_id': RangeValidator(min_value=100, max_value=109999, allow_null=False),
    
    # Item name validation (pattern-based to allow any reasonable item name including Packs_rarity format)
    'item_name': FormatValidator(pattern=r"^[A-Za-z0-9\s'\-&\.\(\)_]+$"),
    
    # Item ID 1 name validation (pattern-based to allow any reasonable item name including Packs_rarity format)
    'item_id_1_name': FormatValidator(pattern=r"^[A-Za-z0-9\s'\-&\.\(\)_]+$"),
    
    # Item ID 2 name validation (pattern-based to allow any reasonable item name including Packs_rarity format)
    'item_id_2_name': FormatValidator(pattern=r"^[A-Za-z0-9\s'\-&\.\(\)_]+$"),
    
    # Item ID validation (1-100000, no null)
    'item_id': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    
    # Free tiles validation (0-64, no null)
    'free_tiles': RangeValidator(min_value=0, max_value=64, allow_null=False),
    
    # Dialog ID validation (10000-1010000, no null)
    'dialog_id': RangeValidator(min_value=10000, max_value=1010000, allow_null=False),
    
    # Goal item ID validation (1-100000, no null) - applies to goal_item_id_1, goal_item_id_2, goal_item_id_3
    'goal_item_id_1': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    'goal_item_id_2': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    'goal_item_id_3': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    
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
    
    # Source validation (fixed set of allowed values)
    'source': FixedSetValidator(allowed_values=[
        "source", "Missions", "PersonalOffer", "Reel", "TimedBoardTask"
    ]),
    
    # Album state validation (JSON array with album page pattern)
    # Supports empty arrays [] and empty pages like "5:"
    'album_state': FormatValidator(pattern=r'^\[\]$|^\[(\"(\d+:( \d+(, \d+)*)?)\",?)*\]$'),
    
    # Item ID range validation (1-100000, no null) - applies to item_id_1, item_id_2, etc.
    'item_id_1': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    'item_id_2': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    'item_id_3': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    'item_id_4': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    'item_id_5': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    
    # Output ID validation (same as item_id_1) - range 1-100000, no null
    'output_id': RangeValidator(min_value=1, max_value=100000, allow_null=False),
    
    # Output ID name validation (pattern-based to allow any reasonable item name including Packs_rarity format)
    'output_id_name': FormatValidator(pattern=r"^[A-Za-z0-9\s'\-&\.\(\)_]+$"),
    
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
    
    # Chapter validation (1-120, allow null)
    'chapter': RangeValidator(min_value=1, max_value=120, allow_null=True),
    'theoretical_chapter': RangeValidator(min_value=1, max_value=120, allow_null=True),
    
    # Active tasks count validation (1-25, no null)
    'active_tasks_count': RangeValidator(min_value=1, max_value=25, allow_null=False),
    
    # Delta credits validation (-200 to -1, no null)
    'delta_credits': RangeValidator(min_value=-200, max_value=-1, allow_null=False),
    
    # Is counter validation (fixed set: True/False)
    'is_counter': FixedSetValidator(allowed_values=["True", "False"]),
    
    # Pack rarities weights validation (JSON array with slot_X_rarity pattern)
    'pack_rarities_weights': PackRaritiesWeightsValidator(),
    
    # Is turbo tip jar validation (fixed set: 1/0)
    'is_turbo_tip_jar': FixedSetValidator(allowed_values=["1", "0"]),
    
    # Turbo tips remaining time validation (HH.MM:SS:MS format)
    'turbo_tips_remaining_time': FormatValidator(pattern=r'^\d{2}\.\d{2}:\d{2}:\d{2}$'),
    
    # Reason validation (supports various error/reason formats)
    'reason': FormatValidator(pattern=r'^[A-Za-z0-9\s\-_,:\[\]\(\)\.\/"]+$'),
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