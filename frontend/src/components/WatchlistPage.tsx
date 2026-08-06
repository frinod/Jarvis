'use client'

import React, { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Star, Plus, Trash2, Bell, BellOff, RefreshCw } from 'lucide-react'
import { useJarvisStore, API_URL } from '@/store/jarvisStore'

export function WatchlistPage() {
  const { watchlist, addToWatchlist, removeFromWatchlist, setWatchlistAlert, stocks, fetchStocks, setActiveNav, setSelectedStock } = useJarvisStore()

  function openStock(symbol: string) {
    setSelectedStock(symbol)
    setActiveNav('stocks')
  }
  const [input, setInput] = useState('')
  const [alertInputs, setAlertInputs] = useState<Record<string, { above: string; below: string }>>({})
  const [refreshing, setRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    setRefreshing(true)
    await fetchStocks('nifty50').catch(() => {})
    setRefreshing(false)
  }, [fetchStocks])

  function add() {
    const sym = input.trim().toUpperCase()
    if (!sym) return
    const s = sym.includes('.') ? sym : `${sym}.NS`
    addToWatchlist({ symbol: s, name: s.replace('.NS', '').replace('.BO', ''), addedAt: Date.now() })
    setInput('')
  }

  function getLive(symbol: string) {
    return stocks.find(s => s.symbol === symbol)
  }

  function getAlertInput(symbol: string) {
    return alertInputs[symbol] ?? { above: '', below: '' }
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold text-jarvis-text flex items-center gap-2">
          <Star size={15} className="text-jarvis-accent" /> Watchlist
        </h1>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-jarvis-muted">{watchlist.length} stocks</span>
          <button onClick={refresh} disabled={refreshing} className="text-jarvis-muted hover:text-jarvis-accent transition-colors disabled:opacity-40">
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      <div className="flex gap-2">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
          placeholder="Add symbol (e.g. INFY or INFY.NS)"
          className="flex-1 bg-white/5 border border-jarvis-border/40 rounded-lg px-3 py-2 text-xs text-jarvis-text placeholder-jarvis-muted focus:outline-none focus:border-jarvis-accent/60" />
        <button onClick={add} className="px-3 py-2 bg-jarvis-accent/20 hover:bg-jarvis-accent/30 text-jarvis-accent rounded-lg transition-all">
          <Plus size={14} />
        </button>
      </div>

      {watchlist.length === 0 ? (
        <div className="text-center text-jarvis-muted text-xs py-16">
          <Star size={32} className="mx-auto mb-3 opacity-20" />
          <p>Your watchlist is empty. Add symbols above to track them.</p>
        </div>
      ) : (
        <div className="space-y-2">
          <AnimatePresence>
            {watchlist.map(item => {
              const live = getLive(item.symbol)
              const pos = live ? live.change_pct >= 0 : true
              const ai = getAlertInput(item.symbol)
              return (
                <motion.div key={item.symbol}
                  initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }}
                  className="glass-strong rounded-xl p-3 border border-white/5 hover:border-jarvis-accent/20 transition-all cursor-pointer"
                  onClick={() => openStock(item.symbol)}>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-bold text-jarvis-text">{item.symbol.replace('.NS', '').replace('.BO', '')}</div>
                      <div className="text-[10px] text-jarvis-muted">{item.name}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      {live ? (
                        <div className="text-right">
                          <div className="text-xs font-bold text-jarvis-text">₹{live.price.toFixed(2)}</div>
                          <div className={`text-[10px] font-semibold ${pos ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
                            {pos ? '+' : ''}{live.change_pct.toFixed(2)}%
                          </div>
                        </div>
                      ) : (
                        <div className="text-[10px] text-jarvis-muted">No live data</div>
                      )}
                      <button onClick={(e) => { e.stopPropagation(); removeFromWatchlist(item.symbol) }}
                        className="text-jarvis-muted hover:text-jarvis-neon-red transition-colors">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Alert row */}
                  <div className="flex items-center gap-2 mt-2 pt-2 border-t border-jarvis-border/20" onClick={e => e.stopPropagation()}>
                    <Bell size={11} className={(item.alertAbove || item.alertBelow) ? 'text-jarvis-accent' : 'text-jarvis-muted'} />
                    <input
                      value={ai.above}
                      onChange={e => setAlertInputs(p => ({ ...p, [item.symbol]: { ...getAlertInput(item.symbol), above: e.target.value } }))}
                      placeholder="Alert above ₹"
                      className="flex-1 bg-white/5 border border-jarvis-border/30 rounded px-2 py-0.5 text-[10px] text-jarvis-text placeholder-jarvis-muted focus:outline-none focus:border-jarvis-accent/50" />
                    <input
                      value={ai.below}
                      onChange={e => setAlertInputs(p => ({ ...p, [item.symbol]: { ...getAlertInput(item.symbol), below: e.target.value } }))}
                      placeholder="Alert below ₹"
                      className="flex-1 bg-white/5 border border-jarvis-border/30 rounded px-2 py-0.5 text-[10px] text-jarvis-text placeholder-jarvis-muted focus:outline-none focus:border-jarvis-accent/50" />
                    <button
                      onClick={async () => {
                        const above = parseFloat(ai.above)
                        const below = parseFloat(ai.below)
                        const a = isNaN(above) ? undefined : above
                        const b = isNaN(below) ? undefined : below
                        setWatchlistAlert(item.symbol, a, b)
                        // sync to backend alert engine
                        await fetch(`${API_URL}/api/alerts/set`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ symbol: item.symbol, above: a ?? null, below: b ?? null }),
                        }).catch(() => {})
                        setAlertInputs(p => ({ ...p, [item.symbol]: { above: '', below: '' } }))
                      }}
                      className="text-[10px] px-2 py-0.5 bg-jarvis-accent/20 text-jarvis-accent rounded hover:bg-jarvis-accent/30 transition-all">
                      Set
                    </button>
                    {(item.alertAbove || item.alertBelow) && (
                      <button onClick={() => setWatchlistAlert(item.symbol, undefined, undefined)}
                        className="text-jarvis-muted hover:text-jarvis-neon-red transition-colors">
                        <BellOff size={11} />
                      </button>
                    )}
                  </div>
                  {(item.alertAbove || item.alertBelow) && (
                    <div className="text-[10px] text-jarvis-accent mt-1 flex gap-3">
                      {item.alertAbove && <span>▲ Above ₹{item.alertAbove}</span>}
                      {item.alertBelow && <span>▼ Below ₹{item.alertBelow}</span>}
                    </div>
                  )}
                </motion.div>
              )
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
