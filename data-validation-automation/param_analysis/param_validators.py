"""
Parameter validation logic for different parameter types.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .param_definitions import ParameterType


class BaseValidator(ABC):
    """Base class for parameter validators."""
    
    @abstractmethod
    def validate(self, value: Any) -> bool:
        """Validate a single value against the rules."""
        pass
    
    @abstractmethod
    def validate_batch(self, values: List[Any]) -> Dict[str, List[Any]]:
        """Validate a batch of values and return invalid ones."""
        pass


class FixedSetValidator(BaseValidator):
    """Validator for parameters with a fixed set of values."""
    pass


class ConstrainedRangeValidator(BaseValidator):
    """Validator for parameters with constrained ranges."""
    pass 