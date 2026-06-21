import os
import pickle
import numpy as np
from sklearn.linear_model import LogisticRegression

def train():
    # Simple synthetic data to train a proof-of-concept LogisticRegression
    # Features: [prob_curr, prob_slope, avg_latency, avg_conf]
    
    # Positive class (will reach threshold) - typically low prob, neg slope, high latency, high conf
    X_pos = [
        [0.6, -0.05, 0.4, 0.9],
        [0.5, -0.08, 0.5, 0.95],
        [0.4, -0.10, 0.6, 0.85],
        [0.7, -0.04, 0.3, 0.88],
        [0.3, -0.15, 0.7, 0.99]
    ]
    y_pos = [1, 1, 1, 1, 1]
    
    # Negative class (will NOT reach threshold) - typically high prob, pos/zero slope, low latency, low conf
    X_neg = [
        [0.9, 0.01, 0.05, 0.6],
        [0.85, 0.00, 0.1, 0.55],
        [0.95, 0.02, 0.0, 0.7],
        [0.8, -0.01, 0.15, 0.5],
        [0.88, 0.00, 0.05, 0.65]
    ]
    y_neg = [0, 0, 0, 0, 0]
    
    X = np.array(X_pos + X_neg)
    y = np.array(y_pos + y_neg)
    
    clf = LogisticRegression(random_state=42)
    clf.fit(X, y)
    
    model_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, "collapse_predictor.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(clf, f)
        
    print(f"Predictor model trained and saved to {model_path}")

if __name__ == "__main__":
    train()
