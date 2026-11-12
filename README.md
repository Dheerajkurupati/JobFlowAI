# 🚀 JobFlow-AI: Autonomous Job Search & Application Co-Pilot

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://www.python.org/)
[![Architecture: Agentic RAG](https://img.shields.io/badge/Architecture-Agentic%20RAG-orange.svg)]()
[![Free Tier Friendly](https://img.shields.io/badge/LLM-Gemini%20Flash%20%7C%20Ollama-purple.svg)]()

> **JobFlow-AI** is a 100% open-source, production-grade autonomous agent that streamlines job hunting across major portals (LinkedIn, Indeed, Naukri, and direct ATS feeds). It features a **RAG Career Vault**, **intelligent screening memory**, and a **Human-in-the-Loop review cockpit** to eliminate spamming, account bans, and hallucinated application answers.

---

## 🌟 Why JobFlow-AI?

| Feature | Generic Auto-Apply Bots | JobFlow-AI |
| :--- | :--- | :--- |
| **Strategy** | Blasts 500 identical resumes blindly | Tailored RAG matching & keyword gap analysis |
| **Account Safety** | High ban/throttle rate on LinkedIn | Strictly bounded daily quotas & natural pacing |
| **Screening Q&A** | Hallucinates or breaks on new questions | Self-learning memory + JD-aware salary negotiation |
| **Review Gate** | Uncontrolled auto-submit | **Cockpit Mode**: Pre-fills and pauses for your approval |
| **Tracking** | Clunky manual notes or none | Auto-generated daily Excel tracker (`Job_Tracker.xlsx`) |
| **Cost** | $50–$150/month SaaS subscription | **100% Free & Open Source** (Gemini Flash or Ollama) |

---

## 🏛️ System Architecture

```text
                           ┌────────────────────────────────────────┐
                           │       1. MULTI-SOURCE HARVESTER        │
                           │  (LinkedIn, Indeed, Naukri, Direct ATS)│
                           └──────────────────┬─────────────────────┘
                                              │ Raw Postings
                                              ▼
┌───────────────────────┐  Semantic  ┌─────────────────────────────────┐
│  USER CAREER VAULT    ├───────────►│       2. RAG & MATCH ENGINE     │
│ (Projects, Skills,    │  Retrieval │ • Cosine Similarity Scoring     │
│  Metrics, Experience) │            │ • ATS Keyword Gap Analysis      │
└───────────────────────┘            └────────────────┬────────────────┘
                                                      │ Filtered (>75% Match)
                                                      ▼
                                     ┌─────────────────────────────────┐
                                     │  3. DECISION & Q&A MEMORY       │
                                     │ • JD-Bounded CTC Negotiation    │
                                     │ • Learned Screening Answers     │
                                     └────────────────┬────────────────┘
                                                      │
                                                      ▼
┌──────────────────────────────────────────────────────────────────────┐
│             4. HUMAN-IN-THE-LOOP (HITL) BROWSER AGENT                │
│                                                                      │
│  [Playwright] ───────────────► Auto-fills Application Form           │
│                                ├─ Uploads resume PDF                 │
│                                ├─ Fills screening questions          │
│                                └─ PAUSES BEFORE SUBMIT               │
│                                                                      │
│  [Terminal / Web Cockpit] ───► Review & Click [Approve & Submit]    │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
                                       ▼
                          ┌────────────────────────┐
                          │ 5. EXCEL AUDIT TRACKER │
                          │ (Applications & HR DMs)│
                          └────────────────────────┘
```

---

## 📁 Repository Structure

```text
JobFlowAI/
├── .env.example                # Template for LLM API keys & configurations
├── requirements.txt            # Python dependencies
├── run_daily.py                # Main CLI execution entry point
│
├── config/
│   ├── settings.example.yaml   # User preferences template (locations, rules, limits)
│   └── default_rules.json      # Blacklist keywords (sales, night shifts, non-IT)
│
├── data/
│   ├── .gitkeep                # Keeps directory in git while ignoring personal files
│   ├── sample_resume.txt       # Anonymized sample fixture for testing
│   └── (Job_Tracker.xlsx)      # Auto-generated (strictly git-ignored for privacy)
│
├── src/
│   ├── config.py               # Pydantic configuration loader & validation
│   ├── parser/                 # Resume ingestion & structured data extraction
│   ├── harvester/              # Multi-board scrapers & strict filter rules
│   ├── brain/                  # RAG vector store, match scoring, & career coach
│   ├── tracker/                # Excel generator with date grouping & audit notes
│   └── agent/                  # Playwright browser pilot with approval gate
│
└── tests/                      # Automated test suite
```

---

## ⚡ Quickstart Guide

### 1. Clone & Setup Environment
```bash
git clone https://github.com/Dheerajkurupati/JobFlowAI.git
cd JobFlowAI

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Settings & Resume
```bash
# Setup environment variables
cp .env.example .env

# Setup user preferences
cp config/settings.example.yaml config/settings.yaml

# Copy your resume into the data folder
cp /path/to/your/resume.pdf data/resume.pdf
```

### 3. Run Your Daily Batch
```bash
python run_daily.py
```

---

## 🛡️ Privacy & Open Source Ethics
- **Zero Data Leakage:** Your resume, generated trackers, and screening answers remain strictly on your local disk.
- **Fair Play:** Adheres to platform rate limits and prevents aggressive spamming.

---

## 📄 License
Distributed under the **MIT License**. See `LICENSE` for more information.

