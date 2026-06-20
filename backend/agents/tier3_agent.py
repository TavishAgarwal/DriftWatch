"""
Driftwatch — Tier 3 Agent Engine
=================================

OpenAI GPT-4o-mini powered elite agents.
~1,000 agents in a full simulation.

Tier 3 agents are the cognitive elite of the simulation: senior
bureaucrats, corporate executives, politicians, university VCs, and
economists.  Their decisions cascade downward through Tier 2 opinion
leaders and ultimately reshape the behaviour of 95,000 Tier 1 citizens.

Every GPT-4o-mini call uses a **fixed seed** for reproducibility and
a **temperature of 0.2** for low-variance reasoning.  All outputs
pass through the ``ConstraintValidator`` before entering the
simulation, preventing hallucinated facts from corrupting the model.

When no OpenAI API key is configured, the engine falls back to
deterministic rule-based decisions so simulations can still run
(at reduced cognitive fidelity).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar

logger = logging.getLogger("synthetic_nation.tier3")

# ---------------------------------------------------------------------------
# Try importing the OpenAI library (graceful fallback if missing)
# ---------------------------------------------------------------------------
try:
    from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False
    AsyncOpenAI = None  # type: ignore[assignment, misc]
    logger.warning("openai package not installed — Tier 3 will use rule-based fallback only")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.2
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)   # exponential backoff schedule
BASE_SEED = 42


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Tier3Decision:
    """A single decision produced by a Tier 3 elite agent."""

    action: str                     # e.g. "increase_subsidy", "no_change"
    policy_recommendation: str      # human-readable policy recommendation
    influence_signal: float         # −1.0 to +1.0
    reasoning_chain: str            # step-by-step reasoning trace
    confidence: float               # 0.0 – 1.0

    def __post_init__(self) -> None:
        if not (-1.0 <= self.influence_signal <= 1.0):
            object.__setattr__(
                self, "influence_signal",
                max(-1.0, min(1.0, self.influence_signal)),
            )
        if not (0.0 <= self.confidence <= 1.0):
            object.__setattr__(
                self, "confidence",
                max(0.0, min(1.0, self.confidence)),
            )


@dataclass(frozen=True, slots=True)
class ValidatedDecision:
    """Wrapper around a Tier3Decision after constraint validation."""

    original: Tier3Decision
    validated: bool
    rejection_reason: str | None
    final_decision: Tier3Decision


@dataclass(slots=True)
class ReasoningLog:
    """Audit log entry for a single GPT-4o-mini call."""

    agent_id: str
    step: int
    prompt: str
    response: str
    decision: Tier3Decision
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Tier 3 Agent
# ---------------------------------------------------------------------------
class Tier3Agent:
    """
    Elite decision-maker powered by OpenAI GPT-4o-mini.

    Types
    -----
    senior_bureaucrat, corporate_executive, politician,
    university_vc, economist
    """

    VALID_TYPES: ClassVar[tuple[str, ...]] = (
        "senior_bureaucrat",
        "corporate_executive",
        "politician",
        "university_vc",
        "economist",
    )

    # Detailed system prompts per agent type
    SYSTEM_PROMPTS: ClassVar[dict[str, str]] = {
        "senior_bureaucrat": (
            "You are a senior Indian government bureaucrat (IAS officer) responsible "
            "for urban transport and city infrastructure policy.  You have decades of "
            "administrative experience and deep knowledge of government procedure.  "
            "Your decisions must balance fiscal responsibility, public welfare, and "
            "political feasibility.  You think in terms of policy instruments: fare "
            "adjustments, subsidies, service frequency changes, and infrastructure "
            "investment.  You are cautious, procedural, and evidence-driven.  "
            "Always consider implementation feasibility and inter-departmental "
            "coordination requirements."
        ),
        "corporate_executive": (
            "You are a C-suite executive at a major Indian corporation with operations "
            "across multiple cities.  Your decisions prioritize workforce productivity, "
            "talent retention, and operational continuity.  Transport policy affects your "
            "employees' commute costs and your supply chain logistics.  You think in terms "
            "of business impact: employee attrition risk, productivity loss from commute "
            "stress, CSR opportunities, and lobbying positions.  You balance profitability "
            "with corporate social responsibility."
        ),
        "politician": (
            "You are an elected political representative in an Indian city.  Your "
            "decisions are driven by constituent welfare, electoral calculus, and "
            "party ideology.  You monitor public sentiment closely and respond to "
            "community distress signals from local leaders.  You think in terms of "
            "political action: public statements, legislative interventions, protest "
            "support or suppression, and media engagement.  You balance short-term "
            "populist appeal with long-term policy credibility."
        ),
        "university_vc": (
            "You are the Vice-Chancellor of a major Indian university.  Your decisions "
            "affect tens of thousands of students and faculty.  Transport policy impacts "
            "student attendance, campus access, and the broader education ecosystem.  "
            "Examination policy integrity is your highest priority.  You think in terms "
            "of academic continuity: exam schedules, student welfare, faculty commute, "
            "and institutional reputation.  You are articulate, principled, and focused "
            "on long-term educational outcomes."
        ),
        "economist": (
            "You are a senior economist advising the city government on urban transport "
            "and labour market policy.  Your analysis is data-driven and considers "
            "second-order effects: how fare changes cascade through the informal economy, "
            "affect labour supply elasticity, and alter consumption patterns.  You model "
            "trade-offs between revenue, equity, and economic efficiency.  You communicate "
            "in terms of welfare analysis, deadweight loss, price elasticity, and "
            "distributional impact.  You are rigorous but accessible."
        ),
    }

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        zone_id: str,
        influence_scope: str,
        policy_domain: str,
    ) -> None:
        if agent_type not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid Tier 3 agent type '{agent_type}'. "
                f"Must be one of {self.VALID_TYPES}"
            )

        self.agent_id = agent_id
        self.agent_type = agent_type
        self.zone_id = zone_id
        self.influence_scope = influence_scope    # e.g. "city_wide", "zone_local"
        self.policy_domain = policy_domain        # e.g. "transport", "education"

        # Audit trail — stores every API call for reproducibility review
        self.reasoning_log: list[ReasoningLog] = []

        # Lazily-initialized OpenAI client
        self._client: AsyncOpenAI | None = None
        self._api_key_checked = False

    def __repr__(self) -> str:
        return (
            f"Tier3Agent(id={self.agent_id!r}, type={self.agent_type!r}, "
            f"zone={self.zone_id!r}, domain={self.policy_domain!r})"
        )

    # ------------------------------------------------------------------
    # OpenAI client management
    # ------------------------------------------------------------------
    def _get_client(self) -> AsyncOpenAI | None:
        """
        Return an AsyncOpenAI client if the API key is available,
        otherwise ``None``.
        """
        if not _HAS_OPENAI:
            return None

        if self._client is not None:
            return self._client

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            if not self._api_key_checked:
                logger.warning(
                    "OPENAI_API_KEY not set — Tier 3 agent %s will use "
                    "rule-based fallback",
                    self.agent_id,
                )
                self._api_key_checked = True
            return None

        self._client = AsyncOpenAI(api_key=api_key)
        self._api_key_checked = True
        return self._client

    # ------------------------------------------------------------------
    # Core: Reasoning  →  Tier3Decision
    # ------------------------------------------------------------------
    async def reason(
        self,
        context: dict[str, Any],
        connected_tier2_signals: list[Any],
        step: int,
    ) -> Tier3Decision:
        """
        Produce a Tier3Decision based on the current city state and
        incoming Tier 2 sentiment signals.

        Parameters
        ----------
        context
            Current city-state dictionary (population metrics, policy
            parameters, transport network state, etc.).
        connected_tier2_signals
            List of signals/broadcasts received from connected Tier 2
            agents this step.
        step
            Simulation time step (used as part of the deterministic
            seed for reproducibility).

        Returns
        -------
        Tier3Decision
        """
        client = self._get_client()
        if client is None:
            decision = self._rule_based_fallback(context, connected_tier2_signals)
            self._record_log(step, "(rule-based — no API key)", "(fallback)", decision)
            return decision

        system_prompt = self.SYSTEM_PROMPTS[self.agent_type]
        user_prompt = self._build_user_prompt(context, connected_tier2_signals, step)

        # ---- Retry loop with exponential backoff ----
        last_exception: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model=OPENAI_MODEL,
                    temperature=OPENAI_TEMPERATURE,
                    seed=BASE_SEED + step,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )

                raw_content = response.choices[0].message.content or ""
                decision = self._parse_response(raw_content)
                self._record_log(step, user_prompt, raw_content, decision)
                return decision

            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "Tier 3 agent %s: parse error on attempt %d/%d: %s",
                    self.agent_id, attempt + 1, MAX_RETRIES, exc,
                )
                last_exception = exc
            except Exception as exc:
                # Covers APIConnectionError, RateLimitError, APIStatusError, etc.
                logger.warning(
                    "Tier 3 agent %s: API error on attempt %d/%d: %s",
                    self.agent_id, attempt + 1, MAX_RETRIES, exc,
                )
                last_exception = exc

            # Backoff before next attempt
            if attempt < MAX_RETRIES - 1:
                import asyncio
                await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])

        # All retries exhausted
        logger.error(
            "Tier 3 agent %s: all %d retries exhausted (last error: %s). "
            "Falling back to rule-based decision.",
            self.agent_id, MAX_RETRIES, last_exception,
        )
        decision = self._rule_based_fallback(context, connected_tier2_signals)
        self._record_log(step, user_prompt, f"(fallback after {MAX_RETRIES} failures)", decision)
        return decision

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------
    def _build_user_prompt(
        self,
        context: dict[str, Any],
        tier2_signals: list[Any],
        step: int,
    ) -> str:
        """Build the user-role prompt for GPT-4o-mini."""

        # Summarize Tier 2 signals
        if tier2_signals:
            signal_summaries = []
            for i, sig in enumerate(tier2_signals[:20]):  # cap at 20 signals
                if hasattr(sig, "sentiment_delta"):
                    signal_summaries.append(
                        f"  Signal {i+1}: sentiment_delta={sig.sentiment_delta:.3f}, "
                        f"message='{getattr(sig, 'message', 'N/A')[:100]}'"
                    )
                elif isinstance(sig, dict):
                    signal_summaries.append(
                        f"  Signal {i+1}: {json.dumps(sig, default=str)[:150]}"
                    )
                else:
                    signal_summaries.append(f"  Signal {i+1}: {str(sig)[:150]}")
            signals_text = "\n".join(signal_summaries)
        else:
            signals_text = "  No Tier 2 signals received this step."

        # Summarize context
        context_text = json.dumps(context, indent=2, default=str)[:2000]

        return (
            f"SIMULATION STEP: {step}\n"
            f"ZONE: {self.zone_id}\n"
            f"POLICY DOMAIN: {self.policy_domain}\n"
            f"INFLUENCE SCOPE: {self.influence_scope}\n\n"
            f"CURRENT CITY STATE:\n{context_text}\n\n"
            f"TIER 2 SENTIMENT SIGNALS:\n{signals_text}\n\n"
            f"Based on the above, produce your decision as a JSON object with "
            f"exactly these keys:\n"
            f'- "action" (string): the policy action you recommend\n'
            f'- "policy_recommendation" (string): detailed recommendation (max 300 chars)\n'
            f'- "influence_signal" (float, -1.0 to 1.0): strength and direction of '
            f"your influence on the social network\n"
            f'- "reasoning_chain" (string): your step-by-step reasoning (max 500 chars)\n'
            f'- "confidence" (float, 0.0 to 1.0): your confidence in this decision\n'
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_response(raw_content: str) -> Tier3Decision:
        """Parse a JSON string from GPT-4o-mini into a Tier3Decision."""
        data = json.loads(raw_content)

        return Tier3Decision(
            action=str(data.get("action", "no_change")),
            policy_recommendation=str(
                data.get("policy_recommendation", "No recommendation")
            )[:300],
            influence_signal=max(
                -1.0, min(1.0, float(data.get("influence_signal", 0.0)))
            ),
            reasoning_chain=str(data.get("reasoning_chain", ""))[:500],
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
        )

    # ------------------------------------------------------------------
    # Rule-based fallback
    # ------------------------------------------------------------------
    def _rule_based_fallback(
        self,
        context: dict[str, Any],
        signals: list[Any],
    ) -> Tier3Decision:
        """
        Simple heuristic fallback when OpenAI is unavailable.

        If average negative sentiment from Tier 2 signals exceeds 0.5,
        recommends policy moderation.
        """
        # Extract sentiment values from signals
        sentiment_values: list[float] = []
        for sig in signals:
            if hasattr(sig, "sentiment_delta"):
                sentiment_values.append(sig.sentiment_delta)
            elif isinstance(sig, dict) and "sentiment_delta" in sig:
                try:
                    sentiment_values.append(float(sig["sentiment_delta"]))
                except (ValueError, TypeError):
                    pass

        if sentiment_values:
            avg_sentiment = sum(sentiment_values) / len(sentiment_values)
        else:
            avg_sentiment = 0.0

        if avg_sentiment < -0.5:
            return Tier3Decision(
                action="moderate_policy",
                policy_recommendation=(
                    f"Tier 2 signals indicate strong negative sentiment "
                    f"(avg={avg_sentiment:.3f}). Recommend phased implementation "
                    f"and stakeholder consultation for {self.policy_domain} in "
                    f"{self.zone_id}."
                ),
                influence_signal=avg_sentiment * 0.6,
                reasoning_chain=(
                    f"Rule-based: avg Tier 2 sentiment ({avg_sentiment:.3f}) below "
                    f"-0.5 threshold → recommend moderation. Agent type "
                    f"{self.agent_type} in {self.zone_id}."
                ),
                confidence=0.4,
            )

        if avg_sentiment < -0.2:
            return Tier3Decision(
                action="monitor",
                policy_recommendation=(
                    f"Moderate negative sentiment detected "
                    f"(avg={avg_sentiment:.3f}). Recommend continued "
                    f"monitoring of {self.policy_domain} impacts in {self.zone_id}."
                ),
                influence_signal=avg_sentiment * 0.3,
                reasoning_chain=(
                    f"Rule-based: avg Tier 2 sentiment ({avg_sentiment:.3f}) between "
                    f"-0.5 and -0.2 → recommend monitoring."
                ),
                confidence=0.3,
            )

        return Tier3Decision(
            action="no_change",
            policy_recommendation=(
                f"Current {self.policy_domain} policy in {self.zone_id} appears stable. "
                f"No immediate action required."
            ),
            influence_signal=0.0,
            reasoning_chain=(
                f"Rule-based: avg Tier 2 sentiment ({avg_sentiment:.3f}) above -0.2 "
                f"→ no action needed."
            ),
            confidence=0.5,
        )

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------
    def _record_log(
        self,
        step: int,
        prompt: str,
        response: str,
        decision: Tier3Decision,
    ) -> None:
        """Append a ReasoningLog entry for audit."""
        self.reasoning_log.append(
            ReasoningLog(
                agent_id=self.agent_id,
                step=step,
                prompt=prompt,
                response=response,
                decision=decision,
            )
        )


# ---------------------------------------------------------------------------
# Constraint Validator
# ---------------------------------------------------------------------------
class ConstraintValidator:
    """
    Post-hoc validation layer for Tier 3 decisions.

    ALL Tier 3 outputs must pass through this validator before entering
    the simulation.  Checks prevent hallucinated facts from corrupting
    the model.  If any check fails, the decision is replaced with a
    safe ``fallback_default_decision``.

    Checks
    ------
    1. **Income bounds** — any income claim must be within the agent
       archetype's range.
    2. **Route existence** — referenced routes/stations must exist in
       the city's transport network.
    3. **Political consistency** — political positions must be
       consistent with the agent's demographic profile.
    4. **Factual grounding** — policy claims are checked against a
       locked knowledge base of known facts.
    """

    # Archetype income bounds (monthly, INR) — from AGENT_SPEC
    INCOME_BOUNDS: ClassVar[dict[str, tuple[int, int]]] = {
        "daily_wage_worker":        (8_000,   16_000),
        "formal_sector_employee":   (18_000,  45_000),
        "government_employee":      (25_000,  85_000),
        "tech_knowledge_worker":    (60_000,  350_000),
        "small_business_owner":     (25_000,  180_000),
        "student":                  (0,       0),
        "homemaker":                (0,       0),
        "street_vendor":            (6_000,   22_000),
        "retired":                  (8_000,   45_000),
        "migrant_worker":           (10_000,  28_000),
        "healthcare_worker":        (15_000,  180_000),
        "exam_aspirant":            (0,       0),
        "gig_economy_worker":       (18_000,  55_000),
        "journalist_tier1":         (15_000,  65_000),
        # Tier 3 agent types (elite)
        "senior_bureaucrat":        (80_000,  300_000),
        "corporate_executive":      (200_000, 2_000_000),
        "politician":               (50_000,  500_000),
        "university_vc":            (150_000, 500_000),
        "economist":                (100_000, 600_000),
    }

    # Political leaning labels
    _VALID_POLITICAL_POSITIONS: ClassVar[set[str]] = {
        "progressive", "moderate", "conservative",
        "populist", "technocratic", "centrist",
        "left", "right", "centre-left", "centre-right",
    }

    # ------------------------------------------------------------------
    # Primary validation entry-point
    # ------------------------------------------------------------------
    @classmethod
    def validate_output(
        cls,
        decision: Tier3Decision,
        agent_profile: dict[str, Any],
        city_state: dict[str, Any],
    ) -> ValidatedDecision:
        """
        Validate a Tier3Decision against simulation constraints.

        Parameters
        ----------
        decision
            The raw decision from the Tier 3 agent.
        agent_profile
            Dictionary describing the agent (must include keys like
            ``agent_type``, ``income_monthly``, ``political_leaning``).
        city_state
            Dictionary describing the current city state (must include
            ``transport_network`` with a ``stations`` or ``routes`` key
            for route-existence checks).

        Returns
        -------
        ValidatedDecision
        """
        # Accumulate rejection reasons
        rejection_reasons: list[str] = []

        # ---- Check 1: Income bounds ----
        income_reason = cls._check_income_bounds(decision, agent_profile)
        if income_reason:
            rejection_reasons.append(income_reason)

        # ---- Check 2: Route existence ----
        route_reason = cls._check_route_existence(decision, city_state)
        if route_reason:
            rejection_reasons.append(route_reason)

        # ---- Check 3: Political consistency ----
        political_reason = cls._check_political_consistency(decision, agent_profile)
        if political_reason:
            rejection_reasons.append(political_reason)

        # ---- Check 4: Factual grounding ----
        factual_reason = cls._check_factual_grounding(decision, city_state)
        if factual_reason:
            rejection_reasons.append(factual_reason)

        if rejection_reasons:
            combined_reason = "; ".join(rejection_reasons)
            logger.warning(
                "Tier 3 decision rejected: %s", combined_reason,
            )
            fallback = cls._fallback_default_decision()
            return ValidatedDecision(
                original=decision,
                validated=False,
                rejection_reason=combined_reason,
                final_decision=fallback,
            )

        return ValidatedDecision(
            original=decision,
            validated=True,
            rejection_reason=None,
            final_decision=decision,
        )

    # ------------------------------------------------------------------
    # Individual constraint checks
    # ------------------------------------------------------------------
    @classmethod
    def _check_income_bounds(
        cls,
        decision: Tier3Decision,
        agent_profile: dict[str, Any],
    ) -> str | None:
        """
        If the decision's reasoning or recommendation references a
        specific income figure, verify it's within the archetype range.
        """
        agent_type = agent_profile.get("agent_type", "")
        bounds = cls.INCOME_BOUNDS.get(agent_type)
        if bounds is None:
            return None

        lower, upper = bounds
        if upper == 0:
            # Non-earning archetype — nothing to check
            return None

        # Quick scan: look for rupee figures in the recommendation/reasoning
        import re
        text = f"{decision.policy_recommendation} {decision.reasoning_chain}"
        # Match patterns like ₹50,000 or 50000 or Rs.50000
        income_matches = re.findall(
            r"(?:₹|Rs\.?\s*|INR\s*)([0-9,]+)", text, re.IGNORECASE
        )
        for match_str in income_matches:
            try:
                value = int(match_str.replace(",", ""))
                if value < lower or value > upper:
                    return (
                        f"Income claim ₹{value:,} outside bounds "
                        f"[₹{lower:,}, ₹{upper:,}] for {agent_type}"
                    )
            except ValueError:
                continue

        return None

    @classmethod
    def _check_route_existence(
        cls,
        decision: Tier3Decision,
        city_state: dict[str, Any],
    ) -> str | None:
        """
        If the decision references specific transport routes or
        stations, verify they exist in the city transport network.
        """
        transport_network = city_state.get("transport_network", {})
        known_stations: set[str] = set(transport_network.get("stations", []))
        known_routes: set[str] = set(transport_network.get("routes", []))

        if not known_stations and not known_routes:
            # No transport network data to validate against
            return None

        text = f"{decision.policy_recommendation} {decision.reasoning_chain}"
        text_upper = text.upper()

        # Check station references
        for station in known_stations:
            pass  # Station exists — no error if mentioned

        # Check for station-like references NOT in known set
        import re
        # Match patterns like "Station: XYZ" or "at XYZ station"
        mentioned_stations = re.findall(
            r"(?:station|stop|halt)[\s:]+([A-Z][A-Za-z_\- ]+)",
            text, re.IGNORECASE,
        )
        for mentioned in mentioned_stations:
            normalized = mentioned.strip().upper().replace(" ", "_")
            if known_stations and normalized not in {s.upper() for s in known_stations}:
                return (
                    f"Referenced station '{mentioned.strip()}' does not exist "
                    f"in city transport network"
                )

        return None

    @classmethod
    def _check_political_consistency(
        cls,
        decision: Tier3Decision,
        agent_profile: dict[str, Any],
    ) -> str | None:
        """
        Verify that the decision's political stance is consistent with
        the agent's demographic profile.
        """
        agent_political_leaning = agent_profile.get("political_leaning", "")
        if not agent_political_leaning:
            return None

        # Simple consistency: a "conservative" agent shouldn't recommend
        # radical progressive policy, and vice versa
        text_lower = (
            f"{decision.action} {decision.policy_recommendation}"
        ).lower()

        opposing_pairs = {
            "conservative": ["radical redistribution", "wealth tax", "nationalize"],
            "progressive":  ["deregulate completely", "eliminate all subsidies"],
            "populist":     ["austerity", "cut welfare"],
        }

        leaning_lower = agent_political_leaning.lower()
        contradictions = opposing_pairs.get(leaning_lower, [])
        for phrase in contradictions:
            if phrase in text_lower:
                return (
                    f"Political inconsistency: {agent_political_leaning} agent "
                    f"recommends '{phrase}'"
                )

        return None

    @classmethod
    def _check_factual_grounding(
        cls,
        decision: Tier3Decision,
        city_state: dict[str, Any],
    ) -> str | None:
        """
        Verify that policy claims reference known facts from the
        locked knowledge base.
        """
        known_facts = city_state.get("known_policy_facts", {})
        if not known_facts:
            # No fact base to validate against
            return None

        # Check for fare claims
        text = f"{decision.policy_recommendation} {decision.reasoning_chain}"

        import re
        fare_mentions = re.findall(
            r"(?:fare|cost|price)[\s:]*(?:₹|Rs\.?\s*|INR\s*)([0-9,]+)",
            text, re.IGNORECASE,
        )
        known_fares = known_facts.get("current_fares", {})
        if fare_mentions and known_fares:
            for fare_str in fare_mentions:
                try:
                    claimed_fare = int(fare_str.replace(",", ""))
                    max_known_fare = max(
                        int(v) for v in known_fares.values()
                        if str(v).isdigit()
                    ) if known_fares else float("inf")
                    if claimed_fare > max_known_fare * 3:
                        return (
                            f"Fare claim ₹{claimed_fare:,} is implausibly high "
                            f"(max known fare ₹{max_known_fare:,})"
                        )
                except (ValueError, TypeError):
                    continue

        return None

    # ------------------------------------------------------------------
    # Fallback default decision
    # ------------------------------------------------------------------
    @staticmethod
    def _fallback_default_decision() -> Tier3Decision:
        """Safe default decision when validation fails."""
        return Tier3Decision(
            action="no_change",
            policy_recommendation="Decision rejected by constraint validator. No action taken.",
            influence_signal=0.0,
            reasoning_chain="Automatic fallback — original decision failed validation.",
            confidence=0.1,
        )
