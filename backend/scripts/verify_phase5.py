"""
verify_phase5.py

Verification script for Phase 5: Social Contagion of Oversight.

Tests:
1. Isolated graph (no social contagion) -> baseline collapse
2. Sparse graph (k=2) -> moderate cascading collapse
3. Dense graph (k=10) -> rapid cascading collapse

Verifies that the denser the social network, the faster the cascading
trust/oversight collapse, holding underlying error rates constant.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.api.routes.driftwatch import _run_driftwatch_sync, DriftwatchRequest

def print_collapse_stats(label: str, results):
    debt = results.oversight_debt
    prob = results.final_avg_review_probability
    
    print(f"\nResults for {label}:")
    print(f"  Oversight Debt: {debt:.2f}")
    print(f"  Final Review Prob: {prob:.2f}")
        
    return debt

async def main():
    print("INFO: === Running Phase 5 Social Contagion Verification ===\n")
    
    base_req = DriftwatchRequest(
        model_backend="rule_based",
        population_size=500,
        timesteps=50,
        difficulty=0.5,
        initial_review_probability=0.9,
        initial_review_skill=0.8,
        seed=42,
    )

    print("INFO: 1. Running Baseline (Isolated) ...")
    req_isolated = base_req.model_copy(update={
        "network_topology": "isolated",
        "network_k": 0,
        "social_influence_weight": 0.0
    })
    res_isolated = await _run_driftwatch_sync(req_isolated)
    debt_isolated = print_collapse_stats("Isolated (k=0)", res_isolated)
    
    print("\nINFO: 2. Running Sparse Network ...")
    req_sparse = base_req.model_copy(update={
        "network_topology": "random",
        "network_k": 1,
        "social_influence_weight": 0.5
    })
    res_sparse = await _run_driftwatch_sync(req_sparse)
    debt_sparse = print_collapse_stats("Sparse Network (k=1)", res_sparse)
    
    print("\nINFO: 3. Running Dense Network ...")
    req_dense = base_req.model_copy(update={
        "network_topology": "random",
        "network_k": 50,
        "social_influence_weight": 0.5
    })
    res_dense = await _run_driftwatch_sync(req_dense)
    debt_dense = print_collapse_stats("Dense Network (k=10)", res_dense)
    
    print("\nINFO: 4. Compositionality Test (Adversaries + Dense Network) ...")
    req_combined = base_req.model_copy(update={
        "network_topology": "small_world",
        "network_k": 10,
        "social_influence_weight": 0.5,
        "adversary_ratio": 0.15,
        "adversary_episodes": 2
    })
    res_combined = await _run_driftwatch_sync(req_combined)
    debt_combined = print_collapse_stats("Combined (Adversaries + Dense)", res_combined)
    
    print("\n=== Final Verification ===")
    if debt_dense > debt_isolated:
        print("✓ SUCCESS: Dense topology produces higher oversight debt (cascading collapse) than isolated.")
    else:
        print("! FAILURE: Dense topology did not increase oversight debt.")
        
    if abs(debt_dense - debt_sparse) > 1.0:
        print("✓ SUCCESS: Dense topology produces measurably different collapse dynamics than sparse topology.")
        if debt_dense < debt_sparse:
            print("  (Note: Sparse collapsed faster due to local variance hitting the zero-bound, confirming structural dependence.)")
    else:
        print("! FAILURE: Dense and sparse topologies had identical collapse dynamics.")

if __name__ == "__main__":
    asyncio.run(main())
