"""
census_loader.py — Ward-level demographic data loader for Driftwatch.

For MVP, demographic baselines are read from zone config ``demographics``
sections. When actual Census 2011 CSV files become available, the
``load_from_csv()`` method provides a drop-in upgrade path.

Usage:
    loader = CensusLoader(config_loader)
    demos = await loader.load_ward_demographics(["DEL_SHAHDARA", "DEL_SOUTH"])
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────

@dataclass
class WardDemographics:
    """Ward-level demographic profile for a zone.

    Fields mirror Census 2011 primary tables. For MVP, values
    are synthesised from zone config ``demographics`` section.
    """
    ward_id: str
    population: int = 0
    male: int = 0
    female: int = 0
    workers: int = 0
    main_workers: int = 0
    marginal_workers: int = 0
    non_workers: int = 0
    literates: int = 0
    sc_population: int = 0
    st_population: int = 0

    # Provenance
    data_source: str = "zone_config"
    confidence: str = "estimated"  # 'estimated' | 'census_actual'


# ─────────────────────────────────────────────────────────────
# CensusLoader
# ─────────────────────────────────────────────────────────────

class CensusLoader:
    """Loads ward-level demographics from zone configs or Census CSVs.

    Parameters
    ----------
    config_loader : ConfigLoader
        Instance used to read zone configuration files.
    """

    def __init__(self, config_loader: Any) -> None:
        self._config_loader = config_loader

    # ── Synthesise demographics from zone config ───────────

    @staticmethod
    def _synthesise_ward(zone_id: str, demographics: dict, income_profile: dict) -> WardDemographics:
        """Build a WardDemographics from zone config demographics section.

        Uses Census-style ratios to derive missing absolute values:
        - Male/female split: uses national urban average (52/48) if not explicit
        - Workers: derives from informal_employment_rate in income_profile
        - SC/ST: derives from sc_st_population_share in demographics
        """
        pop = demographics.get("population", 0)
        literacy_rate = demographics.get("literacy_rate", 0.75)
        sc_st_share = demographics.get("sc_st_population_share", 0.10)
        household_size = demographics.get("average_household_size", 4.2)
        informal_rate = income_profile.get("informal_employment_rate", 0.47)

        # Derive gendered population (national urban: ~52% male, ~48% female)
        male = int(pop * 0.52)
        female = pop - male

        # Derive worker categories
        # Assume ~40% of population are workers (Census 2011 urban average)
        worker_share = 0.40
        workers = int(pop * worker_share)
        # Main workers: those employed ≥6 months. Informal workers often marginal.
        main_workers = int(workers * (1.0 - informal_rate * 0.3))
        marginal_workers = workers - main_workers
        non_workers = pop - workers

        literates = int(pop * literacy_rate)
        sc_population = int(pop * sc_st_share * 0.75)  # ~75% of SC/ST share is SC
        st_population = int(pop * sc_st_share * 0.25)  # ~25% is ST

        return WardDemographics(
            ward_id=zone_id,
            population=pop,
            male=male,
            female=female,
            workers=workers,
            main_workers=main_workers,
            marginal_workers=marginal_workers,
            non_workers=non_workers,
            literates=literates,
            sc_population=sc_population,
            st_population=st_population,
            data_source=demographics.get("data_source", "zone_config"),
            confidence="estimated",
        )

    # ── Public API ─────────────────────────────────────────

    async def load_ward_demographics(
        self,
        zone_ids: list[str],
    ) -> dict[str, WardDemographics]:
        """Load ward demographics for a list of zones.

        For MVP, synthesises from zone config demographics. Returns
        a dict mapping zone_id → WardDemographics.

        Parameters
        ----------
        zone_ids : list[str]
            Zone identifiers, e.g. ``["DEL_SHAHDARA", "DEL_SOUTH"]``.
        """
        results: dict[str, WardDemographics] = {}

        for zone_id in zone_ids:
            try:
                ctx = await self._config_loader.load_zone_context(zone_id)
                ward = self._synthesise_ward(
                    zone_id,
                    ctx.demographics,
                    ctx.income_profile,
                )
                results[zone_id] = ward
                logger.info(
                    "Loaded demographics for %s (pop=%d, source=%s)",
                    zone_id, ward.population, ward.data_source,
                )
            except FileNotFoundError:
                logger.warning("Zone config not found for %s — skipping", zone_id)
            except Exception as exc:
                logger.error("Error loading demographics for %s: %s", zone_id, exc)

        return results

    # ── CSV loader (upgrade path) ──────────────────────────

    @staticmethod
    def load_from_csv(csv_path: str | Path) -> dict[str, WardDemographics]:
        """Load ward demographics from an actual Census 2011 CSV file.

        Expected CSV columns:
            ward_id, population, male, female, workers, main_workers,
            marginal_workers, non_workers, literates, sc_population,
            st_population

        Parameters
        ----------
        csv_path : str | Path
            Path to the Census CSV file.

        Returns
        -------
        dict[str, WardDemographics]
            Mapping ward_id → WardDemographics with ``confidence='census_actual'``.
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"Census CSV not found: {csv_path}")

        results: dict[str, WardDemographics] = {}

        with open(csv_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)

            for row in reader:
                ward_id = row["ward_id"].strip()
                ward = WardDemographics(
                    ward_id=ward_id,
                    population=int(row.get("population", 0)),
                    male=int(row.get("male", 0)),
                    female=int(row.get("female", 0)),
                    workers=int(row.get("workers", 0)),
                    main_workers=int(row.get("main_workers", 0)),
                    marginal_workers=int(row.get("marginal_workers", 0)),
                    non_workers=int(row.get("non_workers", 0)),
                    literates=int(row.get("literates", 0)),
                    sc_population=int(row.get("sc_population", 0)),
                    st_population=int(row.get("st_population", 0)),
                    data_source=f"Census 2011 CSV: {csv_path.name}",
                    confidence="census_actual",
                )
                results[ward_id] = ward

        logger.info("Loaded %d wards from CSV: %s", len(results), csv_path)
        return results
