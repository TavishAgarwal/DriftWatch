"""
oversight_logic.py — Citizen trust/oversight decay logic for Driftwatch.

Implements the core oversight-decay mechanic: each citizen has a
``review_probability`` (chance they check the AI caseworker's decision)
and a ``review_skill`` (chance they catch an error when reviewing).
Both drift over time based on the caseworker's track record.

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
    """
    timestep: int
    citizen_id: str
    is_correct: bool
    reviewed: bool
    caught: bool
    review_probability: float
    review_skill: float
    model_backend: str


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
) -> OversightEvent:
    """Run one oversight step for a single citizen.

    Parameters
    ----------
    citizen : dict
        Mutable agent dict. Must contain ``agent_id``,
        ``review_probability``, ``review_skill``, and
        ``consecutive_low_review_steps``.
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

    Returns
    -------
    OversightEvent
    """
    citizen_id = citizen["agent_id"]
    review_prob = citizen["review_probability"]
    review_skill = citizen["review_skill"]
    consecutive_low = citizen.get("consecutive_low_review_steps", 0)

    is_correct = (decision_outcome == ground_truth)

    # ── Does the citizen review this decision? ──
    reviewed = rng.random() < review_prob

    caught = False

    if reviewed:
        if not is_correct and rng.random() < review_skill:
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
            # Skill gets a tiny recovery boost from being exercised
            if not counterfactual_freeze:
                review_skill = min(MAX_REVIEW_SKILL, review_skill + REVIEW_SKILL_RECOVERY_RATE)

        # Reset consecutive low counter since citizen IS reviewing
        consecutive_low = 0
    else:
        # Did not review — track consecutive low-review steps
        if review_prob < LOW_REVIEW_THRESHOLD:
            consecutive_low += 1
        else:
            consecutive_low = 0

        # Passive skill decay when not reviewing for several consecutive steps
        if consecutive_low >= CONSECUTIVE_LOW_STEPS_TRIGGER and not counterfactual_freeze:
            review_skill = max(MIN_REVIEW_SKILL, review_skill - REVIEW_SKILL_PASSIVE_DECAY)

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
    )
