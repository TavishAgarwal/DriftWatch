"""
domains/healthcare.py — Rural Healthcare Triage domain for Driftwatch.

Scenario: On-device AI diagnostic/triage assistant operating in rural
areas where human doctor availability is structurally scarce.  The AI
triages patients into home-care, specialist referral, or immediate
admission.

KEY DESIGN DECISION — reviewer_availability ceiling:
  This domain sets reviewer_availability = 0.30, meaning that even
  if a citizen's review_probability is 0.90 (they *want* to review),
  only 30% of decisions can actually be reviewed because there simply
  aren't enough doctors.  This is a STRUCTURAL constraint distinct
  from the behavioral trust-decay mechanic:
    - review_probability = citizen's WILLINGNESS to review
    - reviewer_availability = system's CAPACITY to review
    - actual_review = min(review_probability, reviewer_availability)

  This models the reality that in rural India, doctor-to-patient
  ratios can be as low as 1:10,000 (WHO recommends 1:1,000), so
  the AI's decisions go unreviewed not because people trust it too
  much, but because there literally isn't a human available to check.

Relevant policy context:
  - India has ~1 doctor per 1,511 people (national average), but in
    rural areas this drops to 1:10,000+
  - NITI Aayog has promoted AI-assisted diagnostics (e.g. Google's
    retinal screening, Wadhwani AI's TB screening) specifically for
    areas with low doctor density
  - The National Digital Health Mission (ABDM) is building rails for
    AI triage at Primary Health Centres (PHCs)
"""

from __future__ import annotations

from typing import Any

from backend.simulation.domains.base import DomainModule


SYMPTOM_CATEGORIES = [
    "respiratory", "gastrointestinal", "cardiovascular",
    "neurological", "musculoskeletal", "dermatological",
    "fever_infection", "maternal",
]
RISK_CATEGORIES = ["low", "moderate", "high", "critical"]


class HealthcareTriageDomain(DomainModule):
    """Deterministic rural healthcare triage case generator.

    Ground-truth rules determine triage decisions based on symptom
    severity, vital signs, risk factors, and chronicity — no ML model.

    Outcomes map to the standard approve/deny/flag triple:
      - "approve"  →  triage_home (safe to manage at home)
      - "flag"     →  refer_to_specialist (needs specialist consultation)
      - "deny"     →  admit_immediately (override AI, escalate urgently)

    NOTE: reviewer_availability is set to 0.30 to model genuine
    scarcity of human doctors for review, NOT trust decay.
    """

    domain_id = "healthcare_triage"
    domain_name = "Rural Healthcare Triage"
    domain_description = "On-device diagnostic triage — structurally scarce human reviewers"

    # STRUCTURAL CONSTRAINT: Only 30% of decisions CAN be reviewed,
    # regardless of citizens' willingness. This is the critical
    # distinguishing mechanic of this domain.
    reviewer_availability = 0.30
    model_error_multiplier = 1.10
    latency_multiplier = 0.80

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_thresholds = {
            "CRITICAL_SEVERITY_THRESHOLD": 8,   # severity ≥ 8 → admit
            "HIGH_RISK_VITALS_THRESHOLD": 7,    # vital risk ≥ 7 → refer
            "MODERATE_SEVERITY_THRESHOLD": 5,   # severity ≥ 5 → refer
            "CHRONIC_CONDITION_ESCALATION": True, # chronic + moderate → refer
            "DAYS_SYMPTOMATIC_ESCALATION": 7,    # > 7 days → escalate
            "ELDERLY_AGE_THRESHOLD": 65,          # elderly patients get lower bar
        }

    def compute_ground_truth(self, case: dict[str, Any]) -> str:
        """Deterministic triage rules.

        Rules (first match wins):
        1. Severity ≥ CRITICAL → deny (admit immediately)
        2. Vital risk ≥ HIGH_RISK → deny (admit immediately)
        3. Elderly + severity ≥ MODERATE → flag (refer to specialist)
        4. Chronic condition + severity ≥ MODERATE → flag (refer)
        5. Symptomatic > DAYS_ESCALATION + severity ≥ MODERATE → flag
        6. Severity ≥ MODERATE → flag (refer to specialist)
        7. Maternal category → flag (always refer for safety)
        8. Otherwise → approve (triage home)
        """
        thresh = self._current_thresholds
        severity = case["symptom_severity"]
        vitals = case["vital_risk_score"]

        # Rule 1: Critical severity — immediate admission
        if severity >= thresh["CRITICAL_SEVERITY_THRESHOLD"]:
            return "deny"

        # Rule 2: Dangerous vital signs
        if vitals >= thresh["HIGH_RISK_VITALS_THRESHOLD"]:
            return "deny"

        # Rule 3: Elderly with moderate symptoms
        if case["age"] >= thresh["ELDERLY_AGE_THRESHOLD"] and severity >= thresh["MODERATE_SEVERITY_THRESHOLD"]:
            return "flag"

        # Rule 4: Chronic condition with moderate symptoms
        if case["chronic_condition"] and thresh["CHRONIC_CONDITION_ESCALATION"] and severity >= thresh["MODERATE_SEVERITY_THRESHOLD"]:
            return "flag"

        # Rule 5: Prolonged symptoms
        if case["days_symptomatic"] > thresh["DAYS_SYMPTOMATIC_ESCALATION"] and severity >= thresh["MODERATE_SEVERITY_THRESHOLD"]:
            return "flag"

        # Rule 6: Moderate severity
        if severity >= thresh["MODERATE_SEVERITY_THRESHOLD"]:
            return "flag"

        # Rule 7: Maternal — always refer for safety
        if case["symptom_category"] == "maternal":
            return "flag"

        # Rule 8: Low severity, stable vitals
        return "approve"

    def check_and_apply_shock(self, timestep: int) -> dict | None:
        """Shock: sudden change in triage protocol.

        Simulates WHO guideline updates, disease outbreak re-classification,
        or seasonal epidemic responses (e.g., monsoon-season dengue protocol
        shifts triage thresholds dramatically).
        """
        if self._shock_interval > 0 and timestep % self._shock_interval == 0 and timestep > 0:
            keys_to_shift = self._rng.sample(
                ["CRITICAL_SEVERITY_THRESHOLD", "HIGH_RISK_VITALS_THRESHOLD",
                 "MODERATE_SEVERITY_THRESHOLD", "DAYS_SYMPTOMATIC_ESCALATION"],
                k=self._rng.randint(2, 3),
            )
            old = self._current_thresholds.copy()
            for key in keys_to_shift:
                direction = self._rng.choice([-1, 1])
                val = self._current_thresholds[key]
                if isinstance(val, int):
                    shift = max(1, int(val * self._shock_magnitude))
                    self._current_thresholds[key] = max(1, val + direction * shift)

            shock_record = {"timestep": timestep, "old": old, "new": self._current_thresholds.copy()}
            self._shock_log.append(shock_record)
            return shock_record
        return None

    def generate_case(self, difficulty: float = 0.5) -> tuple[dict[str, Any], str]:
        difficulty = max(0.0, min(1.0, difficulty))
        rng = self._rng
        case_id = self._next_case_id()

        age = rng.randint(0, 95)  # includes children and elderly
        symptom_category = rng.choice(SYMPTOM_CATEGORIES)
        chronic_condition = rng.random() < 0.25  # 25% have chronic conditions
        days_symptomatic = rng.randint(1, 21)

        # Severity and vital risk depend on difficulty
        if difficulty < 0.3:
            # Easy: clearly low or clearly critical
            if rng.random() < 0.5:
                symptom_severity = rng.randint(1, 3)
                vital_risk_score = rng.randint(1, 3)
            else:
                symptom_severity = rng.randint(8, 10)
                vital_risk_score = rng.randint(7, 10)
        elif difficulty < 0.7:
            symptom_severity = rng.randint(2, 8)
            vital_risk_score = rng.randint(2, 7)
        else:
            # Hard: cluster near decision thresholds
            target = rng.choice([
                self._current_thresholds["MODERATE_SEVERITY_THRESHOLD"],
                self._current_thresholds["CRITICAL_SEVERITY_THRESHOLD"],
            ])
            symptom_severity = max(1, min(10, target + rng.randint(-1, 1)))
            vital_risk_score = max(1, min(10, rng.randint(
                max(1, self._current_thresholds["HIGH_RISK_VITALS_THRESHOLD"] - 2),
                min(10, self._current_thresholds["HIGH_RISK_VITALS_THRESHOLD"] + 1)
            )))

        case = {
            "case_id": case_id,
            "age": age,
            "symptom_category": symptom_category,
            "symptom_severity": symptom_severity,
            "vital_risk_score": vital_risk_score,
            "chronic_condition": chronic_condition,
            "days_symptomatic": days_symptomatic,
        }

        ground_truth = self.compute_ground_truth(case)
        return case, ground_truth
