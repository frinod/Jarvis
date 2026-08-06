"""AI-powered stock analyst — combines TA signals with LLM reasoning."""
from __future__ import annotations
import json
from typing import Dict, Any, Optional

MARKET_KNOWLEDGE_SYSTEM = """You are an expert quantitative analyst and technical trader with deep knowledge of:

TECHNICAL ANALYSIS:
- All candlestick patterns (Doji, Hammer, Engulfing, Morning/Evening Star, Marubozu, Harami, Spinning Top, Three White Soldiers, Three Black Crows, etc.)
- Chart patterns (Head & Shoulders, Double Top/Bottom, Cup & Handle, Triangles, Flags, Pennants, Wedges, Channels)
- Indicators: RSI, MACD, Bollinger Bands, EMA/SMA crossovers, VWAP, ATR, Stochastic, OBV, Ichimoku Cloud, Fibonacci retracements
- Price action: Support/Resistance, trend lines, breakouts, pullbacks, consolidations
- Volume analysis: volume confirmation, climax volume, accumulation/distribution

MARKET CONCEPTS:
- Trend following vs mean reversion strategies
- Market structure: higher highs/lows, lower highs/lows
- Institutional order flow and smart money concepts
- Market phases: accumulation, markup, distribution, markdown (Wyckoff)
- Risk management: position sizing, stop-loss placement, risk/reward ratios
- Trading psychology: fear/greed, FOMO, support becoming resistance

NSE/BSE SPECIFIC:
- Indian market hours: 9:15 AM - 3:30 PM IST
- Nifty 50 and sectoral indices behavior
- FII/DII activity impact on markets
- Circuit breakers and price bands
- Derivatives expiry effects (monthly/weekly)

ANALYSIS RULES:
- Always provide specific price levels for stop-loss and targets
- Confidence should reflect signal confluence (multiple indicators agreeing)
- Risk/reward must be minimum 1:2 for a valid trade setup
- Always mention key risks that could invalidate the analysis
- Be honest about uncertainty — markets are probabilistic, not deterministic

Respond ONLY with valid JSON in the exact format requested. No markdown, no extra text."""


async def generate_ai_analysis(
    symbol: str,
    name: str,
    ta: Dict[str, Any],
    fundamentals: Optional[Dict] = None,
    llm=None,
) -> Dict[str, Any]:
    """Generate LLM-powered analysis combining TA signals."""

    if llm is None or not llm.default_provider:
        return _fallback_analysis(symbol, name, ta)

    # Build compact TA summary for the prompt
    ind = ta.get("indicators", {})
    signals = ta.get("signals", [])
    candle_patterns = ta.get("candlestick_patterns", [])
    chart_patterns = ta.get("chart_patterns", [])
    sr = ta.get("support_resistance", {})

    signal_summary = "\n".join([f"- {s['indicator']}: {s['signal'].upper()} ({s['strength']}) — {s['reason']}" for s in signals])
    candle_summary = ", ".join([f"{p['pattern']} ({p['type']})" for p in candle_patterns]) or "None detected"
    chart_summary  = ", ".join([f"{p['pattern']} ({p['type']})" for p in chart_patterns]) or "None detected"

    fund_summary = ""
    if fundamentals and not fundamentals.get("error"):
        fund_summary = f"""
FUNDAMENTALS:
- P/E: {fundamentals.get('pe_ratio', 'N/A')} | P/B: {fundamentals.get('pb_ratio', 'N/A')}
- Market Cap: {fundamentals.get('market_cap', 'N/A')}
- ROE: {fundamentals.get('roe', 'N/A')} | Debt/Equity: {fundamentals.get('debt_to_equity', 'N/A')}
- Revenue Growth: {fundamentals.get('revenue_growth', 'N/A')} | Profit Margin: {fundamentals.get('profit_margin', 'N/A')}"""

    prompt = f"""Analyze {symbol} ({name}) and provide a structured trading analysis.

TECHNICAL DATA:
- Current Price: ₹{ta['current_price']}
- Trend: {ta['trend']}
- TA Score: {ta['score']} | Pre-computed Signal: {ta['overall_signal']} | Confidence: {ta['confidence']}%

INDICATORS:
- RSI(14): {ind.get('rsi', 'N/A')}
- MACD: {ind.get('macd', 'N/A')} | Signal: {ind.get('macd_signal', 'N/A')} | Histogram: {ind.get('macd_histogram', 'N/A')}
- Bollinger: Upper {ind.get('bb_upper', 'N/A')} | Mid {ind.get('bb_mid', 'N/A')} | Lower {ind.get('bb_lower', 'N/A')}
- EMA9: {ind.get('ema9', 'N/A')} | EMA21: {ind.get('ema21', 'N/A')} | EMA50: {ind.get('ema50', 'N/A')}
- Stochastic K: {ind.get('stochastic_k', 'N/A')} | D: {ind.get('stochastic_d', 'N/A')}
- VWAP: {ind.get('vwap', 'N/A')} | ATR: {ind.get('atr', 'N/A')}
- Volume Ratio: {ind.get('volume_ratio', 'N/A')}x avg

INDICATOR SIGNALS:
{signal_summary}

CANDLESTICK PATTERNS: {candle_summary}
CHART PATTERNS: {chart_summary}

SUPPORT/RESISTANCE:
- Resistance: {sr.get('resistance', [])}
- Support: {sr.get('support', [])}
- Pivot: {sr.get('pivot', 'N/A')}
{fund_summary}

Respond with ONLY this JSON (no markdown):
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": <number 0-100>,
  "summary": "<2-3 sentence plain English summary of the setup>",
  "reasoning": "<detailed technical reasoning explaining why this signal, what patterns/indicators are driving it>",
  "entry_price": <number>,
  "stop_loss": <number>,
  "target1": <number>,
  "target2": <number>,
  "risk_reward": <number>,
  "timeframe": "<intraday|swing|positional>",
  "key_levels": {{
    "strong_resistance": <number>,
    "strong_support": <number>
  }},
  "risks": ["<risk1>", "<risk2>", "<risk3>"],
  "market_context": "<brief note on broader market/sector context>",
  "sentiment": "bullish" | "bearish" | "neutral"
}}"""

    try:
        from app.core.llm import LLMMessage
        messages = [
            LLMMessage(role="system", content=MARKET_KNOWLEDGE_SYSTEM),
            LLMMessage(role="user", content=prompt),
        ]
        response = await llm.generate(messages, temperature=0.3, max_tokens=1024)
        text = response.content.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        result["source"] = "ai"
        result["symbol"] = symbol
        return result
    except Exception as e:
        return _fallback_analysis(symbol, name, ta)


def _fallback_analysis(symbol: str, name: str, ta: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based fallback when LLM is unavailable."""
    signals = ta.get("signals", [])
    buy_count  = sum(1 for s in signals if s["signal"] == "buy")
    sell_count = sum(1 for s in signals if s["signal"] == "sell")
    price = ta["current_price"]

    reasoning_parts = [s["reason"] for s in signals]
    candle_parts = [f"{p['pattern']}: {p['desc']}" for p in ta.get("candlestick_patterns", [])]
    chart_parts  = [f"{p['pattern']}: {p['desc']}" for p in ta.get("chart_patterns", [])]

    all_reasoning = reasoning_parts + candle_parts + chart_parts

    return {
        "signal": ta["overall_signal"],
        "confidence": ta["confidence"],
        "summary": f"{name} shows {ta['trend'].replace('_', ' ')} with {buy_count} bullish and {sell_count} bearish signals.",
        "reasoning": " | ".join(all_reasoning[:6]) if all_reasoning else "Insufficient data for detailed analysis.",
        "entry_price": price,
        "stop_loss": ta["stop_loss"],
        "target1": ta["target1"],
        "target2": ta["target2"],
        "risk_reward": ta["risk_reward"],
        "timeframe": "swing",
        "key_levels": {
            "strong_resistance": ta["support_resistance"].get("resistance", [price * 1.02])[0] if ta["support_resistance"].get("resistance") else round(price * 1.02, 2),
            "strong_support": ta["support_resistance"].get("support", [price * 0.98])[-1] if ta["support_resistance"].get("support") else round(price * 0.98, 2),
        },
        "risks": [
            "Market-wide selloff could invalidate setup",
            "Low volume may reduce signal reliability",
            "News/events can override technical levels",
        ],
        "market_context": "Analysis based on technical indicators only. No LLM provider configured.",
        "sentiment": "bullish" if ta["overall_signal"] == "BUY" else "bearish" if ta["overall_signal"] == "SELL" else "neutral",
        "source": "rule_based",
        "symbol": symbol,
    }
