'use client'

import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, RefreshCw, BarChart2, TrendingUp } from 'lucide-react'
import { useJarvisStore } from '@/store/jarvisStore'

function PriceChip({ value }: { value: number }) {
  const pos = value >= 0
  return (
    <span className={`text-xs font-semibold ${pos ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
      {pos ? '+' : ''}{value.toFixed(2)}%
    </span>
  )
}

export function MarketDashboardPage() {
  const { movers, heatmap, depth, fetchMovers, fetchHeatmap, fetchDepth } = useJarvisStore()
  const [depthSymbol, setDepthSymbol] = useState('RELIANCE.NS')
  const [moversTab, setMoversTab] = useState<'gainers' | 'losers' | 'most_active'>('gainers')

  useEffect(() => {
    fetchMovers()
    fetchHeatmap()
    const id = setInterval(() => { fetchMovers(); fetchHeatmap() }, 30000)
    return () => clearInterval(id)
  }, [fetchMovers, fetchHeatmap])

  useEffect(() => {
    fetchDepth(depthSymbol)
    const id = setInterval(() => fetchDepth(depthSymbol), 15000)
    return () => clearInterval(id)
  }, [depthSymbol, fetchDepth])

  const list = movers
    ? moversTab === 'gainers' ? movers.gainers
      : moversTab === 'losers' ? movers.losers
      : movers.most_active
    : []

  const maxHeat = heatmap.length ? Math.max(...heatmap.map(h => Math.abs(h.avg_change_pct))) : 1

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* Movers */}
      <div className="glass rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-jarvis-text flex items-center gap-2">
            <Activity size={15} className="text-jarvis-accent" /> Market Movers
            {movers && (
              <span className="text-[10px] text-jarvis-muted font-normal">
                ▲{movers.advancing} ▼{movers.declining}
              </span>
            )}
          </h2>
          <div className="flex gap-1 items-center">
            <button onClick={() => fetchMovers()} className="text-jarvis-muted hover:text-jarvis-accent transition-colors mr-1">
              <RefreshCw size={13} />
            </button>
            {(['gainers', 'losers', 'most_active'] as const).map(t => (
              <button key={t} onClick={() => setMoversTab(t)}
                className={`px-2 py-0.5 rounded text-[10px] font-medium capitalize transition-all ${moversTab === t ? 'bg-jarvis-accent/20 text-jarvis-accent' : 'text-jarvis-muted hover:text-jarvis-text'}`}>
                {t.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
          {list.slice(0, 10).map((m, i) => (
            <motion.div key={m.symbol} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
              className="glass-strong rounded-lg p-2.5 cursor-pointer hover:border-jarvis-accent/40 border border-transparent transition-all"
              onClick={() => setDepthSymbol(m.symbol)}>
              <div className="text-[11px] font-bold text-jarvis-text truncate">{m.symbol.replace('.NS', '').replace('.BO', '')}</div>
              <div className="text-xs text-jarvis-muted mt-0.5">₹{m.price.toFixed(2)}</div>
              <PriceChip value={m.change_pct} />
              <div className="text-[10px] text-jarvis-muted mt-1">Vol: {(m.volume / 1e6).toFixed(1)}M</div>
            </motion.div>
          ))}
          {list.length === 0 && (
            <div className="col-span-5 text-center text-jarvis-muted text-xs py-6">Loading movers…</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Sector Heatmap */}
        <div className="glass rounded-xl p-4">
          <h2 className="text-sm font-semibold text-jarvis-text flex items-center gap-2 mb-3">
            <BarChart2 size={15} className="text-jarvis-accent2" /> Sector Heatmap
            <button onClick={() => fetchHeatmap()} className="ml-auto text-jarvis-muted hover:text-jarvis-accent transition-colors">
              <RefreshCw size={13} />
            </button>
          </h2>
          <div className="grid grid-cols-2 gap-2">
            {heatmap.map((s, i) => {
              const intensity = Math.abs(s.avg_change_pct) / maxHeat
              const pos = s.avg_change_pct >= 0
              return (
                <motion.div key={s.sector} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.05 }}
                  className="rounded-lg p-2.5 border border-white/5"
                  style={{ background: pos ? `rgba(16,185,129,${0.08 + intensity * 0.25})` : `rgba(239,68,68,${0.08 + intensity * 0.25})` }}>
                  <div className="text-[11px] font-semibold text-jarvis-text">{s.sector}</div>
                  <div className="flex items-center justify-between mt-1">
                    <PriceChip value={s.avg_change_pct} />
                    <span className="text-[10px] text-jarvis-muted">{s.stock_count} stocks</span>
                  </div>
                  <div className="text-[10px] text-jarvis-muted mt-0.5">▲{s.advancing} ▼{s.declining}</div>
                </motion.div>
              )
            })}
            {heatmap.length === 0 && (
              <div className="col-span-2 text-center text-jarvis-muted text-xs py-6">Loading heatmap…</div>
            )}
          </div>
        </div>

        {/* Market Depth */}
        <div className="glass rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-jarvis-text flex items-center gap-2">
              <TrendingUp size={15} className="text-jarvis-accent" /> Market Depth
            </h2>
            <div className="flex items-center gap-2">
              <input value={depthSymbol} onChange={e => setDepthSymbol(e.target.value.toUpperCase())}
                className="bg-white/5 border border-jarvis-border/40 rounded px-2 py-0.5 text-[11px] text-jarvis-text w-32 focus:outline-none focus:border-jarvis-accent/60"
                placeholder="SYMBOL.NS" />
              <button onClick={() => fetchDepth(depthSymbol)} className="text-jarvis-muted hover:text-jarvis-accent transition-colors">
                <RefreshCw size={13} />
              </button>
            </div>
          </div>
          {depth ? (
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <span className="text-lg font-bold text-jarvis-text">₹{depth.price.toFixed(2)}</span>
                <span className="text-xs text-jarvis-muted">Bid: <span className="text-jarvis-neon-green">₹{depth.bid.toFixed(2)}</span></span>
                <span className="text-xs text-jarvis-muted">Ask: <span className="text-jarvis-neon-red">₹{depth.ask.toFixed(2)}</span></span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div>
                  <div className="text-jarvis-neon-green font-semibold mb-1 text-center">BID</div>
                  {depth.bids.map((b, i) => (
                    <div key={i} className="flex justify-between px-1 py-0.5 hover:bg-jarvis-neon-green/5 rounded">
                      <span className="text-jarvis-neon-green">{b.price.toFixed(2)}</span>
                      <span className="text-jarvis-muted">{b.qty}</span>
                    </div>
                  ))}
                </div>
                <div>
                  <div className="text-jarvis-neon-red font-semibold mb-1 text-center">ASK</div>
                  {depth.asks.map((a, i) => (
                    <div key={i} className="flex justify-between px-1 py-0.5 hover:bg-jarvis-neon-red/5 rounded">
                      <span className="text-jarvis-neon-red">{a.price.toFixed(2)}</span>
                      <span className="text-jarvis-muted">{a.qty}</span>
                    </div>
                  ))}
                </div>
              </div>
              {depth.note && (
                <div className="text-[10px] text-jarvis-muted border-t border-jarvis-border/20 pt-2">{depth.note}</div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-32 text-jarvis-muted text-xs">Loading depth…</div>
          )}
        </div>
      </div>
    </div>
  )
}
