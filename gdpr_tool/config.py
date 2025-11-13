"""
Configuration management for GDPR automation tool.
"""

import yaml
import os
from typing import Dict, Any


class Config:
    """Configuration loader and manager."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration.

        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create it based on config.example.yaml"
            )

        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    @property
    def mixpanel(self) -> Dict[str, str]:
        """Get Mixpanel configuration."""
        return self.config.get('mixpanel', {})

    @property
    def singular(self) -> Dict[str, str]:
        """Get Singular configuration."""
        return self.config.get('singular', {})

    @property
    def bigquery(self) -> Dict[str, Any]:
        """Get BigQuery configuration."""
        return self.config.get('bigquery', {})

    @property
    def logging(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.config.get('logging', {})

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return self.config.get(key, default)
