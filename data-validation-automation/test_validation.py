"""
Test script for parameter validation.
"""

import pandas as pd
import json
from param_analysis.enhanced_param_definitions import VALIDATORS
from param_analysis.param_analyzer import ParameterAnalyzer
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import sys

def validate_with_rules(value: Any, rules: Dict[str, Any]) -> bool:
    """Validate a value against automatically generated rules."""
    try:
        if rules.get('data_type') == 'timestamp':
            # Handle timestamp validation
            timestamp_format = rules['format']
            if timestamp_format == 'unix_ms':
                return 1577836800000 <= float(value) <= 1893456000000  # 2020-2030
            elif timestamp_format == 'unix_s':
                return 1577836800 <= float(value) <= 1893456000  # 2020-2030
            else:
                # Parse as datetime and check range
                dt = pd.to_datetime(value)
                min_date = pd.to_datetime(rules['min_date'])
                max_date = pd.to_datetime(rules['max_date'])
                return min_date <= dt <= max_date
        
        elif rules.get('allowed_values'):
            # Handle fixed set validation
            return value in rules['allowed_values']
        
        elif rules.get('pattern'):
            # Handle string pattern validation
            import re
            return bool(re.match(rules['pattern'], str(value)))
        
        elif 'min_value' in rules and 'max_value' in rules:
            # Handle numeric range validation
            try:
                num_value = float(value)
                return rules['min_value'] <= num_value <= rules['max_value']
            except (ValueError, TypeError):
                return False
        
        elif 'min_length' in rules and 'max_length' in rules:
            # Handle string length validation
            str_value = str(value)
            return rules['min_length'] <= len(str_value) <= rules['max_length']
        
        return True  # If no specific rules apply
    except:
        return False

def test_validation(csv_path: str, chunk_size: int = 10000) -> dict:
    """
    Test validation rules on the entire dataset, processing it in chunks.
    
    Args:
        csv_path: Path to the CSV file
        chunk_size: Number of rows to process at a time
        
    Returns:
        Dictionary with validation results
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Create timestamped filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    validation_log = logs_dir / f'validation_results_{timestamp}.log'
    validation_summary = logs_dir / f'validation_summary_{timestamp}.json'
    
    # Initialize the parameter analyzer
    analyzer = ParameterAnalyzer(csv_path)
    
    # Initialize results dictionary
    results = {}
    
    with open(validation_log, 'w') as log_file:
        log_file.write(f"Loading data from {csv_path}\n")
        print(f"Loading data from {csv_path}")
        
        # Load first chunk to get column names and initialize auto rules
        print("Loading first chunk to initialize rules...")
        first_chunk = pd.read_csv(csv_path, nrows=chunk_size, low_memory=False)
        analyzer.data = first_chunk  # Set data for rule generation
        
        # Initialize auto rules for all columns
        auto_rules = {}
        for column in first_chunk.columns:
            auto_rules[column] = analyzer.generate_validation_rules(column)
            # Initialize results dictionary for each column
            results[column] = {
                'total_tested': 0,
                'valid_count': 0,
                'has_enhanced_validator': column in VALIDATORS,
                'has_auto_rules': column in auto_rules,
                'invalid_examples': [],
                'validation_details': []
            }
        
        # Get total number of rows by counting lines in the file
        print("Counting total rows...")
        with open(csv_path, 'r') as f:
            total_rows = sum(1 for _ in f) - 1  # Subtract 1 for header
        print(f"Total rows to process: {total_rows:,}")
        
        # Process data in chunks
        chunks_processed = 0
        total_chunks = (total_rows + chunk_size - 1) // chunk_size
        
        print("\nStarting validation...")
        for chunk in pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False):
            chunks_processed += 1
            print(f"\nProcessing chunk {chunks_processed}/{total_chunks} ({(chunks_processed/total_chunks)*100:.1f}%)...")
            
            # Test each parameter in the chunk
            for column in chunk.columns:
                values = chunk[column].dropna()
                
                # Test validation for each value in the chunk
                for value in values:
                    is_valid = True
                    details = []
                    
                    # First check enhanced validator if exists
                    if column in VALIDATORS:
                        enhanced_valid = VALIDATORS[column].validate(value)
                        is_valid = enhanced_valid  # Enhanced validation takes precedence
                        details.append(f"Enhanced: {'✓' if enhanced_valid else '✗'}")
                    
                    # Only check automatic rules if no enhanced validator exists
                    elif column in auto_rules:
                        auto_valid = validate_with_rules(value, auto_rules[column])
                        is_valid = auto_valid
                        details.append(f"Auto: {'✓' if auto_valid else '✗'}")
                    
                    # Update results
                    results[column]['total_tested'] += 1
                    if is_valid:
                        results[column]['valid_count'] += 1
                    else:
                        # Keep only first 5 invalid examples
                        if len(results[column]['invalid_examples']) < 5:
                            results[column]['invalid_examples'].append(str(value))
                            results[column]['validation_details'].append(
                                f"{value}: {', '.join(details)}"
                            )
                
                # Log progress for this column in this chunk
                total_count = results[column]['total_tested']
                valid_count = results[column]['valid_count']
                if total_count > 0:
                    valid_ratio = valid_count / total_count
                    
                    # Write chunk results to log file
                    log_file.write(f"Chunk {chunks_processed} results for {column}:\n")
                    log_file.write(f"- Total tested so far: {total_count:,}\n")
                    log_file.write(f"- Valid so far: {valid_count:,} ({valid_ratio:.1%})\n")
        
        # Calculate final validation ratios and clean up results
        print("\nFinalizing results...")
        for column in results:
            total_count = results[column]['total_tested']
            if total_count > 0:
                results[column]['valid_ratio'] = results[column]['valid_count'] / total_count
                
                # Clean up empty lists
                if not results[column]['invalid_examples']:
                    results[column]['invalid_examples'] = None
                if not results[column]['validation_details']:
                    results[column]['validation_details'] = None
                
                # Log final results
                log_file.write(f"\nFinal results for {column}:\n")
                log_file.write(f"- Total tested: {total_count:,}\n")
                log_file.write(f"- Valid: {results[column]['valid_count']:,} ({results[column]['valid_ratio']:.1%})\n")
                log_file.write(f"- Enhanced validator: {'Yes' if results[column]['has_enhanced_validator'] else 'No'}\n")
                log_file.write(f"- Auto rules: {'Yes' if results[column]['has_auto_rules'] else 'No'}\n")
                if results[column]['validation_details']:
                    log_file.write("- Invalid examples:\n")
                    for detail in results[column]['validation_details']:
                        log_file.write(f"  {detail}\n")
        
        # Save final summary as JSON
        with open(validation_summary, 'w') as summary_file:
            json.dump(results, summary_file, indent=2)
        
        log_file.write("\nValidation complete. Results saved to validation_summary.json\n")
        print("\nValidation complete. Results saved to:")
        print(f"- Log file: {validation_log}")
        print(f"- Summary: {validation_summary}")
    
    return results

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python test_validation.py <csv_file>")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    results = test_validation(csv_path) 