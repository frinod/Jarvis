"""Fundamental data — financials, shareholding, peers via Yahoo Finance v10."""
from __future__ import annotations
import asyncio
import time
from typing import Dict, List, Optional, Tuple
import httpx

from app.api.stock_universe import NAME_MAP, SECTOR_MAP, UNIVERSE_MAP
from app.api.stock_fetcher import HEADERS, fetch_quote, fetch_index, get_all_stocks  # re-export

YF_V10 = "https://query1.finance.yahoo.com/v10/finance/quoteSummary"

# ── Shared helper ─────────────────────────────────────────────

def _yf_val(d: dict, k: str) -> str:
    """Extract formatted or raw value from a Yahoo Finance dict field."""
    v = d.get(k, {})
    if isinstance(v, dict):
        return v.get("fmt") or v.get("raw") or "N/A"
    return v or "N/A"

# ── Crumb / cookie cache ──────────────────────────────────────
_crumb: Optional[str] = None
_cookies: Dict[str, str] = {}
_crumb_ts: float = 0
_CRUMB_TTL = 3600


async def _refresh_crumb() -> Tuple[str, Dict[str, str]]:
    global _crumb, _cookies, _crumb_ts
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        await client.get("https://finance.yahoo.com/quote/RELIANCE.NS")
        r = await client.get("https://query1.finance.yahoo.com/v1/test/getcrumb")
        if r.status_code == 200 and len(r.text.strip()) < 50:
            _crumb = r.text.strip()
            _cookies = dict(client.cookies)
            _crumb_ts = time.time()
    return _crumb or "", _cookies


async def _get_crumb() -> Tuple[str, Dict[str, str]]:
    global _crumb
    if _crumb and (time.time() - _crumb_ts) < _CRUMB_TTL:
        return _crumb, _cookies
    return await _refresh_crumb()


async def _v10_get(symbol: str, modules: str) -> Optional[Dict]:
    crumb, cookies = await _get_crumb()
    if not crumb:
        return None
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        for k, v in cookies.items():
            client.cookies.set(k, v)
        url = f"{YF_V10}/{symbol}?modules={modules}&crumb={crumb}"
        r = await client.get(url)
        if r.status_code == 401:
            _crumb = None
            crumb, cookies = await _refresh_crumb()
            if not crumb:
                return None
            for k, v in cookies.items():
                client.cookies.set(k, v)
            r = await client.get(f"{YF_V10}/{symbol}?modules={modules}&crumb={crumb}")
        if r.status_code != 200:
            return None
        result = r.json().get("quoteSummary", {}).get("result", [])
        return result[0] if result else None


# ── Fundamentals ──────────────────────────────────────────────

async def fetch_fundamentals(symbol: str) -> Dict:
    try:
        r0 = await _v10_get(symbol, "summaryDetail,defaultKeyStatistics,financialData,assetProfile")
        if not r0:
            return {"error": "fetch_failed"}
        sd = r0.get("summaryDetail", {})
        ks = r0.get("defaultKeyStatistics", {})
        fd = r0.get("financialData", {})
        ap = r0.get("assetProfile", {})

        def val(d, k):
            v = d.get(k, {})
            if isinstance(v, dict):
                return v.get("fmt") or v.get("raw") or "N/A"
            return v or "N/A"

        return {
            "symbol": symbol,
            "name": NAME_MAP.get(symbol, symbol.replace(".NS", "")),
            "sector": SECTOR_MAP.get(symbol, ap.get("sector", "N/A")),
            "industry": ap.get("industry", "N/A"),
            "website": ap.get("website", "N/A"),
            "description": (ap.get("longBusinessSummary", "")[:300] + "...") if ap.get("longBusinessSummary") else "N/A",
            "employees": _yf_val(ap, "fullTimeEmployees"),
            "market_cap": _yf_val(sd, "marketCap"),
            "pe_ratio": _yf_val(sd, "trailingPE"),
            "forward_pe": _yf_val(sd, "forwardPE"),
            "pb_ratio": _yf_val(ks, "priceToBook"),
            "ps_ratio": _yf_val(ks, "priceToSalesTrailing12Months"),
            "peg_ratio": _yf_val(ks, "pegRatio"),
            "ev": _yf_val(ks, "enterpriseValue"),
            "ev_ebitda": _yf_val(ks, "enterpriseToEbitda"),
            "ev_revenue": _yf_val(ks, "enterpriseToRevenue"),
            "eps": _yf_val(ks, "trailingEps"),
            "forward_eps": _yf_val(ks, "forwardEps"),
            "book_value": _yf_val(ks, "bookValue"),
            "dividend_yield": _yf_val(sd, "dividendYield"),
            "dividend_rate": _yf_val(sd, "dividendRate"),
            "payout_ratio": _yf_val(sd, "payoutRatio"),
            "52w_high": _yf_val(sd, "fiftyTwoWeekHigh"),
            "52w_low": _yf_val(sd, "fiftyTwoWeekLow"),
            "50d_avg": _yf_val(sd, "fiftyDayAverage"),
            "200d_avg": _yf_val(sd, "twoHundredDayAverage"),
            "beta": _yf_val(sd, "beta"),
            "revenue": _yf_val(fd, "totalRevenue"),
            "gross_profit": _yf_val(fd, "grossProfits"),
            "ebitda": _yf_val(fd, "ebitda"),
            "net_income": _yf_val(fd, "netIncomeToCommon"),
            "profit_margin": _yf_val(fd, "profitMargins"),
            "operating_margin": _yf_val(fd, "operatingMargins"),
            "gross_margin": _yf_val(fd, "grossMargins"),
            "revenue_growth": _yf_val(fd, "revenueGrowth"),
            "earnings_growth": _yf_val(fd, "earningsGrowth"),
            "total_cash": _yf_val(fd, "totalCash"),
            "total_debt": _yf_val(fd, "totalDebt"),
            "debt_to_equity": _yf_val(fd, "debtToEquity"),
            "current_ratio": _yf_val(fd, "currentRatio"),
            "quick_ratio": _yf_val(fd, "quickRatio"),
            "roe": _yf_val(fd, "returnOnEquity"),
            "roa": _yf_val(fd, "returnOnAssets"),
            "free_cashflow": _yf_val(fd, "freeCashflow"),
            "operating_cashflow": _yf_val(fd, "operatingCashflow"),
            "shares_outstanding": _yf_val(ks, "sharesOutstanding"),
            "float_shares": _yf_val(ks, "floatShares"),
            "short_ratio": _yf_val(ks, "shortRatio"),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Quarterly Financials ──────────────────────────────────────

async def fetch_quarterly_financials(symbol: str) -> Dict:
    try:
        modules = (
            "incomeStatementHistory,incomeStatementHistoryQuarterly,"
            "balanceSheetHistory,balanceSheetHistoryQuarterly,"
            "cashflowStatementHistory,cashflowStatementHistoryQuarterly"
        )
        r0 = await _v10_get(symbol, modules)
        if not r0:
            return {"error": "fetch_failed"}

        def fmt(d, k):
            return _yf_val(d, k)

        def parse_pl(stmts):
            return [{"date": fmt(s, "endDate"), "revenue": fmt(s, "totalRevenue"),
                     "gross_profit": fmt(s, "grossProfit"), "operating_income": fmt(s, "operatingIncome"),
                     "net_income": fmt(s, "netIncome"), "ebit": fmt(s, "ebit"),
                     "ebitda": fmt(s, "ebitda"), "interest_expense": fmt(s, "interestExpense")} for s in stmts]

        def parse_bs(stmts):
            rows = []
            for s in stmts:
                ta = s.get("totalAssets", {}).get("raw", 0) or 0
                cl = s.get("totalCurrentLiabilities", {}).get("raw", 0) or 0
                ce = ta - cl
                ebit_r = s.get("ebit", {}).get("raw", 0) if "ebit" in s else 0
                rows.append({"date": fmt(s, "endDate"), "total_assets": fmt(s, "totalAssets"),
                             "total_liabilities": fmt(s, "totalLiab"), "total_equity": fmt(s, "totalStockholderEquity"),
                             "total_debt": fmt(s, "longTermDebt"), "current_assets": fmt(s, "totalCurrentAssets"),
                             "current_liabilities": fmt(s, "totalCurrentLiabilities"), "cash": fmt(s, "cash"),
                             "roce": str(round(ebit_r / ce * 100, 2)) if ce else "N/A"})
            return rows

        def parse_cf(stmts):
            return [{"date": fmt(s, "endDate"),
                     "operating_cf": fmt(s, "totalCashFromOperatingActivities"),
                     "investing_cf": fmt(s, "totalCashflowsFromInvestingActivities"),
                     "financing_cf": fmt(s, "totalCashFromFinancingActivities"),
                     "free_cashflow": fmt(s, "freeCashFlow"), "capex": fmt(s, "capitalExpenditures")} for s in stmts]

        return {
            "symbol": symbol,
            "annual_pl":    parse_pl(r0.get("incomeStatementHistory", {}).get("incomeStatementHistory", [])),
            "quarterly_pl": parse_pl(r0.get("incomeStatementHistoryQuarterly", {}).get("incomeStatementHistory", [])),
            "annual_bs":    parse_bs(r0.get("balanceSheetHistory", {}).get("balanceSheetStatements", [])),
            "quarterly_bs": parse_bs(r0.get("balanceSheetHistoryQuarterly", {}).get("balanceSheetStatements", [])),
            "annual_cf":    parse_cf(r0.get("cashflowStatementHistory", {}).get("cashflowStatements", [])),
            "quarterly_cf": parse_cf(r0.get("cashflowStatementHistoryQuarterly", {}).get("cashflowStatements", [])),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Shareholding ──────────────────────────────────────────────

async def fetch_shareholding(symbol: str) -> Dict:
    try:
        r0 = await _v10_get(symbol, "majorHoldersBreakdown,institutionOwnership,fundOwnership,insiderHolders")
        if not r0:
            return {"error": "fetch_failed"}
        mh = r0.get("majorHoldersBreakdown", {})

        def pct(d, k):
            v = d.get(k, {})
            return round((v.get("raw", 0) if isinstance(v, dict) else 0) * 100, 2)

        promoter = pct(mh, "insidersPercentHeld")
        fii      = pct(mh, "institutionsPercentHeld")
        return {
            "symbol": symbol,
            "summary": {
                "promoters": f"{promoter}%",
                "fii_institutions": f"{fii}%",
                "public": f"{round(max(100 - promoter - fii, 0), 2)}%",
            },
            "top_institutions": [
                {"name": i.get("organization", "N/A"),
                 "pct_held": round((i.get("pctHeld", {}).get("raw", 0) or 0) * 100, 2),
                 "shares": i.get("position", {}).get("fmt", "N/A")}
                for i in r0.get("institutionOwnership", {}).get("ownershipList", [])[:10]
            ],
            "top_funds": [
                {"name": f.get("organization", "N/A"),
                 "pct_held": round((f.get("pctHeld", {}).get("raw", 0) or 0) * 100, 2),
                 "shares": f.get("position", {}).get("fmt", "N/A")}
                for f in r0.get("fundOwnership", {}).get("ownershipList", [])[:10]
            ],
            "insiders": [
                {"name": ins.get("name", "N/A"), "relation": ins.get("relation", "N/A"),
                 "shares": ins.get("positionDirect", {}).get("fmt", "N/A")}
                for ins in r0.get("insiderHolders", {}).get("holders", [])[:10]
            ],
        }
    except Exception as e:
        return {"error": str(e)}


# ── Peers ─────────────────────────────────────────────────────

async def fetch_peers(symbol: str) -> List[Dict]:
    from app.api.stock_universe import NIFTY50_SYMBOLS
    sector = SECTOR_MAP.get(symbol, "Other")
    # Search peers across full universe
    all_syms = UNIVERSE_MAP["all"]
    peer_symbols = [s for s in all_syms if SECTOR_MAP.get(s) == sector and s != symbol][:6]
    if not peer_symbols:
        peer_symbols = NIFTY50_SYMBOLS[:6]

    async def _peer(sym: str) -> Optional[Dict]:
        try:
            r0 = await _v10_get(sym, "summaryDetail,defaultKeyStatistics,financialData")
            if not r0:
                return None
            sd, ks, fd = r0.get("summaryDetail", {}), r0.get("defaultKeyStatistics", {}), r0.get("financialData", {})
            def v(d, k):
                return _yf_val(d, k)
            return {
                "symbol": sym.replace(".NS", ""), "name": NAME_MAP.get(sym, sym.replace(".NS", "")),
                "price": v(sd, "regularMarketPrice") if "regularMarketPrice" in sd else "N/A",
                "market_cap": v(sd, "marketCap"), "pe_ratio": v(sd, "trailingPE"),
                "pb_ratio": v(ks, "priceToBook"), "roe": v(fd, "returnOnEquity"),
                "roa": v(fd, "returnOnAssets"), "profit_margin": v(fd, "profitMargins"),
                "revenue_growth": v(fd, "revenueGrowth"), "debt_to_equity": v(fd, "debtToEquity"),
                "dividend_yield": v(sd, "dividendYield"), "eps": v(ks, "trailingEps"),
            }
        except Exception:
            return None

    results = await asyncio.gather(*[_peer(s) for s in peer_symbols], return_exceptions=True)
    return [r for r in results if r and not isinstance(r, Exception)]
