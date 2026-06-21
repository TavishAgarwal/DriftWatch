"""
domains/benefits.py — Benefits Eligibility domain for Driftwatch.

This is the original domain, refactored from case_oracle.py into the
DomainModule interface.  Logic is byte-for-byte identical to the
pre-refactor CaseOracle; only the class structure changed.

Scenario: AI caseworker evaluating citizens' eligibility for
government welfare benefits (housing, food, medical, childcare,
education) in an Indian administrative context.
"""

from __future__ import annotations

from typing import Any

from backend.simulation.domains.base import DomainModule


CATEGORIES = ["housing", "food", "medical", "childcare", "education"]
EMPLOYMENT_STATUSES = ["employed", "unemployed", "self_employed", "retired"]


class BenefitsEligibilityDomain(DomainModule):
    """Deterministic benefits-eligibility case generator.

    Ground-truth rules are simple, transparent, and model-free so they
    can serve as the objective standard the CaseworkerAgent is measured
    against.
    """

    domain_id = "benefits_eligibility"
    domain_name = "Benefits Eligibility"
    domain_description = "Government welfare benefits — housing, food, medical, childcare, education"
    reviewer_availability = 1.0  # no structural scarcity

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_thresholds = {
            "POVERTY_LINE_PER_CAPITA": 5_000,
            "MODERATE_THRESHOLD_PER_CAPITA": 12_000,
            "HIGH_INCOME_PER_CAPITA": 18_000,
            "MAX_PRIOR_BENEFITS_BEFORE_FLAG": 3,
            "SENIOR_AGE_THRESHOLD": 60,
        }

    # ── Ground truth ──────────────────────────────────────────
    def compute_ground_truth(self, case: dict[str, Any]) -> str:
        """Compute the objectively correct decision for a case.

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
        per_capita = case["income"] / max(1, case["household_size"])
        thresh = self._current_thresholds

        if case["disability_flag"]:
            return "approve"
        if per_capita < thresh["POVERTY_LINE_PER_CAPITA"]:
            return "approve"
        if case["prior_benefits_count"] > thresh["MAX_PRIOR_BENEFITS_BEFORE_FLAG"] and per_capita >= thresh["MODERATE_THRESHOLD_PER_CAPITA"]:
            return "flag"
        if case["age"] >= thresh["SENIOR_AGE_THRESHOLD"] and per_capita < thresh["MODERATE_THRESHOLD_PER_CAPITA"]:
            return "approve"
        if case["employment_status"] == "unemployed" and per_capita < thresh["MODERATE_THRESHOLD_PER_CAPITA"]:
            return "approve"
        if case["dependents_under_18"] >= 2 and per_capita < thresh["MODERATE_THRESHOLD_PER_CAPITA"]:
            return "approve"
        if per_capita >= thresh["HIGH_INCOME_PER_CAPITA"]:
            return "deny"
        if case["claimed_category"] == "medical" and per_capita < thresh["HIGH_INCOME_PER_CAPITA"]:
            return "approve"
        if per_capita < thresh["MODERATE_THRESHOLD_PER_CAPITA"]:
            return "approve"
        return "deny"

    # ── Shock mechanism ───────────────────────────────────────
    def check_and_apply_shock(self, timestep: int) -> dict | None:
        if self._shock_interval > 0 and timestep % self._shock_interval == 0 and timestep > 0:
            thresholds_to_shift = self._rng.sample(
                ["POVERTY_LINE_PER_CAPITA", "MODERATE_THRESHOLD_PER_CAPITA", "HIGH_INCOME_PER_CAPITA", "MAX_PRIOR_BENEFITS_BEFORE_FLAG"],
                k=self._rng.randint(2, 3)
            )
            old_thresholds = self._current_thresholds.copy()
            for key in thresholds_to_shift:
                direction = self._rng.choice([-1, 1])
                val = self._current_thresholds[key]
                if key == "MAX_PRIOR_BENEFITS_BEFORE_FLAG":
                    shift = max(1, int(val * self._shock_magnitude))
                    self._current_thresholds[key] = max(1, val + direction * shift)
                else:
                    self._current_thresholds[key] = int(val * (1.0 + direction * self._shock_magnitude))

            # Preserve threshold ordering
            self._current_thresholds["POVERTY_LINE_PER_CAPITA"] = min(
                self._current_thresholds["POVERTY_LINE_PER_CAPITA"],
                self._current_thresholds["MODERATE_THRESHOLD_PER_CAPITA"] - 1000
            )
            self._current_thresholds["MODERATE_THRESHOLD_PER_CAPITA"] = min(
                self._current_thresholds["MODERATE_THRESHOLD_PER_CAPITA"],
                self._current_thresholds["HIGH_INCOME_PER_CAPITA"] - 1000
            )

            shock_record = {
                "timestep": timestep,
                "old": old_thresholds,
                "new": self._current_thresholds.copy(),
            }
            self._shock_log.append(shock_record)
            return shock_record
        return None

    # ── Case generation ───────────────────────────────────────
    def generate_case(self, difficulty: float = 0.5) -> tuple[dict[str, Any], str]:
        difficulty = max(0.0, min(1.0, difficulty))
        rng = self._rng
        case_id = self._next_case_id()

        household_size = rng.randint(1, 8)
        age = rng.randint(18, 90)
        disability = rng.random() < 0.08
        prior_benefits = rng.randint(0, 6)
        dependents = rng.randint(0, min(6, household_size - 1)) if household_size > 1 else 0
        category = rng.choice(CATEGORIES)
        employment = rng.choice(EMPLOYMENT_STATUSES)

        if difficulty < 0.3:
            if rng.random() < 0.5:
                per_capita_target = rng.randint(1_000, 4_000)
            else:
                per_capita_target = rng.randint(20_000, 50_000)
        elif difficulty < 0.7:
            if rng.random() < 0.3:
                per_capita_target = rng.randint(1_000, 4_000)
            elif rng.random() < 0.5:
                per_capita_target = rng.randint(20_000, 50_000)
            else:
                threshold = rng.choice([
                    self._current_thresholds["POVERTY_LINE_PER_CAPITA"],
                    self._current_thresholds["MODERATE_THRESHOLD_PER_CAPITA"],
                    self._current_thresholds["HIGH_INCOME_PER_CAPITA"],
                ])
                per_capita_target = threshold + rng.randint(-2_000, 2_000)
        else:
            threshold = rng.choice([
                self._current_thresholds["POVERTY_LINE_PER_CAPITA"],
                self._current_thresholds["MODERATE_THRESHOLD_PER_CAPITA"],
                self._current_thresholds["HIGH_INCOME_PER_CAPITA"],
            ])
            per_capita_target = threshold + rng.randint(-1_500, 1_500)

        per_capita_target = max(500, per_capita_target)
        income = per_capita_target * household_size

        case = {
            "case_id": case_id,
            "income": income,
            "household_size": household_size,
            "claimed_category": category,
            "employment_status": employment,
            "disability_flag": disability,
            "prior_benefits_count": prior_benefits,
            "dependents_under_18": dependents,
            "age": age,
        }

        ground_truth = self.compute_ground_truth(case)
        return case, ground_truth
