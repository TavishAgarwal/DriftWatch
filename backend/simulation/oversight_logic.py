"""
oversight_logic.py — Citizen trust/oversight decay logic for Driftwatch.

Implements the core oversight-decay mechanic: each citizen has a
``review_probability`` (chance they check the AI caseworker's decision)
and a ``review_skill`` (chance they catch an error when reviewing).
Both drift over time based on the caseworker's track record.

Phase 3 additions:
  - Language mismatch penalty on effective review_skill
  - Explainability/confidence-calibration effect on error detection
  - Exponential skill atrophy (accelerates with sustained low engagement)
  - Independent skill recovery tracking after shock re-engagement

Configurable nudge constants are at the top of this module so they
can be tuned without touching logic.

Usage
-----
    from backend.simulation.oversight_logic import update_citizen_oversight

    event = update_citizen_oversight(
        citizen=agent_dict,
        decision_outcome="approve",
        ground_truth="deny",
        timestep=5,
        model_backend="gpt-4o",
        rng=random.Random(42),
    )
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


# ═════════════════════════════════════════════════════════════
# CONFIGURABLE NUDGE CONSTANTS
# Tune these to control how fast oversight decays or recovers.
# All values are per-event magnitudes applied once per citizen
# per timestep.
# ═════════════════════════════════════════════════════════════

# When a citizen reviews and the decision was correct:
# their trust in the AI increases → review_probability decreases.
REVIEW_PROB_DECAY_ON_CORRECT: float = 0.02

# When a citizen reviews AND catches an error:
# their vigilance increases → review_probability increases.
REVIEW_PROB_BOOST_ON_CAUGHT: float = 0.05

# Passive decay of review_skill when a citizen has NOT been
# reviewing regularly (use-it-or-lose-it).
REVIEW_SKILL_PASSIVE_DECAY: float = 0.005

# When a citizen successfully catches an error, their skill
# is reinforced and improves slightly.
REVIEW_SKILL_BOOST_ON_CAUGHT: float = 0.03

# Passive skill recovery rate when citizen IS reviewing regularly.
# Much slower than decay to make skill loss sticky.
REVIEW_SKILL_RECOVERY_RATE: float = 0.002

# review_probability must be below this threshold for
# consecutive-step tracking to start counting toward skill decay.
LOW_REVIEW_THRESHOLD: float = 0.3

# Number of consecutive timesteps with review_probability below
# LOW_REVIEW_THRESHOLD before passive skill decay kicks in.
CONSECUTIVE_LOW_STEPS_TRIGGER: int = 3

# Minimum and maximum bounds for review_probability and review_skill
MIN_REVIEW_PROB: float = 0.01   # never truly zero
MAX_REVIEW_PROB: float = 0.99
MIN_REVIEW_SKILL: float = 0.05
MAX_REVIEW_SKILL: float = 0.99

# Default initial values
DEFAULT_INITIAL_REVIEW_PROBABILITY: float = 0.9
DEFAULT_INITIAL_REVIEW_SKILL: float = 0.8

# ── Phase 3: Language mismatch ────────────────────────────────
# Penalty applied to effective review_skill when citizen language
# does not match the caseworker explanation language.
# This is a COMPREHENSION penalty, NOT a willingness penalty.
LANGUAGE_MISMATCH_SKILL_PENALTY: float = 0.25

# ── Phase 3: Explainability / confidence calibration ──────────
# When explanation style is "terse", effective skill is reduced
# because there's less information for the citizen to evaluate.
TERSE_EXPLANATION_SKILL_PENALTY: float = 0.10

# When confidence is uncalibrated (model sounds equally confident
# regardless of actual reliability), catching errors is harder.
UNCALIBRATED_CONFIDENCE_SKILL_PENALTY: float = 0.15

# ── Phase 3: Exponential skill atrophy ────────────────────────
# Base decay rate for exponential atrophy.
SKILL_ATROPHY_BASE_RATE: float = 0.008
# Exponent scaling: how much consecutive low-engagement accelerates decay.
# decay = base_rate * (1 + acceleration * consecutive_low_steps)
SKILL_ATROPHY_ACCELERATION: float = 0.15
# Recovery rate after shock-induced re-engagement (per step while reviewing).
SKILL_RECOVERY_AFTER_SHOCK: float = 0.012


# ═════════════════════════════════════════════════════════════
# OversightEvent dataclass
# ═════════════════════════════════════════════════════════════
@dataclass(slots=True)
class OversightEvent:
    """Logged output of one citizen's oversight step.

    Attributes
    ----------
    timestep : int
        Simulation timestep this event occurred at.
    citizen_id : str
        Agent ID of the citizen.
    is_correct : bool
        Whether the caseworker's decision matched ground truth.
    reviewed : bool
        Whether the citizen actually reviewed the decision.
    caught : bool
        Whether the citizen caught an error (only True if
        reviewed AND decision was incorrect AND skill check passed).
    review_probability : float
        Citizen's review_probability AFTER this event's update.
    review_skill : float
        Citizen's review_skill AFTER this event's update.
    model_backend : str
        Name of the model backend that made the decision.
    skip_reason : str
        Why citizen skipped review (trust/latency/availability/none).
    latency_skip_probability : float
        The latency skip probability used.
    in_burst : bool
        Whether a hallucination burst was active.
    error_injected : bool
        Whether this decision had an error injected.
    burst_error : bool
        Whether this was a burst-induced error.
    language_match : bool
        Whether citizen language matched explanation language.
    effective_skill : float
        Actual review_skill used for this interaction (after penalties).
    explanation_style : str
        "terse" or "detailed".
    confidence_calibrated : bool
        Whether the model's confidence was calibrated.
    skill_atrophy_rate : float
        The instantaneous skill decay rate applied this step.
    initial_review_skill : float
        The citizen's review_skill at the START of this step (before update).
    """
    timestep: int
    citizen_id: str
    is_correct: bool
    reviewed: bool
    caught: bool
    review_probability: float
    review_skill: float
    model_backend: str
    skip_reason: str
    latency_skip_probability: float
    in_burst: bool
    error_injected: bool
    burst_error: bool
    # Phase 3 fields
    language_match: bool = True
    effective_skill: float = 0.0
    explanation_style: str = "detailed"
    confidence_calibrated: bool = True
    skill_atrophy_rate: float = 0.0
    initial_review_skill: float = 0.0
    # Phase 4 fields
    adversarial_submission: bool = False
    # Phase 6 fields
    decision_confidence: float = 1.0


# ═════════════════════════════════════════════════════════════
# Core update function
# ═════════════════════════════════════════════════════════════
def update_citizen_oversight(
    citizen: dict,
    decision_outcome: str,
    ground_truth: str,
    timestep: int,
    model_backend: str,
    rng: random.Random,
    *,
    counterfactual_freeze: bool = False,
    latency_skip_probability: float = 0.0,
    in_burst: bool = False,
    error_injected: bool = False,
    burst_error: bool = False,
    reviewer_availability: float = 1.0,
    # Phase 3 parameters
    language_match: bool = True,
    explanation_style: str = "detailed",
    confidence_calibrated: bool = True,
    # Phase 5 parameters
    neighbor_signal: float = 0.0,
    social_influence_weight: float = 0.0,
    # Phase 6 parameters
    decision_confidence: float = 1.0,
    spot_check_rate: float = 0.0,
    confidence_review_threshold: float = 0.0,
    is_mandatory_audit: bool = False,
) -> OversightEvent:
    """Run one oversight step for a single citizen.

    Parameters
    ----------
    citizen : dict
        Mutable agent dict. Must contain ``agent_id``,
        ``review_probability``, ``review_skill``,
        ``consecutive_low_review_steps``, and
        ``initial_review_skill`` (Phase 3).
    decision_outcome : str
        The caseworker's decision ("approve"/"deny"/"flag").
    ground_truth : str
        The oracle's correct decision.
    timestep : int
        Current simulation timestep.
    model_backend : str
        Name of the active model backend.
    rng : random.Random
        Random number generator for stochastic decisions.
    counterfactual_freeze : bool
        If True, review_probability is frozen at its current value
        (no decay or boost). Used for counterfactual comparison.
    reviewer_availability : float
        Structural ceiling on actual review capacity.
    language_match : bool
        Whether citizen's language matches explanation language.
    explanation_style : str
        "terse" or "detailed".
    confidence_calibrated : bool
        Whether the model reports calibrated confidence.

    Returns
    -------
    OversightEvent
    """
    citizen_id = citizen["agent_id"]
    review_prob = citizen["review_probability"]
    review_skill = citizen["review_skill"]
    consecutive_low = citizen.get("consecutive_low_review_steps", 0)
    citizen_initial_skill = citizen.get("initial_review_skill", review_skill)

    # Record pre-update skill for tracking
    skill_before_update = review_skill

    is_correct = (decision_outcome == ground_truth)

    # ── Phase 3: Compute effective review skill ──
    # Start with raw skill, then apply penalties for language
    # mismatch, terse explanations, and uncalibrated confidence.
    # These are comprehension penalties — they don't change the
    # stored skill, only what's used for the catch roll this step.
    effective_skill = review_skill

    if not language_match:
        effective_skill -= LANGUAGE_MISMATCH_SKILL_PENALTY

    if explanation_style == "terse":
        effective_skill -= TERSE_EXPLANATION_SKILL_PENALTY

    if not confidence_calibrated:
        effective_skill -= UNCALIBRATED_CONFIDENCE_SKILL_PENALTY

    effective_skill = max(MIN_REVIEW_SKILL, min(MAX_REVIEW_SKILL, effective_skill))

    # ── Does the citizen review this decision? ──
    trust_would_review = rng.random() < review_prob
    latency_would_skip = rng.random() < latency_skip_probability
    structural_availability = rng.random() < reviewer_availability

    # Phase 6 intervention logic
    forced_by_spot_check = rng.random() < spot_check_rate
    forced_by_confidence = decision_confidence < confidence_review_threshold
    forced_by_audit = is_mandatory_audit

    if forced_by_audit or forced_by_spot_check or forced_by_confidence:
        reviewed = True
        if forced_by_audit:
            # Audits trigger skill recovery
            consecutive_low = 0
            review_skill = citizen_initial_skill
    else:
        reviewed = trust_would_review and structural_availability and not latency_would_skip

    if not trust_would_review:
        skip_reason = "trust"
    elif not structural_availability:
        skip_reason = "availability"
    elif latency_would_skip:
        skip_reason = "latency"
    else:
        skip_reason = "none"

    caught = False
    atrophy_rate_this_step = 0.0

    if reviewed:
        # Use effective_skill (with penalties) for the catch roll
        if not is_correct and rng.random() < effective_skill:
            # Citizen caught the error
            caught = True
            if not counterfactual_freeze:
                # Error corrected → nudge review_probability and skill UP
                review_prob = min(MAX_REVIEW_PROB, review_prob + REVIEW_PROB_BOOST_ON_CAUGHT)
                review_skill = min(MAX_REVIEW_SKILL, review_skill + REVIEW_SKILL_BOOST_ON_CAUGHT)
        else:
            # Reviewed but didn't catch error (or decision was correct)
            if is_correct and not counterfactual_freeze:
                # Everything looked fine → trust increases → review less
                review_prob = max(MIN_REVIEW_PROB, review_prob - REVIEW_PROB_DECAY_ON_CORRECT)

            # Phase 3: Skill recovery while actively reviewing
            # Recovery rate is higher right after a shock re-engagement
            if not counterfactual_freeze:
                # Use the faster shock-recovery rate if skill is below
                # the citizen's original level (they're recovering)
                if review_skill < citizen_initial_skill:
                    recovery = SKILL_RECOVERY_AFTER_SHOCK
                else:
                    recovery = REVIEW_SKILL_RECOVERY_RATE
                review_skill = min(MAX_REVIEW_SKILL, review_skill + recovery)

        # Reset consecutive low counter since citizen IS reviewing
        consecutive_low = 0
    else:
        # Did not review — track consecutive low-review steps
        if review_prob < LOW_REVIEW_THRESHOLD:
            consecutive_low += 1
        else:
            consecutive_low = 0

        # Phase 3: Exponential skill atrophy
        # Decay accelerates with sustained non-engagement
        if consecutive_low >= CONSECUTIVE_LOW_STEPS_TRIGGER and not counterfactual_freeze:
            # Exponential: rate increases with consecutive low steps
            atrophy_rate_this_step = SKILL_ATROPHY_BASE_RATE * (
                1.0 + SKILL_ATROPHY_ACCELERATION * consecutive_low
            )
            review_skill = max(
                MIN_REVIEW_SKILL,
                review_skill - atrophy_rate_this_step
            )

    # ── Phase 5: Social Contagion Anchoring ──
    # Nudge review_probability toward the neighbor's alarm state.
    if social_influence_weight > 0.0 and not counterfactual_freeze:
        # Expected baseline error catch rate. If neighbors complain less than this, trust rises.
        # If neighbors complain more than this, trust drops (review probability increases).
        baseline_complaint_expectation = 0.26
        social_delta = social_influence_weight * (neighbor_signal - baseline_complaint_expectation)
        review_prob = max(MIN_REVIEW_PROB, min(MAX_REVIEW_PROB, review_prob + social_delta))

    # ── Write updated state back to citizen dict ──
    citizen["review_probability"] = review_prob
    citizen["review_skill"] = review_skill
    citizen["consecutive_low_review_steps"] = consecutive_low

    return OversightEvent(
        timestep=timestep,
        citizen_id=citizen_id,
        is_correct=is_correct,
        reviewed=reviewed,
        caught=caught,
        review_probability=review_prob,
        review_skill=review_skill,
        model_backend=model_backend,
        skip_reason=skip_reason,
        latency_skip_probability=latency_skip_probability,
        in_burst=in_burst,
        error_injected=error_injected,
        burst_error=burst_error,
        # Phase 3 fields
        language_match=language_match,
        effective_skill=effective_skill,
        explanation_style=explanation_style,
        confidence_calibrated=confidence_calibrated,
        skill_atrophy_rate=atrophy_rate_this_step,
        initial_review_skill=citizen_initial_skill,
        decision_confidence=decision_confidence,
    )
