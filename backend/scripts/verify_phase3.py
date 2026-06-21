#!/usr/bin/env python3
"""
verify_phase3.py — Verification script for Phase 3 Depth variables.

Runs a matrix of Driftwatch simulations to verify:
1. Language Mismatch vs Match
2. Calibrated vs Uncalibrated Confidence (burst errors)
3. Skill Atrophy and Divergence (Probability vs Skill)
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.api.routes.driftwatch import _run_driftwatch_sync, DriftwatchRequest

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_phase3")

async def run_experiment(name: str, req: DriftwatchRequest):
    logger.info(f"--- Running Experiment: {name} ---")
    metrics = await _run_driftwatch_sync(req)
    
    print(f"Results for {name}:")
    print(f"  Backend: {metrics.model_backend}")
    print(f"  Time to 10% Silent Errors: {metrics.time_to_threshold or 'Never'}")
    print(f"  Final Review Probability: {metrics.final_avg_review_probability:.2%}")
    print(f"  Final Review Skill: {metrics.final_avg_review_skill:.2%}")
    print(f"  Skill Recovery Rate: +{metrics.skill_recovery_rate * 100:.3f}%/step")
    print(f"  Final Silent Error Rate: {metrics.final_silent_error_rate:.2%}")
    print(f"  Total Language Mismatch Errors: {metrics.language_mismatch_errors}")
    print(f"  Burst Error Contribution: {metrics.burst_error_contribution:.2%}")
    print()
    return metrics

async def main():
    logger.info("Starting Phase 3 Verification Matrix...")

    # 1. Language Mismatch Test
    # Compare 0% mismatch vs 50% mismatch
    base_req = DriftwatchRequest(
        model_backend="ollama_local",
        quantization="int8",
        population_size=500,
        timesteps=30,
        domain="benefits_eligibility",
        initial_review_probability=0.9,
        initial_review_skill=0.8,
        seed=101
    )
    
    req_lang_match = base_req.model_copy(update={"language_mismatch_ratio": 0.0})
    req_lang_mismatch = base_req.model_copy(update={"language_mismatch_ratio": 0.5})
    
    await run_experiment("Language MATCH (0% mismatch)", req_lang_match)
    await run_experiment("Language MISMATCH (50% mismatch)", req_lang_mismatch)

    # 2. Explainability & Calibration Test during Bursts
    # Compare calibrated vs uncalibrated with bursts
    base_burst_req = base_req.model_copy(update={
        "model_backend": "ollama_local", 
        "quantization": "int4", # higher burst prob
    })
    
    req_calibrated = base_burst_req.model_copy(update={"confidence_calibrated": True})
    req_uncalibrated = base_burst_req.model_copy(update={"confidence_calibrated": False})
    
    await run_experiment("Calibrated Confidence (INT4)", req_calibrated)
    await run_experiment("Uncalibrated Confidence (INT4)", req_uncalibrated)

    # 3. Terse Explanations vs Detailed
    req_detailed = base_req.model_copy(update={"explanation_style": "detailed"})
    req_terse = base_req.model_copy(update={"explanation_style": "terse"})
    
    await run_experiment("Detailed Explanations", req_detailed)
    await run_experiment("Terse Explanations", req_terse)
    
    # 4. Atrophy & Recovery Test (with Shock)
    req_shock = base_req.model_copy(update={
        "timesteps": 40,
        "shock_interval": 20,
        "shock_magnitude": 0.40,
        "language_mismatch_ratio": 0.2
    })
    await run_experiment("Skill Atrophy & Recovery (Shock @ T=20)", req_shock)

if __name__ == "__main__":
    asyncio.run(main())
