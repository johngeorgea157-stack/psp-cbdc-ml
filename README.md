# PSP + CBDC + AI/ML Prototype 🚀

[![Tests](https://github.com/johngeorgea157-stack/psp-cbdc-ml/actions/workflows/python-tests.yml/badge.svg)](https://github.com/johngeorgea157-stack/psp-cbdc-ml/actions)
[![Coverage](https://codecov.io/gh/johngeorgea157-stack/psp-cbdc-ml/branch/main/graph/badge.svg)](https://codecov.io/gh/johngeorgea157-stack/psp-cbdc-ml)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-brightgreen.svg)

## Overview
This project is a prototype **Payment Service Provider (PSP)** layer designed for **CBDC (Central Bank Digital Currency)** and tokenized settlement in IFSC GIFT City. (devolopment phase)

It integrates:
- ✅ PSP Wallet APIs (`/create_wallet`, `/transfer`, `/list_wallets`, `/mint`)
- ✅ Mock CBDC + Token support (INR-CBDC, USD-Token)
- ✅ AI/ML Anomaly Detection (planned Phase 3)
- ✅ Blockchain/DLT hooks for auditability (future extension)

## Features
- 🔐 Secure **admin-key controlled minting**
- 💱 Multi-currency support per user
- 📝 Compliance logs (configurable, local only)
- ⚡ FastAPI backend, SQLite DB
- ✅ Fully tested with Pytest & GitHub Actions

## Roadmap
- Phase 1 → Project setup (✅ done)
- Phase 2 → PSP + CBDC wallet APIs (✅ done)
- Phase 3 → AI/ML integration (✅ basic anomaly detection done)
- Phase 4 → Blockchain audit trail (next up, Day 8+)
- Phase 5 → Research & Policy documentation
- Phase 6 → Packaging + Presentation

## Getting Started

### Prerequisites
- Python 3.11+
- Virtual environment (`venv` or `conda`)

### Setup
```bash
git clone https://github.com/johngeorgea157-stack/psp-cbdc-ml.git
cd psp-cbdc-ml
pip install -r requirements.txt
