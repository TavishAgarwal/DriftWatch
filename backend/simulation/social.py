"""
social.py — Social Contagion of Oversight.

Phase 5: Citizens are connected via a social graph. They observe their neighbors'
recent complaint rate (caught errors / total cases). If neighbors aren't complaining,
the citizen's trust in the system increases (they drop their oversight faster).
If neighbors complain frequently, the citizen maintains or increases oversight.
"""

from __future__ import annotations

import networkx as nx
import random
from collections import deque
from typing import Any


class SocialNetworkManager:
    """Manages the social graph and observable signals of a citizen population.
    
    Topologies supported:
      - 'isolated': No connections (k=0)
      - 'random': Erdos-Renyi graph
      - 'small_world': Watts-Strogatz graph (local clustering + short paths)
      - 'dense': Complete graph or highly connected
    """

    def __init__(
        self,
        citizen_ids: list[str],
        topology: str = "isolated",
        k: int = 4,
        p: float = 0.1,
        seed: int = 42,
        history_window: int = 5,
    ) -> None:
        self.citizen_ids = citizen_ids
        self.history_window = history_window
        self.topology = topology
        
        # Build the graph
        num_nodes = len(citizen_ids)
        if topology == "isolated" or k == 0:
            self.graph = nx.empty_graph(num_nodes)
        elif topology == "random":
            # p here represents probability of edge creation
            edge_prob = min(1.0, k / max(1, num_nodes - 1))
            self.graph = nx.erdos_renyi_graph(num_nodes, edge_prob, seed=seed)
        elif topology == "small_world":
            # k must be even, p is rewiring probability
            actual_k = min(num_nodes - 1, max(2, k + (k % 2)))
            self.graph = nx.watts_strogatz_graph(num_nodes, actual_k, p, seed=seed)
        elif topology == "dense":
            # Highly connected, essentially k = N-1 or very large
            edge_prob = 0.5
            self.graph = nx.erdos_renyi_graph(num_nodes, edge_prob, seed=seed)
        else:
            self.graph = nx.empty_graph(num_nodes)
            
        # Map node index back to citizen_id
        self.idx_to_id = {i: cid for i, cid in enumerate(citizen_ids)}
        self.id_to_idx = {cid: i for i, cid in enumerate(citizen_ids)}
        
        # Initialize signal tracking: store (caught_count, total_cases) for recent timesteps
        # We track this per citizen to compute the complaint rate.
        self._history: dict[str, deque[tuple[int, int]]] = {
            cid: deque(maxlen=history_window) for cid in citizen_ids
        }
        
    def update(self, step_events: list[Any]) -> None:
        """Update the complaint history with the latest timestep's events.
        
        Expects step_events to be a list of OversightEvent (or similar objects)
        that have `citizen_id` and `caught` attributes.
        """
        # Aggregate caught vs total cases for each citizen this timestep
        counts = {cid: {"caught": 0, "total": 0} for cid in self.citizen_ids}
        
        for e in step_events:
            cid = e.citizen_id
            if cid in counts:
                counts[cid]["total"] += 1
                if getattr(e, "caught", False):
                    counts[cid]["caught"] += 1
                    
        # Push to history
        for cid, stats in counts.items():
            self._history[cid].append((stats["caught"], stats["total"]))
            
    def _get_complaint_rate(self, citizen_id: str) -> float:
        """Calculate the individual complaint rate for a citizen over the history window."""
        history = self._history.get(citizen_id, [])
        caught_sum = sum(h[0] for h in history)
        total_sum = sum(h[1] for h in history)
        if total_sum == 0:
            return 0.0
        return caught_sum / total_sum
        
    def get_neighbor_signal(self, citizen_id: str) -> float:
        """Get the average complaint rate of the citizen's neighbors."""
        idx = self.id_to_idx.get(citizen_id)
        if idx is None:
            return 0.0
            
        neighbors = list(self.graph.neighbors(idx))
        if not neighbors:
            return 0.0
            
        total_rate = 0.0
        for n_idx in neighbors:
            n_id = self.idx_to_id[n_idx]
            total_rate += self._get_complaint_rate(n_id)
            
        return total_rate / len(neighbors)

    def get_influence_strength(self, citizen_id: str) -> float:
        """Return confidence in the observable neighbor signal.

        A single neighbor is a weak social cue; a broad neighborhood is a
        stronger norm signal.  Saturating at ten neighbors prevents dense
        graphs from producing unbounded updates while preserving a meaningful
        sparse-vs-dense topology distinction.
        """
        idx = self.id_to_idx.get(citizen_id)
        if idx is None:
            return 0.0
        degree = self.graph.degree(idx)
        return min(1.0, degree / 10.0)
