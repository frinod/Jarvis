'use client'

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Briefcase, TrendingUp, TrendingDown, RefreshCw,
  Activity, Wallet, BarChart2, Zap, ChevronDown, ChevronUp,
} from 'lucide-react'
import { API_URL } from '@/store/jarvisStore'
import {
  apiListPortfolios, apiGetPerformance,
  pnlColor, pnlSign,
  type PaperPortfolio, type PaperPosition, type PerformanceStats,
} from './PaperTradingPage'

// ── Auto-refresh every 30s ────────────────────────────────────
const REFRESH_MS = 30_000

// ── Equity mini-sparkline ─────────────────────────────────────
function Sparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (data.length < 2) return null
  const W = 120, H = 36
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * W},${H - ((v - min) / range) * H}`)
    .join(' ')
  const color = positive ? '#30d158' : '#ff453a'
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-24 h-9" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`spk-${positive}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${H} ${pts} ${W},${H}`} fill={`url(#spk-${positive})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  )
}

// ── Single position row ───────────────────────────────────────
function PositionRow({ pos }: { pos: PaperPosition }) {
  const pnlPct = pos.avg_price > 0
    ? ((pos.current_price - pos.avg_price) / pos.avg_price) * 100
    : 0
  const invested = pos.avg_price * pos.qty
  const current  = pos.current_price * pos.qty
  const isProfit = pos.unrealised_pnl >= 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between px-4 py-3 border-b border-jarvis-border/30 last:border-0 hover:bg-white/[0.02] transition-colors"
    >
      {/* Symbol + meta */}
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-1.5 h-8 rounded-full shrink-0 ${isProfit ? 'bg-green-500' : 'bg-red-500'}`} />
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono font-bold text-jarvis-accent">{pos.symbol}</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded font-mono bg-white/5 text-jarvis-muted uppercase">
              {pos.trade_mode}
            </span>
            {pos.source === 'ai' && (
              <span className="text-[9px] px-1.5 py-0.5 rounded font-mono bg-jarvis-accent/10 text-jarvis-accent">
                AI
              </span>
            )}
          </div>
          <div className="text-[10px] text-jarvis-muted font-mono mt-0.5">
            {pos.qty} shares · avg ₹{pos.avg_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
        </div>
      </div>

      {/* Price + P&L */}
      <div className="text-right shrink-0">
        <div className="text-sm font-mono font-bold text-jarvis-text">
          ₹{pos.current_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
        </div>
        <div className={`text-xs font-mono font-bold ${pnlColor(pos.unrealised_pnl)}`}>
          {pnlSign(pos.unrealised_pnl)}₹{Math.abs(pos.unrealised_pnl).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          <span className="text-[10px] opacity-70 ml-1">({pnlSign(pnlPct)}{pnlPct.toFixed(2)}%)</span>
        </div>
      </div>

      {/* Invested vs current */}
      <div className="text-right shrink-0 ml-6 hidden md:block">
        <div className="text-[10px] text-jarvis-muted font-mono">
          ₹{invested.toLocaleString('en-IN', { maximumFractionDigits: 0 })} →{' '}
          <span className={pnlColor(pos.unrealised_pnl)}>
            ₹{current.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div className="text-[9px] text-jarvis-muted font-mono mt-0.5">
          charges ₹{pos.charges_paid.toFixed(2)}
        </div>
      </div>
    </motion.div>
  )
}

// ── Portfolio card ────────────────────────────────────────────
function PortfolioCard({
  portfolio, stats, expanded, onToggle,
}: {
  portfolio: PaperPortfolio
  stats: PerformanceStats | null
  expanded: boolean
  onToggle: () => void
}) {
  const ret      = portfolio.total_return_pct ?? 0
  const isProfit = ret >= 0
  const positions = Object.values(portfolio.positions)
  const sparkData = stats?.equity_curve?.map(e => e.value) ?? []

  // Big P&L number colour + glow
  const bigPnlClass = isProfit
    ? 'text-green-400 drop-shadow-[0_0_8px_rgba(48,209,88,0.5)]'
    : 'text-red-400 drop-shadow-[0_0_8px_rgba(255,69,58,0.5)]'

  return (
    <motion.div
      layout
      className="glass rounded-2xl border border-jarvis-border overflow-hidden"
    >
      {/* ── Header ── */}
      <div
        className="p-4 cursor-pointer hover:bg-white/[0.02] transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between gap-4">
          {/* Left: name + meta */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-base font-bold font-mono text-jarvis-text">{portfolio.name}</span>
              <span className={`text-[9px] px-2 py-0.5 rounded-full font-mono font-bold ${
                portfolio.owner === 'ai'
                  ? 'bg-jarvis-accent/15 text-jarvis-accent border border-jarvis-accent/30'
                  : 'bg-white/5 text-jarvis-muted border border-jarvis-border'
              }`}>{portfolio.owner.toUpperCase()}</span>
            </div>
            <div className="text-[10px] text-jarvis-muted font-mono mt-0.5">
              {portfolio.trade_count} trades · {positions.length} open · ID: {portfolio.id}
            </div>
          </div>

          {/* Right: big P&L + sparkline */}
          <div className="flex items-center gap-4 shrink-0">
            <Sparkline data={sparkData} positive={isProfit} />
            <div className="text-right">
              <div className={`text-2xl font-mono font-black ${bigPnlClass}`}>
                {pnlSign(ret)}{ret.toFixed(2)}%
              </div>
              <div className={`text-sm font-mono font-bold ${pnlColor(portfolio.realised_pnl + portfolio.unrealised_pnl)}`}>
                {pnlSign(portfolio.realised_pnl + portfolio.unrealised_pnl)}
                ₹{Math.abs(portfolio.realised_pnl + portfolio.unrealised_pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <div className="text-[9px] text-jarvis-muted font-mono">total P&L</div>
            </div>
            {expanded
              ? <ChevronUp size={16} className="text-jarvis-accent" />
              : <ChevronDown size={16} className="text-jarvis-muted" />}
          </div>
        </div>

        {/* ── Summary stat pills ── */}
        <div className="grid grid-cols-4 md:grid-cols-8 gap-2 mt-4">
          {[
            { label: 'Portfolio Value', value: `₹${(portfolio.total_value ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: 'text-jarvis-text' },
            { label: 'Cash',            value: `₹${(portfolio.cash ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,        color: 'text-jarvis-accent' },
            { label: 'Unrealised',      value: `${pnlSign(portfolio.unrealised_pnl)}₹${Math.abs(portfolio.unrealised_pnl ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: pnlColor(portfolio.unrealised_pnl) },
            { label: 'Realised',        value: `${pnlSign(portfolio.realised_pnl)}₹${Math.abs(portfolio.realised_pnl ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,   color: pnlColor(portfolio.realised_pnl) },
            { label: 'Win Rate',        value: stats ? `${stats.win_rate}%` : '—',                                                        color: stats ? pnlColor(stats.win_rate - 50) : 'text-jarvis-muted' },
            { label: 'Profit Factor',   value: stats ? stats.profit_factor.toFixed(2) : '—',                                              color: stats ? pnlColor(stats.profit_factor - 1) : 'text-jarvis-muted' },
            { label: 'Sharpe',          value: stats ? stats.sharpe_ratio.toFixed(2) : '—',                                               color: stats ? pnlColor(stats.sharpe_ratio) : 'text-jarvis-muted' },
            { label: 'Max DD',          value: stats ? `-${stats.max_drawdown_pct}%` : '—',                                               color: 'text-red-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white/[0.03] rounded-xl p-2 text-center border border-jarvis-border/40">
              <div className="text-[8px] text-jarvis-muted uppercase tracking-wider leading-tight">{label}</div>
              <div className={`text-[11px] font-mono font-bold mt-0.5 ${color}`}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Expanded: positions list ── */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-jarvis-border/40"
          >
            {positions.length === 0 ? (
              <p className="text-center py-6 text-jarvis-muted text-xs">No open positions</p>
            ) : (
              <div>
                <div className="px-4 py-2 flex items-center justify-between">
                  <span className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">
                    Open Positions ({positions.length})
                  </span>
                  <span className={`text-xs font-mono font-bold ${pnlColor(portfolio.unrealised_pnl)}`}>
                    Unrealised: {pnlSign(portfolio.unrealised_pnl)}
                    ₹{Math.abs(portfolio.unrealised_pnl).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                {positions.map(pos => <PositionRow key={pos.symbol} pos={pos} />)}
              </div>
            )}

            {/* Charges breakdown */}
            {stats && stats.closed_trades > 0 && (
              <div className="px-4 py-3 border-t border-jarvis-border/30 bg-white/[0.01]">
                <div className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold mb-2">
                  Closed Trades Summary
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {[
                    { label: 'Closed Trades', value: String(stats.closed_trades),                                                                                                                    color: 'text-jarvis-text' },
                    { label: 'Realised P&L',  value: `${pnlSign(stats.total_realised_pnl)}₹${Math.abs(stats.total_realised_pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,            color: pnlColor(stats.total_realised_pnl) },
                    { label: 'Avg Profit',    value: `₹${stats.avg_profit.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,                                                                   color: 'text-green-400' },
                    { label: 'Avg Loss',      value: `₹${Math.abs(stats.avg_loss).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,                                                           color: 'text-red-400' },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="bg-white/[0.03] rounded-lg p-2 text-center">
                      <div className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</div>
                      <div className={`text-xs font-mono font-bold mt-0.5 ${color}`}>{value}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ── Main PortfolioPage ────────────────────────────────────────
export function PortfolioPage() {
  const [portfolios, setPortfolios]   = useState<PaperPortfolio[]>([])
  const [statsMap, setStatsMap]       = useState<Record<string, PerformanceStats>>({})
  const [expanded, setExpanded]       = useState<string | null>(null)
  const [loading, setLoading]         = useState(false)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      // 1. Fetch all portfolios with live position prices
      const list = await apiListPortfolios()

      // 2. Refresh each portfolio's live prices
      const refreshed = await Promise.all(
        list.map(p =>
          fetch(`${API_URL}/api/paper/portfolio/${p.id}`)
            .then(r => r.json())
            .catch(() => p)
        )
      )
      setPortfolios(refreshed.filter(p => !p.error))

      // 3. Fetch performance stats for each
      const entries = await Promise.all(
        refreshed
          .filter(p => !p.error)
          .map(p =>
            fetch(`${API_URL}/api/paper/performance/${p.id}`)
              .then(r => r.json())
              .then(s => [p.id, s] as [string, PerformanceStats])
              .catch(() => [p.id, null] as [string, null])
          )
      )
      const map: Record<string, PerformanceStats> = {}
      entries.forEach(([id, s]) => { if (s && !(s as any).error) map[id] = s })
      setStatsMap(map)
      setLastRefresh(new Date())
    } catch {}
    finally { setLoading(false) }
  }, [])

  // Initial load + auto-refresh every 30s
  useEffect(() => {
    load()
    timerRef.current = setInterval(load, REFRESH_MS)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [load])

  // ── Aggregate totals across all portfolios ────────────────
  const totalInvested   = portfolios.reduce((a, p) => a + p.initial_balance, 0)
  const totalValue      = portfolios.reduce((a, p) => a + (p.total_value ?? 0), 0)
  const totalUnrealised = portfolios.reduce((a, p) => a + (p.unrealised_pnl ?? 0), 0)
  const totalRealised   = portfolios.reduce((a, p) => a + (p.realised_pnl ?? 0), 0)
  const totalNet        = totalRealised + totalUnrealised
  const totalRetPct     = totalInvested > 0 ? ((totalValue - totalInvested) / totalInvested) * 100 : 0
  const totalPositions  = portfolios.reduce((a, p) => a + Object.keys(p.positions).length, 0)
  const isOverallProfit = totalNet >= 0

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">

      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Briefcase size={16} className="text-jarvis-accent" />
          <span className="text-sm font-bold text-jarvis-text uppercase tracking-wider">Portfolio</span>
          {lastRefresh && (
            <span className="text-[9px] text-jarvis-muted font-mono">
              · updated {lastRefresh.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
            </span>
          )}
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 text-[10px] font-mono px-3 py-1.5 rounded-lg bg-jarvis-accent/10 text-jarvis-accent border border-jarvis-accent/20 hover:bg-jarvis-accent/20 transition-all disabled:opacity-40"
        >
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* ── Overall P&L hero banner ── */}
      {portfolios.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className={`rounded-2xl p-5 border ${
            isOverallProfit
              ? 'bg-green-500/5 border-green-500/20'
              : 'bg-red-500/5 border-red-500/20'
          }`}
        >
          <div className="flex items-center justify-between flex-wrap gap-4">
            {/* Big number */}
            <div>
              <div className="text-[10px] text-jarvis-muted uppercase tracking-wider font-semibold mb-1">
                Total Net P&L (All Portfolios)
              </div>
              <div className={`text-4xl font-black font-mono ${
                isOverallProfit
                  ? 'text-green-400 drop-shadow-[0_0_16px_rgba(48,209,88,0.4)]'
                  : 'text-red-400 drop-shadow-[0_0_16px_rgba(255,69,58,0.4)]'
              }`}>
                {pnlSign(totalNet)}₹{Math.abs(totalNet).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <div className={`text-lg font-mono font-bold mt-1 ${
                isOverallProfit ? 'text-green-400/70' : 'text-red-400/70'
              }`}>
                {pnlSign(totalRetPct)}{totalRetPct.toFixed(2)}% overall return
              </div>
            </div>

            {/* Right side breakdown */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: 'Invested',    value: `₹${totalInvested.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,   icon: Wallet,    color: 'text-jarvis-text' },
                { label: 'Current',     value: `₹${totalValue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,      icon: Activity,  color: 'text-jarvis-text' },
                { label: 'Unrealised',  value: `${pnlSign(totalUnrealised)}₹${Math.abs(totalUnrealised).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, icon: TrendingUp, color: pnlColor(totalUnrealised) },
                { label: 'Realised',    value: `${pnlSign(totalRealised)}₹${Math.abs(totalRealised).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,     icon: BarChart2,  color: pnlColor(totalRealised) },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label} className="glass rounded-xl p-3 text-center min-w-[90px]">
                  <Icon size={12} className="text-jarvis-muted mx-auto mb-1" />
                  <div className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</div>
                  <div className={`text-sm font-mono font-bold mt-0.5 ${color}`}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick stats bar */}
          <div className="flex items-center gap-4 mt-4 pt-3 border-t border-white/5 flex-wrap">
            {[
              { label: 'Portfolios',      value: portfolios.length },
              { label: 'Open Positions',  value: totalPositions },
              { label: 'Total Trades',    value: portfolios.reduce((a, p) => a + p.trade_count, 0) },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center gap-1.5">
                <Zap size={10} className="text-jarvis-accent" />
                <span className="text-[10px] text-jarvis-muted font-mono">{label}:</span>
                <span className="text-[10px] font-mono font-bold text-jarvis-text">{value}</span>
              </div>
            ))}
            <div className="ml-auto text-[9px] text-jarvis-muted font-mono">
              Auto-refreshes every 30s
            </div>
          </div>
        </motion.div>
      )}

      {/* ── Portfolio cards ── */}
      {loading && portfolios.length === 0 ? (
        <div className="flex items-center justify-center py-16 gap-2 text-jarvis-muted text-xs">
          <RefreshCw size={14} className="animate-spin text-jarvis-accent" />
          Loading portfolios...
        </div>
      ) : portfolios.length === 0 ? (
        <div className="text-center py-16 text-jarvis-muted">
          <Briefcase size={40} className="mx-auto mb-3 opacity-20" />
          <p className="text-sm">No portfolios yet.</p>
          <p className="text-xs mt-1">Go to <span className="text-jarvis-accent">Paper Trading</span> to create one.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {portfolios.map(p => (
            <PortfolioCard
              key={p.id}
              portfolio={p}
              stats={statsMap[p.id] ?? null}
              expanded={expanded === p.id}
              onToggle={() => setExpanded(prev => prev === p.id ? null : p.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
