# Driftwatch Data Ingestion Layer
"""
Data ingestion modules for the Driftwatch simulation platform.

Modules:
    config_loader   — Async config resolution with zone→city→state→defaults hierarchy
    osm_loader      — OpenStreetMap transport network extraction via Overpass API
    census_loader   — Ward-level demographic data from Census or zone configs
    ridership_loader — Transit ridership baselines from city transport configs
    config_validator — Standalone validation script for all zone configurations
"""

__all__ = ["ConfigLoader", "ZoneContext"]


def __getattr__(name: str):
    """Lazy imports to avoid requiring aiofiles/networkx/httpx at import time."""
    if name in ("ConfigLoader", "ZoneContext"):
        from backend.data.config_loader import ConfigLoader, ZoneContext
        globals()["ConfigLoader"] = ConfigLoader
        globals()["ZoneContext"] = ZoneContext
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
