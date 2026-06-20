"""
redteam_agent.py — Adversarial Red-Team Agent for Driftwatch.

Stress-tests simulation scenarios to identify:
  • Edge cases the main simulation may miss
  • Cascade failure chains across the social network
  • Demographic blind spots — populations harmed but invisible in outputs
  • Adversarial scenario variants that exploit policy weaknesses

Also provides a Crisis Injection engine for mid-simulation disruptions:
  flood, railway_strike, fuel_crisis, pandemic, exam_leak.

Usage:
    red = RedTeamAgent()
    report = await red.stress_test(scenario, results)
    crisis = await red.inject_crisis("railway_strike", sim_state)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────
@dataclass
class RedTeamReport:
    """Results of an adversarial stress test on a simulation scenario."""

    edge_cases: list[str] = field(default_factory=list)
    cascade_failures: list[dict] = field(default_factory=list)
    demographic_blind_spots: list[str] = field(default_factory=list)
    adversarial_variants: list[dict] = field(default_factory=list)
    most_harmed_invisible_segment: str = ""
    confidence: float = 0.0


@dataclass
class CrisisInjection:
    """A crisis event to inject mid-simulation with modified parameters."""

    crisis_type: str  # "flood" | "railway_strike" | "fuel_crisis" | "pandemic" | "exam_leak"
    affected_zones: list[str] = field(default_factory=list)
    modified_params: dict = field(default_factory=dict)
    expected_cascade_depth: int = 0
    description: str = ""


# ─────────────────────────────────────────────────────────────
# Crisis Parameter Templates
# ─────────────────────────────────────────────────────────────
_CRISIS_TEMPLATES: dict[str, dict[str, Any]] = {
    "flood": {
        "description": "Urban flooding event — low-elevation zones submerged, transit halted",
        "low_elevation_indicator_key": "geography.elevation_category",
        "low_elevation_values": ["low", "low-lying", "flood_plain"],
        "modified_params": {
            "transit_disruption_pct": 1.0,       # 100% disruption
            "road_accessibility_pct": 0.30,       # 30% roads passable
            "bus_service_operational": False,
            "metro_service_operational": False,
            "auto_rickshaw_available": False,
            "walking_hazard_multiplier": 3.0,
            "duration_days_range": [3, 7],
        },
        "expected_cascade_depth": 5,
    },
    "railway_strike": {
        "description": "Railway workers' strike — all suburban rail halted, bus overload",
        "modified_params": {
            "suburban_rail_ridership_multiplier": 0.0,
            "bus_overcrowding_factor": 2.5,
            "cab_surge_pricing_multiplier": 2.8,
            "auto_rickshaw_surge_multiplier": 1.8,
            "metro_service_operational": True,  # Metro unaffected
            "duration_days_range": [1, 5],
        },
        "expected_cascade_depth": 4,
    },
    "fuel_crisis": {
        "description": "Fuel shortage — bus, auto, cab costs spike; metro/rail unaffected",
        "modified_params": {
            "bus_fare_multiplier": 1.40,
            "auto_rickshaw_fare_multiplier": 1.40,
            "cab_fare_multiplier": 1.45,
            "metro_fare_multiplier": 1.0,    # Unaffected
            "suburban_rail_fare_multiplier": 1.0,  # Unaffected
            "fuel_availability_pct": 0.60,
            "duration_days_range": [7, 21],
        },
        "expected_cascade_depth": 3,
    },
    "pandemic": {
        "description": "Pandemic outbreak — WFH mandate for tech workers, essential-only transit",
        "modified_params": {
            "wfh_mandate_archetypes": ["tech_knowledge_worker"],
            "essential_worker_only_transit": True,
            "essential_archetypes": [
                "healthcare_worker", "daily_wage_worker",
                "street_vendor", "gig_economy_worker",
            ],
            "transit_capacity_pct": 0.33,
            "gathering_ban": True,
            "protest_suppression_factor": 0.8,  # Protests less likely
            "duration_days_range": [14, 90],
        },
        "expected_cascade_depth": 6,
    },
    "exam_leak": {
        "description": "Examination paper leak — trust collapse in student/aspirant archetypes",
        "modified_params": {
            "examination_trust_shock": -0.40,  # 40% drop in exam trust
            "affected_archetypes": ["student", "exam_aspirant"],
            "coaching_centre_attendance_multiplier": 0.60,
            "peer_cascade_speed_multiplier": 2.0,
            "media_coverage_multiplier": 3.0,
            "online_protest_amplifier": 2.5,
            "duration_days_range": [7, 30],
        },
        "expected_cascade_depth": 4,
    },
}


# ─────────────────────────────────────────────────────────────
# RedTeamAgent
# ─────────────────────────────────────────────────────────────
class RedTeamAgent:
    """Adversarial agent that stress-tests simulation outputs to find
    blind spots, cascade failures, and worst-case scenarios.

    Uses GPT-4o-mini at temperature 0.7 for creative adversarial
    thinking. Falls back to rule-based analysis when API is unavailable.
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._has_openai = False

        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                import openai  # type: ignore[import-untyped]

                self._client = openai.AsyncOpenAI(api_key=api_key)
                self._has_openai = True
                logger.info("RedTeamAgent: OpenAI client initialised")
            except ImportError:
                logger.warning(
                    "RedTeamAgent: openai package not installed — "
                    "falling back to rule-based analysis"
                )
        else:
            logger.info(
                "RedTeamAgent: OPENAI_API_KEY not set — "
                "using rule-based analysis"
            )

    # ── Stress Test ───────────────────────────────────────
    async def stress_test(
        self,
        scenario: dict[str, Any],
        simulation_results: dict[str, Any],
    ) -> RedTeamReport:
        """Run adversarial analysis on a completed simulation scenario.

        Identifies edge cases, cascade failures, and populations that
        were most harmed but least visible in the simulation outputs.
        """
        if self._has_openai:
            return await self._llm_stress_test(scenario, simulation_results)
        return self._rule_based_stress_test(simulation_results)

    async def _llm_stress_test(
        self,
        scenario: dict[str, Any],
        simulation_results: dict[str, Any],
    ) -> RedTeamReport:
        """GPT-4o-mini adversarial analysis with higher temperature."""
        prompt = (
            "You are an adversarial red-team analyst for an urban policy simulation. "
            "Your job is to find what the simulation got WRONG or MISSED.\n\n"
            f"Scenario: {json.dumps(scenario, default=str)}\n"
            f"Results: {json.dumps(simulation_results, default=str)}\n\n"
            "Identify:\n"
            "1. edge_cases: list of 3-5 edge cases the simulation may have missed\n"
            "2. cascade_failures: list of {trigger, chain, final_impact} dicts\n"
            "3. demographic_blind_spots: populations harmed but underrepresented in outputs\n"
            "4. adversarial_variants: {variant_name, modifications, expected_worse_outcome} dicts\n"
            "5. most_harmed_invisible_segment: which population was most harmed but LEAST "
            "visible in the simulation outputs?\n"
            "6. confidence: 0-1 float of how confident you are in this analysis\n\n"
            "Respond with a JSON object. Only output JSON, no other text."
        )
        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,  # Higher for creative adversarial thinking
                max_tokens=800,
            )
            content = response.choices[0].message.content or "{}"
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()

            data = json.loads(content)
            return RedTeamReport(
                edge_cases=data.get("edge_cases", []),
                cascade_failures=data.get("cascade_failures", []),
                demographic_blind_spots=data.get("demographic_blind_spots", []),
                adversarial_variants=data.get("adversarial_variants", []),
                most_harmed_invisible_segment=data.get(
                    "most_harmed_invisible_segment", "unknown"
                ),
                confidence=float(data.get("confidence", 0.5)),
            )
        except Exception as exc:
            logger.warning(
                "RedTeamAgent LLM stress test failed: %s — "
                "falling back to rule-based",
                exc,
            )
            return self._rule_based_stress_test(simulation_results)

    def _rule_based_stress_test(
        self, results: dict[str, Any]
    ) -> RedTeamReport:
        """Deterministic adversarial analysis using heuristics.

        Identifies: archetype with highest absolute loss but lowest
        protest_probability (harmed but invisible), and flags any
        archetype where impact > 20% but representation < 5%.
        """
        metrics = results.get("metrics", {})
        agent_decisions = results.get("agent_decisions", {})

        # ── Compute per-archetype impact stats ──
        archetype_stats: dict[str, dict[str, float]] = {}
        total_agents = max(len(agent_decisions), 1)

        for agent_id, decision in agent_decisions.items():
            archetype = decision.get("archetype", "unknown")
            if archetype not in archetype_stats:
                archetype_stats[archetype] = {
                    "count": 0,
                    "affected_count": 0,
                    "protest_signals": 0,
                    "total_loss": 0.0,
                }
            stats = archetype_stats[archetype]
            stats["count"] += 1
            action = decision.get("action", "no_change")
            if action not in ("no_change", None):
                stats["affected_count"] += 1
            if action == "protest_join":
                stats["protest_signals"] += 1
            stats["total_loss"] += abs(decision.get("welfare_change", 0.0))

        # ── Find most harmed but least visible ──
        most_harmed_invisible = "unknown"
        max_loss_per_capita = 0.0
        min_visibility = float("inf")

        edge_cases: list[str] = []
        blind_spots: list[str] = []

        for archetype, stats in archetype_stats.items():
            count = stats["count"]
            if count == 0:
                continue

            loss_per_capita = stats["total_loss"] / count
            representation_pct = count / total_agents
            protest_rate = stats["protest_signals"] / count
            impact_rate = stats["affected_count"] / count

            # Harmed but invisible: high loss, low protest visibility
            visibility = protest_rate + representation_pct
            if loss_per_capita > max_loss_per_capita and visibility < min_visibility + 0.1:
                max_loss_per_capita = loss_per_capita
                min_visibility = visibility
                most_harmed_invisible = archetype

            # Flag: impact > 20% but representation < 5%
            if impact_rate > 0.20 and representation_pct < 0.05:
                blind_spots.append(
                    f"{archetype}: {impact_rate:.0%} impacted but only "
                    f"{representation_pct:.1%} of population"
                )

        # ── Edge cases ──
        edge_cases.append(
            "Multi-trip agents (homemakers, students with coaching) bear "
            "multiplicative fare impact not captured in single-trip analysis"
        )
        edge_cases.append(
            "Migrant workers' return migration threshold uses disposable "
            "income (post-remittance), not gross — fare sensitivity is 2-3x "
            "higher than income level suggests"
        )
        edge_cases.append(
            "Night-shift healthcare workers have zero transit alternatives "
            "after 11pm — fare changes compound existing constraint"
        )

        # ── Cascade failures ──
        cascade_failures: list[dict] = []
        informal_cascade = metrics.get("informal_economy_cascade", {})
        severe_cascade_nodes = [
            nid for nid, change in informal_cascade.items() if change <= -0.20
        ]
        if severe_cascade_nodes:
            cascade_failures.append({
                "trigger": "Homemaker trip consolidation",
                "chain": [
                    "Fare hike → homemaker trip consolidation",
                    "Trip consolidation → market footfall decline",
                    "Footfall decline → vendor income collapse",
                    "Vendor income collapse → employee wage pressure",
                ],
                "final_impact": (
                    f"{len(severe_cascade_nodes)} market nodes with >20% "
                    f"footfall decline"
                ),
            })

        # ── Adversarial variants ──
        adversarial_variants: list[dict] = [
            {
                "variant_name": "Concurrent fuel price hike",
                "modifications": {"fuel_price_increase_pct": 0.15},
                "expected_worse_outcome": (
                    "Eliminates cab/auto as fare-hike escape valve — "
                    "forces all archetypes onto walking/cycling"
                ),
            },
            {
                "variant_name": "Monsoon + fare hike",
                "modifications": {
                    "walking_hazard_multiplier": 2.5,
                    "cycling_feasibility": 0.1,
                },
                "expected_worse_outcome": (
                    "Removes walking/cycling alternatives during fare hike — "
                    "maximum captive ridership stress"
                ),
            },
        ]

        return RedTeamReport(
            edge_cases=edge_cases,
            cascade_failures=cascade_failures,
            demographic_blind_spots=blind_spots,
            adversarial_variants=adversarial_variants,
            most_harmed_invisible_segment=most_harmed_invisible,
            confidence=0.65,  # Rule-based has moderate confidence
        )

    # ── Crisis Injection ──────────────────────────────────
    async def inject_crisis(
        self,
        crisis_type: str,
        simulation_state: dict[str, Any],
    ) -> CrisisInjection:
        """Generate a crisis injection event for the simulation.

        Maps crisis types to concrete parameter modifications and
        identifies affected zones based on simulation state.

        Parameters
        ----------
        crisis_type : str
            One of: flood, railway_strike, fuel_crisis, pandemic, exam_leak
        simulation_state : dict
            Current simulation state including zone context and metrics.
        """
        if crisis_type not in _CRISIS_TEMPLATES:
            raise ValueError(
                f"Unknown crisis type '{crisis_type}'. "
                f"Valid types: {', '.join(_CRISIS_TEMPLATES.keys())}"
            )

        template = _CRISIS_TEMPLATES[crisis_type]
        modified_params = dict(template["modified_params"])

        # ── Determine affected zones ──
        affected_zones: list[str] = []
        zone_context = simulation_state.get("zone_context", {})
        all_zones = simulation_state.get("active_zones", [])

        if crisis_type == "flood":
            # Affect low-elevation zones
            indicator_key = template.get("low_elevation_indicator_key", "")
            low_values = template.get("low_elevation_values", [])
            for zone_id in all_zones:
                zctx = zone_context.get(zone_id, {})
                geo = zctx.get("geography", {})
                elevation = geo.get("elevation_category", "")
                if elevation.lower() in [v.lower() for v in low_values]:
                    affected_zones.append(zone_id)
            # Fallback: if no elevation data, affect 30% of zones
            if not affected_zones and all_zones:
                n_affected = max(1, len(all_zones) * 3 // 10)
                affected_zones = list(all_zones[:n_affected])

        elif crisis_type == "railway_strike":
            # All zones with suburban rail dependency
            for zone_id in all_zones:
                zctx = zone_context.get(zone_id, {})
                commute = zctx.get("commute_profile", {})
                rail_share = commute.get("suburban_rail_share", 0.0)
                if rail_share > 0.05:
                    affected_zones.append(zone_id)
            if not affected_zones:
                affected_zones = list(all_zones)  # All zones affected

        elif crisis_type == "fuel_crisis":
            # All zones affected (fuel is universal)
            affected_zones = list(all_zones) if all_zones else ["ALL"]

        elif crisis_type == "pandemic":
            # All zones affected
            affected_zones = list(all_zones) if all_zones else ["ALL"]

        elif crisis_type == "exam_leak":
            # Zones with high student/aspirant concentration
            for zone_id in all_zones:
                zctx = zone_context.get(zone_id, {})
                weights = zctx.get("tier1_agent_archetype_weights", {})
                student_share = weights.get("student", 0.0) + weights.get("exam_aspirant", 0.0)
                if student_share > 0.15:
                    affected_zones.append(zone_id)
            if not affected_zones:
                affected_zones = list(all_zones)

        return CrisisInjection(
            crisis_type=crisis_type,
            affected_zones=affected_zones,
            modified_params=modified_params,
            expected_cascade_depth=template.get("expected_cascade_depth", 3),
            description=template["description"],
        )
