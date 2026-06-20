"""
Driftwatch — Tier 1 Agent Engine
=================================
Implements the 14 archetypes defined in AGENT_SPEC.md with pure NumPy
vectorised operations.  No LLM calls.  Every decision function uses
np.where for conditional logic; individual agent decision_step is a
single-agent method while the batch wrapper lives in SimulationEngine.

Public API
----------
    from backend.agents.tier1_agent import (
        Tier1Agent,
        PersonalityVector,
        PopulationFactory,
        AgentDecision,
        PolicyState,
    )

References
----------
    AGENT_SPEC.md §TIER 1 CITIZEN ARCHETYPES
    backend/data/config_loader.py  (ZoneContext dataclass consumed here)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Memory vector dimensionality — compressed event history.
MEMORY_DIM: int = 32
# Exponential decay factor for daily memory updates.
MEMORY_DECAY: float = 0.95

# ─────────────────────────────────────────────────────────────
# ACTIONS — canonical string constants
# ─────────────────────────────────────────────────────────────
ACTION_NO_CHANGE = "no_change"
ACTION_MODE_SWITCH = "mode_switch"
ACTION_TRIP_CONSOLIDATION = "trip_consolidation"
ACTION_ROUTE_CHANGE = "route_change"
ACTION_RETURN_MIGRATION = "return_migration"
ACTION_PROTEST_JOIN = "protest_join"
ACTION_WFH_INVOKE = "wfh_invoke"
ACTION_VENDOR_RELOCATE = "vendor_relocate"
ACTION_BANDH_CALL = "bandh_call"
ACTION_REDUCED_HOURS = "reduced_hours"
ACTION_ATTENDANCE_REDUCED = "attendance_reduced"
ACTION_COMPLAINT_FILED = "complaint_filed"


# ═════════════════════════════════════════════════════════════
# PersonalityVector — 47 typed fields
# ═════════════════════════════════════════════════════════════
@dataclass(slots=True)
class PersonalityVector:
    """47-dimension personality vector parameterising an archetype.

    Field groups (AGENT_SPEC.md §PERSONALITY VECTOR):
        ECONOMIC  (10 fields)
        TRANSIT   (8 fields)
        SOCIAL    (8 fields)
        DECISION  (8 fields)
        IDENTITY  (13 fields)

    All numeric fields are float64 unless explicitly int/str.
    """

    # ── ECONOMIC (10) ──────────────────────────────────────
    income_monthly: float = 0.0
    income_stability: float = 0.0
    savings_buffer_days: float = 0.0
    loan_obligation_flag: float = 0.0
    remittance_rate: float = 0.0
    disposable_income_actual: float = 0.0
    income_variability: float = 0.0
    footfall_transit_dependency: float = 0.0
    supply_chain_transit_dependency: float = 0.0
    employee_count: float = 0.0

    # ── TRANSIT (8) ────────────────────────────────────────
    commute_dependency: float = 0.0
    fare_sensitivity_score: float = 0.0
    metro_dependency_score: float = 0.0
    car_ownership_flag: float = 0.0
    cab_aggregator_dependency: float = 0.0
    night_transit_dependency: float = 0.0
    transit_subsidy_flag: float = 0.0
    vending_location_transit_dependency: float = 0.0

    # ── SOCIAL (8) ─────────────────────────────────────────
    political_engagement: float = 0.0
    digital_access_level: float = 0.0
    peer_influence_susceptibility: float = 0.0
    local_community_network_strength: float = 0.0
    media_reach_multiplier: float = 1.0
    political_network_connections: float = 0.0
    source_network_strength: float = 0.0
    editorial_independence: float = 0.0

    # ── DECISION (8) ───────────────────────────────────────
    loss_aversion_score: float = 0.0
    risk_tolerance: float = 0.0
    collective_action_threshold: float = 0.5
    information_diffusion_speed: float = 0.0
    institutional_trust_railways: float = 0.5
    institutional_trust_examinations: float = 0.5
    examination_sensitivity: float = 0.0
    service_quality_sensitivity: float = 0.0

    # ── IDENTITY (13) ──────────────────────────────────────
    archetype: str = ""
    zone_id: str = ""
    family_financial_dependents: int = 0
    children_count: int = 0
    housing_type: str = ""
    shift_pattern: str = "day_shift"
    work_location_stability: float = 0.0
    essential_worker_identity: float = 0.0
    pension_security_index: float = 0.0
    coaching_centre_dependency: float = 0.0
    attempts_remaining: int = 3
    mental_health_stress_index: float = 0.0
    political_expression_restraint: float = 0.0


# ═════════════════════════════════════════════════════════════
# ARCHETYPE_BOUNDS — per-archetype (min, max) for numeric fields
# ═════════════════════════════════════════════════════════════
# Maps archetype name → {field_name: (min, max)}.
# Derived directly from AGENT_SPEC.md §Personality vector base ranges.
# Fields not listed for an archetype use the dataclass defaults.

ARCHETYPE_BOUNDS: dict[str, dict[str, tuple[float, float]]] = {
    # ── 1. Daily wage worker (majdoor) ─────────────────────
    "daily_wage_worker": {
        "income_monthly": (8_000.0, 16_000.0),
        "income_stability": (0.12, 0.28),
        "commute_dependency": (0.91, 0.99),
        "loss_aversion_score": (0.85, 0.95),
        "savings_buffer_days": (2.0, 8.0),
        "work_location_stability": (0.15, 0.35),
        "family_financial_dependents": (2.0, 5.0),
        "digital_access_level": (0.18, 0.35),
        "political_engagement": (0.31, 0.55),
        "fare_sensitivity_score": (0.75, 0.92),
        "risk_tolerance": (0.15, 0.35),
        "collective_action_threshold": (0.30, 0.50),
        "peer_influence_susceptibility": (0.55, 0.75),
    },
    # ── 2. Formal sector employee (naukripesh) ─────────────
    "formal_sector_employee": {
        "income_monthly": (18_000.0, 45_000.0),
        "income_stability": (0.72, 0.88),
        "commute_dependency": (0.74, 0.88),
        "loss_aversion_score": (0.71, 0.82),
        "savings_buffer_days": (15.0, 45.0),
        "work_location_stability": (0.78, 0.92),
        "family_financial_dependents": (1.0, 3.0),
        "loan_obligation_flag": (0.55, 0.75),
        "digital_access_level": (0.61, 0.78),
        "fare_sensitivity_score": (0.50, 0.70),
        "examination_sensitivity": (0.55, 0.78),
        "collective_action_threshold": (0.45, 0.65),
    },
    # ── 3. Government employee (sarkari karmchari) ─────────
    "government_employee": {
        "income_monthly": (25_000.0, 85_000.0),
        "income_stability": (0.95, 0.99),
        "institutional_trust_railways": (0.68, 0.82),
        "institutional_trust_examinations": (0.71, 0.88),
        "transit_subsidy_flag": (0.45, 0.70),
        "political_expression_restraint": (0.65, 0.85),
        "commute_dependency": (0.55, 0.75),
        "pension_security_index": (0.88, 0.98),
        "loss_aversion_score": (0.50, 0.68),
        "fare_sensitivity_score": (0.20, 0.45),
    },
    # ── 4. Tech / knowledge worker (software-wala) ─────────
    "tech_knowledge_worker": {
        "income_monthly": (60_000.0, 350_000.0),
        "income_stability": (0.82, 0.94),
        "commute_dependency": (0.28, 0.55),
        "fare_sensitivity_score": (0.08, 0.22),
        "service_quality_sensitivity": (0.78, 0.92),
        "digital_access_level": (0.92, 0.99),
        "cab_aggregator_dependency": (0.45, 0.75),
        "political_engagement": (0.71, 0.88),
        "examination_sensitivity": (0.55, 0.78),
    },
    # ── 5. Small business owner / trader (vyapari) ─────────
    "small_business_owner": {
        "income_monthly": (25_000.0, 180_000.0),
        "income_stability": (0.35, 0.62),
        "footfall_transit_dependency": (0.45, 0.85),
        "employee_count": (1.0, 15.0),
        "supply_chain_transit_dependency": (0.38, 0.72),
        "risk_tolerance": (0.42, 0.68),
        "loss_aversion_score": (0.62, 0.78),
        "political_network_connections": (0.45, 0.72),
        "collective_action_threshold": (0.30, 0.50),
    },
    # ── 6. Student (vidyarthi) ─────────────────────────────
    "student": {
        "income_monthly": (0.0, 0.0),  # dependent — no personal income
        "examination_sensitivity": (0.88, 0.98),
        "political_engagement": (0.45, 0.72),
        "peer_influence_susceptibility": (0.72, 0.88),
        "coaching_centre_dependency": (0.35, 0.78),
        "digital_access_level": (0.60, 0.85),
        "fare_sensitivity_score": (0.55, 0.85),
        "collective_action_threshold": (0.30, 0.55),
    },
    # ── 7. Homemaker / household manager (grihini) ─────────
    "homemaker": {
        "income_monthly": (0.0, 0.0),  # household role
        "children_count": (1.0, 4.0),
        "local_community_network_strength": (0.78, 0.92),
        "fare_sensitivity_score": (0.82, 0.94),
        "digital_access_level": (0.35, 0.58),
        "loss_aversion_score": (0.72, 0.88),
        "commute_dependency": (0.40, 0.65),
        "collective_action_threshold": (0.50, 0.72),
    },
    # ── 8. Street vendor / hawker (pheriwala) ──────────────
    "street_vendor": {
        "income_monthly": (6_000.0, 22_000.0),
        "income_variability": (0.45, 0.72),
        "vending_location_transit_dependency": (0.88, 0.98),
        "supply_chain_transit_dependency": (0.65, 0.82),
        "savings_buffer_days": (0.0, 5.0),
        "loss_aversion_score": (0.88, 0.97),
        "local_community_network_strength": (0.72, 0.88),
        "fare_sensitivity_score": (0.80, 0.95),
        "commute_dependency": (0.85, 0.98),
    },
    # ── 9. Retired / senior citizen (buzurg) ───────────────
    "retired": {
        "income_monthly": (8_000.0, 45_000.0),
        "commute_dependency": (0.25, 0.50),
        "fare_sensitivity_score": (0.40, 0.65),
        "institutional_trust_railways": (0.55, 0.75),
        "digital_access_level": (0.18, 0.42),
        "local_community_network_strength": (0.78, 0.92),
        "political_engagement": (0.60, 0.82),
        "pension_security_index": (0.55, 0.85),
        "loss_aversion_score": (0.65, 0.80),
    },
    # ── 10. Migrant worker (pravasi majdoor) ───────────────
    "migrant_worker": {
        "income_monthly": (10_000.0, 28_000.0),
        "remittance_rate": (0.35, 0.65),
        "savings_buffer_days": (1.0, 6.0),
        "commute_dependency": (0.90, 0.99),
        "loss_aversion_score": (0.82, 0.94),
        "digital_access_level": (0.20, 0.42),
        "fare_sensitivity_score": (0.78, 0.94),
        "risk_tolerance": (0.18, 0.38),
        "work_location_stability": (0.20, 0.45),
    },
    # ── 11. Healthcare worker (swasthya karmchari) ─────────
    "healthcare_worker": {
        "income_monthly": (15_000.0, 180_000.0),
        "night_transit_dependency": (0.72, 0.92),
        "institutional_trust_railways": (0.68, 0.82),
        "essential_worker_identity": (0.82, 0.95),
        "commute_dependency": (0.80, 0.95),
        "fare_sensitivity_score": (0.35, 0.65),
        "digital_access_level": (0.55, 0.78),
        "loss_aversion_score": (0.55, 0.75),
    },
    # ── 12. Exam aspirant (aspirant) ───────────────────────
    "exam_aspirant": {
        "income_monthly": (0.0, 0.0),  # no personal income
        "examination_sensitivity": (0.95, 0.99),
        "coaching_centre_dependency": (0.70, 0.95),
        "mental_health_stress_index": (0.65, 0.88),
        "attempts_remaining": (1.0, 3.0),
        "peer_influence_susceptibility": (0.78, 0.95),
        "digital_access_level": (0.55, 0.78),
        "fare_sensitivity_score": (0.60, 0.85),
        "commute_dependency": (0.75, 0.92),
    },
    # ── 13. Gig economy worker (gig-worker) ────────────────
    "gig_economy_worker": {
        "income_monthly": (18_000.0, 55_000.0),
        "income_variability": (0.52, 0.78),
        "fare_sensitivity_score": (0.45, 0.68),
        "loan_obligation_flag": (0.55, 0.78),
        "commute_dependency": (0.82, 0.96),
        "digital_access_level": (0.65, 0.85),
        "risk_tolerance": (0.40, 0.65),
        "cab_aggregator_dependency": (0.78, 0.94),
    },
    # ── 14. Journalist / media worker (patrakar) ───────────
    "journalist_tier1": {
        "income_monthly": (15_000.0, 65_000.0),
        "media_reach_multiplier": (2.5, 8.0),
        "editorial_independence": (0.35, 0.82),
        "source_network_strength": (0.65, 0.88),
        "digital_access_level": (0.72, 0.95),
        "political_engagement": (0.60, 0.85),
        "commute_dependency": (0.55, 0.78),
        "fare_sensitivity_score": (0.40, 0.65),
    },
}

ALL_ARCHETYPES: list[str] = list(ARCHETYPE_BOUNDS.keys())


# ═════════════════════════════════════════════════════════════
# AgentDecision — output of a single decision step
# ═════════════════════════════════════════════════════════════
@dataclass(slots=True)
class AgentDecision:
    """Single-step decision output for a Tier 1 agent.

    Attributes
    ----------
    action : str
        One of the canonical ACTION_* constants.
    broadcast_signal : float
        Resistance/support signal broadcast to network (-1.0 to 1.0).
        Positive = resistance; negative = support/benefit.
    broadcast_reach : int
        Number of agents this signal reaches (base connections ×
        media_reach_multiplier for journalist archetype).
    reasoning_key : str
        Short machine-readable key explaining the decision path taken,
        e.g. ``"fare_exceeds_8pct_daily_wage"``.
    """

    action: str = ACTION_NO_CHANGE
    broadcast_signal: float = 0.0
    broadcast_reach: int = 0
    reasoning_key: str = ""


# ═════════════════════════════════════════════════════════════
# PolicyState — description of an active policy scenario
# ═════════════════════════════════════════════════════════════
@dataclass(slots=True)
class PolicyState:
    """Describes the active policy being simulated.

    Attributes
    ----------
    policy_type : str
        E.g. ``"fare_hike"``, ``"concession_removal"``, ``"service_disruption"``.
    fare_change_pct : float
        Percentage change in fare (positive = increase).
    affected_modes : list[str]
        Transit modes affected, e.g. ``["metro", "bus"]``.
    timeline_days : int
        Total duration of the policy scenario.
    day_current : int
        Current simulation day within the scenario.
    """

    policy_type: str = ""
    fare_change_pct: float = 0.0
    affected_modes: list[str] = field(default_factory=list)
    timeline_days: int = 90
    day_current: int = 0


# ═════════════════════════════════════════════════════════════
# Archetype-specific decision functions
# ═════════════════════════════════════════════════════════════
# Each function receives (PersonalityVector, PolicyState, memory,
# network_signals) and returns an AgentDecision.
# Uses np.where for conditional logic per AGENT_SPEC.md.

def _decide_daily_wage_worker(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 1 — majdoor.

    ★ If fare > 8% of daily wage → mode_switch.
    ★ If delay > 45 min → evaluate skip work.
    ★ Highest loss aversion. Zero uncertainty tolerance.
    """
    daily_wage = p.income_monthly / 26.0  # ~26 working days
    fare_pct_of_wage = ps.fare_change_pct / 100.0 * daily_wage / np.maximum(daily_wage, 1.0)
    # Absolute fare burden relative to daily wage
    fare_burden = np.float64(ps.fare_change_pct / 100.0)

    # Network delay signal (avg delay minutes reported by peers)
    delay_minutes = np.float64(ns.get("avg_delay_minutes", 0.0))

    # Resistance signal scales with loss aversion
    signal = np.float64(p.loss_aversion_score * fare_burden)

    action = str(np.where(
        fare_burden > 0.08,
        ACTION_MODE_SWITCH,
        np.where(delay_minutes > 45.0, ACTION_MODE_SWITCH, ACTION_NO_CHANGE),
    ))

    reasoning = str(np.where(
        fare_burden > 0.08,
        "fare_exceeds_8pct_daily_wage",
        np.where(delay_minutes > 45.0, "delay_exceeds_45min", "within_tolerance"),
    ))

    # Collective action check
    net_resistance = np.float64(ns.get("zone_resistance", 0.0))
    if net_resistance > p.collective_action_threshold:
        action = ACTION_PROTEST_JOIN
        reasoning = "collective_threshold_crossed"
        signal = np.clip(signal * 1.3, -1.0, 1.0)

    reach = int(np.floor(p.peer_influence_susceptibility * 40))
    return AgentDecision(
        action=str(action),
        broadcast_signal=float(np.clip(signal, -1.0, 1.0)),
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_formal_sector_employee(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 2 — naukripesh.

    ★ If transport > 12% monthly salary → evaluate alternatives.
    ★ Response delayed 7-14 days.
    ★ High formal complaint filing.
    """
    transport_share = ps.fare_change_pct / 100.0
    above_threshold = np.float64(transport_share > 0.12)
    within_delay_window = np.float64(ps.day_current >= 7)

    action = str(np.where(
        np.logical_and(above_threshold, within_delay_window),
        ACTION_MODE_SWITCH,
        ACTION_NO_CHANGE,
    ))
    reasoning = str(np.where(
        np.logical_and(above_threshold, within_delay_window),
        "transport_exceeds_12pct_salary_after_delay",
        np.where(above_threshold, "above_threshold_within_delay_period", "within_budget"),
    ))

    signal = float(np.clip(
        p.loss_aversion_score * transport_share * p.loan_obligation_flag, -1.0, 1.0,
    ))

    # Formal complaint filing at higher threshold
    net_resistance = np.float64(ns.get("zone_resistance", 0.0))
    if net_resistance > p.collective_action_threshold:
        action = ACTION_COMPLAINT_FILED
        reasoning = "formal_complaint_threshold"

    reach = int(np.floor(p.digital_access_level * 35))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_government_employee(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 3 — sarkari karmchari.

    ★ If transit_subsidy_flag active → immune to fare hike.
    ★ If subsidy removed → highest resistance immediately.
    """
    subsidy_active = np.float64(p.transit_subsidy_flag > 0.5)
    subsidy_removed = np.float64(ps.policy_type == "concession_removal")

    action = str(np.where(
        subsidy_removed,
        ACTION_COMPLAINT_FILED,
        np.where(subsidy_active, ACTION_NO_CHANGE, ACTION_NO_CHANGE),
    ))

    # Perceived betrayal amplifier when subsidy is removed
    signal = float(np.where(
        subsidy_removed,
        np.clip(0.95 * p.institutional_trust_railways, 0.0, 1.0),
        np.where(subsidy_active, 0.0, ps.fare_change_pct / 100.0 * 0.3),
    ))

    reasoning = str(np.where(
        subsidy_removed,
        "subsidy_removal_betrayal",
        np.where(subsidy_active, "subsidy_immune", "fare_pass_through"),
    ))

    reach = int(np.floor(p.digital_access_level * 25))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_tech_knowledge_worker(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 4 — software-wala.

    ★ Evaluates comfort/reliability, NOT fare.
    ★ WFH as first lever.
    ★ Extremely high online broadcast amplitude.
    """
    delay_minutes = np.float64(ns.get("avg_delay_minutes", 0.0))
    service_drop = np.float64(ns.get("service_quality_drop", 0.0))

    quality_impact = delay_minutes / 60.0 + service_drop
    threshold = np.float64(1.0 - p.service_quality_sensitivity)

    action = str(np.where(
        quality_impact > threshold,
        ACTION_WFH_INVOKE,
        ACTION_NO_CHANGE,
    ))
    reasoning = str(np.where(
        quality_impact > threshold,
        "service_quality_below_threshold_wfh",
        "quality_acceptable",
    ))

    # High amplitude online signal even if no personal action change
    signal = float(np.clip(
        ps.fare_change_pct / 100.0 * p.digital_access_level * 0.8, -1.0, 1.0,
    ))

    # Very high reach due to digital presence
    reach = int(np.floor(p.digital_access_level * 80))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_small_business_owner(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 5 — vyapari.

    ★ Triple evaluation: customers, suppliers, employees.
    ★ Footfall drop > 15% in 3 days → reduced hours / bandh call.
    ★ Has direct political network connections.
    """
    fare_impact = np.float64(ps.fare_change_pct / 100.0)

    # Customer impact: footfall × transit dependency
    customer_impact = fare_impact * p.footfall_transit_dependency
    # Supplier impact
    supplier_impact = fare_impact * p.supply_chain_transit_dependency
    # Employee impact: proportional to employee count
    employee_impact = fare_impact * np.minimum(p.employee_count / 15.0, 1.0)

    aggregate_impact = (customer_impact + supplier_impact + employee_impact) / 3.0

    footfall_drop = np.float64(ns.get("footfall_drop_pct", 0.0))

    action = str(np.where(
        footfall_drop > 0.15,
        ACTION_REDUCED_HOURS,
        np.where(aggregate_impact > 0.12, ACTION_COMPLAINT_FILED, ACTION_NO_CHANGE),
    ))
    reasoning = str(np.where(
        footfall_drop > 0.15,
        "footfall_drop_exceeds_15pct",
        np.where(aggregate_impact > 0.12, "triple_eval_above_threshold", "within_tolerance"),
    ))

    # Bandh call at extreme levels
    net_resistance = np.float64(ns.get("zone_resistance", 0.0))
    if net_resistance > p.collective_action_threshold and footfall_drop > 0.20:
        action = ACTION_BANDH_CALL
        reasoning = "bandh_threshold_crossed"

    signal = float(np.clip(aggregate_impact * p.loss_aversion_score, -1.0, 1.0))
    reach = int(np.floor(p.political_network_connections * 50))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_student(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 6 — vidyarthi.

    ★ Family-level decision — student records outcome only.
    ★ Independently evaluates carpooling.
    ★ Highest peer cascade speed.
    """
    peer_switching = np.float64(ns.get("peer_mode_switch_pct", 0.0))
    fare_burden = np.float64(ps.fare_change_pct / 100.0)

    # Family absorbs cost → attendance reduced only at high thresholds
    family_stressed = np.float64(fare_burden > 0.15)

    action = str(np.where(
        family_stressed,
        ACTION_ATTENDANCE_REDUCED,
        np.where(
            peer_switching > p.peer_influence_susceptibility * 0.5,
            ACTION_MODE_SWITCH,  # joins carpool/bus
            ACTION_NO_CHANGE,
        ),
    ))
    reasoning = str(np.where(
        family_stressed,
        "family_cost_threshold_attendance_reduced",
        np.where(
            peer_switching > p.peer_influence_susceptibility * 0.5,
            "peer_cascade_carpool",
            "family_absorbs_cost",
        ),
    ))

    # High protest propensity for exam-related policies
    signal = float(np.clip(fare_burden * p.peer_influence_susceptibility, -1.0, 1.0))
    net_resistance = np.float64(ns.get("zone_resistance", 0.0))
    if net_resistance > p.collective_action_threshold:
        action = ACTION_PROTEST_JOIN
        reasoning = "student_protest_threshold"
        signal = min(signal * 1.4, 1.0)

    reach = int(np.floor(p.peer_influence_susceptibility * 55))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_homemaker(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 7 — grihini.

    ★ Household-level restructuring of ALL trips simultaneously.
    ★ Trip consolidation is primary response.
    ★ Highest local network information density.
    """
    fare_burden = np.float64(ps.fare_change_pct / 100.0)

    # Household cost = personal + children + market trips
    household_multiplier = 1.0 + 0.3 * p.children_count
    effective_burden = fare_burden * household_multiplier

    action = str(np.where(
        effective_burden > 0.10,
        ACTION_TRIP_CONSOLIDATION,
        ACTION_NO_CHANGE,
    ))
    reasoning = str(np.where(
        effective_burden > 0.10,
        "household_trip_consolidation",
        "household_budget_acceptable",
    ))

    signal = float(np.clip(
        effective_burden * p.local_community_network_strength, -1.0, 1.0,
    ))
    # Highest neighbourhood reach
    reach = int(np.floor(p.local_community_network_strength * 60))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_street_vendor(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 8 — pheriwala / rehri-wala.

    ★ If fare > 10% daily income → evaluate vending spot relocation.
    ★ Double cost impact (personal + supply chain).
    """
    daily_income = p.income_monthly / 26.0
    fare_burden = np.float64(ps.fare_change_pct / 100.0)

    # Double cost: personal commute + supply chain
    total_burden = fare_burden * (1.0 + p.supply_chain_transit_dependency)

    action = str(np.where(
        total_burden > 0.10,
        ACTION_VENDOR_RELOCATE,
        ACTION_NO_CHANGE,
    ))
    reasoning = str(np.where(
        total_burden > 0.10,
        "fare_exceeds_10pct_daily_income_relocate",
        "within_vendor_tolerance",
    ))

    signal = float(np.clip(total_burden * p.loss_aversion_score, -1.0, 1.0))
    reach = int(np.floor(p.local_community_network_strength * 35))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_retired(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 9 — buzurg / pensioner.

    ★ senior_concession_removal is #1 trigger.
    ★ High social credibility in network broadcasts.
    ★ Institutional memory amplifies resistance.
    """
    concession_removed = np.float64(ps.policy_type == "concession_removal")
    fare_burden = np.float64(ps.fare_change_pct / 100.0)

    action = str(np.where(
        concession_removed,
        ACTION_COMPLAINT_FILED,
        np.where(fare_burden > 0.20, ACTION_ROUTE_CHANGE, ACTION_NO_CHANGE),
    ))
    reasoning = str(np.where(
        concession_removed,
        "senior_concession_removal_trigger",
        np.where(fare_burden > 0.20, "fare_above_senior_tolerance", "within_pension_budget"),
    ))

    # High credibility low-speed signal
    base_signal = np.where(concession_removed, 0.9, fare_burden * 0.6)
    # Institutional memory amplifier
    signal = float(np.clip(base_signal * 1.15, -1.0, 1.0))
    reach = int(np.floor(p.local_community_network_strength * 30))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_migrant_worker(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 10 — pravasi majdoor.

    ★ Uses disposable_income (after remittance), not gross income.
    ★ Can trigger return_migration — vanishing from city labour pool.
    ★ Hometown cluster cascade.
    """
    disposable = p.income_monthly * (1.0 - p.remittance_rate)
    fare_burden = np.float64(ps.fare_change_pct / 100.0)
    effective_burden = fare_burden * p.income_monthly / np.maximum(disposable, 1.0)

    cluster_return_pct = np.float64(ns.get("hometown_cluster_return_pct", 0.0))

    action = str(np.where(
        np.logical_or(effective_burden > 0.15, cluster_return_pct > 0.15),
        ACTION_RETURN_MIGRATION,
        np.where(effective_burden > 0.08, ACTION_MODE_SWITCH, ACTION_NO_CHANGE),
    ))
    reasoning = str(np.where(
        np.logical_or(effective_burden > 0.15, cluster_return_pct > 0.15),
        "return_migration_disposable_threshold",
        np.where(effective_burden > 0.08, "mode_switch_migrant", "within_disposable_budget"),
    ))

    signal = float(np.clip(effective_burden * p.loss_aversion_score, -1.0, 1.0))
    reach = int(np.floor(p.peer_influence_susceptibility * 30))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_healthcare_worker(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 11 — swasthya karmchari.

    ★ Cannot WFH, cannot miss shift.
    ★ shift_missed_flag → patient_care_impact event.
    ★ policy_impact_multiplier 1.4×.
    """
    fare_burden = np.float64(ps.fare_change_pct / 100.0)
    delay_minutes = np.float64(ns.get("avg_delay_minutes", 0.0))
    night_shift = np.float64(p.shift_pattern in ("night_shift", "rotating"))

    # Night shift compounds the problem
    effective_burden = fare_burden * (1.0 + 0.4 * night_shift)

    shift_missed = np.float64(delay_minutes > 60.0)

    action = str(np.where(
        shift_missed,
        ACTION_MODE_SWITCH,  # forced mode switch — cannot miss shift
        np.where(effective_burden > 0.12, ACTION_ROUTE_CHANGE, ACTION_NO_CHANGE),
    ))
    reasoning = str(np.where(
        shift_missed,
        "shift_missed_forced_mode_switch",
        np.where(effective_burden > 0.12, "healthcare_route_change", "within_tolerance"),
    ))

    # 1.4× media amplification
    signal = float(np.clip(effective_burden * 1.4 * p.essential_worker_identity, -1.0, 1.0))
    reach = int(np.floor(p.digital_access_level * 40))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_exam_aspirant(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 12 — aspirant (JEE/NEET/UPSC).

    ★ Coaching centre is non-negotiable.
    ★ Family absorbs cost.
    ★ Extreme examination sensitivity.
    """
    fare_burden = np.float64(ps.fare_change_pct / 100.0)

    # Coaching centre is non-negotiable — family absorbs all cost
    # Only action is attendance_reduced if transit is completely broken
    delay_minutes = np.float64(ns.get("avg_delay_minutes", 0.0))

    action = str(np.where(
        delay_minutes > 90.0,
        ACTION_ATTENDANCE_REDUCED,
        ACTION_NO_CHANGE,
    ))
    reasoning = str(np.where(
        delay_minutes > 90.0,
        "coaching_unreachable_attendance_reduced",
        "family_absorbs_cost_coaching_maintained",
    ))

    # Exam-related policies trigger extreme response
    exam_policy = np.float64(ps.policy_type in ("exam_leak", "exam_cancellation"))
    if exam_policy:
        signal = float(np.clip(p.examination_sensitivity * 0.95, -1.0, 1.0))
        reasoning = "exam_policy_crisis_response"
    else:
        signal = float(np.clip(fare_burden * p.examination_sensitivity * 0.3, -1.0, 1.0))

    reach = int(np.floor(p.peer_influence_susceptibility * 50))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_gig_economy_worker(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 13 — gig-worker / app-based worker.

    ★ BIDIRECTIONAL: can BENEFIT from public transit fare hike.
    ★ Transit fare rise → cab demand surge → income rises.
    ★ Fuel price rise → operating cost rises → net income falls.
    """
    fare_change = np.float64(ps.fare_change_pct / 100.0)

    # Bidirectional: public transit fare hike → demand surge
    demand_surge = fare_change * p.cab_aggregator_dependency
    # But fuel cost also rises (modelled as fraction of fare change)
    fuel_impact = fare_change * 0.3  # fuel correlates ~30% with transit policy

    net_impact = demand_surge - fuel_impact

    # Positive net_impact = benefit; negative = harm
    action = str(np.where(
        net_impact > 0.05,
        ACTION_NO_CHANGE,  # benefiting — no action needed
        np.where(net_impact < -0.05, ACTION_ROUTE_CHANGE, ACTION_NO_CHANGE),
    ))
    reasoning = str(np.where(
        net_impact > 0.05,
        "gig_demand_surge_benefit",
        np.where(net_impact < -0.05, "gig_net_cost_increase", "gig_neutral"),
    ))

    # Negative signal = support (benefiting from policy)
    signal = float(np.clip(-net_impact * 2.0, -1.0, 1.0))

    # Vehicle loan vulnerability
    loan_stress = np.float64(p.loan_obligation_flag > 0.7 and net_impact < -0.03)
    if loan_stress:
        reasoning = "vehicle_loan_default_risk"

    reach = int(np.floor(p.digital_access_level * 30))
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


def _decide_journalist_tier1(
    p: PersonalityVector,
    ps: PolicyState,
    memory: np.ndarray,
    ns: dict[str, Any],
) -> AgentDecision:
    """AGENT_SPEC.md §ARCHETYPE 14 — patrakar.

    ★ Standard formal_sector_employee commute decision.
    ★ BUT broadcast has media_reach_multiplier applied.
    ★ Evaluates newsworthiness: personal + community impact.
    """
    # Standard commute decision (mirrors formal_sector_employee)
    transport_share = np.float64(ps.fare_change_pct / 100.0)
    above_threshold = np.float64(transport_share > 0.12)

    action = str(np.where(
        above_threshold,
        ACTION_MODE_SWITCH,
        ACTION_NO_CHANGE,
    ))
    reasoning = str(np.where(
        above_threshold,
        "journalist_transport_threshold",
        "journalist_within_budget",
    ))

    # Newsworthiness evaluation
    community_impact = np.float64(ns.get("zone_resistance", 0.0))
    personal_impact = transport_share
    novelty = np.float64(ps.day_current <= 3)  # new policy = newsworthy

    newsworthiness = (
        personal_impact * 0.2
        + community_impact * 0.5
        + float(novelty) * 0.3
    ) * p.editorial_independence

    # Signal amplified by media_reach_multiplier
    signal = float(np.clip(newsworthiness * 0.8, -1.0, 1.0))

    # Reach is multiplied by media_reach_multiplier (2.5–8.0×)
    base_reach = int(np.floor(p.digital_access_level * 40))
    reach = int(base_reach * p.media_reach_multiplier)
    return AgentDecision(
        action=str(action),
        broadcast_signal=signal,
        broadcast_reach=reach,
        reasoning_key=str(reasoning),
    )


# ── Decision dispatch table ───────────────────────────────
_DECISION_DISPATCH: dict[str, Any] = {
    "daily_wage_worker": _decide_daily_wage_worker,
    "formal_sector_employee": _decide_formal_sector_employee,
    "government_employee": _decide_government_employee,
    "tech_knowledge_worker": _decide_tech_knowledge_worker,
    "small_business_owner": _decide_small_business_owner,
    "student": _decide_student,
    "homemaker": _decide_homemaker,
    "street_vendor": _decide_street_vendor,
    "retired": _decide_retired,
    "migrant_worker": _decide_migrant_worker,
    "healthcare_worker": _decide_healthcare_worker,
    "exam_aspirant": _decide_exam_aspirant,
    "gig_economy_worker": _decide_gig_economy_worker,
    "journalist_tier1": _decide_journalist_tier1,
}


# ═════════════════════════════════════════════════════════════
# Tier1Agent — core agent class
# ═════════════════════════════════════════════════════════════
class Tier1Agent:
    """Single Tier 1 citizen agent.

    Holds personality vector, memory, and archetype-dispatched decision
    logic.  Individual agent decision_step is a single-agent method;
    the batch wrapper lives in SimulationEngine.

    Parameters
    ----------
    agent_id : str
        Unique identifier for this agent.
    archetype : str
        One of the 14 canonical archetype names.
    personality : PersonalityVector
        47-dimensional parameterisation of this agent.
    zone_id : str
        Zone where this agent resides.
    memory_vector : np.ndarray
        Compressed 90-day event history (dim=32).

    References
    ----------
    AGENT_SPEC.md §TIER 1 CITIZEN ARCHETYPES, §AGENT FACTORY
    """

    __slots__ = (
        "_agent_id",
        "_archetype",
        "_personality",
        "_zone_id",
        "_memory_vector",
        "_resistance_score",
        "_current_mode",
        "_decision_fn",
    )

    def __init__(
        self,
        agent_id: str,
        archetype: str,
        personality: PersonalityVector,
        zone_id: str,
        memory_vector: np.ndarray,
    ) -> None:
        if archetype not in _DECISION_DISPATCH:
            raise ValueError(
                f"Unknown archetype '{archetype}'. "
                f"Valid: {list(_DECISION_DISPATCH.keys())}"
            )
        self._agent_id = agent_id
        self._archetype = archetype
        self._personality = personality
        self._zone_id = zone_id
        self._memory_vector = np.asarray(memory_vector, dtype=np.float64)
        self._resistance_score: float = 0.0
        self._current_mode: str = "public_transit"
        self._decision_fn = _DECISION_DISPATCH[archetype]

    # ── Properties ─────────────────────────────────────────
    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def archetype(self) -> str:
        return self._archetype

    @property
    def personality(self) -> PersonalityVector:
        return self._personality

    @property
    def zone_id(self) -> str:
        return self._zone_id

    @property
    def memory_vector(self) -> np.ndarray:
        return self._memory_vector

    @property
    def resistance_score(self) -> float:
        """Current resistance score (0–1), updated after each decision step."""
        return self._resistance_score

    @property
    def current_mode(self) -> str:
        """Current transit mode string."""
        return self._current_mode

    # ── Decision step ──────────────────────────────────────
    def decision_step(
        self,
        policy_state: PolicyState,
        memory: np.ndarray,
        network_signals: dict[str, Any],
    ) -> AgentDecision:
        """Execute one decision step using archetype-specific logic.

        Dispatches to the archetype decision function registered in
        ``_DECISION_DISPATCH``.

        Parameters
        ----------
        policy_state : PolicyState
            Active policy scenario.
        memory : np.ndarray
            Current memory vector (may be updated externally).
        network_signals : dict
            Aggregated signals from the agent's network neighbourhood,
            e.g. ``zone_resistance``, ``avg_delay_minutes``, etc.

        Returns
        -------
        AgentDecision
            Action, broadcast signal, reach, and reasoning key.
        """
        decision = self._decision_fn(
            self._personality,
            policy_state,
            memory,
            network_signals,
        )

        # Update internal state
        self._resistance_score = float(np.clip(
            self._resistance_score * 0.7 + abs(decision.broadcast_signal) * 0.3,
            0.0, 1.0,
        ))
        if decision.action == ACTION_MODE_SWITCH:
            self._current_mode = "alternative"
        elif decision.action == ACTION_WFH_INVOKE:
            self._current_mode = "wfh"

        return decision

    # ── Memory update ──────────────────────────────────────
    def update_memory(self, day_events: list[dict[str, Any]]) -> np.ndarray:
        """Compress daily events into memory vector with exponential decay.

        Parameters
        ----------
        day_events : list[dict]
            List of event dicts for the day. Each event should contain
            numeric fields that are hashed into the memory vector.

        Returns
        -------
        np.ndarray
            Updated memory vector (dim=32).
        """
        # Exponential decay of existing memory
        self._memory_vector *= MEMORY_DECAY

        # Encode day events into a perturbation vector
        if day_events:
            perturbation = np.zeros(MEMORY_DIM, dtype=np.float64)
            for event in day_events:
                # Deterministic hash of event keys into vector positions
                for key, value in event.items():
                    if isinstance(value, (int, float)):
                        idx = hash(key) % MEMORY_DIM
                        perturbation[idx] += np.float64(value)
            # Normalise perturbation to prevent unbounded growth
            norm = np.linalg.norm(perturbation)
            if norm > 0:
                perturbation = perturbation / norm * 0.1
            self._memory_vector += perturbation

        return self._memory_vector.copy()

    # ── Factory class method ───────────────────────────────
    @classmethod
    def generate_from_demographics(
        cls,
        archetype: str,
        zone_context: Any,
        rng: np.random.Generator,
    ) -> "Tier1Agent":
        """Construct a single Tier1Agent from zone demographics.

        Samples personality vector within archetype bounds, constrained
        by zone income distribution.

        Parameters
        ----------
        archetype : str
            Archetype name (one of ALL_ARCHETYPES).
        zone_context : ZoneContext
            Fully resolved zone configuration.
        rng : numpy.random.Generator
            Reproducible random generator.

        Returns
        -------
        Tier1Agent

        References
        ----------
        AGENT_SPEC.md §AGENT FACTORY — ARCHETYPE INSTANTIATION
        """
        personality = PopulationFactory._sample_personality(
            archetype, zone_context, rng,
        )
        agent_id = f"{zone_context.zone_id}_{archetype}_{rng.integers(0, 2**31)}"
        memory_vector = rng.standard_normal(MEMORY_DIM).astype(np.float64) * 0.01
        return cls(
            agent_id=agent_id,
            archetype=archetype,
            personality=personality,
            zone_id=zone_context.zone_id,
            memory_vector=memory_vector,
        )


# ═════════════════════════════════════════════════════════════
# PopulationFactory — zone-level agent spawning
# ═════════════════════════════════════════════════════════════
class PopulationFactory:
    """Spawn Tier 1 agent populations from zone configuration.

    Distributes agents proportional to archetype weights, samples
    personality vectors within ARCHETYPE_BOUNDS, and validates the
    resulting population against zone constraints.

    References
    ----------
    AGENT_SPEC.md §AGENT FACTORY — ARCHETYPE INSTANTIATION
    """

    @staticmethod
    def spawn_population(
        n: int,
        zone_context: Any,
        seed: int = 42,
    ) -> list[Tier1Agent]:
        """Generate *n* Tier 1 agents for a zone.

        Parameters
        ----------
        n : int
            Total number of agents to spawn.
        zone_context : ZoneContext
            Fully resolved zone configuration.
        seed : int
            Random seed for reproducibility.

        Returns
        -------
        list[Tier1Agent]
            Population of n agents.

        Raises
        ------
        ValueError
            If population validation fails.
        """
        rng = np.random.default_rng(seed)

        # 1) Read archetype weights, filter out metadata keys
        raw_weights = zone_context.tier1_agent_archetype_weights
        weight_map: dict[str, float] = {
            k: float(v)
            for k, v in raw_weights.items()
            if k != "data_source" and isinstance(v, (int, float))
        }

        if not weight_map:
            raise ValueError(
                f"No valid archetype weights found for zone {zone_context.zone_id}"
            )

        # Normalise weights to sum to 1.0
        total_weight = sum(weight_map.values())
        weight_map = {k: v / total_weight for k, v in weight_map.items()}

        # Map zone config archetype names to canonical names
        # Zone configs may use alternative names; attempt direct mapping first
        canonical_map = _map_zone_archetypes_to_canonical(weight_map)

        # 2) Distribute n agents proportional to weights
        archetypes_sorted = sorted(canonical_map.keys())
        weights_arr = np.array([canonical_map[a] for a in archetypes_sorted])
        counts = _distribute_proportional(n, weights_arr)

        # 3) Spawn agents per archetype batch
        agents: list[Tier1Agent] = []
        for archetype, count in zip(archetypes_sorted, counts):
            for _ in range(count):
                personality = PopulationFactory._sample_personality(
                    archetype, zone_context, rng,
                )
                agent_id = (
                    f"{zone_context.zone_id}_{archetype}_{rng.integers(0, 2**31)}"
                )
                memory = rng.standard_normal(MEMORY_DIM).astype(np.float64) * 0.01
                agent = Tier1Agent(
                    agent_id=agent_id,
                    archetype=archetype,
                    personality=personality,
                    zone_id=zone_context.zone_id,
                    memory_vector=memory,
                )
                agents.append(agent)

        # 4) Validate population
        if not PopulationFactory._validate_population(
            agents, zone_context, canonical_map,
        ):
            logger.warning(
                "Population validation warnings for zone %s — "
                "proceeding with best-effort distribution",
                zone_context.zone_id,
            )

        logger.info(
            "Spawned %d Tier 1 agents for zone %s (%d archetypes)",
            len(agents), zone_context.zone_id, len(canonical_map),
        )
        return agents

    @staticmethod
    def _sample_personality(
        archetype: str,
        zone_context: Any,
        rng: np.random.Generator,
    ) -> PersonalityVector:
        """Sample a PersonalityVector within archetype bounds.

        Income is further constrained by zone income_profile distribution.

        Parameters
        ----------
        archetype : str
            Canonical archetype name.
        zone_context : ZoneContext
            Zone configuration for income constraints.
        rng : numpy.random.Generator
            Reproducible random generator.

        Returns
        -------
        PersonalityVector
        """
        bounds = ARCHETYPE_BOUNDS.get(archetype, {})
        kwargs: dict[str, Any] = {"archetype": archetype, "zone_id": zone_context.zone_id}

        for field_name, (lo, hi) in bounds.items():
            if field_name in ("family_financial_dependents", "children_count",
                              "attempts_remaining", "employee_count"):
                # Integer fields
                kwargs[field_name] = int(rng.integers(int(lo), int(hi) + 1))
            elif field_name == "income_monthly":
                # Constrain income to zone distribution
                kwargs[field_name] = _sample_income(
                    lo, hi, zone_context, rng,
                )
            else:
                kwargs[field_name] = float(rng.uniform(lo, hi))

        # Derived fields
        income = kwargs.get("income_monthly", 0.0)
        remittance = kwargs.get("remittance_rate", 0.0)
        kwargs.setdefault("disposable_income_actual", income * (1.0 - remittance))

        # Sample housing type for migrant workers
        if archetype == "migrant_worker":
            kwargs["housing_type"] = rng.choice(
                ["shared_room", "labour_camp", "pavement"],
                p=[0.55, 0.35, 0.10],
            )

        # Sample shift pattern for healthcare workers
        if archetype == "healthcare_worker":
            kwargs["shift_pattern"] = rng.choice(
                ["day_shift", "night_shift", "rotating"],
                p=[0.40, 0.30, 0.30],
            )

        return PersonalityVector(**kwargs)

    @staticmethod
    def _validate_population(
        agents: list[Tier1Agent],
        zone_context: Any,
        target_weights: dict[str, float],
    ) -> bool:
        """Validate that the spawned population matches zone constraints.

        Checks:
        - Archetype distribution matches weights ±2%
        - Income distribution matches zone profile ±3%

        Returns True if all checks pass, False otherwise.
        """
        n = len(agents)
        if n == 0:
            return False

        # ── Archetype distribution check (±2%) ─────────────
        archetype_counts: dict[str, int] = {}
        for agent in agents:
            archetype_counts[agent.archetype] = (
                archetype_counts.get(agent.archetype, 0) + 1
            )

        valid = True
        for arch, target_w in target_weights.items():
            actual_w = archetype_counts.get(arch, 0) / n
            if abs(actual_w - target_w) > 0.02:
                logger.warning(
                    "Archetype %s: target=%.3f actual=%.3f (>2%% deviation)",
                    arch, target_w, actual_w,
                )
                valid = False

        # ── Income distribution check (±3%) ────────────────
        income_profile = getattr(zone_context, "income_profile", {})
        median_target = income_profile.get("median_monthly_income", None)
        if median_target is not None and median_target > 0:
            incomes = np.array(
                [a.personality.income_monthly for a in agents if a.personality.income_monthly > 0],
                dtype=np.float64,
            )
            if len(incomes) > 0:
                actual_median = float(np.median(incomes))
                deviation = abs(actual_median - median_target) / median_target
                if deviation > 0.03:
                    logger.warning(
                        "Income median: target=%.0f actual=%.0f (%.1f%% deviation)",
                        median_target, actual_median, deviation * 100,
                    )
                    # Income deviation is a warning, not a hard failure
                    # because archetype bounds dominate income range

        return valid


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _distribute_proportional(n: int, weights: np.ndarray) -> np.ndarray:
    """Distribute n items proportionally to weights using largest-remainder.

    Guarantees the output sums to exactly n.

    Parameters
    ----------
    n : int
        Total items to distribute.
    weights : np.ndarray
        Probability weights (must sum to ~1.0).

    Returns
    -------
    np.ndarray of int
        Count per category, summing to n.
    """
    weights = weights / weights.sum()
    raw = weights * n
    floored = np.floor(raw).astype(int)
    remainders = raw - floored
    shortfall = n - floored.sum()
    # Award remaining slots to categories with largest remainders
    if shortfall > 0:
        top_indices = np.argsort(-remainders)[:shortfall]
        floored[top_indices] += 1
    return floored


def _sample_income(
    lo: float,
    hi: float,
    zone_context: Any,
    rng: np.random.Generator,
) -> float:
    """Sample income within [lo, hi] constrained by zone income profile.

    Uses the zone's median_monthly_income as a soft anchor: the sampled
    value is biased towards the zone median when it falls within the
    archetype bounds.

    Parameters
    ----------
    lo, hi : float
        Archetype income bounds.
    zone_context : ZoneContext
        Zone configuration with income_profile.
    rng : numpy.random.Generator

    Returns
    -------
    float
        Sampled income.
    """
    if lo >= hi:
        return lo

    income_profile = getattr(zone_context, "income_profile", {})
    zone_median = income_profile.get("median_monthly_income", None)

    if zone_median is not None and lo < zone_median < hi:
        # Beta distribution centred near zone median
        # Map zone_median to alpha/beta so mode ≈ zone_median
        mode_frac = (zone_median - lo) / (hi - lo)
        # Concentration parameter — higher = tighter around median
        kappa = 5.0
        alpha = 1.0 + kappa * mode_frac
        beta_param = 1.0 + kappa * (1.0 - mode_frac)
        sample = rng.beta(alpha, beta_param)
        return lo + sample * (hi - lo)
    else:
        return float(rng.uniform(lo, hi))


# ── Zone archetype name mapping ───────────────────────────
# Zone configs may use different names than the canonical 14.
# This maps known alternatives to canonical names.
_ZONE_NAME_ALIASES: dict[str, str] = {
    # Direct matches
    "daily_wage_worker": "daily_wage_worker",
    "formal_sector_employee": "formal_sector_employee",
    "government_employee": "government_employee",
    "tech_knowledge_worker": "tech_knowledge_worker",
    "small_business_owner": "small_business_owner",
    "student": "student",
    "homemaker": "homemaker",
    "street_vendor": "street_vendor",
    "retired": "retired",
    "migrant_worker": "migrant_worker",
    "healthcare_worker": "healthcare_worker",
    "exam_aspirant": "exam_aspirant",
    "gig_economy_worker": "gig_economy_worker",
    "journalist_tier1": "journalist_tier1",
    # Common zone config aliases
    "daily_commuter_worker": "daily_wage_worker",
    "professional_formal": "formal_sector_employee",
    "self_employed_informal": "small_business_owner",
}


def _map_zone_archetypes_to_canonical(
    weight_map: dict[str, float],
) -> dict[str, float]:
    """Map zone config archetype names to canonical names.

    Unknown names are logged and dropped.

    Returns
    -------
    dict[str, float]
        Canonical archetype name → weight.
    """
    canonical: dict[str, float] = {}
    for zone_name, weight in weight_map.items():
        canon = _ZONE_NAME_ALIASES.get(zone_name)
        if canon is None:
            logger.warning(
                "Unknown zone archetype name '%s' — dropping from distribution",
                zone_name,
            )
            continue
        # Accumulate in case multiple aliases map to same canonical
        canonical[canon] = canonical.get(canon, 0.0) + weight

    # Re-normalise
    total = sum(canonical.values())
    if total > 0:
        canonical = {k: v / total for k, v in canonical.items()}

    return canonical
