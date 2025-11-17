import pandas as pd
from .database import get_conn


def load_transactions(limit: int = 200) -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            """
            SELECT id, from_wallet, to_wallet, amount, currency,
                   COALESCE(blockchain_hash, '') AS blockchain_hash,
                   COALESCE(type, '') AS type, timestamp
            FROM transactions
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            conn,
            params=(limit,),
        )
    finally:
        conn.close()
    return df
