# Driftwatch

**A simulation testing whether AI model choice (large/closed vs. small/open-source/on-device) changes how fast human oversight of AI-made decisions collapses, even when no single decision is catastrophic.**

---

## The Core Question

When an AI system makes mostly-correct administrative decisions, humans quickly stop checking. This oversight decay creates a compounding feedback loop:

1. **Trust builds** — the AI is usually right, so citizens stop reviewing
2. **Skills atrophy** — without practice, citizens lose the ability to spot errors
3. **Errors slip through** — when the AI gets it wrong, nobody notices
4. **Silent failures compound** — incorrect decisions accumulate invisibly

Driftwatch measures this process across three different AI model tiers to test whether the model powering the caseworker affects how fast oversight collapses:

| Backend | Model | Access |
|---|---|---|
| **Closed** | GPT-4o | OpenAI API |
| **Open (API)** | Llama 3.1 8B | Ollama API |
| **Local (Quantized)** | Llama 3.1 Q4_K_M | Ollama local GGUF |

## Architecture

```
┌────────────────────────────────────────────────────────┐
│  Driftwatch Simulation Engine                          │
│                                                        │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Case     │───▶│  Caseworker  │───▶│  Oversight   │  │
│  │  Oracle   │    │  Agent       │    │  Logic       │  │
│  │ (ground   │    │ (pluggable   │    │ (trust decay │  │
│  │  truth)   │    │  backend)    │    │  loop)       │  │
│  └──────────┘    └──────────────┘    └──────────────┘  │
│                         │                              │
│              ┌──────────┴──────────┐                   │
│              │                     │                   │
│         ┌────▼────┐  ┌────────────▼┐  ┌────────────┐  │
│         │ GPT-4o  │  │ Llama 3.1   │  │ Llama 3.1  │  │
│         │ (closed)│  │ 8B (API)    │  │ Q4 (local) │  │
│         └─────────┘  └─────────────┘  └────────────┘  │
│                                                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Citizen Population (Tier 1/2/3 agents)         │   │
│  │  + review_probability + review_skill tracking   │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────┘
```

## Advanced Simulation Mechanics

The engine includes several interconnected sub-systems that model complex societal dynamics:

- **Phase 3: Depth Variables**
  - **Language Mismatch**: Models non-native speakers who face a "complexity tax" making errors harder to detect.
  - **Confidence Calibration**: Simulates how highly-confident (but wrong) AI output drastically reduces human error detection.
  - **Explanation Style**: Toggles between detailed rationales (higher trust, faster skill decay) and terse outputs.

- **Phase 4: Strategic Adversaries**
  - Introduces intelligent bad actors who probe the system for weaknesses. When the AI makes silent errors, adversaries detect the vulnerability and systematically exploit it with fraudulent submissions.

- **Phase 5: Social Contagion**
  - Uses network topologies (Isolated, Ring, Small-World, Scale-Free, Fully Connected) to model how trust in the AI spreads through social connections. A neighbor catching an AI error can trigger a localized spike in oversight, while systemic trust accelerates decay.

- **Phase 6: Mitigation Interventions**
  - **Spot Checks**: Randomly forcing human review to break automation bias.
  - **Confidence Thresholds**: Routing low-confidence AI decisions directly to mandatory review.
  - **Mandatory Audits**: Periodic deep-dives that reset trust levels and help recover lost oversight skills.

## Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) Ollama for open-source/local models
- (Optional) OpenAI API key for GPT-4o backend

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m backend.api.main
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Run with Docker
```bash
docker-compose up
```

## Key Metrics

| Metric | Description |
|---|---|
| **Oversight Decay** | Average `review_probability` across citizens over time |
| **Silent Error Rate** | Fraction of incorrect decisions that go unnoticed |
| **Time-to-Threshold** | First timestep where silent error rate exceeds 10% |

## Environment Variables

```env
# Model backend selection
CASEWORKER_MODEL_BACKEND=rule_based  # openai | ollama_api | ollama_local | rule_based

# OpenAI (for closed backend)
OPENAI_API_KEY=sk-...

# Ollama (for open/local backends)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_API_MODEL=llama3.1:8b
OLLAMA_LOCAL_MODEL=llama3.1:8b-instruct-q4_K_M
```

## License

MIT
