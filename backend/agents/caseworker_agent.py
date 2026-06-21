"""
caseworker_agent.py — AI Caseworker for Driftwatch oversight-decay simulation.

Implements a pluggable model backend interface so the same caseworker
decision logic can be run against multiple model tiers:
  1. OpenAI GPT-4o (large closed model)
  2. Ollama API — Llama 3.1 8B (open-source via API)
  3. Ollama Local — Llama 3.1 quantized GGUF (on-device)

Each backend receives a structured administrative case and returns
an approve/deny/flag decision with reasoning.  The *same prompt* is
used across all backends so the only variable is the model.

Config
------
    CASEWORKER_MODEL_BACKEND  env var — one of:
        "openai"       → GPT-4o
        "ollama_api"   → Llama 3.1 8B via Ollama API
        "ollama_local" → Llama 3.1 quantized via local Ollama
        "rule_based"   → deterministic fallback (no model call)
"""

from __future__ import annotations

import json
import logging
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from backend.simulation.backend_config import get_backend_profile, BackendProfile

logger = logging.getLogger("driftwatch.caseworker")

# ---------------------------------------------------------------------------
# Decision dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Decision:
    """Output of a caseworker decision on an administrative case.

    Attributes
    ----------
    outcome : str
        One of ``"approve"``, ``"deny"``, ``"flag"``.
    reasoning : str
        Free-text explanation from the model (or rule engine).
    confidence : float
        Model's self-reported confidence, 0.0–1.0.
    fallback_used : bool
        True if this decision was produced by the rule-based fallback
        instead of the intended model backend.
    """
    outcome: str        # "approve" | "deny" | "flag"
    reasoning: str
    confidence: float
    fallback_used: bool = False

    def __post_init__(self) -> None:
        valid = {"approve", "deny", "flag"}
        if self.outcome not in valid:
            object.__setattr__(self, "outcome", "flag")
        if not (0.0 <= self.confidence <= 1.0):
            object.__setattr__(
                self, "confidence", max(0.0, min(1.0, self.confidence))
            )


# ---------------------------------------------------------------------------
# Abstract backend interface
# ---------------------------------------------------------------------------
class ModelBackend(ABC):
    """Abstract interface for a caseworker model backend."""

    # Tracks whether this backend has fallen back to rule-based
    _fallback_active: bool = False

    @property
    def fallback_active(self) -> bool:
        """True if this backend is using rule-based fallback."""
        return self._fallback_active

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name (shown in metrics/UI)."""

    @abstractmethod
    async def decide(self, case: dict[str, Any]) -> Decision:
        """Make a decision on a structured administrative case.

        Parameters
        ----------
        case : dict
            Structured case with fields like ``income``,
            ``household_size``, ``claimed_category``, etc.

        Returns
        -------
        Decision
        """


# ---------------------------------------------------------------------------
# Shared prompt builder
# ---------------------------------------------------------------------------
def _build_caseworker_prompt(case: dict[str, Any]) -> str:
    """Build the identical prompt used by all model backends."""
    return (
        "You are an AI administrative caseworker reviewing a benefits "
        "eligibility application. Based on the case details below, decide "
        "whether to APPROVE, DENY, or FLAG the application for human review.\n\n"
        f"CASE DETAILS:\n"
        f"  Applicant income (monthly): ₹{case.get('income', 0):,}\n"
        f"  Household size: {case.get('household_size', 1)}\n"
        f"  Claimed benefit category: {case.get('claimed_category', 'unknown')}\n"
        f"  Employment status: {case.get('employment_status', 'unknown')}\n"
        f"  Disability flag: {case.get('disability_flag', False)}\n"
        f"  Prior benefits received: {case.get('prior_benefits_count', 0)}\n"
        f"  Dependents under 18: {case.get('dependents_under_18', 0)}\n"
        f"  Applicant age: {case.get('age', 30)}\n\n"
        "Respond ONLY with a JSON object containing exactly these keys:\n"
        '  "outcome": one of "approve", "deny", "flag"\n'
        '  "reasoning": your explanation (max 200 chars)\n'
        '  "confidence": float between 0.0 and 1.0\n'
    )


def _parse_model_response(raw: str) -> Decision:
    """Parse a JSON response from any model backend into a Decision."""
    data = json.loads(raw)
    return Decision(
        outcome=str(data.get("outcome", "flag")).lower().strip(),
        reasoning=str(data.get("reasoning", ""))[:200],
        confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
    )


# ---------------------------------------------------------------------------
# Backend 1: OpenAI GPT-4o
# ---------------------------------------------------------------------------
class OpenAIBackend(ModelBackend):
    """Large closed model backend using OpenAI GPT-4o."""

    @property
    def name(self) -> str:
        return "gpt-4o (closed)"

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning("openai package not installed — OpenAI backend unavailable")
            return None
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set — OpenAI backend unavailable")
            return None
        self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    async def decide(self, case: dict[str, Any]) -> Decision:
        client = self._get_client()
        if client is None:
            self._fallback_active = True
            decision = _rule_based_decide(case)
            return Decision(decision.outcome, decision.reasoning, decision.confidence, fallback_used=True)

        prompt = _build_caseworker_prompt(case)
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                temperature=0.2,
                seed=42,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a fair, careful administrative benefits caseworker."},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = response.choices[0].message.content or "{}"
            return _parse_model_response(raw)
        except Exception as exc:
            logger.warning("OpenAI caseworker error: %s — falling back to rules", exc)
            self._fallback_active = True
            decision = _rule_based_decide(case)
            return Decision(decision.outcome, decision.reasoning, decision.confidence, fallback_used=True)


# ---------------------------------------------------------------------------
# Backend 2: Ollama API (Llama 3.1 8B)
# ---------------------------------------------------------------------------
class OllamaAPIBackend(ModelBackend):
    """Open-source model via Ollama API (Llama 3.1 8B)."""

    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_API_MODEL", "llama3.1:8b")

    @property
    def name(self) -> str:
        return f"llama-3.1-8b (open-source API)"

    async def decide(self, case: dict[str, Any]) -> Decision:
        import httpx

        prompt = _build_caseworker_prompt(case)
        payload = {
            "model": self.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.OLLAMA_BASE_URL}/api/generate", json=payload
                )
                resp.raise_for_status()
            body = resp.json()
            raw = body.get("response", "{}")
            return _parse_model_response(raw)
        except Exception as exc:
            logger.warning("Ollama API caseworker error: %r — falling back to rules", exc)
            self._fallback_active = True
            decision = _rule_based_decide(case)
            return Decision(decision.outcome, decision.reasoning, decision.confidence, fallback_used=True)


# ---------------------------------------------------------------------------
# Backend 3: Ollama Local (quantized GGUF)
# ---------------------------------------------------------------------------
class OllamaLocalBackend(ModelBackend):
    """Local/quantized model via Ollama (e.g. Llama 3.1 Q4_K_M GGUF).

    Setup instructions:
        1. Install Ollama: https://ollama.com/download
        2. Pull the quantized model:
           ollama pull llama3.1:8b-instruct-q4_K_M
        3. Ollama runs on localhost:11434 by default.
    """

    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_LOCAL_MODEL", "llama3.1:8b-instruct-q4_K_M")

    @property
    def name(self) -> str:
        return f"llama-3.1-q4 (local/quantized)"

    async def decide(self, case: dict[str, Any]) -> Decision:
        import httpx

        prompt = _build_caseworker_prompt(case)
        payload = {
            "model": self.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.OLLAMA_BASE_URL}/api/generate", json=payload
                )
                resp.raise_for_status()
            body = resp.json()
            raw = body.get("response", "{}")
            return _parse_model_response(raw)
        except Exception as exc:
            logger.warning("Ollama local caseworker error: %r — falling back to rules", exc)
            self._fallback_active = True
            decision = _rule_based_decide(case)
            return Decision(decision.outcome, decision.reasoning, decision.confidence, fallback_used=True)


# ---------------------------------------------------------------------------
# Rule-based fallback (deterministic, no model call)
# ---------------------------------------------------------------------------
class RuleBasedBackend(ModelBackend):
    """Deterministic rule-based backend for testing without any LLM."""

    @property
    def name(self) -> str:
        return "rule-based (fallback)"

    async def decide(self, case: dict[str, Any]) -> Decision:
        return _rule_based_decide(case)


def _rule_based_decide(case: dict[str, Any]) -> Decision:
    """Deterministic rule-based decision — mirrors the oracle logic
    but with slight noise to simulate a non-perfect model.

    This intentionally introduces ~15% error rate to make the
    oversight simulation meaningful even without a real model.
    """
    income = case.get("income", 0)
    household_size = max(1, case.get("household_size", 1))
    category = case.get("claimed_category", "general")
    disability = case.get("disability_flag", False)
    prior = case.get("prior_benefits_count", 0)
    age = case.get("age", 30)

    per_capita = income / household_size

    # Disability always approved
    if disability:
        return Decision("approve", "Disability flag present — auto-approve", 0.95)

    # High income → deny
    if per_capita > 18_000:
        return Decision("deny", f"Per-capita income ₹{per_capita:,.0f} exceeds threshold", 0.85)

    # Very low income → approve
    if per_capita < 6_000:
        return Decision("approve", f"Per-capita income ₹{per_capita:,.0f} below poverty line", 0.90)

    # Many prior benefits → flag
    if prior > 3:
        return Decision("flag", f"Prior benefits count ({prior}) exceeds review threshold", 0.70)

    # Senior citizen with low income → approve
    if age >= 60 and per_capita < 12_000:
        return Decision("approve", "Senior citizen with limited income", 0.80)

    # Ambiguous middle range — this is where errors happen
    if per_capita < 12_000:
        return Decision("approve", "Income below moderate threshold", 0.60)
    else:
        return Decision("deny", "Income above moderate threshold", 0.55)


# ---------------------------------------------------------------------------
# Factory: select backend from config
# ---------------------------------------------------------------------------
_BACKENDS: dict[str, type[ModelBackend]] = {
    "openai": OpenAIBackend,
    "ollama_api": OllamaAPIBackend,
    "ollama_local": OllamaLocalBackend,
    "ollama_local_fp16": OllamaLocalBackend,
    "ollama_local_int8": OllamaLocalBackend,
    "ollama_local_int4": OllamaLocalBackend,
    "rule_based": RuleBasedBackend,
}


def get_caseworker_backend(backend_name: str | None = None) -> ModelBackend:
    """Return the configured caseworker model backend.

    Parameters
    ----------
    backend_name : str | None
        Override backend name. If None, reads from
        ``CASEWORKER_MODEL_BACKEND`` env var (default ``"rule_based"``).
    """
    name = backend_name or os.environ.get("CASEWORKER_MODEL_BACKEND", "rule_based")
    cls = _BACKENDS.get(name.lower().strip())
    if cls is None:
        logger.warning(
            "Unknown caseworker backend '%s' — falling back to rule_based", name
        )
        cls = RuleBasedBackend
    return cls()


# ---------------------------------------------------------------------------
# CaseworkerAgent — high-level wrapper
# ---------------------------------------------------------------------------
class CaseworkerAgent:
    """AI Caseworker that makes administrative decisions using a
    pluggable model backend.

    Phase 3 additions:
      - explanation_style: "terse" or "detailed"
      - confidence_calibrated: True (states uncertainty when warranted)
        or False (always sounds equally confident)

    Usage
    -----
        agent = CaseworkerAgent("openai")
        decision = await agent.decide(case_dict)
    """

    def __init__(
        self,
        backend_name: str | None = None,
        quantization: str = "none",
        seed: int = 42,
        explanation_style: str = "detailed",
        confidence_calibrated: bool = True,
        live_backend: bool = False,
    ) -> None:
        self.backend = get_caseworker_backend(backend_name)
        # Handle cases where backend_name encodes quantization (e.g., ollama_local_int4)
        b_name = backend_name or "rule_based"
        if b_name.startswith("ollama_local_"):
            q_part = b_name.split("_")[-1].upper()
            quant = q_part
            base_backend = "ollama_local"
        else:
            quant = quantization
            base_backend = b_name

        self._profile = get_backend_profile(base_backend, quant)
        self._rng = random.Random(seed)
        self.burst_remaining = 0
        # Phase 3: explainability settings
        self.explanation_style = explanation_style
        self.confidence_calibrated = confidence_calibrated
        # Full population simulations must be reproducible and runnable without
        # provider credentials.  Live adapters remain available through decide()
        # when explicitly requested, while the simulation evaluates degradation
        # against the domain oracle's known ground truth.
        self.live_backend = live_backend

    @property
    def backend_name(self) -> str:
        return self._profile.name

    @property
    def in_burst(self) -> bool:
        return self.burst_remaining > 0

    def step_burst(self) -> bool:
        """Advance the burst state machine by one timestep.
        Returns True if in burst this timestep.
        """
        if self.burst_remaining > 0:
            self.burst_remaining -= 1
            return True
        else:
            if self._rng.random() < self._profile.burst_probability:
                self.burst_remaining = self._rng.randint(*self._profile.burst_duration_range)
                if self.burst_remaining > 0:
                    self.burst_remaining -= 1 # count current step as 1
                    return True
        return False

    @property
    def fallback_active(self) -> bool:
        """True if the configured backend has fallen back to rule-based."""
        return self.backend.fallback_active

    async def decide(self, case: dict[str, Any]) -> Decision:
        return await self.backend.decide(case)

    async def make_degraded_decision(self, case: dict[str, Any], ground_truth: str) -> tuple[Decision, dict]:
        """Make a decision with quantization-specific errors injected.

        Phase 3: Also returns explanation_style and confidence_calibrated
        in metadata, and adjusts confidence reporting based on calibration
        setting.
        """
        if self.live_backend:
            decision = await self.decide(case)
        else:
            decision = Decision(
                outcome=ground_truth,
                reasoning="Correct decision before modeled degradation",
                confidence=0.90,
            )
        in_burst = self.in_burst

        # Calculate error probabilities
        if in_burst:
            p_error = self._profile.burst_error_rate
        else:
            p_error = self._profile.base_error_rate

        error_injected = False
        burst_error = False

        if self._rng.random() < p_error:
            # Inject an error by picking a wrong outcome
            possible_outcomes = ["approve", "deny", "flag"]
            possible_outcomes.remove(ground_truth)
            wrong_outcome = self._rng.choice(possible_outcomes)

            error_injected = True
            burst_error = in_burst

            if in_burst:
                # Highly confident error
                conf = self._rng.uniform(self._profile.burst_confidence_floor, 1.0)
                reasoning = f"Confident override ({wrong_outcome})"
            else:
                # Normal low-confidence error
                conf = self._rng.uniform(0.4, 0.7)
                reasoning = f"Marginal decision ({wrong_outcome})"

            # Phase 3: Uncalibrated confidence makes errors HARDER to spot
            # because the model sounds just as confident on wrong answers.
            # When calibrated, errors have lower stated confidence.
            if not self.confidence_calibrated:
                # Override: always report high confidence even on errors
                conf = self._rng.uniform(0.85, 0.98)

            decision = Decision(
                outcome=wrong_outcome,
                reasoning=reasoning,
                confidence=conf
            )
        else:
            # Correct decision — calibration affects confidence reporting
            if not self.confidence_calibrated:
                # Always high confidence even when it shouldn't be
                decision = Decision(
                    outcome=decision.outcome,
                    reasoning=decision.reasoning,
                    confidence=self._rng.uniform(0.88, 0.99),
                    fallback_used=decision.fallback_used,
                )

        # Phase 3: Terse explanations strip reasoning
        if self.explanation_style == "terse":
            decision = Decision(
                outcome=decision.outcome,
                reasoning=decision.reasoning[:40] + "..." if len(decision.reasoning) > 40 else decision.reasoning,
                confidence=decision.confidence,
                fallback_used=decision.fallback_used,
            )

        metadata = {
            "in_burst": in_burst,
            "error_injected": error_injected,
            "burst_error": burst_error,
            "explanation_style": self.explanation_style,
            "confidence_calibrated": self.confidence_calibrated,
            "fallback_used": decision.fallback_used,
        }
        return decision, metadata
