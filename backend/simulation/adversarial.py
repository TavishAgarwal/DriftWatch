"""
adversarial.py — Strategic adaptive adversarial citizens for Driftwatch.

Phase 4: A configurable fraction of citizens are "strategic adversaries"
who submit fraudulent cases (cases they know should be denied) and adapt
their submission timing to exploit windows of low oversight.

The adversary uses a noisy proxy of oversight — the recent population-wide
approval rate — as their observability signal. They employ an epsilon-greedy
bandit strategy over binned "oversight windows" to learn which conditions
yield the highest success rate for undetected fraud.

Design Principles:
  - Non-magical: adversaries can't see true review_probability
  - Adaptive: early episodes are exploratory, later ones exploit learned patterns
  - Believable: mirrors real-world fraud timing (e.g., submitting claims
    during known low-staffing periods)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


# ═════════════════════════════════════════════════════════════
# Configuration
# ═════════════════════════════════════════════════════════════

# How many recent timesteps of approval-rate history the adversary can observe
OBSERVATION_WINDOW: int = 5

# Noise added to the observed proxy (stddev of Gaussian noise on approval rate)
PROXY_NOISE_STDDEV: float = 0.05

# Epsilon-greedy exploration rate (decays over episodes)
INITIAL_EPSILON: float = 0.4
MIN_EPSILON: float = 0.05
EPSILON_DECAY: float = 0.92  # per episode

# Number of "oversight level" bins the adversary tracks
NUM_OVERSIGHT_BINS: int = 5  # maps [0.0, 1.0] approval rate → 5 bins

# Threshold: adversary submits fraud when proxy suggests oversight is
# below this fraction of the observed range (i.e., "low oversight window")
SUBMIT_THRESHOLD_PERCENTILE: float = 0.4


@dataclass
class AdversaryState:
    """Per-adversary bandit state for timing exploitation.

    The adversary discretizes observed approval rate into bins and
    tracks a running average of "fraud success" (undetected) per bin.
    """
    # Bandit arm values: success rate per oversight-bin
    arm_values: list[float] = field(default_factory=lambda: [0.5] * NUM_OVERSIGHT_BINS)
    arm_counts: list[int] = field(default_factory=lambda: [1] * NUM_OVERSIGHT_BINS)
    epsilon: float = INITIAL_EPSILON
    total_submissions: int = 0
    total_successes: int = 0  # undetected frauds
    # Track submission timesteps for verification
    submission_timesteps: list[int] = field(default_factory=list)


class StrategicAdversary:
    """Manages a cohort of strategic adversarial citizens.

    Each adversary observes a noisy proxy of current oversight level
    (recent approval rate) and decides whether to submit a fraudulent
    case this timestep. Over repeated episodes, they learn which
    oversight conditions yield higher undetected-fraud rates.

    Usage
    -----
        adversary_mgr = StrategicAdversary(
            adversary_ids=["CIT_00010", "CIT_00011"],
            seed=42,
        )
        # Each timestep:
        for citizen in citizens:
            should_submit = adversary_mgr.should_submit_fraud(
                citizen_id=citizen["agent_id"],
                timestep=t,
                recent_approval_rate=0.85,  # noisy population proxy
            )
    """

    def __init__(self, adversary_ids: list[str], seed: int = 42) -> None:
        self._rng = random.Random(seed)
        self._states: dict[str, AdversaryState] = {
            aid: AdversaryState() for aid in adversary_ids
        }
        self._episode = 0

    @property
    def adversary_ids(self) -> set[str]:
        return set(self._states.keys())

    def is_adversary(self, citizen_id: str) -> bool:
        return citizen_id in self._states

    def new_episode(self) -> None:
        """Signal the start of a new simulation episode.

        Decays epsilon for all adversaries so they exploit more over time.
        """
        self._episode += 1
        for state in self._states.values():
            state.epsilon = max(MIN_EPSILON, state.epsilon * EPSILON_DECAY)

    def _get_oversight_bin(self, noisy_rate: float) -> int:
        """Map a [0.45, 0.50] approval rate to a discrete bin index."""
        # Scale the narrow 0.45-0.50 range to 0.0-1.0 to get useful bins
        scaled_rate = (noisy_rate - 0.45) / 0.05
        clamped = max(0.0, min(1.0, scaled_rate))
        b = int(clamped * NUM_OVERSIGHT_BINS)
        return min(b, NUM_OVERSIGHT_BINS - 1)

    def should_submit_fraud(
        self,
        citizen_id: str,
        timestep: int,
        recent_approval_rate: float,
    ) -> bool:
        """Decide whether this adversary submits a fraudulent case now.

        Parameters
        ----------
        citizen_id : str
            Must be a registered adversary ID.
        timestep : int
            Current simulation timestep.
        recent_approval_rate : float
            Population-level approval rate over recent timesteps
            (the adversary's observable proxy).

        Returns
        -------
        bool
            True if the adversary decides to submit fraud this timestep.
        """
        if citizen_id not in self._states:
            return False

        state = self._states[citizen_id]

        # Add observation noise to the proxy
        noisy_rate = recent_approval_rate + self._rng.gauss(0, PROXY_NOISE_STDDEV)
        noisy_rate = max(0.0, min(1.0, noisy_rate))

        current_bin = self._get_oversight_bin(noisy_rate)

        # Epsilon-greedy: explore or exploit
        if self._rng.random() < state.epsilon:
            # Explore: submit with 50% probability regardless
            submit = self._rng.random() < 0.5
        else:
            # Exploit: submit if this bin has historically high success
            # AND the approval rate suggests low oversight
            bin_value = state.arm_values[current_bin]
            # Higher approval rate = less oversight → more likely to submit
            # Combine bin success rate with current proxy signal
            submit_score = bin_value * 0.6 + noisy_rate * 0.4
            submit = submit_score > SUBMIT_THRESHOLD_PERCENTILE

        if submit:
            state.submission_timesteps.append(timestep)

        return submit

    def record_outcome(
        self,
        citizen_id: str,
        recent_approval_rate: float,
        was_detected: bool,
    ) -> None:
        """Update the adversary's bandit model after a fraud attempt.

        Parameters
        ----------
        citizen_id : str
            The adversary who submitted.
        recent_approval_rate : float
            The proxy value at the time of submission.
        was_detected : bool
            True if the fraud was caught by a reviewer.
        """
        if citizen_id not in self._states:
            return

        state = self._states[citizen_id]
        state.total_submissions += 1

        current_bin = self._get_oversight_bin(recent_approval_rate)
        reward = 0.0 if was_detected else 1.0

        if not was_detected:
            state.total_successes += 1

        # Incremental mean update for the arm
        state.arm_counts[current_bin] += 1
        n = state.arm_counts[current_bin]
        state.arm_values[current_bin] += (reward - state.arm_values[current_bin]) / n

    def get_cohort_stats(self) -> dict[str, Any]:
        """Return aggregate stats for the adversary cohort."""
        total_subs = sum(s.total_submissions for s in self._states.values())
        total_succ = sum(s.total_successes for s in self._states.values())
        all_timesteps = []
        for s in self._states.values():
            all_timesteps.extend(s.submission_timesteps)

        # Compute early vs late submission distribution
        if all_timesteps:
            sorted_ts = sorted(all_timesteps)
            midpoint = len(sorted_ts) // 2
            early_mean = sum(sorted_ts[:midpoint]) / max(1, midpoint) if midpoint > 0 else 0
            late_mean = sum(sorted_ts[midpoint:]) / max(1, len(sorted_ts) - midpoint)
        else:
            early_mean = 0
            late_mean = 0

        return {
            "total_adversaries": len(self._states),
            "total_fraud_submissions": total_subs,
            "total_undetected_frauds": total_succ,
            "fraud_success_rate": total_succ / max(1, total_subs),
            "early_submission_mean_timestep": round(early_mean, 2),
            "late_submission_mean_timestep": round(late_mean, 2),
            "episode": self._episode,
            "avg_epsilon": sum(s.epsilon for s in self._states.values()) / max(1, len(self._states)),
        }
