"""
case_oracle.py — Deterministic ground-truth case generator for Driftwatch.

Produces synthetic administrative cases (benefits-eligibility scenarios)
with a computed ground-truth correct decision.  The oracle uses fixed,
simple rules — NO model calls — so it can serve as the objective
standard the CaseworkerAgent is measured against.

Usage
-----
    oracle = CaseOracle(seed=42)
    case, ground_truth = oracle.generate_case(difficulty=0.5)
    # ground_truth is "approve", "deny", or "flag"
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


# ═════════════════════════════════════════════════════════════
# Case dataclass
# ═════════════════════════════════════════════════════════════
@dataclass(frozen=True, slots=True)
class Case:
    """A synthetic administrative benefits-eligibility case.

    All fields are structured and deterministic — no free text
    is needed for ground-truth evaluation.
    """
    case_id: str
    income: int               # monthly income in ₹
    household_size: int       # 1–8
    claimed_category: str     # housing | food | medical | childcare | education
    employment_status: str    # employed | unemployed | self_employed | retired
    disability_flag: bool
    prior_benefits_count: int # 0–10
    dependents_under_18: int  # 0–6
    age: int                  # 18–90

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "income": self.income,
            "household_size": self.household_size,
            "claimed_category": self.claimed_category,
            "employment_status": self.employment_status,
            "disability_flag": self.disability_flag,
            "prior_benefits_count": self.prior_benefits_count,
            "dependents_under_18": self.dependents_under_18,
            "age": self.age,
        }


# ═════════════════════════════════════════════════════════════
# Ground-truth rules — deterministic, no model calls
# ═════════════════════════════════════════════════════════════

# Eligibility thresholds (per-capita monthly income in ₹)
POVERTY_LINE_PER_CAPITA = 5_000       # below this → always eligible
MODERATE_THRESHOLD_PER_CAPITA = 12_000 # below this → eligible with conditions
HIGH_INCOME_PER_CAPITA = 18_000        # above this → ineligible
MAX_PRIOR_BENEFITS_BEFORE_FLAG = 3     # more than this → flag for review
SENIOR_AGE_THRESHOLD = 60


def compute_ground_truth(case: Case) -> str:
    """Compute the objectively correct decision for a case.

    Returns
    -------
    str
        One of ``"approve"``, ``"deny"``, or ``"flag"``.

    Rules (applied in order, first match wins):
    1. Disability flag → approve
    2. Per-capita income < poverty line → approve
    3. Prior benefits > 3 AND per-capita income > moderate → flag
    4. Senior (≥60) AND per-capita income < moderate → approve
    5. Unemployed AND per-capita income < moderate → approve
    6. Dependents ≥ 2 AND per-capita income < moderate → approve
    7. Per-capita income > high income threshold → deny
    8. Medical category AND per-capita income < high → approve
    9. Per-capita income < moderate → approve
    10. Otherwise → deny
    """
    per_capita = case.income / max(1, case.household_size)

    # Rule 1: Disability always approved
    if case.disability_flag:
        return "approve"

    # Rule 2: Extreme poverty
    if per_capita < POVERTY_LINE_PER_CAPITA:
        return "approve"

    # Rule 3: Excessive prior benefits with moderate+ income
    if case.prior_benefits_count > MAX_PRIOR_BENEFITS_BEFORE_FLAG and per_capita >= MODERATE_THRESHOLD_PER_CAPITA:
        return "flag"

    # Rule 4: Senior citizen with limited income
    if case.age >= SENIOR_AGE_THRESHOLD and per_capita < MODERATE_THRESHOLD_PER_CAPITA:
        return "approve"

    # Rule 5: Unemployed with limited income
    if case.employment_status == "unemployed" and per_capita < MODERATE_THRESHOLD_PER_CAPITA:
        return "approve"

    # Rule 6: Multiple dependents with limited income
    if case.dependents_under_18 >= 2 and per_capita < MODERATE_THRESHOLD_PER_CAPITA:
        return "approve"

    # Rule 7: High income
    if per_capita >= HIGH_INCOME_PER_CAPITA:
        return "deny"

    # Rule 8: Medical category with non-high income
    if case.claimed_category == "medical" and per_capita < HIGH_INCOME_PER_CAPITA:
        return "approve"

    # Rule 9: Below moderate threshold
    if per_capita < MODERATE_THRESHOLD_PER_CAPITA:
        return "approve"

    # Rule 10: Default deny
    return "deny"


# ═════════════════════════════════════════════════════════════
# CaseOracle — generates cases with configurable difficulty
# ═════════════════════════════════════════════════════════════

CATEGORIES = ["housing", "food", "medical", "childcare", "education"]
EMPLOYMENT_STATUSES = ["employed", "unemployed", "self_employed", "retired"]


class CaseOracle:
    """Deterministic case generator with configurable difficulty.

    Parameters
    ----------
    seed : int
        Random seed for reproducibility.
    cases_per_timestep : int
        Number of cases to generate per timestep (default 1).
    """

    def __init__(self, seed: int = 42, cases_per_timestep: int = 1) -> None:
        self._rng = random.Random(seed)
        self._case_counter = 0
        self.cases_per_timestep = cases_per_timestep

    def generate_case(self, difficulty: float = 0.5) -> tuple[Case, str]:
        """Generate a single case with ground-truth decision.

        Parameters
        ----------
        difficulty : float
            0.0 = trivially easy (clear approve/deny), 1.0 = maximally
            ambiguous (income clustered near decision boundaries).

        Returns
        -------
        tuple[Case, str]
            (case, ground_truth_decision)
        """
        difficulty = max(0.0, min(1.0, difficulty))
        rng = self._rng
        self._case_counter += 1
        case_id = f"CASE_{self._case_counter:06d}"

        household_size = rng.randint(1, 8)
        age = rng.randint(18, 90)
        disability = rng.random() < 0.08  # ~8% disability rate
        prior_benefits = rng.randint(0, 6)
        dependents = rng.randint(0, min(6, household_size - 1)) if household_size > 1 else 0
        category = rng.choice(CATEGORIES)
        employment = rng.choice(EMPLOYMENT_STATUSES)

        # Income generation: at low difficulty, income is clearly high or low;
        # at high difficulty, income clusters near the decision boundaries.
        if difficulty < 0.3:
            # Easy: clearly eligible or clearly ineligible
            if rng.random() < 0.5:
                per_capita_target = rng.randint(1_000, 4_000)  # clearly below poverty
            else:
                per_capita_target = rng.randint(20_000, 50_000)  # clearly above high
        elif difficulty < 0.7:
            # Medium: mix of clear and borderline
            if rng.random() < 0.3:
                per_capita_target = rng.randint(1_000, 4_000)
            elif rng.random() < 0.5:
                per_capita_target = rng.randint(20_000, 50_000)
            else:
                # Borderline — near thresholds
                threshold = rng.choice([
                    POVERTY_LINE_PER_CAPITA,
                    MODERATE_THRESHOLD_PER_CAPITA,
                    HIGH_INCOME_PER_CAPITA,
                ])
                per_capita_target = threshold + rng.randint(-2_000, 2_000)
        else:
            # Hard: most cases near decision boundaries
            threshold = rng.choice([
                POVERTY_LINE_PER_CAPITA,
                MODERATE_THRESHOLD_PER_CAPITA,
                HIGH_INCOME_PER_CAPITA,
            ])
            per_capita_target = threshold + rng.randint(-1_500, 1_500)

        per_capita_target = max(500, per_capita_target)
        income = per_capita_target * household_size

        case = Case(
            case_id=case_id,
            income=income,
            household_size=household_size,
            claimed_category=category,
            employment_status=employment,
            disability_flag=disability,
            prior_benefits_count=prior_benefits,
            dependents_under_18=dependents,
            age=age,
        )

        ground_truth = compute_ground_truth(case)
        return case, ground_truth

    def generate_batch(
        self, count: int | None = None, difficulty: float = 0.5
    ) -> list[tuple[Case, str]]:
        """Generate a batch of cases for one timestep.

        Parameters
        ----------
        count : int | None
            Number of cases. If None, uses ``self.cases_per_timestep``.
        difficulty : float
            Difficulty parameter passed to each case generation.
        """
        n = count or self.cases_per_timestep
        return [self.generate_case(difficulty) for _ in range(n)]
