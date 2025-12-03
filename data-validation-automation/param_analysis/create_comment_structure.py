import json
import pandas as pd

# Read the analysis file
with open('logs/parameter_analysis_game_data.json', 'r') as f:
    full_analysis = json.load(f)

analysis = full_analysis['parameters']  # Get the parameters section
total_rows = 27847  # From the unique_count of distinct_id which seems to be the total

# Calculate non-null counts for each parameter
param_stats = {}
for param, details in analysis.items():
    if not isinstance(details, dict) or 'validation_rules' not in details:
        continue
        
    null_count = details['validation_rules'].get('null_count', 0)
    if isinstance(null_count, (int, float)):
        non_null = total_rows - null_count
    else:
        non_null = 0
    param_stats[param] = {'non_null_count': non_null, 'details': details}

# Sort by non-null count
sorted_params = dict(sorted(param_stats.items(), key=lambda x: x[1]['non_null_count'], reverse=True))

# Create markdown output
with open('logs/parameter_analysis_comments.md', 'w') as f:
    f.write("# Parameter Analysis Comments\n\n")
    f.write("For each parameter below:\n")
    f.write("1. Is the type correct?\n")
    f.write("2. What additional constraints should be added?\n")
    f.write("3. Any special handling needed?\n\n")
    
    for param, stats in sorted_params.items():
        details = stats['details']
        rules = details.get('validation_rules', {})
        
        # Write parameter name as header
        f.write(f"## {param}\n\n")
        
        # Write current type
        param_type = details.get('type', 'unknown')
        f.write(f"**Current Type:** {param_type}\n\n")
        
        # Write current logic
        f.write("**Current Logic:**\n")
        
        # Add data type if available
        if 'data_type' in rules:
            f.write(f"- Data type: {rules['data_type']}\n")
        
        # Add non-null stats
        non_null_percent = 100 * (1 - rules.get('null_percentage', 0)/100)
        f.write(f"- Present in {non_null_percent:.1f}% of rows\n")
        
        # Add type-specific details
        if 'allowed_values' in rules:
            f.write(f"- Fixed set with {len(rules['allowed_values'])} possible values\n")
            if len(rules['allowed_values']) <= 10:
                f.write(f"- All values: {rules['allowed_values']}\n")
            elif 'sample_values' in rules:
                f.write(f"- Sample values: {rules['sample_values'][:3]}\n")
        elif 'min_value' in rules:
            f.write(f"- Numeric range: {rules.get('min_value')} to {rules.get('max_value')}\n")
            if 'mean_value' in rules:
                f.write(f"- Mean: {rules['mean_value']:.2f}\n")
        elif 'min_length' in rules:
            f.write(f"- String length: {rules.get('min_length')} to {rules.get('max_length')}\n")
            if 'pattern' in rules and rules['pattern']:
                f.write(f"- Detected pattern: {rules['pattern']}\n")
            if 'unique_count' in rules:
                f.write(f"- Unique values: {rules['unique_count']}\n")
        
        # Special handling for timestamps
        if rules.get('data_type') == 'timestamp':
            f.write(f"- Format: {rules.get('format', 'unknown')}\n")
            f.write(f"- Range: {rules.get('min_date', 'unknown')} to {rules.get('max_date', 'unknown')}\n")
        
        # Add comment template
        f.write("\n**Comments:**\n")
        f.write("```\n# Add your comments here:\n\n```\n\n")
        f.write("---\n\n") 