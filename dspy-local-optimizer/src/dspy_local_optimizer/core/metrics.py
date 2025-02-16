"""Metrics tracking for model performance."""

from dataclasses import dataclass


@dataclass
class ModelMetrics:
    """Metrics for tracking model performance."""
    
    total_api_calls: int = 0
    total_tokens: int = 0
    total_time: float = 0.0
