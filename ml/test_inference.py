import pandas as pd
import joblib

# Load trained model
model = joblib.load("ml/anomaly_model.pkl")

# Example new transactions
new_data = pd.DataFrame([
    {"amount": 150, "currency_code": 0},  # likely normal
    {"amount": 50000, "currency_code": 1} # likely suspicious
])

preds = model.predict(new_data)  # -1 = anomaly, 1 = normal
print("Predictions:", preds)