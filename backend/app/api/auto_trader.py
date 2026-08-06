"""
JARVIS Auto-Trader v3 — autonomous paper-trade test engine.

Key fixes vs v2:
  - FLAT forecast no longer blocks strong TA BUY signals
  - min_positions is a TARGET not a hard block — trade whatever qualifies
  - Conflict guard runs AFTER FLAT relaxation
  - 60s poll, 15m max hold, price ≤ ₹500
  - Force-kill stuck sessions
  - Auto-patch thresholds after each run
"""
from __future__ import annotations
import asyncio
import time
import traceback
from typing import Dict, List, Optional, Any

# ── Session state ─────────────────────────────────────────────
_session: Dict[str, Any] = {
    "running": False,
    "portfolio_id": None,
    "started_at": None,
    "finished_at": None,
    "trades": [],
    "log": [],
    "summary": None,
    "error": None,
    "patches_applied": [],
    "iteration": 0,
}

# ── Tunable thresholds ────────────────────────────────────────
_cfg: Dict[str, Any] = {
    "max_price":               1500.0,  # ₹1500 cap
    "min_ta_score":              2.5,   # TA score gate
    "min_risk_reward":           1.5,   # RR ≥1.5 — reward must be 1.5x the risk
    "min_fc_confidence":        48.0,   # FC ≥48%
    "fc_required":             False,
    "min_volume_ratio":          1.3,
    "max_rsi":                  70.0,   # tighter RSI — avoid overbought entries
    "min_rsi":                  35.0,   # avoid falling knives
    "max_hold_minutes":         30,     # 30m max — cut losers faster
    "poll_seconds":             20,
    "budget_per_trade":      10000.0,   # ₹10k — more qty = charges are smaller % of trade
    "target_positions":          3,
    "max_positions":             4,     # fewer but higher quality
    "scan_universe":        "nifty50",
    "top_n_candidates":         15,
    "combined_score_min":        4.5,
}

PATCH_HISTORY: List[Dict] = []

# ── Loop state (autonomous self-healing loop) ─────────────────
_loop: Dict[str, Any] = {
    "running":    False,
    "iteration":  0,
    "history":    [],   # one entry per completed session
    "stop_flag":  False,
    "log":        [],
}

SUCCESS_WIN_RATE   = 80.0   # target win rate % to declare success
SUCCESS_WINDOW     = 3      # must hit target over last N sessions
MAX_LOOP_ITERS     = 20     # hard cap — never run more than 20 sessions
COOLDOWN_SECS      = 30     # wait between sessions (let market breathe)


# ── Logging ───────────────────────────────────────────────────

def _log(msg: str, level: str = "INFO"):
    entry = {"ts": time.strftime("%H:%M:%S"), "level": level, "msg": msg}
    _session["log"].append(entry)
    print(f"[AT {entry['ts']}] [{level}] {msg}")


def force_reset():
    global _session
    _session = {
        "running": False, "portfolio_id": None,
        "started_at": None, "finished_at": None,
        "trades": [], "log": [], "summary": None,
        "error": None, "patches_applied": [], "iteration": 0,
    }


# ── Step 1: Scan ──────────────────────────────────────────────

async def _scan_candidates() -> List[Dict]:
    from app.api.stock_fetcher import get_all_stocks
    from app.market_data.service import fetch_candles
    from app.api.technical_analysis import compute_technical_analysis
    from app.api.forecaster import forecast

    _log(f"Scanning '{_cfg['scan_universe']}' for stocks ≤ ₹{_cfg['max_price']} …")

    all_data = await get_all_stocks(_cfg["scan_universe"])
    stocks   = all_data.get("stocks", [])
    if not stocks:
        raise RuntimeError("No stocks returned from universe")

    # Pre-filter by price
    affordable = [
        s for s in stocks
        if 0 < (s.get("price") or s.get("ltp") or 9999) <= _cfg["max_price"]
    ]
    _log(f"  {len(affordable)} stocks ≤ ₹{_cfg['max_price']} out of {len(stocks)}")

    # If still too few, pull midcap too
    if len(affordable) < 10:
        _log("  Adding midcap universe …", "WARN")
        mid = await get_all_stocks("midcap")
        extra = [
            s for s in mid.get("stocks", [])
            if 0 < (s.get("price") or s.get("ltp") or 9999) <= _cfg["max_price"]
        ]
        affordable = list({s["symbol"]: s for s in affordable + extra}.values())
        _log(f"  After merge: {len(affordable)} affordable stocks")

    candidates = []

    async def _analyse(stock: Dict):
        sym      = stock["symbol"]
        full_sym = sym if "." in sym else f"{sym}.NS"
        try:
            chart   = await fetch_candles(full_sym, interval="5m", days=2)
            candles = chart.get("candles", [])
            if len(candles) < 26:
                return

            ta    = compute_technical_analysis(candles)
            if ta.get("error"):
                return

            price     = ta["current_price"]
            ta_signal = ta["overall_signal"]
            ta_score  = ta["score"]
            rr        = ta["risk_reward"]

            # Hard gates
            if price <= 0 or price > _cfg["max_price"]:
                return
            if ta_signal != "BUY":          # long-only
                return
            if ta_score < _cfg["min_ta_score"]:
                return
            if rr < _cfg["min_risk_reward"]:
                return

            # Volume filter — must be above average to confirm move
            vol_ratio = ta["indicators"].get("volume_ratio") or 1.0
            if vol_ratio < _cfg["min_volume_ratio"]:
                return

            # RSI bounds — reject deeply oversold (falling knife) and overbought
            rsi   = ta["indicators"].get("rsi") or 50
            bb_u  = ta["indicators"].get("bb_upper") or price * 1.05
            if rsi > _cfg["max_rsi"] or rsi < _cfg["min_rsi"]:
                return
            if price >= bb_u:
                return

            # XGBoost forecast — UP boosts score, FLAT/DOWN penalises but doesn't hard-block
            fc        = await forecast(sym, horizon=15)
            pred      = fc.get("forecast", {}) if not fc.get("error") else {}
            direction = pred.get("direction", "FLAT")
            fc_conf   = pred.get("confidence", 0.0)

            # Hard-block only if FC=DOWN with high confidence
            if direction == "DOWN" and fc_conf >= 65.0:
                return

            # Score: UP boosts, FLAT neutral, DOWN penalises
            if direction == "UP":
                fc_boost  = fc_conf          # full confidence as boost
            elif direction == "FLAT":
                fc_boost  = fc_conf * 0.4    # partial credit
            else:  # DOWN
                fc_boost  = -fc_conf * 0.3   # mild penalty

            # TA is 70% weight, FC is 30% — TA drives the decision
            combined = round(ta_score * 0.7 + fc_boost * 0.3, 2)
            if combined < _cfg["combined_score_min"]:
                return

            used_conf = fc_conf if direction == "UP" else fc_conf * 0.5

            atr = ta["indicators"].get("atr") or price * 0.01
            # Smarter SL: use the deeper of ATR-based SL or nearest support
            atr_sl      = round(price - 1.5 * atr, 2)
            supports    = ta.get("support_resistance", {}).get("support", [])
            near_sup    = max((s for s in supports if s < price), default=None)
            smart_sl    = round(min(atr_sl, near_sup) if near_sup else atr_sl, 2)

            candidates.append({
                "symbol":         sym,
                "full_sym":       full_sym,
                "price":          price,
                "ta_score":       round(ta_score, 2),
                "ta_confidence":  ta["confidence"],
                "fc_direction":   direction,
                "fc_confidence":  fc_conf,
                "used_conf":      used_conf,
                "combined_score": combined,
                "stop_loss":      smart_sl,
                "target":         ta["target1"],
                "risk_reward":    rr,
                "atr":            atr,
                "vol_ratio":      round(vol_ratio, 2),
                "rsi":            round(rsi, 1),
            })
            _log(
                f"  ✓ {sym} ₹{price:.0f} | TA={ta_score:.1f} RSI={rsi:.0f} "
                f"Vol={vol_ratio:.1f}x FC={direction}({fc_conf:.0f}%) "
                f"combined={combined:.1f} R:R={rr} SL=₹{smart_sl} T=₹{ta['target1']}"
            )

        except Exception as e:
            _log(f"  {sym}: {e}", "WARN")

    # Batch 15 at a time
    for i in range(0, min(len(affordable), 90), 15):
        chunk = affordable[i:i + 15]
        await asyncio.gather(*[_analyse(s) for s in chunk], return_exceptions=True)
        await asyncio.sleep(0.3)
        if len(candidates) >= _cfg["top_n_candidates"]:
            break

    candidates.sort(key=lambda x: x["combined_score"], reverse=True)
    top = candidates[:_cfg["max_positions"]]
    _log(f"Qualified: {len(candidates)} → top {len(top)} selected")
    return top


# ── Step 2: Enter ─────────────────────────────────────────────

async def _enter_trades(pid: str, candidates: List[Dict]) -> List[Dict]:
    from app.api.paper_trading import execute_trade, get_portfolio

    p = get_portfolio(pid)
    if not p:
        raise RuntimeError(f"Portfolio {pid} not found")

    entered = []
    for c in candidates[:_cfg["max_positions"]]:
        sym   = c["symbol"]
        price = c["price"]
        qty   = max(1, int(_cfg["budget_per_trade"] / price))

        result = await execute_trade(
            portfolio_id=pid,
            symbol=sym,
            trade_type="BUY",
            qty=qty,
            trade_mode="intraday",
            source="ai",
            ai_signal="BUY",
            ai_confidence=c["used_conf"],
            notes=(
                f"AutoTest v3 | TA={c['ta_score']} "
                f"FC={c['fc_direction']}({c['fc_confidence']:.0f}%) "
                f"RR={c['risk_reward']}"
            ),
        )

        if result.get("error"):
            _log(f"  BUY {sym} FAILED: {result['error']}", "ERROR")
            continue

        buy_charges      = result["trade"]["charges"]
        # Need gross > buy_charges + estimated_sell_charges + min_net
        # sell charges ≈ buy charges, so threshold = 2.5x buy_charges + ₹5 min net
        profit_threshold = round(buy_charges * 2.5 + 5.0, 2)
        trail_sl         = c["stop_loss"]

        rec = {
            "symbol":           sym,
            "qty":              qty,
            "entry_price":      price,
            "entry_time":       time.time(),
            "stop_loss":        c["stop_loss"],
            "target":           c["target"],
            "atr":              c["atr"],
            "ta_score":         c["ta_score"],
            "fc_confidence":    c["fc_confidence"],
            "used_conf":        c["used_conf"],
            "risk_reward":      c["risk_reward"],
            "buy_charges":      buy_charges,
            "profit_threshold": profit_threshold,
            "trail_sl":         trail_sl,
            "trailing_active":  False,
            "exit_price":       None,
            "exit_time":        None,
            "exit_reason":      None,
            "gross_pnl":        None,
            "sell_charges":     None,
            "total_charges":    None,
            "net_pnl":          None,
            "status":           "open",
            "hold_minutes":     None,
        }
        entered.append(rec)
        _session["trades"].append(rec)
        _log(
            f"  ✅ BUY {sym} × {qty} @ ₹{price:.2f} | "
            f"SL=₹{c['stop_loss']} T=₹{c['target']} | "
            f"profit after charges needs > ₹{profit_threshold}"
        )

    return entered


# ── Step 3: Monitor ───────────────────────────────────────────

async def _monitor_and_exit(pid: str, open_trades: List[Dict]):
    from app.api.paper_trading import execute_trade, _get_live_price

    max_secs  = _cfg["max_hold_minutes"] * 60
    poll_secs = _cfg["poll_seconds"]

    _log(
        f"Monitoring {len(open_trades)} position(s) — "
        f"poll every {poll_secs}s, max hold {_cfg['max_hold_minutes']}m"
    )

    while any(t["status"] == "open" for t in open_trades):
        await asyncio.sleep(poll_secs)

        for trade in open_trades:
            if trade["status"] != "open":
                continue

            sym     = trade["symbol"]
            elapsed = time.time() - trade["entry_time"]
            price   = await _get_live_price(sym)

            if price is None:
                _log(f"  {sym}: price unavailable", "WARN")
                continue

            gross = round((price - trade["entry_price"]) * trade["qty"], 2)

            # Trailing SL: activate once gross > 0.5xATR (lower bar = protect profits sooner)
            atr = trade["atr"]
            if not trade["trailing_active"] and gross >= trade["qty"] * atr * 0.5:
                new_trail = round(trade["entry_price"] + 0.3 * atr, 2)
                if new_trail > trade["trail_sl"]:
                    trade["trail_sl"]        = new_trail
                    trade["trailing_active"] = True
                    _log(f"  LOCK {sym} trailing SL -> Rs.{new_trail} (breakeven+)")

            # Exit logic — check trail_sl instead of fixed stop_loss
            if price >= trade["target"]:
                reason = "TARGET_HIT"
            elif gross >= trade["profit_threshold"]:
                reason = "PROFIT"
            elif price <= trade["trail_sl"]:
                reason = "STOP_LOSS" if not trade["trailing_active"] else "TRAIL_SL"
            elif elapsed >= max_secs:
                reason = "TIMEOUT"
            else:
                _log(
                    f"  ⏳ {sym} @ ₹{price:.2f} | gross=₹{gross} "
                    f"SL=₹{trade['trail_sl']} | {elapsed/60:.1f}m"
                )
                continue

            sell = await execute_trade(
                portfolio_id=pid,
                symbol=sym,
                trade_type="SELL",
                qty=trade["qty"],
                trade_mode="intraday",
                source="ai",
                notes=f"AutoTest exit: {reason}",
            )

            if sell.get("error"):
                _log(f"  SELL {sym} ERROR: {sell['error']}", "ERROR")
                trade["status"] = "sell_failed"
                continue

            sell_ch   = sell["trade"]["charges"]
            total_ch  = round(trade["buy_charges"] + sell_ch, 2)
            net_pnl   = round(gross - total_ch, 2)

            trade.update({
                "exit_price":    price,
                "exit_time":     time.time(),
                "exit_reason":   reason,
                "gross_pnl":     gross,
                "sell_charges":  sell_ch,
                "total_charges": total_ch,
                "net_pnl":       net_pnl,
                "status":        "closed",
                "hold_minutes":  round(elapsed / 60, 1),
            })
            icon = "🟢" if net_pnl > 0 else "🔴"
            _log(
                f"  {icon} CLOSED {sym} @ ₹{price:.2f} | "
                f"{reason} | gross=₹{gross} charges=₹{total_ch} "
                f"NET=₹{net_pnl} ({trade['hold_minutes']}m)"
            )

    _log("All positions closed.")


# ── Step 4: Analyse + patch ───────────────────────────────────

def _analyse_and_patch(trades: List[Dict]) -> List[Dict]:
    patches = []
    closed  = [t for t in trades if t["status"] == "closed"]
    if not closed:
        return patches

    wins     = [t for t in closed if (t["net_pnl"] or 0) > 0]
    losses   = [t for t in closed if (t["net_pnl"] or 0) < 0]
    win_rate = len(wins) / len(closed) * 100

    _log(
        f"Analysis: {len(closed)} trades | "
        f"W={len(wins)} L={len(losses)} WR={win_rate:.0f}%"
    )

    def patch(rule, old, new, reason):
        _cfg[rule] = new
        p = {"rule": rule, "old": old, "new": new, "reason": reason}
        patches.append(p)
        PATCH_HISTORY.append(p)
        _log(f"  🔧 PATCH {rule}: {old} → {new} | {reason}", "PATCH")

    sl_hits = [t for t in losses if t.get("exit_reason") == "STOP_LOSS"]
    if len(sl_hits) > len(closed) * 0.5:
        patch("min_fc_confidence", _cfg["min_fc_confidence"],
              min(_cfg["min_fc_confidence"] + 5.0, 80.0),
              f"{len(sl_hits)} SL hits")

    low_ta = [t for t in losses if (t.get("ta_score") or 0) < _cfg["min_ta_score"] + 0.5]
    if len(low_ta) >= max(1, len(losses) * 0.6):
        patch("min_ta_score", _cfg["min_ta_score"],
              round(min(_cfg["min_ta_score"] + 0.5, 4.0), 1),
              f"{len(low_ta)} low-TA losses")

    timeout_losses = [t for t in losses if t.get("exit_reason") == "TIMEOUT"]
    if len(timeout_losses) >= 2:
        patch("max_hold_minutes", _cfg["max_hold_minutes"],
              max(_cfg["max_hold_minutes"] - 3, 5),
              f"{len(timeout_losses)} timeout losses")

    bad_rr = [t for t in losses if (t.get("risk_reward") or 0) < _cfg["min_risk_reward"] + 0.3]
    if len(bad_rr) >= max(1, len(losses) * 0.5):
        patch("min_risk_reward", _cfg["min_risk_reward"],
              round(min(_cfg["min_risk_reward"] + 0.2, 2.5), 1),
              f"{len(bad_rr)} poor-RR losses")

    if win_rate >= 70 and len(closed) >= 3:
        patch("min_fc_confidence", _cfg["min_fc_confidence"],
              max(_cfg["min_fc_confidence"] - 2.0, 45.0),
              f"WR={win_rate:.0f}% — loosen slightly")

    if not patches:
        _log("  ✅ No patches needed")

    return patches


# ── Step 5: Summary ───────────────────────────────────────────

def _build_summary(trades: List[Dict], pid: str) -> Dict:
    from app.api.paper_trading import get_performance_stats

    closed        = [t for t in trades if t["status"] == "closed"]
    wins          = [t for t in closed if (t["net_pnl"] or 0) > 0]
    losses        = [t for t in closed if (t["net_pnl"] or 0) < 0]
    total_gross   = round(sum(t.get("gross_pnl", 0) or 0 for t in closed), 2)
    total_charges = round(sum(t.get("total_charges", 0) or 0 for t in closed), 2)
    total_net     = round(sum(t.get("net_pnl", 0) or 0 for t in closed), 2)
    win_rate      = round(len(wins) / len(closed) * 100, 1) if closed else 0.0
    port          = get_performance_stats(pid) if pid else {}

    return {
        "session_date":  time.strftime("%Y-%m-%d"),
        "session_time":  time.strftime("%H:%M:%S"),
        "iteration":     _session["iteration"],
        "total_trades":  len(closed),
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate_pct":  win_rate,
        "gross_pnl":     total_gross,
        "total_charges": total_charges,
        "net_pnl":       total_net,
        "charge_breakdown": {
            "brokerage": round(total_charges * 0.35, 2),
            "stt":       round(total_charges * 0.40, 2),
            "gst":       round(total_charges * 0.15, 2),
            "other":     round(total_charges * 0.10, 2),
            "total":     total_charges,
        },
        "trades": [{
            "symbol":      t["symbol"],
            "qty":         t["qty"],
            "entry":       t["entry_price"],
            "exit":        t["exit_price"],
            "hold_min":    t.get("hold_minutes"),
            "exit_reason": t["exit_reason"],
            "gross_pnl":   t["gross_pnl"],
            "charges":     t["total_charges"],
            "net_pnl":     t["net_pnl"],
            "result":      "WIN" if (t["net_pnl"] or 0) > 0 else "LOSS",
            "ta_score":    t.get("ta_score"),
            "fc_conf":     t.get("fc_confidence"),
        } for t in closed],
        "patches_applied": _session.get("patches_applied", []),
        "thresholds_used": dict(_cfg),
        "portfolio_stats": {
            "total_return_pct": port.get("total_return_pct"),
            "win_rate":         port.get("win_rate"),
            "sharpe_ratio":     port.get("sharpe_ratio"),
            "max_drawdown_pct": port.get("max_drawdown_pct"),
            "ai_accuracy":      port.get("ai_accuracy"),
        },
        "verdict": (
            "✅ PROFITABLE" if total_net > 0
            else "⚠️  BREAKEVEN" if total_net == 0
            else "❌ LOSS"
        ),
    }


# ── Main ──────────────────────────────────────────────────────

async def run_autotest(portfolio_id: Optional[str] = None) -> Dict:
    global _session

    if _session["running"]:
        _log("Force-killing stuck session …", "WARN")
        force_reset()
        await asyncio.sleep(0.3)

    _session.update({
        "running":         True,
        "portfolio_id":    portfolio_id,
        "started_at":      time.time(),
        "finished_at":     None,
        "trades":          [],
        "log":             [],
        "summary":         None,
        "error":           None,
        "patches_applied": [],
        "iteration":       _session.get("iteration", 0) + 1,
    })

    try:
        from app.api.paper_trading import create_portfolio, get_portfolio

        if not portfolio_id:
            p   = create_portfolio(
                name=f"AutoTest-v3 {time.strftime('%d-%b %H:%M')}",
                balance=100000.0, owner="ai",
            )
            pid = p.id
            _session["portfolio_id"] = pid
            _log(f"Created portfolio '{p.name}' ₹1,00,000 → {pid}")
        else:
            p = get_portfolio(portfolio_id)
            if not p:
                raise RuntimeError(f"Portfolio {portfolio_id} not found")
            pid = portfolio_id
            _log(f"Using '{p.name}' | cash=₹{p.cash:,.0f} | iter #{_session['iteration']}")

        # ── Scan ──────────────────────────────────────────────
        candidates = await _scan_candidates()

        # If below target, loosen once and retry
        if len(candidates) < _cfg["target_positions"]:
            _log(
                f"Only {len(candidates)} found (target {_cfg['target_positions']}) "
                f"— loosening and retrying …", "WARN"
            )
            old_ta   = _cfg["min_ta_score"]
            old_conf = _cfg["min_fc_confidence"]
            _cfg["min_ta_score"]      = max(old_ta - 0.5, 1.0)
            _cfg["min_fc_confidence"] = max(old_conf - 5.0, 40.0)
            _log(f"  TA≥{_cfg['min_ta_score']} conf≥{_cfg['min_fc_confidence']}%", "PATCH")

            more = await _scan_candidates()
            # Merge, dedupe, re-sort
            seen = {c["symbol"] for c in candidates}
            candidates += [c for c in more if c["symbol"] not in seen]
            candidates.sort(key=lambda x: x["combined_score"], reverse=True)
            candidates = candidates[:_cfg["max_positions"]]
            _log(f"After retry: {len(candidates)} candidates")

        if len(candidates) == 0:
            _session["summary"] = {
                "verdict":    "⚠️  NO TRADES",
                "reason":     "0 stocks passed all filters",
                "suggestion": "Market is flat — best time is 9:30–11:30 AM IST",
                "thresholds": dict(_cfg),
            }
            _log("No candidates at all. Aborting.", "ERROR")
            return _session

        # ── Enter — trade whatever qualifies, no hard minimum ─
        open_trades = await _enter_trades(pid, candidates)

        if not open_trades:
            _log("All BUY orders failed — check funds/price errors", "ERROR")
            _session["error"] = "all_entries_failed"
            return _session

        _log(f"Entered {len(open_trades)} position(s) successfully")

        # ── Monitor ───────────────────────────────────────────
        await _monitor_and_exit(pid, open_trades)

        # ── Analyse + patch ───────────────────────────────────
        patches = _analyse_and_patch(_session["trades"])
        _session["patches_applied"] = patches

        # ── Summary ───────────────────────────────────────────
        summary = _build_summary(_session["trades"], pid)
        _session["summary"] = summary

        _log("=" * 52)
        _log(f"  {summary['verdict']}")
        _log(
            f"  Trades={summary['total_trades']} "
            f"W={summary['wins']} L={summary['losses']} "
            f"WR={summary['win_rate_pct']}%"
        )
        _log(f"  Gross   = ₹{summary['gross_pnl']}")
        _log(
            f"  Charges = ₹{summary['total_charges']} "
            f"(STT≈₹{summary['charge_breakdown']['stt']} "
            f"Brok≈₹{summary['charge_breakdown']['brokerage']} "
            f"GST≈₹{summary['charge_breakdown']['gst']})"
        )
        _log(f"  NET P&L = ₹{summary['net_pnl']}")
        _log(f"  Patches = {len(patches)}")
        _log("=" * 52)

    except Exception as e:
        _log(f"CRASH: {e}", "ERROR")
        _log(traceback.format_exc(), "ERROR")
        _session["error"] = str(e)
        if "fetch" in str(e).lower() or "scan" in str(e).lower():
            old = _cfg["top_n_candidates"]
            _cfg["top_n_candidates"] = max(old - 2, 3)
            PATCH_HISTORY.append({
                "rule": "top_n_candidates", "old": old,
                "new": _cfg["top_n_candidates"],
                "reason": f"Crash: {str(e)[:60]}",
            })
    finally:
        # FIX: force-close any orphaned open positions on crash/shutdown
        open_orphans = [t for t in _session["trades"] if t["status"] == "open"]
        if open_orphans:
            _log(f"Closing {len(open_orphans)} orphaned position(s) …", "WARN")
            from app.api.paper_trading import execute_trade as _et
            _pid = _session.get("portfolio_id")
            for t in open_orphans:
                try:
                    await _et(
                        portfolio_id=_pid, symbol=t["symbol"],
                        trade_type="SELL", qty=t["qty"],
                        trade_mode="intraday", source="ai",
                        notes="AutoTest exit: CRASH_CLEANUP",
                    )
                    t["status"]      = "closed"
                    t["exit_reason"] = "CRASH_CLEANUP"
                    _log(f"  ✅ Closed orphan {t['symbol']}")
                except Exception as ce:
                    _log(f"  ❌ Could not close {t['symbol']}: {ce}", "ERROR")
        _session["running"]     = False
        _session["finished_at"] = time.time()

    return _session


# ── Live cfg patch (called by /paper/autotest/patch route) ───────────

def apply_cfg_patch(updates: Dict) -> Dict:
    """Merge updates into _cfg. Only known keys accepted."""
    allowed = set(_cfg.keys())
    applied = {}
    for k, v in updates.items():
        if k in allowed:
            _cfg[k] = v
            applied[k] = v
    if applied:
        PATCH_HISTORY.append({"rule": "manual_patch", "values": applied, "ts": time.strftime("%H:%M:%S")})
    return {"applied": applied, "current_cfg": dict(_cfg)}


# ── Root-cause analyser ────────────────────────────────────────────

def _diagnose_and_patch(session_result: Dict) -> List[Dict]:
    """
    Analyse a completed session, identify root causes of losses,
    and mutate _cfg to fix them for the next iteration.
    Returns list of patches applied.
    """
    sm = session_result.get("summary") or {}
    trades = sm.get("trades", [])
    if not trades:
        return []

    wins    = [t for t in trades if (t.get("net_pnl") or 0) > 0]
    losses  = [t for t in trades if (t.get("net_pnl") or 0) <= 0]
    wr      = len(wins) / len(trades) * 100 if trades else 0
    patches = []

    def _patch(key, new_val, reason):
        old = _cfg.get(key)
        _cfg[key] = new_val
        p = {"rule": key, "old": old, "new": new_val, "reason": reason}
        patches.append(p)
        PATCH_HISTORY.append(p)
        _loop["log"].append({"ts": time.strftime("%H:%M:%S"), "msg": f"PATCH {key}: {old} -> {new_val} | {reason}"})

    # ── 1. Stop-loss too tight — stopped out fast, price recovered after
    sl_losses = [t for t in losses if t.get("exit_reason") in ("STOP_LOSS", "TRAIL_SL")]
    if len(sl_losses) >= max(1, len(losses) * 0.5):
        avg_hold = sum((t.get("hold_min") or 0) for t in sl_losses) / len(sl_losses)
        if avg_hold < 5:   # stopped out in < 5 min = SL too tight
            # Widen SL by reducing min_risk_reward (allows wider SL relative to target)
            new_rr = round(max(_cfg["min_risk_reward"] - 0.1, 0.8), 1)
            _patch("min_risk_reward", new_rr, f"{len(sl_losses)} SL hits avg {avg_hold:.1f}m in")
            # Also raise combined_score_min to only take high-conviction trades
            new_cs = round(min(_cfg["combined_score_min"] + 0.5, 7.0), 1)
            _patch("combined_score_min", new_cs, "raise bar to compensate wider SL")

    # ── 2. Timeout losses — no momentum, stock just sat there
    timeout_losses = [t for t in losses if t.get("exit_reason") == "TIMEOUT"]
    if len(timeout_losses) >= max(1, len(losses) * 0.4):
        # Require stronger volume confirmation
        new_vol = round(min(_cfg["min_volume_ratio"] + 0.2, 2.0), 1)
        _patch("min_volume_ratio", new_vol, f"{len(timeout_losses)} timeout losses — no momentum")
        # Raise TA score requirement
        new_ta = round(min(_cfg["min_ta_score"] + 0.5, 4.5), 1)
        _patch("min_ta_score", new_ta, "require stronger TA signal to avoid flat stocks")

    # ── 3. Weak FC — XGBoost was uncertain on losing trades
    weak_fc_losses = [t for t in losses if (t.get("fc_conf") or 0) < 50]
    if len(weak_fc_losses) >= max(1, len(losses) * 0.5):
        new_fc = round(min(_cfg["min_fc_confidence"] + 5.0, 75.0), 1)
        _patch("min_fc_confidence", new_fc, f"{len(weak_fc_losses)} losses had FC < 50%")

    # ── 4. Low TA score on losses
    low_ta_losses = [t for t in losses if (t.get("ta_score") or 0) < _cfg["min_ta_score"] + 0.5]
    if len(low_ta_losses) >= max(1, len(losses) * 0.6):
        new_ta = round(min(_cfg["min_ta_score"] + 0.5, 4.5), 1)
        if new_ta != _cfg["min_ta_score"]:  # avoid double-patch
            _patch("min_ta_score", new_ta, f"{len(low_ta_losses)} low-TA losses")

    # ── 5. Charges wiped profit — gross positive but net negative
    charge_wipeouts = [t for t in trades if (t.get("gross_pnl") or 0) > 0 and (t.get("net_pnl") or 0) <= 0]
    if len(charge_wipeouts) >= 2:
        new_budget = round(min(_cfg["budget_per_trade"] * 1.5, 20000.0), 0)
        _patch("budget_per_trade", new_budget, f"{len(charge_wipeouts)} charge wipeouts — bigger position size")

    # ── 6. Win rate good — loosen slightly to find more trades
    if wr >= SUCCESS_WIN_RATE and len(trades) >= 3:
        new_cs = round(max(_cfg["combined_score_min"] - 0.3, 2.5), 1)
        _patch("combined_score_min", new_cs, f"WR={wr:.0f}% — loosen to find more trades")
        new_fc = round(max(_cfg["min_fc_confidence"] - 3.0, 40.0), 1)
        _patch("min_fc_confidence", new_fc, "loosen FC threshold after good session")

    if not patches:
        _loop["log"].append({"ts": time.strftime("%H:%M:%S"), "msg": "No patches needed this iteration"})

    return patches


# ── Autonomous self-healing loop ────────────────────────────────────

async def run_autonomous_loop(portfolio_id: Optional[str] = None) -> None:
    """
    Full autonomous loop:
      1. Run autotest session
      2. Analyse P&L
      3. Diagnose losses → patch _cfg
      4. Repeat until win_rate >= 80% for 3 consecutive sessions
         OR max 20 iterations reached
    """
    global _loop
    _loop["running"]   = True
    _loop["stop_flag"] = False
    _loop["history"]   = []
    _loop["log"]       = []
    _loop["iteration"] = 0

    def _llog(msg):
        entry = {"ts": time.strftime("%H:%M:%S"), "msg": msg}
        _loop["log"].append(entry)
        print(f"[LOOP {entry['ts']}] {msg}")

    _llog("=" * 56)
    _llog("JARVIS AUTONOMOUS TRADING LOOP STARTED")
    _llog(f"Target: {SUCCESS_WIN_RATE}% win rate over {SUCCESS_WINDOW} consecutive sessions")
    _llog(f"Max iterations: {MAX_LOOP_ITERS}")
    _llog("=" * 56)

    consecutive_success = 0

    try:
        for iteration in range(1, MAX_LOOP_ITERS + 1):
            if _loop["stop_flag"]:
                _llog("Stop flag set — exiting loop.")
                break

            _loop["iteration"] = iteration
            _llog(f"--- ITERATION {iteration}/{MAX_LOOP_ITERS} ---")
            _llog(f"Config: TA>={_cfg['min_ta_score']} FC>={_cfg['min_fc_confidence']}% "
                  f"Vol>={_cfg['min_volume_ratio']}x RR>={_cfg['min_risk_reward']} "
                  f"combined>={_cfg['combined_score_min']}")

            # ── Run one full autotest session ───────────────────────────
            session = await run_autotest(portfolio_id)
            sm      = session.get("summary") or {}
            trades  = sm.get("trades", [])

            # ── Record history entry ──────────────────────────────────
            wins   = [t for t in trades if (t.get("net_pnl") or 0) > 0]
            losses = [t for t in trades if (t.get("net_pnl") or 0) <= 0]
            wr     = round(len(wins) / len(trades) * 100, 1) if trades else 0.0
            net    = sm.get("net_pnl", 0) or 0

            hist_entry = {
                "iteration":   iteration,
                "ts":          time.strftime("%H:%M:%S"),
                "total":       len(trades),
                "wins":        len(wins),
                "losses":      len(losses),
                "win_rate":    wr,
                "net_pnl":     net,
                "verdict":     sm.get("verdict", "NO_TRADES"),
                "patches":     [],
                "cfg_snapshot": dict(_cfg),
            }

            # ── Handle no-trade session ────────────────────────────────
            if not trades:
                _llog(f"Iter {iteration}: NO TRADES — loosening filters")
                # Loosen aggressively when no trades found
                _cfg["min_ta_score"]      = round(max(_cfg["min_ta_score"] - 0.5, 1.0), 1)
                _cfg["min_fc_confidence"] = round(max(_cfg["min_fc_confidence"] - 5.0, 35.0), 1)
                _cfg["min_volume_ratio"]  = round(max(_cfg["min_volume_ratio"] - 0.1, 0.5), 1)
                _cfg["combined_score_min"]= round(max(_cfg["combined_score_min"] - 0.5, 2.0), 1)
                hist_entry["patches"] = ["loosened_filters"]
                _loop["history"].append(hist_entry)
                _llog(f"  New: TA>={_cfg['min_ta_score']} FC>={_cfg['min_fc_confidence']}% "
                      f"combined>={_cfg['combined_score_min']}")
                await asyncio.sleep(COOLDOWN_SECS)
                continue

            # ── Log session result ─────────────────────────────────────
            _llog(f"Iter {iteration} RESULT: {sm.get('verdict','')} | "
                  f"{len(trades)} trades | W={len(wins)} L={len(losses)} "
                  f"WR={wr:.0f}% | NET=Rs.{net:.2f}")
            for t in trades:
                tag = "WIN " if (t.get("net_pnl") or 0) > 0 else "LOSS"
                _llog(f"  [{tag}] {t['symbol']} entry={t['entry']:.2f} exit={t.get('exit') or 0:.2f} "
                      f"hold={t.get('hold_min') or 0:.1f}m reason={t['exit_reason']} "
                      f"net=Rs.{t.get('net_pnl') or 0:.2f} TA={t.get('ta_score') or 0:.1f} "
                      f"FC={t.get('fc_conf') or 0:.0f}%")

            # ── Check success condition ─────────────────────────────────
            if wr >= SUCCESS_WIN_RATE and len(trades) >= 2:
                consecutive_success += 1
                _llog(f"SUCCESS streak: {consecutive_success}/{SUCCESS_WINDOW} "
                      f"(WR={wr:.0f}% >= {SUCCESS_WIN_RATE}%)")  
            else:
                if consecutive_success > 0:
                    _llog(f"Streak broken at {consecutive_success} — resetting")
                consecutive_success = 0

            # ── Diagnose + patch ──────────────────────────────────────
            patches = _diagnose_and_patch(session)
            hist_entry["patches"] = [{"rule": p["rule"], "old": p["old"], "new": p["new"]} for p in patches]
            _loop["history"].append(hist_entry)

            if patches:
                _llog(f"Applied {len(patches)} patch(es):")
                for p in patches:
                    _llog(f"  {p['rule']}: {p['old']} -> {p['new']} | {p['reason']}")
            else:
                _llog("No patches needed.")

            # ── Exit if success target reached ───────────────────────────
            if consecutive_success >= SUCCESS_WINDOW:
                _llog("=" * 56)
                _llog(f"TARGET ACHIEVED: {SUCCESS_WIN_RATE}% win rate for "
                      f"{SUCCESS_WINDOW} consecutive sessions!")
                _llog(f"Final config: {dict(_cfg)}")
                _llog("=" * 56)
                break

            # ── Cooldown before next session ───────────────────────────
            if iteration < MAX_LOOP_ITERS:
                _llog(f"Cooldown {COOLDOWN_SECS}s before next session...")
                await asyncio.sleep(COOLDOWN_SECS)

        else:
            _llog(f"Max iterations ({MAX_LOOP_ITERS}) reached.")

    except Exception as e:
        _llog(f"LOOP CRASH: {e}")
        import traceback as _tb
        _llog(_tb.format_exc())
    finally:
        _loop["running"] = False
        _llog("Loop finished.")


def get_loop_status() -> Dict:
    recent = _loop["history"][-5:] if _loop["history"] else []
    return {
        "running":       _loop["running"],
        "iteration":     _loop["iteration"],
        "stop_flag":     _loop["stop_flag"],
        "history":       recent,
        "log_tail":      _loop["log"][-50:],
        "current_cfg":   dict(_cfg),
        "patch_history": PATCH_HISTORY[-20:],
        "success_target": f"{SUCCESS_WIN_RATE}% WR x {SUCCESS_WINDOW} sessions",
    }


def stop_loop():
    _loop["stop_flag"] = True


def get_autotest_status() -> Dict:
    return {
        "running":       _session["running"],
        "portfolio_id":  _session["portfolio_id"],
        "started_at":    _session["started_at"],
        "finished_at":   _session["finished_at"],
        "iteration":     _session.get("iteration", 0),
        "trade_count":   len(_session["trades"]),
        "open_count":    sum(1 for t in _session["trades"] if t["status"] == "open"),
        "closed_count":  sum(1 for t in _session["trades"] if t["status"] == "closed"),
        "log_tail":      _session["log"][-40:],
        "summary":       _session["summary"],
        "error":         _session["error"],
        "current_cfg":   dict(_cfg),
        "patch_history": PATCH_HISTORY[-15:],
    }
