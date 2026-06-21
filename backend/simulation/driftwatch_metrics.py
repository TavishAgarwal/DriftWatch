"""
driftwatch_metrics.py — Aggregated metrics for Driftwatch oversight-decay simulation.

Computes three core metrics from logged OversightEvents:
  1. Oversight decay curve   — avg review_probability over time
  2. Silent error rate       — fraction of incorrect+uncaught decisions per timestep
  3. Time-to-threshold       — first timestep where silent error rate exceeds a threshold

All metrics are computed per-timestep and per-model-backend so multiple
backends can be compared side-by-side.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from backend.simulation.oversight_logic import OversightEvent


# ═════════════════════════════════════════════════════════════
# Per-timestep metrics
# ═════════════════════════════════════════════════════════════
@dataclass(slots=True)
class TimestepMetrics:
    """Aggregated metrics for a single simulation timestep."""
    timestep: int
    avg_review_probability: float
    avg_review_skill: float
    silent_error_rate: float
    total_decisions: int
    total_errors: int
    total_caught: int
    total_reviewed: int
    model_backend: str
    burst_errors: int = 0
    baseline_errors: int = 0
    latency_skips: int = 0
    trust_skips: int = 0
    shock_active: bool = False
    in_burst: bool = False
    # Phase 3 fields
    avg_effective_skill: float = 0.0
    avg_skill_atrophy_rate: float = 0.0
    language_mismatch_count: int = 0
    availability_skips: int = 0
    # Phase 4 fields
    adversarial_submissions: int = 0
    adversarial_successes: int = 0
    # Phase 6
    avg_decision_confidence: float = 1.0


# ═════════════════════════════════════════════════════════════
# Full-run metrics
# ═════════════════════════════════════════════════════════════
@dataclass(slots=True)
class DriftwatchRunMetrics:
    """Complete metrics for a single Driftwatch simulation run."""
    model_backend: str
    timestep_metrics: list[TimestepMetrics] = field(default_factory=list)
    time_to_threshold: int | None = None  # first timestep where silent_error_rate > threshold
    final_avg_review_probability: float = 0.0
    final_silent_error_rate: float = 0.0
    total_decisions: int = 0
    total_silent_errors: int = 0
    oversight_debt: float = 0.0
    oversight_half_life: int | str = "not reached"
    burst_silent_errors: int = 0
    baseline_silent_errors: int = 0
    burst_error_contribution: float = 0.0
    latency_skips: int = 0
    trust_skips: int = 0
    shock_events: list[dict] = field(default_factory=list)
    drift_detection_times: list[dict[str, int | str]] = field(default_factory=list)
    # Phase 3 fields
    skill_recovery_rate: float = 0.0
    final_avg_review_skill: float = 0.0
    language_mismatch_errors: int = 0
    total_language_mismatches: int = 0
    # Phase 4 fields
    total_adversarial_submissions: int = 0
    total_adversarial_successes: int = 0
    cumulative_oversight_debt_adversarial: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_backend": self.model_backend,
            "timestep_metrics": [
                {
                    "timestep": m.timestep,
                    "avg_review_probability": round(m.avg_review_probability, 4),
                    "avg_review_skill": round(m.avg_review_skill, 4),
                    "silent_error_rate": round(m.silent_error_rate, 4),
                    "total_decisions": m.total_decisions,
                    "total_errors": m.total_errors,
                    "total_caught": m.total_caught,
                    "total_reviewed": m.total_reviewed,
                    "burst_errors": m.burst_errors,
                    "baseline_errors": m.baseline_errors,
                    "latency_skips": m.latency_skips,
                    "trust_skips": m.trust_skips,
                    "shock_active": m.shock_active,
                    "in_burst": m.in_burst,
                    "avg_effective_skill": round(m.avg_effective_skill, 4),
                    "avg_skill_atrophy_rate": round(m.avg_skill_atrophy_rate, 6),
                    "language_mismatch_count": m.language_mismatch_count,
                    "availability_skips": m.availability_skips,
                    "adversarial_submissions": m.adversarial_submissions,
                    "adversarial_successes": m.adversarial_successes,
                    "avg_decision_confidence": round(m.avg_decision_confidence, 4),
                }
                for m in self.timestep_metrics
            ],
            "time_to_threshold": self.time_to_threshold,
            "final_avg_review_probability": round(self.final_avg_review_probability, 4),
            "final_avg_review_skill": round(self.final_avg_review_skill, 4),
            "final_silent_error_rate": round(self.final_silent_error_rate, 4),
            "total_decisions": self.total_decisions,
            "total_silent_errors": self.total_silent_errors,
            "oversight_debt": round(self.oversight_debt, 4),
            "oversight_half_life": self.oversight_half_life,
            "burst_error_contribution": round(self.burst_error_contribution, 4),
            "latency_skips": self.latency_skips,
            "trust_skips": self.trust_skips,
            "shock_events": self.shock_events,
            "drift_detection_times": self.drift_detection_times,
            "skill_recovery_rate": round(self.skill_recovery_rate, 4),
            "language_mismatch_errors": self.language_mismatch_errors,
            "total_language_mismatches": self.total_language_mismatches,
            "total_adversarial_submissions": self.total_adversarial_submissions,
            "total_adversarial_successes": self.total_adversarial_successes,
            "cumulative_oversight_debt_adversarial": round(self.cumulative_oversight_debt_adversarial, 4),
        }


# ═════════════════════════════════════════════════════════════
# Computation functions
# ═════════════════════════════════════════════════════════════
def compute_timestep_metrics(
    events: list[OversightEvent],
    timestep: int,
    model_backend: str,
    shock_active: bool = False,
) -> TimestepMetrics:
    """Compute aggregated metrics for a single timestep from events."""
    if not events:
        return TimestepMetrics(
            timestep=timestep,
            avg_review_probability=0.0,
            avg_review_skill=0.0,
            silent_error_rate=0.0,
            total_decisions=0,
            total_errors=0,
            total_caught=0,
            total_reviewed=0,
            model_backend=model_backend,
            burst_errors=0,
            baseline_errors=0,
            latency_skips=0,
            trust_skips=0,
            shock_active=shock_active,
            in_burst=False,
        )

    total = len(events)
    total_errors = sum(1 for e in events if not e.is_correct)
    total_caught = sum(1 for e in events if e.caught)
    total_reviewed = sum(1 for e in events if e.reviewed)

    # Silent errors: incorrect AND not caught
    silent_errors = sum(1 for e in events if not e.is_correct and not e.caught)
    silent_error_rate = silent_errors / total if total > 0 else 0.0

    avg_review_prob = sum(e.review_probability for e in events) / total
    avg_review_skill = sum(e.review_skill for e in events) / total

    burst_errors = sum(1 for e in events if not e.is_correct and not e.caught and getattr(e, "burst_error", False))
    baseline_errors = silent_errors - burst_errors
    latency_skips = sum(1 for e in events if getattr(e, "skip_reason", "") in ("latency", "both"))
    trust_skips = sum(1 for e in events if getattr(e, "skip_reason", "") in ("trust", "both"))
    in_burst = any(getattr(e, "in_burst", False) for e in events)

    # Phase 3 metrics
    avg_effective_skill = sum(getattr(e, "effective_skill", e.review_skill) for e in events) / total
    avg_skill_atrophy_rate = sum(getattr(e, "skill_atrophy_rate", 0.0) for e in events) / total
    language_mismatch_count = sum(1 for e in events if not getattr(e, "language_match", True))
    availability_skips = sum(1 for e in events if getattr(e, "skip_reason", "") == "availability")

    # Phase 4 metrics
    adversarial_submissions = sum(1 for e in events if getattr(e, "adversarial_submission", False))
    adversarial_successes = sum(1 for e in events if getattr(e, "adversarial_submission", False) and not e.caught)

    return TimestepMetrics(
        timestep=timestep,
        avg_review_probability=avg_review_prob,
        avg_review_skill=avg_review_skill,
        silent_error_rate=silent_error_rate,
        total_decisions=total,
        total_errors=total_errors,
        total_caught=total_caught,
        total_reviewed=total_reviewed,
        model_backend=model_backend,
        burst_errors=burst_errors,
        baseline_errors=baseline_errors,
        latency_skips=latency_skips,
        trust_skips=trust_skips,
        shock_active=shock_active,
        in_burst=in_burst,
        avg_effective_skill=avg_effective_skill,
        avg_skill_atrophy_rate=avg_skill_atrophy_rate,
        language_mismatch_count=language_mismatch_count,
        availability_skips=availability_skips,
        adversarial_submissions=adversarial_submissions,
        adversarial_successes=adversarial_successes,
        avg_decision_confidence=sum(getattr(e, "decision_confidence", 1.0) for e in events) / max(1, total),
    )


def compute_driftwatch_metrics(
    all_events: list[OversightEvent],
    model_backend: str,
    silent_error_threshold: float = 0.10,
    initial_review_prob: float = 0.9,
    shock_events: list[dict] | None = None,
) -> DriftwatchRunMetrics:
    """Compute full-run Driftwatch metrics from all logged events.

    Parameters
    ----------
    all_events : list[OversightEvent]
        All oversight events across all timesteps.
    model_backend : str
        Name of the model backend.
    silent_error_threshold : float
        Threshold for time-to-threshold metric (default 10%).

    Returns
    -------
    DriftwatchRunMetrics
    """
    # Group events by timestep
    by_timestep: dict[int, list[OversightEvent]] = defaultdict(list)
    for event in all_events:
        by_timestep[event.timestep].append(event)

    timestep_metrics: list[TimestepMetrics] = []
    time_to_threshold: int | None = None

    if shock_events is None:
        shock_events = []
    shock_timesteps = {s["timestep"] for s in shock_events}

    for ts in sorted(by_timestep.keys()):
        ts_events = by_timestep[ts]
        shock_active = ts in shock_timesteps
        ts_metrics = compute_timestep_metrics(ts_events, ts, model_backend, shock_active)
        timestep_metrics.append(ts_metrics)

        # Check for time-to-threshold
        if time_to_threshold is None and ts_metrics.silent_error_rate >= silent_error_threshold:
            time_to_threshold = ts

    total_decisions = len(all_events)
    total_silent_errors = sum(
        1 for e in all_events if not e.is_correct and not e.caught
    )

    # Compute oversight debt
    oversight_debt = sum(initial_review_prob - m.avg_review_probability for m in timestep_metrics)

    # Compute half life
    oversight_half_life: int | str = "not reached"
    for m in timestep_metrics:
        if m.avg_review_probability <= 0.5 * initial_review_prob:
            oversight_half_life = m.timestep
            break

    burst_silent_errors = sum(m.burst_errors for m in timestep_metrics)
    baseline_silent_errors = sum(m.baseline_errors for m in timestep_metrics)
    burst_error_contribution = burst_silent_errors / max(1, total_silent_errors)
    total_latency_skips = sum(m.latency_skips for m in timestep_metrics)
    total_trust_skips = sum(m.trust_skips for m in timestep_metrics)

    # Detection lag after a model/policy update shock.  We use only observable
    # aggregate silent-error behavior: detection occurs when the post-shock
    # rate differs from the immediately preceding rate by >=5 percentage points.
    drift_detection_times: list[dict[str, int | str]] = []
    metrics_by_ts = {m.timestep: m for m in timestep_metrics}
    for shock in shock_events:
        shock_ts = int(shock["timestep"])
        pre = metrics_by_ts.get(shock_ts - 1)
        detected: int | None = None
        if pre is not None:
            for m in timestep_metrics:
                if m.timestep >= shock_ts and abs(m.silent_error_rate - pre.silent_error_rate) >= 0.05:
                    detected = m.timestep
                    break
        drift_detection_times.append({
            "shock_timestep": shock_ts,
            "detected_timestep": detected if detected is not None else "not detected",
            "detection_delay": (detected - shock_ts) if detected is not None else "not detected",
        })

    # Phase 3: Skill recovery rate — how fast skill recovers after hitting minimum
    # Find the minimum skill point and measure recovery slope afterward
    skill_recovery_rate = 0.0
    if len(timestep_metrics) >= 3:
        skills = [m.avg_review_skill for m in timestep_metrics]
        min_idx = skills.index(min(skills))
        if min_idx < len(skills) - 2:
            # Measure recovery over the next few steps after minimum
            recovery_window = skills[min_idx:min(min_idx + 5, len(skills))]
            if len(recovery_window) >= 2:
                skill_recovery_rate = (recovery_window[-1] - recovery_window[0]) / len(recovery_window)

    # Phase 3: Language mismatch error tracking
    language_mismatch_errors = sum(
        1 for e in all_events
        if not e.is_correct and not e.caught and not getattr(e, "language_match", True)
    )
    total_language_mismatches = sum(
        1 for e in all_events if not getattr(e, "language_match", True)
    )

    # Phase 4: Adversarial metrics
    total_adversarial_submissions = sum(m.adversarial_submissions for m in timestep_metrics)
    total_adversarial_successes = sum(m.adversarial_successes for m in timestep_metrics)
    # The additional harm is directly proportional to how many adversarial frauds slipped through (became silent errors)
    cumulative_oversight_debt_adversarial = float(total_adversarial_successes)

    return DriftwatchRunMetrics(
        model_backend=model_backend,
        timestep_metrics=timestep_metrics,
        time_to_threshold=time_to_threshold,
        final_avg_review_probability=(
            timestep_metrics[-1].avg_review_probability if timestep_metrics else 0.0
        ),
        final_silent_error_rate=(
            timestep_metrics[-1].silent_error_rate if timestep_metrics else 0.0
        ),
        final_avg_review_skill=(
            timestep_metrics[-1].avg_review_skill if timestep_metrics else 0.0
        ),
        total_decisions=total_decisions,
        total_silent_errors=total_silent_errors,
        oversight_debt=oversight_debt,
        oversight_half_life=oversight_half_life,
        burst_silent_errors=burst_silent_errors,
        baseline_silent_errors=baseline_silent_errors,
        burst_error_contribution=burst_error_contribution,
        latency_skips=total_latency_skips,
        trust_skips=total_trust_skips,
        shock_events=shock_events,
        drift_detection_times=drift_detection_times,
        skill_recovery_rate=skill_recovery_rate,
        language_mismatch_errors=language_mismatch_errors,
        total_language_mismatches=total_language_mismatches,
        total_adversarial_submissions=total_adversarial_submissions,
        total_adversarial_successes=total_adversarial_successes,
        cumulative_oversight_debt_adversarial=cumulative_oversight_debt_adversarial,
    )

def compute_crossover_point(metrics_a: DriftwatchRunMetrics, metrics_b: DriftwatchRunMetrics) -> dict:
    """Compute the timestep where 'better' backend's cumulative errors exceed 'worse' backend's.
    Assumes a and b are run with identical cases (same seed)."""
    cum_a = []
    curr_a = 0
    for m in metrics_a.timestep_metrics:
        curr_a += (m.burst_errors + m.baseline_errors)
        cum_a.append(curr_a)

    cum_b = []
    curr_b = 0
    for m in metrics_b.timestep_metrics:
        curr_b += (m.burst_errors + m.baseline_errors)
        cum_b.append(curr_b)

    crossover_ts: int | str = "not reached"
    for i in range(min(len(cum_a), len(cum_b))):
        # B is the challenged condition.  The cross-over point is the first
        # timestep where its cumulative silent harm exceeds baseline A.
        if cum_b[i] > cum_a[i]:
            crossover_ts = metrics_a.timestep_metrics[i].timestep
            break

    return {
        "crossover_timestep": crossover_ts,
        "backend_a": metrics_a.model_backend,
        "backend_b": metrics_b.model_backend,
        "cumulative_a": cum_a,
        "cumulative_b": cum_b,
    }
