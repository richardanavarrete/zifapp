"""
HoundCOGS Business Logic Services

Pure functions with no framework dependencies.
All services are stateless and operate on data models.
"""

from houndcogs.services.inventory_parser import parse_inventory_file
from houndcogs.services.feature_engine import compute_features
from houndcogs.services.ordering_agent import run_agent
from houndcogs.services.policy_engine import apply_policies
from houndcogs.services.cogs_analyzer import analyze_cogs, calculate_variance
from houndcogs.services.fuzzy_matcher import FuzzyMatcher
from houndcogs.services.audio_processor import transcribe_audio

__all__ = [
    "parse_inventory_file",
    "compute_features",
    "run_agent",
    "apply_policies",
    "analyze_cogs",
    "calculate_variance",
    "FuzzyMatcher",
    "transcribe_audio",
]
