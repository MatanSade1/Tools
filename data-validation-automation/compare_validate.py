"""
Comparative validation between two CSV versions.
The script validates a new CSV version against rules and value sets from an old CSV version.
"""

import pandas as pd
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Set, Optional
from param_analysis.enhanced_param_definitions import VALIDATORS
from param_analysis.param_analyzer import ParameterAnalyzer

class ComparativeValidator:
    """Validator that compares new data against rules from old data."""
    
    def __init__(self, old_csv_path: str, new_csv_path: str, chunk_size: int = 10000, exclude_parameters: list = None):
        self.old_csv_path = Path(old_csv_path)
        self.new_csv_path = Path(new_csv_path)
        self.chunk_size = chunk_size
        self.exclude_parameters = set(exclude_parameters) if exclude_parameters else set()
        self.analyzer = ParameterAnalyzer(old_csv_path)
        
        # Debug logging for exclusions
        if self.exclude_parameters:
            print(f"ComparativeValidator initialized with {len(self.exclude_parameters)} excluded parameters:")
            for param in sorted(self.exclude_parameters):
                print(f"  - {param}")
        else:
            print("ComparativeValidator initialized with NO excluded parameters")
        
        # Validation rules and value sets from old data
        self.auto_rules = {}  # Column -> rules mapping
        self.value_sets = {}  # Column -> set of valid values mapping
        self.column_types = {}  # Column -> data type mapping
        
        # Results storage
        self.results = {}
        
        # Create logs directory
        self.logs_dir = Path('logs')
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create timestamped filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.validation_log = self.logs_dir / f'comparative_validation_{timestamp}.log'
        self.validation_summary = self.logs_dir / f'comparative_summary_{timestamp}.json'
        self.validation_summary_main = self.logs_dir / f'comparative_summary_main_{timestamp}.json'
    
    def analyze_old_data(self):
        """Analyze old CSV to extract rules and valid value sets."""
        print("Analyzing old CSV data...")
        
        # Load first chunk to get column names and initialize
        first_chunk = pd.read_csv(self.old_csv_path, nrows=self.chunk_size, low_memory=False)
        self.analyzer.data = first_chunk
        
        # Initialize storage for each column (excluding excluded parameters)
        for column in first_chunk.columns:
            # Strong exclusion check with debug logging
            if column in self.exclude_parameters:
                print(f"EXCLUDED: Skipping parameter '{column}' (in exclusion list)")
                continue
                
            print(f"Initializing analysis for column: {column}")
            self.value_sets[column] = set()
            self.auto_rules[column] = self.analyzer.generate_validation_rules(column)
            
            # Detect if column should use value set or rules
            if column in VALIDATORS:
                # Use enhanced validator
                self.column_types[column] = 'enhanced'
            elif self.auto_rules[column].get('allowed_values') or self.is_categorical(first_chunk[column]):
                # Use value set validation
                self.column_types[column] = 'value_set'
            else:
                # Use rule-based validation
                self.column_types[column] = 'rules'
        
        # Process old CSV in chunks to build value sets
        print("\nBuilding value sets from old CSV...")
        chunks_processed = 0
        for chunk in pd.read_csv(self.old_csv_path, chunksize=self.chunk_size, low_memory=False):
            chunks_processed += 1
            print(f"Processing chunk {chunks_processed}...")
            
            for column in chunk.columns:
                # Strong exclusion check during value set building
                if column in self.exclude_parameters:
                    continue
                if column in self.column_types and self.column_types[column] == 'value_set':
                    # Add values to set, converting to strings for consistency
                    self.value_sets[column].update(chunk[column].dropna().astype(str))
        
        print("\nOld data analysis complete!")
        print(f"Analyzed {chunks_processed} chunks")
        
        # Save analysis results
        self.save_analysis_results()
    
    def is_categorical(self, series: pd.Series, unique_ratio_threshold: float = 0.01) -> bool:
        """
        Determine if a column should be treated as categorical based on its unique values.
        
        Args:
            series: The column data
            unique_ratio_threshold: Maximum ratio of unique values to total values to be considered categorical
            
        Returns:
            bool: Whether the column should be treated as categorical
        """
        unique_count = series.nunique()
        total_count = len(series)
        
        if total_count == 0:
            return False
        
        unique_ratio = unique_count / total_count
        return unique_ratio <= unique_ratio_threshold
    
    def validate_value(self, value: Any, column: str) -> tuple[bool, Optional[str]]:
        """
        Validate a single value against the rules or value set for its column.
        
        Returns:
            tuple: (is_valid, error_message)
        """
        if pd.isna(value):
            return True, None
        
        str_value = str(value)
        
        if self.column_types[column] == 'enhanced':
            # Use enhanced validator
            is_valid = VALIDATORS[column].validate(value)
            return is_valid, None if is_valid else "Failed enhanced validation"
        
        elif self.column_types[column] == 'value_set':
            # Check against value set
            is_valid = str_value in self.value_sets[column]
            return is_valid, None if is_valid else f"Value not found in old data: {str_value}"
        
        else:
            # Use rule-based validation
            rules = self.auto_rules[column]
            try:
                if rules.get('data_type') == 'timestamp':
                    # Handle timestamp validation
                    timestamp_format = rules['format']
                    if timestamp_format == 'unix_ms':
                        is_valid = 1577836800000 <= float(value) <= 1893456000000  # 2020-2030
                    elif timestamp_format == 'unix_s':
                        is_valid = 1577836800 <= float(value) <= 1893456000  # 2020-2030
                    else:
                        # Parse as datetime and check range
                        dt = pd.to_datetime(value)
                        min_date = pd.to_datetime(rules['min_date'])
                        max_date = pd.to_datetime(rules['max_date'])
                        is_valid = min_date <= dt <= max_date
                    return is_valid, None if is_valid else f"Invalid timestamp: {value}"
                
                elif rules.get('pattern'):
                    # Handle string pattern validation
                    import re
                    is_valid = bool(re.match(rules['pattern'], str_value))
                    return is_valid, None if is_valid else f"Pattern mismatch: {value}"
                
                elif 'min_value' in rules and 'max_value' in rules:
                    # Handle numeric range validation
                    try:
                        num_value = float(value)
                        is_valid = rules['min_value'] <= num_value <= rules['max_value']
                        return is_valid, None if is_valid else f"Out of range: {value}"
                    except (ValueError, TypeError):
                        return False, f"Invalid numeric value: {value}"
                
                elif 'min_length' in rules and 'max_length' in rules:
                    # Handle string length validation
                    is_valid = rules['min_length'] <= len(str_value) <= rules['max_length']
                    return is_valid, None if is_valid else f"Invalid length: {value}"
                
                return True, None  # If no specific rules apply
                
            except Exception as e:
                return False, f"Validation error: {str(e)}"
    
    def validate_new_data(self):
        """Validate new CSV against rules and value sets from old CSV."""
        print("\nStarting validation of new CSV...")
        
        # Get total number of rows
        with open(self.new_csv_path, 'r') as f:
            total_rows = sum(1 for _ in f) - 1  # Subtract 1 for header
        total_chunks = (total_rows + self.chunk_size - 1) // self.chunk_size
        
        # Initialize results
        for column in self.column_types:
            self.results[column] = {
                'total_tested': 0,
                'valid_count': 0,
                'validation_type': self.column_types[column],
                'invalid_examples': [],
                'error_messages': set()
            }
        
        # Process new CSV in chunks
        print(f"\nProcessing {total_rows:,} rows...")
        chunks_processed = 0
        
        with open(self.validation_log, 'w') as log_file:
            log_file.write(f"Validating new CSV: {self.new_csv_path}\n")
            log_file.write(f"Using rules from: {self.old_csv_path}\n\n")
            
            for chunk in pd.read_csv(self.new_csv_path, chunksize=self.chunk_size, low_memory=False):
                chunks_processed += 1
                print(f"\nProcessing chunk {chunks_processed}/{total_chunks} ({(chunks_processed/total_chunks)*100:.1f}%)...")
                
                # Validate each column in the chunk (excluding excluded parameters)
                for column in chunk.columns:
                    # Strong exclusion check during validation
                    if column in self.exclude_parameters:
                        continue
                    if column not in self.column_types:
                        print(f"Warning: New column found: {column}")
                        continue
                    
                    values = chunk[column]
                    for value in values:
                        is_valid, error_msg = self.validate_value(value, column)
                        
                        # Update results
                        self.results[column]['total_tested'] += 1
                        if is_valid:
                            self.results[column]['valid_count'] += 1
                        else:
                            if len(self.results[column]['invalid_examples']) < 5:
                                self.results[column]['invalid_examples'].append(str(value))
                            if error_msg:
                                self.results[column]['error_messages'].add(error_msg)
                    
                    # Log progress for this column
                    total_count = self.results[column]['total_tested']
                    valid_count = self.results[column]['valid_count']
                    if total_count > 0:
                        valid_ratio = valid_count / total_count
                        log_file.write(f"\nChunk {chunks_processed} results for {column}:\n")
                        log_file.write(f"- Total tested so far: {total_count:,}\n")
                        log_file.write(f"- Valid so far: {valid_count:,} ({valid_ratio:.1%})\n")
        
        # Calculate final results and save
        self.save_validation_results()
    
    def save_analysis_results(self):
        """Save the analysis results from the old CSV."""
        analysis_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        analysis_file = self.logs_dir / f'old_data_analysis_{analysis_timestamp}.json'
        
        analysis_results = {
            'column_types': self.column_types,
            'auto_rules': self.auto_rules,
            'value_sets': {col: list(values) for col, values in self.value_sets.items()
                          if self.column_types[col] == 'value_set'}
        }
        
        with open(analysis_file, 'w') as f:
            json.dump(analysis_results, f, indent=2)
        
        print(f"\nAnalysis results saved to: {analysis_file}")
    
    def save_validation_results(self):
        """Save the validation results."""
        print("\nFinalizing results...")
        
        # SAFETY CHECK: Remove any excluded parameters that somehow made it into results
        excluded_found_in_results = []
        for column in list(self.results.keys()):
            if column in self.exclude_parameters:
                excluded_found_in_results.append(column)
                del self.results[column]
                print(f"SAFETY CHECK: Removed excluded parameter '{column}' from results")
        
        if excluded_found_in_results:
            print(f"WARNING: Found {len(excluded_found_in_results)} excluded parameters in results that were cleaned up")
        
        # Convert results to JSON-serializable format
        final_results = {}
        main_results = {}  # Filtered results for main report
        
        for column, result in self.results.items():
            # Skip excluded parameters (safety check)
            if column in self.exclude_parameters:
                print(f"Skipping excluded parameter in results: {column}")
                continue
                
            result_data = {
                'total_tested': result['total_tested'],
                'valid_count': result['valid_count'],
                'valid_ratio': result['valid_count'] / result['total_tested'] if result['total_tested'] > 0 else 0,
                'validation_type': result['validation_type'],
                'invalid_examples': result['invalid_examples'] if result['invalid_examples'] else None,
                'error_messages': list(result['error_messages']) if result['error_messages'] else None
            }
            
            # Add to full results
            final_results[column] = result_data
            
            # Add to main results only if there are invalid examples
            if result['invalid_examples']:
                main_results[column] = result_data
        
        # Save full summary to JSON
        with open(self.validation_summary, 'w') as f:
            json.dump(final_results, f, indent=2)
        
        # Save filtered main summary to JSON
        with open(self.validation_summary_main, 'w') as f:
            json.dump(main_results, f, indent=2)
        
        print("\nValidation complete! Results saved to:")
        print(f"- Log file: {self.validation_log}")
        print(f"- Full summary: {self.validation_summary}")
        print(f"- Main summary (parameters with invalid examples): {self.validation_summary_main}")
        print(f"- Main summary contains {len(main_results)} parameters with validation issues")

def main():
    """Main function to run comparative validation."""
    if len(sys.argv) != 3:
        print("Usage: python compare_validate.py <old_csv> <new_csv>")
        sys.exit(1)
    
    old_csv = sys.argv[1]
    new_csv = sys.argv[2]
    
    validator = ComparativeValidator(old_csv, new_csv)
    validator.analyze_old_data()
    validator.validate_new_data()

if __name__ == '__main__':
    import sys
    main() 