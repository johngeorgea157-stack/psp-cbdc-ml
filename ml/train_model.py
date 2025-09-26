import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib

def train_model():
    df = pd.read_csv("ml/synthetic_transactions.csv")

    # Encode categorical currency as numeric
    df["currency_code"] = df["currency"].astype("category").cat.codes

    X = df[["amount", "currency_code"]]

    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X)

    joblib.dump(model, "ml/anomaly_model.pkl")
    print("✅ Model trained and saved as ml/anomaly_model.pkl")

if __name__ == "__main__":
    train_model()