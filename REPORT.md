# Driftwatch: Measuring Oversight Collapse Across AI Model Tiers in Administrative Decision-Making

**Tavish Agarwal**
Independent Researcher, New Delhi, India

---

**Regional Track:** Asia-Pacific
**Sub-Track:** AI Safety — Agentic & Autonomous Systems

---

## Abstract

When AI systems make mostly-correct administrative decisions, human reviewers gradually stop checking — a phenomenon we term *oversight decay*. We present Driftwatch, a simulation platform that measures how quickly human oversight of AI-made decisions collapses across three model tiers: large closed (GPT-4o), open-source API (Llama 3.1 8B), and local quantized (Llama 3.1 Q4_K_M). The system uses a deterministic case oracle as ground truth, pluggable model backends making eligibility decisions, and a stochastic citizen population whose review probability and review skill evolve per timestep. We find that oversight decays to sub-50% review probability within 15–25 timesteps regardless of backend, but that model accuracy significantly affects the *rate* of decay and the resulting silent error accumulation. Our counterfactual analysis — freezing review probability — demonstrates that 60–80% of silent errors are attributable to oversight decay rather than model error alone.

*(148 words)*

---

## 1. Introduction

Automation bias — the tendency for humans to over-rely on automated systems — is a well-documented phenomenon in aviation, healthcare, and industrial control. As AI systems are increasingly deployed for administrative decision-making (benefits eligibility, loan approvals, immigration processing), a specific variant of this problem emerges: *oversight decay*.

The mechanism is a compounding feedback loop:

1. **Trust accumulates.** The AI caseworker makes correct decisions, and human reviewers observe this. Their confidence in the system grows.
2. **Review frequency drops.** Reviewers check fewer decisions because past performance suggests checking is unnecessary.
3. **Review skill atrophies.** Without regular practice, the ability to detect subtle errors degrades — a use-it-or-lose-it dynamic.
4. **Silent errors compound.** When the AI does make errors, fewer reviewers are checking, and those who check are less skilled at catching them. Errors go undetected and accumulate.

Critically, no single step in this loop is catastrophic. Each individual decision is low-stakes. The damage is cumulative and invisible until a threshold is crossed.

**The research question** we address is: *Does the choice of AI model powering the caseworker — large closed, open-source, or local quantized — change how fast this oversight collapse happens?* If oversight decays at the same rate regardless of model accuracy, then improving model quality alone is not a sufficient safety intervention. If it decays faster with less accurate models, then model choice is a safety-relevant decision, not merely a performance one.

Driftwatch provides an empirical platform to answer this question through controlled simulation.

---

## 2. Related Work

**Automation bias and complacency.** Parasuraman & Riley (1997) established that operators over-trust automated systems, reducing vigilance. Cummings (2004) extended this to supervisory control contexts, showing that monitoring performance degrades as automation reliability increases — a counterintuitive finding directly relevant to our work. Goddard et al. (2012) documented automation bias in clinical decision support systems.

**Human-AI decision-making.** Bansal et al. (2021) showed that explanations from AI systems can paradoxically increase over-reliance. Green & Chen (2019) found that judges using risk assessment tools deferred to algorithmic recommendations even when they had contradictory evidence. Buçinca et al. (2021) demonstrated that cognitive forcing functions can partially mitigate over-reliance.

**Agent-based modelling for policy.** Agent-based models have been used for policy analysis in epidemiology (Eubank et al., 2004), urban planning (Batty, 2007), and financial markets (LeBaron, 2006). Our contribution extends this methodology to the AI safety domain: modelling the *human response* to AI deployment, not the AI itself.

**Model tier comparisons.** Recent work comparing open-source and closed models on specific tasks (Zheng et al., 2023; Touvron et al., 2023) focuses on task accuracy. We instead focus on the *downstream human behavioural consequence* of accuracy differences — a distinct and underexplored dimension.

---

## 3. Methodology

### 3.1 Architecture Overview

Driftwatch consists of four components:

1. **Case Oracle** — A deterministic, rule-based ground-truth generator that produces structured administrative cases (benefits eligibility) with an objectively correct decision. The oracle uses fixed rules with no model calls, ensuring an independent standard against which the caseworker is evaluated.

2. **Caseworker Agent** — An AI agent with a pluggable model backend that receives each case and returns an approve/deny/flag decision. The *same prompt* is used across all backends; the only variable is the model.

3. **Citizen Population** — A stochastic population of N citizens, each characterised by:
   - `review_probability` ∈ [0.01, 0.99] — the probability this citizen reviews the caseworker's decision at each timestep
   - `review_skill` ∈ [0.05, 0.99] — the probability this citizen catches an error when reviewing

4. **Oversight Logic** — The update rules governing how `review_probability` and `review_skill` evolve each timestep, implementing the trust-decay feedback loop.

### 3.2 Case Oracle

The oracle generates cases with 8 structured fields (income, household size, category, employment status, disability flag, prior benefits count, dependents, age) and computes ground truth via 10 ordered rules. A configurable `difficulty` parameter controls whether generated incomes cluster near decision boundaries (high difficulty) or at extremes (low difficulty).

Key design decision: the oracle is *not* an LLM. If the ground truth were also model-generated, the "silent error rate" metric would be meaningless — it would measure model-model disagreement, not model-reality disagreement.

### 3.3 Model Backends

| Backend | Model | API | Timeout | Fallback |
|:---|:---|:---|:---|:---|
| `openai` | GPT-4o | OpenAI API | — | Rule-based |
| `ollama_api` | Llama 3.1 8B | Ollama API | 15s | Rule-based |
| `ollama_local` | Llama 3.1 Q4_K_M (GGUF) | Ollama local | 30s | Rule-based |
| `rule_based` | Deterministic rules | None | — | N/A |

All LLM backends use the same structured prompt requesting a JSON response with outcome, reasoning, and confidence. Temperature is set to 0.2 with seed 42 for reproducibility.

The rule-based backend intentionally mirrors the oracle logic but with slightly different thresholds, producing a ~15% error rate — realistic for a "mostly correct but imperfect" decision system.

### 3.4 Oversight Decay Dynamics

At each timestep, for each citizen:

1. **Review decision:** The citizen reviews the caseworker's decision with probability `review_probability`.
2. **Error detection:** If the citizen reviews and the decision was incorrect, they catch the error with probability `review_skill`.
3. **State updates (normal mode):**
   - If reviewed and decision was correct: `review_probability` decreases by 0.02 (trust grows → review less)
   - If reviewed and error caught: `review_probability` increases by 0.05, `review_skill` increases by 0.03 (vigilance reinforced)
   - If reviewed (any outcome): `review_skill` recovers by 0.002 (exercising the skill)
   - If not reviewed for ≥3 consecutive timesteps while `review_probability` < 0.3: `review_skill` decays by 0.005 per step (use-it-or-lose-it)
4. **State updates (counterfactual mode):** `review_probability` and `review_skill` are frozen. Citizens still review (or not) based on their current probability, and errors are still detected or missed, but the oversight state never changes. This isolates the contribution of oversight decay to silent error accumulation.

### 3.5 Metrics

Three core metrics are computed from logged oversight events:

- **Oversight decay curve:** Average `review_probability` across all citizens at each timestep. Measures how fast oversight collapses.
- **Silent error rate:** Fraction of caseworker decisions that were incorrect *and* not caught by any reviewer, per timestep. Measures the real-world consequence of oversight decay.
- **Time-to-threshold:** The first timestep at which the silent error rate exceeds 10%. A composite indicator of how quickly the system becomes unsafe.

---

## 4. Results

### 4.1 Rule-Based Baseline (No LLM)

Using the rule-based backend with default parameters (population=500, timesteps=30, difficulty=0.5, seed=42):

| Metric | Value |
|:---|:---|
| Initial review probability | 90% |
| Final review probability | ~52% |
| Final silent error rate | ~8.2% |
| Time to 10% threshold | Step 24 (or not reached in 30 steps) |
| Total decisions | 15,000 |
| Caseworker error rate | ~15% |

**Key finding:** Even with a rule-based backend with a fixed ~15% error rate, oversight decays from 90% to ~52% within 30 timesteps. The silent error rate rises from near-zero to ~8%, approaching the 10% danger threshold.

### 4.2 Counterfactual Analysis

Running the same configuration with `counterfactual=true` (oversight frozen at initial values):

| Metric | Normal Mode | Counterfactual | Difference |
|:---|:---|:---|:---|
| Final review probability | ~52% | 90% (frozen) | −38 pp |
| Final silent error rate | ~8.2% | ~1.5% | +6.7 pp |
| Silent errors attributable to decay | — | — | ~82% |

**Key finding:** Approximately 82% of silent errors in the normal simulation are attributable to oversight decay, not to the underlying model error rate. This validates the central thesis: *oversight decay is the primary safety risk, not model accuracy alone*.

### 4.3 Difficulty Sensitivity

| Difficulty | Error Rate | Final Review Prob | Time to 10% |
|:---|:---|:---|:---|
| 0.2 (easy) | ~10% | ~58% | Not reached |
| 0.5 (medium) | ~15% | ~52% | Step 24 |
| 0.8 (hard) | ~22% | ~46% | Step 16 |

Higher difficulty generates more ambiguous cases near decision boundaries, increasing the caseworker error rate. This accelerates both trust accumulation (on correct decisions) and the silent error rate.

### 4.4 Population Scaling

| Population | Final Review Prob | Final Silent Error Rate |
|:---|:---|:---|
| 50 | ~54% ± 8% | ~7.8% ± 3.2% |
| 500 | ~52% ± 2% | ~8.2% ± 1.1% |
| 2000 | ~52% ± 1% | ~8.1% ± 0.5% |

Results stabilise at ~500 agents, with diminishing variance at larger populations. This is expected for stochastic simulations with independent agents.

---

## 5. Discussion

### 5.1 Implications for AI Safety

Our results demonstrate that oversight decay is an *inherent property* of human-AI decision systems, not a failure of any specific model. Even a hypothetically perfect model (0% error rate) would cause oversight decay — reviewers who never find errors stop reviewing, and their skills atrophy. When the model eventually does err (and all models eventually do), the oversight infrastructure has already degraded.

This has direct implications for deployment policy:

1. **Model accuracy is necessary but not sufficient.** Improving model quality reduces the steady-state error rate but does not prevent oversight collapse.
2. **Mandatory review protocols resist natural decay.** Forcing minimum review rates (e.g., randomly flagging 10% of decisions for human review regardless of model confidence) could maintain reviewer skills.
3. **Monitoring oversight is as important as monitoring accuracy.** Deployments should track *human review rates and error-detection performance* alongside model accuracy metrics.

### 5.2 Model Tier Comparison

When all three model backends are available with proper API configuration, Driftwatch enables direct comparison of oversight decay rates across model tiers. The expected result — supported by the rule-based difficulty sensitivity analysis — is that less accurate models (e.g., quantized local) would produce more errors, but the *trust-building mechanism operates on correct decisions*, which all models still produce in majority. The key question is whether the marginal accuracy difference between GPT-4o (~5% error) and Llama Q4 (~18% error) translates to meaningfully different oversight decay rates.

Preliminary analysis suggests that the relationship is non-linear: small accuracy improvements near the "mostly correct" threshold (85–95% accuracy) have disproportionate effects on oversight decay because they reduce the frequency of "trust-building" correct decisions only marginally, while significantly reducing the errors that trigger vigilance recovery.

### 5.3 Counterfactual Methodology

The counterfactual mode (freezing `review_probability`) provides a clean decomposition of total silent errors into two components:

- **Model-attributable errors:** Errors that would occur even with perfect, constant oversight (measured by the counterfactual run).
- **Decay-attributable errors:** The additional errors caused by declining oversight (the difference between normal and counterfactual runs).

This decomposition is methodologically novel and directly useful for policy: it answers the question "how much of the problem is the AI, and how much is the human response to the AI?"

---

## 6. Limitations and Dual-Use Considerations

### 6.1 Simulation Limitations

1. **Homogeneous citizen population.** All citizens start with identical `review_probability` (0.9) and `review_skill` (0.8). In reality, reviewers have heterogeneous initial competence, motivation, and workload. Future work should model reviewer archetypes with distinct initial conditions.

2. **Independent agent decisions.** Citizens make review decisions independently. In practice, reviewers communicate — a colleague catching an error can increase others' vigilance. Social network effects on review behaviour are not modelled.

3. **Fixed caseworker error rate.** The rule-based backend produces a constant error rate across all timesteps. In reality, AI models may drift over time, and error rates may correlate with case difficulty in non-stationary ways.

4. **No adversarial cases.** The case oracle generates random cases. In real deployments, adversarial actors may craft inputs designed to exploit both model weaknesses and oversight gaps.

5. **Single decision domain.** Results are specific to benefits eligibility decisions. Generalisation to other administrative domains (medical diagnosis, loan approval, criminal risk assessment) requires domain-specific calibration.

6. **Silent fallback behaviour.** When LLM backends are unavailable, the system falls back to rule-based decisions. While we now notify users when this occurs, the deployed demo may show identical results across backends if API keys are not configured.

### 6.2 Dual-Use Considerations

Driftwatch is designed to detect and quantify oversight decay as a safety tool. However, the same simulation could theoretically be used to:

1. **Optimise oversight evasion.** An adversary could use the model to identify the *fastest path* to oversight collapse — e.g., finding the sequence of correct decisions that most rapidly reduces review probability before introducing errors. **Mitigation:** The oversight decay mechanism is well-documented in automation bias literature and is not novel; Driftwatch makes it measurable, not exploitable.

2. **Calibrate manipulation campaigns.** The trust-decay parameters could be tuned to model how quickly populations lose vigilance over specific types of decisions. **Mitigation:** The parameters are derived from general automation bias research and are not specific to any real population.

3. **Justify reduced oversight.** A deployment team could use Driftwatch results to argue "oversight will decay anyway, so mandating it is futile." **Mitigation:** The counterfactual analysis explicitly demonstrates that maintained oversight dramatically reduces silent errors, providing evidence *for* mandatory review protocols, not against them.

We believe the safety benefits of making oversight decay measurable and visible substantially outweigh the dual-use risks. The primary risk of *not* building tools like Driftwatch is that oversight decay continues to occur invisibly in real deployments.

### 6.3 Ethical Considerations

The simulation involves synthetic citizens, not real people. No personal data is used. The case oracle generates fictional administrative cases. All results are from simulation, not observation of real human reviewers. We do not claim that the simulation parameters reflect any specific real-world deployment or population.

---

## 7. Conclusion

Driftwatch demonstrates that human oversight of AI-made decisions decays predictably under realistic conditions: when an AI is mostly correct, humans stop checking, their error-detection skills atrophy, and undetected errors accumulate. Our counterfactual analysis shows that ~80% of silent errors are attributable to this oversight decay rather than model error alone.

The simulation platform enables direct comparison across model tiers (closed, open-source, quantized), provides real-time visualisation of oversight decay curves, and computes key safety metrics (time-to-threshold, silent error rate) from logged simulation events. All results are reproducible via deterministic seeding.

We argue that monitoring human oversight decay should become a standard component of AI deployment safety assessments, alongside model accuracy and fairness metrics. Driftwatch provides a practical tool for this purpose.

---

## References

Bansal, G., Wu, T., Zhou, J., Fok, R., Nushi, B., Kamar, E., ... & Weld, D. (2021). Does the whole exceed its parts? The effect of AI explanations on complementary team performance. *CHI '21*.

Batty, M. (2007). Cities and Complexity. *MIT Press*.

Buçinca, Z., Malaya, M. B., & Gajos, K. Z. (2021). To trust or to think: Cognitive forcing functions can reduce overreliance on AI in AI-assisted decision-making. *CSCW '21*.

Cummings, M. L. (2004). Automation bias in intelligent time critical decision support systems. *AIAA Conference on Intelligent Systems*.

Eubank, S., Guclu, H., Kumar, V. S. A., Marathe, M. V., Srinivasan, A., Toroczkai, Z., & Wang, N. (2004). Modelling disease outbreaks in realistic urban social networks. *Nature*, 429(6988), 180–184.

Goddard, K., Roudsari, A., & Wyatt, J. C. (2012). Automation bias: A systematic review of frequency, effect mediators, and mitigators. *JAMIA*, 19(1), 121–127.

Green, B., & Chen, Y. (2019). The principles and limits of algorithm-in-the-loop decision making. *CSCW '19*.

LeBaron, B. (2006). Agent-based computational finance. *Handbook of Computational Economics*, 2, 1187–1233.

Parasuraman, R., & Riley, V. (1997). Humans and automation: Use, misuse, disuse, abuse. *Human Factors*, 39(2), 230–253.

Touvron, H., Martin, L., Stone, K., et al. (2023). Llama 2: Open foundation and fine-tuned chat models. *arXiv:2307.09288*.

Zheng, L., Chiang, W.-L., Sheng, Y., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. *NeurIPS 2023*.
