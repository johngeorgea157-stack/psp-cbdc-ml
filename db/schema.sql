CREATE TABLE IF NOT EXISTS wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    currency TEXT NOT NULL,
    balance REAL DEFAULT 0,
    UNIQUE(user, currency)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_wallet TEXT,
    to_wallet TEXT,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    type TEXT
);
CREATE TABLE IF NOT EXISTS pending_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    to_user TEXT,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    type TEXT NOT NULL,   -- "mint" or "transfer"
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    confirmed INTEGER DEFAULT 0  -- 0 = pending, 1 = confirmed
);