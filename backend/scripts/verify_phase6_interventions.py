import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.api.routes.driftwatch import _run_driftwatch_sync, DriftwatchRequest

def print_collapse_stats(label: str, results):
    debt = results.oversight_debt
    silent_rate = results.final_silent_error_rate
    hl = results.oversight_half_life
    
    print(f"\nResults for {label}:")
    print(f"  Oversight Debt: {debt:.2f}")
    print(f"  Final Silent Error Rate: {silent_rate:.2f}")
    print(f"  Oversight Half-Life: {hl}")
    return debt, silent_rate, hl

async def main():
    print("INFO: === Running Phase 6 Interventions Verification ===\n")
    
    # Worst case scenario: Dense Network + Adversarial
    base_req = DriftwatchRequest(
        model_backend="rule_based",
        population_size=500,
        timesteps=50,
        difficulty=0.5,
        initial_review_probability=0.9,
        initial_review_skill=0.8,
        seed=42,
        network_topology="random",
        network_k=50,
        social_influence_weight=0.5,
        adversary_ratio=0.15,
        adversary_episodes=2
    )

    print("INFO: 1. Running Baseline (No Interventions) ...")
    req_baseline = base_req.model_copy()
    res_baseline = await _run_driftwatch_sync(req_baseline)
    debt_base, err_base, hl_base = print_collapse_stats("Baseline", res_baseline)
    
    print("\nINFO: 2. Running Spot Checks (10%) ...")
    req_spot = base_req.model_copy(update={"spot_check_rate": 0.10})
    res_spot = await _run_driftwatch_sync(req_spot)
    debt_spot, err_spot, hl_spot = print_collapse_stats("Spot Checks (10%)", res_spot)
    
    print("\nINFO: 3. Running Confidence-Triggered Reviews (threshold < 0.8) ...")
    req_conf = base_req.model_copy(update={"confidence_review_threshold": 0.8})
    res_conf = await _run_driftwatch_sync(req_conf)
    debt_conf, err_conf, hl_conf = print_collapse_stats("Confidence Threshold", res_conf)
    
    print("\nINFO: 4. Running Mandatory Audits (every 10 steps) ...")
    req_audit = base_req.model_copy(update={"mandatory_audit_interval": 10})
    res_audit = await _run_driftwatch_sync(req_audit)
    debt_audit, err_audit, hl_audit = print_collapse_stats("Mandatory Audits", res_audit)

    print("\n=== Final Verification ===")
    success = True
    
    if debt_spot < debt_base:
        print("✓ SUCCESS: Spot Checks reduced Oversight Debt.")
    else:
        print("! FAILURE: Spot Checks did not reduce Oversight Debt.")
        success = False
        
    if debt_conf < debt_base:
        print("✓ SUCCESS: Confidence Reviews reduced Oversight Debt.")
    else:
        print("! FAILURE: Confidence Reviews did not reduce Oversight Debt.")
        success = False

    if debt_audit < debt_base:
        print("✓ SUCCESS: Mandatory Audits reduced Oversight Debt.")
    else:
        print("! FAILURE: Mandatory Audits did not reduce Oversight Debt.")
        success = False
        
    if not success:
        print("\n! Interventions did not behave as expected.")
    else:
        print("\n✓ ALL INTERVENTIONS VERIFIED.")

if __name__ == "__main__":
    asyncio.run(main())
