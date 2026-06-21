"""
domains/microfinance.py — Micro-finance / MSME Credit Approval domain.

Scenario: AI caseworker evaluating micro-loan and MSME (Micro, Small &
Medium Enterprise) credit applications in the context of India's ONDC-era
digital commerce and lending push.  Small businesses apply for working-
capital or expansion loans; the oracle uses simple rule-based criteria
to determine creditworthiness.

Relevant policy context:
  - India's ONDC (Open Network for Digital Commerce) is driving digital
    formalization of small businesses, creating massive demand for
    automated credit scoring.
  - MUDRA loans (Micro Units Development and Refinance Agency) provide
    collateral-free loans up to ₹10 lakh for micro-enterprises.
  - AI-assisted credit decisions at scale are already being deployed by
    Indian fintechs (e.g., Lendingkart, Capital Float, NeoGrowth).
"""

from __future__ import annotations

from typing import Any

from backend.simulation.domains.base import DomainModule


BUSINESS_CATEGORIES = [
    "retail", "agriculture", "food_services", "textiles",
    "handicrafts", "transport", "digital_services",
]
COLLATERAL_TYPES = ["none", "inventory", "equipment", "property", "gold"]
LOAN_PURPOSES = ["working_capital", "expansion", "equipment", "emergency"]


class MicrofinanceDomain(DomainModule):
    """Deterministic micro-finance credit-approval case generator.

    Ground-truth rules determine approve / deny / flag based on
    simple financial ratios and risk indicators — no ML model involved.
    """

    domain_id = "microfinance"
    domain_name = "Micro-Finance / MSME Credit"
    domain_description = "Small business loan approval — India's ONDC-era digital lending"
    reviewer_availability = 1.0  # loan officers are generally available

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_thresholds = {
            "MAX_LOAN_AMOUNT": 500_000,          # ₹5 lakh cap for auto-approval
            "MIN_REVENUE_RATIO": 3.0,            # monthly revenue must be ≥ 3x EMI
            "MAX_DEFAULT_COUNT": 1,              # more than 1 prior default → flag
            "MIN_YEARS_IN_OPERATION": 1,         # must have been operating ≥ 1 year
            "COLLATERAL_COVERAGE_THRESHOLD": 0.5, # collateral must cover 50% of loan
        }

    def compute_ground_truth(self, case: dict[str, Any]) -> str:
        """Deterministic credit decision rules.

        Rules (first match wins):
        1. Prior defaults > MAX_DEFAULT_COUNT → deny
        2. Years in operation < MIN_YEARS_IN_OPERATION → flag (needs manual review)
        3. Requested amount > MAX_LOAN_AMOUNT with no collateral → deny
        4. Revenue ratio < MIN_REVENUE_RATIO → deny
        5. Collateral coverage < threshold AND amount > MAX_LOAN_AMOUNT → flag
        6. Revenue ratio ≥ MIN_REVENUE_RATIO AND low default → approve
        7. Otherwise → deny
        """
        thresh = self._current_thresholds
        monthly_revenue = case["monthly_revenue"]
        requested = case["requested_amount"]
        emi_estimate = requested / max(1, case["loan_term_months"])
        revenue_ratio = monthly_revenue / max(1, emi_estimate)
        collateral_coverage = case["collateral_value"] / max(1, requested)

        # Rule 1: Too many defaults
        if case["prior_defaults"] > thresh["MAX_DEFAULT_COUNT"]:
            return "deny"

        # Rule 2: New business — needs human underwriter
        if case["years_in_operation"] < thresh["MIN_YEARS_IN_OPERATION"]:
            return "flag"

        # Rule 3: Large unsecured loan
        if requested > thresh["MAX_LOAN_AMOUNT"] and case["collateral_type"] == "none":
            return "deny"

        # Rule 4: Can't afford the EMI
        if revenue_ratio < thresh["MIN_REVENUE_RATIO"]:
            return "deny"

        # Rule 5: Large loan with insufficient collateral
        if collateral_coverage < thresh["COLLATERAL_COVERAGE_THRESHOLD"] and requested > thresh["MAX_LOAN_AMOUNT"]:
            return "flag"

        # Rule 6: Good financials
        if revenue_ratio >= thresh["MIN_REVENUE_RATIO"] and case["prior_defaults"] <= thresh["MAX_DEFAULT_COUNT"]:
            return "approve"

        return "deny"

    def check_and_apply_shock(self, timestep: int) -> dict | None:
        """Shock: sudden tightening or loosening of credit policy.

        Simulates RBI (Reserve Bank of India) regulatory shifts, NBFC
        liquidity crunches, or fintech-driven credit expansion waves.
        """
        if self._shock_interval > 0 and timestep % self._shock_interval == 0 and timestep > 0:
            keys_to_shift = self._rng.sample(
                ["MAX_LOAN_AMOUNT", "MIN_REVENUE_RATIO", "MAX_DEFAULT_COUNT", "MIN_YEARS_IN_OPERATION"],
                k=self._rng.randint(2, 3),
            )
            old = self._current_thresholds.copy()
            for key in keys_to_shift:
                direction = self._rng.choice([-1, 1])
                val = self._current_thresholds[key]
                if isinstance(val, float):
                    self._current_thresholds[key] = max(0.5, val * (1.0 + direction * self._shock_magnitude))
                else:
                    self._current_thresholds[key] = max(1, int(val * (1.0 + direction * self._shock_magnitude)))

            shock_record = {"timestep": timestep, "old": old, "new": self._current_thresholds.copy()}
            self._shock_log.append(shock_record)
            return shock_record
        return None

    def generate_case(self, difficulty: float = 0.5) -> tuple[dict[str, Any], str]:
        difficulty = max(0.0, min(1.0, difficulty))
        rng = self._rng
        case_id = self._next_case_id()

        business_category = rng.choice(BUSINESS_CATEGORIES)
        years_in_operation = rng.randint(0, 15)
        prior_defaults = rng.choices([0, 1, 2, 3], weights=[60, 20, 12, 8])[0]
        collateral_type = rng.choice(COLLATERAL_TYPES)
        loan_purpose = rng.choice(LOAN_PURPOSES)
        loan_term_months = rng.choice([6, 12, 18, 24, 36])

        # Revenue and loan amount depend on difficulty
        if difficulty < 0.3:
            # Easy: clearly affordable or clearly unaffordable
            if rng.random() < 0.5:
                monthly_revenue = rng.randint(80_000, 200_000)
                requested_amount = rng.randint(50_000, 200_000)
            else:
                monthly_revenue = rng.randint(5_000, 15_000)
                requested_amount = rng.randint(500_000, 1_000_000)
        elif difficulty < 0.7:
            monthly_revenue = rng.randint(20_000, 120_000)
            requested_amount = rng.randint(100_000, 600_000)
        else:
            # Hard: cluster near decision thresholds
            emi_target = rng.randint(5_000, 30_000)
            monthly_revenue = int(emi_target * self._current_thresholds["MIN_REVENUE_RATIO"] * (1.0 + rng.uniform(-0.3, 0.3)))
            requested_amount = emi_target * loan_term_months

        # Collateral value
        if collateral_type == "none":
            collateral_value = 0
        elif collateral_type == "property":
            collateral_value = rng.randint(200_000, 1_000_000)
        elif collateral_type == "gold":
            collateral_value = rng.randint(50_000, 300_000)
        else:
            collateral_value = rng.randint(20_000, 150_000)

        case = {
            "case_id": case_id,
            "business_category": business_category,
            "years_in_operation": years_in_operation,
            "monthly_revenue": max(1_000, monthly_revenue),
            "requested_amount": max(10_000, requested_amount),
            "loan_term_months": loan_term_months,
            "prior_defaults": prior_defaults,
            "collateral_type": collateral_type,
            "collateral_value": collateral_value,
            "loan_purpose": loan_purpose,
        }

        ground_truth = self.compute_ground_truth(case)
        return case, ground_truth
