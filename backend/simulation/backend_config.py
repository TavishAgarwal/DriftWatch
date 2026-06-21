"""
backend_config.py — Configuration profiles for caseworker model backends.

Defines the quantitative degradation parameters for different model
tiers and quantization levels (error rates, latencies, burst mechanics).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackendProfile:
    name: str                       # display name
    backend_key: str                # "openai" | "ollama_api" | "ollama_local" | "rule_based"
    quantization: str               # "FP32" | "FP16" | "INT8" | "INT4" | "none"
    base_error_rate: float          # baseline error probability [0–1]
    base_latency_ms: float          # simulated TtFT — used as skip-probability input, NOT wall-clock delay
    burst_probability: float        # per-timestep probability of entering hallucination burst
    burst_duration_range: tuple[int, int]  # (min, max) burst length in timesteps
    burst_error_rate: float         # error rate DURING burst (>> base)
    burst_confidence_floor: float   # minimum synthetic confidence during burst (high = deceptive)


ALL_PROFILES = [
    BackendProfile(
        name="GPT-4o (Closed)",
        backend_key="openai",
        quantization="none",
        base_error_rate=0.05,
        base_latency_ms=200,
        burst_probability=0.005,
        burst_duration_range=(2, 4),
        burst_error_rate=0.30,
        burst_confidence_floor=0.85,
    ),
    BackendProfile(
        name="Llama 3.1 8B API (FP16)",
        backend_key="ollama_api",
        quantization="FP16",
        base_error_rate=0.10,
        base_latency_ms=500,
        burst_probability=0.02,
        burst_duration_range=(3, 6),
        burst_error_rate=0.45,
        burst_confidence_floor=0.80,
    ),
    BackendProfile(
        name="Llama 3.1 Local FP16",
        backend_key="ollama_local",
        quantization="FP16",
        base_error_rate=0.12,
        base_latency_ms=700,
        burst_probability=0.025,
        burst_duration_range=(3, 6),
        burst_error_rate=0.48,
        burst_confidence_floor=0.80,
    ),
    BackendProfile(
        name="Llama 3.1 Local INT8",
        backend_key="ollama_local",
        quantization="INT8",
        base_error_rate=0.15,
        base_latency_ms=350,
        burst_probability=0.04,
        burst_duration_range=(4, 7),
        burst_error_rate=0.55,
        burst_confidence_floor=0.82,
    ),
    BackendProfile(
        name="Llama 3.1 Local INT4",
        backend_key="ollama_local",
        quantization="INT4",
        base_error_rate=0.22,
        base_latency_ms=250,
        burst_probability=0.08,
        burst_duration_range=(4, 8),
        burst_error_rate=0.65,
        burst_confidence_floor=0.88,
    ),
    BackendProfile(
        name="Rule-Based (Fallback)",
        backend_key="rule_based",
        quantization="none",
        base_error_rate=0.15,
        base_latency_ms=10,
        burst_probability=0.00,
        burst_duration_range=(0, 0),
        burst_error_rate=0.00,
        burst_confidence_floor=0.50,
    ),
]


def get_backend_profile(backend_key: str, quantization: str = "none") -> BackendProfile:
    """Retrieve the matching BackendProfile.
    
    If no exact match is found, falls back to rule_based.
    If multiple match (should not happen with current set), returns the first.
    If matching just on backend_key (for backward compatibility), returns the first.
    """
    normalized_backend = backend_key.lower().strip()
    normalized_quantization = quantization.upper().strip()
    if normalized_quantization in {"", "NONE"}:
        normalized_quantization = "none"

    # 1. Try exact match
    for p in ALL_PROFILES:
        if p.backend_key == normalized_backend and p.quantization == normalized_quantization:
            return p
    
    # 2. Try match on backend_key only (if e.g. "ollama_local" is requested without specifying quant)
    for p in ALL_PROFILES:
        if p.backend_key == normalized_backend:
            return p

    # 3. Fallback
    return next(p for p in ALL_PROFILES if p.backend_key == "rule_based")
