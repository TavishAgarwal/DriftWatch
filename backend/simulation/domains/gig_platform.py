"""
domains/gig_platform.py — Gig-Platform Dispatch & Rating domain for Driftwatch.

Scenario: AI system making dispatch assignments, performance ratings,
and penalty/suspension decisions for gig workers on a platform (e.g.,
food delivery, ride-hailing, logistics).  This domain connects to the
labor-displacement and gig-platform governance themes in the hackathon
brief.

Relevant policy context:
  - India's gig economy employs ~7.7 million workers (NITI Aayog 2022),
    projected to reach 23.5 million by 2030
  - Platform companies (Zomato, Swiggy, Ola, Urban Company) increasingly
    use AI for dispatch optimization, rating aggregation, and automated
    penalty decisions
  - The Code on Social Security (2020) and Rajasthan Platform-Based Gig
    Workers Act (2023) attempt to regulate algorithmic management
  - Worker complaints about opaque rating systems, unfair deactivations,
    and algorithmic wage theft are common across Indian gig platforms
"""

from __future__ import annotations

from typing import Any

from backend.simulation.domains.base import DomainModule


PLATFORM_TYPES = ["food_delivery", "ride_hailing", "logistics", "home_services"]
COMPLAINT_SEVERITY = ["none", "minor", "moderate", "severe"]
DECISION_TYPES = ["rating_adjustment", "dispatch_priority", "penalty", "deactivation"]
DISPUTE_EVIDENCE = ["none", "screenshot", "gps_log", "customer_testimony", "video"]


class GigPlatformDomain(DomainModule):
    """Deterministic gig-platform dispatch/rating case generator.

    Ground-truth rules determine whether to dismiss a complaint,
    flag it for human review, or take action against a gig worker.
    The oracle is intentionally designed to be more protective of
    workers than a pure profit-maximizing algorithm would be, so
    that AI errors tend to be OVER-penalizing workers — the type
    of error that is hardest for affected workers to appeal.

    Outcomes map to approve/deny/flag:
      - "approve"  →  dismiss complaint / no action against worker
      - "flag"     →  flag for human platform moderator review
      - "deny"     →  take action (penalty, rating cut, deactivation)
    """

    domain_id = "gig_platform"
    domain_name = "Gig-Platform Dispatch"
    domain_description = "Worker rating & penalty decisions — gig economy algorithmic management"
    reviewer_availability = 1.0

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_thresholds = {
            "MIN_RATING_FOR_GOOD_STANDING": 4.0,   # out of 5.0
            "MAX_RECENT_PENALTIES": 2,              # > 2 recent penalties → action
            "MIN_TRIPS_FOR_PATTERN": 50,            # need ≥ 50 trips to establish pattern
            "SEVERE_COMPLAINT_AUTO_ACTION": True,   # severe complaints → auto-penalty
            "DISPUTE_EVIDENCE_WEIGHT": 0.5,         # how much evidence matters
            "DEACTIVATION_THRESHOLD_PENALTIES": 5,  # ≥ 5 total penalties → deactivation
        }

    def compute_ground_truth(self, case: dict[str, Any]) -> str:
        """Deterministic platform decision rules.

        Rules (first match wins):
        1. Worker has dispute evidence (screenshot/video/GPS) + complaint < severe → approve (dismiss)
        2. Severe complaint + no evidence + high penalty count → deny (take action)
        3. Total penalties ≥ deactivation threshold → deny (deactivate)
        4. Recent penalties > MAX + low rating → deny (take action)
        5. Good standing (high rating + low penalties) + non-severe → approve
        6. Complaint is "none" → approve
        7. Low trip count (< MIN_TRIPS) → flag (insufficient data for pattern)
        8. Moderate complaint + some evidence → flag
        9. Otherwise → flag (default to human review for ambiguous cases)
        """
        thresh = self._current_thresholds
        rating = case["worker_rating"]
        recent_penalties = case["recent_penalties"]
        total_penalties = case["total_penalties"]
        total_trips = case["total_trips"]
        complaint = case["complaint_severity"]
        evidence = case["dispute_evidence"]
        has_evidence = evidence not in ("none", "")

        # Rule 1: Worker provides evidence, complaint isn't severe
        if has_evidence and complaint != "severe":
            return "approve"

        # Rule 2: Severe complaint, no evidence, penalty history
        if complaint == "severe" and not has_evidence and total_penalties >= thresh["MAX_RECENT_PENALTIES"]:
            return "deny"

        # Rule 3: Accumulated penalties → deactivation
        if total_penalties >= thresh["DEACTIVATION_THRESHOLD_PENALTIES"]:
            return "deny"

        # Rule 4: Recent pattern of penalties + low rating
        if recent_penalties > thresh["MAX_RECENT_PENALTIES"] and rating < thresh["MIN_RATING_FOR_GOOD_STANDING"]:
            return "deny"

        # Rule 5: Good standing + non-severe → dismiss
        if rating >= thresh["MIN_RATING_FOR_GOOD_STANDING"] and recent_penalties <= 1 and complaint != "severe":
            return "approve"

        # Rule 6: No complaint at all
        if complaint == "none":
            return "approve"

        # Rule 7: Not enough trips to judge
        if total_trips < thresh["MIN_TRIPS_FOR_PATTERN"]:
            return "flag"

        # Rule 8: Moderate with some evidence
        if complaint == "moderate" and has_evidence:
            return "flag"

        # Rule 9: Ambiguous — default to human review
        return "flag"

    def check_and_apply_shock(self, timestep: int) -> dict | None:
        """Shock: sudden platform policy change.

        Simulates regulatory crackdowns, competitor-driven policy shifts,
        or viral-social-media-induced policy overcorrections (e.g., a
        platform suddenly tightening deactivation thresholds after a
        public incident, or loosening them after driver shortages).
        """
        if self._shock_interval > 0 and timestep % self._shock_interval == 0 and timestep > 0:
            keys_to_shift = self._rng.sample(
                ["MIN_RATING_FOR_GOOD_STANDING", "MAX_RECENT_PENALTIES",
                 "DEACTIVATION_THRESHOLD_PENALTIES", "MIN_TRIPS_FOR_PATTERN"],
                k=self._rng.randint(2, 3),
            )
            old = self._current_thresholds.copy()
            for key in keys_to_shift:
                direction = self._rng.choice([-1, 1])
                val = self._current_thresholds[key]
                if isinstance(val, float):
                    self._current_thresholds[key] = max(1.0, min(5.0, val + direction * val * self._shock_magnitude))
                elif isinstance(val, int):
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

        platform_type = rng.choice(PLATFORM_TYPES)
        total_trips = rng.randint(5, 5000)
        decision_type = rng.choice(DECISION_TYPES)
        dispute_evidence = rng.choice(DISPUTE_EVIDENCE)

        # Rating, penalties, and complaint severity depend on difficulty
        if difficulty < 0.3:
            # Easy: clearly good worker or clearly bad
            if rng.random() < 0.5:
                worker_rating = round(rng.uniform(4.5, 5.0), 1)
                recent_penalties = 0
                total_penalties = rng.randint(0, 1)
                complaint_severity = rng.choice(["none", "minor"])
            else:
                worker_rating = round(rng.uniform(1.0, 2.5), 1)
                recent_penalties = rng.randint(3, 6)
                total_penalties = rng.randint(5, 10)
                complaint_severity = "severe"
        elif difficulty < 0.7:
            worker_rating = round(rng.uniform(2.5, 4.8), 1)
            recent_penalties = rng.randint(0, 4)
            total_penalties = rng.randint(0, 6)
            complaint_severity = rng.choice(COMPLAINT_SEVERITY)
        else:
            # Hard: near decision boundaries
            target_rating = self._current_thresholds["MIN_RATING_FOR_GOOD_STANDING"]
            worker_rating = round(max(1.0, min(5.0, target_rating + rng.uniform(-0.5, 0.5))), 1)
            recent_penalties = rng.randint(
                max(0, self._current_thresholds["MAX_RECENT_PENALTIES"] - 1),
                self._current_thresholds["MAX_RECENT_PENALTIES"] + 2,
            )
            total_penalties = rng.randint(
                max(0, self._current_thresholds["DEACTIVATION_THRESHOLD_PENALTIES"] - 2),
                self._current_thresholds["DEACTIVATION_THRESHOLD_PENALTIES"] + 1,
            )
            complaint_severity = rng.choice(["minor", "moderate", "severe"])

        case = {
            "case_id": case_id,
            "platform_type": platform_type,
            "worker_rating": worker_rating,
            "total_trips": total_trips,
            "recent_penalties": recent_penalties,
            "total_penalties": total_penalties,
            "complaint_severity": complaint_severity,
            "dispute_evidence": dispute_evidence,
            "decision_type": decision_type,
        }

        ground_truth = self.compute_ground_truth(case)
        return case, ground_truth
