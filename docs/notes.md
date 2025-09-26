# Project Notes

### ✅ Day 1 — Repo + Skeleton Setup
- Repo initialized with backend, db, docs, ml, tests.
- Synthetic dataset placeholder created.
- FastAPI hello world running (`/` endpoint).
- Initial SQLite schema defined.

### ✅ Day 2 — Wallet API
- Implemented `/create_wallet` and `/list_wallets`.
- Enforced `UNIQUE(user, currency)` to prevent duplicate wallets.
- Normalized usernames (`user.strip().lower()`).
- Verified via curl + database resets.

### ✅ Day 3 — Transfers
- Implemented `/transfer` with balance validation.
- Supports multi-currency transfers.
- Transaction logs written into `transactions` table.
- Caught common errors (insufficient funds, wallet not found).

### ✅ Day 4 — Minting + CI/CD
- Added `/mint` endpoint for testing (admin-key protected).
- Hardened security by moving admin key → request headers.
- Configured **GitHub Actions CI** to run pytest automatically.
- Pytest suite started passing locally.

### ✅ Day 5 — Compliance Logs
- Introduced CSV-based compliance logging (`db/compliance_logs`).
- Each transaction now mirrored for audit trail.
- Updated repo hygiene (`.gitignore`) to prevent sensitive log commits.

### ✅ Day 6 — Documentation
- Added `docs/architecture.md` with **Mermaid diagrams**:
  - Sequence flow (user → PSP → DB → compliance).
  - ER diagram (wallets ↔ transactions).
  - Risk-scoring flow (normal vs suspicious).
- README.md updated with badges, roadmap, and features.

### ✅ Day 7 — ML Pipeline + Tests
- Created `ml/generate_synthetic.py` for synthetic transaction data.
- Trained IsolationForest anomaly detection (`ml/train_model.py`).
- Added inference demo (`ml/test_inference.py`).
- Wrapped ML pipeline into `tests/test_ml.py`.
- CI/CD now validates ML + PSP APIs (7/7 tests passing).