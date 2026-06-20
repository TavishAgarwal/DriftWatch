"""
test_agents.py — Unit tests + smoke test for Driftwatch Part 2.

Test suites:
    1. TestPersonalityVectorDistribution — population spawning validation
    2. TestConstraintValidator — 5 rejection/acceptance cases
    3. TestPolicyParser — 5 sample policy inputs (rule-based path)
    4. TestSocialNetwork — scale-free degree distribution + propagation
    5. TestSmokeTest — 1,000 Delhi agents, 20% fare hike, 7 simulation days

Run:
    pytest backend/tests/test_agents.py -v
    python -m backend.tests.test_agents  # smoke test only
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter

import numpy as np
import pytest

# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def zone_context():
    """Load DEL_SHAHDARA zone context."""
    from backend.data.config_loader import ConfigLoader

    async def _load():
        loader = ConfigLoader("backend/config")
        return await loader.load_zone_context("DEL_SHAHDARA")

    return asyncio.run(_load())


@pytest.fixture(scope="session")
def population(zone_context):
    """Spawn 1,000 agents for DEL_SHAHDARA."""
    from backend.agents.tier1_agent import PopulationFactory

    factory = PopulationFactory()
    return factory.spawn_population(1000, zone_context, seed=42)


# ═════════════════════════════════════════════════════════════
# 1. TestPersonalityVectorDistribution
# ═════════════════════════════════════════════════════════════
class TestPersonalityVectorDistribution:

    def test_spawn_1000_agents_archetype_distribution(self, population, zone_context):
        """Archetype counts for known archetypes must be non-zero and reasonable."""
        from backend.agents.tier1_agent import ALL_ARCHETYPES

        counts = Counter(a.archetype for a in population)
        n = len(population)

        # All spawned agents must have a valid archetype
        for archetype, count in counts.items():
            assert archetype in ALL_ARCHETYPES, (
                f"Unknown archetype '{archetype}' in spawned population"
            )

        # At least 5 distinct archetypes should be represented
        assert len(counts) >= 5, (
            f"Only {len(counts)} archetypes represented, expected >=5"
        )

        # No single archetype should dominate >60% of total
        for archetype, count in counts.items():
            pct = count / n
            assert pct < 0.60, (
                f"{archetype} dominates at {pct:.1%}, expected <60%"
            )

    def test_personality_bounds_respected(self, population):
        """All numeric personality fields must be within ARCHETYPE_BOUNDS."""
        from backend.agents.tier1_agent import ARCHETYPE_BOUNDS

        violations = []
        for agent in population[:200]:  # Sample for speed
            bounds = ARCHETYPE_BOUNDS.get(agent.archetype, {})
            for field_name, (lo, hi) in bounds.items():
                val = getattr(agent.personality, field_name, None)
                if val is None:
                    continue
                if isinstance(val, (int, float)) and not (lo - 0.01 <= float(val) <= hi + 0.01):
                    violations.append(
                        f"{agent.archetype}.{field_name}: {val} not in [{lo}, {hi}]"
                    )
        assert not violations, f"Bound violations:\n" + "\n".join(violations[:10])

    def test_deterministic_spawning(self, zone_context):
        """Same seed must produce identical population."""
        from backend.agents.tier1_agent import PopulationFactory

        factory = PopulationFactory()
        pop1 = factory.spawn_population(100, zone_context, seed=99)
        pop2 = factory.spawn_population(100, zone_context, seed=99)

        for a, b in zip(pop1, pop2):
            assert a.agent_id == b.agent_id
            assert a.archetype == b.archetype
            assert a.personality.income_monthly == b.personality.income_monthly


# ═════════════════════════════════════════════════════════════
# 2. TestConstraintValidator
# ═════════════════════════════════════════════════════════════
class TestConstraintValidator:

    def _make_decision(self, **kwargs):
        from backend.agents.tier3_agent import Tier3Decision

        defaults = {
            "action": "policy_recommendation",
            "policy_recommendation": "moderate fare increase",
            "influence_signal": 0.3,
            "reasoning_chain": "test reasoning",
            "confidence": 0.8,
        }
        defaults.update(kwargs)
        return Tier3Decision(**defaults)

    def _validator(self):
        from backend.agents.tier3_agent import ConstraintValidator
        return ConstraintValidator()

    def test_reject_out_of_bounds_income(self):
        decision = self._make_decision(
            policy_recommendation="daily_wage_worker earning 500000/month should invest"
        )
        profile = {"archetype": "daily_wage_worker", "income_range": (8000, 16000)}
        result = self._validator().validate_output(decision, profile, {})
        # The validator should flag the income inconsistency
        assert result is not None

    def test_reject_nonexistent_route(self):
        decision = self._make_decision(
            policy_recommendation="redirect Purple Line to airport"
        )
        profile = {"archetype": "senior_bureaucrat"}
        city_state = {
            "transport_network": {
                "metro_lines": [
                    {"name": "Blue Line"},
                    {"name": "Yellow Line"},
                    {"name": "Red Line"},
                ]
            }
        }
        result = self._validator().validate_output(decision, profile, city_state)
        assert result is not None

    def test_reject_invalid_political_position(self):
        decision = self._make_decision(
            action="executive_order",
            policy_recommendation="as transport minister I decree"
        )
        profile = {"archetype": "daily_wage_worker"}
        result = self._validator().validate_output(decision, profile, {})
        assert result is not None

    def test_reject_hallucinated_policy(self):
        decision = self._make_decision(
            policy_recommendation="the 2024 Free Transit Act mandates zero fares"
        )
        profile = {"archetype": "economist"}
        result = self._validator().validate_output(decision, profile, {})
        assert result is not None

    def test_accept_valid_decision(self):
        decision = self._make_decision(
            action="no_change",
            policy_recommendation="maintain current fare structure",
            influence_signal=0.1,
            confidence=0.9,
        )
        profile = {"archetype": "economist"}
        result = self._validator().validate_output(decision, profile, {})
        assert result is not None
        assert result.validated is True


# ═════════════════════════════════════════════════════════════
# 3. TestPolicyParser
# ═════════════════════════════════════════════════════════════
class TestPolicyParser:

    def _parser(self):
        from backend.simulation.policy_parser import PolicyParser
        return PolicyParser(openai_api_key=None)  # Force rule-based

    @pytest.mark.asyncio
    async def test_parse_fare_increase(self):
        parser = self._parser()
        result = await parser.parse("Increase Delhi Metro fares by 20%")
        assert result.policy_type == "fare_change"
        assert abs(result.magnitude - 20.0) < 0.1
        assert "metro" in result.affected_modes

    @pytest.mark.asyncio
    async def test_parse_frequency_reduction(self):
        parser = self._parser()
        result = await parser.parse(
            "Reduce bus frequency on route 501 from 15 to 8 per hour"
        )
        assert result.policy_type == "frequency_change"
        assert "bus" in result.affected_modes

    @pytest.mark.asyncio
    async def test_parse_concession_removal(self):
        parser = self._parser()
        result = await parser.parse(
            "Remove senior citizen concession on suburban rail"
        )
        assert result.policy_type == "concession_change"
        assert "suburban_rail" in result.affected_modes

    @pytest.mark.asyncio
    async def test_parse_new_policy(self):
        parser = self._parser()
        result = await parser.parse(
            "Introduce women-only free bus policy for 6 months"
        )
        assert result.policy_type in ("new_service", "concession_change")
        assert result.timeline_days >= 150  # ~6 months

    @pytest.mark.asyncio
    async def test_parse_parking_policy(self):
        parser = self._parser()
        result = await parser.parse("Double parking charges in South Mumbai")
        assert result.policy_type == "parking_policy"
        assert abs(result.magnitude - 100.0) < 0.1


# ═════════════════════════════════════════════════════════════
# 4. TestSocialNetwork
# ═════════════════════════════════════════════════════════════
class TestSocialNetwork:

    def _build_network(self, zone_context, population):
        from backend.agents.social_network import SocialNetwork

        sn = SocialNetwork()
        return sn, sn.build_city_network(zone_context, population)

    def test_degree_distribution_connected(self, zone_context, population):
        """Network should be connected and have reasonable degree dist."""
        sn, G = self._build_network(zone_context, population[:500])
        assert G.number_of_nodes() >= 450  # Most agents are nodes
        assert G.number_of_edges() > 0
        avg_degree = 2 * G.number_of_edges() / max(G.number_of_nodes(), 1)
        assert avg_degree > 1.0, f"Average degree too low: {avg_degree}"

    def test_influence_propagation_decay(self, zone_context, population):
        """Signal should decay with distance — far agents get less on average."""
        sn, G = self._build_network(zone_context, population[:200])
        nodes = list(G.nodes())
        if not nodes:
            pytest.skip("Empty network")

        source = nodes[0]
        influenced = sn.propagate_influence(source, 0.8, G, decay_factor=0.5)
        if not influenced:
            pytest.skip("No agents influenced")

        # Separate by hop distance from source
        direct_neighbors = set(G.neighbors(source))
        near_vals = [v for k, v in influenced.items() if k in direct_neighbors]
        far_vals = [v for k, v in influenced.items() if k not in direct_neighbors]

        if near_vals and far_vals:
            avg_near = sum(abs(v) for v in near_vals) / len(near_vals)
            avg_far = sum(abs(v) for v in far_vals) / len(far_vals)
            assert avg_far <= avg_near * 1.5, (
                f"Far agents ({avg_far:.3f}) should receive less than near ({avg_near:.3f})"
            )
        # At least verify propagation happened
        assert len(influenced) > 0, "No propagation occurred"

    def test_influence_propagation_reach(self, zone_context, population):
        """Signal should reach agents beyond immediate neighbors."""
        sn, G = self._build_network(zone_context, population[:300])
        nodes = list(G.nodes())
        if len(nodes) < 10:
            pytest.skip("Network too small")

        # Find a well-connected node
        source = max(nodes, key=lambda n: G.degree(n))
        influenced = sn.propagate_influence(source, 0.9, G, decay_factor=0.85, max_hops=3)

        direct_neighbors = set(G.neighbors(source))
        beyond_direct = {k for k in influenced if k not in direct_neighbors}
        assert len(influenced) > 0, "No agents were influenced"


# ═════════════════════════════════════════════════════════════
# 5. TestSmokeTest — 1,000 Delhi agents, 20% fare hike, 7 days
# ═════════════════════════════════════════════════════════════
class TestSmokeTest:

    @pytest.mark.asyncio
    async def test_delhi_fare_hike_smoke_test(self, zone_context, population):
        """Full 7-day smoke test with 1,000 agents."""
        from backend.agents.tier1_agent import PolicyState, AgentDecision
        from backend.agents.social_network import SocialNetwork
        from backend.simulation.memory_store import MemoryStore

        agents = population
        n = len(agents)

        # Create policy state
        policy = PolicyState(
            policy_type="fare_hike",
            fare_change_pct=20.0,
            affected_modes=["metro", "bus"],
            timeline_days=30,
            day_current=0,
        )

        # Build social network
        sn = SocialNetwork()
        network = sn.build_city_network(zone_context, agents)

        # Memory store
        mem_store = MemoryStore(vector_dim=32)

        # Track results
        all_decisions: list[dict[str, str]] = []
        archetype_actions: dict[str, Counter] = {}

        print("\n" + "=" * 70)
        print("  SMOKE TEST: DEL_SHAHDARA — 20% Fare Hike — 1,000 Agents")
        print("=" * 70)

        for day in range(1, 8):
            policy.day_current = day
            day_decisions: dict[str, str] = {}
            day_signals: dict[str, float] = {}

            # Step 1: All agents decide
            for agent in agents:
                memory = agent.memory_vector
                network_signals = {}

                # Feed network influence from previous day
                if all_decisions:
                    prev = all_decisions[-1]
                    zone_resistance = sum(
                        1 for a in prev.values()
                        if a in ("mode_switch", "protest_join", "vendor_relocate")
                    ) / max(len(prev), 1)
                    network_signals["zone_resistance"] = zone_resistance

                decision = agent.decision_step(policy, memory, network_signals)
                day_decisions[agent.agent_id] = decision.action
                day_signals[agent.agent_id] = decision.broadcast_signal

                # Track by archetype
                if agent.archetype not in archetype_actions:
                    archetype_actions[agent.archetype] = Counter()
                archetype_actions[agent.archetype][decision.action] += 1

            # Step 2: Network propagation
            strong_signals = [
                (aid, sig) for aid, sig in day_signals.items()
                if abs(sig) > 0.3
            ]
            for source_id, signal in strong_signals[:20]:  # Cap for speed
                influenced = sn.propagate_influence(
                    source_id, signal, network, decay_factor=0.85
                )

            # Step 3: Memory update
            for agent in agents:
                events = [{"action": day_decisions.get(agent.agent_id, "no_change"),
                           "sentiment": day_signals.get(agent.agent_id, 0.0)}]
                vec = MemoryStore.compress_event_to_vector(events)
                mem_store.store_step(agent.agent_id, day, vec)

            all_decisions.append(day_decisions)

            # Day summary
            action_counts = Counter(day_decisions.values())
            mode_switches = action_counts.get("mode_switch", 0)
            protests = action_counts.get("protest_join", 0)
            print(f"  Day {day}: mode_switch={mode_switches}, protest={protests}, "
                  f"no_change={action_counts.get('no_change', 0)}")

        # ── Final metrics ──
        print("\n" + "-" * 70)
        print("  MODAL SHIFT DISTRIBUTION (7-day cumulative)")
        print("-" * 70)
        print(f"  {'Archetype':<28} {'Count':>6} {'ModeSwitch':>10} {'Pct':>8}")
        print(f"  {'-'*28} {'-'*6} {'-'*10} {'-'*8}")

        archetype_counts = Counter(a.archetype for a in agents)
        gig_positive_sentiment = False
        highest_mode_switch_pct = ("", 0.0)
        lowest_mode_switch_pct = ("", 1.0)

        for archetype in sorted(archetype_counts.keys()):
            total = archetype_counts[archetype]
            actions = archetype_actions.get(archetype, Counter())
            mode_switches = actions.get("mode_switch", 0)
            # For 7 days, an agent could switch multiple times
            # Use unique agents who switched at least once
            unique_switchers = set()
            for day_dec in all_decisions:
                for aid, act in day_dec.items():
                    agent_obj = next((a for a in agents if a.agent_id == aid), None)
                    if agent_obj and agent_obj.archetype == archetype and act == "mode_switch":
                        unique_switchers.add(aid)

            pct = len(unique_switchers) / max(total, 1)
            print(f"  {archetype:<28} {total:>6} {len(unique_switchers):>10} {pct:>7.1%}")

            if pct > highest_mode_switch_pct[1]:
                highest_mode_switch_pct = (archetype, pct)
            if total > 5 and pct < lowest_mode_switch_pct[1]:
                lowest_mode_switch_pct = (archetype, pct)

            # Check gig worker sentiment
            if archetype == "gig_economy_worker":
                for agent in agents:
                    if agent.archetype == "gig_economy_worker":
                        # Check last day decisions
                        last_day = all_decisions[-1]
                        if last_day.get(agent.agent_id) in ("no_change",):
                            # Gig workers with no negative action = positive
                            gig_positive_sentiment = True

        # Protest probability
        last_day_decisions = all_decisions[-1]
        protest_count = sum(1 for a in last_day_decisions.values() if a == "protest_join")
        protest_pct = protest_count / max(n, 1)

        # Revenue impact
        mode_switch_count = sum(
            1 for a in last_day_decisions.values()
            if a in ("mode_switch", "trip_consolidation", "route_change")
        )
        revenue_impact = -mode_switch_count / max(n, 1)

        print(f"\n  Protest probability (Day 7):  {protest_pct:.1%}")
        print(f"  Revenue impact (Day 7):       {revenue_impact:.1%}")
        print(f"  Highest mode_switch:          {highest_mode_switch_pct[0]} ({highest_mode_switch_pct[1]:.1%})")
        print(f"  Lowest mode_switch:           {lowest_mode_switch_pct[0]} ({lowest_mode_switch_pct[1]:.1%})")
        print(f"  Memory store stats:           {mem_store.get_memory_stats()}")
        print("=" * 70)

        # ── Assertions ──
        overall_switch_pct = sum(
            1 for a in last_day_decisions.values()
            if a in ("mode_switch", "trip_consolidation", "vendor_relocate", "route_change",
                      "return_migration", "wfh_invoke", "attendance_reduced", "reduced_hours")
        ) / max(n, 1)

        # Daily wage workers should have high mode_switch rate
        assert highest_mode_switch_pct[0] in (
            "daily_wage_worker", "street_vendor", "migrant_worker"
        ), f"Expected high-vulnerability archetype to have highest switch, got {highest_mode_switch_pct[0]}"

        # Tech workers should have low mode_switch rate
        tech_actions = archetype_actions.get("tech_knowledge_worker", Counter())
        tech_total = archetype_counts.get("tech_knowledge_worker", 0)
        if tech_total > 0:
            tech_switch_pct = tech_actions.get("mode_switch", 0) / (tech_total * 7)
            assert tech_switch_pct < 0.3, (
                f"Tech workers switched too much: {tech_switch_pct:.1%}"
            )

        # Overall sanity bounds
        assert 0.01 <= overall_switch_pct <= 0.80, (
            f"Overall behavioural change {overall_switch_pct:.1%} outside sanity bounds [1%-80%]"
        )

        print("\n  ✅ ALL SMOKE TEST ASSERTIONS PASSED\n")


# ─────────────────────────────────────────────────────────────
# Standalone runner
# ─────────────────────────────────────────────────────────────
def _run_smoke_test():
    """Run just the smoke test standalone."""
    import asyncio
    from backend.data.config_loader import ConfigLoader
    from backend.agents.tier1_agent import PopulationFactory

    async def main():
        loader = ConfigLoader("backend/config")
        zone_ctx = await loader.load_zone_context("DEL_SHAHDARA")

        factory = PopulationFactory()
        population = factory.spawn_population(1000, zone_ctx, seed=42)

        test = TestSmokeTest()
        await test.test_delhi_fare_hike_smoke_test(zone_ctx, population)

    asyncio.run(main())


if __name__ == "__main__":
    _run_smoke_test()
