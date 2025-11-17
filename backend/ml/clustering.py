import pandas as pd
from sklearn.cluster import KMeans


def cluster_entities(df: pd.DataFrame, n_clusters: int = 3) -> dict:
    """Return clustering assignment for wallets based on simple features.
    This is intentionally lightweight — replace with richer features for research.
    """
    if df.empty:
        return {"clusters": {}}

    feat = df.groupby("from_wallet")["amount"].agg(["count", "sum", "mean"]).fillna(0)
    feat = feat.reset_index()
    X = feat[["count", "sum", "mean"]].values

    if len(feat) < n_clusters:
        n = max(1, len(feat))
    else:
        n = n_clusters

    try:
        k = KMeans(n_clusters=n, random_state=42).fit(X)
        feat["cluster"] = k.labels_
    except Exception:
        feat["cluster"] = 0

    return {r["from_wallet"]: int(r["cluster"]) for _, r in feat.iterrows()}
