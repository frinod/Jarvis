'use client'

import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Sparkles, RefreshCw, Plus, ShoppingCart } from 'lucide-react'
import { useJarvisStore } from '@/store/jarvisStore'

const CATEGORIES = [
  { id: 'intraday', label: 'Intraday' },
  { id: 'swing',    label: 'Swing'    },
  { id: 'momentum', label: 'Momentum' },
  { id: 'breakout', label: 'Breakout' },
  { id: 'value',    label: 'Value'    },
  { id: 'growth',   label: 'Growth'   },
  { id: 'dividend', label: 'Dividend' },
  { id: 'longterm', label: 'Long Term'},
]

function ScoreBar({ score }: { score: number }) {
  const color = score >= 70 ? '#10b981' : score >= 45 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-[10px] font-bold" style={{ color }}>{score}</span>
    </div>
  )
}

export function AIDiscoveryPage() {
  const { discovery, fetchDiscovery, addToWatchlist, openQuickTrade, setActiveNav, setSelectedStock } = useJarvisStore()
  const [cat, setCat] = useState('intraday')
  const [loading, setLoading] = useState(false)

  function openStock(symbol: string) {
    setSelectedStock(symbol)
    setActiveNav('stocks')
  }

  async function load(c: string) {
    setLoading(true)
    await fetchDiscovery(c)
    setLoading(false)
  }

  useEffect(() => { load(cat) }, [cat])

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold text-jarvis-text flex items-center gap-2">
          <Sparkles size={15} className="text-jarvis-accent" /> AI Stock Discovery
        </h1>
        <button onClick={() => load(cat)} className="text-jarvis-muted hover:text-jarvis-accent transition-colors">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {CATEGORIES.map(c => (
          <button key={c.id} onClick={() => setCat(c.id)}
            className={`px-3 py-1 rounded-full text-[11px] font-medium transition-all ${cat === c.id ? 'bg-jarvis-accent text-black' : 'bg-white/5 text-jarvis-muted hover:text-jarvis-text hover:bg-white/10'}`}>
            {c.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-jarvis-muted text-xs">
          <RefreshCw size={16} className="animate-spin mr-2" /> Scanning market…
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {discovery.map((s, i) => (
            <motion.div key={s.symbol} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className="glass-strong rounded-xl p-3 border border-white/5 hover:border-jarvis-accent/30 transition-all cursor-pointer"
              onClick={() => openStock(s.symbol)}>
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="text-xs font-bold text-jarvis-text">{s.symbol.replace('.NS', '').replace('.BO', '')}</div>
                  <div className="text-[10px] text-jarvis-muted">{s.name} · {s.sector}</div>
                </div>
                <div className="flex items-center gap-1">
                  <span className={`text-[10px] font-semibold ${s.change_pct >= 0 ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
                    {s.change_pct >= 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
                  </span>
                  <button onClick={(e) => { e.stopPropagation(); addToWatchlist({ symbol: s.symbol, name: s.name, addedAt: Date.now() }) }}
                    className="text-jarvis-muted hover:text-jarvis-accent transition-colors ml-1">
                    <Plus size={12} />
                  </button>
                </div>
              </div>

              <div className="text-sm font-bold text-jarvis-text mb-2">₹{s.price.toFixed(2)}</div>

              <div className="mb-2">
                <div className="flex justify-between text-[10px] text-jarvis-muted mb-1">
                  <span>AI Score</span>
                  <span className="capitalize">{s.grade} · {s.signal}</span>
                </div>
                <ScoreBar score={s.score} />
              </div>

              {s.reasons.length > 0 && (
                <div className="text-[10px] text-jarvis-muted mb-2 line-clamp-2">{s.reasons[0]}</div>
              )}

              <div className="grid grid-cols-2 gap-1 text-[10px]">
                <div className="bg-jarvis-neon-red/10 rounded p-1 text-center">
                  <div className="text-jarvis-muted">SL</div>
                  <div className="text-jarvis-neon-red font-semibold">₹{s.stop_loss.toFixed(1)}</div>
                </div>
                <div className="bg-jarvis-accent/10 rounded p-1 text-center">
                  <div className="text-jarvis-muted">T1</div>
                  <div className="text-jarvis-accent font-semibold">₹{s.target1.toFixed(1)}</div>
                </div>
              </div>

              <div className="flex items-center justify-between mt-2 text-[10px] text-jarvis-muted">
                <span>R:R {(s.risk_reward ?? 0).toFixed(1)}x</span>
                <span>RSI {s.rsi != null ? s.rsi.toFixed(0) : 'N/A'}</span>
                <span>Vol×{s.volume_ratio != null ? s.volume_ratio.toFixed(1) : 'N/A'}</span>
                <span className="capitalize px-1.5 py-0.5 rounded bg-white/5">{s.trend}</span>
              </div>

              {/* Paper Trade */}
              <button
                onClick={(e) => { e.stopPropagation(); openQuickTrade({
                  symbol: s.symbol.replace('.NS', '').replace('.BO', ''),
                  side: s.signal === 'BUY' ? 'BUY' : 'SELL',
                  entry: s.target1 ? s.stop_loss + (s.target1 - s.stop_loss) * 0.1 : s.price,
                  stop_loss: s.stop_loss,
                  target1: s.target1,
                  signal: s.signal,
                  confidence: s.confidence,
                  source: 'discovery',
                }) }}
                className="mt-2 w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[10px] font-mono font-bold transition-all border"
                style={{
                  background: s.signal === 'BUY' ? 'rgba(38,166,154,0.12)' : 'rgba(239,83,80,0.12)',
                  color: s.signal === 'BUY' ? '#26a69a' : '#ef5350',
                  borderColor: s.signal === 'BUY' ? 'rgba(38,166,154,0.25)' : 'rgba(239,83,80,0.25)',
                }}
              >
                <ShoppingCart size={10} /> Paper Trade
              </button>
            </motion.div>
          ))}
          {!loading && discovery.length === 0 && (
            <div className="col-span-3 text-center text-jarvis-muted text-xs py-12">No stocks found for this category.</div>
          )}
        </div>
      )}
    </div>
  )
}
