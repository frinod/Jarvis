'use client'

import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, TrendingUp, TrendingDown, Minus, Star, Clock, ShoppingCart } from 'lucide-react'
import { API_URL, useJarvisStore } from '@/store/jarvisStore'

interface TopPick {
  rank: number
  symbol: string
  name: string
  sector: string
  price: number
  change_pct: number
  signal: string
  confidence: number
  score: number
  grade: string
  trend: string
  rsi: number | null
  volume_ratio: number | null
  buy_price: number
  stop_loss: number
  target1: number
  target2: number
  risk_reward: number
  hold_duration: string
  hold_hours: number
  reasons: string[]
  category: 'intraday' | 'swing' | 'longterm'
}

interface TopPicksData {
  generated_at: string
  market_date: string
  intraday: TopPick[]
  swing: TopPick[]
  longterm: TopPick[]
  summary: {
    total_scanned: number
    bullish_count: number
    bearish_count: number
    market_mood: string
  }
}

const GRADE_COLOR: Record<string, string> = {
  'A+': '#30d158', 'A': '#06b6d4', 'B': '#ff9f0a', 'C': '#ff453a', 'D': '#ff453a',
}

const SIG_STYLE: Record<string, string> = {
  BUY:  'bg-jarvis-neon-green/10 text-jarvis-neon-green border-jarvis-neon-green/30',
  SELL: 'bg-jarvis-neon-red/10 text-jarvis-neon-red border-jarvis-neon-red/30',
  HOLD: 'bg-white/5 text-jarvis-muted border-white/10',
}

function PickCard({ pick, rank }: { pick: TopPick; rank: number }) {
  const [expanded, setExpanded] = useState(false)
  const { openQuickTrade, setActiveNav, setSelectedStock } = useJarvisStore()
  const up = pick.change_pct >= 0
  const gc = GRADE_COLOR[pick.grade] ?? '#94a3b8'
  const DirIcon = pick.signal === 'BUY' ? TrendingUp : pick.signal === 'SELL' ? TrendingDown : Minus

  function openStock() {
    setSelectedStock(pick.symbol + (pick.symbol.includes('.') ? '' : '.NS'))
    setActiveNav('stocks')
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: rank * 0.03 }}
      className="glass rounded-xl border border-jarvis-border hover:border-jarvis-accent/20 transition-all cursor-pointer"
      onClick={openStock}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          {/* Rank + Symbol */}
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-black font-mono shrink-0"
              style={{ backgroundColor: `${gc}20`, color: gc }}>
              {rank}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-mono font-bold text-jarvis-accent">{pick.symbol}</span>
                <span className="text-[10px] text-jarvis-muted truncate">{pick.name}</span>
                <span className="text-[10px] bg-white/5 text-jarvis-muted px-1.5 py-0.5 rounded">{pick.sector}</span>
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs font-mono text-jarvis-text">₹{pick.price.toLocaleString('en-IN')}</span>
                <span className={`text-[10px] font-mono ${up ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
                  {up ? '+' : ''}{pick.change_pct.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>

          {/* Signal + Grade */}
          <div className="flex items-center gap-2 shrink-0">
            <span className={`text-[10px] px-2 py-0.5 rounded border font-mono font-bold ${SIG_STYLE[pick.signal] ?? SIG_STYLE.HOLD}`}>
              <DirIcon size={9} className="inline mr-0.5" />{pick.signal}
            </span>
            <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
              style={{ color: gc, backgroundColor: `${gc}15` }}>
              {pick.grade}
            </span>
          </div>
        </div>

        {/* Score bar */}
        <div className="mt-3 flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all" style={{ width: `${pick.score}%`, backgroundColor: gc }} />
          </div>
          <span className="text-[10px] font-mono text-jarvis-muted shrink-0">{pick.score}/100</span>
        </div>

        {/* Key levels row */}
        <div className="grid grid-cols-5 gap-2 mt-3">
          {([
            ['Buy', `₹${pick.buy_price.toLocaleString('en-IN')}`, '#06b6d4'],
            ['SL', `₹${pick.stop_loss.toLocaleString('en-IN')}`, '#ff453a'],
            ['T1', `₹${pick.target1.toLocaleString('en-IN')}`, '#30d158'],
            ['T2', `₹${pick.target2.toLocaleString('en-IN')}`, '#30d158'],
            ['R:R', `1:${pick.risk_reward}`, '#ff9f0a'],
          ] as [string, string, string][]).map(([label, val, color]) => (
            <div key={label} className="text-center">
              <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</p>
              <p className="text-[10px] font-mono font-bold" style={{ color }}>{val}</p>
            </div>
          ))}
        </div>

        {/* Hold duration */}
        <div className="flex items-center gap-2 mt-2.5 pt-2.5 border-t border-jarvis-border/40">
          <Clock size={10} className="text-jarvis-accent shrink-0" />
          <span className="text-[10px] text-jarvis-accent font-mono font-semibold">{pick.hold_duration}</span>
          {pick.rsi !== null && (
            <span className="text-[10px] text-jarvis-muted ml-auto">RSI {pick.rsi.toFixed(0)}</span>
          )}
          {pick.volume_ratio !== null && (
            <span className="text-[10px] text-jarvis-muted">Vol {pick.volume_ratio.toFixed(1)}x</span>
          )}
          <span className="text-[10px] text-jarvis-muted">Conf {pick.confidence}%</span>
        </div>

        {/* Paper Trade button */}
        <button
          onClick={e => {
            e.stopPropagation()
            openQuickTrade({
              symbol: pick.symbol,
              side: pick.signal === 'BUY' ? 'BUY' : 'SELL',
              entry: pick.buy_price,
              stop_loss: pick.stop_loss,
              target1: pick.target1,
              signal: pick.signal,
              confidence: pick.confidence,
              source: 'toppicks',
            })
          }}
          className="mt-2.5 w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[10px] font-mono font-bold transition-all border"
          style={{
            background: pick.signal === 'BUY' ? 'rgba(38,166,154,0.12)' : 'rgba(239,83,80,0.12)',
            color: pick.signal === 'BUY' ? '#26a69a' : '#ef5350',
            borderColor: pick.signal === 'BUY' ? 'rgba(38,166,154,0.25)' : 'rgba(239,83,80,0.25)',
          }}
        >
          <ShoppingCart size={10} /> Paper Trade
        </button>
      </div>

        {/* Expanded reasons */}
        <button
          onClick={e => { e.stopPropagation(); setExpanded(v => !v) }}
          className="w-full text-[10px] text-jarvis-muted hover:text-jarvis-accent transition-colors py-1.5 border-t border-jarvis-border/40 text-center">
          {expanded ? '▲ Hide reasons' : '▼ Why this pick?'}
        </button>
      {expanded && pick.reasons.length > 0 && (
        <div className="px-4 pb-4 border-t border-jarvis-border/40 pt-3">
          <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-2 font-semibold">Why this pick?</p>
          <div className="flex flex-wrap gap-1.5">
            {pick.reasons.map((r, i) => (
              <span key={i} className="text-[10px] bg-white/5 text-jarvis-muted px-2 py-0.5 rounded">{r}</span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  )
}

export function TopPicksPage() {
  const [data, setData] = useState<TopPicksData | null>(null)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<'intraday' | 'swing' | 'longterm'>('intraday')
  const [universe, setUniverse] = useState('nifty50')
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/api/market/top-picks?universe=${universe}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const d = await res.json()
      setData(d)
    } catch (e: any) {
      setError(e.message || 'Failed to load picks')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [universe])

  const picks = data ? data[tab] : []
  const moodColor = data?.summary.market_mood === 'bullish' ? '#30d158'
    : data?.summary.market_mood === 'bearish' ? '#ff453a' : '#ff9f0a'

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Star size={15} className="text-jarvis-accent" />
          <span className="text-sm font-bold text-jarvis-text uppercase tracking-wider">Daily AI Top Picks</span>
          {data && (
            <span className="text-[10px] text-jarvis-muted font-mono">
              {new Date(data.generated_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' })} IST
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Universe */}
          <div className="flex gap-1">
            {(['nifty50', 'nifty100', 'all'] as const).map(u => (
              <button key={u} onClick={() => setUniverse(u)}
                className={`text-[10px] px-2 py-0.5 rounded font-mono transition-all ${universe === u ? 'bg-jarvis-accent text-jarvis-bg font-bold' : 'text-jarvis-muted bg-white/5 hover:text-jarvis-text'}`}>
                {u === 'nifty50' ? 'N50' : u === 'nifty100' ? 'N100' : 'All'}
              </button>
            ))}
          </div>
          <button onClick={load} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-jarvis-accent/20 hover:bg-jarvis-accent/30 text-jarvis-accent rounded-lg text-xs transition-all disabled:opacity-50">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            {loading ? 'Scanning...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Market summary bar */}
      {data?.summary && (
        <div className="glass rounded-xl px-4 py-3 flex items-center gap-6 flex-wrap border border-jarvis-border">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-jarvis-muted">Market Mood</span>
            <span className="text-xs font-mono font-bold capitalize" style={{ color: moodColor }}>
              {data.summary.market_mood}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-jarvis-neon-green" />
            <span className="text-[10px] text-jarvis-muted">{data.summary.bullish_count} Bullish</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-jarvis-neon-red" />
            <span className="text-[10px] text-jarvis-muted">{data.summary.bearish_count} Bearish</span>
          </div>
          <div className="text-[10px] text-jarvis-muted ml-auto">
            Scanned <span className="text-jarvis-accent font-mono">{data.summary.total_scanned}</span> stocks
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-jarvis-border">
        {([
          ['intraday', '⚡ Intraday Top 20', data?.intraday.length ?? 0],
          ['swing',    '📈 Swing Top 10',    data?.swing.length ?? 0],
          ['longterm', '🏦 Long-Term Top 10', data?.longterm.length ?? 0],
        ] as const).map(([key, label, count]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`text-xs px-4 py-2 font-mono transition-all border-b-2 -mb-px flex items-center gap-1.5 ${
              tab === key ? 'border-jarvis-accent text-jarvis-accent' : 'border-transparent text-jarvis-muted hover:text-jarvis-text'
            }`}>
            {label}
            {count > 0 && <span className="text-[9px] bg-jarvis-accent/20 text-jarvis-accent px-1.5 py-0.5 rounded-full font-bold">{count}</span>}
          </button>
        ))}
      </div>

      {/* Hold duration legend */}
      <div className="flex items-center gap-4 text-[10px] text-jarvis-muted">
        <Clock size={10} className="text-jarvis-accent" />
        {tab === 'intraday' && <span>Hold duration = estimated time to reach target within today's session</span>}
        {tab === 'swing' && <span>Hold duration = estimated days to reach swing target (2–10 days)</span>}
        {tab === 'longterm' && <span>Hold duration = estimated weeks/months for long-term target</span>}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-jarvis-muted">
          <RefreshCw size={24} className="animate-spin text-jarvis-accent" />
          <p className="text-sm">Scanning {universe === 'nifty50' ? '50' : universe === 'nifty100' ? '100' : '644'} stocks with AI...</p>
          <p className="text-xs text-jarvis-muted/60">Computing TA · Scoring signals · Ranking picks</p>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="glass rounded-xl p-6 text-center border border-jarvis-neon-red/20">
          <p className="text-jarvis-neon-red text-sm mb-3">{error}</p>
          <button onClick={load} className="px-4 py-1.5 text-xs font-mono rounded bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30">
            Retry
          </button>
        </div>
      )}

      {/* Picks grid */}
      {!loading && !error && picks.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
          {picks.map((pick, i) => (
            <PickCard key={pick.symbol} pick={pick} rank={i + 1} />
          ))}
        </div>
      )}

      {!loading && !error && data && picks.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-jarvis-muted">
          <Star size={40} className="text-jarvis-border" />
          <p className="text-sm">No strong picks found for this category today.</p>
          <p className="text-xs text-jarvis-muted/60">Try a different universe or check back after market opens.</p>
        </div>
      )}

      {!loading && !error && !data && (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-jarvis-muted">
          <Star size={40} className="text-jarvis-border" />
          <p className="text-sm">Click Refresh to scan and rank today's top AI picks</p>
        </div>
      )}
    </div>
  )
}
