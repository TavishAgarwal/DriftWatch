import asyncio
import random
import numpy as np
import pickle
import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
from backend.api.routes.driftwatch import _run_driftwatch_sync, DriftwatchRequest

async def generate_dataset(num_runs: int = 50):
    print(f"Generating {num_runs} simulation runs for dataset...")
    X = []
    y = []
    
    rng = random.Random(1337)
    
    for i in range(num_runs):
        difficulty = rng.uniform(0.3, 0.7)
        initial_prob = rng.uniform(0.5, 0.99)
        k = rng.choice([0, 1, 5, 10, 50])
        topology = rng.choice(["isolated", "random", "small_world"])
        social_weight = rng.uniform(0.0, 1.0)
        
        backend, quantization = rng.choice([
            ("openai", "none"),
            ("ollama_api", "fp16"),
            ("ollama_local", "fp16"),
            ("ollama_local", "int8"),
            ("ollama_local", "int4"),
        ])

        req = DriftwatchRequest(
            model_backend=backend,
            quantization=quantization,
            population_size=100,
            timesteps=25,
            difficulty=difficulty,
            initial_review_probability=initial_prob,
            initial_review_skill=0.8,
            seed=1337 + i,
            network_topology=topology,
            network_k=k,
            social_influence_weight=social_weight,
            adversary_ratio=0.0,
            silent_error_threshold=0.15
        )
        
        res = await _run_driftwatch_sync(req)
        
        # Extract features at t=10
        if len(res.timestep_metrics) < 10:
            continue
            
        m1 = res.timestep_metrics[0]
        m10 = res.timestep_metrics[9]
        
        prob_t10 = m10.avg_review_probability
        prob_slope = (m10.avg_review_probability - m1.avg_review_probability) / 10.0
        avg_latency = sum(m.latency_skips for m in res.timestep_metrics[:10]) / 10.0
        avg_conf = sum(m.avg_decision_confidence for m in res.timestep_metrics[:10]) / 10.0
        
        # Predict a FUTURE collapse using only t<=10 features.  Events at or
        # before the feature cutoff are intentionally excluded from the label.
        collapsed = int(any(
            m.timestep > 10 and m.silent_error_rate >= req.silent_error_threshold
            for m in res.timestep_metrics
        ))
        
        X.append([prob_t10, prob_slope, avg_latency, avg_conf])
        y.append(collapsed)
        
        if (i+1) % 10 == 0:
            print(f"  Generated {i+1} runs...")
            
    return np.array(X), np.array(y)

async def main():
    X, y = await generate_dataset(60)
    
    if len(np.unique(y)) < 2:
        raise RuntimeError("Generated dataset has only one outcome class; adjust simulation sampling")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train, y_train)
    
    y_pred = clf.predict(X_test)
    
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    
    print("\n=== Early Warning Predictor Evaluation ===")
    print(f"Accuracy:  {acc:.2f}")
    print(f"Precision: {prec:.2f}")
    print(f"Recall:    {rec:.2f}")
    
    feature_names = ["Review Prob (t=10)", "Review Prob Slope", "Avg Latency Skips", "Avg Confidence"]
    print("\nFeature Coefficients (Interpretability):")
    for name, coef in zip(feature_names, clf.coef_[0]):
        print(f"  {name}: {coef:.4f}")
        
    model_path = os.path.join(os.path.dirname(__file__), "..", "models", "collapse_predictor.pkl")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(clf, f)
    print(f"\nModel saved to {model_path}")

    evaluation = {
        "training_runs": int(len(y_train)),
        "held_out_runs": int(len(y_test)),
        "feature_cutoff_timestep": 10,
        "target": "silent-error threshold reached after timestep 10",
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
    }
    evaluation_path = os.path.join(os.path.dirname(model_path), "collapse_predictor_metrics.json")
    with open(evaluation_path, "w", encoding="utf-8") as f:
        json.dump(evaluation, f, indent=2)
    print(f"Evaluation saved to {evaluation_path}")

if __name__ == "__main__":
    asyncio.run(main())
