import React, { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, AreaChart, Area, ReferenceLine, ReferenceArea
} from 'recharts';
import logoImg from '../assets/driftwatch-logo.png';
import { useNavigate } from 'react-router-dom';
import { API_BASE } from '../api/config';

/* ─── Types ─── */
interface TimestepData {
  timestep: number;
  avg_review_probability: number;
  avg_review_skill: number;
  silent_error_rate: number;
  total_decisions: number;
  total_errors: number;
  total_caught: number;
  total_reviewed: number;
  burst_errors: number;
  baseline_errors: number;
  latency_skips: number;
  trust_skips: number;
  shock_active: boolean;
  in_burst: boolean;
  risk_score?: number;
}

interface RunResult {
  backend: string;
  label: string;
  color: string;
  timeline: TimestepData[];
  timeToThreshold: number | null;
  finalReviewProb: number;
  finalSilentError: number;
  counterfactual: boolean;
  oversightDebt: number;
  oversightHalfLife: number | string;
  burstErrorContribution: number;
  latencySkips: number;
  trustSkips: number;
  shockEvents: Array<{ timestep: number }>;
  metrics?: any;
}

/* ─── Model backends ─── */
const BACKENDS = [
  { id: 'openai', label: 'GPT-4o (Closed)', color: '#ef4444', description: 'Large closed model via OpenAI API' },
  { id: 'ollama_api', label: 'Llama 3.1 8B API (FP16)', color: '#06b6d4', description: 'Open-source model via Ollama' },
  { id: 'ollama_local_fp16', label: 'Llama 3.1 FP16 (Local)', color: '#22c55e', description: 'Local model — full precision baseline' },
  { id: 'ollama_local_int8', label: 'Llama 3.1 INT8 (Local)', color: '#c084fc', description: 'Local model — 8-bit quantized' },
  { id: 'ollama_local_int4', label: 'Llama 3.1 INT4 (Local)', color: '#e879f9', description: 'Local model — 4-bit quantized' },
  { id: 'rule_based', label: 'Rule-Based (Fallback)', color: '#f59e0b', description: 'Deterministic rules — no LLM' },
];

const BACKEND_QUANTIZATION: Record<string, string> = {
  ollama_api: 'FP16',
  ollama_local_fp16: 'FP16',
  ollama_local_int8: 'INT8',
  ollama_local_int4: 'INT4',
};

/* ─── SSE helpers ─── */
interface SSEEvent {
  event: string;
  simulation_id?: string;
  model_backend?: string;
  counterfactual?: boolean;
  timestep?: number;
  avg_review_probability?: number;
  avg_review_skill?: number;
  silent_error_rate?: number;
  total_decisions?: number;
  total_errors?: number;
  total_caught?: number;
  total_reviewed?: number;
  metrics?: {
    time_to_threshold: number | null;
    final_avg_review_probability: number;
    final_silent_error_rate: number;
    oversight_debt: number;
    oversight_half_life: number | string;
    burst_error_contribution: number;
    latency_skips: number;
    trust_skips: number;
    shock_events: Array<{ timestep: number }>;
  };
  message?: string;
  burst_errors?: number;
  baseline_errors?: number;
  latency_skips?: number;
  trust_skips?: number;
  shock_active?: boolean;
  in_burst?: boolean;
  risk_score?: number;
}

export default function DriftwatchDashboard() {
  const navigate = useNavigate();
  const [selectedBackends, setSelectedBackends] = useState<string[]>(['rule_based']);
  const [population, setPopulation] = useState(500);
  const [timesteps, setTimesteps] = useState(30);
  const [difficulty, setDifficulty] = useState(0.5);
  const [shockInterval, setShockInterval] = useState(0);
  const [showCounterfactual, setShowCounterfactual] = useState(false);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [results, setResults] = useState<RunResult[]>([]);
  const [error, setError] = useState('');
  const [domains, setDomains] = useState<{id: string, name: string, description: string}[]>([]);
  const [selectedDomain, setSelectedDomain] = useState('benefits_eligibility');
  // Phase 3 state
  const [explanationStyle, setExplanationStyle] = useState('detailed');
  const [confidenceCalibrated, setConfidenceCalibrated] = useState(true);
  const [languageMismatchRatio, setLanguageMismatchRatio] = useState(0.0);

  // Phase 4: Adversarial
  const [adversaryRatio, setAdversaryRatio] = useState(0.0);
  const [adversaryEpisodes, setAdversaryEpisodes] = useState(1);

  // Phase 5: Network
  const [networkTopology, setNetworkTopology] = useState('isolated');
  const [networkK, setNetworkK] = useState(5);
  const [socialInfluenceWeight, setSocialInfluenceWeight] = useState(0.5);

  // Phase 6: Interventions
  const [spotCheckRate, setSpotCheckRate] = useState(0.0);
  const [confidenceReviewThreshold, setConfidenceReviewThreshold] = useState(0.0);
  const [mandatoryAuditInterval, setMandatoryAuditInterval] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  // Fetch available domains on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/driftwatch/domains`)
      .then(r => r.json())
      .then(d => {
        if (d.domains) {
          setDomains(d.domains);
        }
      })
      .catch(e => console.error("Failed to load domains:", e));
  }, []);

  const toggleBackend = useCallback((id: string) => {
    setSelectedBackends(prev =>
      prev.includes(id) ? prev.filter(b => b !== id) : [...prev, id]
    );
  }, []);

  /* ─── Run simulation ─── */
  const runSimulation = useCallback(async () => {
    if (selectedBackends.length === 0) return;
    setRunning(true);
    setError('');
    setResults([]);
    setProgress({});

    const controller = new AbortController();
    abortRef.current = controller;

    const runConfigs: { backend: string; counterfactual: boolean }[] = [];
    for (const b of selectedBackends) {
      runConfigs.push({ backend: b, counterfactual: false });
      if (showCounterfactual) {
        runConfigs.push({ backend: b, counterfactual: true });
      }
    }

    const allResults: RunResult[] = [];

    for (const config of runConfigs) {
      if (controller.signal.aborted) break;
      const backendMeta = BACKENDS.find(b => b.id === config.backend) || BACKENDS[3];
      const timeline: TimestepData[] = [];
      const runKey = config.counterfactual ? `${config.backend}_cf` : config.backend;

      try {
        const response = await fetch(`${API_BASE}/api/driftwatch/simulate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model_backend: config.backend,
            population_size: population,
            timesteps: timesteps,
            difficulty: difficulty,
            counterfactual: config.counterfactual,
            seed: 42,
            shock_interval: shockInterval,
            shock_magnitude: 0.30,
            quantization: BACKEND_QUANTIZATION[config.backend] ?? "none",
            domain: selectedDomain,
            explanation_style: explanationStyle,
            confidence_calibrated: confidenceCalibrated,
            language_mismatch_ratio: languageMismatchRatio,
            adversary_ratio: adversaryRatio,
            adversary_episodes: adversaryEpisodes,
            network_topology: networkTopology,
            network_k: networkK,
            social_influence_weight: socialInfluenceWeight,
            spot_check_rate: spotCheckRate,
            confidence_review_threshold: confidenceReviewThreshold,
            mandatory_audit_interval: mandatoryAuditInterval,
          }),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Backend returned ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop() ?? '';

          for (const chunk of chunks) {
            const line = chunk.split('\n').find(l => l.startsWith('data: '));
            if (!line) continue;
            const evt: SSEEvent = JSON.parse(line.slice(6));

            if (evt.event === 'timestep' && evt.timestep !== undefined) {
              timeline.push({
                timestep: evt.timestep,
                avg_review_probability: evt.avg_review_probability ?? 0,
                avg_review_skill: evt.avg_review_skill ?? 0,
                silent_error_rate: evt.silent_error_rate ?? 0,
                total_decisions: evt.total_decisions ?? 0,
                total_errors: evt.total_errors ?? 0,
                total_caught: evt.total_caught ?? 0,
                total_reviewed: evt.total_reviewed ?? 0,
                burst_errors: evt.burst_errors ?? 0,
                baseline_errors: evt.baseline_errors ?? 0,
                latency_skips: evt.latency_skips ?? 0,
                trust_skips: evt.trust_skips ?? 0,
                shock_active: evt.shock_active ?? false,
                in_burst: evt.in_burst ?? false,
                risk_score: evt.risk_score,
              });
              setProgress(prev => ({ ...prev, [runKey]: evt.timestep! }));
              // Publish the in-flight timeline so charts and the predictor risk
              // badge move during the run instead of appearing only at the end.
              setResults([
                ...allResults,
                {
                  backend: config.backend,
                  label: config.counterfactual
                    ? `${backendMeta.label} (No Decay)`
                    : backendMeta.label,
                  color: config.counterfactual ? `${backendMeta.color}80` : backendMeta.color,
                  timeline: [...timeline],
                  timeToThreshold: null,
                  finalReviewProb: timeline.at(-1)?.avg_review_probability ?? 0,
                  finalSilentError: timeline.at(-1)?.silent_error_rate ?? 0,
                  counterfactual: config.counterfactual,
                  oversightDebt: 0,
                  oversightHalfLife: 'running',
                  burstErrorContribution: 0,
                  latencySkips: timeline.reduce((sum, point) => sum + point.latency_skips, 0),
                  trustSkips: timeline.reduce((sum, point) => sum + point.trust_skips, 0),
                  shockEvents: [],
                },
              ]);
            }

            if (evt.event === 'sim_complete' && evt.metrics) {
              allResults.push({
                backend: config.backend,
                label: config.counterfactual
                  ? `${backendMeta.label} (No Decay)`
                  : backendMeta.label,
                color: config.counterfactual
                  ? `${backendMeta.color}80`
                  : backendMeta.color,
                timeline,
                timeToThreshold: evt.metrics.time_to_threshold,
                finalReviewProb: evt.metrics.final_avg_review_probability,
                finalSilentError: evt.metrics.final_silent_error_rate,
                counterfactual: config.counterfactual,
                oversightDebt: evt.metrics.oversight_debt,
                oversightHalfLife: evt.metrics.oversight_half_life,
                burstErrorContribution: evt.metrics.burst_error_contribution,
                latencySkips: evt.metrics.latency_skips,
                trustSkips: evt.metrics.trust_skips,
                shockEvents: evt.metrics.shock_events || [],
                metrics: evt.metrics,
              });
              setResults([...allResults]);
            }

            if (evt.event === 'sim_error') {
              setError(evt.message || 'Simulation failed');
            }
          }
        }
      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') break;
        setError(e instanceof Error ? e.message : 'Connection failed');
        break;
      }
    }

    setRunning(false);
  }, [
    selectedBackends, population, timesteps, difficulty, showCounterfactual,
    shockInterval, selectedDomain, explanationStyle, confidenceCalibrated,
    languageMismatchRatio, adversaryRatio, adversaryEpisodes, networkTopology,
    networkK, socialInfluenceWeight, spotCheckRate, confidenceReviewThreshold,
    mandatoryAuditInterval
  ]);

  const cancelSimulation = useCallback(() => {
    abortRef.current?.abort();
    setRunning(false);
  }, []);

  /* ─── Combined chart data ─── */
  const chartData = useMemo(() => {
    if (results.length === 0) return [];
    const maxTs = Math.max(...results.flatMap(r => r.timeline.map(t => t.timestep)));
    const data: Record<string, unknown>[] = [];
    for (let t = 1; t <= maxTs; t++) {
      const row: Record<string, unknown> = { timestep: t };
      for (const r of results) {
        const key = r.counterfactual ? `${r.backend}_cf` : r.backend;
        const point = r.timeline.find(p => p.timestep === t);
        if (point) {
          row[`${key}_review_prob`] = point.avg_review_probability;
          row[`${key}_silent_error`] = point.silent_error_rate;
          row[`${key}_skill`] = point.avg_review_skill;
          row[`${key}_latency_skips`] = point.latency_skips;
          row[`${key}_trust_skips`] = point.trust_skips;
          row[`${key}_in_burst`] = point.in_burst;
          row[`${key}_shock_active`] = point.shock_active;
        }
      }

      // Look for risk score in the main result (not counterfactual) timeline or final metrics
      for (const r of results) {
        if (!r.counterfactual) {
          const point = r.timeline.find(p => p.timestep === t);
          if (point?.risk_score !== undefined) {
            row[`${r.backend}_risk_score`] = point.risk_score;
          }
        }
      }

      data.push(row);
    }
    return data;
  }, [results]);

  const burstRegions = useMemo(() => {
    const mainResult = results.find(r => !r.counterfactual);
    if (!mainResult) return [];
    const regions: { start: number, end: number }[] = [];
    let start: number | null = null;
    for (const p of mainResult.timeline) {
      if (p.in_burst && start === null) start = p.timestep;
      if (!p.in_burst && start !== null) {
        regions.push({ start, end: p.timestep - 1 });
        start = null;
      }
    }
    if (start !== null) regions.push({ start, end: mainResult.timeline[mainResult.timeline.length - 1].timestep });
    return regions;
  }, [results]);

  return (
    <div style={{ background: '#0a0c10', minHeight: '100vh', color: 'var(--color-text-primary)' }}>
      {/* ─── Header ─── */}
      <div
        style={{
          height: 52,
          background: '#0d0f14',
          borderBottom: '1px solid #1e2d47',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0 24px',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <button
          onClick={() => navigate('/')}
          style={{
            background: 'transparent',
            border: 0,
            padding: 0,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <img
            src={logoImg}
            alt="Driftwatch Logo"
            style={{ height: 32, width: 'auto', borderRadius: 4, border: '1px solid rgba(255,255,255,0.05)' }}
          />
          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 14,
              fontWeight: 'bold',
              color: '#00e5ff',
              letterSpacing: '0.15em',
            }}
          >
            DRIFTWATCH
          </span>
        </button>
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: 'var(--color-text-ghost)' }}>
          OVERSIGHT DECAY SIMULATION
        </div>
      </div>

      {/* ─── Main Content ─── */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px 80px' }}>
        {/* Explainer */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            background: '#111318',
            border: '1px solid #1e2d47',
            borderLeft: '3px solid #06b6d4',
            padding: '20px 24px',
            marginBottom: 28,
          }}
        >
          <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: '#06b6d4', letterSpacing: '0.1em', marginBottom: 12 }}>
            WHAT THIS SIMULATION MEASURES
          </div>
          <ul style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-secondary)', lineHeight: 1.6, paddingLeft: 20, margin: 0 }}>
            <li style={{ marginBottom: 8 }}>
              <strong style={{ color: 'var(--color-text-primary)' }}>Review Probability:</strong> The likelihood a human will actually check the AI's work. Drops due to automation bias and latency.
            </li>
            <li style={{ marginBottom: 8 }}>
              <strong style={{ color: 'var(--color-text-primary)' }}>Silent Errors:</strong> Mistakes the AI makes that the human fails to catch. Spikes during AI hallucinations (bursts).
            </li>
            <li style={{ marginBottom: 8 }}>
              <strong style={{ color: 'var(--color-text-primary)' }}>Oversight Debt:</strong> The cumulative shortfall between initial review capacity and the review probability that remains over time.
            </li>
            <li>
              <strong style={{ color: 'var(--color-text-primary)' }}>Live Risk Score:</strong> An ML-driven prediction (0-100%) of whether oversight will completely collapse, based purely on the first 10 timesteps.
            </li>
          </ul>
        </motion.div>

        {/* ─── Configuration Panel ─── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-panel"
          style={{ padding: 24, marginBottom: 28, borderRadius: 0 }}
        >
          <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: '#00e5ff', letterSpacing: '0.1em', marginBottom: 20 }}>
            SIMULATION CONFIGURATION
          </div>

          {/* Backend selector */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 8, fontFamily: 'var(--font-data)' }}>
              MODEL BACKENDS (select one or more to compare)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
              {BACKENDS.map(b => {
                const isSelected = selectedBackends.includes(b.id);
                return (
                  <button
                    key={b.id}
                    onClick={() => toggleBackend(b.id)}
                    disabled={running}
                    style={{
                      background: isSelected ? `${b.color}15` : '#0b0f19',
                      border: `1px solid ${isSelected ? b.color : '#1e2d47'}`,
                      padding: '12px 14px',
                      cursor: running ? 'default' : 'pointer',
                      textAlign: 'left',
                      transition: 'all 150ms ease-out',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <div style={{
                        width: 10, height: 10,
                        border: `2px solid ${isSelected ? b.color : 'var(--color-text-ghost)'}`,
                        background: isSelected ? b.color : 'transparent',
                      }} />
                      <span style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: isSelected ? b.color : 'var(--color-text-secondary)' }}>
                        {b.label}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-ghost)', paddingLeft: 18 }}>
                      {b.description}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Domain Selector */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 8 }}>
              Simulation Domain
            </div>
            <select
              value={selectedDomain}
              onChange={e => setSelectedDomain(e.target.value)}
              disabled={running}
              style={{
                width: '100%',
                padding: '8px 12px',
                background: '#13161f',
                border: '1px solid #1e2d47',
                borderRadius: 4,
                color: 'var(--color-text-primary)',
                fontSize: 13,
                outline: 'none',
              }}
            >
              {domains.map(d => (
                <option key={d.id} value={d.id}>
                  {d.name} — {d.description}
                </option>
              ))}
            </select>
          </div>

          {/* Sliders */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 20, marginBottom: 20 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-dim)' }}>Population</span>
                <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{population.toLocaleString()}</span>
              </div>
              <input
                type="range" min="10" max="5000" step="10" value={population}
                onChange={e => setPopulation(Number(e.target.value))}
                onInput={e => setPopulation(Number(e.currentTarget.value))}
                disabled={running}
                style={{ width: '100%', accentColor: 'var(--color-primary)' }}
              />
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-dim)' }}>Timesteps</span>
                <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{timesteps}</span>
              </div>
              <input
                type="range" min="5" max="100" step="5" value={timesteps}
                onChange={e => setTimesteps(Number(e.target.value))}
                onInput={e => setTimesteps(Number(e.currentTarget.value))}
                disabled={running}
                style={{ width: '100%', accentColor: 'var(--color-primary)' }}
              />
            </div>
          </div>

          {/* Phase 3 Controls */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginBottom: 20, background: 'rgba(0,229,255,0.02)', border: '1px solid rgba(0,229,255,0.1)', padding: 16 }}>
            <div style={{ gridColumn: '1 / span 3', fontFamily: 'var(--font-data)', fontSize: 10, color: '#00e5ff', letterSpacing: '0.1em' }}>
              PHASE 3: DEPTH VARIABLES
            </div>

            {/* Language Mismatch */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-dim)' }}>Language Mismatch</span>
                <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{(languageMismatchRatio * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range" min="0" max="1" step="0.1" value={languageMismatchRatio}
                onChange={e => setLanguageMismatchRatio(Number(e.target.value))}
                onInput={e => setLanguageMismatchRatio(Number(e.currentTarget.value))}
                disabled={running}
                style={{ width: '100%', accentColor: '#00e5ff' }}
              />
              <div style={{ fontSize: 10, color: 'var(--color-text-ghost)', marginTop: 4 }}>
                % of citizens penalized for caseworker language
              </div>
            </div>

            {/* Explanation Style */}
            <div>
              <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 4 }}>
                Explanation Style
              </div>
              <select
                value={explanationStyle}
                onChange={e => setExplanationStyle(e.target.value)}
                disabled={running}
                style={{ width: '100%', padding: '6px 8px', background: '#0b0f19', border: '1px solid #1e2d47', color: 'var(--color-text-primary)', fontSize: 12 }}
              >
                <option value="detailed">Detailed (Standard)</option>
                <option value="terse">Terse (Stripped)</option>
              </select>
              <div style={{ fontSize: 10, color: 'var(--color-text-ghost)', marginTop: 4 }}>
                "Terse" reduces effective review skill
              </div>
            </div>

            {/* Confidence Calibration */}
            <div>
              <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 4 }}>
                Confidence Calibration
              </div>
              <div style={{ display: 'flex', alignItems: 'center', height: '28px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={confidenceCalibrated}
                    onChange={e => setConfidenceCalibrated(e.target.checked)}
                    disabled={running}
                    style={{ accentColor: '#00e5ff' }}
                  />
                  <span style={{ fontSize: 12, color: 'var(--color-text-primary)' }}>Calibrated Output</span>
                </label>
              </div>
              <div style={{ fontSize: 10, color: 'var(--color-text-ghost)', marginTop: 4 }}>
                Uncalibrated conceals errors with high confidence
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-dim)' }}>Difficulty</span>
                <span style={{ fontFamily: 'var(--font-data)', color: difficulty > 0.7 ? 'var(--color-alert)' : difficulty > 0.4 ? 'var(--color-warn)' : 'var(--color-success)' }}>
                  {difficulty < 0.3 ? 'Easy' : difficulty < 0.7 ? 'Medium' : 'Hard'} ({(difficulty * 100).toFixed(0)}%)
                </span>
              </div>
              <input
                type="range" min="0" max="1" step="0.05" value={difficulty}
                onChange={e => setDifficulty(Number(e.target.value))}
                onInput={e => setDifficulty(Number(e.currentTarget.value))}
                disabled={running}
                style={{ width: '100%', accentColor: 'var(--color-primary)' }}
              />
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-dim)' }}>Shock Interval</span>
                <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>
                  {shockInterval === 0 ? 'Disabled' : `${shockInterval} steps (±30%)`}
                </span>
              </div>
              <input
                type="range" min="0" max="30" step="5" value={shockInterval}
                onChange={e => setShockInterval(Number(e.target.value))}
                onInput={e => setShockInterval(Number(e.currentTarget.value))}
                disabled={running}
                style={{ width: '100%', accentColor: 'var(--color-primary)' }}
              />
            </div>
          </div>

          {/* Phase 4 & 5 Controls */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
            {/* Phase 5: Network Topology */}
            <div style={{ background: 'rgba(239,68,68,0.02)', border: '1px solid rgba(239,68,68,0.1)', padding: 16 }}>
              <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: '#ef4444', letterSpacing: '0.1em', marginBottom: 16 }}>
                PHASE 5: SOCIAL CONTAGION
              </div>

              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 4 }}>
                  Network Topology
                </div>
                <select
                  value={networkTopology}
                  onChange={e => setNetworkTopology(e.target.value)}
                  disabled={running}
                  style={{ width: '100%', padding: '6px 8px', background: '#0b0f19', border: '1px solid #1e2d47', color: 'var(--color-text-primary)', fontSize: 12 }}
                >
                  <option value="isolated">Isolated (No social influence)</option>
                  <option value="random">Random Graph (Dense)</option>
                  <option value="small_world">Small-World (Clustered)</option>
                </select>
              </div>

              {networkTopology !== 'isolated' && (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                      <span style={{ color: 'var(--color-text-dim)' }}>Neighbors (K)</span>
                      <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{networkK}</span>
                    </div>
                    <input
                      type="range" min="2" max="50" step="1" value={networkK}
                      onChange={e => setNetworkK(Number(e.target.value))}
                      onInput={e => setNetworkK(Number(e.currentTarget.value))}
                      disabled={running}
                      style={{ width: '100%', accentColor: '#ef4444' }}
                    />
                  </div>

                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                      <span style={{ color: 'var(--color-text-dim)' }}>Social Influence Weight</span>
                      <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{(socialInfluenceWeight * 100).toFixed(0)}%</span>
                    </div>
                    <input
                      type="range" min="0" max="1" step="0.1" value={socialInfluenceWeight}
                      onChange={e => setSocialInfluenceWeight(Number(e.target.value))}
                      onInput={e => setSocialInfluenceWeight(Number(e.currentTarget.value))}
                      disabled={running}
                      style={{ width: '100%', accentColor: '#ef4444' }}
                    />
                  </div>
                </>
              )}
            </div>

            {/* Phase 4: Adversarial */}
            <div style={{ background: 'rgba(192,132,252,0.02)', border: '1px solid rgba(192,132,252,0.1)', padding: 16 }}>
              <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: '#c084fc', letterSpacing: '0.1em', marginBottom: 16 }}>
                PHASE 4: STRATEGIC ADVERSARIES
              </div>

              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                  <span style={{ color: 'var(--color-text-dim)' }}>Adversary Ratio</span>
                  <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{(adversaryRatio * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range" min="0" max="0.3" step="0.05" value={adversaryRatio}
                  onChange={e => setAdversaryRatio(Number(e.target.value))}
                  onInput={e => setAdversaryRatio(Number(e.currentTarget.value))}
                  disabled={running}
                  style={{ width: '100%', accentColor: '#c084fc' }}
                />
                <div style={{ fontSize: 10, color: 'var(--color-text-ghost)', marginTop: 4 }}>
                  % of population attempting fraud
                </div>
              </div>

              {adversaryRatio > 0 && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                    <span style={{ color: 'var(--color-text-dim)' }}>Attack Episodes</span>
                    <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{adversaryEpisodes}</span>
                  </div>
                  <input
                    type="range" min="1" max="5" step="1" value={adversaryEpisodes}
                    onChange={e => setAdversaryEpisodes(Number(e.target.value))}
                    onInput={e => setAdversaryEpisodes(Number(e.currentTarget.value))}
                    disabled={running}
                    style={{ width: '100%', accentColor: '#c084fc' }}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Phase 6 Controls */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginBottom: 20, background: 'rgba(59,130,246,0.02)', border: '1px solid rgba(59,130,246,0.1)', padding: 16 }}>
            <div style={{ gridColumn: '1 / span 3', fontFamily: 'var(--font-data)', fontSize: 10, color: '#3b82f6', letterSpacing: '0.1em' }}>
              PHASE 6: MITIGATION INTERVENTIONS
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-dim)' }}>Spot Check Rate</span>
                <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{(spotCheckRate * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range" min="0" max="0.2" step="0.05" value={spotCheckRate}
                onChange={e => setSpotCheckRate(Number(e.target.value))}
                onInput={e => setSpotCheckRate(Number(e.currentTarget.value))}
                disabled={running}
                style={{ width: '100%', accentColor: '#3b82f6' }}
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-dim)' }}>Confidence Review Threshold</span>
                <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>
                  {confidenceReviewThreshold > 0 ? `< ${confidenceReviewThreshold.toFixed(2)}` : 'Disabled'}
                </span>
              </div>
              <input
                type="range" min="0" max="1" step="0.1" value={confidenceReviewThreshold}
                onChange={e => setConfidenceReviewThreshold(Number(e.target.value))}
                onInput={e => setConfidenceReviewThreshold(Number(e.currentTarget.value))}
                disabled={running}
                style={{ width: '100%', accentColor: '#3b82f6' }}
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-dim)' }}>Mandatory Audit Interval</span>
                <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>
                  {mandatoryAuditInterval > 0 ? `Every ${mandatoryAuditInterval} steps` : 'Disabled'}
                </span>
              </div>
              <input
                type="range" min="0" max="20" step="5" value={mandatoryAuditInterval}
                onChange={e => setMandatoryAuditInterval(Number(e.target.value))}
                onInput={e => setMandatoryAuditInterval(Number(e.currentTarget.value))}
                disabled={running}
                style={{ width: '100%', accentColor: '#3b82f6' }}
              />
            </div>
          </div>

          {/* Counterfactual toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--color-text-secondary)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={showCounterfactual}
                onChange={e => setShowCounterfactual(e.target.checked)}
                disabled={running}
                style={{ accentColor: 'var(--color-primary)' }}
              />
              Include counterfactual baseline (freeze oversight — no decay)
            </label>
          </div>

          {/* Run button */}
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button
              className="primary-cta chamfered"
              onClick={running ? cancelSimulation : runSimulation}
              disabled={!running && selectedBackends.length === 0}
              style={{
                marginTop: 0,
                padding: '12px 32px',
                opacity: !running && selectedBackends.length === 0 ? 0.4 : 1,
                background: running ? 'var(--color-alert)' : undefined,
              }}
            >
              {running ? '■ Cancel' : '▶ Run Simulation'}
            </button>
            {running && (
              <span style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: 'var(--color-text-dim)' }}>
                {Object.entries(progress).map(([k, v]) => `${k}: step ${v}`).join(' · ')}
              </span>
            )}
          </div>

          {error && (
            <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.1)', border: '1px solid var(--color-alert)', fontSize: 12, color: 'var(--color-alert)' }}>
              {error}
            </div>
          )}
        </motion.div>

        {/* ─── Results ─── */}
        {results.length > 0 && (
          <>
            {/* Metric cards */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ display: 'grid', gridTemplateColumns: `repeat(${results.filter(r => !r.counterfactual).length}, 1fr)`, gap: 12, marginBottom: 28 }}
            >
              {results.filter(r => !r.counterfactual).map(r => (
                <div key={r.backend} style={{ background: '#111318', border: '1px solid #1e2d47', padding: 20 }}>
                  <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: r.color, letterSpacing: '0.1em', marginBottom: 12 }}>
                    {r.label.toUpperCase()}
                  </div>
                  <div style={{ display: 'grid', gap: 12 }}>
                    <div>
                      <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: 'var(--color-text-ghost)', marginBottom: 4 }}>
                        TIME TO 10% SILENT ERRORS
                      </div>
                      <div style={{ fontFamily: 'var(--font-display)', fontSize: 28, color: r.timeToThreshold ? 'var(--color-alert)' : 'var(--color-success)' }}>
                        {r.timeToThreshold ? `Step ${r.timeToThreshold}` : 'Never'}
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div>
                        <div style={{ fontFamily: 'var(--font-data)', fontSize: 9, color: 'var(--color-text-ghost)' }}>FINAL REVIEW PROB</div>
                        <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: r.finalReviewProb < 0.5 ? 'var(--color-warn)' : 'var(--color-text-primary)' }}>
                          {(r.finalReviewProb * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div style={{ fontFamily: 'var(--font-data)', fontSize: 9, color: 'var(--color-text-ghost)' }}>FINAL SILENT ERROR</div>
                        <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: r.finalSilentError > 0.1 ? 'var(--color-alert)' : 'var(--color-text-primary)' }}>
                          {(r.finalSilentError * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </motion.div>

            {/* Advanced Metric cards */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ display: 'grid', gridTemplateColumns: `repeat(${results.filter(r => !r.counterfactual).length}, 1fr)`, gap: 12, marginBottom: 28 }}
            >
              {results.filter(r => !r.counterfactual).map(r => (
                <div key={`${r.backend}_advanced`} style={{ background: '#111318', border: '1px solid #1e2d47', padding: 20 }}>
                  <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: r.color, letterSpacing: '0.1em', marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>{r.label.toUpperCase()} — DEGRADATION</span>
                    {(() => {
                      const finalTimeline = r.timeline[r.timeline.length - 1];
                      if (!finalTimeline || finalTimeline.risk_score === undefined) return null;
                      const rs = finalTimeline.risk_score;
                      const color = rs > 0.7 ? 'var(--color-alert)' : rs > 0.3 ? 'var(--color-warn)' : 'var(--color-success)';
                      return (
                        <div style={{
                          background: `${color}15`,
                          border: `1px solid ${color}50`,
                          padding: '2px 8px',
                          borderRadius: 12,
                          color: color
                        }}>
                          RISK SCORE: {(rs * 100).toFixed(1)}%
                        </div>
                      );
                    })()}
                  </div>
                  <div style={{ display: 'grid', gap: 12 }}>
                    <div>
                      <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: 'var(--color-text-ghost)', marginBottom: 4 }}>
                        OVERSIGHT DEBT
                      </div>
                      <div style={{ fontFamily: 'var(--font-display)', fontSize: 24, color: 'var(--color-alert)' }}>
                        {r.oversightDebt} <span style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>cases</span>
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div>
                        <div style={{ fontFamily: 'var(--font-data)', fontSize: 9, color: 'var(--color-text-ghost)' }}>HALF-LIFE</div>
                        <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--color-text-primary)' }}>
                          {r.oversightHalfLife} {typeof r.oversightHalfLife === 'number' ? 'steps' : ''}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontFamily: 'var(--font-data)', fontSize: 9, color: 'var(--color-text-ghost)' }}>BURST CONTRIBUTION</div>
                        <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--color-text-primary)' }}>
                          {(r.burstErrorContribution * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 4, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                      <div>
                        <div style={{ fontFamily: 'var(--font-data)', fontSize: 9, color: '#00e5ff' }}>FINAL REVIEW SKILL</div>
                        <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--color-text-primary)' }}>
                          {(r.metrics?.final_avg_review_skill * 100 || 0).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div style={{ fontFamily: 'var(--font-data)', fontSize: 9, color: '#00e5ff' }}>SKILL RECOVERY</div>
                        <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--color-text-primary)' }}>
                          +{(r.metrics?.skill_recovery_rate * 100 || 0).toFixed(2)}%/step
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </motion.div>

            {/* Charts */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
              {/* Chart 1: Oversight Decay */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-panel"
                style={{ padding: 20, borderRadius: 0 }}
              >
                <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 16 }}>
                  OVERSIGHT DECAY — REVIEW PROBABILITY OVER TIME
                </div>
                <div style={{ width: '100%', height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="timestep" stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
                      <YAxis stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} />
                      <Tooltip
                        contentStyle={{ background: '#0b0f19', border: '1px solid var(--color-border)', borderRadius: 8, fontFamily: 'var(--font-data)', fontSize: 11 }}
                        formatter={(value: unknown, name: unknown) => [`${(Number(value) * 100).toFixed(1)}%`, name as string]}
                      />
                      <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 10, fontFamily: 'var(--font-data)', paddingTop: '20px' }} />
                      {results.map(r => {
                        const key = r.counterfactual ? `${r.backend}_cf` : r.backend;
                        return (
                          <Line
                            key={`${key}_rp`}
                            name={r.label}
                            type="monotone"
                            dataKey={`${key}_review_prob`}
                            stroke={r.color}
                            strokeWidth={r.counterfactual ? 1.5 : 2}
                            strokeDasharray={r.counterfactual ? '5 5' : undefined}
                            dot={false}
                          />
                        );
                      })}
                      {results[0]?.shockEvents?.map((evt, i) => (
                        <ReferenceLine key={`shock_${i}`} x={evt.timestep} stroke="var(--color-alert)" strokeDasharray="3 3" label={{ position: 'top', value: 'SHOCK', fill: 'var(--color-alert)', fontSize: 10, fontFamily: 'var(--font-data)' }} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>

              {/* Chart 2: Silent Error Rate */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="glass-panel"
                style={{ padding: 20, borderRadius: 0 }}
              >
                <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 16 }}>
                  SILENT ERROR RATE — UNDETECTED MISTAKES OVER TIME
                </div>
                <div style={{ width: '100%', height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="timestep" stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
                      <YAxis stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
                      <Tooltip
                        contentStyle={{ background: '#0b0f19', border: '1px solid var(--color-border)', borderRadius: 8, fontFamily: 'var(--font-data)', fontSize: 11 }}
                        formatter={(value: unknown, name: unknown) => [`${(Number(value) * 100).toFixed(1)}%`, name as string]}
                      />
                      <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 10, fontFamily: 'var(--font-data)', paddingTop: '20px' }} />
                      {/* 10% threshold line */}
                      <Line
                        name="10% Threshold"
                        type="monotone"
                        dataKey={() => 0.10}
                        stroke="var(--color-alert)"
                        strokeWidth={1}
                        strokeDasharray="8 4"
                        dot={false}
                        legendType="plainline"
                      />
                      {results.map(r => {
                        const key = r.counterfactual ? `${r.backend}_cf` : r.backend;
                        return (
                          <Line
                            key={`${key}_se`}
                            name={r.label}
                            type="monotone"
                            dataKey={`${key}_silent_error`}
                            stroke={r.color}
                            strokeWidth={r.counterfactual ? 1.5 : 2}
                            strokeDasharray={r.counterfactual ? '5 5' : undefined}
                            dot={false}
                          />
                        );
                      })}
                      {burstRegions.map((br, i) => (
                        <ReferenceArea key={`burst_${i}`} x1={br.start} x2={br.end} fill="rgba(255,255,255,0.05)" />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            </div>

            {/* Chart 3: Review Skill Atrophy & Chart 4: Skip Breakdown */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
              {/* Chart 3: Review Skill Atrophy */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="glass-panel"
                style={{ padding: 20, borderRadius: 0 }}
              >
                <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: '#00e5ff', marginBottom: 16 }}>
                  REVIEW SKILL DIVERGENCE (PROBABILITY vs SKILL)
                </div>
                <div style={{ width: '100%', height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="timestep" stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
                      <YAxis stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} />
                      <Tooltip
                        contentStyle={{ background: '#0b0f19', border: '1px solid var(--color-border)', borderRadius: 8, fontFamily: 'var(--font-data)', fontSize: 11 }}
                        formatter={(value: unknown, name: unknown) => [`${(Number(value) * 100).toFixed(1)}%`, name as string]}
                      />
                      <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 10, fontFamily: 'var(--font-data)', paddingTop: '20px' }} />
                      {results.filter(r => !r.counterfactual).map(r => (
                        <React.Fragment key={`${r.backend}_skill_frag`}>
                          <Line
                            key={`${r.backend}_prob`}
                            name={`${r.label} (Prob)`}
                            type="monotone"
                            dataKey={`${r.backend}_review_prob`}
                            stroke={r.color}
                            strokeWidth={1}
                            strokeDasharray="4 4"
                            dot={false}
                          />
                          <Line
                            key={`${r.backend}_skill`}
                            name={`${r.label} (Skill)`}
                            type="monotone"
                            dataKey={`${r.backend}_review_skill`}
                            stroke={r.color}
                            strokeWidth={2}
                            dot={false}
                          />
                        </React.Fragment>
                      ))}
                      {results[0]?.shockEvents?.map((evt, i) => (
                        <ReferenceLine key={`shock_${i}`} x={evt.timestep} stroke="var(--color-alert)" strokeDasharray="3 3" />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="glass-panel"
                style={{ padding: 20, borderRadius: 0 }}
              >
                <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 16 }}>
                  REVIEW SKILL ATROPHY — CITIZEN ERROR-DETECTION CAPABILITY
                </div>
                <div style={{ width: '100%', height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="timestep" stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
                      <YAxis stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} />
                      <Tooltip
                        contentStyle={{ background: '#0b0f19', border: '1px solid var(--color-border)', borderRadius: 8, fontFamily: 'var(--font-data)', fontSize: 11 }}
                        formatter={(value: unknown, name: unknown) => [`${(Number(value) * 100).toFixed(1)}%`, name as string]}
                      />
                      <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 10, fontFamily: 'var(--font-data)', paddingTop: '20px' }} />
                      {results.map(r => {
                        const key = r.counterfactual ? `${r.backend}_cf` : r.backend;
                        return (
                          <Line
                            key={`${key}_skill`}
                            name={r.label}
                            type="monotone"
                            dataKey={`${key}_skill`}
                            stroke={r.color}
                            strokeWidth={r.counterfactual ? 1.5 : 2}
                            strokeDasharray={r.counterfactual ? '5 5' : undefined}
                            dot={false}
                          />
                        );
                      })}
                      {results[0]?.shockEvents?.map((evt, i) => (
                        <ReferenceLine key={`shock_${i}`} x={evt.timestep} stroke="var(--color-alert)" strokeDasharray="3 3" label={{ position: 'top', value: 'SHOCK', fill: 'var(--color-alert)', fontSize: 10, fontFamily: 'var(--font-data)' }} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>

              {/* Chart 4: Skip Breakdown */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="glass-panel"
                style={{ padding: 20, borderRadius: 0 }}
              >
                <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 16 }}>
                  SKIP BREAKDOWN — LATENCY VS TRUST
                </div>
                <div style={{ width: '100%', height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="timestep" stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
                      <YAxis stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
                      <Tooltip
                        contentStyle={{ background: '#0b0f19', border: '1px solid var(--color-border)', borderRadius: 8, fontFamily: 'var(--font-data)', fontSize: 11 }}
                      />
                      <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 10, fontFamily: 'var(--font-data)', paddingTop: '20px' }} />
                      {results.filter(r => !r.counterfactual).flatMap(r => [
                        <Area key={`${r.backend}_latency`} type="monotone" dataKey={`${r.backend}_latency_skips`} stackId={r.backend} stroke={r.color} fill={r.color} fillOpacity={0.6} name={`${r.label} (Latency Skip)`} />,
                        <Area key={`${r.backend}_trust`} type="monotone" dataKey={`${r.backend}_trust_skips`} stackId={r.backend} stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.6} name={`${r.label} (Trust Skip)`} />
                      ])}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            </div>

          </>
        )}

        {/* Empty state */}
        {results.length === 0 && !running && (
          <div style={{
            textAlign: 'center',
            padding: '80px 24px',
            color: 'var(--color-text-ghost)',
            fontFamily: 'var(--font-data)',
            fontSize: 13,
          }}>
            Select model backends and click "Run Simulation" to begin.
            <br />
            <span style={{ fontSize: 11, marginTop: 8, display: 'block' }}>
              Results will appear here with real-time oversight decay curves.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
