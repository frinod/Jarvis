"""
JARVIS Trade Tracker - live P&L monitor + post-session diagnosis + auto-patch.
Run: python track_trades.py
"""
import time, json, sys, os
import urllib.request

BASE = "http://localhost:8000/api"

GRN = "\033[92m"
RED = "\033[91m"
YLW = "\033[93m"
CYN = "\033[96m"
DIM = "\033[2m"
BLD = "\033[1m"
RST = "\033[0m"

def _get(path):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=6) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def _post(path, body={}):
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def clr():
    os.system("cls" if os.name == "nt" else "clear")

def col(val):
    if val is None: return f"{DIM}N/A{RST}"
    if val > 0:  return f"{GRN}{val:+.2f}{RST}"
    if val < 0:  return f"{RED}{val:+.2f}{RST}"
    return f"{DIM}{val:+.2f}{RST}"

# ── parse open positions from log tail ───────────────────────
def parse_open(log_tail):
    open_pos = {}
    for e in log_tail:
        msg = e["msg"]
        # open position line: "  [wait] SYMBOL @ Rs.price | gross=Rs.X SL=Rs.Y | Zm"
        if "gross=" in msg and "CLOSED" not in msg and "BUY" not in msg and "SELL" not in msg:
            try:
                # strip leading icons/spaces
                clean = msg.strip().lstrip("[wait]").lstrip("...").strip()
                sym_part, rest = clean.split("@", 1)
                sym   = sym_part.strip()
                price = float(rest.split("|")[0].replace("Rs.","").replace("Rs","").replace("\u20b9","").strip())
                gross = float(rest.split("gross=")[1].split()[0].replace("Rs.","").replace("Rs","").replace("\u20b9",""))
                sl    = float(rest.split("SL=")[1].split()[0].replace("Rs.","").replace("Rs","").replace("\u20b9",""))
                hold  = rest.split("|")[-1].strip()
                open_pos[sym] = {"price": price, "gross": gross, "sl": sl, "hold": hold, "trail": False}
            except Exception:
                pass
        # trailing SL update
        if "trailing SL moved" in msg:
            try:
                parts = msg.split()
                sym   = parts[1]
                new_sl = float([p for p in parts if p.startswith("Rs") or "\u20b9" in p][0]
                               .replace("Rs.","").replace("\u20b9","").rstrip(")"))
                if sym in open_pos:
                    open_pos[sym]["sl"]    = new_sl
                    open_pos[sym]["trail"] = True
            except Exception:
                pass
    return open_pos

# ── parse closed trades from log tail ────────────────────────
def parse_closed(log_tail):
    closed = []
    for e in log_tail:
        msg = e["msg"]
        if "CLOSED" in msg and "NET=" in msg:
            try:
                # "  [WIN/LOSS] CLOSED SYMBOL @ Rs.price | REASON | gross=Rs.X charges=Rs.Y NET=Rs.Z (Hm)"
                clean = msg.strip()
                # remove leading result tag
                for tag in ["[WIN]","[LOSS]","WIN","LOSS"]:
                    clean = clean.replace(tag,"").strip()
                clean = clean.replace("CLOSED","").strip()
                sym_part, rest = clean.split("@", 1)
                sym   = sym_part.strip()
                price = float(rest.split("|")[0].replace("\u20b9","").strip())
                reason = rest.split("|")[1].strip() if "|" in rest else "?"
                gross  = float(rest.split("gross=")[1].split()[0].replace("\u20b9","")) if "gross=" in rest else 0
                chg    = float(rest.split("charges=")[1].split()[0].replace("\u20b9","")) if "charges=" in rest else 0
                net    = float(rest.split("NET=")[1].split()[0].replace("\u20b9","")) if "NET=" in rest else 0
                hold   = rest.split("(")[-1].replace(")","").strip() if "(" in rest else "?"
                closed.append({"sym": sym, "price": price, "reason": reason,
                                "gross": gross, "charges": chg, "net": net, "hold": hold})
            except Exception:
                pass
    return closed

# ── live dashboard ────────────────────────────────────────────
def render(d):
    clr()
    cfg = d.get("current_cfg", {})
    print(f"{BLD}{CYN}{'='*64}")
    print(f"  JARVIS AUTO-TRADER  |  Iter #{d['iteration']}  |  {time.strftime('%H:%M:%S')}")
    print(f"{'='*64}{RST}")
    status_tag = f"{GRN}[RUNNING]{RST}" if d['running'] else f"{RED}[STOPPED]{RST}"
    print(f"  Portfolio : {d['portfolio_id']}   {status_tag}")
    print(f"  Open: {BLD}{d['open_count']}{RST}   Closed: {BLD}{d['closed_count']}{RST}   Total: {d['trade_count']}")
    print()

    open_pos = parse_open(d.get("log_tail", []))
    if open_pos:
        print(f"  {BLD}OPEN POSITIONS:{RST}")
        print(f"  {'SYMBOL':<12} {'PRICE':>8} {'GROSS P&L':>10} {'STOP LOSS':>10} {'HOLD':>7}  STATUS")
        print(f"  {'-'*62}")
        for sym, p in open_pos.items():
            trail = f"  {YLW}[TRAIL]{RST}" if p["trail"] else ""
            g = p["gross"]
            g_str = f"{GRN}{g:>+10.2f}{RST}" if g >= 0 else f"{RED}{g:>+10.2f}{RST}"
            print(f"  {CYN}{sym:<12}{RST} {p['price']:>8.2f} {g_str} {p['sl']:>10.2f} {p['hold']:>7}{trail}")
        print()

    closed = parse_closed(d.get("log_tail", []))
    if closed:
        print(f"  {BLD}CLOSED TRADES:{RST}")
        print(f"  {'SYMBOL':<12} {'EXIT':>8} {'REASON':<16} {'GROSS':>8} {'CHARGES':>8} {'NET':>8} {'HOLD':>7}")
        print(f"  {'-'*72}")
        for t in closed:
            n_str = f"{GRN}{t['net']:>+8.2f}{RST}" if t["net"] > 0 else f"{RED}{t['net']:>+8.2f}{RST}"
            print(f"  {CYN}{t['sym']:<12}{RST} {t['price']:>8.2f} {t['reason']:<16} "
                  f"{t['gross']:>+8.2f} {t['charges']:>8.2f} {n_str} {t['hold']:>7}")
        total_net = sum(t["net"] for t in closed)
        print(f"  {'-'*72}")
        lbl = f"{GRN}RUNNING NET P&L{RST}" if total_net >= 0 else f"{RED}RUNNING NET P&L{RST}"
        print(f"  {lbl:<30} {col(total_net):>8}")
        print()

    print(f"  {DIM}Config: price<=Rs{cfg.get('max_price')} | TA>={cfg.get('min_ta_score')} | "
          f"FC>={cfg.get('min_fc_confidence')}% | RR>={cfg.get('min_risk_reward')} | "
          f"RSI {cfg.get('min_rsi')}-{cfg.get('max_rsi')} | "
          f"Vol>={cfg.get('min_volume_ratio')}x | hold<={cfg.get('max_hold_minutes')}m{RST}")
    print()

# ── post-session diagnosis ────────────────────────────────────
def diagnose(sm, cfg):
    print(f"\n{BLD}{CYN}{'='*64}")
    print(f"  SESSION COMPLETE  --  DIAGNOSIS & LEARNING")
    print(f"{'='*64}{RST}\n")

    verdict = sm.get("verdict", "")
    net     = sm.get("net_pnl", 0) or 0
    gross   = sm.get("gross_pnl", 0) or 0
    charges = sm.get("total_charges", 0) or 0
    trades  = sm.get("trades", [])
    wins    = [t for t in trades if (t.get("net_pnl") or 0) > 0]
    losses  = [t for t in trades if (t.get("net_pnl") or 0) <= 0]
    wr      = sm.get("win_rate_pct", 0) or 0

    res_col = GRN if net > 0 else RED
    print(f"  RESULT     : {res_col}{BLD}{verdict}{RST}")
    print(f"  Gross P&L  : {col(gross)}")
    print(f"  Charges    : {RED}-Rs.{charges:.2f}{RST}")
    print(f"  NET P&L    : {col(net)}")
    print(f"  Win Rate   : {wr:.0f}%  ({len(wins)}W / {len(losses)}L)")
    print()

    # per-trade table
    if trades:
        print(f"  {BLD}TRADE BREAKDOWN:{RST}")
        print(f"  {'SYMBOL':<12} {'ENTRY':>8} {'EXIT':>8} {'HOLD':>6} {'REASON':<16} {'NET':>8} {'TA':>5} {'FC%':>5}")
        print(f"  {'-'*74}")
        for t in trades:
            n   = t.get("net_pnl") or 0
            n_s = f"{GRN}{n:>+8.2f}{RST}" if n > 0 else f"{RED}{n:>+8.2f}{RST}"
            ex  = t.get("exit") or 0
            hm  = t.get("hold_min") or 0
            ta  = t.get("ta_score") or 0
            fc  = t.get("fc_conf") or 0
            print(f"  {CYN}{t['symbol']:<12}{RST} {t['entry']:>8.2f} {ex:>8.2f} "
                  f"{hm:>5.1f}m {t['exit_reason']:<16} {n_s} {ta:>5.1f} {fc:>5.0f}%")
        print()

    # ── root cause analysis ───────────────────────────────────
    print(f"  {BLD}ROOT CAUSE ANALYSIS:{RST}")
    issues = []

    sl_losses = [t for t in losses if t.get("exit_reason") in ("STOP_LOSS", "TRAIL_SL")]
    if sl_losses:
        avg_hold = sum((t.get("hold_min") or 0) for t in sl_losses) / len(sl_losses)
        issues.append(("STOP_LOSS_TOO_TIGHT",
            f"{len(sl_losses)} trade(s) stopped out avg {avg_hold:.1f}m in. "
            f"1.5xATR SL is too tight for intraday noise on 5m chart. "
            f"Fix: raise SL multiplier to 2.0xATR."))

    timeout_losses = [t for t in losses if t.get("exit_reason") == "TIMEOUT"]
    if timeout_losses:
        issues.append(("NO_MOMENTUM",
            f"{len(timeout_losses)} trade(s) timed out. Stock had TA signal but no price momentum. "
            f"Fix: require volume_ratio >= 1.3 AND price > VWAP at entry."))

    low_ta_losses = [t for t in losses if (t.get("ta_score") or 0) < 2.5]
    if low_ta_losses:
        issues.append(("WEAK_TA",
            f"{len(low_ta_losses)} loss(es) had TA score < 2.5. Borderline signals lack conviction. "
            f"Fix: raise min_ta_score to 2.5."))

    flat_fc_losses = [t for t in losses if (t.get("fc_conf") or 0) < 50]
    if flat_fc_losses:
        issues.append(("FC_WEAK",
            f"{len(flat_fc_losses)} loss(es) had FC confidence < 50%. "
            f"XGBoost was uncertain. Fix: require FC >= 50% OR TA score >= 3.5."))

    if wr < 50 and len(trades) >= 3:
        issues.append(("LOW_WIN_RATE",
            f"Win rate {wr:.0f}% below 50%. Signals not selective enough. "
            f"Fix: raise combined_score_min from {cfg.get('combined_score_min',3.5)} to 4.5."))

    if gross > 0 and net < 0:
        issues.append(("CHARGE_WIPEOUT",
            f"Gross +Rs.{gross:.2f} but charges Rs.{charges:.2f} turned it negative. "
            f"Need gross >= 2.5x charges per trade. Fix: raise profit_threshold multiplier."))

    if not issues:
        print(f"  {GRN}[OK] No major issues. Strategy performing well.{RST}")
    else:
        for tag, desc in issues:
            print(f"  {YLW}[ISSUE] {tag}{RST}")
            # wrap desc at 60 chars
            words = desc.split()
            line  = "     "
            for w in words:
                if len(line) + len(w) > 65:
                    print(line)
                    line = "     " + w + " "
                else:
                    line += w + " "
            if line.strip():
                print(line)
            print()

    # ── patch recommendations ─────────────────────────────────
    print(f"  {BLD}PATCH RECOMMENDATIONS:{RST}")
    patches = []

    if any(i[0] == "STOP_LOSS_TOO_TIGHT" for i in issues):
        patches.append(("SL multiplier",
                         "1.5xATR -> 2.0xATR",
                         "auto_trader.py _analyse(): atr_sl = price - 2.0*atr"))
    if any(i[0] == "NO_MOMENTUM" for i in issues):
        old = cfg.get("min_volume_ratio", 0.8)
        new = round(min(old + 0.3, 1.5), 1)
        patches.append(("min_volume_ratio", f"{old} -> {new}", "require volume confirmation"))
    if any(i[0] == "WEAK_TA" for i in issues):
        old = cfg.get("min_ta_score", 2.0)
        new = round(min(old + 0.5, 4.0), 1)
        patches.append(("min_ta_score", f"{old} -> {new}", "filter weak TA signals"))
    if any(i[0] == "FC_WEAK" for i in issues):
        old = cfg.get("min_fc_confidence", 45)
        new = min(old + 5, 70)
        patches.append(("min_fc_confidence", f"{old} -> {new}", "require more FC conviction"))
    if any(i[0] == "LOW_WIN_RATE" for i in issues):
        old = cfg.get("combined_score_min", 3.5)
        new = round(min(old + 1.0, 6.0), 1)
        patches.append(("combined_score_min", f"{old} -> {new}", "raise combined score bar"))
    if any(i[0] == "CHARGE_WIPEOUT" for i in issues):
        patches.append(("profit_threshold",
                         "3x charges -> 4x charges",
                         "auto_trader.py _enter_trades(): buy_charges * 4 + 2.0"))

    if not patches:
        print(f"  {GRN}[OK] No patches needed.{RST}")
    else:
        for name, change, reason in patches:
            print(f"  {GRN}[PATCH] {name}: {change}{RST}")
            print(f"         Reason: {reason}")
        print()
        _apply_patches(issues, cfg)

    print(f"\n{DIM}  Run again to start a new session with patched config.{RST}\n")


def _apply_patches(issues, cfg):
    new_cfg = dict(cfg)
    applied = []

    for tag, _ in issues:
        if tag == "NO_MOMENTUM":
            new_cfg["min_volume_ratio"] = round(min(new_cfg.get("min_volume_ratio", 0.8) + 0.3, 1.5), 1)
            applied.append("min_volume_ratio")
        if tag == "WEAK_TA":
            new_cfg["min_ta_score"] = round(min(new_cfg.get("min_ta_score", 2.0) + 0.5, 4.0), 1)
            applied.append("min_ta_score")
        if tag == "FC_WEAK":
            new_cfg["min_fc_confidence"] = min(new_cfg.get("min_fc_confidence", 45) + 5, 70)
            applied.append("min_fc_confidence")
        if tag == "LOW_WIN_RATE":
            new_cfg["combined_score_min"] = round(min(new_cfg.get("combined_score_min", 3.5) + 1.0, 6.0), 1)
            applied.append("combined_score_min")

    patch_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autotest_patches.json")
    with open(patch_path, "w") as f:
        json.dump({
            "cfg": new_cfg,
            "applied": applied,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "issues": [i[0] for i in issues]
        }, f, indent=2)
    print(f"\n  {GRN}[SAVED] Patches written to autotest_patches.json{RST}")
    print(f"  {GRN}        Applied: {applied}{RST}")

    # also patch auto_trader._cfg directly via a small inline rewrite
    _patch_auto_trader_cfg(new_cfg)


def _patch_auto_trader_cfg(new_cfg):
    """Directly update _cfg values in auto_trader.py."""
    at_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "app", "api", "auto_trader.py")
    if not os.path.exists(at_path):
        return
    with open(at_path, "r", encoding="utf-8") as f:
        src = f.read()

    patch_map = {
        "min_ta_score":       new_cfg.get("min_ta_score"),
        "min_fc_confidence":  new_cfg.get("min_fc_confidence"),
        "min_volume_ratio":   new_cfg.get("min_volume_ratio"),
        "combined_score_min": new_cfg.get("combined_score_min"),
    }

    import re
    changed = []
    for key, val in patch_map.items():
        if val is None:
            continue
        # match:  "key":   <number>,
        pattern = rf'("{key}":\s*)([0-9.]+)'
        new_src, n = re.subn(pattern, lambda m: m.group(1) + str(val), src)
        if n:
            src = new_src
            changed.append(f"{key}={val}")

    if changed:
        with open(at_path, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"  {GRN}[PATCHED] auto_trader.py updated: {changed}{RST}")
        print(f"  {YLW}  Restart backend for changes to take effect.{RST}")


# ── main loop ─────────────────────────────────────────────────
def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"{CYN}JARVIS Trade Tracker starting...{RST}")
    last_closed = 0

    while True:
        d = _get("/paper/autotest/status")
        if d.get("error"):
            print(f"{RED}Backend unreachable: {d['error']}{RST}")
            time.sleep(5)
            continue

        render(d)

        if d["closed_count"] > last_closed:
            diff = d["closed_count"] - last_closed
            print(f"  {GRN}>> {diff} new trade(s) closed!{RST}")
            last_closed = d["closed_count"]

        # session finished with summary
        if not d["running"] and d.get("summary"):
            diagnose(d["summary"], d.get("current_cfg", {}))
            break

        # session ended with no trades
        if not d["running"] and not d.get("summary") and d.get("iteration", 0) > 0:
            print(f"  {YLW}Session ended -- no trades executed.{RST}")
            reason = d.get("error") or "No stocks passed all filters"
            print(f"  Reason: {reason}")
            break

        time.sleep(20)

    print(f"\n{CYN}Done. Run again to track next session.{RST}\n")


if __name__ == "__main__":
    if os.name == "nt":
        os.system("color")
    main()
