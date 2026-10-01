'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  RefreshCw, Plus, Trash2, TrendingUp, TrendingDown,
  BarChart2, Bot, User, Wallet, Activity, ChevronDown, ChevronUp,
} from 'lucide-react'
import { API_URL } from '@/store/jarvisStore'

// ─────────────────────────────────────────────
// A1.1 — TYPES
// ─────────────────────────────────────────────

export interface PaperPosition {
  symbol: string
  qty: number
  avg_price: number
  current_price: number
  unrealised_pnl: number
  charges_paid: number
  trade_mode: string
  source: string
  opened_at: number
}

export interface PaperTrade {
  id: string
  symbol: string
  trade_type: 'BUY' | 'SELL'
  qty: number
  price: number
  timestamp: number
  trade_mode: string
  source: string
  charges: number
  pnl: number | null
  exit_price: number | null
  notes: string
  ai_signal: string | null
  ai_confidence: number | null
}

export interface PaperPortfolio {
  id: string
  name: string
  owner: string
  initial_balance: number
  cash: number
  total_value: number
  total_return_pct: number
  realised_pnl: number
  unrealised_pnl: number
  trade_count: number
  created_at: number
  positions: Record<string, PaperPosition>
}

export interface PerformanceStats {
  total_trades: number
  closed_trades: number
  open_positions: number
  win_rate: number
  loss_rate: number
  avg_profit: number
  avg_loss: number
  profit_factor: number
  total_realised_pnl: number
  total_return_pct: number
  max_drawdown_pct: number
  sharpe_ratio: number
  volatility_pct: number
  ai_accuracy: number
  ai_trades: number
  equity_curve: { date: string; value: number }[]
  initial_balance: number
  current_value: number
}

export interface CompareItem {
  id: string
  name: string
  owner: string
  total_return_pct: number
  total_realised_pnl: number
  win_rate: number
  sharpe_ratio: number
  max_drawdown_pct: number
  ai_accuracy: number
  total_trades: number
}

// ─────────────────────────────────────────────
// A1.1 — API HELPERS
// ─────────────────────────────────────────────

export async function apiCreatePortfolio(name: string, balance: number): Promise<PaperPortfolio> {
  const r = await fetch(`${API_URL}/api/paper/portfolio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, balance }),
  })
  return r.json()
}

export async function apiListPortfolios(): Promise<PaperPortfolio[]> {
  const r = await fetch(`${API_URL}/api/paper/portfolios`)
  const d = await r.json()
  return d.portfolios ?? []
}

export async function apiDeletePortfolio(pid: string): Promise<void> {
  await fetch(`${API_URL}/api/paper/portfolio/${pid}`, { method: 'DELETE' })
}

export async function apiExecuteTrade(
  pid: string,
  symbol: string,
  trade_type: 'BUY' | 'SELL',
  qty: number,
  trade_mode: string,
): Promise<{ status?: string; error?: string; trade?: PaperTrade; portfolio?: PaperPortfolio }> {
  const r = await fetch(`${API_URL}/api/paper/trade/${pid}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, trade_type, qty, trade_mode, source: 'user' }),
  })
  return r.json()
}

export async function apiAITrade(
  pid: string,
  symbol: string,
): Promise<{ status?: string; error?: string; reason?: string }> {
  const r = await fetch(`${API_URL}/api/paper/ai-trade/${pid}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, budget_per_trade: 10000 }),
  })
  return r.json()
}

export async function apiGetPerformance(pid: string): Promise<PerformanceStats> {
  const r = await fetch(`${API_URL}/api/paper/performance/${pid}`)
  return r.json()
}

export async function apiGetTrades(pid: string): Promise<PaperTrade[]> {
  const r = await fetch(`${API_URL}/api/paper/trades/${pid}`)
  const d = await r.json()
  return d.trades ?? []
}

export async function apiCompare(pids: string[]): Promise<CompareItem[]> {
  const params = pids.map(p => `ids=${p}`).join('&')
  const r = await fetch(`${API_URL}/api/paper/compare?${params}`)
  const d = await r.json()
  return d.comparison ?? []
}

// ─────────────────────────────────────────────
// SHARED STYLE UTILS
// ─────────────────────────────────────────────

export const pnlColor = (v: number) =>
  v > 0 ? 'text-jarvis-neon-green' : v < 0 ? 'text-jarvis-neon-red' : 'text-jarvis-muted'

export const pnlSign = (v: number) => (v > 0 ? '+' : '')

export const inputCls =
  'bg-white/5 border border-jarvis-border rounded px-3 py-1.5 text-xs font-mono text-jarvis-text outline-none focus:border-jarvis-accent/50 w-full placeholder-jarvis-muted/50'

export const activeBtnCls =
  'px-3 py-1.5 text-xs font-mono rounded bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all'

export const mutedBtnCls =
  'px-3 py-1.5 text-xs font-mono rounded bg-white/5 text-jarvis-muted hover:text-jarvis-text border border-transparent transition-all'

// ─────────────────────────────────────────────
// A1.2 — PORTFOLIO CREATOR
// ─────────────────────────────────────────────

function PortfolioCreator({ onCreated }: { onCreated: (p: PaperPortfolio) => void }) {
  const [name, setName]       = useState('My Portfolio')
  const [balance, setBalance] = useState('100000')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const handleCreate = async () => {
    if (!name.trim()) { setError('Enter a name'); return }
    const bal = parseFloat(balance)
    if (!bal || bal < 1000) { setError('Min balance ₹1,000'); return }
    setLoading(true); setError('')
    try {
      const p = await apiCreatePortfolio(name.trim(), bal)
      if ((p as any).error) { setError((p as any).error); return }
      onCreated(p)
      setName('My Portfolio')
      setBalance('100000')
    } catch {
      setError('Failed to create portfolio')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="glass rounded-xl p-4 border border-jarvis-border">
      <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold mb-3">
        ➕ New Virtual Portfolio
      </p>
      <div className="flex gap-2 flex-wrap items-end">
        <div className="flex-1 min-w-[140px]">
          <label className="text-[10px] text-jarvis-muted block mb-1">Portfolio Name</label>
          <input
            className={inputCls}
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="My Portfolio"
          />
        </div>
        <div className="w-40">
          <label className="text-[10px] text-jarvis-muted block mb-1">Starting Balance (₹)</label>
          <input
            className={inputCls}
            type="number"
            value={balance}
            onChange={e => setBalance(e.target.value)}
            placeholder="100000"
          />
        </div>
        <button
          onClick={handleCreate}
          disabled={loading}
          className={`${activeBtnCls} flex items-center gap-1.5 shrink-0 disabled:opacity-40`}
        >
          {loading
            ? <RefreshCw size={11} className="animate-spin" />
            : <Plus size={11} />}
          Create
        </button>
      </div>
      {error && <p className="text-[10px] text-jarvis-neon-red mt-2">{error}</p>}
    </div>
  )
}

// ─────────────────────────────────────────────
// A1.3 — PORTFOLIO SELECTOR + SUMMARY CARDS
// ─────────────────────────────────────────────

function PortfolioSelector({
  portfolios, activeId, onSelect, onDelete, onRefresh, loading,
}: {
  portfolios: PaperPortfolio[]
  activeId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onRefresh: () => void
  loading: boolean
}) {
  if (portfolios.length === 0)
    return <p className="text-center py-6 text-jarvis-muted text-xs">No portfolios yet — create one above</p>

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">
          Your Portfolios ({portfolios.length})
        </p>
        <button onClick={onRefresh} disabled={loading} className="text-jarvis-muted hover:text-jarvis-accent transition-colors">
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>
      {portfolios.map(p => {
        const ret = p.total_return_pct ?? 0
        const isActive = p.id === activeId
        return (
          <motion.div
            key={p.id}
            whileHover={{ x: 2 }}
            onClick={() => onSelect(p.id)}
            className={`flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer border transition-all ${
              isActive
                ? 'bg-jarvis-accent/10 border-jarvis-accent/30'
                : 'bg-white/[0.02] border-jarvis-border hover:border-jarvis-accent/20'
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-jarvis-text truncate">{p.name}</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                  p.owner === 'ai' ? 'bg-jarvis-accent/10 text-jarvis-accent' : 'bg-white/5 text-jarvis-muted'
                }`}>{p.owner.toUpperCase()}</span>
              </div>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="text-[10px] text-jarvis-muted font-mono">
                  ₹{(p.total_value ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </span>
                <span className={`text-[10px] font-mono font-bold ${pnlColor(ret)}`}>
                  {pnlSign(ret)}{ret.toFixed(2)}%
                </span>
                <span className="text-[9px] text-jarvis-muted">{p.trade_count} trades</span>
              </div>
            </div>
            <button
              onClick={e => { e.stopPropagation(); onDelete(p.id) }}
              className="text-jarvis-muted hover:text-jarvis-neon-red transition-colors ml-2 shrink-0"
            >
              <Trash2 size={12} />
            </button>
          </motion.div>
        )
      })}
    </div>
  )
}

function PortfolioSummaryCards({ p }: { p: PaperPortfolio }) {
  const cards = [
    { label: 'Total Value',    value: `₹${(p.total_value ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: 'text-jarvis-text',         icon: Wallet },
    { label: 'Cash',          value: `₹${(p.cash ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,        color: 'text-jarvis-accent',       icon: Wallet },
    { label: 'Unrealised P&L', value: `${pnlSign(p.unrealised_pnl ?? 0)}₹${Math.abs(p.unrealised_pnl ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: pnlColor(p.unrealised_pnl ?? 0), icon: Activity },
    { label: 'Realised P&L',   value: `${pnlSign(p.realised_pnl ?? 0)}₹${Math.abs(p.realised_pnl ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,   color: pnlColor(p.realised_pnl ?? 0),   icon: Activity },
    { label: 'Return',        value: `${pnlSign(p.total_return_pct ?? 0)}${(p.total_return_pct ?? 0).toFixed(2)}%`,   color: pnlColor(p.total_return_pct ?? 0), icon: TrendingUp },
    { label: 'Trades',        value: String(p.trade_count ?? 0),                                                       color: 'text-jarvis-text',         icon: BarChart2 },
  ]
  return (
    <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
      {cards.map(({ label, value, color, icon: Icon }) => (
        <div key={label} className="glass rounded-xl p-3 text-center">
          <Icon size={13} className="text-jarvis-muted mx-auto mb-1" />
          <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</p>
          <p className={`text-xs font-mono font-bold mt-0.5 ${color}`}>{value}</p>
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────
// A1.4 — TRADE PANEL
// ─────────────────────────────────────────────

function TradePanel({ portfolioId, onTradeExecuted }: {
  portfolioId: string
  onTradeExecuted: (p: PaperPortfolio) => void
}) {
  const [symbol, setSymbol]   = useState('RELIANCE')
  const [side, setSide]       = useState<'BUY' | 'SELL'>('BUY')
  const [qty, setQty]         = useState('10')
  const [mode, setMode]       = useState<'delivery' | 'intraday'>('intraday')
  const [loading, setLoading] = useState(false)
  const [aiLoad, setAiLoad]   = useState(false)
  const [msg, setMsg]         = useState<{ text: string; ok: boolean } | null>(null)

  const flash = (text: string, ok: boolean) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3500)
  }

  const handleTrade = async () => {
    const q = parseInt(qty)
    if (!symbol.trim() || !q || q <= 0) { flash('Enter valid symbol and qty', false); return }
    setLoading(true)
    try {
      const res = await apiExecuteTrade(portfolioId, symbol.trim().toUpperCase(), side, q, mode)
      if (res.error) flash(`Error: ${res.error}`, false)
      else {
        flash(`${side} ${q} ${symbol.toUpperCase()} @ ₹${res.trade?.price?.toLocaleString('en-IN')}`, true)
        if (res.portfolio) onTradeExecuted(res.portfolio)
      }
    } catch { flash('Trade failed', false) }
    finally { setLoading(false) }
  }

  const handleAITrade = async () => {
    if (!symbol.trim()) { flash('Enter a symbol', false); return }
    setAiLoad(true)
    try {
      const res = await apiAITrade(portfolioId, symbol.trim().toUpperCase())
      if (res.error) flash(`AI Error: ${res.error}`, false)
      else if (res.status === 'no_trade') flash(`AI skipped: ${res.reason}`, false)
      else flash('AI trade executed!', true)
    } catch { flash('AI trade failed', false) }
    finally { setAiLoad(false) }
  }

  return (
    <div className="glass rounded-xl p-4 border border-jarvis-border space-y-3">
      <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">Execute Trade</p>
      <div className="flex gap-1">
        {(['BUY', 'SELL'] as const).map(s => (
          <button key={s} onClick={() => setSide(s)}
            className={`flex-1 py-1.5 text-xs font-mono font-bold rounded transition-all ${
              side === s
                ? s === 'BUY'
                  ? 'bg-jarvis-neon-green/20 text-jarvis-neon-green border border-jarvis-neon-green/40'
                  : 'bg-jarvis-neon-red/20 text-jarvis-neon-red border border-jarvis-neon-red/40'
                : 'bg-white/5 text-jarvis-muted border border-transparent'
            }`}>{s === 'BUY' ? '▲' : '▼'} {s}</button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-jarvis-muted block mb-1">Symbol</label>
          <input className={inputCls} value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} placeholder="RELIANCE" />
        </div>
        <div>
          <label className="text-[10px] text-jarvis-muted block mb-1">Quantity</label>
          <input className={inputCls} type="number" value={qty} onChange={e => setQty(e.target.value)} placeholder="10" />
        </div>
      </div>
      <div className="flex gap-1">
        {(['intraday', 'delivery'] as const).map(m => (
          <button key={m} onClick={() => setMode(m)}
            className={`text-[10px] px-3 py-1 rounded font-mono transition-all ${
              mode === m ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30' : 'bg-white/5 text-jarvis-muted'
            }`}>{m.charAt(0).toUpperCase() + m.slice(1)}</button>
        ))}
      </div>
      <div className="flex gap-2">
        <button onClick={handleTrade} disabled={loading}
          className={`flex-1 py-2 text-xs font-mono font-bold rounded transition-all flex items-center justify-center gap-1.5 disabled:opacity-40 ${
            side === 'BUY'
              ? 'bg-jarvis-neon-green/20 text-jarvis-neon-green border border-jarvis-neon-green/30 hover:bg-jarvis-neon-green/30'
              : 'bg-jarvis-neon-red/20 text-jarvis-neon-red border border-jarvis-neon-red/30 hover:bg-jarvis-neon-red/30'
          }`}>
          {loading ? <RefreshCw size={11} className="animate-spin" /> : <User size={11} />}
          {side}
        </button>
        <button onClick={handleAITrade} disabled={aiLoad}
          className="flex-1 py-2 text-xs font-mono font-bold rounded bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all flex items-center justify-center gap-1.5 disabled:opacity-40">
          {aiLoad ? <RefreshCw size={11} className="animate-spin" /> : <Bot size={11} />}
          AI Trade
        </button>
      </div>
      <AnimatePresence>
        {msg && (
          <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className={`text-[11px] font-mono px-2 py-1.5 rounded ${
              msg.ok ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' : 'bg-jarvis-neon-red/10 text-jarvis-neon-red'
            }`}>{msg.text}</motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─────────────────────────────────────────────
// A1.5 — INLINE POSITION CHART
// ─────────────────────────────────────────────

interface Candle { t: number; o: number; h: number; l: number; c: number; v: number }

function holdDuration(openedAt: number): string {
  const secs = Math.floor(Date.now() / 1000 - openedAt)
  if (secs < 60) return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
  return `${Math.floor(secs / 86400)}d ${Math.floor((secs % 86400) / 3600)}h`
}

// Returns { label, countdown, urgent } for when the position ends
function getExitInfo(tradeMode: string, buyPrice: number, currentPrice: number): {
  label: string
  countdown: string
  urgent: boolean
  color: string
} {
  const nowIST = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
  const h = nowIST.getHours(), m = nowIST.getMinutes()
  const isWeekend = nowIST.getDay() === 0 || nowIST.getDay() === 6
  const marketOpen = !isWeekend && (h > 9 || (h === 9 && m >= 15))
  const marketClose = !isWeekend && (h < 15 || (h === 15 && m < 30))
  const marketLive = marketOpen && marketClose

  if (tradeMode === 'intraday') {
    if (isWeekend) return { label: 'Ends Monday', countdown: 'Market closed', urgent: false, color: 'text-yellow-400' }
    if (!marketOpen) return { label: 'Ends today', countdown: 'Market opens 9:15 AM', urgent: false, color: 'text-yellow-400' }
    if (!marketClose) return { label: 'Closed', countdown: 'Squared off at 3:30 PM', urgent: false, color: 'text-jarvis-muted' }
    // countdown to 3:30 PM IST
    const closeH = 15, closeM = 30
    const secsLeft = (closeH - h) * 3600 + (closeM - m) * 60 - nowIST.getSeconds()
    const urgent = secsLeft < 1800 // < 30 min
    const hh = Math.floor(secsLeft / 3600)
    const mm = Math.floor((secsLeft % 3600) / 60)
    const ss = secsLeft % 60
    const countdown = hh > 0 ? `${hh}h ${mm}m left` : mm > 0 ? `${mm}m ${ss}s left` : `${ss}s left`
    return { label: 'Intraday ends at 3:30 PM', countdown, urgent, color: urgent ? 'text-red-400' : 'text-orange-400' }
  }

  // Delivery — estimate days to target based on daily % move
  const pnlPct = buyPrice > 0 ? ((currentPrice - buyPrice) / buyPrice) * 100 : 0
  const avgDailyMove = 1.2 // assume ~1.2% avg daily move toward target
  const targetPct = 5      // default 5% target
  const remaining = Math.max(0, targetPct - pnlPct)
  const estDays = remaining > 0 ? Math.ceil(remaining / avgDailyMove) : 0

  if (estDays === 0) return { label: 'Near target', countdown: 'Consider booking profit', urgent: false, color: 'text-green-400' }
  if (estDays <= 3)  return { label: `Est. exit in ~${estDays}d`, countdown: `~${estDays} trading day${estDays > 1 ? 's' : ''} to 5% target`, urgent: false, color: 'text-cyan-400' }
  return { label: `Est. exit in ~${estDays}d`, countdown: `~${estDays} trading days to 5% target`, urgent: false, color: 'text-jarvis-muted' }
}

function PositionChart({ symbol, buyPrice, openedAt, currentPrice }: {
  symbol: string
  buyPrice: number
  openedAt: number
  currentPrice: number
}) {
  const [candles, setCandles] = useState<Candle[]>([])
  const [loading, setLoading] = useState(true)
  const [tf, setTf] = useState<'5m' | '15m' | '1H' | '1D'>('15m')
  const [tick, setTick] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const TF_MAP = {
    '5m':  { interval: '5m',  range: '1d' },
    '15m': { interval: '15m', range: '5d' },
    '1H':  { interval: '60m', range: '1mo' },
    '1D':  { interval: '1d',  range: '1y' },
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { interval, range } = TF_MAP[tf]
      const apiSymbol = symbol.includes('.') ? symbol : `${symbol}.NS`
      const r = await fetch(`${API_URL}/api/stocks/chart/${apiSymbol}?interval=${interval}&range=${range}`)
      const d = await r.json()
      if (d.candles?.length) setCandles(d.candles)
    } catch {}
    finally { setLoading(false) }
  }, [symbol, tf])

  useEffect(() => { load() }, [load])

  // live hold-duration ticker
  useEffect(() => {
    timerRef.current = setInterval(() => setTick(t => t + 1), 1000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [])

  // patch last candle with live price
  const displayCandles = candles.length > 0 ? [
    ...candles.slice(0, -1),
    { ...candles[candles.length - 1], c: currentPrice, h: Math.max(candles[candles.length - 1].h, currentPrice), l: Math.min(candles[candles.length - 1].l, currentPrice) },
  ] : []

  const W = 900, H = 260
  const PAD = { top: 16, right: 56, bottom: 28, left: 56 }
  const cw = W - PAD.left - PAD.right
  const ch = H - PAD.top - PAD.bottom

  const allPrices = displayCandles.flatMap(c => [c.h, c.l])
  if (buyPrice > 0) allPrices.push(buyPrice)
  const minP = allPrices.length ? Math.min(...allPrices) * 0.9995 : 0
  const maxP = allPrices.length ? Math.max(...allPrices) * 1.0005 : 1
  const priceRange = maxP - minP || 1

  const xS = (i: number) => PAD.left + (i / Math.max(displayCandles.length - 1, 1)) * cw
  const yS = (v: number) => PAD.top + ch - ((v - minP) / priceRange) * ch

  const positive = displayCandles.length > 1
    ? displayCandles[displayCandles.length - 1].c >= displayCandles[0].c
    : currentPrice >= buyPrice

  const linePts = displayCandles.map((c, i) => `${xS(i)},${yS(c.c)}`).join(' ')
  const yTicks = Array.from({ length: 5 }, (_, i) => minP + (priceRange / 4) * i)
  const xStep = Math.max(1, Math.floor(displayCandles.length / 8))

  const buyY = yS(buyPrice)
  const isInRange = buyPrice >= minP && buyPrice <= maxP
  const duration = holdDuration(openedAt)
  const pnlPct = buyPrice > 0 ? ((currentPrice - buyPrice) / buyPrice) * 100 : 0

  return (
    <div className="mt-3 space-y-2">
      {/* TF selector */}
      <div className="flex items-center gap-1">
        {(['5m', '15m', '1H', '1D'] as const).map(t => (
          <button key={t} onClick={e => { e.stopPropagation(); setTf(t) }}
            className={`text-[10px] px-2 py-0.5 rounded font-mono transition-all ${
              tf === t ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30' : 'bg-white/5 text-jarvis-muted hover:text-jarvis-text'
            }`}>{t}</button>
        ))}
        <button onClick={e => { e.stopPropagation(); load() }} className="ml-1 text-jarvis-muted hover:text-jarvis-accent transition-colors">
          <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
        </button>
        <span className="ml-auto text-[10px] font-mono text-jarvis-muted">
          ⏱ <span className={pnlPct >= 0 ? 'text-green-400' : 'text-red-400'} key={tick}>{duration}</span>
        </span>
      </div>

      {/* Chart SVG */}
      <div className="rounded-xl overflow-hidden bg-white/[0.02] border border-jarvis-border/50">
        {loading ? (
          <div className="flex items-center justify-center h-[260px] text-jarvis-muted text-xs gap-2">
            <RefreshCw size={13} className="animate-spin text-jarvis-accent" /> Loading chart...
          </div>
        ) : displayCandles.length === 0 ? (
          <div className="flex items-center justify-center h-[260px] text-jarvis-muted text-xs">No chart data</div>
        ) : (
          <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full" style={{ height: 260 }}>
            <defs>
              <linearGradient id={`grad-${symbol}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={positive ? '#30d158' : '#ff453a'} stopOpacity="0.18" />
                <stop offset="100%" stopColor={positive ? '#30d158' : '#ff453a'} stopOpacity="0" />
              </linearGradient>
            </defs>

            {/* Grid */}
            {yTicks.map((v, i) => (
              <g key={i}>
                <line x1={PAD.left} x2={W - PAD.right} y1={yS(v)} y2={yS(v)}
                  stroke="rgba(6,182,212,0.06)" strokeWidth="1" />
                <text x={PAD.left - 4} y={yS(v) + 4} textAnchor="end"
                  fill="rgba(148,163,184,0.7)" fontSize="9" fontFamily="monospace">
                  {v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v.toFixed(0)}
                </text>
              </g>
            ))}
            {displayCandles.filter((_, i) => i % xStep === 0).map((c, _, arr) => {
              const i = displayCandles.indexOf(c)
              const d = new Date(c.t)
              const label = ['1H','1D'].includes(tf)
                ? d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
                : d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
              return (
                <text key={i} x={xS(i)} y={H - 6} textAnchor="middle"
                  fill="rgba(148,163,184,0.6)" fontSize="9" fontFamily="monospace">{label}</text>
              )
            })}

            {/* Area + line */}
            <polygon
              points={`${PAD.left},${PAD.top + ch} ${linePts} ${xS(displayCandles.length - 1)},${PAD.top + ch}`}
              fill={`url(#grad-${symbol})`}
            />
            <polyline points={linePts} fill="none"
              stroke={positive ? '#30d158' : '#ff453a'} strokeWidth="1.5"
              strokeLinejoin="round" strokeLinecap="round" />

            {/* Live price dot */}
            <circle
              cx={xS(displayCandles.length - 1)}
              cy={yS(displayCandles[displayCandles.length - 1].c)}
              r="3.5"
              fill={positive ? '#30d158' : '#ff453a'}
              stroke={positive ? 'rgba(48,209,88,0.3)' : 'rgba(255,69,58,0.3)'}
              strokeWidth="6"
            />
            {/* Live price label on right */}
            <rect
              x={W - PAD.right + 2}
              y={yS(displayCandles[displayCandles.length - 1].c) - 9}
              width={50} height={16} rx="3"
              fill={positive ? '#30d158' : '#ff453a'} opacity="0.9"
            />
            <text
              x={W - PAD.right + 5}
              y={yS(displayCandles[displayCandles.length - 1].c) + 3}
              fontSize="9" fontFamily="monospace" fill="#000" fontWeight="bold"
            >
              ₹{currentPrice >= 1000 ? (currentPrice / 1000).toFixed(1) + 'k' : currentPrice.toFixed(0)}
            </text>

            {/* BUY price horizontal line */}
            {isInRange && (() => {
              const labelText = `BUY ₹${buyPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}  ·  ${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%`
              const lw = labelText.length * 5.8 + 14
              return (
                <g>
                  <line x1={PAD.left} x2={W - PAD.right} y1={buyY} y2={buyY}
                    stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="6,3" opacity="0.9" />
                  {/* pill label */}
                  <rect x={PAD.left} y={buyY - 10} width={lw} height={18} rx="4"
                    fill="rgba(245,158,11,0.15)" stroke="#f59e0b" strokeWidth="1" />
                  <text x={PAD.left + 7} y={buyY + 4} fontSize="9.5" fontFamily="monospace"
                    fill="#f59e0b" fontWeight="bold">{labelText}</text>
                  {/* right price tag */}
                  <rect x={W - PAD.right + 2} y={buyY - 9} width={50} height={16} rx="3"
                    fill="rgba(245,158,11,0.85)" />
                  <text x={W - PAD.right + 5} y={buyY + 3} fontSize="9" fontFamily="monospace"
                    fill="#000" fontWeight="bold">
                    ₹{buyPrice >= 1000 ? (buyPrice / 1000).toFixed(1) + 'k' : buyPrice.toFixed(0)}
                  </text>
                </g>
              )
            })()}
          </svg>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// A1.5 — OPEN POSITIONS TABLE
// ─────────────────────────────────────────────

function PositionsTable({ positions, onRefresh, portfolioId }: {
  positions: Record<string, PaperPosition>
  onRefresh?: () => void
  portfolioId: string
}) {
  const rows = Object.values(positions)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const [closing, setClosing] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ symbol: string; text: string; ok: boolean } | null>(null)

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 1000)
    return () => clearInterval(id)
  }, [])

  const handleClose = async (e: React.MouseEvent, pos: PaperPosition) => {
    e.stopPropagation()
    setClosing(pos.symbol)
    try {
      const r = await fetch(`${API_URL}/api/paper/trade/${portfolioId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: pos.symbol, trade_type: 'SELL', qty: pos.qty, trade_mode: pos.trade_mode, source: 'user' }),
      })
      const d = await r.json()
      if (d.error) {
        setMsg({ symbol: pos.symbol, text: d.error, ok: false })
      } else {
        const pnl = d.trade?.pnl ?? 0
        setMsg({ symbol: pos.symbol, text: `Closed @ ₹${d.trade?.price?.toLocaleString('en-IN')} · P&L ${pnl >= 0 ? '+' : ''}₹${Math.abs(pnl).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, ok: pnl >= 0 })
        setTimeout(() => { setMsg(null); onRefresh?.() }, 2500)
      }
    } catch {
      setMsg({ symbol: pos.symbol, text: 'Failed to close position', ok: false })
    } finally {
      setClosing(null)
    }
  }

  if (rows.length === 0)
    return <p className="text-center py-6 text-jarvis-muted text-xs">No open positions</p>

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">Open Positions ({rows.length})</p>
        {onRefresh && (
          <button onClick={onRefresh} className="text-jarvis-muted hover:text-jarvis-accent transition-colors" title="Refresh live prices">
            <RefreshCw size={11} />
          </button>
        )}
      </div>

      <div className="space-y-3">
        {rows.map(pos => {
          const pnlPct = pos.avg_price > 0 ? (pos.unrealised_pnl / (pos.avg_price * pos.qty)) * 100 : 0
          const ltp = pos.current_price || pos.avg_price
          const buyDate = new Date(pos.opened_at * 1000)
          const isProfit = pos.unrealised_pnl >= 0
          const isOpen = expanded === pos.symbol
          const exitInfo = getExitInfo(pos.trade_mode, pos.avg_price, ltp)

          return (
            <div
              key={pos.symbol}
              className={`glass rounded-xl border transition-all ${
                isOpen ? 'border-jarvis-accent/40' : 'border-jarvis-border hover:border-jarvis-accent/30'
              }`}
            >
              {/* ── Card header — always visible, click to expand ── */}
              <div
                className="p-4 cursor-pointer"
                onClick={() => setExpanded(isOpen ? null : pos.symbol)}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono font-bold text-jarvis-accent">{pos.symbol}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                      pos.source === 'ai' ? 'bg-jarvis-accent/10 text-jarvis-accent' : 'bg-white/5 text-jarvis-muted'
                    }`}>{pos.source.toUpperCase()}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded font-mono bg-white/5 text-jarvis-muted">{pos.trade_mode}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={`text-sm font-mono font-bold ${pnlColor(pos.unrealised_pnl)}`}>
                      {pnlSign(pos.unrealised_pnl)}₹{Math.abs(pos.unrealised_pnl).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      <span className="text-[10px] ml-1 opacity-70">({pnlSign(pnlPct)}{pnlPct.toFixed(2)}%)</span>
                    </div>
                    {/* Square Off button */}
                    <button
                      onClick={e => handleClose(e, pos)}
                      disabled={closing === pos.symbol}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25 transition-all disabled:opacity-40 shrink-0"
                    >
                      {closing === pos.symbol
                        ? <RefreshCw size={9} className="animate-spin" />
                        : <span>▼</span>}
                      {closing === pos.symbol ? 'Closing...' : 'Square Off'}
                    </button>
                    {isOpen
                      ? <ChevronUp size={14} className="text-jarvis-accent shrink-0" />
                      : <ChevronDown size={14} className="text-jarvis-muted shrink-0" />}
                  </div>
                </div>

                {/* Close result flash */}
                <AnimatePresence>
                  {msg?.symbol === pos.symbol && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      className={`text-[11px] font-mono px-3 py-1.5 rounded-lg mb-2 ${
                        msg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
                      }`}
                    >
                      {msg.ok ? '✓' : '✗'} {msg.text}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Stats row */}
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div>
                    <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">LTP</p>
                    <p className="text-xs font-mono text-jarvis-text">₹{ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">Buy Price</p>
                    <p className="text-xs font-mono text-amber-400">₹{pos.avg_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">Qty</p>
                    <p className="text-xs font-mono text-jarvis-text">{pos.qty}</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">Holding</p>
                    <p className={`text-xs font-mono font-bold ${ isProfit ? 'text-green-400' : 'text-red-400' }`} key={tick}>
                      {holdDuration(pos.opened_at)}
                    </p>
                  </div>
                </div>

                {/* Buy date + exit info */}
                <div className="flex items-center justify-between mt-2">
                  <p className="text-[9px] text-jarvis-muted font-mono">
                    📅 {buyDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                    {' '}{buyDate.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })}
                    {isOpen ? '' : '  ·  Click to view chart'}
                  </p>
                  <div className={`flex items-center gap-1.5 text-[9px] font-mono px-2 py-0.5 rounded-full border ${
                    exitInfo.urgent
                      ? 'bg-red-500/10 border-red-500/30 animate-pulse'
                      : 'bg-white/5 border-jarvis-border/50'
                  }`} key={tick}>
                    <span className="text-jarvis-muted">🏁</span>
                    <span className={exitInfo.color}>{exitInfo.label}</span>
                    <span className="text-jarvis-muted">·</span>
                    <span className={`font-bold ${exitInfo.color}`}>{exitInfo.countdown}</span>
                  </div>
                </div>
              </div>

              {/* ── Inline chart — shown when expanded ── */}
              <AnimatePresence>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.22 }}
                    className="overflow-hidden px-4 pb-4"
                    onClick={e => e.stopPropagation()}
                  >
                    <PositionChart
                      symbol={pos.symbol}
                      buyPrice={pos.avg_price}
                      openedAt={pos.opened_at}
                      currentPrice={ltp}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// A1.6 — TRADE HISTORY TABLE
// ─────────────────────────────────────────────

function TradeHistoryTable({ trades }: { trades: PaperTrade[] }) {
  if (trades.length === 0)
    return <p className="text-center py-6 text-jarvis-muted text-xs">No trades yet</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-jarvis-border">
            {['Time', 'Symbol', 'Type', 'Qty', 'Price', 'Charges', 'P&L', 'Source'].map(h => (
              <th key={h} className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {trades.map(t => (
            <tr key={t.id} className="border-b border-jarvis-border/40 hover:bg-white/[0.02] transition-colors">
              <td className="py-2 px-3 text-jarvis-muted font-mono text-[10px] whitespace-nowrap">
                {new Date(t.timestamp * 1000).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })}
              </td>
              <td className="py-2 px-3 font-mono font-bold text-jarvis-accent">{t.symbol}</td>
              <td className="py-2 px-3">
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
                  t.trade_type === 'BUY' ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' : 'bg-jarvis-neon-red/10 text-jarvis-neon-red'
                }`}>{t.trade_type}</span>
              </td>
              <td className="py-2 px-3 font-mono text-jarvis-text">{t.qty}</td>
              <td className="py-2 px-3 font-mono text-jarvis-text">₹{t.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
              <td className="py-2 px-3 font-mono text-jarvis-muted">₹{t.charges.toFixed(2)}</td>
              <td className={`py-2 px-3 font-mono font-bold ${
                t.pnl == null ? 'text-jarvis-muted' : pnlColor(t.pnl)
              }`}>
                {t.pnl == null ? '—' : `${pnlSign(t.pnl)}₹${Math.abs(t.pnl).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
              </td>
              <td className="py-2 px-3">
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                  t.source === 'ai' ? 'bg-jarvis-accent/10 text-jarvis-accent' : 'bg-white/5 text-jarvis-muted'
                }`}>{t.source.toUpperCase()}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─────────────────────────────────────────────
// A1.7 — PERFORMANCE STATS PANEL
// ─────────────────────────────────────────────

function PerformancePanel({ portfolioId }: { portfolioId: string }) {
  const [stats, setStats]     = useState<PerformanceStats | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try { setStats(await apiGetPerformance(portfolioId)) }
    catch {}
    finally { setLoading(false) }
  }, [portfolioId])

  useEffect(() => { load() }, [load])

  if (loading) return (
    <div className="flex items-center justify-center py-8 text-jarvis-muted text-xs">
      <RefreshCw size={13} className="animate-spin mr-2 text-jarvis-accent" /> Loading stats...
    </div>
  )
  if (!stats) return null

  const statCards = [
    { label: 'Win Rate',      value: `${stats.win_rate}%`,          color: pnlColor(stats.win_rate - 50) },
    { label: 'Profit Factor', value: stats.profit_factor.toFixed(2), color: pnlColor(stats.profit_factor - 1) },
    { label: 'Sharpe Ratio',  value: stats.sharpe_ratio.toFixed(2),  color: pnlColor(stats.sharpe_ratio) },
    { label: 'Max Drawdown',  value: `-${stats.max_drawdown_pct}%`,  color: 'text-jarvis-neon-red' },
    { label: 'Volatility',    value: `${stats.volatility_pct}%`,     color: 'text-jarvis-muted' },
    { label: 'AI Accuracy',   value: `${stats.ai_accuracy}%`,        color: pnlColor(stats.ai_accuracy - 50) },
    { label: 'Total Return',  value: `${pnlSign(stats.total_return_pct)}${stats.total_return_pct.toFixed(2)}%`, color: pnlColor(stats.total_return_pct) },
    { label: 'Realised P&L',  value: `${pnlSign(stats.total_realised_pnl)}₹${Math.abs(stats.total_realised_pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: pnlColor(stats.total_realised_pnl) },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">Performance Stats</p>
        <button onClick={load} className="text-jarvis-muted hover:text-jarvis-accent transition-colors">
          <RefreshCw size={11} />
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {statCards.map(({ label, value, color }) => (
          <div key={label} className="glass rounded-xl p-3 text-center">
            <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</p>
            <p className={`text-sm font-mono font-bold mt-0.5 ${color}`}>{value}</p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="glass rounded-xl p-3">
          <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">Closed Trades</p>
          <p className="text-sm font-mono font-bold text-jarvis-text mt-0.5">{stats.closed_trades}</p>
        </div>
        <div className="glass rounded-xl p-3">
          <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">Avg Profit</p>
          <p className={`text-sm font-mono font-bold mt-0.5 ${pnlColor(stats.avg_profit)}`}>₹{stats.avg_profit.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
        </div>
        <div className="glass rounded-xl p-3">
          <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">Avg Loss</p>
          <p className="text-sm font-mono font-bold mt-0.5 text-jarvis-neon-red">₹{Math.abs(stats.avg_loss).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
        </div>
      </div>
      {stats.equity_curve.length > 1 && (
        <div className="glass rounded-xl p-4">
          <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold mb-3">Equity Curve</p>
          <EquityCurve data={stats.equity_curve} initial={stats.initial_balance} />
        </div>
      )}
    </div>
  )
}

function EquityCurve({ data, initial }: { data: { date: string; value: number }[]; initial: number }) {
  const W = 600, H = 120
  const vals = data.map(d => d.value)
  const min = Math.min(...vals, initial)
  const max = Math.max(...vals, initial)
  const range = max - min || 1
  const xS = (i: number) => (i / Math.max(data.length - 1, 1)) * W
  const yS = (v: number) => H - ((v - min) / range) * H
  const pts = data.map((d, i) => `${xS(i)},${yS(d.value)}`).join(' ')
  const positive = vals[vals.length - 1] >= initial
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 80 }}>
      <defs>
        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={positive ? '#30d158' : '#ff453a'} stopOpacity="0.3" />
          <stop offset="100%" stopColor={positive ? '#30d158' : '#ff453a'} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${H} ${pts} ${W},${H}`} fill="url(#eqGrad)" />
      <polyline points={pts} fill="none" stroke={positive ? '#30d158' : '#ff453a'} strokeWidth="2" strokeLinejoin="round" />
      <line x1={0} x2={W} y1={yS(initial)} y2={yS(initial)} stroke="rgba(148,163,184,0.3)" strokeWidth="1" strokeDasharray="4,3" />
    </svg>
  )
}

// ─────────────────────────────────────────────
// A1.8 — AI VS USER COMPARISON PANEL
// ─────────────────────────────────────────────

function ComparePanel({ portfolioIds }: { portfolioIds: string[] }) {
  const [data, setData]       = useState<CompareItem[]>([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (portfolioIds.length < 1) return
    setLoading(true)
    try { setData(await apiCompare(portfolioIds)) }
    catch {}
    finally { setLoading(false) }
  }, [portfolioIds.join(',')])

  useEffect(() => { load() }, [load])

  if (loading) return (
    <div className="flex items-center justify-center py-8 text-jarvis-muted text-xs">
      <RefreshCw size={13} className="animate-spin mr-2 text-jarvis-accent" /> Comparing...
    </div>
  )
  if (data.length === 0) return (
    <p className="text-center py-6 text-jarvis-muted text-xs">Create multiple portfolios to compare</p>
  )

  const metrics: { key: keyof CompareItem; label: string }[] = [
    { key: 'total_return_pct',  label: 'Return %' },
    { key: 'total_realised_pnl', label: 'Realised P&L' },
    { key: 'win_rate',          label: 'Win Rate %' },
    { key: 'sharpe_ratio',      label: 'Sharpe' },
    { key: 'max_drawdown_pct',  label: 'Max DD %' },
    { key: 'ai_accuracy',       label: 'AI Accuracy %' },
    { key: 'total_trades',      label: 'Trades' },
  ]

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">Portfolio Comparison</p>
        <button onClick={load} className="text-jarvis-muted hover:text-jarvis-accent transition-colors">
          <RefreshCw size={11} />
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-jarvis-border">
              <th className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">Portfolio</th>
              {metrics.map(m => (
                <th key={m.key} className="text-right py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold whitespace-nowrap">{m.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map(row => (
              <tr key={row.id} className="border-b border-jarvis-border/40 hover:bg-white/[0.02] transition-colors">
                <td className="py-2 px-3">
                  <div className="flex items-center gap-2">
                    {row.owner === 'ai' ? <Bot size={11} className="text-jarvis-accent" /> : <User size={11} className="text-jarvis-muted" />}
                    <span className="font-mono text-jarvis-text text-xs">{row.name}</span>
                  </div>
                </td>
                <td className={`py-2 px-3 text-right font-mono font-bold ${pnlColor(row.total_return_pct)}`}>
                  {pnlSign(row.total_return_pct)}{row.total_return_pct.toFixed(2)}%
                </td>
                <td className={`py-2 px-3 text-right font-mono ${pnlColor(row.total_realised_pnl)}`}>
                  {pnlSign(row.total_realised_pnl)}₹{Math.abs(row.total_realised_pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </td>
                <td className={`py-2 px-3 text-right font-mono ${pnlColor(row.win_rate - 50)}`}>{row.win_rate}%</td>
                <td className={`py-2 px-3 text-right font-mono ${pnlColor(row.sharpe_ratio)}`}>{row.sharpe_ratio.toFixed(2)}</td>
                <td className="py-2 px-3 text-right font-mono text-jarvis-neon-red">{row.max_drawdown_pct}%</td>
                <td className={`py-2 px-3 text-right font-mono ${pnlColor(row.ai_accuracy - 50)}`}>{row.ai_accuracy}%</td>
                <td className="py-2 px-3 text-right font-mono text-jarvis-muted">{row.total_trades}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// A1.9 — FINAL ASSEMBLY
// ─────────────────────────────────────────────

export function PaperTradingPage() {
  const [portfolios, setPortfolios] = useState<PaperPortfolio[]>([])
  const [activeId, setActiveId]     = useState<string | null>(null)
  const [trades, setTrades]         = useState<PaperTrade[]>([])
  const [listLoading, setListLoad]  = useState(false)
  const [activeTab, setActiveTab]   = useState<'trade' | 'positions' | 'history' | 'stats' | 'compare'>('trade')

  const activePortfolio = portfolios.find(p => p.id === activeId) ?? null

  const loadPortfolios = useCallback(async () => {
    setListLoad(true)
    try {
      const list = await apiListPortfolios()
      setPortfolios(list)
      if (!activeId && list.length > 0) setActiveId(list[0].id)
    } catch {}
    finally { setListLoad(false) }
  }, [activeId])

  const loadTrades = useCallback(async () => {
    if (!activeId) return
    try { setTrades(await apiGetTrades(activeId)) } catch {}
  }, [activeId])

  const loadActivePortfolio = useCallback(async () => {
    if (!activeId) return
    try {
      const r = await fetch(`${API_URL}/api/paper/portfolio/${activeId}`)
      const updated: PaperPortfolio = await r.json()
      if (updated && !('error' in updated))
        setPortfolios(prev => prev.map(p => p.id === activeId ? updated : p))
    } catch {}
  }, [activeId])

  useEffect(() => { loadPortfolios() }, [])
  useEffect(() => { loadTrades() }, [activeId])
  useEffect(() => { if (activeTab === 'positions') loadActivePortfolio() }, [activeTab, activeId])

  const handleCreated = (p: PaperPortfolio) => {
    setPortfolios(prev => [...prev, p])
    setActiveId(p.id)
  }

  const handleDelete = async (id: string) => {
    await apiDeletePortfolio(id)
    setPortfolios(prev => prev.filter(p => p.id !== id))
    if (activeId === id) setActiveId(portfolios.find(p => p.id !== id)?.id ?? null)
  }

  const handleTradeExecuted = (updated: PaperPortfolio) => {
    setPortfolios(prev => prev.map(p => p.id === updated.id ? updated : p))
    loadTrades()
    setActiveTab('positions')
  }

  const tabs: { id: typeof activeTab; label: string }[] = [
    { id: 'trade',     label: 'Trade' },
    { id: 'positions', label: 'Positions' },
    { id: 'history',   label: 'History' },
    { id: 'stats',     label: 'Stats' },
    { id: 'compare',   label: 'Compare' },
  ]

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Left sidebar: creator + selector */}
      <div className="w-72 shrink-0 flex flex-col border-r border-jarvis-border overflow-y-auto p-3 gap-3">
        <div className="flex items-center gap-2 mb-1">
          <BarChart2 size={15} className="text-jarvis-accent" />
          <span className="text-sm font-bold text-jarvis-text uppercase tracking-wider">Paper Trading</span>
        </div>
        <PortfolioCreator onCreated={handleCreated} />
        <PortfolioSelector
          portfolios={portfolios}
          activeId={activeId}
          onSelect={setActiveId}
          onDelete={handleDelete}
          onRefresh={loadPortfolios}
          loading={listLoading}
        />
      </div>

      {/* Right: main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!activePortfolio ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-jarvis-muted">
            <BarChart2 size={40} className="text-jarvis-border" />
            <p className="text-sm">Create or select a portfolio to start trading</p>
          </div>
        ) : (
          <>
            {/* Sticky header + tabs */}
            <div className="shrink-0 px-4 pt-4 pb-0 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold font-mono text-jarvis-text">{activePortfolio.name}</h2>
                  <p className="text-[10px] text-jarvis-muted font-mono">ID: {activePortfolio.id} · {activePortfolio.owner.toUpperCase()}</p>
                </div>
                <button onClick={loadActivePortfolio} className="text-jarvis-muted hover:text-jarvis-accent transition-colors">
                  <RefreshCw size={13} />
                </button>
              </div>
              <PortfolioSummaryCards p={activePortfolio} />
              <div className="flex gap-1 border-b border-jarvis-border">
                {tabs.map(t => (
                  <button key={t.id} onClick={() => setActiveTab(t.id)}
                    className={`text-xs px-4 py-2 font-mono transition-all border-b-2 -mb-px ${
                      activeTab === t.id
                        ? 'border-jarvis-accent text-jarvis-accent'
                        : 'border-transparent text-jarvis-muted hover:text-jarvis-text'
                    }`}>{t.label}</button>
                ))}
              </div>
            </div>
            {/* Scrollable tab content */}
            <div className="flex-1 overflow-y-auto p-4">
              <div className="glass rounded-2xl p-4">
                {activeTab === 'trade' && (
                  <TradePanel portfolioId={activePortfolio.id} onTradeExecuted={handleTradeExecuted} />
                )}
                {activeTab === 'positions' && (
                  <PositionsTable positions={activePortfolio.positions} onRefresh={loadActivePortfolio} portfolioId={activePortfolio.id} />
                )}
                {activeTab === 'history' && (
                  <TradeHistoryTable trades={trades} />
                )}
                {activeTab === 'stats' && (
                  <PerformancePanel portfolioId={activePortfolio.id} />
                )}
                {activeTab === 'compare' && (
                  <ComparePanel portfolioIds={portfolios.map(p => p.id)} />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
