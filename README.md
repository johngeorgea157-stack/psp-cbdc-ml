#  CBDC Payments Risk Monitoring Prototype 🚀

[![Tests](https://github.com/johngeorgea157-stack/psp-cbdc-ml/actions/workflows/python-tests.yml/badge.svg)](https://github.com/johngeorgea157-stack/psp-cbdc-ml/actions)
[![Coverage](https://codecov.io/gh/johngeorgea157-stack/psp-cbdc-ml/branch/main/graph/badge.svg)](https://codecov.io/gh/johngeorgea157-stack/psp-cbdc-ml)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-brightgreen.svg)

---

## Overview
A lightweight prototype of a **Payment Service Provider (PSP) layer** for simulated CBDC-style transfers.  
The project shows how a simple **SQL ledger** can be paired with a clean **FastAPI interface**, a **risk engine**, and an optional **Polkadot-based audit trail**—useful for demos, research, and hackathons.

---

## Features
- 🔐 Admin-key controlled minting  
- 💼 Multi-currency wallet support (INR-CBDC, USD-Token)  
- 🔄 Secure transfers with duplicate-transaction checks  
- ⚡ FastAPI backend + SQLite ledger  
- 🧠 Early anomaly scoring and feature logs  
- 🔗 Polkadot Westend audit logging (with fallback hashing)  
- 🧪 Pytest-based CI on GitHub Actions  

---

## Architecture
- **Ledger:** SQLite (authoritative internal balances)  
- **API Layer:** FastAPI  
- **Risk Engine:** Rule-based scoring + feature store (ML-ready)  
- **Audit Layer:** Optional Polkadot DLT hooks  

This mirrors real CBDC system designs where the **core ledger remains centralized**, and the blockchain acts as a **tamper-evident audit layer**, not a balance store.

---

## Roadmap
- ✔️ Phase 1 — Project skeleton, DB, CI  
- ✔️ Phase 2 — Wallets, transfers, minting  
- ✔️ Phase 3 — Basic anomaly scoring  
- ✔️ Phase 4 — Polkadot audit logging  
- ⏳ Phase 5 — Research & documentation  
- ⏳ Phase 6 — UI demo + packaging  

---

## Getting Started

### Prerequisites
- Python **3.11+**
- Any virtual environment (venv or conda)

### Setup
```bash
git clone https://github.com/johngeorgea157-stack/psp-cbdc-ml.git
cd psp-cbdc-ml
pip install -r requirements.txt
