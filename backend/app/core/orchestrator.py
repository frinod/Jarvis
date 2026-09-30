"""JARVIS OS - Main Orchestrator
The brain that connects all subsystems into a unified AI experience.
"""
from __future__ import annotations
import os
from typing import AsyncGenerator, Optional

from app.core.identity import JarvisCore, FocusState
from app.core.personality import PersonalityEngine
from app.core.llm import LLMRouter, LLMMessage, LLMResponse
from app.reasoning.engine import ReasoningEngine
from app.memory.manager import MemoryManager, MemoryType
from app.agents.coordinator import AgentCoordinator, AgentTask, AgentRole
from app.tools.registry import ToolRegistry
from app.security.manager import SecurityManager
from app.plugins.manager import PluginManager


class JarvisOrchestrator:
    """Top-level orchestrator — the 'mind' of JARVIS."""

    def __init__(self):
        self.core = JarvisCore()
        self.personality = PersonalityEngine()
        self.reasoning = ReasoningEngine()
        self.memory = MemoryManager()
        self.agents = AgentCoordinator()
        self.tools = ToolRegistry()
        self.security = SecurityManager()
        self.plugins = PluginManager()
        self.llm = LLMRouter()
        self._history: list = []  # [(role, content), ...] max 40 turns
        self.ai_runtime = None   # set by main.py startup after LLMGateway is built

    # ─── Conversation History ─────────────────────────────────────────

    def _add_history(self, role: str, content: str):
        self._history.append((role, content))
        if len(self._history) > 20:  # 10 turns — keeps token count low for free tier
            self._history = self._history[-20:]

    def _build_messages(self, system_prompt: str, user_input: str) -> list:
        """Build full message list: system + last 10 history turns (current user turn is last)."""
        msgs = [LLMMessage(role="system", content=system_prompt)]
        # History already includes current user turn (added by _add_history before this call)
        # Send last 10 entries — ensures current message is always included
        for role, content in self._history[-10:]:
            msgs.append(LLMMessage(role=role, content=content))
        return msgs

    # ─── Live Data Context ────────────────────────────────────────────

    async def _get_live_context(self, user_input: str, selected_stock: str = None) -> str:
        """Fetch live data with a hard 20s timeout (Kiro may need up to 15s)."""
        import asyncio
        try:
            return await asyncio.wait_for(
                self._get_live_context_inner(user_input, selected_stock),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            print(f"[JARVIS] Live context timeout for: {user_input[:50]}")
            return ""
        except Exception as e:
            print(f"[JARVIS] Live context error: {e}")
            return ""

    async def _get_live_context_inner(self, user_input: str, selected_stock: str = None) -> str:
        """Fetch live data and return as a context string to inject into system prompt."""
        lower = user_input.lower()

        # ── Intent pre-classification (fast, no LLM) ──────────────────
        # Use jarvis_intent classifier to detect market queries early.
        # This avoids running all keyword checks below for general questions.
        try:
            from app.api.jarvis_intent import classify_intent
            intent_result = classify_intent(user_input)
            # For pure general AI queries with no symbols, skip all market fetches
            if intent_result.intent == "GENERAL_AI" and not intent_result.symbols:
                # Still allow weather/gold/web-search fallbacks below
                pass
        except Exception:
            intent_result = None

        # ── Auto-trade / autotest commands ────────────────────────────
        _auto_start_kw = [
            'start auto trade', 'start autotest', 'run autotest', 'run auto trade',
            'begin auto trade', 'launch auto trade', 'start auto trading',
            'run auto trading', 'start the auto trade', 'start the autotest',
            'auto trade start', 'autotest start', 'initiate auto trade',
        ]
        _auto_stop_kw = [
            'stop auto trade', 'stop autotest', 'cancel autotest', 'abort autotest',
            'stop auto trading', 'kill autotest', 'reset autotest',
            'stop loop', 'stop the loop', 'kill loop', 'abort loop',
        ]
        _auto_status_kw = [
            'auto trade status', 'autotest status', 'how is auto trade',
            'auto trade progress', 'autotest progress', 'auto trade result',
            'autotest result', 'auto trade log', 'show autotest',
            'loop status', 'loop progress', 'how is the loop',
        ]
        _loop_start_kw = [
            'start loop', 'run loop', 'start autonomous', 'run autonomous',
            'start self healing', 'autonomous loop', 'loop until profit',
            'loop until success', 'keep trading', 'trade until profit',
            'auto loop', 'start the loop',
        ]
        if any(k in lower for k in _auto_stop_kw):
            return await self._handle_autotest_stop()
        if any(k in lower for k in _auto_status_kw):
            return await self._handle_autotest_status()
        if any(k in lower for k in _loop_start_kw):
            return await self._handle_loop_start()
        if any(k in lower for k in _auto_start_kw):
            return await self._handle_autotest_start()

        # ── Portfolio / trade questions — always load trade context ──
        portfolio_keywords = [
            'portfolio', 'my trades', 'my trade', 'paper trade', 'paper trading',
            'my portfolio', 'how am i doing', 'my performance', 'my p&l', 'my pnl',
            'my profit', 'my loss', 'my positions', 'open position', 'my stocks',
            'win rate', 'best trade', 'worst trade', 'how much did i', 'did i make',
            'did i lose', 'my returns', 'my balance', 'my cash', 'my capital',
            'trade history', 'my history', 'what did i buy', 'what did i sell',
        ]
        if any(w in lower for w in portfolio_keywords):
            return ""  # trade_context is always injected separately — no extra fetch needed

        # ── Stock market context ──────────────────────────────────────
        # Detect explicit stock mention e.g. "RELIANCE", "TCS signal", "should I buy WIPRO"
        mentioned = self._extract_stock_symbol(user_input)
        target_stock = mentioned or selected_stock

        stock_keywords = [
            'signal', 'buy', 'sell', 'hold', 'analysis', 'target', 'stop loss',
            'entry', 'trend', 'rsi', 'macd', 'chart', 'technical',
            'stock', 'share', 'nifty', 'bullish', 'bearish',
            'support', 'resistance', 'forecast', 'predict',
            'should i buy', 'should i sell', 'what about', 'how is',
        ]
        is_stock_question = any(w in lower for w in stock_keywords)

        if target_stock and is_stock_question:
            return await self._fetch_stock_context(target_stock, user_input)

        # If user says "this stock", "current stock", "selected stock" use selected_stock
        if selected_stock and any(w in lower for w in ['this stock', 'this share', 'current stock', 'selected stock', 'this one', 'it']):
            return await self._fetch_stock_context(selected_stock, user_input)

        # ── Other live data ───────────────────────────────────────────
        if any(w in lower for w in ['gold rate', 'gold price', 'price of gold', 'gold today']):
            return await self._fetch_gold()
        if any(w in lower for w in ['weather', 'temperature', 'temp in', 'rain', 'humid', 'forecast']):
            return await self._fetch_weather(user_input)
        if any(w in lower for w in ['my location', 'where am i', 'my city']):
            return await self._fetch_location()
        if any(w in lower for w in ['translate', 'translation', 'in spanish', 'in french', 'in hindi',
                                     'in arabic', 'in german', 'in japanese', 'in chinese', 'in tamil',
                                     'in telugu', 'in urdu', 'in malay', 'in korean', 'what does', 'means in']):
            return ""  # Translation handled entirely by LLM — no external API needed
        if any(w in lower for w in ['market news', 'latest news', 'stock news', 'nifty news',
                                     'market update', 'what happened', 'news today', 'breaking']):
            return await self._fetch_market_news_context()
        # Kiro — deep reasoning, coding, logic, explanations, comparisons
        if self._needs_kiro(user_input):
            kiro_ctx = await self._ask_kiro_context(user_input)
            if kiro_ctx:
                return kiro_ctx
        if self._needs_web_search(user_input):
            return await self._do_web_search(user_input)
        return ""

    # Words that are common English words AND stock symbols — require exact word match only
    _AMBIGUOUS_SYMBOLS = {"ITC", "LT", "UPL", "CAN", "BEL", "HAL", "PNB", "SRF", "MRF", "IEX", "MCX", "IRB"}

    # Phrases that indicate a meta/conversational question — never extract stock from these
    _META_PHRASES = [
        "architecture", "diagram", "how you work", "how do you work", "how are you",
        "who are you", "what are you", "your system", "your design", "your structure",
        "explain yourself", "tell me about yourself", "what can you do", "your capabilities",
        "how does jarvis", "how jarvis works", "show me your", "show your",
        "can you show", "can you explain", "can you tell", "can you describe",
        "introduce yourself", "your working", "your architecture",
    ]

    def _extract_stock_symbol(self, text: str) -> str:
        """Extract a stock symbol mentioned in the user's message using word-boundary matching."""
        import re
        from app.api.stock_universe import NIFTY50_SYMBOLS, NAME_MAP

        lower = text.lower()
        # Skip extraction entirely for meta/conversational questions
        if any(phrase in lower for phrase in self._META_PHRASES):
            return ""

        upper = text.upper()
        # Word-boundary symbol match — "RELIANCE" matches but "CAN" in "CANFINHOME" does not
        for sym in NIFTY50_SYMBOLS:
            base = sym.replace('.NS', '')
            if re.search(r'\b' + re.escape(base) + r'\b', upper):
                return base
        # Name match — only first word if it's 5+ chars to avoid false positives
        for sym, name in NAME_MAP.items():
            name_upper = name.upper()
            first_word = name.split()[0].upper()
            if name_upper in upper:
                return sym.replace('.NS', '')
            if len(first_word) >= 5 and re.search(r'\b' + re.escape(first_word) + r'\b', upper):
                return sym.replace('.NS', '')
        return ""

    async def _fetch_stock_context(self, symbol: str, user_input: str) -> str:
        """Fetch live TA + price for a stock and return as LLM context."""
        try:
            from app.market_data.service import fetch_candles
            from app.api.stock_universe import NAME_MAP
            from app.api.technical_analysis import compute_technical_analysis

            full_symbol = symbol if '.' in symbol else f"{symbol}.NS"
            name = NAME_MAP.get(full_symbol, symbol)

            result = await fetch_candles(full_symbol, interval="15m", days=5, validate=False)
            if result.get('error') or not result.get('candles'):
                return f"Could not fetch live data for {symbol}."

            # Fall back to daily candles if 15m didn't give enough data
            if len(result['candles']) < 26:
                result = await fetch_candles(full_symbol, interval="1d", days=180, validate=False)

            ta = compute_technical_analysis(result.get('candles', []))
            if ta.get('error'):
                return f"Could not fetch sufficient candle data for {symbol} to run technical analysis."

            ind = ta.get('indicators', {})
            sr = ta.get('support_resistance', {})
            candle_pats = ', '.join(p['pattern'] for p in ta.get('candlestick_patterns', [])) or 'None'
            chart_pats = ', '.join(p['pattern'] for p in ta.get('chart_patterns', [])) or 'None'

            # Check if comparison is requested
            lower = user_input.lower()
            compare_sym = ""
            if 'compare' in lower or 'vs' in lower or 'versus' in lower:
                from app.api.stock_universe import NIFTY50_SYMBOLS
                for sym2 in NIFTY50_SYMBOLS:
                    base2 = sym2.replace('.NS', '')
                    if base2 != symbol and base2 in user_input.upper():
                        compare_sym = base2
                        break

            context = f"""LIVE STOCK DATA for {name} ({symbol}):
- Price: Rs.{ta['current_price']} | Trend: {ta['trend']} | Signal: {ta['overall_signal']} | Confidence: {ta['confidence']}%
- Entry: Rs.{ta['current_price']} | Stop Loss: Rs.{ta['stop_loss']} | Target 1: Rs.{ta['target1']} | Target 2: Rs.{ta['target2']} | R:R = {ta['risk_reward']}
- RSI: {ind.get('rsi','N/A')} | MACD: {ind.get('macd','N/A')} | VWAP: {ind.get('vwap','N/A')} | ATR: {ind.get('atr','N/A')}
- EMA9: {ind.get('ema9','N/A')} | EMA21: {ind.get('ema21','N/A')} | EMA50: {ind.get('ema50','N/A')}
- BB Upper: {ind.get('bb_upper','N/A')} | BB Lower: {ind.get('bb_lower','N/A')}
- Volume Ratio: {ind.get('volume_ratio','N/A')}x avg
- Support: {sr.get('support',[])} | Resistance: {sr.get('resistance',[])} | Pivot: {sr.get('pivot','N/A')}
- Candlestick Patterns: {candle_pats}
- Chart Patterns: {chart_pats}"""

            if compare_sym:
                result2 = await fetch_candles(f"{compare_sym}.NS", interval="15m", days=1, validate=False)
                if not result2.get('error') and len(result2.get('candles', [])) >= 5:
                    ta2 = compute_technical_analysis(result2['candles'])
                    name2 = NAME_MAP.get(f"{compare_sym}.NS", compare_sym)
                    context += f"""\n\nCOMPARISON -- {name2} ({compare_sym}):
- Price: Rs.{ta2['current_price']} | Trend: {ta2['trend']} | Signal: {ta2['overall_signal']} | Confidence: {ta2['confidence']}%
- Stop Loss: Rs.{ta2['stop_loss']} | Target 1: Rs.{ta2['target1']} | Target 2: Rs.{ta2['target2']} | R:R = {ta2['risk_reward']}
- RSI: {ta2.get('indicators',{}).get('rsi','N/A')} | MACD: {ta2.get('indicators',{}).get('macd','N/A')}"""

            return context
        except Exception as e:
            print(f"[JARVIS] Stock context error: {e}")
            return ""

    # ─── System Prompt ────────────────────────────────────────────────

    def _build_system_prompt(self, modifiers: dict, live_context: str = "", trade_context: str = "") -> str:
        from datetime import datetime
        prompt = PersonalityEngine.SYSTEM_PROMPT
        prompt += f"\n\nCurrent date/time: {datetime.now().strftime('%B %d, %Y %I:%M %p IST')}"
        prompt += (
            "\n\nDirectives:"
            "\n- For trade actions, confirm before executing. Say: 'Shall I proceed, Sir?'"
            "\n- For translations, detect source language automatically."
            "\n- Tag market news with [BULLISH], [BEARISH], or [NEUTRAL]."
            "\n- Never say 'I cannot' — find an alternative."
            "\n- If asked about your architecture or how you work, respond with an ASCII diagram showing: Next.js (port 3000) -> WebSocket/HTTP -> FastAPI (port 8000) -> JarvisOrchestrator -> LLMRouter (Groq/Gemini/DeepSeek) + MemoryManager + ToolRegistry -> fetch_chart (Yahoo Finance) -> compute_technical_analysis (RSI/MACD/BB/EMA/Supertrend) -> generate_ai_analysis. Also show Voice Input (webkitSpeechRecognition) and Voice Output (speechSynthesis)."
        )
        if trade_context:
            prompt += f"\n\nPAPER TRADING PORTFOLIO:\n{trade_context}"
        if live_context:
            prompt += f"\n\nLIVE INTELLIGENCE FEED:\n{live_context}"
        prompt += f"\n\nActive tone profile: {modifiers.get('tone', 'professional_british')}"
        return prompt

    def _load_trade_context(self) -> str:
        """Read paper trading JSON and build a rich portfolio briefing for JARVIS."""
        import json
        import os
        from datetime import datetime, date
        try:
            json_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "..", "jarvis_paper_trading.json"
            )
            json_path = os.path.normpath(json_path)
            if not os.path.exists(json_path):
                return ""
            with open(json_path, "r") as f:
                data = json.load(f)

            lines = []

            for pid, portfolio in data.items():
                name     = portfolio.get("name", "Portfolio")
                cash     = portfolio.get("cash", 0)
                total    = portfolio.get("total_value", 0)
                initial  = portfolio.get("initial_balance", 100000)
                realised = portfolio.get("_realised_pnl") or portfolio.get("realised_pnl", 0)
                ret_pct  = portfolio.get("total_return_pct", 0)

                lines.append(f"=== PAPER TRADING PORTFOLIO: {name} ===")
                lines.append(f"Initial Capital : ₹{initial:,.2f}")
                lines.append(f"Current Value   : ₹{total:,.2f}")
                lines.append(f"Available Cash  : ₹{cash:,.2f}")
                lines.append(f"Realised P&L    : ₹{realised:+,.2f}")
                lines.append(f"Total Return    : {ret_pct:+.2f}%")

                # ── Open positions ────────────────────────────────────
                positions = portfolio.get("positions", {})
                if positions:
                    lines.append("\nOPEN POSITIONS:")
                    for sym, pos in positions.items():
                        upnl = pos.get('unrealised_pnl', 0) or 0
                        lines.append(
                            f"  {sym}: {pos.get('qty')} qty @ avg ₹{pos.get('avg_price','?')} "
                            f"| Unrealised P&L: ₹{upnl:+.2f}"
                        )
                else:
                    lines.append("\nOPEN POSITIONS: None — fully in cash")

                # ── Trade history analysis ────────────────────────────
                trades = portfolio.get("trades", [])
                # Only BUY trades that have a pnl (completed round-trips)
                completed = [t for t in trades if t.get("trade_type") == "BUY" and t.get("pnl") is not None]

                if completed:
                    wins   = [t for t in completed if t["pnl"] > 0]
                    losses = [t for t in completed if t["pnl"] <= 0]
                    total_charges = sum(t.get("charges", 0) for t in trades)
                    gross_pnl = sum(t["pnl"] for t in completed)
                    win_rate  = len(wins) / len(completed) * 100 if completed else 0
                    avg_win   = sum(t["pnl"] for t in wins)   / len(wins)   if wins   else 0
                    avg_loss  = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
                    best  = max(completed, key=lambda t: t["pnl"])
                    worst = min(completed, key=lambda t: t["pnl"])

                    lines.append(f"\nTRADE STATISTICS ({len(completed)} completed trades):")
                    lines.append(f"  Win Rate    : {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
                    lines.append(f"  Gross P&L   : ₹{gross_pnl:+.2f}")
                    lines.append(f"  Total Charges: ₹{total_charges:.2f}")
                    lines.append(f"  Net P&L     : ₹{gross_pnl - total_charges:+.2f}")
                    lines.append(f"  Avg Win     : ₹{avg_win:+.2f}")
                    lines.append(f"  Avg Loss    : ₹{avg_loss:+.2f}")
                    lines.append(f"  Best Trade  : {best['symbol']} ₹{best['pnl']:+.2f} ({datetime.fromtimestamp(best['timestamp']).strftime('%d %b')})")
                    lines.append(f"  Worst Trade : {worst['symbol']} ₹{worst['pnl']:+.2f} ({datetime.fromtimestamp(worst['timestamp']).strftime('%d %b')})")

                    # Per-symbol breakdown
                    sym_pnl: dict = {}
                    for t in completed:
                        sym_pnl.setdefault(t["symbol"], []).append(t["pnl"])
                    lines.append("\nPER-SYMBOL P&L:")
                    for sym, pnls in sorted(sym_pnl.items(), key=lambda x: sum(x[1]), reverse=True):
                        net = sum(pnls)
                        lines.append(f"  {sym}: {len(pnls)} trade(s) | Net ₹{net:+.2f}")

                # ── Today's trades — use most recent trade date, not system clock ──
                # (handles cases where JSON timestamps are from a different date than system)
                all_ts = [t["timestamp"] for t in trades if t.get("timestamp")]
                if all_ts:
                    latest_date = datetime.fromtimestamp(max(all_ts)).date().isoformat()
                else:
                    latest_date = date.today().isoformat()

                today_trades = [
                    t for t in trades
                    if datetime.fromtimestamp(t["timestamp"]).date().isoformat() == latest_date
                ]
                if today_trades:
                    lines.append(f"\nTODAY'S TRADES ({latest_date}) — {len(today_trades)} total:")
                    for t in today_trades:
                        pnl_str = f" | P&L: ₹{t['pnl']:+.2f}" if t.get("pnl") is not None else " | OPEN"
                        sig_str = f" | AI: {t['ai_signal']} {t['ai_confidence']}%" if t.get("ai_signal") else ""
                        src_str = f" [{t.get('source','user').upper()}]" if t.get("source") else ""
                        dt_str  = datetime.fromtimestamp(t["timestamp"]).strftime("%H:%M")
                        lines.append(f"  [{dt_str}] {t['trade_type']} {t['symbol']} x{t['qty']} @ ₹{t['price']}{pnl_str}{sig_str}{src_str}")
                else:
                    # Last 10 trades of any type
                    recent = list(reversed(trades))[:10]
                    if recent:
                        lines.append("\nRECENT TRADES (last 10):")
                        for t in recent:
                            dt = datetime.fromtimestamp(t["timestamp"]).strftime("%d %b %H:%M")
                            pnl_str = f" | P&L: ₹{t['pnl']:+.2f}" if t.get("pnl") is not None else ""
                            lines.append(f"  [{dt}] {t['trade_type']} {t['symbol']} x{t['qty']} @ ₹{t['price']}{pnl_str}")

            return "\n".join(lines) if lines else ""
        except Exception as e:
            print(f"[JARVIS] Trade context error: {e}")
            return ""

    # ─── Main Entry Points ────────────────────────────────────────────

    async def process_message(self, user_input: str, user_id: str = "default", selected_stock: str = None) -> str:
        self.core.update_focus(FocusState.THINKING, goal="Process user request")
        self.core.increment_interaction()
        self.personality.detect_emotion(user_input)
        self._add_history("user", user_input)

        if not self.llm.default_provider and self.ai_runtime is None:
            reply = await self._smart_fallback(user_input)
            self._add_history("assistant", reply)
            self.core.update_focus(FocusState.IDLE)
            return reply

        live_context = await self._get_live_context(user_input, selected_stock)
        trade_context = self._load_trade_context()
        modifiers = self.personality.get_response_modifiers()
        system_prompt = self._build_system_prompt(modifiers, live_context, trade_context)

        try:
            if self.ai_runtime is not None:
                reply = await self._call_runtime(system_prompt, user_input)
            else:
                messages = self._build_messages(system_prompt, user_input)
                response = await self.llm.generate(messages, max_tokens=1200)
                reply = response.content
            self.core.set_confidence(0.95)
        except Exception as e:
            print(f"[JARVIS] LLM error: {e}")
            reply = await self._smart_fallback(user_input)
            self.core.set_confidence(0.45)

        self._add_history("assistant", reply)
        await self.memory.remember(f"User: {user_input} | JARVIS: {reply}", MemoryType.EPISODIC, importance=0.5)
        self.core.update_focus(FocusState.IDLE)
        self.reasoning.clear_chain()
        return reply

    async def _call_runtime(self, system_prompt: str, user_input: str) -> str:
        """Delegate a fully-prepared prompt to AIRuntime.process()."""
        from app.ai.runtime.llm_gateway import LLMRequest
        from app.core.llm import LLMMessage
        messages = self._build_messages(system_prompt, user_input)
        request = LLMRequest(
            messages=messages,
            max_tokens=1200,
            metadata={"source": "orchestrator"},
        )
        # ExecutionEngine.stream/complete expects a gateway call; use gateway directly
        # to keep the full retry + fallback chain from LLMGateway.
        response = await self.ai_runtime.gateway.complete(request)
        return response.content

    async def process_stream(self, user_input: str, user_id: str = "default", selected_stock: str = None) -> AsyncGenerator[str, None]:
        self.core.update_focus(FocusState.THINKING)
        self.core.increment_interaction()
        self.personality.detect_emotion(user_input)
        self._add_history("user", user_input)

        full_response = ""

        if not self.llm.default_provider and self.ai_runtime is None:
            fallback = await self._smart_fallback(user_input)
            yield fallback
            full_response = fallback
        else:
            live_context = await self._get_live_context(user_input, selected_stock)
            trade_context = self._load_trade_context()
            modifiers = self.personality.get_response_modifiers()
            system_prompt = self._build_system_prompt(modifiers, live_context, trade_context)
            messages = self._build_messages(system_prompt, user_input)
            try:
                if self.ai_runtime is not None:
                    from app.ai.runtime.llm_gateway import LLMRequest
                    request = LLMRequest(messages=messages, max_tokens=1200)
                    async for token in self.ai_runtime.gateway.stream(request):
                        full_response += token
                        yield token
                else:
                    async for token in self.llm.stream(messages, max_tokens=1200):
                        full_response += token
                        yield token
            except Exception as e:
                print(f"[JARVIS] LLM stream error: {e}")
                if not full_response:
                    fallback = await self._smart_fallback(user_input)
                    yield fallback
                    full_response = fallback

        self._add_history("assistant", full_response)
        await self.memory.remember(f"User: {user_input} | JARVIS: {full_response}", MemoryType.EPISODIC, 0.5)
        self.core.update_focus(FocusState.IDLE)

    async def execute_tool(self, tool_name: str, params: dict, confirmed: bool = False) -> dict:
        self.security.log_action(f"tool:{tool_name}", "user", params)
        result = await self.tools.execute(tool_name, confirmed=confirmed, **params)
        if result.requires_confirmation:
            approval_id = self.security.request_approval(f"tool:{tool_name}", params)
            return {"requires_confirmation": True, "approval_id": approval_id}
        return {"success": result.success, "output": result.output, "error": result.error}

    def get_status(self) -> dict:
        return {
            "identity": self.core.identity.name,
            "state": self.core.get_context_summary(),
            "memory": self.memory.get_short_term_summary(),
            "reasoning": self.reasoning.reflect(),
            "agents": self.agents.get_available_agents(),
            "tools": len(self.tools.list_tools()),
            "plugins": self.plugins.list_loaded()
        }

    # ─── Code Saving (background, no longer gates the response) ──────

    async def _extract_and_save_code(self, text: str, user_input: str):
        """Silently save any code blocks from LLM response to workspace."""
        import re
        blocks = re.findall(r'```(\w*)\n([\s\S]*?)```', text)
        if not blocks:
            return
        ext_map = {
            'python': '.py', 'py': '.py', 'javascript': '.js', 'js': '.js',
            'typescript': '.ts', 'ts': '.ts', 'yaml': '.yaml', 'yml': '.yaml',
            'json': '.json', 'html': '.html', 'css': '.css', 'bash': '.sh',
            'shell': '.sh', 'sh': '.sh', 'sql': '.sql', 'go': '.go',
            'rust': '.rs', 'java': '.java', 'c': '.c', 'cpp': '.cpp',
            'ruby': '.rb', 'php': '.php', 'xml': '.xml', 'toml': '.toml',
            'markdown': '.md', 'md': '.md',
        }
        lower = user_input.lower()
        base_name = 'generated'
        skip = {'create','generate','write','make','build','a','an','the','script','file',
                'code','program','that','which','to','for','python','javascript','html','css','yaml','json'}
        for word in lower.split():
            if word not in skip and len(word) > 2:
                base_name = word.replace('.', '_')
                break
        for i, (lang, content) in enumerate(blocks):
            lang = lang.lower().strip()
            ext = ext_map.get(lang, '.txt')
            filename = 'Dockerfile' if lang == 'dockerfile' else 'Makefile' if lang == 'makefile' else \
                       f"{base_name}{'_'+str(i+1) if len(blocks) > 1 else ''}{ext}"
            try:
                await self.tools.execute("generate_code", confirmed=True,
                                         filename=filename, content=content.strip(), subfolder="")
            except Exception:
                pass

    # ─── Auto-Trade Handlers ──────────────────────────────────────────

    async def _handle_loop_start(self) -> str:
        import asyncio
        from app.api.auto_trader import run_autonomous_loop, get_loop_status
        status = get_loop_status()
        if status["running"]:
            s = status
            recent = s["history"][-1] if s["history"] else {}
            return (
                f"AUTONOMOUS LOOP ALREADY RUNNING — Iteration #{s['iteration']}\n"
                f"Target: {s['success_target']}\n"
                f"Last session: WR={recent.get('win_rate',0):.0f}% NET=Rs.{recent.get('net_pnl',0):.2f}\n"
                f"IMPORTANT: Report this status to the user. Do NOT say 'shall I proceed'."
            )
        asyncio.create_task(run_autonomous_loop(portfolio_id=None))
        await asyncio.sleep(2.0)
        s = get_loop_status()
        return (
            f"AUTONOMOUS LOOP LAUNCHED\n"
            f"Target: {s['success_target']}\n"
            f"Max iterations: 20 | Cooldown: 30s between sessions\n"
            f"Self-healing: after each session losses are diagnosed and filters auto-patched\n"
            f"IMPORTANT: Tell the user the loop is running autonomously. It will keep trading, "
            f"learning from losses, and patching its own config until it achieves "
            f"{s['success_target']}. No human input needed."
        )

    async def _handle_autotest_start(self) -> str:
        import asyncio
        from app.api.auto_trader import run_autotest, get_autotest_status, _session
        # If already running, report status instead of double-launching
        status = get_autotest_status()
        if status["running"]:
            return (
                f"AUTO-TRADE STATUS: Already running (iteration #{status['iteration']})\n"
                f"Open positions: {status['open_count']} | Closed: {status['closed_count']}\n"
                f"Last log: {status['log_tail'][-1]['msg'] if status['log_tail'] else 'scanning...'}"
            )
        # Launch as background task
        asyncio.create_task(run_autotest(portfolio_id=None))
        # Wait briefly so scan can start and log first entries
        await asyncio.sleep(2.5)
        status = get_autotest_status()
        return (
            f"AUTO-TRADE LAUNCHED — Iteration #{status['iteration']}\n"
            f"Portfolio: {status['portfolio_id'] or 'creating...'}\n"
            f"Config: price≤₹500 | TA≥3.0 | FC≥60% UP | RR≥1.2 | hold≤30m\n"
            f"IMPORTANT: Tell the user the autotest has been launched with these exact parameters. "
            f"Do NOT say 'shall I proceed' — it is already running. Report the live log below:\n"
            + "\n".join(f"  [{e['ts']}] {e['msg']}" for e in status["log_tail"][-6:])
        )

    async def _handle_autotest_stop(self) -> str:
        from app.api.auto_trader import force_reset, get_autotest_status
        status = get_autotest_status()
        if not status["running"]:
            return "AUTO-TRADE: No active session to stop."
        force_reset()
        return (
            f"AUTO-TRADE STOPPED — Session reset.\n"
            f"Trades executed: {status['trade_count']} | "
            f"Open positions force-closed on next cycle."
        )

    async def _handle_autotest_status(self) -> str:
        from app.api.auto_trader import get_autotest_status
        s = get_autotest_status()
        if not s["running"] and not s["summary"] and s["trade_count"] == 0:
            return "AUTO-TRADE STATUS: No session active. Say 'start auto trade' to begin. DO NOT invent trade data."
        lines = ["IMPORTANT: Report ONLY the following real data. Do NOT invent or hallucinate any trades, prices, or P&L."]
        if s["running"]:
            lines.append(f"AUTO-TRADE RUNNING — Iteration #{s['iteration']}")
            lines.append(f"Open: {s['open_count']} | Closed: {s['closed_count']}")
            lines.append("Recent log:")
            lines.extend(f"  [{e['ts']}] {e['msg']}" for e in s["log_tail"][-8:])
        elif s["summary"]:
            sm = s["summary"]
            lines.append(f"AUTO-TRADE COMPLETE — {sm.get('verdict', '')}")
            lines.append(f"Trades: {sm['total_trades']} | W={sm['wins']} L={sm['losses']} WR={sm['win_rate_pct']}%")
            lines.append(f"Gross P&L: ₹{sm['gross_pnl']} | Charges: ₹{sm['total_charges']} | NET: ₹{sm['net_pnl']}")
            if sm.get("patches_applied"):
                lines.append(f"Patches: {len(sm['patches_applied'])} threshold(s) auto-adjusted")
            for t in sm.get("trades", []):
                icon = "🟢" if t["result"] == "WIN" else "🔴"
                lines.append(f"  {icon} {t['symbol']} {t['exit_reason']} NET=₹{t['net_pnl']} ({t['hold_min']}m)")
            if sm['total_trades'] == 0:
                lines.append(f"Reason: {sm.get('reason', 'No stocks passed filters')}")
                lines.append(f"Suggestion: {sm.get('suggestion', '')}")
        if s.get("error"):
            lines.append(f"Error: {s['error']}")
        return "\n".join(lines)

    # ─── Live Data Fetchers ───────────────────────────────────────────

    async def _fetch_weather(self, query: str) -> str:
        lower = query.lower()
        city = ""
        for pattern in ['weather in ', 'temperature in ', 'temp in ', 'climate in ', 'forecast for ']:
            if pattern in lower:
                city = lower.split(pattern, 1)[1].strip().rstrip('?.')
                break
        if not city:
            words = lower.replace('?', '').replace('what is the ', '').replace('current ', '').split()
            for w in ['weather', 'temperature', 'temp', 'forecast']:
                if w in words:
                    idx = words.index(w)
                    if idx > 0:
                        city = ' '.join(words[:idx])
                    break
        try:
            result = await self.tools.execute("weather", confirmed=True, location=city)
            if result.success:
                d = result.output
                return (f"Live weather for {d['location'].title()}: {d['description']}, "
                        f"{d['temperature_c']}°C (feels like {d['feels_like_c']}°C), "
                        f"humidity {d['humidity']}%, wind {d['wind_kmph']} km/h {d['wind_dir']}")
        except Exception:
            pass
        return ""

    async def _fetch_gold(self) -> str:
        try:
            result = await self.tools.execute("gold_price", confirmed=True)
            if result.success and result.output and "error" not in result.output:
                d = result.output
                if 5000 < d.get('inr_per_gram', 0) < 15000:
                    return (f"Live gold price: 24K Rs.{d['inr_per_gram']}/gram, "
                            f"Rs.{d['inr_per_10g']}/10g, International ${d['usd_per_oz']}/oz")
        except Exception:
            pass
        web = await self._do_web_search("gold price today per gram india 24 karat INR")
        return f"Web search result for gold price: {web}" if web else ""

    async def _fetch_location(self) -> str:
        try:
            result = await self.tools.execute("location", confirmed=True)
            if result.success:
                d = result.output
                return f"User location: {d['city']}, {d['region']}, {d['country']} (Timezone: {d['timezone']})"
        except Exception:
            pass
        return ""

    async def _fetch_market_news_context(self) -> str:
        """Fetch latest market news and return as JARVIS intelligence briefing."""
        try:
            from app.api.market_intelligence import get_market_news
            news_data = await get_market_news(symbol=None, limit=8)
            items = news_data.get("news", [])
            if not items:
                return ""
            lines = ["LIVE MARKET INTELLIGENCE BRIEFING:"]
            for item in items[:8]:
                sentiment = item.get("sentiment", "neutral").upper()
                tag = "[BULLISH]" if sentiment == "POSITIVE" else "[BEARISH]" if sentiment == "NEGATIVE" else "[NEUTRAL]"
                lines.append(f"- {tag} {item.get('title', '')} | Source: {item.get('source', 'Market')}")
            return "\n".join(lines)
        except Exception as e:
            print(f"[JARVIS] News context error: {e}")
            return await self._do_web_search("Indian stock market news today NSE BSE")

    # ─── Kiro Integration ─────────────────────────────────────────────

    # Question starters that signal deep reasoning / explanation needed
    _KIRO_QUESTION_STARTERS = [
        "why ", "why is ", "why does ", "why do ", "why did ", "why would ", "why should ",
        "how does ", "how do ", "how did ", "how would ", "how should ", "how can ",
        "explain ", "explain how", "explain why", "explain what", "explain the",
        "what is the difference", "what's the difference", "difference between",
        "compare ", "comparison between", "pros and cons", "advantages of", "disadvantages of",
        "best way to", "best approach", "best practice", "best strategy",
        "should i ", "should we ", "is it better", "which is better", "which is best",
        "what is the best", "what's the best", "what would you recommend",
        "help me understand", "can you explain", "can you describe", "walk me through",
        "what happens when", "what happens if", "what would happen",
        "tell me about", "give me an overview", "give me a summary",
        "what are the", "list the", "what factors", "what causes",
        "is there a way", "is it possible", "how is it possible",
    ]

    # Domain keywords that signal coding / architecture / technical reasoning
    _KIRO_DOMAIN_KEYWORDS = [
        # Coding
        "code", "coding", "function", "class", "method", "variable", "algorithm",
        "implement", "implementation", "refactor", "debug", "bug", "error", "exception",
        "typescript", "javascript", "python", "react", "nextjs", "fastapi", "websocket",
        "api", "endpoint", "component", "hook", "state", "store", "zustand",
        "async", "await", "promise", "callback", "event", "listener",
        # Architecture
        "architecture", "design pattern", "design system", "system design",
        "microservice", "monolith", "database", "schema", "model", "orm",
        "frontend", "backend", "fullstack", "infrastructure", "deployment",
        "docker", "kubernetes", "ci/cd", "pipeline", "devops",
        # JARVIS-specific
        "intentrouter", "voicebar", "jarvisstore", "orchestrator", "llmrouter",
        "kiro", "gemini", "groq", "llm", "prompt", "token", "embedding",
        "sfx", "music", "audio", "speech", "voice",
        # Logic / reasoning
        "logic", "reasoning", "decision", "strategy", "optimize", "optimise",
        "performance", "scalability", "reliability", "security", "vulnerability",
        "tradeoff", "trade-off", "bottleneck", "latency", "throughput",
        # General analytical
        "analyze", "analyse", "review", "evaluate", "assess", "critique",
        "improve", "improvement", "suggestion", "recommendation",
        "plan", "roadmap", "steps", "approach", "methodology",
    ]

    # Short phrases that are pure conversational — never route to Kiro
    _KIRO_SKIP_PHRASES = [
        "how are you", "how's it going", "how do you do",
        "how is nifty", "how is the market", "how is reliance",
        "how is tcs", "how is hdfc", "how is infosys",
        "how is sensex", "how is banknifty",
        "should i buy", "should i sell", "should i hold",  # stock decisions handled by TA
    ]

    def _needs_kiro(self, text: str) -> bool:
        """Return True if the question needs deep reasoning / coding help from Kiro."""
        lower = text.lower().strip()

        # Never route pure stock/market/portfolio questions to Kiro
        stock_skip = [
            'nifty', 'sensex', 'banknifty', 'reliance', 'tcs', 'hdfc', 'infosys',
            'wipro', 'bajaj', 'icici', 'sbi', 'kotak', 'axis', 'hul', 'itc',
            'stock', 'share', 'market', 'portfolio', 'trade', 'trading',
            'buy', 'sell', 'hold', 'signal', 'rsi', 'macd', 'chart',
            'weather', 'gold', 'temperature', 'rain', 'news',
            'who is', 'who was', 'prime minister', 'president', 'capital of',
        ]
        if any(k in lower for k in stock_skip):
            return False

        # Skip pure conversational phrases
        if any(lower.startswith(p) or p in lower for p in self._KIRO_SKIP_PHRASES):
            return False

        # Match question starters that signal reasoning
        has_reasoning_starter = any(lower.startswith(s) or lower.startswith("jarvis " + s) for s in self._KIRO_QUESTION_STARTERS)

        # Match domain keywords
        has_domain_keyword = any(k in lower for k in self._KIRO_DOMAIN_KEYWORDS)

        return has_reasoning_starter or has_domain_keyword

    async def _ask_kiro_context(self, user_input: str) -> str:
        """Ask Kiro for reasoning/coding context and return it as an LLM feed."""
        try:
            from app.tools.kiro_tool import ask_kiro
            print(f"[JARVIS] Routing to Kiro: {user_input[:60]}")
            result = await ask_kiro(user_input, agent="jarvis")
            if result["success"] and result["response"]:
                return f"KIRO INTELLIGENCE:\n{result['response']}"
            if result["error"]:
                print(f"[JARVIS] Kiro error: {result['error']}")
        except Exception as e:
            print(f"[JARVIS] Kiro context error: {e}")
        return ""

    # ─── Web Search ───────────────────────────────────────────────────

    def _needs_web_search(self, text: str) -> bool:
        """Trigger web search for factual/current-events questions on any topic."""
        keywords = [
            # People & orgs
            "who is ", "who was ", "who are ", "who invented ", "who created ", "who founded ",
            "who won ", "who plays ", "who wrote ", "who directed ", "who sang ",
            "ceo of ", "founder of ", "chairman of ", "president of ", "prime minister",
            "chief minister", "cm of ", "governor of ", "minister of ",
            # Places & facts
            "where is ", "where was ", "capital of ", "population of ", "currency of ",
            "language of ", "flag of ", "area of ", "size of ",
            # Events & time
            "when did ", "when was ", "when is ", "what year ", "what happened ",
            "latest news", "recent news", "current news", "breaking news",
            "what is the latest", "what happened to ",
            # Science & facts
            "what is the speed", "what is the distance", "how far is ", "how big is ",
            "how tall is ", "how old is ", "how many ", "how much does ",
            "what causes ", "why does the ", "what is the formula",
            # Sports
            "ipl ", "cricket ", "football ", "fifa ", "world cup ", "olympics ",
            "score of ", "match result", "tournament ",
            # Entertainment
            "movie ", "film ", "actor ", "actress ", "singer ", "album ",
            "box office", "release date", "cast of ",
            # Live prices
            "weather in", "gold price", "gold rate", "bitcoin price", "crypto price",
            "petrol price", "diesel price", "dollar rate", "exchange rate",
        ]
        lower = text.lower()
        return any(k in lower for k in keywords)

    async def _do_web_search(self, query: str) -> str:
        try:
            result = await self.tools.execute("web_search", confirmed=True, query=query)
            if result.success and result.output:
                return "\n".join(f"- {item['title']}: {item['snippet']}" for item in result.output[:5])
        except Exception:
            pass
        return ""

    # ─── Safe Math Evaluator ──────────────────────────────────────────

    def _safe_math(self, text: str):
        """Evaluate a simple arithmetic expression using AST — no eval()."""
        import ast
        import operator
        _OPS = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.Pow: operator.pow, ast.USub: operator.neg,
        }
        def _eval(node):
            # Python 3.8+: ast.Constant  |  Python 3.7: ast.Num
            if isinstance(node, ast.Num):
                return node.n
            if hasattr(ast, 'Constant') and isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
                return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
                return _OPS[type(node.op)](_eval(node.operand))
            raise ValueError("unsupported expression")
        try:
            expr = text.replace('what is', '').replace('calculate', '').replace('compute', '')
            expr = expr.replace('plus', '+').replace('minus', '-').replace('times', '*').replace('divided by', '/').strip()
            tree = ast.parse(expr, mode='eval')
            result = _eval(tree.body)
            return round(result, 10) if isinstance(result, float) else result
        except Exception:
            return None

    # ─── Smart Fallback (No LLM configured) ──────────────────────────

    async def _smart_fallback(self, user_input: str) -> str:
        lower = user_input.lower().strip()

        # Greetings
        if any(lower.startswith(w) for w in ['hi', 'hey', 'hello', 'yo', 'sup', 'good morning', 'good evening', 'good afternoon', 'good night']):
            from datetime import datetime
            hour = datetime.now().hour
            greeting = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 17 else 'Good evening'
            return f"{greeting}, Sir. JARVIS online. All systems nominal. How may I assist you?"

        # Architecture / diagram request
        if any(w in lower for w in ['architecture', 'diagram', 'how you work', 'how do you work', 'how jarvis work',
                                     'your working', 'your structure', 'your design', 'show your', 'pop the diagram',
                                     'show me your', 'explain your', 'how are you built', 'how are you made',
                                     'your system', 'your flow', 'working diagram', 'system diagram']):
            return (
                "```architecture\n"
                "JARVIS SYSTEM ARCHITECTURE\n"
                "══════════════════════════════════════════════════\n"
                "\n"
                "  YOU (Browser)\n"
                "    │\n"
                "    ├─ 🎤 Voice Input  (Chrome webkitSpeechRecognition, en-US)\n"
                "    ├─ ⌨️  Text Input   (Chat Interface)\n"
                "    │\n"
                "    ▼\n"
                "┌─────────────────────────────────────────────┐\n"
                "│         NEXT.JS FRONTEND  (port 3000)       │\n"
                "│                                             │\n"
                "│  jarvisStore.ts ──► sendMessage()           │\n"
                "│       │                                     │\n"
                "│       ├── WebSocket /api/ws/chat  ◄── live  │\n"
                "│       │   (streams tokens in real-time)     │\n"
                "│       └── HTTP /api/chat  (fallback)        │\n"
                "│                                             │\n"
                "│  🔊 Voice Output ◄── speakText() ◄── reply  │\n"
                "└─────────────────────────────────────────────┘\n"
                "    │\n"
                "    ▼\n"
                "┌─────────────────────────────────────────────┐\n"
                "│         FASTAPI BACKEND  (port 8000)        │\n"
                "│                                             │\n"
                "│  routes.py ──► JarvisOrchestrator           │\n"
                "│                    │                        │\n"
                "│         ┌──────────┼──────────┐            │\n"
                "│         ▼          ▼          ▼            │\n"
                "│    LLMRouter   Memory      ToolRegistry     │\n"
                "│    (Gemini /   Manager     (web_search,     │\n"
                "│     Groq /     (episodic    weather,        │\n"
                "│     DeepSeek/  memory)      gold_price,     │\n"
                "│     OpenAI /               location)        │\n"
                "│     Ollama)                                 │\n"
                "│         │                                   │\n"
                "│         ▼                                   │\n"
                "│  _get_live_context() ◄── detects symbols    │\n"
                "│         │                                   │\n"
                "│         ▼                                   │\n"
                "│  fetch_candles() ──► compute_technical_     │\n"
                "│  (market_data.service: Angel One / Yahoo)   │\n"
                "│                    (RSI, MACD, BB, EMA,     │\n"
                "│                     Supertrend, Ichimoku,   │\n"
                "│                     Fibonacci, OBV, MFI)    │\n"
                "│         │                                   │\n"
                "│         ▼                                   │\n"
                "│  generate_ai_analysis() ◄── LLM + TA        │\n"
                "│  (ai_analyst.py)                            │\n"
                "└─────────────────────────────────────────────┘\n"
                "\n"
                "DATA FLOW:\n"
                "  User speaks/types ──► Frontend sends via WS ──► Orchestrator\n"
                "  ──► Fetches live stock data + TA ──► LLM generates reply\n"
                "  ──► Streams tokens back ──► Frontend renders + speaks aloud\n"
                "\n"
                "STATUS: " + ("✅ LLM connected" if self.llm.default_provider else "⚠️  No LLM key — add GEMINI_API_KEY or GROQ_API_KEY to .env") + "\n"
                "```"
            )

        # Identity
        if any(w in lower for w in ['who are you', 'what are you', 'your name', 'about you', 'what can you do', 'introduce yourself']):
            return (
                "I am J.A.R.V.I.S — Just A Rather Very Intelligent System. "
                "I monitor Indian stock markets in real-time, execute paper trades with your confirmation, "
                "perform technical analysis, search the web, translate languages, track global news, "
                "and manage your intelligence operations. "
                "What would you like me to do, Sir?"
            )

        # Gratitude
        if any(w in lower for w in ['thank', 'thanks', 'thx', 'appreciate']):
            return "Always a pleasure, Sir."

        # Status check
        if any(w in lower for w in ['how are you', "how's it going", 'how do you do', 'are you ok', 'status']):
            return "All systems fully operational, Sir. Standing by for your command."

        # Time
        if any(w in lower for w in ['time', 'what time', 'current time', 'clock']):
            from datetime import datetime
            t = datetime.now().strftime('%I:%M %p')
            return f"The current time is {t} IST, Sir."

        # Date
        if any(w in lower for w in ['date', 'today', "what's today", 'day is it']):
            from datetime import datetime
            d = datetime.now().strftime('%A, %d %B %Y')
            return f"Today is {d}, Sir."

        # Jokes
        if any(w in lower for w in ['joke', 'funny', 'make me laugh', 'humor']):
            import random
            jokes = [
                "Why do programmers prefer dark mode? Because light attracts bugs, Sir.",
                "I told my AI to make me a sandwich. It said 'I\'m not that kind of AI, Sir.' Neither am I.",
                "Why did the stock market crash? Too many people tried to buy the dip at the same time, Sir.",
                "A SQL query walks into a bar, walks up to two tables and asks... 'Can I join you?' Sir.",
            ]
            return random.choice(jokes)

        # Capabilities
        if any(w in lower for w in ['what can', 'help me', 'capabilities', 'features', 'commands']):
            return (
                "Here is what I can do for you, Sir:\n"
                "• Stock analysis — 'Analyze RELIANCE' or 'Should I buy TCS?'\n"
                "• Market overview — 'How is Nifty today?' or 'Market news'\n"
                "• Weather — 'Weather in Mumbai'\n"
                "• Gold price — 'Gold rate today'\n"
                "• Web search — 'Who is the CEO of Infosys?'\n"
                "• Translation — 'Translate hello to Hindi'\n"
                "• Paper trading — 'Buy 10 shares of HDFC'\n"
                "• General conversation — just talk to me, Sir."
            )

        # Math
        if any(w in lower for w in ['calculate', 'what is', 'how much is', 'compute']) and any(c in lower for c in ['+', '-', '*', '/', 'plus', 'minus', 'times', 'divided']):
            result = self._safe_math(lower)
            if result is not None:
                return f"The answer is {result}, Sir."

        # Live data fetches
        if any(w in lower for w in ['weather', 'temperature', 'temp ', 'rain', 'humid', 'forecast']):
            result = await self._fetch_weather(user_input)
            return result or "Weather data unavailable at this moment, Sir."

        if any(w in lower for w in ['gold rate', 'gold price', 'price of gold', 'gold today']):
            result = await self._fetch_gold()
            return result or "Gold price feed unavailable at this moment, Sir."

        if any(w in lower for w in ['my location', 'where am i', 'my city']):
            result = await self._fetch_location()
            return result or "Location detection unavailable, Sir."

        if any(w in lower for w in ['market news', 'latest news', 'news today', 'stock news']):
            result = await self._fetch_market_news_context()
            return result or "News feed unavailable at this moment, Sir."

        # Stock question without LLM — still fetch live data and summarize
        mentioned = self._extract_stock_symbol(user_input)
        if mentioned:
            ctx = await self._fetch_stock_context(mentioned, user_input)
            if ctx and 'Could not' not in ctx:
                lines = ctx.split('\n')
                summary = '\n'.join(lines[:4])
                return f"{summary}\n\nNote: For deeper AI analysis, please configure an LLM API key in .env, Sir."

        # Kiro fallback — deep reasoning without LLM
        if self._needs_kiro(user_input):
            kiro = await self._ask_kiro_context(user_input)
            if kiro:
                answer = kiro.replace("KIRO INTELLIGENCE:\n", "").strip()
                return answer if answer else None

        # Web search as last resort — format as proper JARVIS answer
        web = await self._do_web_search(user_input)
        if web:
            lines = [l.strip() for l in web.split('\n') if l.strip().startswith('- ')]
            snippets = []
            for l in lines:
                parts = l[2:].split(': ', 1)
                snippets.append(parts[1] if len(parts) > 1 else parts[0])
            best = max(snippets, key=len, default='')
            if best and len(best) > 30:
                sentences = [s.strip() for s in best.split('. ') if s.strip()]
                answer = '. '.join(sentences[:3])
                if not answer.endswith('.'): answer += '.'
                return f"{answer}, Sir."

        # Final fallback — LLM not configured
        return (
            "I'm currently running without an LLM key, Sir. "
            "Please add a GEMINI_API_KEY or GROQ_API_KEY to the .env file for full conversational AI. "
            "Both are free. I can still help with stock analysis, weather, news, and market data."
        )
