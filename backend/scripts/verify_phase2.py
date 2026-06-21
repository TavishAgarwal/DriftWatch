import asyncio
import sys
from pathlib import Path

# Add backend to path so imports work
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.simulation.domains import get_domain, DOMAIN_REGISTRY
from backend.agents.caseworker_agent import CaseworkerAgent
from backend.simulation.oversight_logic import update_citizen_oversight
from backend.simulation.driftwatch_metrics import compute_driftwatch_metrics, compute_crossover_point
import random

async def run_domain(domain_id: str):
    print(f"\n========================================")
    print(f"TESTING DOMAIN: {domain_id}")
    print(f"========================================")
    
    seed = 42
    timesteps = 20
    population = 10
    difficulty = 0.5
    
    agent_gpt = CaseworkerAgent("openai", "none", seed)
    agent_int4 = CaseworkerAgent("ollama_local", "int4", seed)
    
    async def run_sim(agent: CaseworkerAgent):
        rng = random.Random(seed)
        oracle = get_domain(domain_id, seed=seed, cases_per_timestep=1, shock_interval=30, shock_magnitude=0.30)
        latency_skip_prob = min(0.5, agent._profile.base_latency_ms / 2000.0)
        
        citizens = [{"agent_id": f"CIT_{i}", "review_probability": 0.8, "review_skill": 0.8, "consecutive_low_review_steps": 0} for i in range(population)]
        all_events = []
        
        for t in range(1, timesteps + 1):
            agent.step_burst()
            oracle.check_and_apply_shock(t)
            for citizen in citizens:
                case, ground_truth = oracle.generate_case(difficulty=difficulty)
                decision, metadata = await agent.make_degraded_decision(case, ground_truth)
                
                event = update_citizen_oversight(
                    citizen=citizen,
                    decision_outcome=decision.outcome,
                    ground_truth=ground_truth,
                    timestep=t,
                    model_backend=agent.backend_name,
                    rng=rng,
                    counterfactual_freeze=False,
                    latency_skip_probability=latency_skip_prob,
                    in_burst=metadata["in_burst"],
                    error_injected=metadata["error_injected"],
                    burst_error=metadata["burst_error"],
                    reviewer_availability=oracle.reviewer_availability,
                )
                all_events.append(event)
                
        return compute_driftwatch_metrics(all_events, agent.backend_name, 0.10, 0.8, oracle._shock_log)

    metrics_gpt = await run_sim(agent_gpt)
    metrics_int4 = await run_sim(agent_int4)
    
    crossover = compute_crossover_point(metrics_gpt, metrics_int4)
    print("\nCross-Over Analysis:")
    if crossover and crossover['crossover_timestep'] != 'not reached':
        print(f"  Crossover reached at step {crossover['crossover_timestep']}.")
        print(f"  GPT-4o cumulative errors: {crossover['cumulative_a'][-1]}")
        print(f"  INT4 cumulative errors: {crossover['cumulative_b'][-1]}")
    else:
        print("  No crossover or threshold reached.")

    print(f"\nHealthcare specific checks for {domain_id}:")
    print(f"  GPT-4o Total decisions: {timesteps * population}")
    print(f"  GPT-4o Total reviewed: {sum(m.total_reviewed for m in metrics_gpt.timestep_metrics)}")
    print(f"  GPT-4o Reviewer Availability Ceiling: {get_domain(domain_id).reviewer_availability}")

async def verify_phase2():
    for domain_id in DOMAIN_REGISTRY.keys():
        await run_domain(domain_id)
        
if __name__ == "__main__":
    asyncio.run(verify_phase2())
