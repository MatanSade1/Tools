#!/usr/bin/env python3
"""
Main orchestration script for the game data validation system.
This script provides a unified interface to run the entire validation workflow:
1. Data extraction from BigQuery
2. Version comparison and validation
3. Parameter analysis and reporting
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('validation_run.log')
    ]
)

# Suppress verbose Google Cloud library logs
logging.getLogger('google').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('google.cloud').setLevel(logging.WARNING)

class ValidationRunner:
    """Orchestrates the entire validation workflow."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self.load_config(config_path)
        self.setup_directories()
        
    def load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from file or use defaults."""
        default_config = {
            "bigquery": {
                "project_id": "yotam-395120",
                "dataset_id": "peerplay",
                "table_id": "vmp_master_event_normalized",
                "service_account_path": "yotam-395120-0c59ae7bb76e.json"
            },
            "validation": {
                "chunk_size": 10000,
                "output_dir": "data",
                "logs_dir": "logs",
                "exclude_parameters": [
                    "res_timestamp",
                    "time",
                    "timestamp_client",
                    "timestamp_source",
                    "mp_mp_api_timestamp_ms",
                    "mp_processing_time_ms",
                    "distinct_id",
                    "user_id",
                    "device_id",
                    "gaid",
                    "mp_distinct_id_before_identity",
                    "entity_id",
                    "exception_message",
                    "res_constraint",
                    "error_messages",
                    "updated_keys",
                    "realm_file_size",
                    "error_message",
                    "inner_exception_name",
                    "exception",
                    "files_count",
                    "race_request_board_level",
                    "race_request_board_cycle",
                    "failure_description_message"
                ]
            },
            "analysis": {
                "unique_ratio_threshold": 0.01,
                "generate_reports": True
            }
        }
        
        if config_path:
            try:
                with open(config_path) as f:
                    user_config = json.load(f)
                    # Deep merge user config with defaults
                    self.deep_merge(default_config, user_config)
            except Exception as e:
                logging.warning(f"Failed to load config from {config_path}: {e}")
                logging.info("Using default configuration")
        
        return default_config
    
    @staticmethod
    def deep_merge(dict1: dict, dict2: dict) -> dict:
        """Deep merge two dictionaries."""
        for key in dict2:
            if key in dict1 and isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                ValidationRunner.deep_merge(dict1[key], dict2[key])
            else:
                dict1[key] = dict2[key]
        return dict1
    
    def setup_directories(self):
        """Create necessary directories."""
        for dir_path in [
            self.config["validation"]["output_dir"],
            self.config["validation"]["logs_dir"]
        ]:
            Path(dir_path).mkdir(exist_ok=True)
    
    def extract_data(self, old_version: str, new_version: str, start_date: str, end_date: str, sample_size: int = None, preserve_purchase_events: bool = False) -> bool:
        """Run data extraction step."""
        try:
            from create_csv import extract_data_from_bigquery, split_and_save_versions
            
            logging.info(f"Starting data extraction for versions {old_version} and {new_version}")
            
            # Extract data
            df = extract_data_from_bigquery(old_version, new_version, start_date, end_date, sample_size, preserve_purchase_events)
            
            logging.info("Data extraction completed, starting split and save process...")
            logging.info(f"DataFrame info: {df.shape[0]:,} rows x {df.shape[1]} columns")
            
            # Split and save
            split_and_save_versions(df, old_version, new_version)
            
            logging.info("Split and save process completed successfully")
            
            return True
            
        except Exception as e:
            logging.error(f"Data extraction failed: {e}")
            return False
    
    def run_validation(self, exclude_parameters: list = None, include_parameters: list = None) -> bool:
        """Run validation comparison."""
        try:
            from compare_validate import ComparativeValidator
            
            old_csv = Path(self.config["validation"]["output_dir"]) / "game_data_old.csv"
            new_csv = Path(self.config["validation"]["output_dir"]) / "game_data_new.csv"
            
            if not old_csv.exists() or not new_csv.exists():
                logging.error("CSV files not found. Run data extraction first.")
                return False
            
            logging.info("Starting validation comparison")
            
            validator = ComparativeValidator(
                str(old_csv),
                str(new_csv),
                chunk_size=self.config["validation"]["chunk_size"],
                exclude_parameters=exclude_parameters,
                include_parameters=include_parameters
            )
            
            # Run validation
            validator.analyze_old_data()
            validator.validate_new_data()
            validator.save_validation_results()
            
            return True
            
        except Exception as e:
            logging.error(f"Validation failed: {e}")
            return False
    
    def run_analysis(self) -> bool:
        """Run parameter analysis."""
        try:
            from param_analysis.param_analyzer import ParameterAnalyzer
            
            logging.info("Starting parameter analysis")
            
            analyzer = ParameterAnalyzer(
                str(Path(self.config["validation"]["output_dir"]) / "game_data_new.csv")
            )
            
            analyzer.load_data()
            parameter_definitions = analyzer.analyze_parameters()
            
            # Save results (simplified version)
            output_file = Path(self.config["validation"]["logs_dir"]) / f"parameter_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            analysis_output = {
                "metadata": {
                    "total_parameters": len(parameter_definitions),
                    "analysis_date": datetime.now().timestamp(),
                    "csv_file": str(Path(self.config["validation"]["output_dir"]) / "game_data_new.csv")
                },
                "parameters": {
                    name: {
                        "type": param_def.__class__.__name__,
                        "description": param_def.description,
                        "validation_rules": param_def.validation_rules
                    }
                    for name, param_def in parameter_definitions.items()
                }
            }
            
            with open(output_file, 'w') as f:
                import json
                json.dump(analysis_output, f, indent=2)
            
            logging.info(f"Parameter analysis results saved to: {output_file}")
            
            return True
            
        except Exception as e:
            logging.error(f"Parameter analysis failed: {e}")
            return False
    
    def generate_parameter_changes_report(self, old_version: str = None, new_version: str = None, start_date: str = None, end_date: str = None, exclude_parameters: list = None) -> bool:
        """Generate parameter changes report comparing old and new versions."""
        try:
            logging.info("Starting parameter changes report generation")
            
            # Import the functions from our parameter changes script
            import pandas as pd
            from param_analysis.param_analyzer import ParameterAnalyzer
            
            old_csv = Path(self.config["validation"]["output_dir"]) / "game_data_old.csv"
            new_csv = Path(self.config["validation"]["output_dir"]) / "game_data_new.csv"
            
            if not old_csv.exists() or not new_csv.exists():
                logging.error("CSV files not found. Run data extraction first.")
                return False
            
            # Use the same analysis functions from generate_parameter_changes_report.py
            results = self._analyze_parameter_changes(str(old_csv), str(new_csv), old_version, new_version, start_date, end_date, exclude_parameters)
            
            # Generate output files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            logs_dir = Path(self.config["validation"]["logs_dir"])
            logs_dir.mkdir(exist_ok=True)
            
            json_file = logs_dir / f'parameter_changes_{timestamp}.json'
            report_file = logs_dir / f'parameter_changes_report_{timestamp}.txt'
            
            # Save JSON
            with open(json_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            # Generate text report
            self._generate_parameter_changes_text_report(results, str(report_file))
            
            logging.info(f"Parameter changes report generated:")
            logging.info(f"- JSON data: {json_file}")
            logging.info(f"- Text report: {report_file}")
            
            return True
            
        except Exception as e:
            logging.error(f"Parameter changes report generation failed: {e}")
            return False
    
    def _validate_parameter_in_bigquery(self, parameter: str, version: str, start_date: str, end_date: str) -> bool:
        """
        Validate if a parameter actually exists in the full BigQuery dataset.
        Returns True if parameter has non-null values, False if it's truly missing.
        """
        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account
            
            # Use same credentials as data extraction
            credentials = service_account.Credentials.from_service_account_file(
                'yotam-395120-0c59ae7bb76e.json', 
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            client = bigquery.Client(credentials=credentials, project='yotam-395120')
            
            # Try to convert version to float, if it fails, use it as string
            try:
                version_float = float(version)
                version_filter = f"version_float = {version_float}"
            except ValueError:
                # If version can't be converted to float, use string comparison
                version_filter = f"CAST(version_float AS STRING) = '{version}'"
            
            # Query to check if parameter has any non-null values
            query = f"""
            SELECT DISTINCT {parameter}
            FROM `yotam-395120.peerplay.vmp_master_event_normalized`
            WHERE date BETWEEN '{start_date}' AND '{end_date}'
              AND {version_filter}
              AND {parameter} IS NOT NULL
            LIMIT 1
            """
            
            logging.info(f"Validating parameter '{parameter}' in version {version}...")
            result = client.query(query).result()
            
            # If we get any result, parameter exists with data
            has_data = len(list(result)) > 0
            logging.info(f"Parameter '{parameter}' validation result: {'EXISTS' if has_data else 'MISSING'}")
            return has_data
            
        except Exception as e:
            logging.warning(f"BigQuery validation failed for parameter '{parameter}': {e}")
            # If validation fails, assume parameter change is real to be conservative
            return False
    
    def _analyze_parameter_changes(self, old_csv_path: str, new_csv_path: str, old_version: str, new_version: str, start_date: str, end_date: str, exclude_parameters: list = None) -> Dict[str, Any]:
        """Analyze parameter changes between old and new versions."""
        exclude_set = set(exclude_parameters) if exclude_parameters else set()
        
        logging.info("Loading CSV files for parameter changes analysis...")
        import pandas as pd
        old_df = pd.read_csv(old_csv_path, low_memory=False)
        new_df = pd.read_csv(new_csv_path, low_memory=False)
        
        logging.info(f"Old version: {len(old_df):,} rows x {len(old_df.columns)} columns")
        logging.info(f"New version: {len(new_df):,} rows x {len(new_df.columns)} columns")
        
        # Initialize analyzers
        from param_analysis.param_analyzer import ParameterAnalyzer
        old_analyzer = ParameterAnalyzer(old_csv_path)
        new_analyzer = ParameterAnalyzer(new_csv_path)
        
        results = {
            "analysis_date": datetime.now().isoformat(),
            "old_csv": old_csv_path,
            "new_csv": new_csv_path,
            "old_version": old_version,
            "new_version": new_version,
            "start_date": start_date,
            "end_date": end_date,
            "excluded_parameters": list(exclude_set),
            "new_parameters": [],
            "removed_parameters": []
        }
        
        # Find parameters that exist in both versions
        old_columns = set(old_df.columns) - exclude_set
        new_columns = set(new_df.columns) - exclude_set
        common_columns = old_columns & new_columns
        
        # Section 1: New Parameters
        logging.info("Identifying new parameters...")
        candidate_new_params = []
        
        for col in new_columns:
            if col in exclude_set:
                continue
                
            if col not in old_columns:
                # Completely new parameter - need to validate
                candidate_new_params.append((col, "Not present in old version"))
            
            elif col in common_columns:
                # Check if it was effectively null in old version
                if self._is_effectively_null(old_df[col]) and not self._is_effectively_null(new_df[col]):
                    candidate_new_params.append((col, "Was null/empty in old version, now has data"))
        
        # Validate candidate new parameters against BigQuery
        logging.info(f"Validating {len(candidate_new_params)} candidate new parameters against full dataset...")
        for col, reason in candidate_new_params:
            # Check if parameter actually exists in old version in full dataset
            if reason == "Not present in old version" or "null/empty in old version" in reason:
                # For new parameters, check if they truly don't exist in old version
                exists_in_old = self._validate_parameter_in_bigquery(col, old_version, start_date, end_date)
                
                if not exists_in_old:
                    # Parameter is truly new
                    sample_values = self._get_sample_values(new_df[col])
                    validation_type = self._get_validation_type(new_analyzer, col, sample_values)
                    
                    results["new_parameters"].append({
                        "parameter": col,
                        "validation_type": validation_type,
                        "example_values": sample_values,
                        "reason": reason,
                        "validated": True
                    })
                else:
                    logging.info(f"Parameter '{col}' exists in full old dataset - not truly new, skipping")
            else:
                # For other cases, add without validation for now
                sample_values = self._get_sample_values(new_df[col])
                validation_type = self._get_validation_type(new_analyzer, col, sample_values)
                
                results["new_parameters"].append({
                    "parameter": col,
                    "validation_type": validation_type,
                    "example_values": sample_values,
                    "reason": reason,
                    "validated": False
                })
        
        # Section 2: Removed Parameters
        logging.info("Identifying removed parameters...")
        candidate_removed_params = []
        
        for col in old_columns:
            if col in exclude_set:
                continue
                
            if col not in new_columns:
                # Completely removed parameter - need to validate
                candidate_removed_params.append((col, "Not present in new version"))
            
            elif col in common_columns:
                # Check if it became effectively null in new version
                if not self._is_effectively_null(old_df[col]) and self._is_effectively_null(new_df[col]):
                    candidate_removed_params.append((col, "Had data in old version, now null/empty"))
        
        # Validate candidate removed parameters against BigQuery
        logging.info(f"Validating {len(candidate_removed_params)} candidate removed parameters against full dataset...")
        for col, reason in candidate_removed_params:
            # Check if parameter actually exists in new version in full dataset
            if reason == "Not present in new version" or "now null/empty" in reason:
                # For removed parameters, check if they truly don't exist in new version
                exists_in_new = self._validate_parameter_in_bigquery(col, new_version, start_date, end_date)
                
                if not exists_in_new:
                    # Parameter is truly removed
                    sample_values = self._get_sample_values(old_df[col])
                    validation_type = self._get_validation_type(old_analyzer, col, sample_values)
                    
                    results["removed_parameters"].append({
                        "parameter": col,
                        "validation_type": validation_type,
                        "example_values": sample_values,
                        "reason": reason,
                        "validated": True
                    })
                else:
                    logging.info(f"Parameter '{col}' exists in full new dataset - not truly removed, skipping")
            else:
                # For other cases, add without validation for now
                sample_values = self._get_sample_values(old_df[col])
                validation_type = self._get_validation_type(old_analyzer, col, sample_values)
                
                results["removed_parameters"].append({
                    "parameter": col,
                    "validation_type": validation_type,
                    "example_values": sample_values,
                    "reason": reason,
                    "validated": False
                })
        
        logging.info(f"Parameter changes analysis complete: {len(results['new_parameters'])} new, {len(results['removed_parameters'])} removed")
        return results
    
    def _is_effectively_null(self, series) -> bool:
        """Check if a series is effectively null (all null, empty strings, or zeros)."""
        import pandas as pd
        
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
    
    def _get_sample_values(self, series, count: int = 3) -> List[str]:
        """Get sample non-null values from a series."""
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
    
    def _get_validation_type(self, analyzer, column: str, sample_values: List[str]) -> str:
        """Determine the validation type for a parameter."""
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
    
    def _generate_parameter_changes_text_report(self, results: Dict[str, Any], output_path: str):
        """Generate a formatted text report."""
        with open(output_path, 'w') as f:
            f.write("PARAMETER CHANGES REPORT\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Analysis Date: {results['analysis_date']}\n")
            f.write(f"Old Version: {results.get('old_version', 'N/A')}\n")
            f.write(f"New Version: {results.get('new_version', 'N/A')}\n")
            f.write(f"Date Range: {results.get('start_date', 'N/A')} to {results.get('end_date', 'N/A')}\n")
            f.write(f"Old CSV: {results['old_csv']}\n")
            f.write(f"New CSV: {results['new_csv']}\n")
            
            if results['excluded_parameters']:
                f.write(f"Excluded Parameters: {len(results['excluded_parameters'])}\n")
            
            f.write("\n")
            
            # Section 1: New Parameters
            f.write("SECTION 1 - NEW PARAMETERS\n")
            f.write("-" * 30 + "\n")
            f.write("Parameters which exist in the new version, but not exist (always null) in the old version\n")
            f.write("✅ = Validated against full BigQuery dataset\n\n")
            
            if not results['new_parameters']:
                f.write("No new parameters found.\n\n")
            else:
                for i, param in enumerate(results['new_parameters'], 1):
                    validation_status = "✅" if param.get('validated', False) else "⚠️"
                    f.write(f"{i}. Parameter: {param['parameter']} {validation_status}\n")
                    f.write(f"   Validation Type: {param['validation_type']}\n")
                    f.write(f"   Example Values: {', '.join(param['example_values'])}\n")
                    f.write(f"   Reason: {param['reason']}\n")
                    if param.get('validated', False):
                        f.write(f"   ✅ Confirmed: Parameter truly new (not found in full old dataset)\n")
                    else:
                        f.write(f"   ⚠️ Note: Not validated against full dataset\n")
                    f.write("\n")
            
            # Section 2: Removed Parameters
            f.write("SECTION 2 - REMOVED PARAMETERS\n")
            f.write("-" * 32 + "\n")
            f.write("Parameters which exist in the old version, but not exist (always null/empty/zero) in the new version\n")
            f.write("✅ = Validated against full BigQuery dataset\n\n")
            
            if not results['removed_parameters']:
                f.write("No removed parameters found.\n\n")
            else:
                for i, param in enumerate(results['removed_parameters'], 1):
                    validation_status = "✅" if param.get('validated', False) else "⚠️"
                    f.write(f"{i}. Parameter: {param['parameter']} {validation_status}\n")
                    f.write(f"   Validation Type: {param['validation_type']}\n")
                    f.write(f"   Example Values: {', '.join(param['example_values'])}\n")
                    f.write(f"   Reason: {param['reason']}\n")
                    if param.get('validated', False):
                        f.write(f"   ✅ Confirmed: Parameter truly removed (not found in full new dataset)\n")
                    else:
                        f.write(f"   ⚠️ Note: Not validated against full dataset\n")
                    f.write("\n")
            
            f.write("=" * 50 + "\n")
            f.write("End of Report\n")

def main():
    parser = argparse.ArgumentParser(
        description="Game Data Validation System - Main Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config',
        help='Path to configuration JSON file'
    )
    parser.add_argument(
        '--old-version',
        help='Old version number in format 0.x'
    )
    parser.add_argument(
        '--new-version',
        help='New version number in format 0.x'
    )
    parser.add_argument('--start-date', type=str, required=True, help='(Required) Start date for filtering events (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='(Required) End date for filtering events (YYYY-MM-DD)')
    parser.add_argument(
        '--skip-extraction',
        action='store_true',
        help='Skip data extraction step'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip validation comparison step'
    )
    parser.add_argument(
        '--skip-analysis',
        action='store_true',
        help='Skip parameter analysis step'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        help='Number of rows to sample per version (default: 10,000)'
    )
    parser.add_argument(
        '--exclude-parameters',
        nargs='+',
        help='List of parameters to exclude from validation (e.g., --exclude-parameters timestamp distinct_id)'
    )
    parser.add_argument(
        '--include-parameters',
        nargs='+',
        help='List of parameters to include in validation (only these will be validated, e.g., --include-parameters param1 param2)'
    )
    parser.add_argument(
        '--skip-parameter-changes',
        action='store_true',
        help='Skip parameter changes report generation'
    )
    parser.add_argument(
        '--preserve-purchase-events',
        action='store_true',
        help='Always include all purchase_successful events (may exceed sample size)'
    )
    
    args = parser.parse_args()
    
    # Create runner
    runner = ValidationRunner(args.config)
    
    # Track success of each step
    success = True
    
    # Run extraction if not skipped
    if not args.skip_extraction:
        if not (args.old_version and args.new_version):
            logging.error("Old and new versions required for data extraction")
            return 1
        success = runner.extract_data(args.old_version, args.new_version, args.start_date, args.end_date, args.sample_size, args.preserve_purchase_events)
        if not success:
            return 1
    
    # Run validation if not skipped
    if not args.skip_validation and success:
        # Combine command line and config exclusions
        config_exclusions = runner.config.get("validation", {}).get("exclude_parameters", [])
        cmd_exclusions = args.exclude_parameters or []
        all_exclusions = list(set(config_exclusions + cmd_exclusions))
        
        # Debug logging for exclusions
        logging.info(f"Validation exclusions - Config: {len(config_exclusions)}, Command line: {len(cmd_exclusions)}, Total: {len(all_exclusions)}")
        if all_exclusions:
            logging.info(f"Excluded parameters: {', '.join(sorted(all_exclusions))}")
        else:
            logging.info("No parameters will be excluded from validation")
        
        # Get include parameters if specified
        include_params = args.include_parameters if args.include_parameters else None
        if include_params:
            logging.info(f"Including only {len(include_params)} parameters: {', '.join(sorted(include_params))}")
        
        success = runner.run_validation(exclude_parameters=all_exclusions, include_parameters=include_params)
        if not success:
            return 1
    
    # Run analysis if not skipped
    if not args.skip_analysis and success:
        success = runner.run_analysis()
        if not success:
            return 1
    
    # Generate parameter changes report (automatically runs when we have both versions)
    if success and args.old_version and args.new_version and not args.skip_parameter_changes:
        # Use the same exclusions as validation
        config_exclusions = runner.config.get("validation", {}).get("exclude_parameters", [])
        cmd_exclusions = args.exclude_parameters or []
        all_exclusions = list(set(config_exclusions + cmd_exclusions))
        
        success = runner.generate_parameter_changes_report(args.old_version, args.new_version, args.start_date, args.end_date, exclude_parameters=all_exclusions)
        if not success:
            logging.warning("Parameter changes report generation failed, but continuing...")
            # Don't fail the entire pipeline for this
            success = True
    
    if success:
        logging.info("All requested steps completed successfully!")
        return 0
    else:
        logging.error("Some steps failed. Check the logs for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 