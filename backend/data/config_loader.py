"""
config_loader.py — Async hierarchical configuration loader for Driftwatch.

Resolution order: zone → city → state → defaults.json
Every parameter tracks where it was resolved from in `resolved_from`.

Usage:
    loader = ConfigLoader(Path("backend/config"))
    ctx = await loader.load_zone_context("DEL_SHAHDARA")
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import aiofiles

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# ZoneContext — fully resolved configuration for one zone
# ─────────────────────────────────────────────────────────────
@dataclass
class ZoneContext:
    """Fully merged zone configuration with resolution tracking."""

    # ── Zone-level fields ──────────────────────────────────
    zone_id: str = ""
    zone_name: str = ""
    city_id: str = ""
    state_id: str = ""
    geography: dict = field(default_factory=dict)
    demographics: dict = field(default_factory=dict)
    income_profile: dict = field(default_factory=dict)
    commute_profile: dict = field(default_factory=dict)
    sensitivity_parameters: dict = field(default_factory=dict)
    social_network_parameters: dict = field(default_factory=dict)
    informal_economy_nodes: list = field(default_factory=list)
    tier1_agent_archetype_weights: dict = field(default_factory=dict)
    tier2_agent_types: dict = field(default_factory=dict)

    # ── City-level resolved fields ─────────────────────────
    transport_network: dict = field(default_factory=dict)
    osm_extract: dict = field(default_factory=dict)
    validation_anchors: list = field(default_factory=list)
    confidence_grade: str = ""
    population_city: int = 0
    topology_type: str = ""
    economic_baseline: dict = field(default_factory=dict)

    # ── State-level resolved fields ────────────────────────
    union_legal_framework: str = ""
    political_contestation_index: float = 0.0
    language_network_multiplier: float = 0.0
    language_primary: str = ""
    ruling_party_trust_index: float = 0.0
    state_gdp_per_capita: float = 0.0
    state_informal_economy_share: float = 0.0
    media_penetration: dict = field(default_factory=dict)

    # ── Resolution tracking ────────────────────────────────
    resolved_from: dict = field(default_factory=dict)
    # Maps parameter name → 'zone' | 'city' | 'state' | 'defaults'


# ─────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────
class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""


def _validate_weights_sum(
    weights: dict[str, float],
    label: str,
    tolerance: float = 0.001,
) -> list[str]:
    """Return list of warning strings if weights don't sum to ~1.0."""
    errors: list[str] = []
    if not weights:
        errors.append(f"{label}: empty weights dictionary")
        return errors
    numeric_values = {k: v for k, v in weights.items() if k != "data_source" and isinstance(v, (int, float))}
    if not numeric_values:
        errors.append(f"{label}: no numeric weights found")
        return errors
    total = sum(numeric_values.values())
    if abs(total - 1.0) > tolerance:
        errors.append(f"{label}: weights sum to {total:.6f}, expected 1.0 (±{tolerance})")
    return errors


_ZONE_REQUIRED_FIELDS = [
    "zone_id", "zone_name", "city_id", "state_id",
    "geography", "demographics", "income_profile", "commute_profile",
    "sensitivity_parameters", "social_network_parameters",
    "tier1_agent_archetype_weights", "tier2_agent_types",
]


# ─────────────────────────────────────────────────────────────
# Deep-merge utility
# ─────────────────────────────────────────────────────────────
def _deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
    *,
    base_level: str,
    override_level: str,
    resolved_from: dict[str, str],
    prefix: str = "",
) -> dict[str, Any]:
    """Recursively merge *override* into *base*, tracking resolution source.

    - Scalars / lists in *override* replace *base* values.
    - Dicts are merged recursively.
    - *resolved_from* is populated with ``key → level`` for every leaf.
    """
    merged: dict[str, Any] = {}

    all_keys = set(base) | set(override)
    for key in all_keys:
        fq_key = f"{prefix}.{key}" if prefix else key
        if key in override:
            val = override[key]
            if isinstance(val, dict) and isinstance(base.get(key), dict):
                merged[key] = _deep_merge(
                    base[key],
                    val,
                    base_level=base_level,
                    override_level=override_level,
                    resolved_from=resolved_from,
                    prefix=fq_key,
                )
            else:
                merged[key] = val
                resolved_from[fq_key] = override_level
        else:
            val = base[key]
            merged[key] = val
            if not isinstance(val, dict):
                resolved_from[fq_key] = base_level
            else:
                # Mark leaves inside base-only dicts
                _mark_leaves(val, base_level, resolved_from, fq_key)
    return merged


def _mark_leaves(
    d: dict[str, Any],
    level: str,
    resolved_from: dict[str, str],
    prefix: str,
) -> None:
    """Walk a dict tree and mark every leaf in *resolved_from*."""
    for key, val in d.items():
        fq_key = f"{prefix}.{key}"
        if isinstance(val, dict):
            _mark_leaves(val, level, resolved_from, fq_key)
        else:
            resolved_from[fq_key] = level


# ─────────────────────────────────────────────────────────────
# ConfigLoader
# ─────────────────────────────────────────────────────────────
class ConfigLoader:
    """Async configuration loader with zone→city→state→defaults hierarchy.

    Parameters
    ----------
    config_dir : Path | str
        Root of the config directory containing ``defaults.json``,
        ``states/``, ``cities/``, and ``zones/`` subdirectories.
    """

    def __init__(self, config_dir: Path | str) -> None:
        self.config_dir = Path(config_dir).resolve()
        self._defaults_path = self.config_dir / "defaults.json"
        self._states_dir = self.config_dir / "states"
        self._cities_dir = self.config_dir / "cities"
        self._zones_dir = self.config_dir / "zones"

        # In-memory cache: keyed by file path
        self._cache: dict[Path, dict] = {}

    # ── Async JSON reader ──────────────────────────────────
    async def _read_json(self, path: Path) -> dict[str, Any]:
        """Read and parse a JSON file, using an in-memory cache."""
        if path in self._cache:
            return self._cache[path]

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        async with aiofiles.open(path, mode="r", encoding="utf-8") as fh:
            raw = await fh.read()

        data = json.loads(raw)
        self._cache[path] = data
        return data

    # ── Config file locators ───────────────────────────────
    def _zone_path(self, zone_id: str) -> Path:
        """Derive file path for a zone config.

        Zone files live at zones/{city_id}/{zone_id}.json.
        The city_id is the prefix before the first underscore, e.g.
        DEL_SHAHDARA → zones/DEL/DEL_SHAHDARA.json.
        """
        city_id = zone_id.split("_", 1)[0]
        return self._zones_dir / city_id / f"{zone_id}.json"

    def _city_path(self, city_id: str) -> Path:
        return self._cities_dir / f"{city_id}.json"

    def _state_path(self, state_id: str) -> Path:
        return self._states_dir / f"{state_id}.json"

    # ── Core merge pipeline ────────────────────────────────
    async def load_zone_context(self, zone_id: str) -> ZoneContext:
        """Load and merge a single zone's configuration.

        Resolution order: zone → city → state → defaults.
        """
        resolved_from: dict[str, str] = {}

        # 1) Load defaults
        defaults = await self._read_json(self._defaults_path)

        # 2) Load zone
        zone_data = await self._read_json(self._zone_path(zone_id))

        # Validate required fields in zone
        missing = [f for f in _ZONE_REQUIRED_FIELDS if f not in zone_data]
        if missing:
            raise ConfigValidationError(
                f"Zone {zone_id} missing required fields: {', '.join(missing)}"
            )

        city_id = zone_data["city_id"]
        state_id = zone_data["state_id"]

        # 3) Load city config
        city_data: dict[str, Any] = {}
        city_path = self._city_path(city_id)
        if city_path.exists():
            city_data = await self._read_json(city_path)
        else:
            logger.warning("City config not found for %s — skipping city layer", city_id)

        # 4) Load state config
        state_data: dict[str, Any] = {}
        state_path = self._state_path(state_id)
        if state_path.exists():
            state_data = await self._read_json(state_path)
        else:
            logger.warning("State config not found for %s — skipping state layer", state_id)

        # 5) Build merged sensitivity_parameters with full resolution chain
        #    defaults → state → city → zone
        merged_sensitivity = _deep_merge(
            defaults,
            state_data.get("sensitivity_parameters", state_data),
            base_level="defaults",
            override_level="state",
            resolved_from=resolved_from,
            prefix="sensitivity_parameters",
        )
        # Rebuild from defaults for clean layering
        resolved_from_sp: dict[str, str] = {}
        layer_1 = _deep_merge(
            defaults, state_data,
            base_level="defaults", override_level="state",
            resolved_from=resolved_from_sp,
        )
        layer_2 = _deep_merge(
            layer_1, city_data,
            base_level="state", override_level="city",
            resolved_from=resolved_from_sp,
        )
        layer_3 = _deep_merge(
            layer_2, zone_data,
            base_level="city", override_level="zone",
            resolved_from=resolved_from_sp,
        )
        # Promote resolution tracking for sensitivity_parameters specifically
        for key, level in resolved_from_sp.items():
            if key.startswith("sensitivity_parameters."):
                resolved_from[key] = level
            elif key in defaults:
                # Top-level default keys that may appear in sensitivity
                resolved_from[f"sensitivity_parameters.{key}"] = level

        # 6) Validate archetype weights
        archetype_weights = zone_data.get("tier1_agent_archetype_weights", {})
        weight_errors = _validate_weights_sum(archetype_weights, f"Zone {zone_id} archetype weights")
        if weight_errors:
            raise ConfigValidationError("; ".join(weight_errors))

        # 7) Validate income decile distribution
        income_dist = zone_data.get("income_profile", {}).get("distribution", {})
        if income_dist:
            decile_errors = _validate_weights_sum(income_dist, f"Zone {zone_id} income deciles")
            if decile_errors:
                raise ConfigValidationError("; ".join(decile_errors))

        # 8) Build the ZoneContext
        # Resolve sensitivity_parameters through the full chain
        sp_defaults = defaults.copy()
        sp_state = {**sp_defaults, **{
            k: v for k, v in state_data.items()
            if k in sp_defaults  # only merge overlapping scalar keys
        }}
        sp_city = {**sp_state, **{
            k: v for k, v in city_data.items()
            if k in sp_state
        }}
        sp_zone_overrides = zone_data.get("sensitivity_parameters", {})

        # Final sensitivity_parameters: merge from defaults through zone
        final_sensitivity = dict(sp_city)
        # Apply zone-level sensitivity overrides
        for k, v in sp_zone_overrides.items():
            final_sensitivity[k] = v
            resolved_from[f"sensitivity_parameters.{k}"] = "zone"

        # Track sources for parameters that weren't zone-overridden
        for k in final_sensitivity:
            fq = f"sensitivity_parameters.{k}"
            if fq not in resolved_from:
                if k in sp_zone_overrides:
                    resolved_from[fq] = "zone"
                elif k in city_data:
                    resolved_from[fq] = "city"
                elif k in state_data:
                    resolved_from[fq] = "state"
                else:
                    resolved_from[fq] = "defaults"

        ctx = ZoneContext(
            # Zone-level
            zone_id=zone_data["zone_id"],
            zone_name=zone_data["zone_name"],
            city_id=city_id,
            state_id=state_id,
            geography=zone_data.get("geography", {}),
            demographics=zone_data.get("demographics", {}),
            income_profile=zone_data.get("income_profile", {}),
            commute_profile=zone_data.get("commute_profile", {}),
            sensitivity_parameters=zone_data.get("sensitivity_parameters", {}),
            social_network_parameters=zone_data.get("social_network_parameters", {}),
            informal_economy_nodes=zone_data.get("informal_economy_nodes", []),
            tier1_agent_archetype_weights=archetype_weights,
            tier2_agent_types=zone_data.get("tier2_agent_types", {}),

            # City-level
            transport_network=city_data.get("transport_network", {}),
            osm_extract=city_data.get("osm_extract", {}),
            validation_anchors=city_data.get("validation_anchors", []),
            confidence_grade=city_data.get("confidence_grade", "C"),
            population_city=city_data.get("population", 0),
            topology_type=city_data.get("topology_type", ""),
            economic_baseline=city_data.get("economic_baseline", {}),

            # State-level
            union_legal_framework=state_data.get("union_legal_framework", "moderate"),
            political_contestation_index=state_data.get("political_contestation_index", 0.5),
            language_network_multiplier=state_data.get("language_network_multiplier", 1.0),
            language_primary=state_data.get("language_primary", ""),
            ruling_party_trust_index=state_data.get("ruling_party_trust_index", 0.5),
            state_gdp_per_capita=state_data.get("state_gdp_per_capita", 0.0),
            state_informal_economy_share=state_data.get("state_informal_economy_share", 0.0),
            media_penetration=state_data.get("media_penetration", {}),

            # Resolution tracking
            resolved_from=resolved_from,
        )

        logger.info("Loaded ZoneContext for %s (city=%s, state=%s)", zone_id, city_id, state_id)
        return ctx

    # ── Zone listing ───────────────────────────────────────
    def list_zones(self, city_id: str | None = None) -> list[str]:
        """Scan zone directories and return zone IDs.

        Parameters
        ----------
        city_id : str, optional
            If provided, only return zones for that city.
        """
        zones: list[str] = []

        if city_id:
            city_dir = self._zones_dir / city_id
            if not city_dir.is_dir():
                logger.warning("No zone directory found for city %s", city_id)
                return zones
            dirs_to_scan = [city_dir]
        else:
            if not self._zones_dir.is_dir():
                return zones
            dirs_to_scan = [d for d in self._zones_dir.iterdir() if d.is_dir()]

        for city_dir in sorted(dirs_to_scan):
            for json_file in sorted(city_dir.glob("*.json")):
                zones.append(json_file.stem)

        return zones

    # ── Bulk city loader ───────────────────────────────────
    async def get_city_zones(self, city_id: str) -> list[ZoneContext]:
        """Load all zone contexts for a city concurrently.

        Reads zone IDs from the city config's ``zones`` array if available,
        otherwise falls back to scanning the zone directory.
        """
        # Try reading zone list from city config
        city_path = self._city_path(city_id)
        if city_path.exists():
            city_data = await self._read_json(city_path)
            zone_ids = city_data.get("zones", [])
        else:
            zone_ids = self.list_zones(city_id)

        if not zone_ids:
            zone_ids = self.list_zones(city_id)

        tasks = [self.load_zone_context(zid) for zid in zone_ids]
        return await asyncio.gather(*tasks)

    def clear_cache(self) -> None:
        """Flush the in-memory JSON cache."""
        self._cache.clear()
