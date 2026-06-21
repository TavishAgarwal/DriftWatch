"""
domains/base.py — Domain-agnostic interfaces for Driftwatch case generation.

Every simulation domain implements DomainModule, which provides:
  - generate_case(difficulty) → (case_dict, ground_truth_str)
  - compute_ground_truth(case_dict) → str
  - check_and_apply_shock(timestep) → dict | None
  - domain metadata (name, description, reviewer_availability)

This abstraction allows the simulation loop (driftwatch.py, oversight_logic.py)
to remain completely domain-agnostic while supporting pluggable scenarios.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Any


class DomainModule(ABC):
    """Abstract base for a Driftwatch simulation domain.

    Each concrete domain must define how cases are generated, how ground
    truth is evaluated, and how policy shocks mutate decision thresholds.

    Attributes
    ----------
    domain_id : str
        Machine-readable domain key (e.g. "benefits_eligibility").
    domain_name : str
        Human-readable display name.
    domain_description : str
        One-line context for the domain scenario.
    reviewer_availability : float
        Structural ceiling on review capacity (0.0–1.0).  Even if a
        citizen's ``review_probability`` is higher, actual review rate
        is clamped to this value.  Default 1.0 = no structural limit.
        The rural-healthcare domain overrides this to model genuine
        human-reviewer scarcity.
    """

    domain_id: str = "base"
    domain_name: str = "Base Domain"
    domain_description: str = ""
    reviewer_availability: float = 1.0  # no structural ceiling by default

    def __init__(
        self,
        seed: int = 42,
        cases_per_timestep: int = 1,
        shock_interval: int = 0,
        shock_magnitude: float = 0.30,
    ) -> None:
        self._rng = random.Random(seed)
        self._case_counter = 0
        self.cases_per_timestep = cases_per_timestep
        self._shock_interval = shock_interval
        self._shock_magnitude = shock_magnitude
        self._shock_log: list[dict] = []

    @abstractmethod
    def generate_case(self, difficulty: float = 0.5) -> tuple[dict[str, Any], str]:
        """Generate a single case and its ground-truth decision.

        Returns
        -------
        tuple[dict, str]
            (case_dict, ground_truth_decision)
            ground_truth_decision is one of "approve", "deny", "flag".
        """
        ...

    @abstractmethod
    def compute_ground_truth(self, case: dict[str, Any]) -> str:
        """Compute the objectively correct decision for a case dict.

        Returns one of "approve", "deny", or "flag".
        """
        ...

    @abstractmethod
    def check_and_apply_shock(self, timestep: int) -> dict | None:
        """Apply a policy shock at this timestep if one is scheduled.

        Returns a shock record dict if a shock occurred, None otherwise.
        Records are also appended to ``self._shock_log``.
        """
        ...

    def generate_batch(
        self, count: int | None = None, difficulty: float = 0.5
    ) -> list[tuple[dict[str, Any], str]]:
        """Generate a batch of cases for one timestep."""
        n = count or self.cases_per_timestep
        return [self.generate_case(difficulty) for _ in range(n)]

    def _next_case_id(self) -> str:
        self._case_counter += 1
        return f"CASE_{self._case_counter:06d}"
