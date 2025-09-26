import pandas as pd
import numpy as np

def generate_transactions(n=1000, seed=42):
    np.random.seed(seed)
    users = ["alice", "bob", "charlie", "john", "eve"]

    data = []
    for _ in range(n):
        user = np.random.choice(users)
        amount = np.random.exponential(scale=200)  # most transactions small
        currency = np.random.choice(["INR-CBDC", "USD-Token"])

        # Inject anomalies
        if np.random.rand() < 0.05:  # 5% anomalous
            amount = amount * np.random.randint(20, 100)  # huge spike

        data.append([user, amount, currency])

    df = pd.DataFrame(data, columns=["user", "amount", "currency"])
    df.to_csv("ml/synthetic_transactions.csv", index=False)
    return df

if __name__ == "__main__":
    df = generate_transactions()
    print(df.head())