"""
Parameter definitions and types for the analysis tool.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


class ParameterType(Enum):
    """Types of parameters that can be analyzed."""
    FIXED_SET = "fixed_set"
    CONSTRAINED_RANGE = "constrained_range"


@dataclass
class ParameterDefinition:
    """Base class for parameter definitions."""
    name: str
    description: str = ""
    validation_rules: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FixedSetParameter(ParameterDefinition):
    """Parameter that can only take values from a fixed set."""
    allowed_values: List[Any] = field(default_factory=list)


@dataclass
class ConstrainedRangeParameter(ParameterDefinition):
    """Parameter that must fall within certain constraints."""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    min_date: Optional[datetime] = None
    max_date: Optional[datetime] = None
    format: Optional[str] = None
    is_unique: bool = False 