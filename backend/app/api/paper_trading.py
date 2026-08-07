"""Paper Trading Engine — virtual portfolios, trade execution, P&L, AI vs User vs Benchmark."""
from __future__ import annotations
import json
import os
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

# ── Constants ─────────────────────────────────────────────────
BROKERAGE_PCT   = 0.0003
STT_PCT         = 0.001
STT_INTRADAY    = 0.00025
EXCHANGE_TXN    = 0.0000345
SEBI_CHARGES    = 0.000001
GST_PCT         = 0.18
STAMP_DUTY      = 0.00015
MAX_TRADES_HISTORY = 500

# ── Persistence path ──────────────────────────────────────────
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "jarvis_paper_trading.json")
_DB_PATH = os.path.abspath(_DB_PATH)


def _save_to_disk():
    """Persist all portfolios to JSON file."""
    try:
        data = {}
        for pid, p in _portfolios.items():
            pd = p.to_dict()
            pd["trades"] = [t.to_dict() for t in p.trades]
            pd["daily_snapshots"] = p.daily_snapshots
            pd["_realised_pnl"] = p._realised_pnl
            pd["initial_balance"] = p.initial_balance
            pd["cash"] = p.cash
            # Store full position data including opened_at
            pd["positions"] = {k: v.to_dict() for k, v in p.positions.items()}
            data[pid] = pd
        with open(_DB_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[JARVIS] Portfolio save error: {e}")


def _load_from_disk():
    """Load portfolios from JSON file on startup."""
    if not os.path.exists(_DB_PATH):
        return
    try:
        with open(_DB_PATH, "r") as f:
            data = json.load(f)
        for pid, pd in data.items():
            p = Portfolio(
                id=pd["id"],
                name=pd["name"],
                owner=pd["owner"],
                initial_balance=pd["initial_balance"],
                cash=pd["cash"],
                created_at=pd["created_at"],
            )
            p._realised_pnl = pd.get("_realised_pnl", 0.0)
            p.daily_snapshots = pd.get("daily_snapshots", [])
            # Restore positions
            for sym, pos_d in pd.get("positions", {}).items():
                p.positions[sym] = Position(
                    symbol=pos_d["symbol"],
                    qty=pos_d["qty"],
                    avg_price=pos_d["avg_price"],
                    trade_mode=pos_d["trade_mode"],
                    source=pos_d["source"],
                    opened_at=pos_d["opened_at"],
                    current_price=pos_d.get("current_price", pos_d["avg_price"]),
                    unrealised_pnl=pos_d.get("unrealised_pnl", 0.0),
                    charges_paid=pos_d.get("charges_paid", 0.0),
                )
            # Restore trades
            for t_d in pd.get("trades", []):
                p.trades.append(Trade(
                    id=t_d["id"],
                    portfolio_id=t_d["portfolio_id"],
                    symbol=t_d["symbol"],
                    trade_type=t_d["trade_type"],
                    qty=t_d["qty"],
                    price=t_d["price"],
                    timestamp=t_d["timestamp"],
                    trade_mode=t_d["trade_mode"],
                    source=t_d["source"],
                    ai_signal=t_d.get("ai_signal"),
                    ai_confidence=t_d.get("ai_confidence"),
                    notes=t_d.get("notes", ""),
                    pnl=t_d.get("pnl"),
                    exit_price=t_d.get("exit_price"),
                    exit_time=t_d.get("exit_time"),
                    charges=t_d.get("charges", 0.0),
                ))
            _portfolios[pid] = p
        print(f"[JARVIS] Loaded {len(_portfolios)} portfolio(s) from disk.")
    except Exception as e:
        print(f"[JARVIS] Portfolio load error: {e}")

# ── Data Models ───────────────────────────────────────────────

@dataclass
class Trade:
    id: str
    portfolio_id: str
    symbol: str
    trade_type: str          # "BUY" | "SELL"
    qty: int
    price: float
    timestamp: float
    trade_mode: str          # "intraday" | "delivery"
    source: str              # "user" | "ai"
    ai_signal: Optional[str] = None
    ai_confidence: Optional[float] = None
    notes: str = ""
    # Computed after close
    pnl: Optional[float] = None
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    charges: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Position:
    symbol: str
    qty: int
    avg_price: float
    trade_mode: str
    source: str
    opened_at: float
    current_price: float = 0.0
    unrealised_pnl: float = 0.0
    charges_paid: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Portfolio:
    id: str
    name: str
    owner: str               # "user" | "ai" | "benchmark"
    initial_balance: float
    cash: float
    created_at: float
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    daily_snapshots: List[Dict] = field(default_factory=list)

    # Performance cache
    _total_value: float = 0.0
    _realised_pnl: float = 0.0

    def total_value(self) -> float:
        invested = sum(p.avg_price * p.qty for p in self.positions.values())
        unrealised = sum(p.unrealised_pnl for p in self.positions.values())
        return round(self.cash + invested + unrealised, 2)

    def total_return_pct(self) -> float:
        tv = self.total_value()
        if self.initial_balance == 0:
            return 0.0
        return round((tv - self.initial_balance) / self.initial_balance * 100, 2)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "initial_balance": self.initial_balance,
            "cash": round(self.cash, 2),
            "total_value": self.total_value(),
            "total_return_pct": self.total_return_pct(),
            "realised_pnl": round(self._realised_pnl, 2),
            "unrealised_pnl": round(sum(p.unrealised_pnl for p in self.positions.values()), 2),
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "trade_count": len(self.trades),
            "created_at": self.created_at,
        }


# ── In-memory store ───────────────────────────────────────────
_portfolios: Dict[str, Portfolio] = {}
_ai_predictions: List[Dict] = []

# Load persisted portfolios on module import
_load_from_disk()


# ── Brokerage Calculator ──────────────────────────────────────

def calculate_charges(price: float, qty: int, trade_type: str, trade_mode: str) -> float:
    """Calculate realistic Indian market transaction charges."""
    value = price * qty
    brokerage = min(BROKERAGE_PCT * value, 20.0)  # max ₹20 per order
    exchange   = EXCHANGE_TXN * value
    sebi       = SEBI_CHARGES * value
    gst        = GST_PCT * (brokerage + exchange)
    stamp      = STAMP_DUTY * value if trade_type == "BUY" else 0.0
    # STT rules (NSE): delivery = 0.1% on both BUY and SELL; intraday = 0.025% on SELL only
    if trade_mode == "intraday":
        stt = STT_INTRADAY * value if trade_type == "SELL" else 0.0
    else:
        stt = STT_PCT * value  # delivery: applies on both sides
    return round(brokerage + exchange + sebi + gst + stamp + stt, 2)


# ── Portfolio Management ──────────────────────────────────────

def create_portfolio(name: str, balance: float, owner: str = "user") -> Portfolio:
    pid = str(uuid.uuid4())[:8]
    p = Portfolio(
        id=pid, name=name, owner=owner,
        initial_balance=balance, cash=balance, created_at=time.time(),
    )
    _portfolios[pid] = p
    _save_to_disk()
    return p


def get_portfolio(pid: str) -> Optional[Portfolio]:
    return _portfolios.get(pid)


def list_portfolios() -> List[Dict]:
    return [p.to_dict() for p in _portfolios.values()]


def delete_portfolio(pid: str) -> bool:
    if pid in _portfolios:
        del _portfolios[pid]
        _save_to_disk()
        return True
    return False


# ── Trade Execution ───────────────────────────────────────────

async def execute_trade(
    portfolio_id: str,
    symbol: str,
    trade_type: str,
    qty: int,
    trade_mode: str = "delivery",
    source: str = "user",
    ai_signal: Optional[str] = None,
    ai_confidence: Optional[float] = None,
    notes: str = "",
    price_override: Optional[float] = None,
) -> Dict:
    """Execute a paper trade at live market price."""
    p = _portfolios.get(portfolio_id)
    if not p:
        return {"error": "portfolio_not_found"}
    if qty <= 0:
        return {"error": "invalid_qty"}

    # Fetch live price
    if price_override is not None:
        price = price_override
    else:
        price = await _get_live_price(symbol)
        if price is None:
            return {"error": "price_fetch_failed", "symbol": symbol}

    charges = calculate_charges(price, qty, trade_type, trade_mode)
    total_cost = price * qty + (charges if trade_type == "BUY" else 0)
    total_proceeds = price * qty - (charges if trade_type == "SELL" else 0)

    sym_key = symbol.replace(".NS", "").replace(".BO", "")

    if trade_type == "BUY":
        if p.cash < total_cost:
            return {"error": "insufficient_funds", "required": total_cost, "available": p.cash}
        p.cash -= total_cost
        if sym_key in p.positions:
            pos = p.positions[sym_key]
            total_qty = pos.qty + qty
            pos.avg_price = round((pos.avg_price * pos.qty + price * qty) / total_qty, 2)
            pos.qty = total_qty
            pos.charges_paid += charges
        else:
            p.positions[sym_key] = Position(
                symbol=sym_key,
                qty=qty,
                avg_price=price,
                trade_mode=trade_mode,
                source=source,
                opened_at=time.time(),
                current_price=price,
                charges_paid=charges,
            )

    elif trade_type == "SELL":
        if sym_key not in p.positions:
            return {"error": "no_position", "symbol": sym_key}
        pos = p.positions[sym_key]
        if pos.qty < qty:
            return {"error": "insufficient_qty", "held": pos.qty, "requested": qty}

        # Calculate realised P&L
        buy_cost  = pos.avg_price * qty
        sell_proc = total_proceeds
        realised  = round(sell_proc - buy_cost - pos.charges_paid * (qty / pos.qty), 2)
        p._realised_pnl += realised
        p.cash += total_proceeds

        pos.qty -= qty
        if pos.qty == 0:
            del p.positions[sym_key]
        else:
            pos.charges_paid *= (pos.qty / (pos.qty + qty))

        # Update last trade with P&L
        for t in reversed(p.trades):
            if t.symbol == sym_key and t.trade_type == "BUY" and t.pnl is None:
                t.pnl = realised
                t.exit_price = price
                t.exit_time = time.time()
                break
    else:
        return {"error": "invalid_trade_type"}

    trade = Trade(
        id=str(uuid.uuid4())[:8],
        portfolio_id=portfolio_id,
        symbol=sym_key,
        trade_type=trade_type,
        qty=qty,
        price=price,
        timestamp=time.time(),
        trade_mode=trade_mode,
        source=source,
        ai_signal=ai_signal,
        ai_confidence=ai_confidence,
        notes=notes,
        charges=charges,
    )
    p.trades.append(trade)
    if len(p.trades) > MAX_TRADES_HISTORY:
        p.trades = p.trades[-MAX_TRADES_HISTORY:]

    # Snapshot daily value and persist
    _snapshot_portfolio(p)
    _save_to_disk()

    return {
        "status": "executed",
        "trade": trade.to_dict(),
        "portfolio": p.to_dict(),
    }


def _snapshot_portfolio(p: Portfolio):
    """Record daily portfolio value snapshot."""
    today = time.strftime("%Y-%m-%d")
    snap = {"date": today, "value": p.total_value(), "cash": p.cash, "ts": time.time()}
    if p.daily_snapshots and p.daily_snapshots[-1]["date"] == today:
        p.daily_snapshots[-1] = snap
    else:
        p.daily_snapshots.append(snap)
        if len(p.daily_snapshots) > 365:
            p.daily_snapshots = p.daily_snapshots[-365:]


async def update_positions(portfolio_id: str) -> Dict:
    """Refresh unrealised P&L for all open positions with live prices."""
    p = _portfolios.get(portfolio_id)
    if not p:
        return {"error": "portfolio_not_found"}
    for sym, pos in p.positions.items():
        price = await _get_live_price(sym)
        if price:
            pos.current_price = price
            pos.unrealised_pnl = round((price - pos.avg_price) * pos.qty, 2)
    return p.to_dict()


# ── Performance Analytics ─────────────────────────────────────

def get_performance_stats(portfolio_id: str) -> Dict:
    """Compute full performance statistics for a portfolio."""
    p = _portfolios.get(portfolio_id)
    if not p:
        return {"error": "portfolio_not_found"}

    trades = p.trades
    closed = [t for t in trades if t.pnl is not None]
    wins   = [t for t in closed if (t.pnl or 0) > 0]
    losses = [t for t in closed if (t.pnl or 0) < 0]

    win_rate   = round(len(wins) / len(closed) * 100, 1) if closed else 0.0
    avg_profit = round(sum(t.pnl for t in wins) / len(wins), 2) if wins else 0.0
    avg_loss   = round(sum(t.pnl for t in losses) / len(losses), 2) if losses else 0.0
    profit_factor = round(abs(sum(t.pnl for t in wins)) / abs(sum(t.pnl for t in losses)), 2) if losses and wins else 0.0

    # Equity curve from snapshots
    values = [s["value"] for s in p.daily_snapshots]
    max_dd = _max_drawdown(values)
    sharpe = _sharpe_ratio(values)
    volatility = _volatility(values)

    # AI prediction accuracy
    ai_trades = [t for t in closed if t.source == "ai"]
    ai_correct = [t for t in ai_trades if (
        (t.ai_signal == "BUY"  and (t.pnl or 0) > 0) or
        (t.ai_signal == "SELL" and (t.pnl or 0) > 0)
    )]
    ai_accuracy = round(len(ai_correct) / len(ai_trades) * 100, 1) if ai_trades else 0.0

    return {
        "portfolio_id": portfolio_id,
        "total_trades": len(trades),
        "closed_trades": len(closed),
        "open_positions": len(p.positions),
        "win_rate": win_rate,
        "loss_rate": round(100 - win_rate, 1),
        "avg_profit": avg_profit,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "total_realised_pnl": round(p._realised_pnl, 2),
        "total_return_pct": p.total_return_pct(),
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe,
        "volatility_pct": volatility,
        "ai_accuracy": ai_accuracy,
        "ai_trades": len(ai_trades),
        "equity_curve": [{"date": s["date"], "value": s["value"]} for s in p.daily_snapshots],
        "initial_balance": p.initial_balance,
        "current_value": p.total_value(),
    }


def compare_portfolios(portfolio_ids: List[str]) -> Dict:
    """Side-by-side comparison of multiple portfolios."""
    result = []
    for pid in portfolio_ids:
        stats = get_performance_stats(pid)
        if "error" not in stats:
            p = _portfolios[pid]
            result.append({
                "id": pid,
                "name": p.name,
                "owner": p.owner,
                **stats,
            })
    return {"comparison": result}


# ── AI Trade Execution (auto-trade based on analysis) ─────────

# Pending trade confirmations store: {confirmation_id: trade_payload}
_pending_trade_confirmations: dict = {}


async def ai_auto_trade(portfolio_id: str, symbol: str, budget_per_trade: float = 10000) -> dict:
    """Analyse the stock and return a trade proposal requiring manual confirmation.
    Does NOT execute — returns a confirmation_id that must be approved via confirm_ai_trade().
    """
    from app.market_data.service import fetch_candles
    from app.api.technical_analysis import compute_technical_analysis

    full_sym = symbol if "." in symbol else f"{symbol}.NS"
    chart = await fetch_candles(full_sym, interval="15m", days=5)
    if chart.get("error") or len(chart.get("candles", [])) < 26:
        return {"error": "insufficient_data"}

    candles = chart["candles"]
    ta = compute_technical_analysis(candles)
    if ta.get("error"):
        return {"error": ta["error"]}

    signal = ta["overall_signal"]
    price  = ta["current_price"]
    confidence = ta["confidence"]

    if signal == "HOLD" or confidence < 55:
        return {"status": "no_trade", "reason": f"Signal {signal} with {confidence}% confidence — no trade warranted, Sir."}

    qty = max(1, int(budget_per_trade / price))
    trade_type = "BUY" if signal == "BUY" else "SELL"

    p = _portfolios.get(portfolio_id)
    sym_key = symbol.replace(".NS", "")
    if trade_type == "SELL" and sym_key not in (p.positions if p else {}):
        return {"status": "no_trade", "reason": "SELL signal detected but no open position exists, Sir."}

    # Build confirmation payload — do NOT execute yet
    import uuid
    confirmation_id = str(uuid.uuid4())[:12]
    estimated_cost = round(price * qty + calculate_charges(price, qty, trade_type, "intraday"), 2)

    payload = {
        "confirmation_id": confirmation_id,
        "portfolio_id": portfolio_id,
        "symbol": sym_key,
        "trade_type": trade_type,
        "qty": qty,
        "price": price,
        "estimated_cost": estimated_cost,
        "signal": signal,
        "confidence": confidence,
        "trend": ta["trend"],
        "stop_loss": ta["stop_loss"],
        "target1": ta["target1"],
        "target2": ta["target2"],
        "risk_reward": ta["risk_reward"],
        "score": ta["score"],
        "budget_per_trade": budget_per_trade,
    }
    _pending_trade_confirmations[confirmation_id] = payload

    return {
        "status": "awaiting_confirmation",
        "message": f"JARVIS has analysed {sym_key}. Awaiting your confirmation, Sir.",
        "proposal": payload,
    }


async def confirm_ai_trade(confirmation_id: str, approved: bool) -> dict:
    """Execute or cancel a pending AI trade proposal."""
    payload = _pending_trade_confirmations.pop(confirmation_id, None)
    if not payload:
        return {"error": "confirmation_not_found_or_expired"}

    if not approved:
        return {"status": "cancelled", "message": "Trade cancelled as instructed, Sir."}

    result = await execute_trade(
        portfolio_id=payload["portfolio_id"],
        symbol=payload["symbol"],
        trade_type=payload["trade_type"],
        qty=payload["qty"],
        trade_mode="intraday",
        source="ai",
        ai_signal=payload["signal"],
        ai_confidence=payload["confidence"],
        notes=f"Auto-trade confirmed: {payload['trend']} | Score: {payload['score']}",
    )

    _ai_predictions.append({
        "symbol": payload["symbol"],
        "signal": payload["signal"],
        "confidence": payload["confidence"],
        "price_at_signal": payload["price"],
        "target": payload["target1"],
        "stop_loss": payload["stop_loss"],
        "timestamp": time.time(),
        "outcome": None,
    })

    return {**result, "message": "Trade executed as confirmed, Sir."}


def get_ai_self_evaluation() -> Dict:
    """AI evaluates its own prediction accuracy."""
    total = len(_ai_predictions)
    if total == 0:
        return {"total_predictions": 0, "message": "No AI predictions recorded yet"}

    evaluated = [p for p in _ai_predictions if p.get("outcome") is not None]
    correct_dir = [p for p in evaluated if p["outcome"] == "correct"]
    target_hit  = [p for p in evaluated if p.get("target_hit")]
    sl_hit      = [p for p in evaluated if p.get("sl_hit")]

    return {
        "total_predictions": total,
        "evaluated": len(evaluated),
        "direction_accuracy": round(len(correct_dir) / len(evaluated) * 100, 1) if evaluated else 0,
        "target_hit_rate": round(len(target_hit) / len(evaluated) * 100, 1) if evaluated else 0,
        "stop_loss_hit_rate": round(len(sl_hit) / len(evaluated) * 100, 1) if evaluated else 0,
        "avg_confidence": round(sum(p["confidence"] for p in _ai_predictions) / total, 1),
        "recent_predictions": _ai_predictions[-10:][::-1],
    }


# ── Helpers ───────────────────────────────────────────────────

async def _get_live_price(symbol: str) -> Optional[float]:
    # Priority 1: Angel One real-time tick (0-delay) — only if feed is live
    try:
        from app.api.angel_feed import is_feed_available, get_feed
        if is_feed_available():
            tick = get_feed().latest_ticks.get(symbol)
            if tick and tick.get("price"):
                return float(tick["price"])
    except Exception:
        pass

    # Priority 2: Yahoo Finance fallback
    full = symbol if "." in symbol else f"{symbol}.NS"
    try:
        import httpx
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{full}?interval=1m&range=1d"
        async with httpx.AsyncClient(timeout=6) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            meta = r.json()["chart"]["result"][0]["meta"]
            return float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0)
    except Exception:
        return None


def _max_drawdown(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak else 0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


def _sharpe_ratio(values: List[float], risk_free: float = 0.065) -> float:
    if len(values) < 2:
        return 0.0
    returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
    if not returns:
        return 0.0
    import math
    avg_r = sum(returns) / len(returns)
    # Use sample std dev (N-1) — correct for Sharpe ratio calculation
    std_r = (sum((r - avg_r) ** 2 for r in returns) / max(len(returns) - 1, 1)) ** 0.5
    if std_r == 0:
        return 0.0
    daily_rf = risk_free / 252
    sharpe = (avg_r - daily_rf) / std_r * math.sqrt(252)
    return round(sharpe, 2)


def _volatility(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    import math
    returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
    if not returns:
        return 0.0
    avg = sum(returns) / len(returns)
    # Use sample std dev (N-1) — correct for annualised volatility
    std = (sum((r - avg) ** 2 for r in returns) / max(len(returns) - 1, 1)) ** 0.5
    return round(std * math.sqrt(252) * 100, 2)
