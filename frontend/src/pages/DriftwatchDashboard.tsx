import { useState, useCallback, useRef, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
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
}

/* ─── Model backends ─── */
const BACKENDS = [
  { id: 'openai', label: 'GPT-4o (Closed)', color: '#ef4444', description: 'Large closed model via OpenAI API' },
  { id: 'ollama_api', label: 'Llama 3.1 8B (Open)', color: '#06b6d4', description: 'Open-source model via Ollama' },
  { id: 'ollama_local', label: 'Llama 3.1 Q4 (Local)', color: '#c084fc', description: 'Quantized model running locally' },
  { id: 'rule_based', label: 'Rule-Based (Fallback)', color: '#f59e0b', description: 'Deterministic rules — no LLM' },
];

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
  };
  message?: string;
}

export default function DriftwatchDashboard() {
  const navigate = useNavigate();
  const [selectedBackends, setSelectedBackends] = useState<string[]>(['rule_based']);
  const [population, setPopulation] = useState(500);
  const [timesteps, setTimesteps] = useState(30);
  const [difficulty, setDifficulty] = useState(0.5);
  const [showCounterfactual, setShowCounterfactual] = useState(false);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [results, setResults] = useState<RunResult[]>([]);
  const [error, setError] = useState('');
  const [fallbackWarnings, setFallbackWarnings] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

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
    setFallbackWarnings([]);

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

            if (evt.event === 'timestep_update' && evt.timestep !== undefined) {
              timeline.push({
                timestep: evt.timestep,
                avg_review_probability: evt.avg_review_probability ?? 0,
                avg_review_skill: evt.avg_review_skill ?? 0,
                silent_error_rate: evt.silent_error_rate ?? 0,
                total_decisions: evt.total_decisions ?? 0,
                total_errors: evt.total_errors ?? 0,
                total_caught: evt.total_caught ?? 0,
                total_reviewed: evt.total_reviewed ?? 0,
              });
              setProgress(prev => ({ ...prev, [runKey]: evt.timestep! }));
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
              });
              setResults([...allResults]);
            }

            if (evt.event === 'backend_fallback' && evt.message) {
              setFallbackWarnings(prev => [...prev, evt.message!]);
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
  }, [selectedBackends, population, timesteps, difficulty, showCounterfactual]);

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
        }
      }
      data.push(row);
    }
    return data;
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
          <p style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
            <strong style={{ color: '#00e5ff' }}>Driftwatch</strong> measures how quickly humans stop checking AI decisions —
            and how that inattention compounds errors over time. Each line represents a different AI model making
            the same administrative decisions. The gap between lines reveals whether model choice matters for
            oversight collapse, not just accuracy.
          </p>
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

          {/* Sliders */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginBottom: 20 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-dim)' }}>Population</span>
                <span style={{ fontFamily: 'var(--font-data)', color: 'var(--color-text-primary)' }}>{population.toLocaleString()}</span>
              </div>
              <input
                type="range" min="1" max="5000" step="1" value={population}
                onChange={e => setPopulation(Number(e.target.value))}
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
                type="range" min="1" max="100" step="1" value={timesteps}
                onChange={e => setTimesteps(Number(e.target.value))}
                disabled={running}
                style={{ width: '100%', accentColor: 'var(--color-primary)' }}
              />
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
                disabled={running}
                style={{ width: '100%', accentColor: 'var(--color-primary)' }}
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

        {/* ─── Fallback Warnings ─── */}
        {fallbackWarnings.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.4)',
              borderLeft: '3px solid #f59e0b',
              padding: '14px 18px',
              marginBottom: 20,
            }}
          >
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: '#f59e0b', letterSpacing: '0.1em', marginBottom: 8 }}>
              ⚠ BACKEND FALLBACK DETECTED
            </div>
            {fallbackWarnings.map((msg, i) => (
              <div key={i} style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.5, marginBottom: i < fallbackWarnings.length - 1 ? 6 : 0 }}>
                {msg}
              </div>
            ))}
          </motion.div>
        )}

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
                      <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
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
                      <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
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
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            </div>

            {/* Chart 3: Review Skill Atrophy */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="glass-panel"
              style={{ padding: 20, borderRadius: 0, marginBottom: 28 }}
            >
              <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 16 }}>
                REVIEW SKILL ATROPHY — CITIZEN ERROR-DETECTION CAPABILITY
              </div>
              <div style={{ width: '100%', height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="timestep" stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
                    <YAxis stroke="var(--color-text-ghost)" style={{ fontSize: 10, fontFamily: 'var(--font-data)' }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} />
                    <Tooltip
                      contentStyle={{ background: '#0b0f19', border: '1px solid var(--color-border)', borderRadius: 8, fontFamily: 'var(--font-data)', fontSize: 11 }}
                      formatter={(value: unknown, name: unknown) => [`${(Number(value) * 100).toFixed(1)}%`, name as string]}
                    />
                    <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: 10, fontFamily: 'var(--font-data)' }} />
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
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </motion.div>
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
