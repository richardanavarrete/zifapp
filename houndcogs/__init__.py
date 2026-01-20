"""
HoundCOGS Core Package

Pure business logic for inventory management, order recommendations, and COGS analysis.
No framework dependencies (Streamlit, FastAPI) in this package.
"""

__version__ = "1.0.0"

from houndcogs.models.inventory import Item, WeeklyRecord, InventoryDataset
from houndcogs.models.orders import OrderTargets, OrderConstraints, Recommendation
from houndcogs.models.cogs import COGSSummary, PourCostResult
from houndcogs.models.voice import VoiceSession, VoiceCountRecord

__all__ = [
    "Item",
    "WeeklyRecord",
    "InventoryDataset",
    "OrderTargets",
    "OrderConstraints",
    "Recommendation",
    "COGSSummary",
    "PourCostResult",
    "VoiceSession",
    "VoiceCountRecord",
]
