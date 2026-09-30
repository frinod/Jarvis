# JARVIS OS — Architecture

## Request flow
```
Voice/Text Input
  → VoiceBar.tsx (STT + correction)
  → intentRouter.ts (classify + context resolve)
  → capabilityTools.ts (market data fetch)
  → jarvisStore.sendMessage() (WebSocket to backend)
  → orchestrator.process_stream() (LLM + live context)
  → CenterWorkspace CommandConsole (render response)
  → speakText() (TTS)
```

## Frontend state machine (JarvisPhase)
`offline` → `boot` → `dormant` → `waking` → `listening` → `thinking` → `tooling` → `speaking`

## Intent types (intentRouter.ts)
`STOCK_ANALYSIS`, `FORECAST`, `MTF`, `INTRADAY`, `CONFLUENCE`, `REGIME`, `MOVERS`,
`NEWS`, `PORTFOLIO`, `PAPER_TRADE`, `PRICE_ALERT`, `TOP_PICKS`, `MARKET_SESSION`,
`MARKET_OVERVIEW`, `DATE_TIME`, `COMPARE`, `FOLLOW_UP`, `GENERAL_AI`

## Backend LLM priority chain
1. Gemini 2.5 Flash (`GEMINI_API_KEY` in .env, starts with `AIza`)
2. Groq llama-3.3-70b (`GROQ_API_KEY`, starts with `gsk_`)
3. DeepSeek (`DEEPSEEK_API_KEY`)
4. OpenAI (`OPENAI_API_KEY`)
5. Ollama (local, `LOCAL_MODEL_PATH`)

## Market data priority chain
1. Angel One SmartAPI (real-time WebSocket ticks)
2. Yahoo Finance (15s polling fallback)

## Kiro MCP integration
- Kiro runs as WebSocket server on port 8082
- Backend tool: `backend/app/tools/kiro_tool.py`
- Registered in `backend/app/tools/registry.py` as `kiro_assist`
- JARVIS can delegate coding/analysis tasks to Kiro via this tool
- Frontend can call Kiro via `/api/kiro/ask` REST endpoint

## Paper trading safety
- All AI trade proposals require explicit user confirmation
- Confirmation modal in CenterWorkspace (never auto-executes)
- `PaperTradeTool` returns proposal, `confirm_ai_trade()` executes

## XGBoost models
- Stored in `backend/models/*.pkl` + `*.meta`
- Horizon: h3 (3-period) or h6 (6-period) direction forecast
- 50+ Nifty stocks covered
- `backend/app/api/forecaster.py` loads and runs inference
