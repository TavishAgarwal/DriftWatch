"""
government_agent.py — Autonomous Government Agent for Driftwatch.

Monitors simulation state against configurable thresholds and:
  • Fires alerts (info / warning / critical) when metrics cross boundaries
  • Auto-generates policy alternatives via GPT-4o-mini (fallback: rule-based)
  • Produces legally-structured impact assessments from simulation results

Usage:
    gov = GovernmentAgent()
    action = await gov.monitor_simulation(step_results)
    if action and action.severity == "critical":
        alt = await gov.generate_policy_alternative(policy, state)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────
@dataclass
class GovernmentAction:
    """An alert or recommendation emitted by the Government Agent."""

    action_type: str  # "alert" | "policy_alternative" | "legal_assessment"
    message: str
    severity: str  # "info" | "warning" | "critical"
    metrics_snapshot: dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class PolicyRecommendation:
    """A concrete policy modification suggested to reduce resistance."""

    alternative_magnitude: float  # e.g. 0.10 for a 10% fare hike (reduced from 20%)
    alternative_timeline_days: int  # e.g. 60 (phased rollout)
    targeting_adjustments: dict = field(default_factory=dict)
    projected_resistance_reduction: float = 0.0  # 0–1 scale
    reasoning: str = ""


@dataclass
class LegalImpactReport:
    """Equity and legal risk analysis derived from simulation results."""

    summary: str = ""
    affected_populations: dict[str, int] = field(default_factory=dict)
    equity_assessment: str = ""
    risk_factors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# Default Thresholds
# ─────────────────────────────────────────────────────────────
_DEFAULT_THRESHOLDS: dict[str, float] = {
    "protest_probability": 0.35,
    "modal_shift_pct": 0.15,
    "revenue_impact_pct": -0.10,
}


# ─────────────────────────────────────────────────────────────
# GovernmentAgent
# ─────────────────────────────────────────────────────────────
class GovernmentAgent:
    """Autonomous monitoring agent that watches simulation metrics
    and generates policy alternatives when thresholds are breached.

    Parameters
    ----------
    thresholds : dict, optional
        Override default thresholds. Keys: ``protest_probability``,
        ``modal_shift_pct``, ``revenue_impact_pct``.
    """

    def __init__(self, thresholds: dict[str, float] | None = None) -> None:
        self.thresholds = {**_DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._client: Any = None
        self._has_openai = False

        # Attempt to initialise OpenAI async client
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                import openai  # type: ignore[import-untyped]

                self._client = openai.AsyncOpenAI(api_key=api_key)
                self._has_openai = True
                logger.info("GovernmentAgent: OpenAI client initialised")
            except ImportError:
                logger.warning(
                    "GovernmentAgent: openai package not installed — "
                    "falling back to rule-based reasoning"
                )
        else:
            logger.info(
                "GovernmentAgent: OPENAI_API_KEY not set — "
                "using rule-based reasoning"
            )

    # ── Monitoring ────────────────────────────────────────
    async def monitor_simulation(
        self, step_results: dict[str, Any]
    ) -> GovernmentAction | None:
        """Check simulation step metrics against thresholds.

        Returns a ``GovernmentAction`` if any threshold is crossed,
        ``None`` otherwise.
        """
        metrics = step_results.get("metrics", {})
        breaches: list[tuple[str, str, float, float]] = []  # (key, severity, value, threshold)

        # Protest probability
        protest_prob = metrics.get("protest_probability", 0.0)
        if protest_prob >= self.thresholds["protest_probability"]:
            severity = "critical" if protest_prob >= 0.50 else "warning"
            breaches.append(("protest_probability", severity, protest_prob, self.thresholds["protest_probability"]))

        # Modal shift
        modal_shift = metrics.get("modal_shift_pct", 0.0)
        if modal_shift >= self.thresholds["modal_shift_pct"]:
            severity = "warning" if modal_shift < 0.25 else "critical"
            breaches.append(("modal_shift_pct", severity, modal_shift, self.thresholds["modal_shift_pct"]))

        # Revenue impact (negative = loss)
        revenue_impact = metrics.get("revenue_impact_pct", 0.0)
        if revenue_impact <= self.thresholds["revenue_impact_pct"]:
            severity = "critical" if revenue_impact <= -0.20 else "warning"
            breaches.append(("revenue_impact_pct", severity, revenue_impact, self.thresholds["revenue_impact_pct"]))

        if not breaches:
            return None

        # Determine worst severity
        worst_severity = "critical" if any(s == "critical" for _, s, _, _ in breaches) else "warning"

        # Build alert message
        breach_summaries = [
            f"{key}: {val:.2%} (threshold: {thr:.2%})"
            for key, _, val, thr in breaches
        ]

        if self._has_openai and worst_severity == "critical":
            message = await self._llm_alert_reasoning(breaches, metrics)
        else:
            message = (
                f"Government Agent Alert [{worst_severity.upper()}]\n"
                f"Thresholds breached:\n" +
                "\n".join(f"  • {s}" for s in breach_summaries) +
                "\nRecommendation: Consider phased rollout or magnitude reduction."
            )

        return GovernmentAction(
            action_type="alert",
            message=message,
            severity=worst_severity,
            metrics_snapshot=dict(metrics),
        )

    async def _llm_alert_reasoning(
        self, breaches: list[tuple[str, str, float, float]], metrics: dict
    ) -> str:
        """Use GPT-4o-mini to produce a contextual alert message."""
        try:
            breach_text = "\n".join(
                f"- {key}: current={val:.4f}, threshold={thr:.4f}, severity={sev}"
                for key, sev, val, thr in breaches
            )
            prompt = (
                "You are a government policy advisor AI monitoring an urban transit simulation.\n"
                f"The following thresholds have been breached:\n{breach_text}\n\n"
                f"Full metrics snapshot: {json.dumps(metrics, default=str)}\n\n"
                "Generate a concise, actionable alert (3-5 sentences) explaining "
                "the situation and suggesting immediate action. "
                "Be specific about which populations are most affected."
            )
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300,
            )
            return response.choices[0].message.content or "Alert generated (empty response)"
        except Exception as exc:
            logger.warning("GovernmentAgent LLM alert failed: %s — using rule-based", exc)
            return (
                f"CRITICAL ALERT: {len(breaches)} threshold(s) breached. "
                "Immediate policy review recommended."
            )

    # ── Policy Alternative Generation ─────────────────────
    async def generate_policy_alternative(
        self,
        current_policy: dict[str, Any],
        simulation_state: dict[str, Any],
    ) -> PolicyRecommendation:
        """Generate a policy modification to reduce resistance while
        maintaining revenue objectives.

        Uses GPT-4o-mini with structured JSON output when available,
        otherwise falls back to a simple heuristic: halve the magnitude,
        double the timeline.
        """
        if self._has_openai:
            return await self._llm_policy_alternative(current_policy, simulation_state)
        return self._rule_based_policy_alternative(current_policy, simulation_state)

    async def _llm_policy_alternative(
        self,
        current_policy: dict[str, Any],
        simulation_state: dict[str, Any],
    ) -> PolicyRecommendation:
        """GPT-4o-mini powered policy alternative generation."""
        prompt = (
            "You are a government policy design AI. Given the current transit policy "
            "and its observed outcomes, suggest a modified policy that reduces "
            "public resistance while maintaining at least 70% of the intended revenue.\n\n"
            f"Current policy: {json.dumps(current_policy, default=str)}\n"
            f"Simulation state summary: {json.dumps(simulation_state, default=str)}\n\n"
            "Respond with a JSON object containing:\n"
            '  "alternative_magnitude": <float, e.g. 0.10 for 10% fare change>,\n'
            '  "alternative_timeline_days": <int>,\n'
            '  "targeting_adjustments": {<archetype>: <adjustment_factor>},\n'
            '  "projected_resistance_reduction": <float 0-1>,\n'
            '  "reasoning": "<explanation>"\n'
            "Only output the JSON object, no other text."
        )
        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            content = response.choices[0].message.content or "{}"
            # Strip markdown code fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()

            data = json.loads(content)
            return PolicyRecommendation(
                alternative_magnitude=float(data.get("alternative_magnitude", 0.10)),
                alternative_timeline_days=int(data.get("alternative_timeline_days", 60)),
                targeting_adjustments=data.get("targeting_adjustments", {}),
                projected_resistance_reduction=float(
                    data.get("projected_resistance_reduction", 0.50)
                ),
                reasoning=data.get("reasoning", "LLM-generated alternative"),
            )
        except Exception as exc:
            logger.warning(
                "GovernmentAgent LLM policy alternative failed: %s — "
                "falling back to rule-based",
                exc,
            )
            return self._rule_based_policy_alternative(current_policy, simulation_state)

    def _rule_based_policy_alternative(
        self,
        current_policy: dict[str, Any],
        simulation_state: dict[str, Any],
    ) -> PolicyRecommendation:
        """Deterministic fallback: halve magnitude, double timeline."""
        current_magnitude = current_policy.get("fare_change_pct", 0.20)
        current_timeline = current_policy.get("implementation_days", 30)

        alt_magnitude = current_magnitude * 0.5
        alt_timeline = current_timeline * 2

        # Targeting: exempt the most vulnerable archetypes
        metrics = simulation_state.get("metrics", {})
        protest_prob = metrics.get("protest_probability", 0.0)

        targeting = {
            "daily_wage_worker": 0.0,    # Full exemption
            "street_vendor": 0.0,         # Full exemption
            "migrant_worker": 0.0,        # Full exemption
            "student": 0.5,               # Half fare
            "retired": 0.5,               # Senior concession maintained
        }

        # Estimate resistance reduction based on magnitude halving
        projected_reduction = min(0.58, 0.30 + (current_magnitude - alt_magnitude))

        return PolicyRecommendation(
            alternative_magnitude=alt_magnitude,
            alternative_timeline_days=alt_timeline,
            targeting_adjustments=targeting,
            projected_resistance_reduction=projected_reduction,
            reasoning=(
                f"Rule-based alternative: reduced magnitude from "
                f"{current_magnitude:.0%} to {alt_magnitude:.0%}, "
                f"extended timeline from {current_timeline}d to {alt_timeline}d. "
                f"Exemptions applied for daily_wage_worker, street_vendor, "
                f"migrant_worker archetypes. Student and senior concessions at 50%."
            ),
        )

    # ── Legal Impact Assessment ───────────────────────────
    def format_legal_assessment(
        self, results: dict[str, Any]
    ) -> LegalImpactReport:
        """Compute a legal impact report from simulation results.

        Pure computation — no API call needed. Analyses affected
        populations, equity impacts, and risk factors.
        """
        # ── Affected populations per archetype ──
        agent_decisions = results.get("agent_decisions", {})
        archetype_counts: dict[str, int] = {}
        for agent_id, decision in agent_decisions.items():
            archetype = decision.get("archetype", "unknown")
            if decision.get("action") not in ("no_change", None):
                archetype_counts[archetype] = archetype_counts.get(archetype, 0) + 1

        # ── Equity assessment from income decile impacts ──
        metrics = results.get("metrics", {})
        equity_by_decile = metrics.get("equity_impact_by_income_decile", {})

        if equity_by_decile:
            bottom_3_impact = sum(
                equity_by_decile.get(f"D{d}", 0.0) for d in range(1, 4)
            )
            top_3_impact = sum(
                equity_by_decile.get(f"D{d}", 0.0) for d in range(8, 11)
            )
            if abs(bottom_3_impact) > abs(top_3_impact) * 2:
                equity_str = (
                    f"REGRESSIVE: Bottom 3 deciles bear {abs(bottom_3_impact):.1%} "
                    f"cumulative impact vs {abs(top_3_impact):.1%} for top 3 deciles. "
                    f"Ratio: {abs(bottom_3_impact / top_3_impact) if top_3_impact else float('inf'):.1f}x"
                )
            elif abs(bottom_3_impact) > abs(top_3_impact):
                equity_str = (
                    f"MODERATELY REGRESSIVE: Bottom 3 deciles impacted at "
                    f"{abs(bottom_3_impact):.1%} vs {abs(top_3_impact):.1%} for top 3."
                )
            else:
                equity_str = (
                    f"PROGRESSIVE OR NEUTRAL: Impact distributed "
                    f"proportionally across income deciles."
                )
        else:
            equity_str = "Insufficient data for equity assessment."

        # ── Risk factors ──
        risk_factors: list[str] = []
        protest_prob = metrics.get("protest_probability", 0.0)
        if protest_prob >= 0.50:
            risk_factors.append(
                f"CRITICAL: Protest probability at {protest_prob:.0%} — "
                f"exceeds safe threshold by {(protest_prob - 0.35) / 0.35:.0%}"
            )
        elif protest_prob >= 0.35:
            risk_factors.append(
                f"WARNING: Protest probability at {protest_prob:.0%}"
            )

        cascade = metrics.get("informal_economy_cascade", {})
        severe_nodes = [
            nid for nid, change in cascade.items() if change <= -0.20
        ]
        if severe_nodes:
            risk_factors.append(
                f"Informal economy: {len(severe_nodes)} node(s) with >20% "
                f"footfall decline — livelihoods at risk"
            )

        modal_shift = metrics.get("modal_shift_pct", 0.0)
        if modal_shift >= 0.15:
            risk_factors.append(
                f"Modal shift at {modal_shift:.0%} may indicate service "
                f"avoidance rather than genuine mode preference"
            )

        # ── Recommendations ──
        recommendations: list[str] = []
        if protest_prob >= 0.35:
            recommendations.append(
                "Phase implementation over 60+ days to allow gradual adaptation"
            )
        if severe_nodes:
            recommendations.append(
                "Provide targeted relief for informal economy nodes near "
                "transit stations with >20% footfall decline"
            )
        if any("REGRESSIVE" in equity_str for _ in [1]):
            recommendations.append(
                "Introduce income-linked concession tiers to reduce "
                "regressive impact on lower deciles"
            )
        recommendations.append(
            "Establish a real-time monitoring dashboard for the first "
            "30 days post-implementation"
        )

        # ── Summary ──
        total_affected = sum(archetype_counts.values())
        summary = (
            f"Legal impact assessment: {total_affected} agents affected "
            f"across {len(archetype_counts)} archetypes. "
            f"Protest probability: {protest_prob:.0%}. "
            f"Equity: {equity_str.split(':')[0]}."
        )

        return LegalImpactReport(
            summary=summary,
            affected_populations=archetype_counts,
            equity_assessment=equity_str,
            risk_factors=risk_factors,
            recommendations=recommendations,
        )
