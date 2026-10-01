'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { RefreshCw, BarChart2, TrendingUp, TrendingDown, Play } from 'lucide-react'
import { API_URL } from '@/store/jarvisStore'

// ─────────────────────────────────────────────
// B1.1 — TYPES
// ─────────────────────────────────────────────

interface BacktestTrade {
  date: string
  type: 'BUY' | 'SELL'
  price: number
  qty: number
  pnl: number
  charges: number
}

interface BacktestResult {
  strategy: string
  symbol: string
  period: string
  initial_capital: number
  final_value: number
  total_return_pct: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  profit_factor: number
  max_drawdown_pct: number
  sharpe_ratio: number
  avg_profit: number
  avg_loss: number
  total_charges: number
  equity_curve: { date: string; value: number }[]
  trades: BacktestTrade[]
  error?: string
}

interface StrategyCompare {
  strategy: string
  strategy_name?: string
  total_return_pct: number
  annualised_return_pct?: number
  win_rate: number
  sharpe_ratio: number
  max_drawdown_pct: number
  total_trades: number
  profit_factor: number
  final_value?: number
  error?: boolean
}

// ─────────────────────────────────────────────
// B1.1 — API HELPERS
// ─────────────────────────────────────────────

async function apiRunBacktest(
  symbol: string,
  strategy: string,
  period: string,
  capital: number,
): Promise<BacktestResult> {
  const r = await fetch(
    `${API_URL}/api/backtest/run?symbol=${symbol}&strategy=${strategy}&period=${period}&capital=${capital}`,
  )
  return r.json()
}

async function apiCompareStrategies(
  symbol: string,
  period: string,
  capital: number,
): Promise<StrategyCompare[]> {
  const r = await fetch(
    `${API_URL}/api/backtest/compare?symbol=${symbol}&period=${period}&capital=${capital}`,
  )
  const d = await r.json()
  return d.comparison ?? d.results ?? []
}

async function apiGetStrategies(): Promise<string[]> {
  const r = await fetch(`${API_URL}/api/backtest/strategies`)
  const d = await r.json()
  return d.strategies ?? []
}

// ─────────────────────────────────────────────
// SHARED STYLE UTILS
// ─────────────────────────────────────────────

const pnlColor = (v: number) =>
  v > 0 ? 'text-jarvis-neon-green' : v < 0 ? 'text-jarvis-neon-red' : 'text-jarvis-muted'
const pnlSign = (v: number) => (v > 0 ? '+' : '')
const inputCls =
  'bg-white/5 border border-jarvis-border rounded px-3 py-1.5 text-xs font-mono text-jarvis-text outline-none focus:border-jarvis-accent/50 w-full placeholder-jarvis-muted/50'

// ─────────────────────────────────────────────
// B1.2 — STRATEGY SELECTOR + PERIOD PICKER
// ─────────────────────────────────────────────

const STRATEGIES = [
  { id: 'trend_following', label: 'Trend Following' },
  { id: 'mean_reversion',  label: 'Mean Reversion'  },
  { id: 'momentum',        label: 'Momentum'        },
  { id: 'breakout',        label: 'Breakout'        },
  { id: 'swing',           label: 'Swing'           },
  { id: 'ai_hybrid',       label: 'AI Hybrid'       },
]

const PERIODS = [
  { id: '1m', label: '1 Month'  },
  { id: '3m', label: '3 Months' },
  { id: '6m', label: '6 Months' },
  { id: '1y', label: '1 Year'   },
  { id: '3y', label: '3 Years'  },
  { id: '5y', label: '5 Years'  },
]

function BacktestControls({
  symbol, setSymbol,
  strategy, setStrategy,
  period, setPeriod,
  capital, setCapital,
  onRun, onCompare,
  loading, compareLoading,
}: {
  symbol: string;        setSymbol: (v: string) => void
  strategy: string;      setStrategy: (v: string) => void
  period: string;        setPeriod: (v: string) => void
  capital: string;       setCapital: (v: string) => void
  onRun: () => void;     onCompare: () => void
  loading: boolean;      compareLoading: boolean
}) {
  return (
    <div className="glass rounded-xl p-4 border border-jarvis-border space-y-4">
      <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">Backtest Settings</p>

      {/* Symbol + Capital */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] text-jarvis-muted block mb-1">Symbol</label>
          <input className={inputCls} value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} placeholder="RELIANCE" />
        </div>
        <div>
          <label className="text-[10px] text-jarvis-muted block mb-1">Capital (₹)</label>
          <input className={inputCls} type="number" value={capital} onChange={e => setCapital(e.target.value)} placeholder="100000" />
        </div>
      </div>

      {/* Strategy */}
      <div>
        <label className="text-[10px] text-jarvis-muted block mb-2">Strategy</label>
        <div className="flex gap-1 flex-wrap">
          {STRATEGIES.map(s => (
            <button key={s.id} onClick={() => setStrategy(s.id)}
              className={`text-[10px] px-3 py-1.5 rounded font-mono transition-all ${
                strategy === s.id
                  ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30'
                  : 'bg-white/5 text-jarvis-muted hover:text-jarvis-text border border-transparent'
              }`}>{s.label}</button>
          ))}
        </div>
      </div>

      {/* Period */}
      <div>
        <label className="text-[10px] text-jarvis-muted block mb-2">Period</label>
        <div className="flex gap-1 flex-wrap">
          {PERIODS.map(p => (
            <button key={p.id} onClick={() => setPeriod(p.id)}
              className={`text-[10px] px-3 py-1.5 rounded font-mono transition-all ${
                period === p.id
                  ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30'
                  : 'bg-white/5 text-jarvis-muted hover:text-jarvis-text border border-transparent'
              }`}>{p.label}</button>
          ))}
        </div>
      </div>

      {/* Buttons */}
      <div className="flex gap-2">
        <button onClick={onRun} disabled={loading}
          className="flex-1 py-2 text-xs font-mono font-bold rounded bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all flex items-center justify-center gap-2 disabled:opacity-40">
          {loading ? <RefreshCw size={11} className="animate-spin" /> : <Play size={11} />}
          Run Backtest
        </button>
        <button onClick={onCompare} disabled={compareLoading}
          className="flex-1 py-2 text-xs font-mono font-bold rounded bg-white/5 text-jarvis-muted hover:text-jarvis-text border border-jarvis-border transition-all flex items-center justify-center gap-2 disabled:opacity-40">
          {compareLoading ? <RefreshCw size={11} className="animate-spin" /> : <BarChart2 size={11} />}
          Compare All
        </button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
// B1.3 — EQUITY CURVE SVG
// ─────────────────────────────────────────────

function BacktestEquityCurve({
  data, initial,
}: {
  data: { date: string; value: number }[]
  initial: number
}) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; d: { date: string; value: number } } | null>(null)

  if (!data || data.length < 2) return (
    <p className="text-center py-6 text-jarvis-muted text-xs">Not enough data for equity curve</p>
  )

  const W = 800, H = 200
  const PAD = { top: 10, right: 10, bottom: 24, left: 60 }
  const cw = W - PAD.left - PAD.right
  const ch = H - PAD.top - PAD.bottom

  const vals  = data.map(d => d.value)
  const minV  = Math.min(...vals, initial)
  const maxV  = Math.max(...vals, initial)
  const range = maxV - minV || 1

  const xS = (i: number) => PAD.left + (i / Math.max(data.length - 1, 1)) * cw
  const yS = (v: number) => PAD.top + ch - ((v - minV) / range) * ch

  const pts = data.map((d, i) => `${xS(i)},${yS(d.value)}`).join(' ')
  const positive = vals[vals.length - 1] >= initial
  const color = positive ? '#30d158' : '#ff453a'

  const yTicks = Array.from({ length: 4 }, (_, i) => minV + (range / 3) * i)
  const xStep  = Math.max(1, Math.floor(data.length / 6))

  return (
    <div className="relative">
      {tooltip && (
        <div className="absolute top-2 left-16 z-10 glass rounded-lg px-3 py-1.5 border border-jarvis-border pointer-events-none">
          <p className="text-[10px] text-jarvis-accent font-mono">{tooltip.d.date}</p>
          <p className="text-xs font-mono font-bold text-jarvis-text">₹{tooltip.d.value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
          <p className={`text-[10px] font-mono ${pnlColor(tooltip.d.value - initial)}`}>
            {pnlSign(tooltip.d.value - initial)}{(((tooltip.d.value - initial) / initial) * 100).toFixed(2)}%
          </p>
        </div>
      )}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-crosshair"
        style={{ height: 160 }}
        onMouseMove={e => {
          const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
          const mx = ((e.clientX - rect.left) / rect.width) * W
          const idx = Math.max(0, Math.min(data.length - 1, Math.round(((mx - PAD.left) / cw) * (data.length - 1))))
          setTooltip({ x: xS(idx), y: yS(data[idx].value), d: data[idx] })
        }}
        onMouseLeave={() => setTooltip(null)}
      >
        {yTicks.map((v, i) => (
          <g key={i}>
            <line x1={PAD.left} x2={W - PAD.right} y1={yS(v)} y2={yS(v)} stroke="rgba(6,182,212,0.07)" strokeWidth="1" strokeDasharray="4,4" />
            <text x={PAD.left - 4} y={yS(v) + 4} textAnchor="end" fill="rgba(148,163,184,0.7)" fontSize="10" fontFamily="monospace">
              {v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v.toFixed(0)}
            </text>
          </g>
        ))}
        {data.filter((_, i) => i % xStep === 0).map((d, i) => (
          <text key={i} x={xS(i * xStep)} y={H - 4} textAnchor="middle" fill="rgba(148,163,184,0.6)" fontSize="9" fontFamily="monospace">
            {d.date.slice(5)}
          </text>
        ))}
        <defs>
          <linearGradient id="btGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.25" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={`${PAD.left},${PAD.top + ch} ${pts} ${W - PAD.right},${PAD.top + ch}`} fill="url(#btGrad)" />
        <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
        <line x1={PAD.left} x2={W - PAD.right} y1={yS(initial)} y2={yS(initial)} stroke="rgba(148,163,184,0.3)" strokeWidth="1" strokeDasharray="4,3" />
        {tooltip && (
          <g>
            <line x1={tooltip.x} x2={tooltip.x} y1={PAD.top} y2={PAD.top + ch} stroke="rgba(6,182,212,0.5)" strokeWidth="1" strokeDasharray="3,3" />
            <circle cx={tooltip.x} cy={tooltip.y} r="4" fill={color} stroke="rgba(6,182,212,0.3)" strokeWidth="5" />
          </g>
        )}
      </svg>
    </div>
  )
}

// ─────────────────────────────────────────────
// B1.4 — METRICS CARDS
// ─────────────────────────────────────────────

function BacktestMetrics({ result }: { result: BacktestResult }) {
  const cards = [
    { label: 'Total Return',   value: `${pnlSign(result.total_return_pct)}${result.total_return_pct.toFixed(2)}%`,  color: pnlColor(result.total_return_pct) },
    { label: 'Final Value',    value: `₹${result.final_value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: 'text-jarvis-text' },
    { label: 'Win Rate',       value: `${result.win_rate.toFixed(1)}%`,       color: pnlColor(result.win_rate - 50) },
    { label: 'Profit Factor',  value: result.profit_factor.toFixed(2),         color: pnlColor(result.profit_factor - 1) },
    { label: 'Sharpe Ratio',   value: result.sharpe_ratio.toFixed(2),          color: pnlColor(result.sharpe_ratio) },
    { label: 'Max Drawdown',   value: `-${result.max_drawdown_pct.toFixed(2)}%`, color: 'text-jarvis-neon-red' },
    { label: 'Total Trades',   value: String(result.total_trades),             color: 'text-jarvis-text' },
    { label: 'Total Charges',  value: `₹${result.total_charges.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: 'text-jarvis-muted' },
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
      {cards.map(({ label, value, color }) => (
        <div key={label} className="glass rounded-xl p-3 text-center">
          <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</p>
          <p className={`text-sm font-mono font-bold mt-0.5 ${color}`}>{value}</p>
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────
// B1.5 — STRATEGY COMPARISON TABLE
// ─────────────────────────────────────────────

function StrategyCompareTable({ data }: { data: StrategyCompare[] }) {
  if (!data.length) return null
  const valid = data.filter(d => !d.error)
  if (!valid.length) return null
  const best = valid.reduce((a, b) => (a.total_return_pct ?? -Infinity) > (b.total_return_pct ?? -Infinity) ? a : b)
  return (
    <div className="overflow-x-auto">
      <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold mb-3">All Strategies Comparison</p>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-jarvis-border">
            {['Strategy', 'Return %', 'Win Rate', 'Sharpe', 'Max DD', 'Trades', 'P.Factor'].map(h => (
              <th key={h} className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[...data].filter(row => !row.error).sort((a, b) => (b.total_return_pct ?? 0) - (a.total_return_pct ?? 0)).map(row => (
            <tr key={row.strategy}
              className={`border-b border-jarvis-border/40 hover:bg-white/[0.02] transition-colors ${
                row.strategy === best.strategy ? 'bg-jarvis-accent/5' : ''
              }`}>
              <td className="py-2 px-3 font-mono text-jarvis-text capitalize">
                {row.strategy === best.strategy && <span className="text-jarvis-accent mr-1">★</span>}
                {row.strategy.replace(/_/g, ' ')}
              </td>
              <td className={`py-2 px-3 font-mono font-bold ${pnlColor(row.total_return_pct)}`}>
                {pnlSign(row.total_return_pct)}{row.total_return_pct.toFixed(2)}%
              </td>
              <td className={`py-2 px-3 font-mono ${pnlColor(row.win_rate - 50)}`}>{row.win_rate.toFixed(1)}%</td>
              <td className={`py-2 px-3 font-mono ${pnlColor(row.sharpe_ratio)}`}>{row.sharpe_ratio.toFixed(2)}</td>
              <td className="py-2 px-3 font-mono text-jarvis-neon-red">{row.max_drawdown_pct.toFixed(2)}%</td>
              <td className="py-2 px-3 font-mono text-jarvis-muted">{row.total_trades}</td>
              <td className={`py-2 px-3 font-mono ${pnlColor(row.profit_factor - 1)}`}>{row.profit_factor.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─────────────────────────────────────────────
// B1.6 — FINAL ASSEMBLY
// ─────────────────────────────────────────────

export function BacktestPage() {
  const [symbol, setSymbol]           = useState('RELIANCE')
  const [strategy, setStrategy]       = useState('trend_following')
  const [period, setPeriod]           = useState('1y')
  const [capital, setCapital]         = useState('100000')
  const [result, setResult]           = useState<BacktestResult | null>(null)
  const [compareData, setCompareData] = useState<StrategyCompare[]>([])
  const [loading, setLoading]         = useState(false)
  const [compareLoad, setCompareLoad] = useState(false)
  const [error, setError]             = useState('')
  const [activeTab, setActiveTab]     = useState<'result' | 'compare'>('result')

  const handleRun = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await apiRunBacktest(symbol.trim().toUpperCase(), strategy, period, parseFloat(capital) || 100000)
      if (r.error) setError(r.error)
      else { setResult(r); setActiveTab('result') }
    } catch { setError('Backtest failed') }
    finally { setLoading(false) }
  }

  const handleCompare = async () => {
    setCompareLoad(true); setError('')
    try {
      const r = await apiCompareStrategies(symbol.trim().toUpperCase(), period, parseFloat(capital) || 100000)
      setCompareData(r); setActiveTab('compare')
    } catch { setError('Compare failed') }
    finally { setCompareLoad(false) }
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <BarChart2 size={16} className="text-jarvis-accent" />
        <span className="text-sm font-bold text-jarvis-text uppercase tracking-wider">Strategy Backtester</span>
      </div>

      {/* Controls */}
      <BacktestControls
        symbol={symbol}     setSymbol={setSymbol}
        strategy={strategy} setStrategy={setStrategy}
        period={period}     setPeriod={setPeriod}
        capital={capital}   setCapital={setCapital}
        onRun={handleRun}   onCompare={handleCompare}
        loading={loading}   compareLoading={compareLoad}
      />

      {error && (
        <p className="text-xs text-jarvis-neon-red font-mono px-2">{error}</p>
      )}

      {/* Loading */}
      {(loading || compareLoad) && (
        <div className="flex items-center gap-3 py-8 justify-center text-jarvis-muted">
          <RefreshCw size={16} className="animate-spin text-jarvis-accent" />
          <span className="text-sm">{loading ? 'Running backtest on historical data...' : 'Comparing all 6 strategies...'}</span>
        </div>
      )}

      {/* Tabs */}
      {(result || compareData.length > 0) && (
        <div className="flex gap-1 border-b border-jarvis-border">
          {(['result', 'compare'] as const).map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`text-xs px-4 py-2 font-mono transition-all border-b-2 -mb-px ${
                activeTab === t
                  ? 'border-jarvis-accent text-jarvis-accent'
                  : 'border-transparent text-jarvis-muted hover:text-jarvis-text'
              }`}>{t === 'result' ? 'Result' : 'Compare All'}</button>
          ))}
        </div>
      )}

      {/* Result tab */}
      {activeTab === 'result' && result && !loading && (
        <div className="space-y-4">
          <div className="glass rounded-xl p-3 border border-jarvis-border">
            <div className="flex items-center gap-3 mb-1">
              <span className="text-sm font-mono font-bold text-jarvis-accent">{result.symbol}</span>
              <span className="text-xs text-jarvis-muted capitalize">{result.strategy.replace(/_/g, ' ')}</span>
              <span className="text-xs text-jarvis-muted">{result.period}</span>
              {result.total_return_pct >= 0
                ? <TrendingUp size={14} className="text-jarvis-neon-green ml-auto" />
                : <TrendingDown size={14} className="text-jarvis-neon-red ml-auto" />}
            </div>
          </div>
          <BacktestMetrics result={result} />
          <div className="glass rounded-xl p-4">
            <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold mb-3">Equity Curve</p>
            <BacktestEquityCurve data={result.equity_curve} initial={result.initial_capital} />
          </div>
        </div>
      )}

      {/* Compare tab */}
      {activeTab === 'compare' && compareData.length > 0 && !compareLoad && (
        <div className="glass rounded-2xl p-4">
          <StrategyCompareTable data={compareData} />
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && compareData.length === 0 && !compareLoad && (
        <div className="flex flex-col items-center justify-center py-16 gap-3 text-jarvis-muted">
          <BarChart2 size={40} className="text-jarvis-border" />
          <p className="text-sm">Configure settings and run a backtest</p>
          <p className="text-xs text-jarvis-muted/60">6 strategies · 6 periods · realistic charges included</p>
        </div>
      )}
    </div>
  )
}
