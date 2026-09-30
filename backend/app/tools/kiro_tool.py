"""
app/tools/kiro_tool.py
======================
Kiro CLI integration tool for JARVIS OS.

Connects to a running `kiro-cli serve` WebSocket server (default port 8082)
and lets JARVIS delegate coding assistance, code review, and analysis tasks
to Kiro using the organisation's Ericsson Kiro access.

Usage (from orchestrator or any tool caller):
    result = await ask_kiro("Explain the intentRouter.ts architecture")
    result = await ask_kiro("Review the capabilityTools.ts file for bugs")

The tool is registered in ToolRegistry as 'kiro_assist'.
JARVIS will use it when the user asks coding/architecture questions.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

# Kiro serve WebSocket endpoint
KIRO_WS_URL = os.getenv("KIRO_WS_URL", "ws://localhost:8082")
KIRO_TIMEOUT = float(os.getenv("KIRO_TIMEOUT", "60"))

# Project root — injected as context so Kiro knows where files are
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)


async def ask_kiro(
    query: str,
    agent: str = "jarvis",
    timeout: float = KIRO_TIMEOUT,
) -> dict:
    """
    Send a query to the running kiro-cli serve instance and return the response.

    Parameters
    ----------
    query   : Natural language question or task for Kiro
    agent   : Kiro agent name to use (default: 'jarvis' — our custom agent)
    timeout : Max seconds to wait for response

    Returns
    -------
    dict with keys:
        success  : bool
        response : str   — Kiro's answer
        error    : str   — error message if success=False
    """
    try:
        import websockets  # type: ignore
    except ImportError:
        return {
            "success": False,
            "response": "",
            "error": "websockets package not installed. Run: pip install websockets",
        }

    # Build the message payload for kiro-cli serve
    payload = {
        "query": query,
        "agent": agent,
        "cwd": _PROJECT_ROOT,
    }

    try:
        async with websockets.connect(
            KIRO_WS_URL,
            open_timeout=10,
            close_timeout=5,
        ) as ws:
            await ws.send(json.dumps(payload))

            full_response = ""
            deadline = asyncio.get_event_loop().time() + timeout

            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return {
                        "success": False,
                        "response": full_response or "",
                        "error": "Kiro response timeout",
                    }

                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    # Plain text token
                    full_response += raw
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "token":
                    full_response += msg.get("content", "")
                elif msg_type == "message":
                    full_response += msg.get("content", "")
                elif msg_type == "done" or msg_type == "end":
                    if msg.get("content"):
                        full_response += msg["content"]
                    break
                elif msg_type == "error":
                    return {
                        "success": False,
                        "response": "",
                        "error": msg.get("message", "Kiro returned an error"),
                    }

            return {
                "success": True,
                "response": full_response.strip(),
                "error": "",
            }

    except ConnectionRefusedError:
        return {
            "success": False,
            "response": "",
            "error": (
                "Kiro serve is not running. "
                "Start it with: "
                "C:\\Users\\edxxfri\\AppData\\Local\\Kiro-Cli\\kiro-cli.exe serve --port 8082"
            ),
        }
    except Exception as e:
        return {
            "success": False,
            "response": "",
            "error": f"Kiro connection error: {e}",
        }


async def kiro_status() -> dict:
    """Check if kiro-cli serve is reachable."""
    try:
        import websockets  # type: ignore
        async with websockets.connect(KIRO_WS_URL, open_timeout=3):
            return {"running": True, "url": KIRO_WS_URL}
    except Exception:
        return {"running": False, "url": KIRO_WS_URL}
