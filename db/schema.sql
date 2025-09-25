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