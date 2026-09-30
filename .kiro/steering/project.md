# JARVIS OS — Project Steering

## What this project is
JARVIS OS is a full-stack AI-powered Indian stock market intelligence system with an Iron Man JARVIS-style UI. It is a personal project by Frino D (Ericsson).

## Stack
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Framer Motion, Zustand
- **Backend**: Python 3.11, FastAPI, WebSocket streaming, SQLite
- **AI**: Gemini 2.5 Flash (primary), Groq llama-3.3-70b (fallback), XGBoost ML models
- **Market data**: Angel One SmartAPI (primary), Yahoo Finance (fallback)
- **Voice**: Browser SpeechRecognition (STT) + speechSynthesis (TTS) + Web Audio SFX

## Ports
- Frontend: 3000
- Backend: 8000
- Kiro serve: 8082

## Non-negotiable rules
1. DO NOT commit or push — user manages git manually
2. DO NOT add paid dependencies without asking
3. DO NOT remove working code without explicit instruction
4. Tool context is internal — never shown in user-facing UI
5. JarvisOverlay popup only for trade confirmations, not normal AI responses
6. All financial output uses "Model indicates..." language — never "X will rise"
7. Free-first LLM priority: Gemini → Groq → DeepSeek → OpenAI → Ollama

## How to run
```bash
# Frontend
cd frontend && npm run dev

# Backend
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Kiro serve (MCP bridge)
C:\Users\edxxfri\AppData\Local\Kiro-Cli\kiro-cli.exe serve --port 8082
```

## Key files to know
| File | Purpose |
|------|---------|
| `frontend/src/store/jarvisStore.ts` | All frontend state + sendMessage() |
| `frontend/src/components/VoiceBar.tsx` | Voice pipeline + intent routing |
| `frontend/src/lib/intentRouter.ts` | Intent classifier + context manager |
| `frontend/src/lib/capabilityTools.ts` | 15 market tool wrappers |
| `backend/app/core/orchestrator.py` | Main AI brain |
| `backend/app/core/llm.py` | LLM provider abstractions |
| `backend/app/api/routes.py` | All API routes + WebSocket |
| `backend/app/api/jarvis_intent.py` | Backend intent classifier |
| `backend/.env` | API keys (never commit) |

## Current known state
- TypeScript: 0 errors
- Audio: Web Audio synthesis active, MP3 overrides optional in `frontend/public/audio/`
- Intent pipeline: context-aware with follow-up resolution
- Gemini 2.5 Flash: needs `GEMINI_API_KEY` in `backend/.env`
