"""
policy_parser.py — Natural language → structured PolicyParams.

Uses OpenAI GPT-4o-mini when API key is available, with a comprehensive
rule-based fallback for offline use and testing.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Valid archetype names (must match tier1_agent.py)
VALID_ARCHETYPES = [
    "daily_wage_worker", "formal_sector_employee", "government_employee",
    "tech_knowledge_worker", "small_business_owner", "student", "homemaker",
    "street_vendor", "retired", "migrant_worker", "healthcare_worker",
    "exam_aspirant", "gig_economy_worker", "journalist_tier1",
]

VALID_MODES = ["metro", "bus", "suburban_rail", "auto", "cab", "bicycle", "walking"]

VALID_POLICY_TYPES = [
    "fare_change", "frequency_change", "concession_change",
    "new_service", "route_modification", "parking_policy",
]


class ParseError(Exception):
    """Raised when policy parsing fails validation."""

    def __init__(self, explanation: str) -> None:
        self.explanation = explanation
        super().__init__(explanation)


@dataclass
class PolicyParams:
    """Structured policy parameters extracted from natural language."""

    policy_type: str = "fare_change"
    affected_routes: list[str] = field(default_factory=list)
    affected_modes: list[str] = field(default_factory=list)
    magnitude: float = 0.0  # percentage change (can be negative)
    timeline_days: int = 30
    affected_population_segments: list[str] = field(default_factory=list)
    geographic_scope: list[str] = field(default_factory=list)
    raw_input: str = ""


class PolicyParser:
    """Parse natural language policy descriptions into structured params.

    Parameters
    ----------
    openai_api_key : str, optional
        OpenAI API key. If None, checks ``OPENAI_API_KEY`` env var.
        Falls back to rule-based parsing when no key is available.
    """

    def __init__(self, openai_api_key: str | None = None) -> None:
        self._api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None

        if self._api_key:
            try:
                import openai
                self._client = openai.AsyncOpenAI(api_key=self._api_key)
            except ImportError:
                logger.warning("openai package not installed — using rule-based parser")

    async def parse(
        self,
        natural_language_input: str,
        zone_context: Any = None,
    ) -> PolicyParams:
        """Parse a natural language policy statement.

        Parameters
        ----------
        natural_language_input : str
            Plain English policy statement.
        zone_context : ZoneContext, optional
            City/zone context for validation.

        Returns
        -------
        PolicyParams
        """
        text = natural_language_input.strip()

        if self._client:
            try:
                return await self._api_parse(text, zone_context)
            except Exception as e:
                logger.warning("OpenAI parse failed (%s), falling back to rule-based", e)

        # Rule-based fallback
        parsed = self._rule_based_parse(text)
        params = PolicyParams(
            policy_type=parsed.get("policy_type", "fare_change"),
            affected_routes=parsed.get("affected_routes", []),
            affected_modes=parsed.get("affected_modes", []),
            magnitude=parsed.get("magnitude", 0.0),
            timeline_days=parsed.get("timeline_days", 30),
            affected_population_segments=parsed.get("affected_population_segments", []),
            geographic_scope=parsed.get("geographic_scope", []),
            raw_input=text,
        )
        return params

    async def _api_parse(
        self,
        text: str,
        zone_context: Any,
    ) -> PolicyParams:
        """Parse using GPT-4o-mini."""
        import json

        system_prompt = (
            "Extract structured policy parameters from the user's input. "
            "Return JSON with these fields:\n"
            "- policy_type: one of fare_change, frequency_change, concession_change, "
            "new_service, route_modification, parking_policy\n"
            "- affected_routes: list of route names/numbers\n"
            "- affected_modes: list from [metro, bus, suburban_rail, auto, cab]\n"
            "- magnitude: percentage change as a number (e.g. 20 for 20% increase, "
            "-10 for 10% decrease, 100 for doubling)\n"
            "- timeline_days: duration in days (default 30)\n"
            "- affected_population_segments: list of affected groups\n"
            "- geographic_scope: list of zone/area names\n"
            "Return only valid JSON, no markdown."
        )

        response = await self._client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )

        data = json.loads(response.choices[0].message.content)
        return PolicyParams(
            policy_type=data.get("policy_type", "fare_change"),
            affected_routes=data.get("affected_routes", []),
            affected_modes=data.get("affected_modes", []),
            magnitude=float(data.get("magnitude", 0.0)),
            timeline_days=int(data.get("timeline_days", 30)),
            affected_population_segments=data.get("affected_population_segments", []),
            geographic_scope=data.get("geographic_scope", []),
            raw_input=text,
        )

    def _rule_based_parse(self, text: str) -> dict[str, Any]:
        """Regex + keyword-based extraction fallback."""
        text_lower = text.lower()
        result: dict[str, Any] = {
            "affected_routes": [],
            "affected_modes": [],
            "affected_population_segments": [],
            "geographic_scope": [],
        }

        # ── Policy type detection ──
        if any(w in text_lower for w in ["fare", "price", "tariff", "cost", "charge"]):
            if any(w in text_lower for w in ["parking", "park"]):
                result["policy_type"] = "parking_policy"
            else:
                result["policy_type"] = "fare_change"
        elif any(w in text_lower for w in ["frequency", "headway", "schedule"]):
            result["policy_type"] = "frequency_change"
        elif any(w in text_lower for w in ["concession", "discount", "free", "subsidy", "exemption"]):
            result["policy_type"] = "concession_change"
        elif any(w in text_lower for w in ["new", "introduce", "launch", "start"]):
            result["policy_type"] = "new_service"
        elif any(w in text_lower for w in ["route", "reroute", "divert"]):
            result["policy_type"] = "route_modification"
        elif any(w in text_lower for w in ["parking", "park"]):
            result["policy_type"] = "parking_policy"
        else:
            result["policy_type"] = "fare_change"

        # ── Magnitude extraction ──
        # Look for patterns like "20%", "by 20 percent", "double", "halve"
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|pct)", text_lower)
        if pct_match:
            magnitude = float(pct_match.group(1))
            if any(w in text_lower for w in ["decrease", "reduce", "cut", "lower", "drop"]):
                magnitude = -magnitude
            result["magnitude"] = magnitude
        elif "double" in text_lower or "doubled" in text_lower:
            result["magnitude"] = 100.0
        elif "triple" in text_lower:
            result["magnitude"] = 200.0
        elif "halve" in text_lower or "half" in text_lower:
            result["magnitude"] = -50.0
        elif any(w in text_lower for w in ["free", "no cost", "zero fare"]):
            result["magnitude"] = -100.0
        else:
            result["magnitude"] = 0.0

        # ── Mode detection ──
        mode_keywords = {
            "metro": ["metro", "dmrc", "subway", "underground"],
            "bus": ["bus", "dtc", "best", "mts"],
            "suburban_rail": ["suburban", "local train", "rail", "railway", "mumba"],
            "auto": ["auto", "autorickshaw", "three-wheeler"],
            "cab": ["cab", "taxi", "ola", "uber"],
        }
        for mode, keywords in mode_keywords.items():
            if any(kw in text_lower for kw in keywords):
                result["affected_modes"].append(mode)

        if not result["affected_modes"]:
            # Default to all public transit
            result["affected_modes"] = ["metro", "bus"]

        # ── Timeline extraction ──
        timeline_match = re.search(r"(\d+)\s*(?:month|months)", text_lower)
        if timeline_match:
            result["timeline_days"] = int(timeline_match.group(1)) * 30
        else:
            timeline_match = re.search(r"(\d+)\s*(?:day|days)", text_lower)
            if timeline_match:
                result["timeline_days"] = int(timeline_match.group(1))
            elif timeline_match := re.search(r"(\d+)\s*(?:week|weeks)", text_lower):
                result["timeline_days"] = int(timeline_match.group(1)) * 7
            elif timeline_match := re.search(r"(\d+)\s*(?:year|years)", text_lower):
                result["timeline_days"] = int(timeline_match.group(1)) * 365
            else:
                result["timeline_days"] = 30

        # ── Affected segments ──
        segment_keywords = {
            "retired": ["senior", "elderly", "pension", "senior citizen"],
            "student": ["student", "school", "college"],
            "homemaker": ["women", "woman", "female", "ladies"],
            "daily_wage_worker": ["worker", "labour", "laborer"],
            "exam_aspirant": ["aspirant", "jee", "neet", "upsc"],
        }
        for segment, keywords in segment_keywords.items():
            if any(kw in text_lower for kw in keywords):
                result["affected_population_segments"].append(segment)

        # ── Route extraction ──
        route_match = re.findall(r"route\s+(\w+)", text_lower)
        if route_match:
            result["affected_routes"] = route_match

        # ── Geographic scope ──
        geo_keywords = {
            "DEL": ["delhi", "ncr"],
            "MUM": ["mumbai", "bombay"],
            "BLR": ["bangalore", "bengaluru"],
            "CHN": ["chennai", "madras"],
            "HYD": ["hyderabad"],
            "KOL": ["kolkata", "calcutta"],
        }
        for city_id, keywords in geo_keywords.items():
            if any(kw in text_lower for kw in keywords):
                result["geographic_scope"].append(city_id)

        # Zone-specific
        zone_keywords = ["south mumbai", "shahdara", "dharavi", "whitefield"]
        for zk in zone_keywords:
            if zk in text_lower:
                result["geographic_scope"].append(zk.upper().replace(" ", "_"))

        return result

    def validate_params(
        self,
        policy_params: PolicyParams,
        zone_context: Any = None,
    ) -> PolicyParams:
        """Validate extracted policy parameters.

        Raises
        ------
        ParseError
            If any parameter is invalid.
        """
        errors = []

        # Check policy type
        if policy_params.policy_type not in VALID_POLICY_TYPES:
            errors.append(
                f"Invalid policy_type '{policy_params.policy_type}'. "
                f"Must be one of: {VALID_POLICY_TYPES}"
            )

        # Check affected modes
        for mode in policy_params.affected_modes:
            if mode not in VALID_MODES:
                errors.append(f"Invalid mode '{mode}'. Must be one of: {VALID_MODES}")

        # Check affected segments
        for seg in policy_params.affected_population_segments:
            if seg not in VALID_ARCHETYPES:
                errors.append(
                    f"Invalid segment '{seg}'. Must be one of: {VALID_ARCHETYPES}"
                )

        # Check magnitude bounds
        if abs(policy_params.magnitude) > 500:
            errors.append(
                f"Magnitude {policy_params.magnitude}% seems unrealistic (>500%)"
            )

        # Check timeline
        if policy_params.timeline_days <= 0:
            errors.append("timeline_days must be positive")

        if errors:
            raise ParseError("; ".join(errors))

        return policy_params
