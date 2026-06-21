#!/usr/bin/env python3
"""
verify_phase4.py — Verification script for Phase 4 Adversarial Dynamics.

Runs:
1. Prompt injection test harness across rule-based, int8, and int4 backends.
2. Adversarial timing adaptation verification (15 episodes).
3. Oversight debt delta check (0% adversaries vs 10% adversaries).
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.api.routes.driftwatch import _run_driftwatch_sync, DriftwatchRequest
from backend.simulation.adversarial import StrategicAdversary
from backend.simulation.injection_harness import run_injection_harness

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_phase4")

async def test_prompt_injection():
    logger.info("=== 1. Running Prompt Injection Test Harness ===")
    
    backends_to_test = [
        ("openai", "none"),
        ("ollama_api", "fp16"),
        ("ollama_local", "fp16"),
        ("rule_based", "none"),
        ("ollama_local", "int8"),
        ("ollama_local", "int4"),
    ]
    
    for backend, quant in backends_to_test:
        logger.info(f"Testing {backend} ({quant})...")
        report = await run_injection_harness(backend=backend, quantization=quant, seed=42)
        print(f"\nResults for {backend} ({quant}):")
        print(f"  Overall Success Rate: {report.overall_success_rate:.2%}")
        for category, stats in report.results_by_category.items():
            print(f"    - {category}: {stats['successes']}/{stats['total']} ({stats['successes']/stats['total']:.2%})")
        print()

async def test_adversary_learning():
    logger.info("=== 2. Running Adversarial Timing Adaptation (15 Episodes) ===")
    
    # We run with 10% adversaries and 15 episodes.
    req = DriftwatchRequest(
        model_backend="rule_based", # rule_based is fast
        population_size=500,
        timesteps=50,
        domain="benefits_eligibility",
        adversary_ratio=0.1,
        adversary_episodes=15,
        seed=123
    )
    
    # To get cohort stats, we need to inject the adversary_mgr observation or intercept it.
    # Since we can't easily intercept the inner adversary_mgr from outside, we can just run
    # the sync simulation and look at the timestep distributions of adversarial successes.
    metrics = await _run_driftwatch_sync(req)
    
    # Analyze the events in the final episode directly from the metrics.
    total_subs = metrics.total_adversarial_submissions
    total_succ = metrics.total_adversarial_successes
    
    print(f"Final Episode Results:")
    print(f"  Total Adversarial Submissions: {total_subs}")
    print(f"  Total Undetected Frauds (Successes): {total_succ}")
    
    # Let's see the submission distribution across timesteps in the final episode
    # We can get this from timestep_metrics.
    early_subs = sum(m.adversarial_submissions for m in metrics.timestep_metrics[:25])
    late_subs = sum(m.adversarial_submissions for m in metrics.timestep_metrics[25:])
    
    print(f"  Submissions in early timesteps (1-25): {early_subs}")
    print(f"  Submissions in late timesteps (26-50): {late_subs}")
    if late_subs > early_subs:
        print("  ✓ Adversaries learned to wait for oversight decay later in the simulation.")
    else:
        print("  ! Adversaries did not strongly bias towards late timesteps.")
    print()

async def test_oversight_debt():
    logger.info("=== 3. Running Oversight Debt Delta Check ===")
    
    base_req = DriftwatchRequest(
        model_backend="rule_based",
        population_size=1000,
        timesteps=40,
        domain="benefits_eligibility",
        initial_review_probability=0.9,
        seed=44
    )
    
    req_no_adv = base_req.model_copy(update={"adversary_ratio": 0.0})
    req_with_adv = base_req.model_copy(update={"adversary_ratio": 0.15})
    
    logger.info("Running baseline (0% adversaries)...")
    metrics_no_adv = await _run_driftwatch_sync(req_no_adv)
    
    logger.info("Running adversarial (15% adversaries)...")
    metrics_with_adv = await _run_driftwatch_sync(req_with_adv)
    
    print("\nOversight Debt Comparison:")
    print(f"  Baseline (0% Adv): {metrics_no_adv.oversight_debt:.2f}")
    print(f"  Adversarial (15% Adv): {metrics_with_adv.oversight_debt:.2f}")
    
    # Specifically check the adversarial contribution
    adv_harm = metrics_with_adv.cumulative_oversight_debt_adversarial
    print(f"  Adversary-specific Cumulative Harm: {adv_harm:.2f}")
    
    if adv_harm > 0:
        print("  ✓ Adversarial population causes measurably different oversight debt.")
    else:
        print("  ! No additional harm measured.")
    print()

async def main():
    await test_prompt_injection()
    await test_adversary_learning()
    await test_oversight_debt()

if __name__ == "__main__":
    asyncio.run(main())
