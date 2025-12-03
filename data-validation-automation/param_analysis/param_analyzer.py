"""
Main analysis logic for parameter validation.
"""

import pandas as pd
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import re

from .param_definitions import (
    ParameterType,
    ParameterDefinition,
    FixedSetParameter,
    ConstrainedRangeParameter
)
from .utils import get_logger


class ParameterAnalyzer:
    """Main class for analyzing and validating parameters."""
    
    def __init__(self, csv_path: str, log_level: int = None):
        """
        Initialize the analyzer with a CSV file path.
        
        Args:
            csv_path: Path to the CSV file to analyze
            log_level: Optional logging level override
        """
        self.csv_path = Path(csv_path)
        self.data = None
        self.parameter_definitions = {}
        self.logger = get_logger('analyzer')
        if log_level:
            self.logger.setLevel(log_level)
        
        self.logger.info(f"Initializing ParameterAnalyzer with CSV: {csv_path}")
        self.logger.debug("Parameter definitions initialized as empty dictionary")
    
    def load_data(self) -> None:
        """
        Load the CSV data into memory.
        
        Raises:
            FileNotFoundError: If the CSV file doesn't exist
            pd.errors.EmptyDataError: If the CSV file is empty
            pd.errors.ParserError: If the CSV file is malformed
        """
        self.logger.info(f"Loading data from {self.csv_path}")
        start_time = time.time()
        
        try:
            self.data = pd.read_csv(self.csv_path)
            load_time = time.time() - start_time
            
            self.logger.info(
                f"Successfully loaded {len(self.data):,} rows with {len(self.data.columns)} columns "
                f"in {load_time:.2f} seconds"
            )
            self.logger.debug(f"Column names: {', '.join(self.data.columns)}")
            
        except FileNotFoundError:
            self.logger.error(f"CSV file not found: {self.csv_path}")
            raise
        except pd.errors.EmptyDataError:
            self.logger.error("CSV file is empty")
            raise
        except pd.errors.ParserError as e:
            self.logger.error(f"Error parsing CSV file: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error loading CSV: {str(e)}")
            raise
    
    def analyze_parameters(self) -> Dict[str, ParameterDefinition]:
        """
        Analyze all parameters in the dataset.
        
        Returns:
            Dictionary mapping parameter names to their definitions
        """
        if self.data is None:
            self.logger.error("No data loaded. Call load_data() first.")
            raise ValueError("No data loaded")
        
        self.logger.info("Starting parameter analysis")
        start_time = time.time()
        
        for column in self.data.columns:
            self.logger.info(f"Analyzing parameter: {column}")
            try:
                param_type = self.detect_parameter_type(column)
                self.logger.debug(f"Detected parameter type: {param_type}")
                
                validation_rules = self.generate_validation_rules(column)
                self.logger.debug(f"Generated validation rules: {validation_rules}")
                
                # Create parameter definition based on type
                if param_type == ParameterType.FIXED_SET:
                    self.parameter_definitions[column] = FixedSetParameter(
                        name=column,
                        description=f"Parameter: {column}",
                        validation_rules=validation_rules
                    )
                else:
                    self.parameter_definitions[column] = ConstrainedRangeParameter(
                        name=column,
                        description=f"Parameter: {column}",
                        validation_rules=validation_rules
                    )
                
                self.logger.info(f"Successfully analyzed parameter: {column}")
                
            except Exception as e:
                self.logger.error(f"Error analyzing parameter {column}: {str(e)}")
                continue
        
        analysis_time = time.time() - start_time
        self.logger.info(
            f"Parameter analysis completed in {analysis_time:.2f} seconds. "
            f"Analyzed {len(self.parameter_definitions)} parameters."
        )
        
        return self.parameter_definitions
    
    def detect_parameter_type(self, column: str) -> ParameterType:
        """
        Detect the type of a parameter based on its values.
        
        Args:
            column: Name of the column to analyze
            
        Returns:
            Detected parameter type
        """
        self.logger.debug(f"Detecting type for parameter: {column}")
        
        # Get unique values count
        unique_count = self.data[column].nunique()
        total_count = len(self.data)
        unique_ratio = unique_count / total_count
        
        self.logger.debug(
            f"Parameter {column} has {unique_count:,} unique values "
            f"({unique_ratio:.2%} of total)"
        )
        
        # If unique values are less than 20 or less than 1% of total, consider it fixed set
        if unique_count < 20 or unique_ratio < 0.01:
            self.logger.debug(f"Parameter {column} classified as FIXED_SET")
            return ParameterType.FIXED_SET
        
        self.logger.debug(f"Parameter {column} classified as CONSTRAINED_RANGE")
        return ParameterType.CONSTRAINED_RANGE
    
    def is_timestamp(self, values: pd.Series) -> bool:
        """Check if a series contains timestamp values."""
        try:
            # Try parsing a sample of non-null values
            sample = values.dropna().sample(min(100, len(values.dropna())))
            
            # Try different timestamp formats
            for value in sample:
                if isinstance(value, (int, float)):
                    # Check if it's a reasonable timestamp (between 2020 and 2030)
                    if 1577836800 <= float(value) <= 1893456000:  # 2020-01-01 to 2030-01-01
                        return True
                    if 1577836800000 <= float(value) <= 1893456000000:  # Same in milliseconds
                        return True
                elif isinstance(value, str):
                    # Try parsing as ISO format
                    try:
                        datetime.fromisoformat(value.replace('Z', '+00:00'))
                        return True
                    except ValueError:
                        pass
            
            return False
        except:
            return False
    
    def analyze_distinct_id(self, values: pd.Series) -> Dict[str, Any]:
        """Analyze distinct_id field for patterns and constraints."""
        values = values.dropna()
        
        # Get basic stats
        lengths = values.astype(str).str.len()
        unique_count = values.nunique()
        
        # Detect common patterns
        sample = values.sample(min(1000, len(values)))
        patterns = []
        for value in sample:
            value = str(value)
            if value.isdigit():
                patterns.append("numeric")
            elif value.isalnum():
                patterns.append("alphanumeric")
            elif re.match(r'^[0-9a-f-]+$', value.lower()):
                patterns.append("uuid-like")
            elif re.match(r'^[A-Za-z0-9+/=]+$', value):
                patterns.append("base64-like")
            else:
                patterns.append("other")
        
        # Determine most common pattern
        pattern_counts = pd.Series(patterns).value_counts()
        dominant_pattern = pattern_counts.index[0] if len(pattern_counts) > 0 else None
        pattern_consistency = (pattern_counts.iloc[0] / len(patterns)) if len(pattern_counts) > 0 else 0
        
        # Generate regex pattern if consistent
        regex_pattern = None
        if dominant_pattern == "uuid-like" and pattern_consistency > 0.9:
            regex_pattern = r'^[0-9a-f-]+$'
        elif dominant_pattern == "base64-like" and pattern_consistency > 0.9:
            regex_pattern = r'^[A-Za-z0-9+/=]+$'
        elif dominant_pattern == "numeric" and pattern_consistency > 0.9:
            regex_pattern = r'^\d+$'
        elif dominant_pattern == "alphanumeric" and pattern_consistency > 0.9:
            regex_pattern = r'^[A-Za-z0-9]+$'
        
        return {
            "data_type": str(values.dtype),
            "min_length": int(lengths.min()),
            "max_length": int(lengths.max()),
            "unique_count": int(unique_count),
            "is_unique": unique_count == len(values),
            "dominant_pattern": dominant_pattern,
            "pattern_consistency": float(pattern_consistency),
            "regex_pattern": regex_pattern,
            "sample_values": values.sample(min(5, len(values))).tolist()
        }
    
    def analyze_time_field(self, values: pd.Series) -> Dict[str, Any]:
        """Analyze time field for format and constraints."""
        values = values.dropna()
        
        try:
            # Determine timestamp format
            if values.dtype == 'float64' or values.dtype == 'int64':
                # Convert to datetime
                if max(values) > 2e10:  # Milliseconds
                    timestamps = pd.to_datetime(values, unit='ms')
                    timestamp_format = "unix_ms"
                else:  # Seconds
                    timestamps = pd.to_datetime(values, unit='s')
                    timestamp_format = "unix_s"
            else:
                timestamps = pd.to_datetime(values)
                # Check if ISO format
                if all(str(x).endswith('Z') or '+' in str(x) or '-' in str(x) for x in values.sample(min(10, len(values)))):
                    timestamp_format = "iso"
                else:
                    timestamp_format = "datetime"
            
            # Get time range stats
            time_range = {
                "data_type": "timestamp",
                "format": timestamp_format,
                "min_date": timestamps.min().isoformat(),
                "max_date": timestamps.max().isoformat(),
                "unique_count": int(values.nunique()),
                "is_unique": values.nunique() == len(values),
                "sample_values": values.sample(min(5, len(values))).tolist()
            }
            
            # Add format-specific constraints
            if timestamp_format in ["unix_s", "unix_ms"]:
                time_range.update({
                    "min_value": float(values.min()),
                    "max_value": float(values.max())
                })
            
            return time_range
            
        except Exception as e:
            self.logger.warning(f"Failed to parse time values: {e}")
            return {
                "data_type": str(values.dtype),
                "error": str(e),
                "sample_values": values.sample(min(5, len(values))).tolist()
            }
    
    def generate_validation_rules(self, column: str) -> Dict[str, Any]:
        """
        Generate validation rules for a parameter.
        
        Args:
            column: Name of the column to analyze
            
        Returns:
            Dictionary of validation rules
        """
        self.logger.debug(f"Generating validation rules for parameter: {column}")
        
        param_type = self.detect_parameter_type(column)
        values = self.data[column].dropna()
        
        if param_type == ParameterType.FIXED_SET:
            # For fixed set parameters, get unique values and their distribution
            value_counts = values.value_counts().to_dict()
            allowed_values = list(value_counts.keys())
            
            self.logger.debug(
                f"Fixed set parameter {column} has {len(allowed_values)} allowed values: "
                f"{', '.join(map(str, allowed_values))}"
            )
            
            return {
                "allowed_values": allowed_values,
                "value_distribution": value_counts
            }
        else:
            # For constrained range parameters, analyze value patterns
            rules = {
                "data_type": str(values.dtype),
                "null_count": int(self.data[column].isna().sum()),
                "null_percentage": round(100 * self.data[column].isna().mean(), 2)
            }
            
            # Special handling for distinct_id
            if column == "distinct_id":
                rules.update(self.analyze_distinct_id(values))
            
            # Special handling for time fields
            elif column in ["time", "timestamp", "timestamp_client", "res_timestamp"] or self.is_timestamp(values):
                rules.update(self.analyze_time_field(values))
            
            # Length constraints for string values
            elif values.dtype == 'object':
                lengths = values.astype(str).str.len()
                rules.update({
                    "min_length": int(lengths.min()),
                    "max_length": int(lengths.max()),
                    "unique_count": int(values.nunique()),
                    "is_unique": values.nunique() == len(values),
                    "pattern": self.detect_pattern(values) if len(values) > 0 else None
                })
            
            # Numeric constraints
            elif pd.api.types.is_numeric_dtype(values):
                rules.update({
                    "min_value": float(values.min()),
                    "max_value": float(values.max()),
                    "mean_value": float(values.mean()),
                    "median_value": float(values.median()),
                    "std_dev": float(values.std()),
                    "is_integer": all(values.dropna().apply(lambda x: float(x).is_integer()))
                })
            
            # Add sample values for reference
            rules["sample_values"] = values.sample(min(5, len(values))).tolist()
            
            return rules
    
    def detect_pattern(self, values: pd.Series) -> Optional[str]:
        """Try to detect a pattern in string values."""
        try:
            # Take a sample of values
            sample = values.dropna().sample(min(100, len(values.dropna())))
            
            # Check for common patterns
            patterns = []
            for value in sample:
                value = str(value)
                if value.isdigit():
                    patterns.append("\\d+")
                elif value.isalpha():
                    patterns.append("[A-Za-z]+")
                elif value.isalnum():
                    patterns.append("[A-Za-z0-9]+")
                elif '-' in value and all(part.isalnum() for part in value.split('-')):
                    patterns.append("[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+")
                elif '.' in value and all(part.isalnum() for part in value.split('.')):
                    patterns.append("[A-Za-z0-9]+(?:\\.[A-Za-z0-9]+)+")
            
            # If all values match the same pattern, return it
            if len(set(patterns)) == 1:
                return patterns[0]
            
            return None
        except:
            return None 