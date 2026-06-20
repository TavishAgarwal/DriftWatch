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
from collections import defaultdict, deque
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agents.caseworker_agent import CaseworkerAgent, Decision
from backend.simulation.case_oracle import CaseOracle
from backend.simulation.oversight_logic import (
    update_citizen_oversight,
    OversightEvent,
    DEFAULT_INITIAL_REVIEW_PROBABILITY,
    DEFAULT_INITIAL_REVIEW_SKILL,
)
from backend.simulation.driftwatch_metrics import (
    compute_timestep_metrics,
    compute_driftwatch_metrics,
    DriftwatchRunMetrics,
)

router = APIRouter()

# ─────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────
ModelBackendType = Literal["openai", "ollama_api", "ollama_local", "rule_based"]


class DriftwatchRequest(BaseModel):
    model_backend: ModelBackendType = "rule_based"
    population_size: Annotated[int, Field(ge=1, le=5_000)] = 500
    timesteps: Annotated[int, Field(ge=1, le=100)] = 30
    difficulty: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
    counterfactual: bool = False  # freeze review_probability if True
    initial_review_probability: Annotated[float, Field(ge=0.01, le=0.99)] = 0.9
    initial_review_skill: Annotated[float, Field(ge=0.05, le=0.99)] = 0.8
    seed: Annotated[int, Field(ge=0, le=2_147_483_647)] = 42
    silent_error_threshold: Annotated[float, Field(ge=0.01, le=0.50)] = 0.10


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


# ─────────────────────────────────────────────────────────────
# Simulation core
# ─────────────────────────────────────────────────────────────
async def _run_driftwatch(req: DriftwatchRequest, sim_id: str):
    """Run the full Driftwatch oversight-decay simulation.

    Yields SSE-formatted JSON events per timestep.
    """
    rng = random.Random(req.seed)
    caseworker = CaseworkerAgent(req.model_backend)
    oracle = CaseOracle(seed=req.seed, cases_per_timestep=1)

    # Spawn citizen population (simplified — we only need oversight state)
    citizens: list[dict] = []
    for i in range(req.population_size):
        citizens.append({
            "agent_id": f"CIT_{i:05d}",
            "review_probability": req.initial_review_probability,
            "review_skill": req.initial_review_skill,
            "consecutive_low_review_steps": 0,
        })

    all_events: list[OversightEvent] = []
    timestep_summaries: list[dict] = []
    fallback_warning_sent = False

    for t in range(1, req.timesteps + 1):
        step_events: list[OversightEvent] = []

        semaphore = asyncio.Semaphore(50)  # Limit concurrent API calls to prevent rate limits

        async def process_citizen(citizen: dict) -> OversightEvent:
            # Generate a case for this citizen
            case, ground_truth = oracle.generate_case(difficulty=req.difficulty)

            # Caseworker makes a decision with concurrency limit
            async with semaphore:
                decision: Decision = await caseworker.decide(case.to_dict())

            # Citizen oversight step
            return update_citizen_oversight(
                citizen=citizen,
                decision_outcome=decision.outcome,
                ground_truth=ground_truth,
                timestep=t,
                model_backend=caseworker.backend_name,
                rng=rng,
                counterfactual_freeze=req.counterfactual,
            )

        tasks = [process_citizen(c) for c in citizens]
        step_events = list(await asyncio.gather(*tasks))

        # After the first timestep, check if fallback was used
        if not fallback_warning_sent and caseworker.fallback_active:
            fallback_warning_sent = True
            yield json.dumps({
                "event": "backend_fallback",
                "simulation_id": sim_id,
                "requested_backend": req.model_backend,
                "actual_backend": "rule_based",
                "message": (
                    f"'{req.model_backend}' backend unavailable "
                    f"(missing API key or service not running). "
                    f"Using rule-based fallback — results will be identical "
                    f"to the Rule-Based backend."
                ),
            })

        all_events.extend(step_events)

        # Compute per-timestep metrics
        ts_metrics = compute_timestep_metrics(
            step_events, t, caseworker.backend_name
        )
        summary = {
            "timestep": t,
            "avg_review_probability": round(ts_metrics.avg_review_probability, 4),
            "avg_review_skill": round(ts_metrics.avg_review_skill, 4),
            "silent_error_rate": round(ts_metrics.silent_error_rate, 4),
            "total_decisions": ts_metrics.total_decisions,
            "total_errors": ts_metrics.total_errors,
            "total_caught": ts_metrics.total_caught,
            "total_reviewed": ts_metrics.total_reviewed,
        }
        timestep_summaries.append(summary)

        yield json.dumps({
            "event": "timestep_update",
            "simulation_id": sim_id,
            "model_backend": caseworker.backend_name,
            "counterfactual": req.counterfactual,
            **summary,
        })

        # Yield control to event loop between timesteps
        await asyncio.sleep(0)

    # Compute full-run metrics
    run_metrics = compute_driftwatch_metrics(
        all_events, caseworker.backend_name, req.silent_error_threshold
    )

    result = {
        "event": "sim_complete",
        "simulation_id": sim_id,
        "model_backend": caseworker.backend_name,
        "counterfactual": req.counterfactual,
        "fallback_active": caseworker.fallback_active,
        "metrics": run_metrics.to_dict(),
    }

    # Store for later retrieval
    _driftwatch_results[sim_id] = result
    while len(_driftwatch_results) > _MAX_STORED:
        _driftwatch_results.pop(next(iter(_driftwatch_results)))

    yield json.dumps(result)



# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@router.post("/driftwatch/simulate")
async def simulate_driftwatch(req: DriftwatchRequest, request: Request):
    """Run a Driftwatch oversight-decay simulation.

    Returns an SSE stream with per-timestep metrics and a final
    sim_complete event with aggregated results.
    """
    _enforce_rate_limit(request)
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


@router.get("/driftwatch/backends")
async def list_backends():
    """List available model backends."""
    return {
        "backends": [
            {"id": "openai", "name": "GPT-4o (Closed)", "description": "Large closed model via OpenAI API"},
            {"id": "ollama_api", "name": "Llama 3.1 8B (Open)", "description": "Open-source model via Ollama API"},
            {"id": "ollama_local", "name": "Llama 3.1 Q4 (Local)", "description": "Quantized model running locally via Ollama"},
            {"id": "rule_based", "name": "Rule-Based (Fallback)", "description": "Deterministic rule-based decisions — no LLM"},
        ],
    }
