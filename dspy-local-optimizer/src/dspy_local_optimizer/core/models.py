"""Core models for the DSPy local optimizer."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class GuidelineContent:
    """Content of a guideline.
    
    Attributes:
        condition: The customer's inquiry or situation
        response: The response to provide for this condition
    """
    condition: str
    response: str  # Changed from action to response to match usage


@dataclass
class Guideline:
    """A guideline for customer service responses.
    
    Attributes:
        id: Unique identifier for the guideline
        creation_utc: When the guideline was created
        content: The guideline's content (condition and response)
    """
    id: str
    creation_utc: datetime
    content: GuidelineContent
