"""
config_validator.py — Standalone validation for all Driftwatch zone configs.

Validates every zone JSON file against the required schema, checks
archetype weight sums, income decile distributions, required fields,
and data_source citations. Reports pass/fail/warning per zone.

Run as a module:
    python -m backend.data.config_validator

Run directly:
    python backend/data/config_validator.py

Exit codes:
    0 — all zones pass validation
    1 — one or more zones failed
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# Required fields & schema definitions
# ─────────────────────────────────────────────────────────────

ZONE_REQUIRED_FIELDS = [
    "zone_id",
    "zone_name",
    "city_id",
    "state_id",
    "geography",
    "demographics",
    "income_profile",
    "commute_profile",
    "sensitivity_parameters",
    "social_network_parameters",
    "tier1_agent_archetype_weights",
    "tier2_agent_types",
]

GEOGRAPHY_REQUIRED = ["centroid_lat", "centroid_lng", "area_sq_km"]
DEMOGRAPHICS_REQUIRED = ["population", "population_density_per_sqkm"]
INCOME_REQUIRED = ["distribution", "median_monthly_income"]
COMMUTE_REQUIRED = ["primary_mode", "metro_dependency_score"]

SENSITIVITY_EXPECTED = [
    "fare_sensitivity_score",
    "examination_sensitivity_score",
    "collective_action_threshold",
    "information_diffusion_speed",
    "loss_aversion_coefficient",
    "institutional_trust_railways",
    "institutional_trust_examinations",
    "political_mobilisation_index",
]

SOCIAL_NETWORK_EXPECTED = [
    "avg_connections_tier1",
    "clustering_coefficient",
    "cross_income_bridge_frequency",
    "tier2_agent_density",
]

# Sections that should have a data_source field
SECTIONS_WITH_DATA_SOURCE = [
    "demographics",
    "income_profile",
    "commute_profile",
]

TOLERANCE = 0.001


# ─────────────────────────────────────────────────────────────
# Validation result
# ─────────────────────────────────────────────────────────────

@dataclass
class ZoneValidationResult:
    """Validation report for a single zone."""
    zone_id: str
    zone_file: Path
    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# Validators
# ─────────────────────────────────────────────────────────────

def _check_required(
    data: dict,
    required: list[str],
    section: str,
) -> tuple[list[str], list[str]]:
    """Check that required fields are present in a dict.

    Returns (errors, warnings).
    """
    errors: list[str] = []
    for f in required:
        if f not in data:
            errors.append(f"[{section}] missing required field: '{f}'")
    return errors, []


def _check_weights_sum(
    weights: dict,
    label: str,
    tolerance: float = TOLERANCE,
) -> tuple[list[str], list[str]]:
    """Check that weights sum to 1.0 within tolerance."""
    errors: list[str] = []
    if not weights:
        errors.append(f"[{label}] empty weights dictionary")
        return errors, []

    total = sum(float(v) for k, v in weights.items() if k != "data_source")
    if abs(total - 1.0) > tolerance:
        errors.append(
            f"[{label}] sum = {total:.6f}, expected 1.0 (±{tolerance})"
        )
    return errors, []


def _check_data_sources(
    data: dict,
    sections: list[str],
) -> tuple[list[str], list[str]]:
    """Warn if data_source citations are missing from key sections."""
    warnings: list[str] = []
    for section in sections:
        section_data = data.get(section, {})
        if isinstance(section_data, dict) and "data_source" not in section_data:
            warnings.append(f"[{section}] missing data_source citation")
    return [], warnings


def _check_numeric_range(
    value: float | int,
    field_name: str,
    min_val: float = 0.0,
    max_val: float = 1.0,
) -> tuple[list[str], list[str]]:
    """Check that a numeric value falls within expected range."""
    errors: list[str] = []
    try:
        v = float(value)
        if v < min_val or v > max_val:
            errors.append(
                f"[{field_name}] value {v} outside range [{min_val}, {max_val}]"
            )
    except (ValueError, TypeError):
        errors.append(f"[{field_name}] invalid numeric value: {value!r}")
    return errors, []


def _check_zone_id_consistency(data: dict, filepath: Path) -> tuple[list[str], list[str]]:
    """Check that zone_id matches filename and city_id prefix."""
    errors: list[str] = []
    zone_id = data.get("zone_id", "")
    city_id = data.get("city_id", "")
    expected_stem = filepath.stem

    if zone_id != expected_stem:
        errors.append(
            f"zone_id '{zone_id}' does not match filename '{expected_stem}.json'"
        )

    # zone_id should start with city_id
    if city_id and not zone_id.startswith(city_id + "_"):
        # Allow exact match for zones that are just the city prefix
        if zone_id != city_id:
            errors.append(
                f"zone_id '{zone_id}' does not start with city_id prefix '{city_id}_'"
            )

    return errors, []


def _check_malformed_fields(data: dict) -> tuple[list[str], list[str]]:
    """Check for obviously malformed field types."""
    errors: list[str] = []

    # geography should be dict
    geo = data.get("geography")
    if geo is not None and not isinstance(geo, dict):
        errors.append("[geography] expected dict, got " + type(geo).__name__)

    # demographics should be dict
    demo = data.get("demographics")
    if demo is not None and not isinstance(demo, dict):
        errors.append("[demographics] expected dict, got " + type(demo).__name__)

    # tier1_agent_archetype_weights should be dict of str→float
    weights = data.get("tier1_agent_archetype_weights")
    if weights is not None:
        if not isinstance(weights, dict):
            errors.append(
                "[tier1_agent_archetype_weights] expected dict, got "
                + type(weights).__name__
            )
        else:
            for k, v in weights.items():
                if k == "data_source":
                    continue
                if not isinstance(v, (int, float)):
                    errors.append(
                        f"[tier1_agent_archetype_weights.{k}] expected numeric, "
                        f"got {type(v).__name__}"
                    )

    # tier2_agent_types should be dict of str→int
    t2 = data.get("tier2_agent_types")
    if t2 is not None:
        if not isinstance(t2, dict):
            errors.append(
                "[tier2_agent_types] expected dict, got " + type(t2).__name__
            )
        else:
            for k, v in t2.items():
                if k == "data_source":
                    continue
                if not isinstance(v, (int, str)):
                    errors.append(
                        f"[tier2_agent_types.{k}] expected int, got {type(v).__name__}"
                    )

    # informal_economy_nodes should be list
    nodes = data.get("informal_economy_nodes")
    if nodes is not None and not isinstance(nodes, list):
        errors.append("[informal_economy_nodes] expected list, got " + type(nodes).__name__)

    return errors, []


# ─────────────────────────────────────────────────────────────
# Main validation
# ─────────────────────────────────────────────────────────────

def validate_zone(filepath: Path) -> ZoneValidationResult:
    """Run all validation checks on a single zone JSON file.

    Parameters
    ----------
    filepath : Path
        Absolute path to the zone JSON file.

    Returns
    -------
    ZoneValidationResult
    """
    result = ZoneValidationResult(zone_id=filepath.stem, zone_file=filepath)

    # Load JSON
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        result.passed = False
        result.errors.append(f"Invalid JSON: {exc}")
        return result
    except OSError as exc:
        result.passed = False
        result.errors.append(f"Cannot read file: {exc}")
        return result

    result.zone_id = data.get("zone_id", filepath.stem)

    # ── Required top-level fields ──────────────────────────
    errs, warns = _check_required(data, ZONE_REQUIRED_FIELDS, "root")
    result.errors.extend(errs)
    result.warnings.extend(warns)

    # ── Consistency checks ─────────────────────────────────
    errs, warns = _check_zone_id_consistency(data, filepath)
    result.errors.extend(errs)
    result.warnings.extend(warns)

    # ── Malformed fields ───────────────────────────────────
    errs, warns = _check_malformed_fields(data)
    result.errors.extend(errs)
    result.warnings.extend(warns)

    # ── Geography sub-fields ───────────────────────────────
    if "geography" in data and isinstance(data["geography"], dict):
        errs, warns = _check_required(data["geography"], GEOGRAPHY_REQUIRED, "geography")
        result.errors.extend(errs)
        result.warnings.extend(warns)

    # ── Demographics sub-fields ────────────────────────────
    if "demographics" in data and isinstance(data["demographics"], dict):
        errs, warns = _check_required(data["demographics"], DEMOGRAPHICS_REQUIRED, "demographics")
        result.errors.extend(errs)
        result.warnings.extend(warns)

    # ── Income profile sub-fields ──────────────────────────
    income = data.get("income_profile", {})
    if isinstance(income, dict):
        errs, warns = _check_required(income, INCOME_REQUIRED, "income_profile")
        result.errors.extend(errs)
        result.warnings.extend(warns)

        # Validate income decile distribution sums to 1.0
        distribution = income.get("distribution", {})
        if distribution:
            errs, warns = _check_weights_sum(distribution, "income_profile.distribution")
            result.errors.extend(errs)
            result.warnings.extend(warns)

    # ── Commute profile sub-fields ─────────────────────────
    commute = data.get("commute_profile", {})
    if isinstance(commute, dict):
        errs, warns = _check_required(commute, COMMUTE_REQUIRED, "commute_profile")
        result.errors.extend(errs)
        result.warnings.extend(warns)

    # ── Sensitivity parameters ─────────────────────────────
    sensitivity = data.get("sensitivity_parameters", {})
    if isinstance(sensitivity, dict):
        for sp_field in SENSITIVITY_EXPECTED:
            if sp_field not in sensitivity:
                result.warnings.append(
                    f"[sensitivity_parameters] missing expected field: '{sp_field}'"
                )
            else:
                errs, warns = _check_numeric_range(
                    sensitivity[sp_field], f"sensitivity_parameters.{sp_field}"
                )
                result.errors.extend(errs)
                result.warnings.extend(warns)

    # ── Social network parameters ──────────────────────────
    social = data.get("social_network_parameters", {})
    if isinstance(social, dict):
        for sn_field in SOCIAL_NETWORK_EXPECTED:
            if sn_field not in social:
                result.warnings.append(
                    f"[social_network_parameters] missing expected field: '{sn_field}'"
                )

    # ── Archetype weights ──────────────────────────────────
    archetype_weights = data.get("tier1_agent_archetype_weights", {})
    if isinstance(archetype_weights, dict):
        errs, warns = _check_weights_sum(
            archetype_weights, "tier1_agent_archetype_weights"
        )
        result.errors.extend(errs)
        result.warnings.extend(warns)

    # ── Data source citations ──────────────────────────────
    errs, warns = _check_data_sources(data, SECTIONS_WITH_DATA_SOURCE)
    result.errors.extend(errs)
    result.warnings.extend(warns)

    # ── Final pass/fail ────────────────────────────────────
    if result.errors:
        result.passed = False

    return result


def validate_all_zones(config_dir: Path) -> list[ZoneValidationResult]:
    """Validate all zone JSON files in the config directory.

    Parameters
    ----------
    config_dir : Path
        Root of the config directory (containing ``zones/`` subdirectory).

    Returns
    -------
    list[ZoneValidationResult]
        One result per zone file found.
    """
    zones_dir = config_dir / "zones"
    results: list[ZoneValidationResult] = []

    if not zones_dir.is_dir():
        print(f"⚠ No zones/ directory found at {zones_dir}")
        return results

    for city_dir in sorted(zones_dir.iterdir()):
        if not city_dir.is_dir():
            continue
        for zone_file in sorted(city_dir.glob("*.json")):
            result = validate_zone(zone_file)
            results.append(result)

    return results


def print_report(results: list[ZoneValidationResult]) -> bool:
    """Print a formatted validation report.

    Returns
    -------
    bool
        True if all zones passed, False if any failed.
    """
    if not results:
        print("═" * 60)
        print("  CONFIG VALIDATOR — No zone files found")
        print("═" * 60)
        print()
        print("  The zones/ directory is empty or missing.")
        print("  Zone configs must be created before validation can run.")
        print()
        print("  Expected structure:")
        print("    config/zones/{CITY_ID}/{ZONE_ID}.json")
        print()
        print("═" * 60)
        return True  # No files to fail

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    total_warnings = sum(len(r.warnings) for r in results)
    total_errors = sum(len(r.errors) for r in results)

    print()
    print("═" * 60)
    print("  DRIFTWATCH — CONFIG VALIDATOR REPORT")
    print("═" * 60)
    print()

    # Details for failed zones
    for r in results:
        if not r.passed:
            print(f"  ✗ FAIL  {r.zone_id}")
            print(f"    File: {r.zone_file}")
            for err in r.errors:
                print(f"    ❌ {err}")
            for warn in r.warnings:
                print(f"    ⚠  {warn}")
            print()

    # Details for passed zones with warnings
    for r in results:
        if r.passed and r.warnings:
            print(f"  ✓ PASS  {r.zone_id}  ({len(r.warnings)} warnings)")
            for warn in r.warnings:
                print(f"    ⚠  {warn}")
            print()

    # Passed zones without warnings (compact list)
    clean_passes = [r for r in results if r.passed and not r.warnings]
    if clean_passes:
        print("  Clean passes:")
        for r in clean_passes:
            print(f"    ✓ {r.zone_id}")
        print()

    # Summary
    print("─" * 60)
    print(f"  Total zones:  {total}")
    print(f"  Passed:       {passed}")
    print(f"  Failed:       {failed}")
    print(f"  Warnings:     {total_warnings}")
    print(f"  Errors:       {total_errors}")
    print("─" * 60)

    if failed == 0:
        print("  ✅ ALL ZONES PASSED VALIDATION")
    else:
        print(f"  ❌ {failed} ZONE(S) FAILED VALIDATION")

    print("═" * 60)
    print()

    return failed == 0


# ─────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────

def main() -> None:
    """Run validation as a standalone script or module."""
    # Determine config directory
    # Try relative to this file: backend/data/ → backend/config/
    this_dir = Path(__file__).resolve().parent
    default_config_dir = this_dir.parent / "config"

    # Allow override via command-line argument
    if len(sys.argv) > 1:
        config_dir = Path(sys.argv[1]).resolve()
    else:
        config_dir = default_config_dir

    if not config_dir.is_dir():
        print(f"Error: config directory not found: {config_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Validating zone configs in: {config_dir}")
    results = validate_all_zones(config_dir)
    all_passed = print_report(results)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
