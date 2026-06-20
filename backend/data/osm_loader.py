"""
osm_loader.py — OpenStreetMap transport network extractor for Driftwatch.

Downloads metro stations, bus stops, railway stations, and road network
from the Overpass API within a city's bounding box, and builds a
NetworkX graph suitable for agent commute simulation.

Features:
    • Async HTTP via httpx with exponential backoff for rate-limiting
    • Local JSON cache in backend/data/cache/ for offline mode
    • Returns nx.Graph with typed nodes (station/stop) and weighted edges

Usage:
    loader = OSMLoader(config_loader)
    graph = await loader.load_transport_network("DEL")
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import networkx as nx

logger = logging.getLogger(__name__)

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"

# Maximum retry attempts for Overpass API
MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 2.0


# ─────────────────────────────────────────────────────────────
# Overpass query templates
# ─────────────────────────────────────────────────────────────

def _build_transport_query(bbox: list[float]) -> str:
    """Build an Overpass QL query for transport infrastructure.

    Parameters
    ----------
    bbox : list[float]
        [min_lng, min_lat, max_lng, max_lat] — note Overpass uses
        (south, west, north, east) = (min_lat, min_lng, max_lat, max_lng).
    """
    south, west, north, east = bbox[1], bbox[0], bbox[3], bbox[2]
    bb = f"{south},{west},{north},{east}"

    return f"""
[out:json][timeout:120];
(
  // Metro stations
  node["railway"="station"]["station"="subway"]({bb});
  node["railway"="station"]["railway:station"="metro"]({bb});
  node["station"="subway"]({bb});

  // Light rail / monorail stations
  node["railway"="station"]["station"="light_rail"]({bb});
  node["railway"="station"]["station"="monorail"]({bb});

  // Suburban / commuter rail stations
  node["railway"="station"]["station"!="subway"]({bb});
  node["railway"="halt"]({bb});

  // Major bus stops
  node["highway"="bus_stop"]({bb});
  node["amenity"="bus_station"]({bb});

  // Rail routes within bbox (for edges)
  relation["route"="subway"]({bb});
  relation["route"="light_rail"]({bb});
  relation["route"="train"]({bb});
);
out body;
>;
out skel qt;
"""


# ─────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────

@dataclass
class TransportNode:
    """A single transport stop or station."""
    osm_id: int
    name: str
    lat: float
    lng: float
    node_type: str  # 'metro_station' | 'bus_stop' | 'railway_station' | 'light_rail'
    tags: dict = field(default_factory=dict)


@dataclass
class TransportEdge:
    """A connection between two transport nodes."""
    source_id: int
    target_id: int
    distance_km: float
    mode: str  # 'metro' | 'suburban_rail' | 'bus' | 'road'
    route_name: str = ""


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km between two (lat, lng) points."""
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _classify_node(tags: dict[str, str]) -> str:
    """Determine the node type from OSM tags."""
    station = tags.get("station", "")
    railway = tags.get("railway", "")
    highway = tags.get("highway", "")
    amenity = tags.get("amenity", "")

    if station in ("subway",) or "metro" in tags.get("railway:station", ""):
        return "metro_station"
    if station in ("light_rail", "monorail"):
        return "light_rail"
    if railway in ("station", "halt"):
        return "railway_station"
    if highway == "bus_stop" or amenity == "bus_station":
        return "bus_stop"
    return "unknown"


# ─────────────────────────────────────────────────────────────
# OSMLoader
# ─────────────────────────────────────────────────────────────

class OSMLoader:
    """Loads transport network data from OpenStreetMap via Overpass API.

    Parameters
    ----------
    config_loader : ConfigLoader
        Instance of ConfigLoader to read city bbox from config.
    cache_dir : Path | str | None
        Directory for caching downloaded Overpass responses.
        Defaults to ``backend/data/cache/``.
    offline : bool
        If True, only serve from cache — never hit the network.
    """

    def __init__(
        self,
        config_loader: Any,
        cache_dir: Path | str | None = None,
        offline: bool = False,
    ) -> None:
        self._config_loader = config_loader
        self._offline = offline

        if cache_dir is None:
            self._cache_dir = Path(__file__).parent / "cache"
        else:
            self._cache_dir = Path(cache_dir)

        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Cache helpers ──────────────────────────────────────

    def _cache_path(self, city_id: str) -> Path:
        return self._cache_dir / f"osm_{city_id}.json"

    def _read_cache(self, city_id: str) -> dict | None:
        path = self._cache_path(city_id)
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            logger.info("Loaded OSM cache for %s (%s)", city_id, path)
            return data
        return None

    def _write_cache(self, city_id: str, data: dict) -> None:
        path = self._cache_path(city_id)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        logger.info("Wrote OSM cache for %s → %s", city_id, path)

    # ── Overpass API call with exponential backoff ─────────

    async def _query_overpass(self, query: str) -> dict:
        """Send a query to the Overpass API with retries and backoff."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    resp = await client.post(
                        OVERPASS_API_URL,
                        data={"data": query},
                    )

                    if resp.status_code == 200:
                        return resp.json()

                    if resp.status_code == 429:
                        wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                        logger.warning(
                            "Overpass rate-limited (429). Retrying in %.1fs (attempt %d/%d)",
                            wait, attempt, MAX_RETRIES,
                        )
                        await asyncio.sleep(wait)
                        continue

                    if resp.status_code >= 500:
                        wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                        logger.warning(
                            "Overpass server error %d. Retrying in %.1fs (attempt %d/%d)",
                            resp.status_code, wait, attempt, MAX_RETRIES,
                        )
                        await asyncio.sleep(wait)
                        continue

                    resp.raise_for_status()

            except httpx.TimeoutException:
                wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Overpass timeout. Retrying in %.1fs (attempt %d/%d)",
                    wait, attempt, MAX_RETRIES,
                )
                await asyncio.sleep(wait)

            except httpx.HTTPError as exc:
                logger.error("HTTP error querying Overpass: %s", exc)
                if attempt == MAX_RETRIES:
                    raise
                await asyncio.sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))

        raise RuntimeError(f"Overpass API failed after {MAX_RETRIES} retries")

    # ── Graph construction ─────────────────────────────────

    @staticmethod
    def _build_graph(overpass_data: dict) -> nx.Graph:
        """Parse Overpass JSON response into a NetworkX graph.

        Nodes: transport stops/stations with attributes.
        Edges: sequential connections along routes, or proximity links.
        """
        G = nx.Graph()
        elements = overpass_data.get("elements", [])

        # Separate nodes and relations
        node_map: dict[int, dict] = {}
        relations: list[dict] = []

        for elem in elements:
            if elem["type"] == "node" and "tags" in elem:
                tags = elem["tags"]
                ntype = _classify_node(tags)
                if ntype == "unknown":
                    continue

                node_map[elem["id"]] = {
                    "osm_id": elem["id"],
                    "name": tags.get("name", tags.get("name:en", f"node_{elem['id']}")),
                    "lat": elem["lat"],
                    "lng": elem["lon"],
                    "node_type": ntype,
                }
            elif elem["type"] == "relation":
                relations.append(elem)

        # Add nodes to graph
        for osm_id, attrs in node_map.items():
            G.add_node(
                osm_id,
                name=attrs["name"],
                lat=attrs["lat"],
                lng=attrs["lng"],
                node_type=attrs["node_type"],
            )

        # Build edges from route relations (sequential station connections)
        for rel in relations:
            tags = rel.get("tags", {})
            route_type = tags.get("route", "")
            mode = {
                "subway": "metro",
                "light_rail": "light_rail",
                "train": "suburban_rail",
            }.get(route_type, route_type)

            route_name = tags.get("name", "")

            # Extract ordered station members
            member_ids = [
                m["ref"] for m in rel.get("members", [])
                if m["type"] == "node" and m["ref"] in node_map
            ]

            # Connect sequential stations
            for i in range(len(member_ids) - 1):
                src, tgt = member_ids[i], member_ids[i + 1]
                src_data = node_map[src]
                tgt_data = node_map[tgt]
                dist = _haversine(
                    src_data["lat"], src_data["lng"],
                    tgt_data["lat"], tgt_data["lng"],
                )
                G.add_edge(
                    src, tgt,
                    distance_km=round(dist, 3),
                    mode=mode,
                    route_name=route_name,
                )

        logger.info(
            "Built transport graph: %d nodes, %d edges",
            G.number_of_nodes(), G.number_of_edges(),
        )
        return G

    # ── Public API ─────────────────────────────────────────

    async def load_transport_network(self, city_id: str) -> nx.Graph:
        """Load (or download) the transport network for a city.

        Parameters
        ----------
        city_id : str
            City identifier (e.g. ``"DEL"``, ``"MUM"``).

        Returns
        -------
        nx.Graph
            Transport network graph with typed nodes and edges.
        """
        # Check cache first
        cached = self._read_cache(city_id)
        if cached is not None:
            return self._build_graph(cached)

        if self._offline:
            raise FileNotFoundError(
                f"No cached OSM data for {city_id} and offline mode is enabled"
            )

        # Read bbox from city config
        city_path = self._config_loader._city_path(city_id)
        city_data = await self._config_loader._read_json(city_path)
        osm_extract = city_data.get("osm_extract", {})
        bbox = osm_extract.get("bbox")

        if not bbox or len(bbox) != 4:
            raise ValueError(
                f"City {city_id} config missing valid osm_extract.bbox "
                f"(expected [min_lng, min_lat, max_lng, max_lat])"
            )

        query = _build_transport_query(bbox)
        logger.info("Querying Overpass API for %s (bbox=%s)…", city_id, bbox)
        overpass_data = await self._query_overpass(query)

        # Cache the response
        self._write_cache(city_id, overpass_data)

        return self._build_graph(overpass_data)
