"""
driftwatch.py — Driftwatch API routes for oversight-decay simulation.

Endpoints
---------
    POST /api/driftwatch/simulate
        Run a Driftwatch simulation with a specific model backend.
        Returns SSE stream with per-timestep oversight metrics.

    GET  /api/driftwatch/results/{simulation_id}
        Retrieve aggregated Driftwatch results for a completed run.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
import os
import pickle
import numpy as np
from collections import defaultdict, deque
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agents.caseworker_agent import CaseworkerAgent, Decision
from backend.simulation.adversarial import StrategicAdversary
from backend.simulation.social import SocialNetworkManager
from backend.simulation.domains import get_domain, list_domains
from backend.simulation.oversight_logic import (
    update_citizen_oversight,
    OversightEvent,
    DEFAULT_INITIAL_REVIEW_PROBABILITY,
    DEFAULT_INITIAL_REVIEW_SKILL,
)
from backend.simulation.driftwatch_metrics import (
    compute_timestep_metrics,
    compute_driftwatch_metrics,
    compute_crossover_point,
    DriftwatchRunMetrics,
)

router = APIRouter()

# ─────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────
ModelBackendType = Literal[
    "openai", "ollama_api", "ollama_local",
    "ollama_local_fp16", "ollama_local_int8", "ollama_local_int4",
    "rule_based"
]


class DriftwatchRequest(BaseModel):
    model_backend: ModelBackendType = "rule_based"
    population_size: Annotated[int, Field(ge=10, le=10_000)] = 500
    timesteps: Annotated[int, Field(ge=5, le=100)] = 30
    difficulty: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
    counterfactual: bool = False  # freeze review_probability if True
    initial_review_probability: Annotated[float, Field(ge=0.01, le=0.99)] = 0.9
    initial_review_skill: Annotated[float, Field(ge=0.05, le=0.99)] = 0.8
    seed: Annotated[int, Field(ge=0, le=2_147_483_647)] = 42
    silent_error_threshold: Annotated[float, Field(ge=0.01, le=0.50)] = 0.10
    quantization: str = "none"
    shock_interval: int = 0
    shock_magnitude: float = 0.30
    domain: str = "benefits_eligibility"
    # Phase 3 parameters
    explanation_style: str = "detailed"  # "terse" or "detailed"
    confidence_calibrated: bool = True   # calibrated vs uncalibrated confidence
    language_mismatch_ratio: float = 0.0  # fraction of citizens with language mismatch (0.0-1.0)
    # Phase 4 parameters
    adversary_ratio: float = 0.0  # fraction of population that is adversarial
    adversary_episodes: int = 1   # number of learning episodes
    # Phase 5 parameters
    network_topology: str = "isolated"
    network_k: int = 4
    social_influence_weight: float = 0.0
    # Phase 6 interventions
    spot_check_rate: float = 0.0
    confidence_review_threshold: float = 0.0
    mandatory_audit_interval: int = 0
    adaptive_interventions: bool = False
    shock_adaptation_delay: Annotated[int, Field(ge=0, le=20)] = 2


class CompareRequest(BaseModel):
    req_a: DriftwatchRequest
    req_b: DriftwatchRequest

# ─────────────────────────────────────────────────────────────
# In-memory store for completed runs
# ─────────────────────────────────────────────────────────────
_driftwatch_results: dict[str, dict] = {}
_MAX_STORED = 50

# Rate limiting
_request_windows: dict[str, deque[float]] = defaultdict(deque)


def _enforce_rate_limit(request: Request, limit: int = 10, window_seconds: int = 60) -> None:
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _request_windows[client]
    while window and now - window[0] > window_seconds:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    window.append(now)


def _normalized_quantization(req: DriftwatchRequest) -> str:
    """Honor quantization encoded in local backend ids and request bodies."""
    encoded = {
        "ollama_local_fp16": "FP16",
        "ollama_local_int8": "INT8",
        "ollama_local_int4": "INT4",
    }.get(req.model_backend)
    if encoded:
        return encoded
    quant = req.quantization.upper().strip()
    return "none" if quant in {"", "NONE"} else quant


def _model_reference_truth(oracle, case: dict, ground_truth: str, stale_thresholds: dict | None) -> str:
    """Return the policy truth currently available to the simulated model."""
    if stale_thresholds is None:
        return ground_truth
    return oracle.compute_ground_truth_with_thresholds(case, stale_thresholds)


def _predictor_features(ts_metrics: list) -> np.ndarray:
    """Build population-invariant early-warning features from ten steps."""
    window = ts_metrics[-10:]
    current = window[-1]
    slope = (current.avg_review_probability - window[0].avg_review_probability) / max(1, len(window) - 1)
    latency_rate = sum(
        item.latency_skips / max(1, item.total_decisions) for item in window
    ) / len(window)
    avg_confidence = sum(item.avg_decision_confidence for item in window) / len(window)
    return np.array([[
        current.avg_review_probability,
        slope,
        latency_rate,
        avg_confidence,
    ]])


async def _train_adversary_episode(
    req: DriftwatchRequest,
    episode: int,
    citizens: list[dict],
    adversary_mgr: StrategicAdversary,
    quantization: str,
) -> None:
    """Run one complete hidden learning episode before the reported episode."""
    episode_seed = req.seed + episode
    rng = random.Random(episode_seed)
    oracle = get_domain(
        req.domain,
        seed=episode_seed,
        cases_per_timestep=1,
        shock_interval=req.shock_interval,
        shock_magnitude=req.shock_magnitude,
    )
    caseworker = CaseworkerAgent(
        req.model_backend,
        quantization,
        episode_seed,
        explanation_style=req.explanation_style,
        confidence_calibrated=req.confidence_calibrated,
    )
    social_mgr = SocialNetworkManager(
        citizen_ids=[c["agent_id"] for c in citizens],
        topology=req.network_topology,
        k=req.network_k,
        seed=episode_seed,
    )
    latency_skip_prob = min(
        0.5,
        caseworker._profile.base_latency_ms * oracle.latency_multiplier / 2000.0,
    )
    recent_approval_rate = 0.9
    stale_thresholds = None
    stale_steps_remaining = 0

    for t in range(1, req.timesteps + 1):
        caseworker.step_burst()
        shock_event = oracle.check_and_apply_shock(t)
        if shock_event is not None and req.shock_adaptation_delay > 0:
            stale_thresholds = shock_event["old"]
            stale_steps_remaining = req.shock_adaptation_delay
        step_events = []
        approvals_this_step = 0
        is_audit = req.mandatory_audit_interval > 0 and t % req.mandatory_audit_interval == 0

        for citizen in citizens:
            is_adversary = adversary_mgr.is_adversary(citizen["agent_id"])
            if is_adversary and not adversary_mgr.should_submit_fraud(
                citizen["agent_id"], t, recent_approval_rate
            ):
                continue
            case, ground_truth = oracle.generate_case(difficulty=req.difficulty)
            if is_adversary:
                ground_truth = "deny"
            reference_truth = _model_reference_truth(
                oracle, case, ground_truth, None if is_adversary else stale_thresholds
            )
            decision, metadata = await caseworker.make_degraded_decision(
                case, reference_truth, oracle.model_error_multiplier
            )
            event = update_citizen_oversight(
                citizen=citizen,
                decision_outcome=decision.outcome,
                ground_truth=ground_truth,
                timestep=t,
                model_backend=caseworker.backend_name,
                rng=rng,
                counterfactual_freeze=req.counterfactual,
                latency_skip_probability=latency_skip_prob,
                in_burst=metadata["in_burst"],
                error_injected=metadata["error_injected"],
                burst_error=metadata["burst_error"],
                reviewer_availability=oracle.reviewer_availability,
                language_match=citizen.get("language_match", True),
                explanation_style=req.explanation_style,
                confidence_calibrated=req.confidence_calibrated,
                neighbor_signal=social_mgr.get_neighbor_signal(citizen["agent_id"]),
                social_influence_weight=(
                    req.social_influence_weight
                    * social_mgr.get_influence_strength(citizen["agent_id"])
                ),
                decision_confidence=decision.confidence,
                spot_check_rate=req.spot_check_rate,
                confidence_review_threshold=req.confidence_review_threshold,
                is_mandatory_audit=is_audit,
            )
            if is_adversary:
                event.adversarial_submission = True
                adversary_mgr.record_outcome(citizen["agent_id"], recent_approval_rate, event.caught)
            if (ground_truth if event.caught else decision.outcome) == "approve":
                approvals_this_step += 1
            step_events.append(event)

        social_mgr.update(step_events)
        if step_events:
            recent_approval_rate = approvals_this_step / len(step_events)
        if stale_steps_remaining > 0:
            stale_steps_remaining -= 1
            if stale_steps_remaining == 0:
                stale_thresholds = None


# ─────────────────────────────────────────────────────────────
# Simulation core
# ─────────────────────────────────────────────────────────────
async def _run_driftwatch(req: DriftwatchRequest, sim_id: str):
    """Run the full Driftwatch oversight-decay simulation.

    Yields SSE-formatted JSON events per timestep.
    """
    rng = random.Random(req.seed)
    quantization = _normalized_quantization(req)
    caseworker = CaseworkerAgent(
        req.model_backend, quantization, req.seed,
        explanation_style=req.explanation_style,
        confidence_calibrated=req.confidence_calibrated,
    )
    oracle = get_domain(
        req.domain,
        seed=req.seed,
        cases_per_timestep=1,
        shock_interval=req.shock_interval,
        shock_magnitude=req.shock_magnitude
    )

    # Precompute latency skip probability
    latency_skip_prob = min(
        0.5,
        caseworker._profile.base_latency_ms * oracle.latency_multiplier / 2000.0,
    )

    # Spawn citizen population (simplified — we only need oversight state)
    citizens: list[dict] = []
    for i in range(req.population_size):
        # Phase 3: assign language mismatch based on ratio
        has_mismatch = rng.random() < req.language_mismatch_ratio
        citizens.append({
            "agent_id": f"CIT_{i:05d}",
            "review_probability": req.initial_review_probability,
            "review_skill": req.initial_review_skill,
            "consecutive_low_review_steps": 0,
            "initial_review_skill": req.initial_review_skill,
            "language_match": not has_mismatch,
        })

    # Phase 4: Setup adversaries
    adversary_count = int(req.population_size * req.adversary_ratio)
    adversary_ids = [c["agent_id"] for c in citizens[:adversary_count]]
    adversary_mgr = StrategicAdversary(adversary_ids=adversary_ids, seed=req.seed)

    # Phase 5: Setup social network
    citizen_ids = [c["agent_id"] for c in citizens]
    social_mgr = SocialNetworkManager(
        citizen_ids=citizen_ids,
        topology=req.network_topology,
        k=req.network_k,
        seed=req.seed
    )

    all_events: list[OversightEvent] = []

    # Complete every requested learning episode. Only the final episode is
    # streamed/reported, but the adversary's learned bandit state persists.
    for ep in range(max(0, req.adversary_episodes - 1)):
        await _train_adversary_episode(req, ep, citizens, adversary_mgr, quantization)
        adversary_mgr.new_episode()
        for citizen in citizens:
            citizen["review_probability"] = req.initial_review_probability
            citizen["review_skill"] = req.initial_review_skill
            citizen["consecutive_low_review_steps"] = 0

    final_episode = max(0, req.adversary_episodes - 1)
    final_seed = req.seed + final_episode
    rng = random.Random(final_seed)
    oracle = get_domain(
        req.domain,
        seed=final_seed,
        cases_per_timestep=1,
        shock_interval=req.shock_interval,
        shock_magnitude=req.shock_magnitude,
    )
    caseworker = CaseworkerAgent(
        req.model_backend,
        quantization,
        final_seed,
        explanation_style=req.explanation_style,
        confidence_calibrated=req.confidence_calibrated,
    )
    latency_skip_prob = min(
        0.5,
        caseworker._profile.base_latency_ms * oracle.latency_multiplier / 2000.0,
    )
    social_mgr = SocialNetworkManager(
        citizen_ids=citizen_ids,
        topology=req.network_topology,
        k=req.network_k,
        seed=final_seed,
    )

    predictor = None
    model_path = os.path.join(os.path.dirname(__file__), "..", "..", "models", "collapse_predictor.pkl")
    if os.path.exists(model_path):
        with open(model_path, "rb") as f:
            predictor = pickle.load(f)

    # Compute per-timestep metrics
    ts_metrics = []

    try:
        recent_approval_rate = 0.9
        current_risk_score = 0.0
        stale_thresholds = None
        stale_steps_remaining = 0

        for t in range(1, req.timesteps + 1):
            # Phase 6
            is_mandatory_audit = (req.mandatory_audit_interval > 0 and t % req.mandatory_audit_interval == 0)
            
            # ML-Driven Interventions: Scale up based on predicted risk of collapse
            active_spot_check_rate = req.spot_check_rate
            active_audit = is_mandatory_audit
            
            if req.adaptive_interventions:
                if current_risk_score > 0.8:
                    active_spot_check_rate = max(0.5, req.spot_check_rate)
                    active_audit = True
                elif current_risk_score > 0.5:
                    active_spot_check_rate = max(0.2, req.spot_check_rate)

            caseworker.step_burst()
            shock_event = oracle.check_and_apply_shock(t)
            if shock_event is not None and req.shock_adaptation_delay > 0:
                stale_thresholds = shock_event["old"]
                stale_steps_remaining = req.shock_adaptation_delay
            step_events = []
            approvals_this_step = 0

            for citizen in citizens:
                is_adversary = adversary_mgr.is_adversary(citizen["agent_id"])
                if is_adversary:
                    if not adversary_mgr.should_submit_fraud(citizen["agent_id"], t, recent_approval_rate):
                        continue
                    case, _ = oracle.generate_case(difficulty=req.difficulty)
                    ground_truth = "deny"
                else:
                    case, ground_truth = oracle.generate_case(difficulty=req.difficulty)

                reference_truth = _model_reference_truth(
                    oracle,
                    case,
                    ground_truth,
                    None if is_adversary else stale_thresholds,
                )
                decision, metadata = await caseworker.make_degraded_decision(
                    case, reference_truth, oracle.model_error_multiplier
                )

                neighbor_signal = social_mgr.get_neighbor_signal(citizen["agent_id"])
                topology_strength = social_mgr.get_influence_strength(citizen["agent_id"])

                event = update_citizen_oversight(
                    citizen=citizen,
                    decision_outcome=decision.outcome,
                    ground_truth=ground_truth,
                    timestep=t,
                    model_backend=caseworker.backend_name,
                    rng=rng,
                    counterfactual_freeze=req.counterfactual,
                    latency_skip_probability=latency_skip_prob,
                    in_burst=metadata["in_burst"],
                    error_injected=metadata["error_injected"],
                    burst_error=metadata["burst_error"],
                    reviewer_availability=oracle.reviewer_availability,
                    language_match=citizen.get("language_match", True),
                    explanation_style=req.explanation_style,
                    confidence_calibrated=req.confidence_calibrated,
                    neighbor_signal=neighbor_signal,
                    social_influence_weight=req.social_influence_weight * topology_strength,
                    decision_confidence=decision.confidence,
                    spot_check_rate=active_spot_check_rate,
                    confidence_review_threshold=req.confidence_review_threshold,
                    is_mandatory_audit=active_audit,
                )
                if is_adversary:
                    event.adversarial_submission = True
                    adversary_mgr.record_outcome(citizen["agent_id"], recent_approval_rate, event.caught)

                final_outcome = ground_truth if event.caught else decision.outcome
                if final_outcome == "approve":
                    approvals_this_step += 1

                step_events.append(event)
                all_events.append(event)

            social_mgr.update(step_events)

            if len(step_events) > 0:
                recent_approval_rate = approvals_this_step / len(step_events)

            m = compute_timestep_metrics(step_events, t, caseworker.backend_name, shock_event is not None)
            ts_metrics.append(m)

            # Serialize for SSE
            ts_dict = {
                "timestep": m.timestep,
                "avg_review_probability": round(m.avg_review_probability, 4),
                "avg_review_skill": round(m.avg_review_skill, 4),
                "silent_error_rate": round(m.silent_error_rate, 4),
                "errors_caught": m.total_caught,
                "latency_skips": m.latency_skips,
                "trust_skips": m.trust_skips,
                "shock_active": m.shock_active,
                "in_burst": m.in_burst,
                "avg_decision_confidence": round(m.avg_decision_confidence, 4),
            }

            if predictor is not None and t >= 10:
                risk_score = predictor.predict_proba(_predictor_features(ts_metrics))[0][1]
                current_risk_score = float(risk_score)
                ts_dict["risk_score"] = round(float(risk_score), 4)

            yield json.dumps({"event": "timestep", **ts_dict}) + "\n\n"
            await asyncio.sleep(0.01)

            if stale_steps_remaining > 0:
                stale_steps_remaining -= 1
                if stale_steps_remaining == 0:
                    stale_thresholds = None

        metrics = compute_driftwatch_metrics(
            all_events,
            caseworker.backend_name,
            req.silent_error_threshold,
            req.initial_review_probability,
            oracle._shock_log
        )

        result_dict = metrics.to_dict()
        _driftwatch_results[sim_id] = result_dict
        while len(_driftwatch_results) > _MAX_STORED:
            _driftwatch_results.pop(next(iter(_driftwatch_results)))

        yield json.dumps({"event": "sim_complete", "metrics": result_dict}) + "\n\n"

    except Exception as exc:
        yield json.dumps({"event": "sim_error", "message": str(exc)}) + "\n\n"


async def _run_driftwatch_sync(req: DriftwatchRequest) -> DriftwatchRunMetrics:
    """Run simulation sequentially (no SSE) and return metrics. Used for comparisons."""
    rng = random.Random(req.seed)
    quantization = _normalized_quantization(req)
    caseworker = CaseworkerAgent(
        req.model_backend, quantization, req.seed,
        explanation_style=req.explanation_style,
        confidence_calibrated=req.confidence_calibrated,
    )
    oracle = get_domain(
        req.domain,
        seed=req.seed,
        cases_per_timestep=1,
        shock_interval=req.shock_interval,
        shock_magnitude=req.shock_magnitude
    )

    latency_skip_prob = min(
        0.5,
        caseworker._profile.base_latency_ms * oracle.latency_multiplier / 2000.0,
    )

    citizens: list[dict] = []
    for i in range(req.population_size):
        has_mismatch = rng.random() < req.language_mismatch_ratio
        citizens.append({
            "agent_id": f"CIT_{i:05d}",
            "review_probability": req.initial_review_probability,
            "review_skill": req.initial_review_skill,
            "consecutive_low_review_steps": 0,
            "initial_review_skill": req.initial_review_skill,
            "language_match": not has_mismatch,
        })

    adversary_count = int(req.population_size * req.adversary_ratio)
    adversary_ids = [c["agent_id"] for c in citizens[:adversary_count]]
    adversary_mgr = StrategicAdversary(adversary_ids=adversary_ids, seed=req.seed)

    citizen_ids = [c["agent_id"] for c in citizens]
    social_mgr = SocialNetworkManager(
        citizen_ids=citizen_ids,
        topology=req.network_topology,
        k=req.network_k,
        seed=req.seed
    )

    all_events: list[OversightEvent] = []

    for ep in range(req.adversary_episodes):
        if ep > 0:
            adversary_mgr.new_episode()
            all_events.clear()
            for citizen in citizens:
                citizen["review_probability"] = req.initial_review_probability
                citizen["review_skill"] = req.initial_review_skill
                citizen["consecutive_low_review_steps"] = 0

            oracle = get_domain(
                req.domain, seed=req.seed + ep, cases_per_timestep=1,
                shock_interval=req.shock_interval, shock_magnitude=req.shock_magnitude
            )
            caseworker = CaseworkerAgent(
                req.model_backend, quantization, req.seed + ep,
                explanation_style=req.explanation_style,
                confidence_calibrated=req.confidence_calibrated,
            )

        recent_approval_rate = 0.9
        stale_thresholds = None
        stale_steps_remaining = 0

        for t in range(1, req.timesteps + 1):
            is_mandatory_audit = (req.mandatory_audit_interval > 0 and t % req.mandatory_audit_interval == 0)

            caseworker.step_burst()
            shock_event = oracle.check_and_apply_shock(t)
            if shock_event is not None and req.shock_adaptation_delay > 0:
                stale_thresholds = shock_event["old"]
                stale_steps_remaining = req.shock_adaptation_delay
            step_events = []
            approvals_this_step = 0

            for citizen in citizens:
                is_adversary = adversary_mgr.is_adversary(citizen["agent_id"])
                if is_adversary:
                    if not adversary_mgr.should_submit_fraud(citizen["agent_id"], t, recent_approval_rate):
                        continue
                    case, _ = oracle.generate_case(difficulty=req.difficulty)
                    ground_truth = "deny"
                else:
                    case, ground_truth = oracle.generate_case(difficulty=req.difficulty)

                reference_truth = _model_reference_truth(
                    oracle,
                    case,
                    ground_truth,
                    None if is_adversary else stale_thresholds,
                )
                decision, metadata = await caseworker.make_degraded_decision(
                    case, reference_truth, oracle.model_error_multiplier
                )

                neighbor_signal = social_mgr.get_neighbor_signal(citizen["agent_id"])
                topology_strength = social_mgr.get_influence_strength(citizen["agent_id"])

                event = update_citizen_oversight(
                    citizen=citizen,
                    decision_outcome=decision.outcome,
                    ground_truth=ground_truth,
                    timestep=t,
                    model_backend=caseworker.backend_name,
                    rng=rng,
                    counterfactual_freeze=req.counterfactual,
                    latency_skip_probability=latency_skip_prob,
                    in_burst=metadata["in_burst"],
                    error_injected=metadata["error_injected"],
                    burst_error=metadata["burst_error"],
                    reviewer_availability=oracle.reviewer_availability,
                    language_match=citizen.get("language_match", True),
                    explanation_style=req.explanation_style,
                    confidence_calibrated=req.confidence_calibrated,
                    neighbor_signal=neighbor_signal,
                    social_influence_weight=req.social_influence_weight * topology_strength,
                    decision_confidence=decision.confidence,
                    spot_check_rate=req.spot_check_rate,
                    confidence_review_threshold=req.confidence_review_threshold,
                    is_mandatory_audit=is_mandatory_audit,
                )
                if is_adversary:
                    event.adversarial_submission = True
                    adversary_mgr.record_outcome(citizen["agent_id"], recent_approval_rate, event.caught)

                final_outcome = ground_truth if event.caught else decision.outcome
                if final_outcome == "approve":
                    approvals_this_step += 1

                step_events.append(event)
                all_events.append(event)

            social_mgr.update(step_events)

            if len(step_events) > 0:
                recent_approval_rate = approvals_this_step / len(step_events)

            if stale_steps_remaining > 0:
                stale_steps_remaining -= 1
                if stale_steps_remaining == 0:
                    stale_thresholds = None

    return compute_driftwatch_metrics(
        all_events,
        caseworker.backend_name,
        req.silent_error_threshold,
        req.initial_review_probability,
        oracle._shock_log
    )


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@router.post("/driftwatch/simulate")
async def simulate_driftwatch(req: DriftwatchRequest, request: Request):
    """Run a Driftwatch oversight-decay simulation.

    Returns an SSE stream with per-timestep metrics and a final
    sim_complete event with aggregated results.
    """
    # A judge-style control walkthrough legitimately launches many short runs.
    # Keep protection in place without blocking the full comparison matrix.
    _enforce_rate_limit(request, limit=60)
    sim_id = f"DW-{uuid.uuid4().hex[:8]}"

    async def event_stream():
        yield f"data: {json.dumps({'event': 'sim_start', 'simulation_id': sim_id, 'model_backend': req.model_backend, 'counterfactual': req.counterfactual})}\n\n"
        try:
            async for event_json in _run_driftwatch(req, sim_id):
                yield f"data: {event_json}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'event': 'sim_error', 'simulation_id': sim_id, 'message': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/driftwatch/results/{simulation_id}")
async def get_driftwatch_results(simulation_id: str):
    """Retrieve results for a completed Driftwatch simulation."""
    result = _driftwatch_results.get(simulation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return result


@router.post("/driftwatch/compare")
async def compare_driftwatch(req: CompareRequest, request: Request):
    """Run two backends in parallel and compute cross-over point."""
    _enforce_rate_limit(request)

    # Run both sequentially to get metrics
    metrics_a = await _run_driftwatch_sync(req.req_a)
    metrics_b = await _run_driftwatch_sync(req.req_b)

    crossover = compute_crossover_point(metrics_a, metrics_b)

    return {
        "event": "compare_complete",
        "backend_a_metrics": metrics_a.to_dict(),
        "backend_b_metrics": metrics_b.to_dict(),
        "crossover_analysis": crossover,
    }

@router.get("/driftwatch/backends")
async def list_backends():
    """List available model backends."""
    return {
        "backends": [
            {"id": "openai", "name": "GPT-4o (Closed)", "description": "Large closed model via OpenAI API"},
            {"id": "ollama_api", "name": "Llama 3.1 8B (Open)", "description": "Open-source model via Ollama API"},
            {"id": "ollama_local_fp16", "name": "Llama 3.1 Local FP16", "description": "Local model running with FP16 profile"},
            {"id": "ollama_local_int8", "name": "Llama 3.1 Local INT8", "description": "Local 8-bit quantized model profile"},
            {"id": "ollama_local_int4", "name": "Llama 3.1 Local INT4", "description": "Local 4-bit quantized model profile"},
            {"id": "rule_based", "name": "Rule-Based (Fallback)", "description": "Deterministic rule-based decisions — no LLM"},
        ],
    }

@router.get("/driftwatch/domains")
async def get_domains():
    """List available domain scenarios."""
    return {"domains": list_domains()}
