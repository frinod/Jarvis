"""Frino OS - FastAPI Application"""
from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.orchestrator import JarvisOrchestrator
from app.api.routes import router


orchestrator = None  # type: JarvisOrchestrator

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Serve frontend UI
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_ui():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frino OS API. Visit /docs for API documentation."}


@app.get("/stocks")
async def serve_stocks():
    stocks_path = os.path.join(STATIC_DIR, "stocks.html")
    if os.path.exists(stocks_path):
        return FileResponse(stocks_path)
    return {"error": "stocks.html not found"}


@app.get("/favicon.ico")
async def favicon():
    ico_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(ico_path):
        return FileResponse(ico_path, media_type="image/x-icon")
    return FileResponse(ico_path)


@app.on_event("startup")
async def startup():
    global orchestrator
    orchestrator = JarvisOrchestrator()

    # Initialise unified market data layer (Angel One primary, Yahoo fallback)
    try:
        from app.market_data.service import initialise as md_init
        await md_init()
        from app.market_data.service import get_provider_status
        status = await get_provider_status()
        for p in status["providers"]:
            state = "ready" if p.get("available") else "unavailable"
            print(f"[JARVIS] + Market data provider: {p['name']} ({state})")
    except Exception as e:
        print(f"[JARVIS] Market data init failed: {e}")

    # Start Angel One WebSocket tick feed (updates quote cache in real-time)
    try:
        from app.api.angel_feed import start_feed, _credentials_present
        if _credentials_present():
            start_feed()
            print("[JARVIS] + Angel One WebSocket tick feed started")
        else:
            print("[JARVIS] Angel One feed skipped — credentials not configured")
    except Exception as e:
        print(f"[JARVIS] Angel One feed failed to start: {e}")

    # Start price alert engine
    try:
        from app.api.alert_engine import start_alert_engine
        start_alert_engine()
        print("[JARVIS] + Price alert engine started")
    except Exception as e:
        print(f"[JARVIS] Alert engine failed to start: {e}")

    connected = False

    # Priority 1: Gemini (free)
    gemini_key = (settings.gemini_api_key or '').strip()
    if gemini_key.startswith('AIza'):
        from app.core.llm import GeminiProvider
        orchestrator.llm.register(
            "gemini",
            GeminiProvider(gemini_key, settings.gemini_model),
            default=True
        )
        print(f"[JARVIS] + Google Gemini connected (model: {settings.gemini_model})")
        connected = True
    elif gemini_key:
        print(f"[JARVIS] ! Gemini key looks invalid (should start with AIza). Skipping.")

    # Priority 2: Groq (free, fast)
    groq_key = (settings.groq_api_key or '').strip()
    if groq_key.startswith('gsk_'):
        from app.core.llm import OpenAICompatibleProvider
        orchestrator.llm.register(
            "groq",
            OpenAICompatibleProvider(groq_key, settings.groq_model, "https://api.groq.com/openai/v1"),
            default=not connected
        )
        print(f"[JARVIS] + Groq connected (model: {settings.groq_model})")
        connected = True
    elif groq_key:
        print(f"[JARVIS] ! Groq key looks invalid (should start with gsk_). Skipping.")

    # Priority 3: DeepSeek
    deepseek_key = (settings.deepseek_api_key or '').strip()
    if deepseek_key:
        from app.core.llm import OpenAICompatibleProvider
        orchestrator.llm.register(
            "deepseek",
            OpenAICompatibleProvider(deepseek_key, settings.deepseek_model, "https://api.deepseek.com/v1"),
            default=not connected
        )
        print(f"[FRINO] + DeepSeek connected (model: {settings.deepseek_model})")
        connected = True

    # Priority 4: OpenAI
    openai_key = (settings.openai_api_key or '').strip()
    if openai_key:
        from app.core.llm import OpenAICompatibleProvider
        orchestrator.llm.register(
            "openai",
            OpenAICompatibleProvider(openai_key, settings.openai_model, "https://api.openai.com/v1"),
            default=not connected
        )
        print(f"[FRINO] + OpenAI connected (model: {settings.openai_model})")
        connected = True

    # Priority 5: OpenRouter
    openrouter_key = (settings.openrouter_api_key or '').strip()
    if openrouter_key:
        from app.core.llm import OpenAICompatibleProvider
        orchestrator.llm.register(
            "openrouter",
            OpenAICompatibleProvider(openrouter_key, "meta-llama/llama-3.1-8b-instruct:free", "https://openrouter.ai/api/v1"),
            default=not connected
        )
        print("[FRINO] + OpenRouter connected")
        connected = True

    # Priority 6: Ollama (local)
    if settings.local_model_path and not connected:
        from app.core.llm import OllamaProvider
        import httpx
        try:
            r = httpx.get(settings.local_model_path, timeout=3.0)
            if r.status_code == 200:
                orchestrator.llm.register(
                    "ollama",
                    OllamaProvider(settings.local_model_path, settings.ollama_model),
                    default=True
                )
                print(f"[FRINO] + Ollama connected (model: {settings.ollama_model})")
                connected = True
        except Exception:
            pass

    if not connected:
        print("[FRINO] ===================================================")
        print("[FRINO] WARNING: No LLM provider configured! Running in fallback mode.")
        print("[FRINO]   To enable full AI (like ChatGPT), add an API key to .env:")
        print("[FRINO]   - GEMINI_API_KEY  (free: https://aistudio.google.com/app/apikey)")
        print("[FRINO]   - GROQ_API_KEY    (free: https://console.groq.com/keys)")
        print("[FRINO]   - DEEPSEEK_API_KEY (cheap: https://platform.deepseek.com)")
        print("[FRINO] ===================================================")


@app.on_event("shutdown")
async def shutdown():
    global orchestrator
    orchestrator = None

    # Stop Angel One feed
    try:
        from app.api.angel_feed import get_feed
        get_feed().stop()
    except Exception:
        pass

    # Stop alert engine
    try:
        from app.api.alert_engine import stop_alert_engine
        stop_alert_engine()
    except Exception:
        pass


def get_orchestrator():
    # type: () -> JarvisOrchestrator
    return orchestrator
