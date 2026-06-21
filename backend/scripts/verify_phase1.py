import asyncio
import sys
import random
from pathlib import Path

# Add backend to path so imports work
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.simulation.backend_config import get_backend_profile
from backend.agents.caseworker_agent import CaseworkerAgent
from backend.simulation.case_oracle import CaseOracle
from backend.simulation.oversight_logic import update_citizen_oversight
from backend.simulation.driftwatch_metrics import compute_driftwatch_metrics, compute_crossover_point

async def verify_phase1():
    print("========================================")
    print("DRIFTWATCH PHASE 1: VERIFICATION SCRIPT")
    print("========================================\n")
    
    seed = 42
    timesteps = 20
    population = 5
    difficulty = 0.5
    
    print(f"Simulation Parameters:")
    print(f"  Timesteps: {timesteps}")
    print(f"  Population: {population}")
    print(f"  Difficulty: {difficulty}")
    print(f"  Seed: {seed}\n")
    
    # 1. Test backend initialization and quantization
    print("--- 1. Testing Backend Profiles ---")
    backends_to_test = [
        ("openai", "none"),
        ("ollama_local", "fp16"),
        ("ollama_local", "int8"),
        ("ollama_local", "int4"),
    ]
    
    agents = []
    for backend, quant in backends_to_test:
        agent = CaseworkerAgent(backend, quant, seed)
        profile = agent._profile
        print(f"Loaded {backend} ({quant}):")
        print(f"  Base Error: {profile.base_error_rate:.4f}")
        print(f"  Burst Prob: {profile.burst_probability:.4f}")
        print(f"  Burst Length: {profile.burst_duration_range}")
        print(f"  Latency: {profile.base_latency_ms}ms")
        agents.append(agent)
    print()

    # 2. Test CaseOracle shock mechanism
    print("--- 2. Testing CaseOracle Shocks ---")
    oracle = CaseOracle(seed=seed, cases_per_timestep=1, shock_interval=10, shock_magnitude=0.30)
    print("Initial Thresholds:", oracle._current_thresholds)
    
    shocks = []
    for t in range(1, timesteps + 1):
        shock = oracle.check_and_apply_shock(t)
        if shock:
            shocks.append((t, shock, oracle._current_thresholds.copy()))
    
    for t, shock, thresholds in shocks:
        print(f"Step {t}: Shock applied! New Thresholds: {thresholds}")
    print(f"Total Shocks Applied: {len(shocks)}\n")
    assert len(shocks) == 2, "Shock scheduler did not fire at the configured interval"

    # 3. Test Full Metrics Comparison (Crossover)
    print("--- 3. Testing Cross-Over Metrics (OpenAI vs INT4) ---")
    
    async def run_sim(agent: CaseworkerAgent):
        rng = random.Random(seed)
        sim_oracle = CaseOracle(seed=seed, cases_per_timestep=1, shock_interval=30, shock_magnitude=0.30)
        latency_skip_prob = min(0.5, agent._profile.base_latency_ms / 2000.0)
        
        citizens = [{"agent_id": f"CIT_{i}", "review_probability": 0.8, "review_skill": 0.8, "consecutive_low_review_steps": 0} for i in range(population)]
        all_events = []
        
        for t in range(1, timesteps + 1):
            agent.step_burst()
            sim_oracle.check_and_apply_shock(t)
            for citizen in citizens:
                case, ground_truth = sim_oracle.generate_case(difficulty=difficulty)
                decision, metadata = await agent.make_degraded_decision(case.to_dict(), ground_truth)
                
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
                    burst_error=metadata["burst_error"]
                )
                all_events.append(event)
                
        return compute_driftwatch_metrics(all_events, agent.backend_name, 0.10, 0.8, sim_oracle._shock_log)

    metrics_gpt = await run_sim(agents[0]) # openai
    metrics_int4 = await run_sim(agents[3]) # int4
    
    print("GPT-4o Metrics:")
    print(f"  Final Review Prob: {metrics_gpt.final_avg_review_probability:.4f}")
    print(f"  Final Silent Error: {metrics_gpt.final_silent_error_rate:.4f}")
    print(f"  Oversight Debt: {metrics_gpt.oversight_debt} cases")
    print(f"  Burst Contribution: {metrics_gpt.burst_error_contribution*100:.1f}%")
    
    print("\nINT4 Metrics:")
    print(f"  Final Review Prob: {metrics_int4.final_avg_review_probability:.4f}")
    print(f"  Final Silent Error: {metrics_int4.final_silent_error_rate:.4f}")
    print(f"  Oversight Debt: {metrics_int4.oversight_debt} cases")
    print(f"  Burst Contribution: {metrics_int4.burst_error_contribution*100:.1f}%")

    crossover = compute_crossover_point(metrics_gpt, metrics_int4)
    print("\nCross-Over Analysis:")
    if crossover and crossover['crossover_timestep'] != 'not reached':
        print(f"  Crossover reached at step {crossover['crossover_timestep']}.")
        print(f"  {metrics_gpt.model_backend} cumulative errors: {crossover['cumulative_a'][-1]}")
        print(f"  {metrics_int4.model_backend} cumulative errors: {crossover['cumulative_b'][-1]}")
    else:
        print("  No crossover or threshold reached.")
        
    print("\nVerification Complete.")

if __name__ == "__main__":
    asyncio.run(verify_phase1())
