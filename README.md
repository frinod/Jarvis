# JARVIS OS — Just A Rather Very Intelligent System

> An Iron Man-inspired autonomous AI trading assistant with real-time stock analysis,
> voice control, XGBoost price forecasting, and a full AI Cognition Runtime.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/frinod/Jarvis.git
cd Jarvis

# 2. Backend
cd backend
cp .env.example .env          # fill in at least one AI provider key
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev                   # http://localhost:3000
```

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [AI Cognition Runtime](#3-ai-cognition-runtime)
4. [Tech Stack](#4-tech-stack)
5. [Project Structure](#5-project-structure)
6. [Backend Modules](#6-backend-modules)
7. [Frontend UI](#7-frontend-ui)
8. [Auto-Trade Flow](#8-auto-trade-flow)
9. [API Reference](#9-api-reference)
10. [Setup and Installation](#10-setup-and-installation)
11. [Environment Variables](#11-environment-variables)
12. [Running Tests](#12-running-tests)
13. [Phase Roadmap](#13-phase-roadmap)

---

## 1. Project Overview

JARVIS OS is a full-stack AI-powered trading assistant built for the Indian stock market (NSE/BSE).
It combines a Hollywood-grade Iron Man HUD interface with a fully autonomous paper trading engine
and a complete AI Cognition Runtime — Brain, Memory, Reasoning, Agents, Perception, and Prediction.

### What It Does

- Listens to your voice and responds like JARVIS from Iron Man
- Scans the Nifty 50 universe in real time using Technical Analysis + XGBoost forecasting
- Executes paper trades autonomously with stop-loss, trailing SL, and profit targets
- Reasons through multi-step chains of thought before responding
- Maintains short-term and long-term memory across sessions
- Dispatches specialised agents (Analyst, Researcher, Trader, Planner)
- Diagnoses its own losses and patches its own config
- Streams live stock data, candlestick patterns, and AI analysis through a chat interface

### Key Numbers

| Metric                  | Value                                                    |
|-------------------------|----------------------------------------------------------|
| Universe                | Nifty 50 (50 stocks)                                     |
| Budget per trade        | ₹10,000                                                  |
| Max hold time           | 30 minutes                                               |
| TA indicators           | 20+ (RSI, MACD, BB, EMA, Supertrend, Ichimoku, etc.)    |
| XGBoost features        | 49 features per prediction                               |
| AI Runtime tests        | 1459 / 1459 passing                                      |
| Current version         | v0.6.0                                                   |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  YOU  (Browser / Electron)               │
│  Mic ──► Voice Input    Keys ──► Chat Interface          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / WebSocket
                         ▼
┌─────────────────────────────────────────────────────────┐
│              NEXT.JS FRONTEND  (port 3000)               │
│  jarvisStore.ts ──► sendMessage()                        │
│  WebSocket /api/ws/chat  │  HTTP POST /api/chat          │
└────────────────────────┬────────────────────────────────┘
                         │ REST / WS
                         ▼
┌─────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND  (port 8000)                │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              AI COGNITION RUNTIME                │   │
│  │  Brain ──► Coordinator ──► ExecutionEngine       │   │
│  │     │                                            │   │
│  │  Memory (STM + LTM + Embeddings)                 │   │
│  │  Reasoning (ChainOfThought + Reflection)         │   │
│  │  Agents (Analyst / Researcher / Trader / Planner)│   │
│  │  Perception (Market / News / Sentiment)          │   │
│  │  Prediction (Features / Forecasting / Confidence)│   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  LLMRouter (Gemini / Groq / DeepSeek / OpenAI / Ollama) │
│  MemoryManager  │  ToolRegistry  │  MarketData           │
│  XGBoost Forecaster  │  Auto-Trader Engine               │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                     DATA LAYER                           │
│  jarvis_paper_trading.json  ──  portfolios / P&L         │
│  backend/models/*.pkl       ──  trained XGBoost models   │
│  Yahoo Finance              ──  OHLCV candles            │
│  Angel One SmartAPI         ──  live tick feed (optional)│
└─────────────────────────────────────────────────────────┘
```

---

## 3. AI Cognition Runtime

The AI Cognition Runtime (`backend/app/ai/`) is the core intelligence layer introduced in Phase 6.

### Sub-systems

| Sub-system   | Package                    | Description                                      |
|--------------|----------------------------|--------------------------------------------------|
| Runtime      | `ai/runtime/`              | AIRuntime facade, ExecutionEngine, LLMGateway    |
| Brain        | `ai/brain/`                | Brain — top-level cognitive controller           |
| Orchestration| `ai/orchestration/`        | Coordinator, WorkflowEngine (DAG)                |
| Memory       | `ai/memory/`               | ShortTermMemory (ring), LongTermMemory, Embeddings|
| Reasoning    | `ai/reasoning/`            | ChainOfThought, Reflection, ReasoningPlanner     |
| Prompts      | `ai/prompts/`              | TemplateRegistry, SystemPromptBuilder            |
| Agents       | `ai/agents/`               | BaseAgent, Analyst, Researcher, Trader, Planner  |
| Skills       | `ai/skills/`               | BaseSkill, SkillRegistry                         |
| Tools        | `ai/tools/`                | BaseTool, AIToolRegistry (RBAC + timeout)        |
| Perception   | `ai/perception/`           | MarketPerception, NewsPerception, SentimentPerception |
| Prediction   | `ai/prediction/`           | FeatureStore, ForecastingEngine, ConfidenceScorer|

### Extension Points (Phase 7)

| Current stub              | Phase 7 replacement          |
|---------------------------|------------------------------|
| `InMemoryLongTermMemory`  | Qdrant vector store          |
| `SimpleEmbeddingService`  | SentenceTransformer           |
| `InMemoryMarketPerception`| Real market data provider    |
| `MockForecastingEngine`   | XGBoost / live model         |
| Sequential workflow loop  | `asyncio.gather()` parallel  |

---

## 4. Tech Stack

### Backend
- Python 3.7.9
- FastAPI 0.95 + Uvicorn
- SQLAlchemy 1.4 + Alembic
- XGBoost 1.6 + scikit-learn 1.0
- pandas 1.3 + numpy 1.21
- python-jose (JWT)
- pytest + pytest-asyncio

### Frontend
- Next.js 13 (App Router)
- React 18 + TypeScript
- Tailwind CSS
- Zustand (jarvisStore)
- WebSocket streaming

### Infrastructure
- Docker + Docker Compose
- Kubernetes (k8s manifests)
- GitHub Actions CI

---

## 5. Project Structure

```
jarvis-os/
├── backend/
│   ├── app/
│   │   ├── ai/                  ← AI Cognition Runtime (Phase 6)
│   │   │   ├── agents/          ← BaseAgent + 4 domain agents
│   │   │   ├── brain/           ← Brain controller
│   │   │   ├── memory/          ← STM + LTM + Embeddings
│   │   │   ├── orchestration/   ← Coordinator + Workflow DAG
│   │   │   ├── perception/      ← Market / News / Sentiment
│   │   │   ├── prediction/      ← Features / Forecasting / Confidence
│   │   │   ├── prompts/         ← Templates + SystemPromptBuilder
│   │   │   ├── reasoning/       ← ChainOfThought + Reflection + Planner
│   │   │   ├── runtime/         ← AIRuntime + ExecutionEngine + LLMGateway
│   │   │   ├── skills/          ← BaseSkill + SkillRegistry
│   │   │   └── tools/           ← BaseTool + AIToolRegistry
│   │   ├── api/                 ← FastAPI routes
│   │   ├── config/              ← Settings kernel (Phase 5)
│   │   ├── core/                ← Infrastructure kernel (Phase 5.5)
│   │   ├── market_data/         ← Yahoo / Angel One providers
│   │   ├── memory/              ← Legacy memory manager
│   │   ├── resilience/          ← Retry policies
│   │   └── main.py
│   ├── models/                  ← Trained XGBoost .pkl files
│   ├── tests/
│   │   ├── phase3/              ← 9 test files
│   │   ├── phase4/              ← 4 test files
│   │   ├── phase5/              ← 13 test files
│   │   ├── phase5_5/            ← 6 test files
│   │   └── phase6/              ← 16 test files (1459 tests)
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                 ← Next.js App Router
│   │   ├── components/          ← 37 React components
│   │   ├── store/               ← jarvisStore.ts (Zustand)
│   │   └── lib/                 ← voiceRouter.ts
│   ├── package.json
│   └── next.config.js
├── docs/
│   ├── ai-runtime-architecture.md
│   ├── plugin-sdk.md
│   └── scientific-intelligence.md
├── infrastructure/
│   ├── docker/
│   └── k8s/
├── plugins/
│   └── example_plugin/
├── .github/
│   └── workflows/ci.yml
├── .gitignore
├── pytest.ini
├── CHANGELOG.md
├── ROADMAP.md
├── ARCHITECTURE.md
└── PROJECT_STATUS.md
```

---

## 6. Backend Modules

### API Layer (`app/api/`)
| File                    | Purpose                                      |
|-------------------------|----------------------------------------------|
| `routes.py`             | Main chat + WebSocket endpoints              |
| `paper_trading.py`      | Paper trading session management             |
| `auto_trader.py`        | Autonomous trading engine                    |
| `forecaster.py`         | XGBoost prediction endpoint                  |
| `technical_analysis.py` | TA computation (RSI, MACD, BB, etc.)         |
| `stock_data.py`         | OHLCV data fetch                             |
| `backtesting.py`        | Strategy backtesting                         |
| `market_intelligence.py`| Market regime + intelligence                 |

### Config Kernel (`app/config/`) — Phase 5
Typed settings with environment validation: `AppSettings`, `AISettings`, `MarketSettings`, `RiskSettings`, `BrokerSettings`, `CacheSettings`, `LoggingSettings`.

### Infrastructure Kernel (`app/core/`) — Phase 5.5
DI container, event bus, lifecycle manager, service registry, plugin loader, task queue, scheduler, worker pool, health monitor, metrics engine.

---

## 7. Frontend UI

37 React components including:
- `ChatInterface.tsx` — main JARVIS chat with streaming
- `VoiceBar.tsx` — voice input with correction map
- `HolographicCore.tsx` — Iron Man HUD core animation
- `PaperTradingPage.tsx` — live paper trading dashboard
- `StocksPage.tsx` / `StocksPanel.tsx` — market data views
- `PortfolioPage.tsx` — P&L tracking
- `MarketDashboardPage.tsx` — full market overview

---

## 8. Auto-Trade Flow

```
POST /api/paper/autotest/start
  │
  ├─ SCAN    _scan_candidates()   ← 50 stocks, TA + XGBoost scoring
  ├─ ENTER   _enter_trades()      ← BUY top N, record SL/target/ATR
  ├─ MONITOR _monitor_and_exit()  ← poll 20s, trailing SL, exit on condition
  ├─ ANALYSE _analyse_and_patch() ← diagnose losses, patch thresholds
  └─ SUMMARY _build_summary()     ← win rate, P&L, Sharpe, drawdown
```

---

## 9. API Reference

| Method | Endpoint                      | Description                  |
|--------|-------------------------------|------------------------------|
| POST   | `/api/chat`                   | Single-turn chat             |
| WS     | `/api/ws/chat`                | Streaming chat               |
| POST   | `/api/paper/autotest/start`   | Start auto-trade session     |
| GET    | `/api/paper/status`           | Session status               |
| GET    | `/api/stocks/{symbol}`        | Stock data + TA              |
| GET    | `/api/forecast/{symbol}`      | XGBoost forecast             |
| GET    | `/api/health`                 | Health check                 |

---

## 10. Setup and Installation

### Prerequisites
- Python 3.7.9
- Node.js 18+
- Git

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add at least one AI provider key
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Docker (optional)
```bash
cd infrastructure/docker
docker-compose up --build
```

---

## 11. Environment Variables

See `backend/.env.example` for the full list. Minimum required:

```env
# Pick ONE AI provider
GEMINI_API_KEY=your-key-here
# OR
GROQ_API_KEY=your-key-here

# Database (SQLite works out of the box)
DATABASE_URL=sqlite:///jarvis.db

# Security
SECRET_KEY=change-me-to-a-random-secret
```

---

## 12. Running Tests

```bash
cd backend
python -m pytest tests/ -q
# Expected: 1459 passed
```

Run a specific phase:
```bash
python -m pytest tests/phase6/ -q
```

---

## 13. Phase Roadmap

| Phase   | Name                        | Status |
|---------|-----------------------------|--------|
| Phase 1 | Market Data Foundation      | ✅     |
| Phase 2 | Module Migration            | ✅     |
| Phase 3 | Validation                  | ✅     |
| Phase 4 | Cleanup                     | ✅     |
| Phase 5 | Configuration Kernel        | ✅     |
| Phase 5.5 | Infrastructure Kernel     | ✅     |
| Phase 6 | AI Cognition Runtime        | ✅     |
| Phase 7 | Real Integrations           | 🔜     |
| Phase 8 | Production Hardening        | 🔜     |

See [ROADMAP.md](ROADMAP.md) for detailed Phase 7+ plans.
