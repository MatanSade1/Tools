#!/usr/bin/env python3
"""
Script to identify new parameters and new values in the new version compared to the old version.
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, List, Any

def analyze_version_differences(old_csv_path: str, new_csv_path: str, exclude_parameters: list = None) -> Dict[str, Any]:
    """
    Analyze differences between old and new versions.
    
    Args:
        old_csv_path: Path to old version CSV
        new_csv_path: Path to new version CSV  
        exclude_parameters: List of parameters to exclude from analysis
    
    Returns:
        Dictionary containing new parameters, new values, and statistics
    """
    exclude_set = set(exclude_parameters) if exclude_parameters else set()
    print("Loading CSV files...")
    old_df = pd.read_csv(old_csv_path, low_memory=False)
    new_df = pd.read_csv(new_csv_path, low_memory=False)
    
    print(f"Old version: {len(old_df):,} rows x {len(old_df.columns)} columns")
    print(f"New version: {len(new_df):,} rows x {len(new_df.columns)} columns")
    
    results = {
        "analysis_date": datetime.now().isoformat(),
        "old_version_stats": {
            "rows": len(old_df),
            "columns": len(old_df.columns)
        },
        "new_version_stats": {
            "rows": len(new_df),
            "columns": len(new_df.columns)
        },
        "new_parameters": [],
        "missing_parameters": [],
        "parameters_with_new_values": {},
        "summary": {}
    }
    
    # Find new parameters (columns that exist in new but not in old)
    old_columns = set(old_df.columns) - exclude_set
    new_columns = set(new_df.columns) - exclude_set
    
    new_parameters = new_columns - old_columns
    missing_parameters = old_columns - new_columns
    common_parameters = old_columns & new_columns
    
    if exclude_set:
        print(f"Excluding {len(exclude_set)} parameters from analysis: {', '.join(sorted(exclude_set))}")
    
    results["new_parameters"] = sorted(list(new_parameters))
    results["missing_parameters"] = sorted(list(missing_parameters))
    
    print(f"\nParameter Analysis:")
    print(f"- New parameters: {len(new_parameters)}")
    print(f"- Missing parameters: {len(missing_parameters)}")
    print(f"- Common parameters: {len(common_parameters)}")
    
    if new_parameters:
        print("\nNew parameters found:")
        for param in sorted(new_parameters):
            print(f"  - {param}")
            # Get sample values from the new parameter
            sample_values = new_df[param].dropna().unique()[:10]  # First 10 unique values
            results["parameters_with_new_values"][param] = {
                "type": "new_parameter",
                "sample_values": [str(v) for v in sample_values],
                "unique_count": len(new_df[param].dropna().unique()),
                "null_count": new_df[param].isnull().sum()
            }
    
    if missing_parameters:
        print("\nMissing parameters (exist in old but not in new):")
        for param in sorted(missing_parameters):
            print(f"  - {param}")
    
    # Analyze common parameters for new values
    print(f"\nAnalyzing {len(common_parameters)} common parameters for new values...")
    parameters_with_new_values = 0
    
    for param in common_parameters:
        if param in ['res_timestamp', 'time', 'timestamp_client', 'timestamp_source']:
            # Skip timestamp fields as they're always unique
            continue
            
        try:
            # Get unique values from both versions (as strings for comparison)
            old_values = set(old_df[param].dropna().astype(str))
            new_values = set(new_df[param].dropna().astype(str))
            
            # Find values that exist in new but not in old
            truly_new_values = new_values - old_values
            
            if truly_new_values:
                parameters_with_new_values += 1
                # Limit to first 20 new values to avoid huge outputs
                sample_new_values = sorted(list(truly_new_values))[:20]
                
                results["parameters_with_new_values"][param] = {
                    "type": "existing_parameter_new_values",
                    "new_values": sample_new_values,
                    "new_values_count": len(truly_new_values),
                    "old_unique_count": len(old_values),
                    "new_unique_count": len(new_values)
                }
                
                print(f"  {param}: {len(truly_new_values)} new values")
                if len(truly_new_values) <= 5:
                    print(f"    New values: {sample_new_values}")
                else:
                    print(f"    Sample new values: {sample_new_values[:5]}... (+{len(truly_new_values)-5} more)")
                    
        except Exception as e:
            print(f"  Error analyzing {param}: {e}")
            continue
    
    # Summary
    results["summary"] = {
        "total_new_parameters": len(new_parameters),
        "total_missing_parameters": len(missing_parameters),
        "parameters_with_new_values": parameters_with_new_values,
        "total_parameters_analyzed": len(common_parameters)
    }
    
    print(f"\nSummary:")
    print(f"- {len(new_parameters)} completely new parameters")
    print(f"- {len(missing_parameters)} missing parameters")  
    print(f"- {parameters_with_new_values} existing parameters with new values")
    
    return results

def save_results(results: Dict[str, Any], output_file: str):
    """Save analysis results to JSON file."""
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_file}")

def generate_markdown_report(results: Dict[str, Any], output_file: str):
    """Generate a markdown report of the differences."""
    with open(output_file, 'w') as f:
        f.write("# Version Differences Analysis Report\n\n")
        f.write(f"**Analysis Date:** {results['analysis_date']}\n\n")
        
        # Summary
        f.write("## Summary\n\n")
        summary = results['summary']
        f.write(f"- **New Parameters:** {summary['total_new_parameters']}\n")
        f.write(f"- **Missing Parameters:** {summary['total_missing_parameters']}\n")
        f.write(f"- **Parameters with New Values:** {summary['parameters_with_new_values']}\n")
        f.write(f"- **Total Parameters Analyzed:** {summary['total_parameters_analyzed']}\n\n")
        
        # New parameters
        if results['new_parameters']:
            f.write("## New Parameters\n\n")
            f.write("These parameters exist in the new version but not in the old version:\n\n")
            for param in results['new_parameters']:
                f.write(f"### `{param}`\n\n")
                if param in results['parameters_with_new_values']:
                    info = results['parameters_with_new_values'][param]
                    f.write(f"- **Unique Values:** {info['unique_count']}\n")
                    f.write(f"- **Null Values:** {info['null_count']}\n")
                    f.write(f"- **Sample Values:** {', '.join(info['sample_values'][:5])}\n\n")
        
        # Parameters with new values
        existing_params_with_new_values = {
            k: v for k, v in results['parameters_with_new_values'].items() 
            if v['type'] == 'existing_parameter_new_values'
        }
        
        if existing_params_with_new_values:
            f.write("## Existing Parameters with New Values\n\n")
            f.write("These parameters existed in both versions but have new values in the new version:\n\n")
            
            for param, info in existing_params_with_new_values.items():
                f.write(f"### `{param}`\n\n")
                f.write(f"- **New Values Count:** {info['new_values_count']}\n")
                f.write(f"- **Old Version Unique Values:** {info['old_unique_count']}\n")
                f.write(f"- **New Version Unique Values:** {info['new_unique_count']}\n")
                f.write("- **Sample New Values:**\n")
                for value in info['new_values'][:10]:  # Show first 10
                    f.write(f"  - `{value}`\n")
                if info['new_values_count'] > 10:
                    f.write(f"  - ... and {info['new_values_count'] - 10} more\n")
                f.write("\n")
        
        # Missing parameters
        if results['missing_parameters']:
            f.write("## Missing Parameters\n\n")
            f.write("These parameters existed in the old version but not in the new version:\n\n")
            for param in results['missing_parameters']:
                f.write(f"- `{param}`\n")
            f.write("\n")
    
    print(f"Markdown report saved to: {output_file}")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze differences between two CSV versions')
    parser.add_argument('--old-csv', default='data/game_data_old.csv', help='Path to old version CSV')
    parser.add_argument('--new-csv', default='data/game_data_new.csv', help='Path to new version CSV')
    parser.add_argument('--output-dir', default='logs', help='Output directory for results')
    parser.add_argument('--exclude-parameters', nargs='+', help='List of parameters to exclude from analysis')
    
    args = parser.parse_args()
    
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
    
    # Analyze differences
    print("Starting version differences analysis...")
    results = analyze_version_differences(args.old_csv, args.new_csv, exclude_parameters=args.exclude_parameters)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_file = output_dir / f'version_differences_{timestamp}.json'
    markdown_file = output_dir / f'version_differences_{timestamp}.md'
    
    save_results(results, str(json_file))
    generate_markdown_report(results, str(markdown_file))
    
    print(f"\n✅ Analysis complete!")
    print(f"📊 JSON results: {json_file}")
    print(f"📝 Markdown report: {markdown_file}")
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
