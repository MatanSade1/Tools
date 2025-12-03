"""
Utility functions for parameter analysis.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

def setup_logging(log_file: str = None, log_level: int = logging.INFO) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        log_file: Optional name for log file (without extension)
        log_level: Logging level to use
        
    Returns:
        Logger instance
    """
    # Create logs directory if needed
    if log_file:
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Add timestamp to log filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = log_dir / f"{log_file}_{timestamp}.log"
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),  # Console handler
            logging.FileHandler(log_path) if log_file else logging.NullHandler()
        ]
    )
    
    return logging.getLogger('param_analysis')

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Name for the logger
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f'param_analysis.{name}')

# Create a default logger instance
logger = setup_logging('param_analysis') 