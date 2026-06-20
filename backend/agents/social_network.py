"""
social_network.py — Scale-free social network for Driftwatch.

Builds a Barabási–Albert network with archetype-aware edge rewiring
and modified SIR dynamics for influence propagation.

References
----------
    ARCHITECTURE.md §Social Network Architecture
    AGENT_SPEC.md §HOW ARCHETYPES INTERACT IN THE SOCIAL NETWORK
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Archetype affinity matrix (from AGENT_SPEC.md §824-851)
# ─────────────────────────────────────────────────────────────
# Symmetric: affinity(A,B) == affinity(B,A).
# Default for unlisted pairs: 0.20.

_AFFINITY_PAIRS: dict[tuple[str, str], float] = {
    # Same-archetype HIGH
    ("daily_wage_worker", "daily_wage_worker"): 0.85,
    ("homemaker", "homemaker"): 0.82,
    ("tech_knowledge_worker", "tech_knowledge_worker"): 0.80,
    ("student", "student"): 0.88,
    ("migrant_worker", "migrant_worker"): 0.92,
    ("exam_aspirant", "exam_aspirant"): 0.90,
    ("formal_sector_employee", "formal_sector_employee"): 0.70,
    ("government_employee", "government_employee"): 0.72,
    ("small_business_owner", "small_business_owner"): 0.68,
    ("street_vendor", "street_vendor"): 0.78,
    ("retired", "retired"): 0.65,
    ("healthcare_worker", "healthcare_worker"): 0.60,
    ("gig_economy_worker", "gig_economy_worker"): 0.65,
    ("journalist_tier1", "journalist_tier1"): 0.55,

    # Cross-archetype — from AGENT_SPEC.md
    ("small_business_owner", "daily_wage_worker"): 0.75,
    ("street_vendor", "homemaker"): 0.78,
    ("retired", "homemaker"): 0.80,
    ("gig_economy_worker", "daily_wage_worker"): 0.55,
    ("government_employee", "tech_knowledge_worker"): 0.15,
    ("student", "exam_aspirant"): 0.82,
    ("homemaker", "student"): 0.55,
    ("daily_wage_worker", "migrant_worker"): 0.72,
    ("small_business_owner", "homemaker"): 0.52,
    ("formal_sector_employee", "homemaker"): 0.48,
    ("retired", "formal_sector_employee"): 0.40,
    ("healthcare_worker", "formal_sector_employee"): 0.35,
}

# Journalist and healthcare have special broad-reach affinities
_JOURNALIST_AFFINITY = 0.45   # journalist_tier1 ↔ ALL
_HEALTHCARE_AFFINITY = 0.25   # healthcare_worker ↔ ALL (low direct, high mediated)
_DEFAULT_AFFINITY = 0.20


def _get_affinity(arch_a: str, arch_b: str) -> float:
    """Return the archetype affinity score for a pair."""
    if arch_a == "journalist_tier1" or arch_b == "journalist_tier1":
        if arch_a == arch_b:
            return 0.55
        return _JOURNALIST_AFFINITY
    if arch_a == "healthcare_worker" or arch_b == "healthcare_worker":
        if arch_a == arch_b:
            return 0.60
        return _HEALTHCARE_AFFINITY

    key = (arch_a, arch_b)
    if key in _AFFINITY_PAIRS:
        return _AFFINITY_PAIRS[key]
    key_rev = (arch_b, arch_a)
    if key_rev in _AFFINITY_PAIRS:
        return _AFFINITY_PAIRS[key_rev]
    return _DEFAULT_AFFINITY


class SocialNetwork:
    """Scale-free social network builder and influence propagation engine.

    Uses Barabási–Albert model with archetype-aware edge rewiring.
    Tier 2 agents become hub nodes, Tier 3 become super-hub nodes.
    """

    def build_city_network(
        self,
        zone_context: Any,
        agents: list[Any],
        tier2_agents: list[Any] | None = None,
        tier3_agents: list[Any] | None = None,
    ) -> nx.Graph:
        """Build the social network graph for a zone population.

        Parameters
        ----------
        zone_context : ZoneContext
            Zone configuration (social_network_parameters used for calibration).
        agents : list
            Tier 1 agents. Each must have ``agent_id`` and ``archetype`` attrs
            (or be dicts with those keys).
        tier2_agents, tier3_agents : list, optional
            Higher-tier agents to add as hub / super-hub nodes.

        Returns
        -------
        nx.Graph
            Graph with node attrs: agent_id, archetype, tier.
            Edge attrs: weight (affinity score).
        """
        tier2_agents = tier2_agents or []
        tier3_agents = tier3_agents or []

        # Extract social network params
        sn_params = getattr(zone_context, "social_network_parameters", {}) or {}
        avg_connections = sn_params.get("avg_connections_tier1", 35)
        m_param = max(2, avg_connections // 2)

        n_total = len(agents) + len(tier2_agents) + len(tier3_agents)
        if n_total < 2:
            G = nx.Graph()
            for a in agents:
                aid = _agent_id(a)
                G.add_node(aid, agent_id=aid, archetype=_archetype(a), tier=1)
            return G

        # Cap m for small populations
        m_param = min(m_param, n_total - 1)

        # Step 1: Build base BA graph on Tier 1 nodes
        n_t1 = len(agents)
        G = nx.barabasi_albert_graph(max(n_t1, m_param + 1), m_param, seed=42)

        # Relabel nodes to agent IDs
        id_map = {}
        for i, agent in enumerate(agents):
            if i < G.number_of_nodes():
                id_map[i] = _agent_id(agent)
        G = nx.relabel_nodes(G, id_map)

        # Step 2: Set node attributes
        for agent in agents:
            aid = _agent_id(agent)
            if aid in G:
                G.nodes[aid]["agent_id"] = aid
                G.nodes[aid]["archetype"] = _archetype(agent)
                G.nodes[aid]["tier"] = 1

        # Step 3: Rewire edges using affinity matrix
        rng = np.random.default_rng(42)
        edges_to_remove = []
        for u, v in list(G.edges()):
            arch_u = G.nodes[u].get("archetype", "")
            arch_v = G.nodes[v].get("archetype", "")
            affinity = _get_affinity(arch_u, arch_v)
            # Keep edge with probability = affinity, remove otherwise
            if rng.random() > affinity:
                edges_to_remove.append((u, v))
            else:
                G.edges[u, v]["weight"] = affinity

        G.remove_edges_from(edges_to_remove)

        # Re-add some edges to maintain connectivity
        node_list = list(G.nodes())
        for u in node_list:
            if G.degree(u) < 2 and len(node_list) > 2:
                arch_u = G.nodes[u].get("archetype", "")
                # Connect to a random same-archetype node
                candidates = [
                    n for n in node_list
                    if n != u and G.nodes[n].get("archetype") == arch_u
                    and not G.has_edge(u, n)
                ]
                if not candidates:
                    candidates = [n for n in node_list if n != u and not G.has_edge(u, n)]
                if candidates:
                    target = candidates[int(rng.integers(0, len(candidates)))]
                    affinity = _get_affinity(arch_u, G.nodes[target].get("archetype", ""))
                    G.add_edge(u, target, weight=affinity)

        # Step 4: Add Tier 2 hub nodes (degree 50-200 in 1000-agent network)
        for t2 in tier2_agents:
            t2_id = _agent_id(t2)
            t2_type = _archetype(t2)
            G.add_node(t2_id, agent_id=t2_id, archetype=t2_type, tier=2)

            hub_degree = min(int(n_t1 * 0.15), 200)
            targets = rng.choice(node_list, size=min(hub_degree, len(node_list)), replace=False)
            for t in targets:
                affinity = _get_affinity(t2_type, G.nodes[t].get("archetype", ""))
                G.add_edge(t2_id, str(t), weight=affinity * 1.2)

        # Step 5: Add Tier 3 super-hub nodes
        all_nodes = list(G.nodes())
        for t3 in tier3_agents:
            t3_id = _agent_id(t3)
            t3_type = _archetype(t3)
            G.add_node(t3_id, agent_id=t3_id, archetype=t3_type, tier=3)

            super_degree = min(int(n_t1 * 0.3), 500)
            targets = rng.choice(all_nodes, size=min(super_degree, len(all_nodes)), replace=False)
            for t in targets:
                G.add_edge(t3_id, str(t), weight=0.5)

        logger.info(
            "SocialNetwork: %d nodes, %d edges, avg_degree=%.1f",
            G.number_of_nodes(),
            G.number_of_edges(),
            2 * G.number_of_edges() / max(G.number_of_nodes(), 1),
        )
        return G

    def propagate_influence(
        self,
        source_id: str,
        signal: float,
        network: nx.Graph,
        decay_factor: float = 0.85,
        max_hops: int = 4,
    ) -> dict[str, float]:
        """Propagate influence through the network using modified SIR dynamics.

        Parameters
        ----------
        source_id : str
            Agent ID originating the signal.
        signal : float
            Signal strength (-1.0 to 1.0).
        network : nx.Graph
            The social network graph.
        decay_factor : float
            Signal decay per hop (default 0.85).
        max_hops : int
            Maximum propagation depth (default 4).

        Returns
        -------
        dict[str, float]
            Mapping of affected agent_id → influence received.
        """
        if source_id not in network or abs(signal) < 0.01:
            return {}

        influenced: dict[str, float] = {}
        # S=susceptible, I=infected (propagating), R=recovered
        recovered: set[str] = {source_id}
        frontier: set[str] = {source_id}

        current_signal = signal

        for hop in range(max_hops):
            current_signal *= decay_factor
            if abs(current_signal) < 0.01:
                break

            next_frontier: set[str] = set()
            for node in frontier:
                for neighbor in network.neighbors(node):
                    if neighbor in recovered:
                        continue
                    # Edge weight modulates signal
                    edge_weight = network.edges[node, neighbor].get("weight", 0.5)
                    received = current_signal * edge_weight
                    if abs(received) >= 0.01:
                        influenced[neighbor] = influenced.get(neighbor, 0.0) + received
                        next_frontier.add(neighbor)

            recovered.update(frontier)
            frontier = next_frontier - recovered

            if not frontier:
                break

        return influenced

    def get_agent_neighborhood(
        self,
        agent_id: str,
        network: nx.Graph,
        hops: int = 2,
    ) -> set[str]:
        """Return all agent IDs within ``hops`` distance."""
        if agent_id not in network:
            return set()
        neighborhood = set()
        current_layer = {agent_id}
        visited = {agent_id}
        for _ in range(hops):
            next_layer: set[str] = set()
            for node in current_layer:
                for neighbor in network.neighbors(node):
                    if neighbor not in visited:
                        next_layer.add(neighbor)
                        visited.add(neighbor)
            neighborhood.update(next_layer)
            current_layer = next_layer
        return neighborhood

    @staticmethod
    def get_degree_distribution(network: nx.Graph) -> dict[int, int]:
        """Return {degree: count} for validation."""
        dist: dict[int, int] = defaultdict(int)
        for _, degree in network.degree():
            dist[degree] += 1
        return dict(sorted(dist.items()))


# ─────────────────────────────────────────────────────────────
# Helpers — extract agent_id / archetype from objects or dicts
# ─────────────────────────────────────────────────────────────
def _agent_id(agent: Any) -> str:
    if isinstance(agent, dict):
        return str(agent.get("agent_id", id(agent)))
    return str(getattr(agent, "agent_id", id(agent)))


def _archetype(agent: Any) -> str:
    if isinstance(agent, dict):
        return str(agent.get("archetype", agent.get("agent_type", "unknown")))
    return str(getattr(agent, "archetype", getattr(agent, "agent_type", "unknown")))
