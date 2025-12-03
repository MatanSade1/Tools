"""
Script to run the parameter analyzer on CSV data.
"""

import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from param_analysis.param_analyzer import ParameterAnalyzer
from param_analysis.utils import setup_logging

def generate_markdown(analysis_output, output_file):
    """Generate a markdown file from the analysis output."""
    with open(output_file, 'w') as f:
        # Write header
        f.write("# Parameter Analysis Report\n\n")
        
        # Write metadata
        f.write("## Metadata\n\n")
        f.write(f"- **Total Parameters**: {analysis_output['metadata']['total_parameters']}\n")
        f.write(f"- **Analysis Date**: {datetime.fromtimestamp(analysis_output['metadata']['analysis_date']).strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **CSV File**: {analysis_output['metadata']['csv_file']}\n\n")
        
        # Write parameters
        f.write("## Parameters\n\n")
        for param_name, param_data in analysis_output['parameters'].items():
            f.write(f"### {param_name}\n\n")
            f.write(f"**Type**: {param_data['type']}\n\n")
            f.write(f"**Description**: {param_data['description'] or 'No description provided'}\n\n")
            
            f.write("**Validation Rules**:\n")
            if 'allowed_values' in param_data['validation_rules']:
                values = param_data['validation_rules']['allowed_values']
                if len(values) > 0:
                    f.write("- Allowed Values:\n")
                    # Show first 5 values and total count if more exist
                    for val in values[:5]:
                        f.write(f"  - {val}\n")
                    if len(values) > 5:
                        f.write(f"  - ... ({len(values)} total values)\n")
                else:
                    f.write("- No values found in dataset\n")
                
                # Add value distribution if available
                if 'value_distribution' in param_data['validation_rules']:
                    f.write("\nValue Distribution:\n")
                    dist = param_data['validation_rules']['value_distribution']
                    # Show top 5 most common values
                    sorted_dist = sorted(dist.items(), key=lambda x: x[1], reverse=True)[:5]
                    for val, count in sorted_dist:
                        f.write(f"- {val}: {count} occurrences\n")
            
            # Add sections for comments
            f.write("\n**Comments**:\n")
            f.write("<!-- Add your comments about this parameter here -->\n")
            f.write("- \n\n")
            
            f.write("**Suggested Changes**:\n")
            f.write("<!-- Add your suggested changes to the validation rules here -->\n")
            f.write("- \n\n")
            
            f.write("---\n\n")

def main():
    # Set up logging
    logger = setup_logging(
        log_file='parameter_analysis',
        log_level=logging.DEBUG
    )
    
    # Check command line arguments for CSV file
    if len(sys.argv) < 2:
        logger.error("Please provide the path to your CSV file as an argument")
        logger.info("Usage: python run_analyzer.py <path_to_csv>")
        sys.exit(1)
    
    # Get CSV path from command line
    csv_path = Path(sys.argv[1])
    
    # Validate CSV file exists
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)
    
    try:
        # Initialize and run the analyzer
        analyzer = ParameterAnalyzer(csv_path, log_level=logging.DEBUG)
        analyzer.load_data()
        parameter_definitions = analyzer.analyze_parameters()
        
        # Convert to a more readable/editable format
        analysis_output = {
            "metadata": {
                "total_parameters": len(parameter_definitions),
                "analysis_date": Path(csv_path).stat().st_mtime,
                "csv_file": str(csv_path)
            },
            "parameters": {}
        }
        
        for param_name, param_def in parameter_definitions.items():
            analysis_output["parameters"][param_name] = {
                "type": param_def.__class__.__name__,
                "description": param_def.description,
                "validation_rules": param_def.validation_rules,
                "comments": [],  # Add a place for comments
                "suggested_changes": []  # Add a place for suggested rule changes
            }
        
        # Save as JSON
        json_file = Path('logs') / f'parameter_analysis_{csv_path.stem}.json'
        with open(json_file, 'w') as f:
            json.dump(analysis_output, f, indent=2)
            
        # Save as Markdown
        md_file = Path('logs') / f'parameter_analysis_{csv_path.stem}.md'
        generate_markdown(analysis_output, md_file)
            
        logger.info(f"\nAnalysis saved to:")
        logger.info(f"- JSON: {json_file}")
        logger.info(f"- Markdown: {md_file}")
        logger.info("\nYou can edit the Markdown file to add comments and suggested changes to the validation rules")
            
    except Exception as e:
        logger.error(f"Error running analysis: {str(e)}")
        raise

if __name__ == "__main__":
    main() 