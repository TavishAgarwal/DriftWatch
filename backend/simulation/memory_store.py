"""
memory_store.py — In-memory agent memory store (pgvector-ready interface).

Stores compressed event vectors per agent with 90-day sliding window.
Uses cosine similarity for ANN retrieval.  Designed so swapping to
PostgreSQL+pgvector is a config change, not a code rewrite.

References
----------
    ARCHITECTURE.md §Memory Architecture
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AgentMemory:
    """Single memory entry for an agent."""

    agent_id: str
    day: int
    event_vector: np.ndarray  # dim=32
    event_type: str = "decision_event"  # decision_event | sentiment_update | network_interaction | policy_announcement
    importance_score: float = 0.5  # 0-1


class MemoryStore:
    """In-memory vector store that mirrors the pgvector API contract.

    Parameters
    ----------
    vector_dim : int
        Dimensionality of event vectors (default 32).
    max_window_days : int
        Sliding window for memory retention (default 90).
    """

    def __init__(self, vector_dim: int = 32, max_window_days: int = 90) -> None:
        self.vector_dim = vector_dim
        self.max_window_days = max_window_days
        self._store: dict[str, list[AgentMemory]] = {}

    def store_step(
        self,
        agent_id: str,
        day: int,
        event_vector: np.ndarray,
        event_type: str = "decision_event",
        importance_score: float = 0.5,
    ) -> None:
        """Append an event to the agent's timeline.

        - High-importance events (≥0.7, or decision_event): stored losslessly.
        - Low-importance events (<0.3): lossy-compressed by averaging with
          the previous low-importance event.
        - Events older than max_window_days are evicted.
        """
        if agent_id not in self._store:
            self._store[agent_id] = []

        timeline = self._store[agent_id]

        # Evict old events
        cutoff_day = day - self.max_window_days
        if timeline and timeline[0].day < cutoff_day:
            timeline[:] = [m for m in timeline if m.day >= cutoff_day]

        mem = AgentMemory(
            agent_id=agent_id,
            day=day,
            event_vector=np.asarray(event_vector, dtype=np.float32),
            event_type=event_type,
            importance_score=importance_score,
        )

        # Lossy compression for low-importance events
        if importance_score < 0.3 and timeline:
            prev_low = None
            prev_idx = None
            for i in range(len(timeline) - 1, -1, -1):
                if timeline[i].importance_score < 0.3:
                    prev_low = timeline[i]
                    prev_idx = i
                    break
            if prev_low is not None and prev_idx is not None:
                # Average the two vectors
                merged_vec = (prev_low.event_vector + mem.event_vector) / 2.0
                timeline[prev_idx] = AgentMemory(
                    agent_id=agent_id,
                    day=day,
                    event_vector=merged_vec,
                    event_type=event_type,
                    importance_score=(prev_low.importance_score + importance_score) / 2.0,
                )
                return

        timeline.append(mem)

    def retrieve_relevant(
        self,
        agent_id: str,
        context_vector: np.ndarray,
        top_k: int = 5,
    ) -> list[AgentMemory]:
        """Cosine similarity ANN search for relevant memories.

        Parameters
        ----------
        agent_id : str
        context_vector : np.ndarray
            Query vector (dim=vector_dim).
        top_k : int
            Number of results to return.

        Returns
        -------
        list[AgentMemory]
            Top-k most similar memories, sorted by similarity descending.
        """
        timeline = self._store.get(agent_id, [])
        if not timeline:
            return []

        ctx = np.asarray(context_vector, dtype=np.float32).flatten()
        ctx_norm = np.linalg.norm(ctx)
        if ctx_norm < 1e-8:
            return timeline[:top_k]

        # Vectorised cosine similarity
        vectors = np.stack([m.event_vector.flatten() for m in timeline])
        norms = np.linalg.norm(vectors, axis=1)
        # Avoid division by zero
        valid = norms > 1e-8
        similarities = np.zeros(len(timeline))
        similarities[valid] = (vectors[valid] @ ctx) / (norms[valid] * ctx_norm)

        # Top-k indices
        k = min(top_k, len(timeline))
        top_indices = np.argsort(similarities)[-k:][::-1]
        return [timeline[i] for i in top_indices]

    def bulk_update(
        self,
        agent_events: dict[str, tuple[np.ndarray, str, float]],
        day: int,
    ) -> None:
        """Batch write for performance.

        Parameters
        ----------
        agent_events : dict
            Maps agent_id → (event_vector, event_type, importance_score).
        day : int
            Current simulation day.
        """
        for agent_id, (vec, etype, importance) in agent_events.items():
            self.store_step(agent_id, day, vec, etype, importance)

    def get_agent_history(
        self,
        agent_id: str,
        window_days: int = 90,
    ) -> list[AgentMemory]:
        """Return agent's memory timeline within window."""
        timeline = self._store.get(agent_id, [])
        if not timeline:
            return []
        if window_days >= self.max_window_days:
            return list(timeline)
        latest_day = timeline[-1].day
        cutoff = latest_day - window_days
        return [m for m in timeline if m.day >= cutoff]

    def get_memory_stats(self) -> dict:
        """Return store statistics."""
        total_events = sum(len(v) for v in self._store.values())
        mem_bytes = total_events * (self.vector_dim * 4 + 64)  # rough estimate
        return {
            "total_agents": len(self._store),
            "total_events": total_events,
            "memory_size_mb": round(mem_bytes / (1024 * 1024), 2),
            "vector_dim": self.vector_dim,
            "max_window_days": self.max_window_days,
        }

    @staticmethod
    def compress_event_to_vector(
        events: list[dict[str, Any]],
        vector_dim: int = 32,
    ) -> np.ndarray:
        """Compress a list of event dicts into a fixed-size vector.

        Uses hash-based feature encoding for categorical fields and
        direct scaling for numeric fields.

        Parameters
        ----------
        events : list[dict]
            Each dict may contain keys: action, sentiment, fare_impact,
            protest_joined, mode_switched, etc.
        vector_dim : int
            Output dimensionality (default 32).

        Returns
        -------
        np.ndarray
            Compressed event vector of shape (vector_dim,).
        """
        vec = np.zeros(vector_dim, dtype=np.float32)
        if not events:
            return vec

        for event in events:
            # Numeric fields → direct mapping to first 16 dims
            numeric_keys = [
                "sentiment", "fare_impact", "resistance_score",
                "impact_ratio", "protest_probability", "footfall_change",
                "revenue_impact", "mode_switch_pct",
            ]
            for i, key in enumerate(numeric_keys):
                if key in event and i < vector_dim:
                    val = float(event[key])
                    vec[i] += val

            # Categorical fields → hash to dims 16-31
            cat_keys = ["action", "archetype", "event_type", "policy_type"]
            for key in cat_keys:
                if key in event:
                    h = int(hashlib.md5(str(event[key]).encode()).hexdigest(), 16)
                    idx = 16 + (h % (vector_dim - 16))
                    vec[idx] += 1.0

        # Normalise
        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec /= norm

        return vec
