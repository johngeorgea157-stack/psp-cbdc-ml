# tests/test_ml.py
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

def test_ml_pipeline(tmp_path):
    # Step 1: Dummy data
    data = pd.DataFrame({
        "user": ["alice", "bob", "charlie"],
        "amount": [100, 2000, 50],
        "currency": ["INR-CBDC", "INR-CBDC", "USD-Token"]
    })

    data["currency_code"] = data["currency"].astype("category").cat.codes
    X = data[["amount", "currency_code"]]

    # Step 2: Train Isolation Forest
    model = IsolationForest(contamination=0.2, random_state=42)
    model.fit(X)

    # Step 3: Save + reload (ensures joblib works properly)
    model_path = tmp_path / "test_model.pkl"
    joblib.dump(model, model_path)
    loaded_model = joblib.load(model_path)

    # Step 4: Inference
    preds = loaded_model.predict(X)

    # Assertions
    assert len(preds) == len(data)
    assert all(p in [-1, 1] for p in preds)