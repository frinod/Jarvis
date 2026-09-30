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

    # Build LLMGateway (AIRuntime's LLM layer) alongside LLMRouter
    from app.ai.runtime.llm_gateway import LLMGateway
    gateway = LLMGateway()

    connected = False

    from app.core.config import _is_valid_key

    # Priority 1: OpenRouter (free tier, OpenAI-compatible)
    openrouter_key = (settings.openrouter_api_key or '').strip()
    if _is_valid_key(openrouter_key, 'sk-or-'):
        from app.core.llm import OpenAICompatibleProvider
        or_model = getattr(settings, 'openrouter_model', 'qwen/qwen3.8-27b:free')
        or_base  = getattr(settings, 'openrouter_base_url', 'https://openrouter.ai/api/v1')
        provider = OpenAICompatibleProvider(openrouter_key, or_model, or_base)
        orchestrator.llm.register("openrouter", provider, default=True)
        gateway.register("openrouter", provider, priority=10, default=True)
        print(f"[JARVIS] + OpenRouter connected (model: {or_model})")
        connected = True
    elif openrouter_key:
        print(f"[JARVIS] ! OpenRouter key invalid (must start with sk-or-). Status: INVALID_CONFIGURATION")

    # Priority 2: Groq (free, fast)
    groq_key = (settings.groq_api_key or '').strip()
    if _is_valid_key(groq_key, 'gsk_'):
        from app.core.llm import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(groq_key, settings.groq_model, "https://api.groq.com/openai/v1")
        orchestrator.llm.register("groq", provider, default=not connected)
        gateway.register("groq", provider, priority=20, default=not connected)
        print(f"[JARVIS] + Groq connected (model: {settings.groq_model})")
        connected = True
    elif groq_key:
        print(f"[JARVIS] ! Groq key invalid (must start with gsk_). Status: INVALID_CONFIGURATION")

    # Priority 3: Gemini
    # NOTE: placeholder 'AIzaSy_PASTE_YOUR_KEY_HERE' starts with 'AIza' but is NOT valid.
    # _is_valid_key() rejects it because it contains 'PASTE'.
    gemini_key = (settings.gemini_api_key or '').strip()
    if _is_valid_key(gemini_key, 'AIza'):
        from app.core.llm import GeminiProvider
        provider = GeminiProvider(gemini_key, settings.gemini_model)
        orchestrator.llm.register("gemini", provider, default=not connected)
        gateway.register("gemini", provider, priority=30, default=not connected)
        print(f"[JARVIS] + Google Gemini connected (model: {settings.gemini_model})")
        connected = True
    elif gemini_key:
        print(f"[JARVIS] ! Gemini key NOT_CONFIGURED (placeholder or invalid). Skipping.")

    # Priority 4: DeepSeek
    deepseek_key = (settings.deepseek_api_key or '').strip()
    if _is_valid_key(deepseek_key):
        from app.core.llm import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(deepseek_key, settings.deepseek_model, "https://api.deepseek.com/v1")
        orchestrator.llm.register("deepseek", provider, default=not connected)
        gateway.register("deepseek", provider, priority=40, default=not connected)
        print(f"[JARVIS] + DeepSeek connected (model: {settings.deepseek_model})")
        connected = True

    # Priority 5: OpenAI
    openai_key = (settings.openai_api_key or '').strip()
    if _is_valid_key(openai_key):
        from app.core.llm import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(openai_key, settings.openai_model, "https://api.openai.com/v1")
        orchestrator.llm.register("openai", provider, default=not connected)
        gateway.register("openai", provider, priority=50, default=not connected)
        print(f"[JARVIS] + OpenAI connected (model: {settings.openai_model})")
        connected = True

    # Priority 6: Ollama (local)
    if settings.local_model_path and not connected:
        from app.core.llm import OllamaProvider
        import httpx
        try:
            r = httpx.get(settings.local_model_path, timeout=3.0)
            if r.status_code == 200:
                provider = OllamaProvider(settings.local_model_path, settings.ollama_model)
                orchestrator.llm.register("ollama", provider, default=True)
                gateway.register("ollama", provider, priority=60, default=True)
                print(f"[JARVIS] + Ollama connected (model: {settings.ollama_model})")
                connected = True
        except Exception:
            pass

    if not connected:
        print("[JARVIS] ===================================================")
        print("[JARVIS] WARNING: No LLM provider configured. Status: LLM_UNAVAILABLE")
        print("[JARVIS]   JARVIS will use keyword fallback only — NOT an LLM.")
        print("[JARVIS]   Add a key to backend/.env to enable real AI:")
        print("[JARVIS]   - OPENROUTER_API_KEY  (free: https://openrouter.ai/settings/keys)")
        print("[JARVIS]   - GROQ_API_KEY        (free: https://console.groq.com/keys)")
        print("[JARVIS]   - GEMINI_API_KEY      (free: https://aistudio.google.com/app/apikey)")
        print("[JARVIS] ===================================================")

    # Wire AIRuntime — attaches to orchestrator so all live requests flow through it
    if connected:
        try:
            from app.ai import AIRuntime
            orchestrator.ai_runtime = AIRuntime(gateway=gateway)
            print("[JARVIS] + AIRuntime initialized (gateway wired). NOTE: normal chat routes via orchestrator._call_runtime() -> gateway.complete() directly. Brain/ExecutionEngine/agents are initialized but not yet active in the normal chat path.")
        except Exception as e:
            print(f"[JARVIS] AIRuntime init failed (falling back to LLMRouter): {e}")


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
