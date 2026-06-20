"""
Driftwatch — Tier 2 Agent Engine
=================================

Ollama-powered (Llama 3.1 8B) opinion leaders.
~4,000 agents in a full simulation.

Tier 2 agents sit between the 95,000 deterministic Tier 1 citizens and
the 1,000 GPT-4o-mini Tier 3 elites.  Each Tier 2 agent monitors
sentiment from its connected Tier 1 cluster and, when negativity
crosses a threshold, produces a reasoned *InfluenceBroadcast* that
cascades back down through the social network via belief contagion.

Ollama integration uses httpx.AsyncClient with a 10-second timeout and
automatic rule-based fallback when the local LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import ClassVar

import httpx

logger = logging.getLogger("synthetic_nation.tier2")

# ---------------------------------------------------------------------------
# Ollama endpoint configuration
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_TIMEOUT_SECONDS = 10.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class InfluenceBroadcast:
    """Signal emitted by a Tier 2 agent to influence connected Tier 1 agents."""

    message: str
    sentiment_delta: float          # −1.0 (strongly negative) to +1.0 (strongly positive)
    target_archetypes: list[str]
    credibility_score: float        # 0.0 – 1.0

    def __post_init__(self) -> None:
        if not (-1.0 <= self.sentiment_delta <= 1.0):
            object.__setattr__(
                self, "sentiment_delta",
                max(-1.0, min(1.0, self.sentiment_delta)),
            )
        if not (0.0 <= self.credibility_score <= 1.0):
            object.__setattr__(
                self, "credibility_score",
                max(0.0, min(1.0, self.credibility_score)),
            )


@dataclass(frozen=True, slots=True)
class InfluenceDelta:
    """Directed influence change applied to a single Tier 1 agent."""

    target_agent_id: str
    delta: float
    source_type: str                # e.g. "tier2_broadcast", "tier3_cascade"


# ---------------------------------------------------------------------------
# Tier 2 Agent
# ---------------------------------------------------------------------------
class Tier2Agent:
    """
    Opinion leader powered by Ollama (Llama 3.1 8B).

    Types
    -----
    journalist, rwa_president, union_representative, school_principal,
    small_business_owner, local_councillor, coaching_owner,
    community_leader, tech_executive, senior_bureaucrat
    """

    # All valid Tier 2 agent types
    VALID_TYPES: ClassVar[tuple[str, ...]] = (
        "journalist",
        "rwa_president",
        "union_representative",
        "school_principal",
        "small_business_owner",
        "local_councillor",
        "coaching_owner",
        "community_leader",
        "tech_executive",
        "senior_bureaucrat",
    )

    # Base credibility per type (governs how strongly broadcasts land)
    CREDIBILITY_SCORES: ClassVar[dict[str, float]] = {
        "journalist":           0.75,
        "rwa_president":        0.82,
        "union_representative": 0.70,
        "school_principal":     0.78,
        "small_business_owner": 0.65,
        "local_councillor":     0.85,
        "coaching_owner":       0.60,
        "community_leader":     0.80,
        "tech_executive":       0.72,
        "senior_bureaucrat":    0.88,
    }

    # Amplification factor: how much each type amplifies incoming Tier 3
    # policy signals before relaying to Tier 1
    AMPLIFICATION_FACTORS: ClassVar[dict[str, float]] = {
        "journalist":           1.40,   # media multiplier (from AGENT_SPEC)
        "rwa_president":        1.15,
        "union_representative": 1.30,
        "school_principal":     1.10,
        "small_business_owner": 1.05,
        "local_councillor":     1.35,
        "coaching_owner":       1.00,
        "community_leader":     1.20,
        "tech_executive":       1.10,
        "senior_bureaucrat":    1.25,
    }

    # Pre-baked fallback message templates (used when Ollama is unavailable)
    _FALLBACK_TEMPLATES: ClassVar[dict[str, str]] = {
        "journalist":           "Community sentiment is {direction}. Reporting on ground-level impact in {zone}.",
        "rwa_president":        "As RWA president of {zone}, residents have raised concerns about {direction} sentiment.",
        "union_representative": "Workers in {zone} express {direction} sentiment. Union will evaluate collective response.",
        "school_principal":     "School community in {zone} is affected. Parents report {direction} impact on families.",
        "small_business_owner": "Business conditions in {zone} are {direction}. Footfall and costs both impacted.",
        "local_councillor":     "Constituents in {zone} report {direction} sentiment. Evaluating policy response options.",
        "coaching_owner":       "Students in {zone} affected by current conditions. Attendance trends are {direction}.",
        "community_leader":     "Community in {zone} is experiencing {direction} conditions. Organizing support measures.",
        "tech_executive":       "Industry perspective from {zone}: current policy trajectory is {direction} for the sector.",
        "senior_bureaucrat":    "Administrative assessment for {zone}: ground sentiment is {direction}. Reviewing options.",
    }

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        zone_id: str,
        influence_radius: float,
        connected_tier1_ids: list[str],
    ) -> None:
        if agent_type not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid Tier 2 agent type '{agent_type}'. "
                f"Must be one of {self.VALID_TYPES}"
            )

        self.agent_id = agent_id
        self.agent_type = agent_type
        self.zone_id = zone_id
        self.influence_radius = influence_radius
        self.connected_tier1_ids = list(connected_tier1_ids)

        self.base_credibility = self.CREDIBILITY_SCORES[agent_type]
        self.amplification_factor = self.AMPLIFICATION_FACTORS[agent_type]

        # Mutable state
        self._last_broadcast_ts: float = 0.0
        self._consecutive_negative_steps: int = 0

    def __repr__(self) -> str:
        return (
            f"Tier2Agent(id={self.agent_id!r}, type={self.agent_type!r}, "
            f"zone={self.zone_id!r}, tier1_conns={len(self.connected_tier1_ids)})"
        )

    # ------------------------------------------------------------------
    # Ollama availability probe
    # ------------------------------------------------------------------
    @classmethod
    async def _is_ollama_available(cls) -> bool:
        """Ping Ollama /api/tags to verify the server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(OLLAMA_TAGS_URL)
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            return False

    # ------------------------------------------------------------------
    # Core: Sentiment Monitor  →  InfluenceBroadcast
    # ------------------------------------------------------------------
    async def sentiment_monitor(
        self,
        tier1_sentiments: dict[str, float],
        *,
        negative_threshold: float = 0.3,
    ) -> InfluenceBroadcast | None:
        """
        Monitor connected Tier 1 agents' sentiment and, if average
        negativity exceeds *negative_threshold*, generate an
        InfluenceBroadcast.

        Parameters
        ----------
        tier1_sentiments
            Mapping of ``agent_id → sentiment`` for **all** Tier 1
            agents (only connected IDs are used).
        negative_threshold
            Absolute value of mean negative sentiment that triggers a
            response (default 0.3).

        Returns
        -------
        InfluenceBroadcast | None
            Broadcast object if a response was triggered, else ``None``.
        """
        # ---- Collect connected sentiments ----
        connected_values: list[float] = [
            tier1_sentiments[tid]
            for tid in self.connected_tier1_ids
            if tid in tier1_sentiments
        ]
        if not connected_values:
            return None

        mean_sentiment = sum(connected_values) / len(connected_values)

        # ---- Check if negativity crosses threshold ----
        if abs(mean_sentiment) < negative_threshold and mean_sentiment <= 0:
            return None
        if mean_sentiment > 0:
            # Positive sentiment — no alarm broadcast needed
            return None

        # Negative sentiment exceeds threshold → respond
        self._consecutive_negative_steps += 1

        # ---- Try Ollama first ----
        broadcast = await self._ollama_generate_response(
            mean_sentiment, connected_values
        )
        if broadcast is not None:
            self._last_broadcast_ts = time.monotonic()
            return broadcast

        # ---- Fallback: rule-based response ----
        broadcast = self._rule_based_response(mean_sentiment)
        self._last_broadcast_ts = time.monotonic()
        return broadcast

    # ------------------------------------------------------------------
    # Ollama LLM call
    # ------------------------------------------------------------------
    async def _ollama_generate_response(
        self,
        mean_sentiment: float,
        connected_values: list[float],
    ) -> InfluenceBroadcast | None:
        """
        Call Ollama Llama 3.1 8B for a reasoned response.

        Returns ``None`` on any failure (timeout, parse error, server
        unavailable) so the caller can fall back to rules.
        """
        sentiment_summary = (
            f"Average sentiment: {mean_sentiment:.3f} across "
            f"{len(connected_values)} connected citizens. "
            f"Range: [{min(connected_values):.2f}, {max(connected_values):.2f}]. "
            f"Consecutive negative steps: {self._consecutive_negative_steps}."
        )

        prompt = (
            f"You are a {self.agent_type.replace('_', ' ')} in zone {self.zone_id}. "
            f"The community sentiment is: {sentiment_summary} "
            f"As a {self.agent_type.replace('_', ' ')}, what is your public response? "
            f"Respond ONLY with a JSON object containing exactly these keys: "
            f'"message" (string, your public statement, max 200 chars), '
            f'"sentiment_delta" (float between -1.0 and 1.0), '
            f'"target_archetypes" (list of strings from: daily_wage_worker, '
            f"formal_sector_employee, government_employee, tech_knowledge_worker, "
            f"small_business_owner, student, homemaker, street_vendor, retired, "
            f"migrant_worker, healthcare_worker, exam_aspirant, gig_economy_worker, "
            f'journalist_tier1).'
        )

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=OLLAMA_TIMEOUT_SECONDS
            ) as client:
                resp = await client.post(OLLAMA_GENERATE_URL, json=payload)
                resp.raise_for_status()

            body = resp.json()
            raw_text: str = body.get("response", "")

            # Parse the JSON payload from the LLM
            data = json.loads(raw_text)

            message = str(data.get("message", ""))[:200]
            sentiment_delta = float(data.get("sentiment_delta", 0.0))
            sentiment_delta = max(-1.0, min(1.0, sentiment_delta))

            raw_archetypes = data.get("target_archetypes", [])
            if isinstance(raw_archetypes, str):
                raw_archetypes = [raw_archetypes]
            target_archetypes = [str(a) for a in raw_archetypes][:14]

            return InfluenceBroadcast(
                message=message,
                sentiment_delta=sentiment_delta,
                target_archetypes=target_archetypes,
                credibility_score=self.base_credibility,
            )

        except httpx.TimeoutException:
            logger.warning(
                "Ollama timeout (%.1fs) for agent %s — falling back to rules",
                OLLAMA_TIMEOUT_SECONDS, self.agent_id,
            )
            return None
        except (httpx.ConnectError, httpx.HTTPStatusError, OSError) as exc:
            logger.warning(
                "Ollama unavailable for agent %s: %s — falling back to rules",
                self.agent_id, exc,
            )
            return None
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Failed to parse Ollama response for agent %s: %s — "
                "falling back to rules",
                self.agent_id, exc,
            )
            return None

    # ------------------------------------------------------------------
    # Rule-based fallback
    # ------------------------------------------------------------------
    def _rule_based_response(
        self,
        mean_sentiment: float,
    ) -> InfluenceBroadcast:
        """
        Deterministic fallback when Ollama is unavailable.

        sentiment_delta = mean_sentiment × credibility × 0.8
        Message is selected from per-type templates.
        """
        sentiment_delta = mean_sentiment * self.base_credibility * 0.8
        sentiment_delta = max(-1.0, min(1.0, sentiment_delta))

        direction = "negative" if mean_sentiment < 0 else "positive"
        template = self._FALLBACK_TEMPLATES.get(
            self.agent_type,
            "Sentiment in {zone} is {direction}. Evaluating response.",
        )
        message = template.format(zone=self.zone_id, direction=direction)

        # Default target: all archetypes reachable by this agent type
        target_archetypes = self._default_target_archetypes()

        return InfluenceBroadcast(
            message=message,
            sentiment_delta=sentiment_delta,
            target_archetypes=target_archetypes,
            credibility_score=self.base_credibility,
        )

    def _default_target_archetypes(self) -> list[str]:
        """
        Return the default archetype audience for this agent type.

        Journalists broadcast to everyone; school principals target
        students & homemakers; union reps target workers; etc.
        """
        _mapping: dict[str, list[str]] = {
            "journalist":           [
                "daily_wage_worker", "formal_sector_employee", "student",
                "homemaker", "tech_knowledge_worker", "migrant_worker",
                "street_vendor", "retired", "gig_economy_worker",
            ],
            "rwa_president":        ["homemaker", "retired", "formal_sector_employee"],
            "union_representative": [
                "daily_wage_worker", "formal_sector_employee", "migrant_worker",
            ],
            "school_principal":     ["student", "homemaker", "exam_aspirant"],
            "small_business_owner": [
                "daily_wage_worker", "street_vendor", "homemaker",
            ],
            "local_councillor":     [
                "daily_wage_worker", "homemaker", "small_business_owner",
                "retired", "street_vendor",
            ],
            "coaching_owner":       ["student", "exam_aspirant"],
            "community_leader":     [
                "daily_wage_worker", "homemaker", "migrant_worker",
                "street_vendor", "retired",
            ],
            "tech_executive":       [
                "tech_knowledge_worker", "gig_economy_worker",
                "formal_sector_employee",
            ],
            "senior_bureaucrat":    [
                "government_employee", "formal_sector_employee",
            ],
        }
        return _mapping.get(self.agent_type, ["formal_sector_employee"])

    # ------------------------------------------------------------------
    # Belief Contagion: Tier 3 → Tier 2 → Tier 1
    # ------------------------------------------------------------------
    def belief_contagion_step(
        self,
        received_broadcasts: list[InfluenceBroadcast],
    ) -> list[InfluenceDelta]:
        """
        Process incoming broadcasts (typically from Tier 3 decisions
        translated into InfluenceBroadcasts) and generate per-Tier-1
        InfluenceDeltas.

        Each incoming broadcast's ``sentiment_delta`` is amplified by
        this agent's type-specific amplification factor and weighted
        by the broadcast's credibility before being applied to each
        connected Tier 1 agent.

        Parameters
        ----------
        received_broadcasts
            List of InfluenceBroadcast objects received this step.

        Returns
        -------
        list[InfluenceDelta]
            One delta per connected Tier 1 agent, summing all
            broadcast effects.
        """
        if not received_broadcasts:
            return []

        # Aggregate the weighted influence from all broadcasts
        total_delta = 0.0
        for broadcast in received_broadcasts:
            weighted_signal = (
                broadcast.sentiment_delta
                * broadcast.credibility_score
                * self.amplification_factor
            )
            total_delta += weighted_signal

        # Clamp the combined delta
        total_delta = max(-1.0, min(1.0, total_delta))

        # Generate one InfluenceDelta per connected Tier 1 agent
        deltas: list[InfluenceDelta] = []
        for tid in self.connected_tier1_ids:
            deltas.append(
                InfluenceDelta(
                    target_agent_id=tid,
                    delta=total_delta,
                    source_type=f"tier2_{self.agent_type}",
                )
            )

        return deltas
