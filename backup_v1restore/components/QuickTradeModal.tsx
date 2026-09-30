'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Bot, User, RefreshCw, TrendingUp, TrendingDown, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useJarvisStore, API_URL } from '@/store/jarvisStore'

// ── API helpers (local, no import from PaperTradingPage to avoid circular) ──

async function fetchPortfolios() {
  const r = await fetch(`${API_URL}/api/paper/portfolios`)
  const d = await r.json()
  return d.portfolios ?? []
}

async function createPortfolio(name: string, balance: number) {
  const r = await fetch(`${API_URL}/api/paper/portfolio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, balance }),
  })
  return r.json()
}

async function executeTrade(pid: string, symbol: string, side: 'BUY' | 'SELL', qty: number, mode: string) {
  const r = await fetch(`${API_URL}/api/paper/trade/${pid}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, trade_type: side, qty, trade_mode: mode, source: 'user' }),
  })
  return r.json()
}

async function executeAITrade(pid: string, symbol: string) {
  const r = await fetch(`${API_URL}/api/paper/ai-trade/${pid}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, budget_per_trade: 10000 }),
  })
  return r.json()
}

// ── Component ─────────────────────────────────────────────────

export function QuickTradeModal() {
  const { quickTrade, closeQuickTrade, activePaperPortfolioId, setActivePaperPortfolioId } = useJarvisStore()

  const [portfolios, setPortfolios] = useState<any[]>([])
  const [pid, setPid] = useState<string>(activePaperPortfolioId ?? '')
  const [qty, setQty] = useState('10')
  const [mode, setMode] = useState<'intraday' | 'delivery'>('intraday')
  const [loading, setLoading] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('Quick Portfolio')
  const [newBal, setNewBal] = useState('100000')

  const loadPortfolios = useCallback(async () => {
    try {
      const list = await fetchPortfolios()
      setPortfolios(list)
      // auto-select active or first
      if (activePaperPortfolioId && list.find((p: any) => p.id === activePaperPortfolioId)) {
        setPid(activePaperPortfolioId)
      } else if (list.length > 0) {
        setPid(list[0].id)
        setActivePaperPortfolioId(list[0].id)
      }
    } catch {}
  }, [activePaperPortfolioId, setActivePaperPortfolioId])

  useEffect(() => {
    if (quickTrade) { loadPortfolios(); setResult(null) }
  }, [quickTrade, loadPortfolios])

  // sync pid → store
  useEffect(() => { if (pid) setActivePaperPortfolioId(pid) }, [pid, setActivePaperPortfolioId])

  if (!quickTrade) return null

  const { symbol, side, entry, stop_loss, target1, signal, confidence, source } = quickTrade
  const price = entry ?? quickTrade.price ?? 0
  const cost = price * parseInt(qty || '0')
  const rr = entry && stop_loss && target1
    ? Math.abs(target1 - entry) / Math.abs(entry - stop_loss)
    : null

  const handleTrade = async () => {
    if (!pid) { setResult({ ok: false, msg: 'Select or create a portfolio first' }); return }
    const q = parseInt(qty)
    if (!q || q <= 0) { setResult({ ok: false, msg: 'Enter valid quantity' }); return }
    setLoading(true); setResult(null)
    try {
      const res = await executeTrade(pid, symbol, side, q, mode)
      if (res.error) setResult({ ok: false, msg: res.error })
      else setResult({ ok: true, msg: `${side} ${q} × ${symbol} @ ₹${res.trade?.price?.toLocaleString('en-IN')} — Paper trade executed!` })
    } catch { setResult({ ok: false, msg: 'Trade failed — check backend' }) }
    finally { setLoading(false) }
  }

  const handleAITrade = async () => {
    if (!pid) { setResult({ ok: false, msg: 'Select or create a portfolio first' }); return }
    setAiLoading(true); setResult(null)
    try {
      const res = await executeAITrade(pid, symbol)
      if (res.error) setResult({ ok: false, msg: `AI: ${res.error}` })
      else if (res.status === 'no_trade') setResult({ ok: false, msg: `AI skipped: ${res.reason}` })
      else setResult({ ok: true, msg: `AI trade executed on ${symbol}!` })
    } catch { setResult({ ok: false, msg: 'AI trade failed' }) }
    finally { setAiLoading(false) }
  }

  const handleCreate = async () => {
    const bal = parseFloat(newBal)
    if (!newName.trim() || !bal || bal < 1000) return
    setLoading(true)
    try {
      const p = await createPortfolio(newName.trim(), bal)
      if (!p.error) {
        setPortfolios(prev => [...prev, p])
        setPid(p.id)
        setCreating(false)
      }
    } catch {}
    finally { setLoading(false) }
  }

  const isBuy = side === 'BUY'

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={closeQuickTrade}>
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.15 }}
          onClick={e => e.stopPropagation()}
          className="relative w-full max-w-md rounded-2xl border border-jarvis-border overflow-hidden"
          style={{ background: '#131722' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-jarvis-border">
            <div className="flex items-center gap-3">
              {isBuy
                ? <TrendingUp size={16} className="text-jarvis-neon-green" />
                : <TrendingDown size={16} className="text-jarvis-neon-red" />}
              <div>
                <p className="text-sm font-bold font-mono text-jarvis-text">
                  Paper Trade — {symbol}
                </p>
                <p className="text-[10px] text-jarvis-muted capitalize">
                  {source ?? 'manual'} signal
                  {signal && <span className="ml-1 text-jarvis-accent">· {signal}</span>}
                  {confidence && <span className="ml-1 text-jarvis-muted">· {confidence}% conf</span>}
                </p>
              </div>
            </div>
            <button onClick={closeQuickTrade} className="text-jarvis-muted hover:text-jarvis-text transition-colors">
              <X size={16} />
            </button>
          </div>

          <div className="p-5 space-y-4">
            {/* Signal levels */}
            {(entry || stop_loss || target1) && (
              <div className="grid grid-cols-3 gap-2">
                {entry && (
                  <div className="rounded-lg p-2 text-center" style={{ background: '#2962ff15' }}>
                    <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">Entry</p>
                    <p className="text-xs font-mono font-bold text-jarvis-accent">₹{entry.toFixed(2)}</p>
                  </div>
                )}
                {stop_loss && (
                  <div className="rounded-lg p-2 text-center" style={{ background: '#ef535015' }}>
                    <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">Stop Loss</p>
                    <p className="text-xs font-mono font-bold" style={{ color: '#ef5350' }}>₹{stop_loss.toFixed(2)}</p>
                  </div>
                )}
                {target1 && (
                  <div className="rounded-lg p-2 text-center" style={{ background: '#26a69a15' }}>
                    <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">Target</p>
                    <p className="text-xs font-mono font-bold" style={{ color: '#26a69a' }}>₹{target1.toFixed(2)}</p>
                  </div>
                )}
              </div>
            )}
            {rr && (
              <p className="text-[10px] text-jarvis-muted text-center">
                Risk:Reward = <span className="text-jarvis-accent font-mono font-bold">1:{rr.toFixed(1)}</span>
              </p>
            )}

            {/* Portfolio selector */}
            <div>
              <label className="text-[10px] text-jarvis-muted block mb-1.5 uppercase tracking-wider">Paper Portfolio</label>
              {portfolios.length > 0 ? (
                <select
                  value={pid}
                  onChange={e => setPid(e.target.value)}
                  className="w-full bg-white/5 border border-jarvis-border rounded-lg px-3 py-2 text-xs text-jarvis-text font-mono outline-none focus:border-jarvis-accent/50"
                >
                  {portfolios.map((p: any) => (
                    <option key={p.id} value={p.id} className="bg-[#131722]">
                      {p.name} — ₹{(p.cash ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })} cash
                    </option>
                  ))}
                </select>
              ) : (
                <p className="text-xs text-jarvis-muted py-2">No portfolios yet</p>
              )}
              <button
                onClick={() => setCreating(c => !c)}
                className="mt-1.5 text-[10px] text-jarvis-accent hover:underline"
              >
                {creating ? '— Cancel' : '+ Create new portfolio'}
              </button>
            </div>

            {/* Create portfolio inline */}
            {creating && (
              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <input
                    value={newName}
                    onChange={e => setNewName(e.target.value)}
                    placeholder="Portfolio name"
                    className="w-full bg-white/5 border border-jarvis-border rounded px-2 py-1.5 text-xs text-jarvis-text outline-none focus:border-jarvis-accent/50"
                  />
                </div>
                <div className="w-28">
                  <input
                    type="number"
                    value={newBal}
                    onChange={e => setNewBal(e.target.value)}
                    placeholder="Balance"
                    className="w-full bg-white/5 border border-jarvis-border rounded px-2 py-1.5 text-xs text-jarvis-text font-mono outline-none focus:border-jarvis-accent/50"
                  />
                </div>
                <button
                  onClick={handleCreate}
                  disabled={loading}
                  className="px-3 py-1.5 text-xs rounded bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all disabled:opacity-40 shrink-0"
                >
                  Create
                </button>
              </div>
            )}

            {/* Qty + Mode */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] text-jarvis-muted block mb-1.5 uppercase tracking-wider">Quantity</label>
                <input
                  type="number"
                  value={qty}
                  onChange={e => setQty(e.target.value)}
                  className="w-full bg-white/5 border border-jarvis-border rounded-lg px-3 py-2 text-xs text-jarvis-text font-mono outline-none focus:border-jarvis-accent/50"
                />
                {cost > 0 && (
                  <p className="text-[10px] text-jarvis-muted mt-1 font-mono">
                    ≈ ₹{cost.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </p>
                )}
              </div>
              <div>
                <label className="text-[10px] text-jarvis-muted block mb-1.5 uppercase tracking-wider">Mode</label>
                <div className="flex gap-1">
                  {(['intraday', 'delivery'] as const).map(m => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={`flex-1 py-2 text-[10px] rounded-lg font-mono transition-all ${
                        mode === m
                          ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30'
                          : 'bg-white/5 text-jarvis-muted border border-transparent'
                      }`}
                    >
                      {m === 'intraday' ? 'Intraday' : 'Delivery'}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-2">
              <button
                onClick={handleTrade}
                disabled={loading || aiLoading}
                className={`flex-1 py-2.5 text-xs font-mono font-bold rounded-lg transition-all flex items-center justify-center gap-2 disabled:opacity-40 ${
                  isBuy
                    ? 'bg-jarvis-neon-green/20 text-jarvis-neon-green border border-jarvis-neon-green/30 hover:bg-jarvis-neon-green/30'
                    : 'bg-jarvis-neon-red/20 text-jarvis-neon-red border border-jarvis-neon-red/30 hover:bg-jarvis-neon-red/30'
                }`}
              >
                {loading ? <RefreshCw size={12} className="animate-spin" /> : <User size={12} />}
                {side} {qty} × {symbol}
              </button>
              <button
                onClick={handleAITrade}
                disabled={loading || aiLoading}
                className="flex-1 py-2.5 text-xs font-mono font-bold rounded-lg bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all flex items-center justify-center gap-2 disabled:opacity-40"
              >
                {aiLoading ? <RefreshCw size={12} className="animate-spin" /> : <Bot size={12} />}
                AI Trade
              </button>
            </div>

            {/* Result */}
            <AnimatePresence>
              {result && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className={`flex items-start gap-2 rounded-lg px-3 py-2.5 text-xs font-mono ${
                    result.ok
                      ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green border border-jarvis-neon-green/20'
                      : 'bg-jarvis-neon-red/10 text-jarvis-neon-red border border-jarvis-neon-red/20'
                  }`}
                >
                  {result.ok
                    ? <CheckCircle2 size={13} className="shrink-0 mt-0.5" />
                    : <AlertCircle size={13} className="shrink-0 mt-0.5" />}
                  {result.msg}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Go to paper trading link */}
            {result?.ok && (
              <button
                onClick={() => {
                  useJarvisStore.getState().setActiveNav('papertrading')
                  closeQuickTrade()
                }}
                className="w-full text-center text-[10px] text-jarvis-accent hover:underline"
              >
                View in Paper Trading →
              </button>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
