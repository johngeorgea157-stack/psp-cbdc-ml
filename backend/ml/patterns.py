import pandas as pd


def detect_patterns(df: pd.DataFrame) -> list:
    """Return list of detected pattern flags from transactions df."""
    flags = []

    if df.empty:
        return flags

    # repeated amounts (same amount >= 3 times)
    if df["amount"].value_counts().max() >= 3:
        flags.append("repeat_amount_pattern")

    # ping-pong (A->B then B->A)
    if ("from_wallet" in df.columns) and ("to_wallet" in df.columns):
        f = df.reset_index(drop=True)
        if (f["from_wallet"] == f["to_wallet"].shift(1)).any() and (
            f["to_wallet"] == f["from_wallet"].shift(1)
        ).any():
            flags.append("ping_pong_pattern")

    # burst detection: many tx with small deltas
    f = df.copy()
    f["t"] = pd.to_datetime(f["timestamp"])
    f = f.sort_values("t")
    if len(f) > 3:
        f["delta"] = f["t"].diff().dt.total_seconds()
        if (f["delta"] < 2).sum() > 3:
            flags.append("burst_activity")

    return flags
