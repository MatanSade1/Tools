#!/usr/bin/env python3
"""
Generate a detailed parameter changes report between two CSV versions.
Shows new parameters and removed parameters with validation types and example values.
"""

import pandas as pd
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, List, Any, Tuple
from param_analysis.param_analyzer import ParameterAnalyzer

def is_effectively_null(series: pd.Series) -> bool:
    """
    Check if a series is effectively null (all null, empty strings, or zeros).
    """
    if series.isnull().all():
        return True
    
    # Remove null values and check remaining
    non_null = series.dropna()
    if len(non_null) == 0:
        return True
    
    # Convert to string and check for empty strings or zeros
    str_values = non_null.astype(str).str.strip()
    non_empty = str_values[str_values != '']
    
    if len(non_empty) == 0:
        return True
    
    # Check if all remaining values are zero (as string)
    zero_variants = {'0', '0.0', '0.00'}
    if all(val in zero_variants for val in non_empty):
        return True
    
    return False

def get_validation_type(analyzer: ParameterAnalyzer, column: str, sample_values: List[str]) -> str:
    """
    Determine the validation type for a parameter.
    """
    try:
        # Try to generate validation rules
        rules = analyzer.generate_validation_rules(column)
        
        if rules.get('data_type') == 'timestamp':
            return 'Timestamp'
        elif rules.get('allowed_values'):
            return f'Fixed Set ({len(rules["allowed_values"])} values)'
        elif rules.get('pattern'):
            return 'String Pattern'
        elif 'min_value' in rules and 'max_value' in rules:
            return f'Numeric Range ({rules["min_value"]} - {rules["max_value"]})'
        elif 'min_length' in rules and 'max_length' in rules:
            return f'String Length ({rules["min_length"]}-{rules["max_length"]} chars)'
        else:
            # Try to infer from sample values
            if all(val.replace('.', '').replace('-', '').isdigit() for val in sample_values if val):
                return 'Numeric'
            elif any(len(val) > 50 for val in sample_values if val):
                return 'Long Text'
            else:
                return 'Short Text'
    except Exception:
        # Fallback inference
        if all(val.replace('.', '').replace('-', '').isdigit() for val in sample_values if val):
            return 'Numeric'
        else:
            return 'Text'

def get_sample_values(series: pd.Series, count: int = 3) -> List[str]:
    """
    Get sample non-null values from a series.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return ['(all null)']
    
    # Remove empty strings and zeros
    str_values = non_null.astype(str).str.strip()
    meaningful_values = str_values[
        (str_values != '') & 
        (str_values != '0') & 
        (str_values != '0.0') & 
        (str_values != '0.00')
    ]
    
    if len(meaningful_values) == 0:
        return ['(all empty/zero)']
    
    # Get unique values
    unique_values = meaningful_values.unique()
    
    # Return up to 'count' samples
    samples = unique_values[:count].tolist()
    return samples

def analyze_parameter_changes(old_csv_path: str, new_csv_path: str, exclude_parameters: list = None) -> Dict[str, Any]:
    """
    Analyze parameter changes between old and new versions.
    """
    exclude_set = set(exclude_parameters) if exclude_parameters else set()
    
    print("Loading CSV files...")
    old_df = pd.read_csv(old_csv_path, low_memory=False)
    new_df = pd.read_csv(new_csv_path, low_memory=False)
    
    print(f"Old version: {len(old_df):,} rows x {len(old_df.columns)} columns")
    print(f"New version: {len(new_df):,} rows x {len(new_df.columns)} columns")
    
    if exclude_set:
        print(f"Excluding {len(exclude_set)} parameters from analysis")
    
    # Initialize analyzers
    old_analyzer = ParameterAnalyzer(old_csv_path)
    new_analyzer = ParameterAnalyzer(new_csv_path)
    
    results = {
        "analysis_date": datetime.now().isoformat(),
        "old_csv": old_csv_path,
        "new_csv": new_csv_path,
        "excluded_parameters": list(exclude_set),
        "new_parameters": [],
        "removed_parameters": []
    }
    
    print("\\nAnalyzing parameter changes...")
    
    # Find parameters that exist in both versions
    old_columns = set(old_df.columns) - exclude_set
    new_columns = set(new_df.columns) - exclude_set
    
    common_columns = old_columns & new_columns
    
    # Section 1: New Parameters
    # Parameters that exist in new but are effectively null in old
    print("\\nSection 1: Identifying new parameters...")
    
    for col in new_columns:
        if col in exclude_set:
            continue
            
        if col not in old_columns:
            # Completely new parameter
            print(f"  Found completely new parameter: {col}")
            sample_values = get_sample_values(new_df[col])
            validation_type = get_validation_type(new_analyzer, col, sample_values)
            
            results["new_parameters"].append({
                "parameter": col,
                "validation_type": validation_type,
                "example_values": sample_values,
                "reason": "Not present in old version"
            })
        
        elif col in common_columns:
            # Check if it was effectively null in old version
            if is_effectively_null(old_df[col]) and not is_effectively_null(new_df[col]):
                print(f"  Found parameter with new data: {col}")
                sample_values = get_sample_values(new_df[col])
                validation_type = get_validation_type(new_analyzer, col, sample_values)
                
                results["new_parameters"].append({
                    "parameter": col,
                    "validation_type": validation_type,
                    "example_values": sample_values,
                    "reason": "Was null/empty in old version, now has data"
                })
    
    # Section 2: Removed Parameters
    # Parameters that exist in old but are effectively null in new
    print("\\nSection 2: Identifying removed parameters...")
    
    for col in old_columns:
        if col in exclude_set:
            continue
            
        if col not in new_columns:
            # Completely removed parameter
            print(f"  Found completely removed parameter: {col}")
            sample_values = get_sample_values(old_df[col])
            validation_type = get_validation_type(old_analyzer, col, sample_values)
            
            results["removed_parameters"].append({
                "parameter": col,
                "validation_type": validation_type,
                "example_values": sample_values,
                "reason": "Not present in new version"
            })
        
        elif col in common_columns:
            # Check if it became effectively null in new version
            if not is_effectively_null(old_df[col]) and is_effectively_null(new_df[col]):
                print(f"  Found parameter with removed data: {col}")
                sample_values = get_sample_values(old_df[col])
                validation_type = get_validation_type(old_analyzer, col, sample_values)
                
                results["removed_parameters"].append({
                    "parameter": col,
                    "validation_type": validation_type,
                    "example_values": sample_values,
                    "reason": "Had data in old version, now null/empty"
                })
    
    print(f"\\nAnalysis complete:")
    print(f"- New parameters: {len(results['new_parameters'])}")
    print(f"- Removed parameters: {len(results['removed_parameters'])}")
    
    return results

def generate_report(results: Dict[str, Any], output_path: str):
    """
    Generate a formatted text report.
    """
    with open(output_path, 'w') as f:
        f.write("PARAMETER CHANGES REPORT\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Analysis Date: {results['analysis_date']}\n")
        f.write(f"Old Version: {results['old_csv']}\n")
        f.write(f"New Version: {results['new_csv']}\n")
        
        if results['excluded_parameters']:
            f.write(f"Excluded Parameters: {len(results['excluded_parameters'])}\n")
        
        f.write("\n")
        
        # Section 1: New Parameters
        f.write("SECTION 1 - NEW PARAMETERS\n")
        f.write("-" * 30 + "\n")
        f.write("Parameters which exist in the new version, but not exist (always null) in the old version\n\n")
        
        if not results['new_parameters']:
            f.write("No new parameters found.\n\n")
        else:
            for i, param in enumerate(results['new_parameters'], 1):
                f.write(f"{i}. Parameter: {param['parameter']}\n")
                f.write(f"   Validation Type: {param['validation_type']}\n")
                f.write(f"   Example Values: {', '.join(param['example_values'])}\n")
                f.write(f"   Reason: {param['reason']}\n\n")
        
        # Section 2: Removed Parameters
        f.write("SECTION 2 - REMOVED PARAMETERS\n")
        f.write("-" * 32 + "\n")
        f.write("Parameters which exist in the old version, but not exist (always null/empty/zero) in the new version\n\n")
        
        if not results['removed_parameters']:
            f.write("No removed parameters found.\n\n")
        else:
            for i, param in enumerate(results['removed_parameters'], 1):
                f.write(f"{i}. Parameter: {param['parameter']}\n")
                f.write(f"   Validation Type: {param['validation_type']}\n")
                f.write(f"   Example Values: {', '.join(param['example_values'])}\n")
                f.write(f"   Reason: {param['reason']}\n\n")
        
        f.write("=" * 50 + "\n")
        f.write("End of Report\n")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Generate parameter changes report between two CSV versions')
    parser.add_argument('--old-csv', default='data/game_data_old.csv', help='Path to old version CSV')
    parser.add_argument('--new-csv', default='data/game_data_new.csv', help='Path to new version CSV')
    parser.add_argument('--output-dir', default='logs', help='Output directory for results')
    parser.add_argument('--exclude-parameters', nargs='+', help='List of parameters to exclude from analysis')
    parser.add_argument('--config', help='Path to configuration JSON file')
    
    args = parser.parse_args()
    
    # Load exclusions from config if provided
    exclude_parameters = args.exclude_parameters or []
    if args.config and Path(args.config).exists():
        with open(args.config, 'r') as f:
            config = json.load(f)
            config_exclusions = config.get("validation", {}).get("exclude_parameters", [])
            exclude_parameters.extend(config_exclusions)
    
    # Remove duplicates
    exclude_parameters = list(set(exclude_parameters))
    
    # Check if files exist
    if not Path(args.old_csv).exists():
        print(f"Error: Old CSV file not found: {args.old_csv}")
        return 1
    
    if not Path(args.new_csv).exists():
        print(f"Error: New CSV file not found: {args.new_csv}")
        return 1
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Analyze parameter changes
    print("Starting parameter changes analysis...")
    results = analyze_parameter_changes(args.old_csv, args.new_csv, exclude_parameters=exclude_parameters)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_file = output_dir / f'parameter_changes_{timestamp}.json'
    report_file = output_dir / f'parameter_changes_report_{timestamp}.txt'
    
    # Save JSON
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate report
    generate_report(results, report_file)
    
    print(f"\\nResults saved:")
    print(f"- JSON data: {json_file}")
    print(f"- Text report: {report_file}")
    
    return 0

if __name__ == "__main__":
    exit(main())
