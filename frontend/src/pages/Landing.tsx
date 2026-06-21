import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useTypewriter } from '../hooks/useTypewriter';
import logoImg from '../assets/driftwatch-logo.png';

const tickerItems = [
  ['Citizen #2,847', 'Skipped review — trust at 94%'],
  ['Citizen #891', 'Caught error — trust boost +5%'],
  ['Citizen #6,203', 'Auto-approved — no review'],
  ['Citizen #1,544', 'Skill decay triggered'],
  ['Citizen #9,012', 'Silent error — undetected'],
  ['Citizen #3,777', 'Reviewed — decision correct'],
  ['Citizen #428', 'Review probability dropped to 31%'],
  ['Citizen #7,661', 'Oversight threshold breached'],
];

const howSteps = [
  {
    step: 'STEP 01',
    kicker: 'Choose your model',
    title: 'Pick the AI caseworker',
    body: 'Select from three model tiers: GPT-4o (large/closed), Llama 3.1 8B (open-source/API), or Llama 3.1 quantized (on-device). Same prompt, different brain.',
  },
  {
    step: 'STEP 02',
    kicker: 'Cases are generated',
    title: 'Deterministic ground truth',
    body: 'An oracle generates administrative cases — benefits eligibility, dispute resolutions — each with an objectively correct answer. The AI caseworker decides on each one.',
  },
  {
    step: 'STEP 03',
    kicker: 'Citizens drift',
    title: 'Oversight decays',
    body: 'Each citizen has a review probability that drifts. When the AI is right, trust grows and review drops. When review drops, skill atrophies. Errors slip through silently.',
  },
  {
    step: 'STEP 04',
    kicker: 'Compare the models',
    title: 'Does model choice matter?',
    body: 'The dashboard shows oversight decay curves, silent error rates, and time-to-threshold for each model tier side-by-side. The gap between lines is the answer.',
  },
];

export default function Landing() {
  const navigate = useNavigate();
  const { displayText, isComplete } = useTypewriter(
    'An AI caseworker makes decisions. Citizens stop checking. Errors compound silently. Driftwatch measures how fast oversight collapses — and whether the model matters.',
    18,
    800
  );

  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });

  return (
    <div style={{ background: '#0a0c10', color: 'var(--color-text-primary)' }}>
      <section style={{ minHeight: '100vh', position: 'relative', overflow: 'hidden', padding: '28px 28px 72px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            onClick={() => navigate('/')}
            style={{
              background: 'transparent',
              border: 0,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: 0,
            }}
          >
            <img src={logoImg} alt="Driftwatch Logo" style={{ height: 36, width: 'auto', borderRadius: 4 }} />
            <span style={{
              fontFamily: 'var(--font-data)',
              fontSize: 16,
              letterSpacing: '0.15em',
              color: '#00e5ff',
              fontWeight: 'bold',
            }}>
              DRIFTWATCH<span className="cursor-blink">_</span>
            </span>
          </button>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', color: 'var(--color-text-ghost)' }}>
            <button className="landing-link" onClick={() => scrollTo('how')}>How it works</button>
            <span>·</span>
            <a className="landing-link" href="https://github.com/TavishAgarwal/Driftwatch" target="_blank" rel="noreferrer">
              GitHub →
            </a>
          </div>
        </div>

        <div
          style={{
            minHeight: 'calc(100vh - 140px)',
            display: 'grid',
            placeItems: 'center',
            textAlign: 'center',
          }}
        >
          <div>
            <div
              style={{
                fontFamily: 'var(--font-data)',
                fontSize: 11,
                color: 'var(--color-text-dim)',
                letterSpacing: '0.12em',
                marginBottom: 20,
              }}
            >
              <span className="pulse-square">■</span> OVERSIGHT DECAY SIMULATION ENGINE
            </div>
            <h1 className="landing-headline">
              <span>When AI decides,</span>
              <span>humans stop watching.</span>
              <span style={{ color: '#00e5ff' }}>We measure the drift.</span>
            </h1>
            <p className={`landing-subhead ${isComplete ? 'typewriter-cursor landing-cursor-fade' : 'typewriter-cursor'}`}>
              {displayText}
            </p>
            <div className="landing-stats">
              {['3 Model Tiers', 'Trust Decay Loop', 'Silent Error Tracking'].map((stat, index) => (
                <motion.span
                  key={stat}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 2.7 + index * 0.2 }}
                >
                  {index > 0 && <span style={{ color: 'var(--color-text-ghost)', margin: '0 14px' }}>·</span>}
                  {stat}
                </motion.span>
              ))}
            </div>
            <button className="primary-cta chamfered" onClick={() => navigate('/driftwatch')}>
              Run a simulation →
            </button>
            <button className="landing-demo-link" onClick={() => scrollTo('how')}>
              or learn how it works ↓
            </button>
          </div>
        </div>

        <div className="agent-ticker">
          <div className="agent-ticker-track">
            {[0, 1].map((copy) => (
              <span key={copy} style={{ paddingRight: 120 }}>
                {tickerItems.map(([name, decision], index) => (
                  <span key={`${copy}-${name}`}>
                    <span style={{ color: 'var(--color-text-secondary)' }}>{name}</span>
                    <span> → {decision}</span>
                    <span style={{ color: 'var(--color-text-ghost)' }}>{index === tickerItems.length - 1 ? '        ' : ' · '}</span>
                  </span>
                ))}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section id="how" style={{ background: '#0d0f14', borderTop: '1px solid #1e2d47', padding: '80px 24px' }}>
        <h2 className="section-heading">How it works</h2>
        <div className="section-rule" />
        <div className="how-grid">
          {howSteps.map((item) => (
            <div key={item.step} className="how-card">
              <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 10 }}>{item.step}</div>
              <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: '#00e5ff', marginBottom: 6 }}>{item.kicker.toUpperCase()}</div>
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 22, marginBottom: 8 }}>{item.title}</h3>
              <p style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>{item.body}</p>
            </div>
          ))}
        </div>
        <div style={{ textAlign: 'center', marginTop: 36 }}>
          <button className="primary-cta chamfered" onClick={() => navigate('/driftwatch')}>
            Start simulating →
          </button>
        </div>
      </section>

      <section style={{ background: '#0a0c10', padding: '80px 24px', textAlign: 'center' }}>
        <h2 className="section-heading">The Core Question</h2>
        <div className="section-rule" />
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <p style={{ fontSize: 18, lineHeight: 1.7, color: 'var(--color-text-secondary)', marginBottom: 28 }}>
            When an AI caseworker is usually right, people stop checking its work. Their ability to spot errors atrophies.
            Errors accumulate invisibly. This is <strong style={{ color: '#00e5ff' }}>oversight decay</strong>.
          </p>
          <div className="how-grid" style={{ gap: 16, marginBottom: 32 }}>
            {[
              ['TRUST BUILDS', 'AI is usually right → citizens stop reviewing', '#1aad6e'],
              ['SKILLS ATROPHY', 'Without practice → error detection declines', '#ffb347'],
              ['ERRORS SLIP', 'AI makes mistakes → nobody notices', '#ff0055'],
              ['FAILURES COMPOUND', 'Undetected errors accumulate over time', '#c084fc'],
            ].map(([title, desc, color]) => (
              <div key={title} className="how-card" style={{ borderLeft: `3px solid ${color}` }}>
                <div style={{ fontFamily: 'var(--font-data)', fontSize: 11, color, marginBottom: 6 }}>{title}</div>
                <p style={{ fontSize: 14, lineHeight: 1.5, color: 'var(--color-text-secondary)' }}>{desc}</p>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 15, lineHeight: 1.6, color: 'var(--color-text-dim)' }}>
            Driftwatch tests whether the AI model powering the caseworker — large/closed, open-source/API, or local/quantized —
            changes how fast this decay happens. Same cases, same citizens, different brain.
          </p>
        </div>
      </section>

      <footer className="landing-footer">
        <span>DRIFTWATCH</span>
        <span>2026 · Oversight Decay Research</span>
        <a href="https://github.com/TavishAgarwal/Driftwatch" target="_blank" rel="noreferrer">
          GitHub
        </a>
      </footer>
    </div>
  );
}
