"""
ridership_loader.py — Transit ridership baseline loader for Driftwatch.

Reads daily ridership data from city transport_network configs and
structures it for simulation calibration. Supports filtering by mode
(metro, suburban_rail, bus, all).

For MVP, data comes from city config ``transport_network`` sections.
Can be extended with actual DMRC/MMRDA/BMRCL CSV data files.

Usage:
    loader = RidershipLoader(config_loader)
    baseline = await loader.load_ridership("DEL", mode="metro")
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
class LineRidership:
    """Ridership data for a single transit line."""
    line_id: str
    name: str
    daily_ridership: int
    stations: int
    data_source: str = ""


@dataclass
class RidershipBaseline:
    """Aggregated ridership data for a city and mode."""
    city_id: str
    mode: str  # 'metro' | 'suburban_rail' | 'bus' | 'all'
    lines: list[LineRidership] = field(default_factory=list)
    total_daily: int = 0
    data_source: str = ""


# ─────────────────────────────────────────────────────────────
# RidershipLoader
# ─────────────────────────────────────────────────────────────

class RidershipLoader:
    """Loads transit ridership baselines from city config or CSV files.

    Parameters
    ----------
    config_loader : ConfigLoader
        Instance used to read city configuration files.
    """

    VALID_MODES = {"metro", "suburban_rail", "bus", "all"}

    def __init__(self, config_loader: Any) -> None:
        self._config_loader = config_loader

    # ── Extract metro lines from city config ───────────────

    @staticmethod
    def _extract_metro_lines(transport: dict) -> list[LineRidership]:
        """Parse metro_lines array from transport_network config."""
        lines: list[LineRidership] = []
        for ml in transport.get("metro_lines", []):
            lines.append(LineRidership(
                line_id=ml.get("line_id", ""),
                name=ml.get("name", ""),
                daily_ridership=ml.get("daily_ridership", 0),
                stations=ml.get("stations", 0),
                data_source=ml.get("data_source", ""),
            ))
        return lines

    # ── Extract suburban rail from city config ─────────────

    @staticmethod
    def _extract_suburban_rail(transport: dict) -> list[LineRidership]:
        """Parse suburban_rail section from transport_network config."""
        lines: list[LineRidership] = []
        suburban = transport.get("suburban_rail", {})

        if not suburban.get("present", False):
            return lines

        # Suburban rail may have a lines array or aggregate data
        for sl in suburban.get("lines", []):
            lines.append(LineRidership(
                line_id=sl.get("line_id", ""),
                name=sl.get("name", ""),
                daily_ridership=sl.get("daily_ridership", 0),
                stations=sl.get("stations", 0),
                data_source=sl.get("data_source", ""),
            ))

        # If no lines array but aggregate ridership exists
        if not lines and suburban.get("daily_ridership"):
            lines.append(LineRidership(
                line_id="suburban_aggregate",
                name=suburban.get("name", "Suburban Rail"),
                daily_ridership=suburban.get("daily_ridership", 0),
                stations=suburban.get("stations", 0),
                data_source=suburban.get("data_source", ""),
            ))

        return lines

    # ── Extract bus network from city config ───────────────

    @staticmethod
    def _extract_bus_network(transport: dict) -> list[LineRidership]:
        """Parse bus_network section from transport_network config."""
        lines: list[LineRidership] = []
        bus = transport.get("bus_network", {})

        if not bus:
            return lines

        # Bus network is typically aggregated, not per-line
        lines.append(LineRidership(
            line_id="bus_aggregate",
            name=bus.get("operator", "Bus Network"),
            daily_ridership=bus.get("daily_ridership", 0),
            stations=bus.get("route_count", 0),  # use route_count as proxy
            data_source=bus.get("data_source", ""),
        ))

        return lines

    # ── Public API ─────────────────────────────────────────

    async def load_ridership(
        self,
        city_id: str,
        mode: str = "all",
    ) -> RidershipBaseline:
        """Load ridership baseline for a city, optionally filtered by mode.

        Parameters
        ----------
        city_id : str
            City identifier (e.g. ``"DEL"``, ``"MUM"``).
        mode : str
            One of ``'metro'``, ``'suburban_rail'``, ``'bus'``, ``'all'``.

        Returns
        -------
        RidershipBaseline
            Aggregated ridership data.
        """
        if mode not in self.VALID_MODES:
            raise ValueError(
                f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(self.VALID_MODES))}"
            )

        # Load city config through the config loader
        city_path = self._config_loader._city_path(city_id)
        city_data = await self._config_loader._read_json(city_path)
        transport = city_data.get("transport_network", {})

        all_lines: list[LineRidership] = []
        sources: list[str] = []

        match mode:
            case "metro":
                all_lines = self._extract_metro_lines(transport)
            case "suburban_rail":
                all_lines = self._extract_suburban_rail(transport)
            case "bus":
                all_lines = self._extract_bus_network(transport)
            case "all":
                all_lines.extend(self._extract_metro_lines(transport))
                all_lines.extend(self._extract_suburban_rail(transport))
                all_lines.extend(self._extract_bus_network(transport))

        # Collect unique data sources
        for line in all_lines:
            if line.data_source and line.data_source not in sources:
                sources.append(line.data_source)

        total = sum(line.daily_ridership for line in all_lines)

        # If city config has aggregate total, prefer that for 'all' mode
        if mode == "all":
            config_total = transport.get("total_daily_pt_ridership", 0)
            if config_total > 0:
                total = config_total

        baseline = RidershipBaseline(
            city_id=city_id,
            mode=mode,
            lines=all_lines,
            total_daily=total,
            data_source="; ".join(sources) if sources else "city_config",
        )

        logger.info(
            "Loaded ridership for %s mode=%s: %d daily across %d lines",
            city_id, mode, baseline.total_daily, len(baseline.lines),
        )
        return baseline

    # ── CSV loader (upgrade path) ──────────────────────────

    @staticmethod
    def load_from_csv(
        csv_path: str | Path,
        city_id: str,
        mode: str = "metro",
    ) -> RidershipBaseline:
        """Load ridership from an actual transit authority CSV file.

        Expected CSV columns:
            line_id, name, daily_ridership, stations

        Parameters
        ----------
        csv_path : str | Path
            Path to the ridership CSV file.
        city_id : str
            City identifier.
        mode : str
            Transit mode this CSV represents.

        Returns
        -------
        RidershipBaseline
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"Ridership CSV not found: {csv_path}")

        lines: list[LineRidership] = []

        with open(csv_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                lines.append(LineRidership(
                    line_id=row.get("line_id", "").strip(),
                    name=row.get("name", "").strip(),
                    daily_ridership=int(row.get("daily_ridership", 0)),
                    stations=int(row.get("stations", 0)),
                    data_source=f"CSV: {csv_path.name}",
                ))

        total = sum(l.daily_ridership for l in lines)

        baseline = RidershipBaseline(
            city_id=city_id,
            mode=mode,
            lines=lines,
            total_daily=total,
            data_source=f"CSV: {csv_path.name}",
        )

        logger.info(
            "Loaded %d lines from CSV for %s (%s): %d daily",
            len(lines), city_id, mode, total,
        )
        return baseline
