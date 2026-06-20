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
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

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
            async with httpx.AsyncClient(timeout=300.0) as client:
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
            async with httpx.AsyncClient(timeout=300.0) as client:
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

    Usage
    -----
        agent = CaseworkerAgent("openai")
        decision = await agent.decide(case_dict)
    """

    def __init__(self, backend_name: str | None = None) -> None:
        self.backend = get_caseworker_backend(backend_name)

    @property
    def backend_name(self) -> str:
        return self.backend.name

    @property
    def fallback_active(self) -> bool:
        """True if the configured backend has fallen back to rule-based."""
        return self.backend.fallback_active

    async def decide(self, case: dict[str, Any]) -> Decision:
        return await self.backend.decide(case)

