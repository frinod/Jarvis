'use client'

import React, { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Zap, RefreshCw, Layers, Clock, TrendingUp, TrendingDown, Minus, ShoppingCart } from 'lucide-react'
import { useJarvisStore, API_URL } from '@/store/jarvisStore'

const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h']

const SIGNAL_STYLE: Record<string, string> = {
  BUY:         'bg-jarvis-neon-green/20 text-jarvis-neon-green border-jarvis-neon-green/40',
  SELL:        'bg-jarvis-neon-red/20 text-jarvis-neon-red border-jarvis-neon-red/40',
  HOLD:        'bg-white/10 text-jarvis-muted border-white/20',
  WAIT:        'bg-yellow-500/20 text-yellow-400 border-yellow-500/40',
  STRONG_BUY:  'bg-jarvis-neon-green/30 text-jarvis-neon-green border-jarvis-neon-green/60',
  STRONG_SELL: 'bg-jarvis-neon-red/30 text-jarvis-neon-red border-jarvis-neon-red/60',
  MIXED:       'bg-white/10 text-jarvis-muted border-white/20',
}

const SIG_COLOR: Record<string, string> = {
  buy:     'bg-jarvis-neon-green/10 text-jarvis-neon-green',
  sell:    'bg-jarvis-neon-red/10 text-jarvis-neon-red',
  hold:    'bg-white/5 text-jarvis-muted',
  confirm: 'bg-jarvis-accent/10 text-jarvis-accent',
}

interface ConfluenceRow {
  timeframe: string
  signal?: string
  confidence?: number
  trend?: string
  rsi?: number
  entry?: number
  stop_loss?: number
  target1?: number
  risk_reward?: number
  momentum?: string
  volume_confirmation?: boolean
  error?: boolean
}

interface ConfluenceData {
  symbol: string
  confluence: ConfluenceRow[]
  verdict: string
  buy_count: number
  sell_count: number
  hold_count: number
}

function ConfluencePanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<ConfluenceData | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!symbol) return
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/market/confluence/${symbol}`)
      const d = await res.json()
      setData(d)
    } catch {}
    setLoading(false)
  }, [symbol])

  useEffect(() => { load() }, [load])

  const verdictStyle = SIGNAL_STYLE[data?.verdict ?? 'HOLD'] ?? SIGNAL_STYLE.HOLD
  const VerdictIcon = data?.verdict?.includes('BUY') ? TrendingUp
    : data?.verdict?.includes('SELL') ? TrendingDown : Minus

  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers size={13} className="text-jarvis-accent" />
          <span className="text-[11px] font-semibold text-jarvis-accent uppercase tracking-wider">Multi-Timeframe Confluence</span>
        </div>
        <button onClick={load} disabled={loading}
          className="text-jarvis-muted hover:text-jarvis-accent transition-colors">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {loading && !data && (
        <div className="flex items-center justify-center py-6 text-jarvis-muted text-xs gap-2">
          <RefreshCw size={13} className="animate-spin" /> Analysing 4 timeframes...
        </div>
      )}

      {data && (
        <>
          {/* Verdict */}
          <div className={`flex items-center justify-between rounded-lg px-3 py-2 border ${verdictStyle}`}>
            <div className="flex items-center gap-2">
              <VerdictIcon size={14} />
              <span className="text-xs font-mono font-bold">Confluence: {data.verdict}</span>
            </div>
            <div className="flex items-center gap-3 text-[10px]">
              <span className="text-jarvis-neon-green">{data.buy_count} BUY</span>
              <span className="text-jarvis-neon-red">{data.sell_count} SELL</span>
              <span className="text-jarvis-muted">{data.hold_count} HOLD</span>
            </div>
          </div>

          {/* Timeframe grid */}
          <div className="grid grid-cols-2 gap-2">
            {data.confluence.map((row) => {
              if (row.error) return (
                <div key={row.timeframe} className="glass rounded-lg p-3 border border-jarvis-border opacity-40">
                  <span className="text-[10px] font-mono text-jarvis-muted">{row.timeframe} — no data</span>
                </div>
              )
              const sigStyle = SIGNAL_STYLE[row.signal ?? 'HOLD'] ?? SIGNAL_STYLE.HOLD
              const trendUp = row.trend?.includes('up')
              return (
                <div key={row.timeframe} className={`rounded-lg p-3 border ${sigStyle} bg-opacity-10`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-mono font-bold text-jarvis-text">{row.timeframe}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono font-bold ${sigStyle}`}>
                      {row.signal}
                    </span>
                  </div>
                  <div className="space-y-1 text-[10px]">
                    <div className="flex justify-between">
                      <span className="text-jarvis-muted">Conf</span>
                      <span className="font-mono text-jarvis-text">{row.confidence}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-jarvis-muted">Trend</span>
                      <span className={`font-mono capitalize ${trendUp ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
                        {row.trend?.replace(/_/g, ' ')}
                      </span>
                    </div>
                    {row.rsi !== null && row.rsi !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-jarvis-muted">RSI</span>
                        <span className={`font-mono ${(row.rsi ?? 50) < 30 ? 'text-jarvis-neon-green' : (row.rsi ?? 50) > 70 ? 'text-jarvis-neon-red' : 'text-jarvis-text'}`}>
                          {row.rsi?.toFixed(0)}
                        </span>
                      </div>
                    )}
                    {row.entry !== null && row.entry !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-jarvis-muted">Entry</span>
                        <span className="font-mono text-jarvis-accent">₹{row.entry?.toFixed(2)}</span>
                      </div>
                    )}
                    {row.stop_loss !== null && row.stop_loss !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-jarvis-muted">SL</span>
                        <span className="font-mono text-jarvis-neon-red">₹{row.stop_loss?.toFixed(2)}</span>
                      </div>
                    )}
                    {row.risk_reward !== null && row.risk_reward !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-jarvis-muted">R:R</span>
                        <span className="font-mono text-jarvis-text">{row.risk_reward?.toFixed(1)}x</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-jarvis-muted">Vol</span>
                      <span className={`font-mono ${row.volume_confirmation ? 'text-jarvis-neon-green' : 'text-jarvis-muted'}`}>
                        {row.volume_confirmation ? '✓ Confirmed' : '—'}
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

export function IntradayAssistantPage() {
  const { intradaySignal, fetchIntradaySignal, openQuickTrade } = useJarvisStore()
  const [symbol, setSymbol] = useState('RELIANCE.NS')
  const [tf, setTf] = useState('5m')
  const [loading, setLoading] = useState(false)
  const [showConfluence, setShowConfluence] = useState(false)
  const [countdown, setCountdown] = useState(60)

  async function load(sym = symbol, timeframe = tf) {
    setLoading(true)
    await fetchIntradaySignal(sym, timeframe)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    setCountdown(60)
    const ticker = setInterval(() => setCountdown(c => Math.max(0, c - 1)), 1000)
    const refresher = setInterval(() => { load(); setCountdown(60) }, 60000)
    return () => { clearInterval(ticker); clearInterval(refresher) }
  }, [symbol, tf])

  const s = intradaySignal

  const signalsList: { indicator: string; signal: string; reason: string }[] =
    Array.isArray(s?.signals)
      ? (s!.signals as any[]).map(sig =>
          typeof sig === 'string'
            ? { indicator: '', signal: sig, reason: '' }
            : { indicator: sig.indicator ?? '', signal: sig.signal ?? '', reason: sig.reason ?? '' }
        )
      : []

  // Hold duration estimate from signal data
  const holdDuration = (() => {
    if (!s || 'error' in s) return null
    const atr = (s.target1 - s.entry) / 2 || s.price * 0.01
    const moveNeeded = Math.abs(s.target1 - s.price)
    const avgMovePerHour = atr * 0.5
    const hours = Math.max(0.5, Math.min(moveNeeded / avgMovePerHour, 6))
    if (hours < 1) return `~${Math.round(hours * 60)} min`
    return `~${hours.toFixed(1)}h`
  })()

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <h1 className="text-sm font-semibold text-jarvis-text flex items-center gap-2">
        <Zap size={15} className="text-jarvis-accent" /> Intraday Assistant
        <span className="ml-auto text-[10px] font-mono text-jarvis-muted flex items-center gap-1">
          <Clock size={9} className="text-jarvis-accent" />
          {loading ? 'Refreshing...' : `Auto-refresh in ${countdown}s`}
        </span>
      </h1>

      <div className="flex gap-2 flex-wrap">
        <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())}
          placeholder="Symbol (e.g. INFY.NS)"
          className="bg-white/5 border border-jarvis-border/40 rounded-lg px-3 py-2 text-xs text-jarvis-text placeholder-jarvis-muted focus:outline-none focus:border-jarvis-accent/60 w-40" />
        <div className="flex gap-1">
          {TIMEFRAMES.map(t => (
            <button key={t} onClick={() => setTf(t)}
              className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all ${tf === t ? 'bg-jarvis-accent/20 text-jarvis-accent' : 'bg-white/5 text-jarvis-muted hover:text-jarvis-text'}`}>
              {t}
            </button>
          ))}
        </div>
        <button onClick={() => load(symbol, tf)} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-jarvis-accent/20 hover:bg-jarvis-accent/30 text-jarvis-accent rounded-lg text-xs transition-all disabled:opacity-50">
          {loading ? <RefreshCw size={13} className="animate-spin" /> : <Zap size={13} />}
          Analyse
        </button>
        <button onClick={() => setShowConfluence(v => !v)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all ${showConfluence ? 'bg-jarvis-accent/20 text-jarvis-accent' : 'bg-white/5 text-jarvis-muted hover:text-jarvis-text'}`}>
          <Layers size={13} />
          Confluence
        </button>
      </div>

      {loading && !s && (
        <div className="flex items-center justify-center h-48 text-jarvis-muted text-xs">
          <RefreshCw size={16} className="animate-spin mr-2" /> Analysing…
        </div>
      )}

      {s && !('error' in s) ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
          {/* Main signal card */}
          <div className="glass rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-sm font-bold text-jarvis-text">{s.symbol.replace('.NS', '').replace('.BO', '')}</div>
                <div className="text-[10px] text-jarvis-muted">{s.timeframe} · {new Date(s.updated_at * 1000).toLocaleTimeString()}</div>
              </div>
              <span className={`px-2 py-0.5 rounded border text-xs font-bold ${SIGNAL_STYLE[s.signal] ?? SIGNAL_STYLE.HOLD}`}>
                {s.signal}
              </span>
            </div>

            <div className="text-2xl font-bold text-jarvis-text mb-3">₹{s.price.toFixed(2)}</div>

            <div className="grid grid-cols-4 gap-2 text-[11px]">
              <div className="bg-jarvis-neon-green/10 rounded-lg p-2 text-center">
                <div className="text-jarvis-muted text-[10px]">Entry</div>
                <div className="text-jarvis-neon-green font-bold">₹{s.entry.toFixed(2)}</div>
              </div>
              <div className="bg-jarvis-neon-red/10 rounded-lg p-2 text-center">
                <div className="text-jarvis-muted text-[10px]">Stop Loss</div>
                <div className="text-jarvis-neon-red font-bold">₹{s.stop_loss.toFixed(2)}</div>
              </div>
              <div className="bg-jarvis-accent/10 rounded-lg p-2 text-center">
                <div className="text-jarvis-muted text-[10px]">Target 1</div>
                <div className="text-jarvis-accent font-bold">₹{s.target1.toFixed(2)}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-2 text-center">
                <div className="text-jarvis-muted text-[10px]">Target 2</div>
                <div className="text-jarvis-text font-bold">₹{s.target2.toFixed(2)}</div>
              </div>
            </div>

            <div className="grid grid-cols-5 gap-2 mt-3 text-[10px] text-center">
              <div><span className="text-jarvis-muted">R:R </span><span className="text-jarvis-text font-semibold">{s.risk_reward.toFixed(1)}x</span></div>
              <div><span className="text-jarvis-muted">Conf </span><span className="text-jarvis-text font-semibold">{s.confidence}%</span></div>
              <div><span className="text-jarvis-muted">RSI </span><span className="text-jarvis-text font-semibold">{s.rsi.toFixed(0)}</span></div>
              <div><span className="text-jarvis-muted">Trend </span><span className="text-jarvis-text font-semibold capitalize">{s.trend}</span></div>
              {holdDuration && (
                <div className="flex items-center justify-center gap-1">
                  <Clock size={9} className="text-jarvis-accent" />
                  <span className="text-jarvis-accent font-semibold">{holdDuration}</span>
                </div>
              )}
            </div>

            {/* Hold duration prediction */}
            {holdDuration && (
              <div className="mt-3 pt-3 border-t border-jarvis-border/40 flex items-center gap-2">
                <Clock size={11} className="text-jarvis-accent shrink-0" />
                <span className="text-[11px] text-jarvis-accent font-mono font-semibold">
                  Buy at ₹{s.entry.toFixed(2)} · Hold {holdDuration} · Sell at ₹{s.target1.toFixed(2)}
                </span>
              </div>
            )}

            {/* Paper Trade button */}
            {s.signal !== 'HOLD' && (
              <button
                onClick={() => openQuickTrade({
                  symbol: s.symbol.replace('.NS', '').replace('.BO', ''),
                  side: s.signal === 'BUY' || s.signal === 'STRONG_BUY' ? 'BUY' : 'SELL',
                  entry: s.entry,
                  stop_loss: s.stop_loss,
                  target1: s.target1,
                  signal: s.signal,
                  confidence: s.confidence,
                  source: 'intraday',
                })}
                className="mt-3 w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-mono font-bold transition-all border"
                style={{
                  background: s.signal.includes('BUY') ? 'rgba(38,166,154,0.15)' : 'rgba(239,83,80,0.15)',
                  color: s.signal.includes('BUY') ? '#26a69a' : '#ef5350',
                  borderColor: s.signal.includes('BUY') ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
                }}
              >
                <ShoppingCart size={12} />
                Paper Trade this signal
              </button>
            )}
          </div>

          {/* Multi-timeframe confluence */}
          {showConfluence && <ConfluencePanel symbol={symbol} />}

          {/* Details */}
          <div className="glass rounded-xl p-3">
            <div className="text-[11px] font-semibold text-jarvis-muted mb-2">Signal Details</div>
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div><span className="text-jarvis-muted">Action: </span><span className="text-jarvis-text capitalize">{s.action}</span></div>
              <div><span className="text-jarvis-muted">Momentum: </span><span className="text-jarvis-text capitalize">{s.momentum}</span></div>
              <div><span className="text-jarvis-muted">Vol Confirm: </span><span className={s.volume_confirmation ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}>{s.volume_confirmation ? 'Yes' : 'No'}</span></div>
              {s.nearest_support !== null && s.nearest_support !== undefined && (
                <div><span className="text-jarvis-muted">Support: </span><span className="text-jarvis-neon-green">₹{(s.nearest_support as number).toFixed(2)}</span></div>
              )}
              {s.nearest_resistance !== null && s.nearest_resistance !== undefined && (
                <div><span className="text-jarvis-muted">Resistance: </span><span className="text-jarvis-neon-red">₹{(s.nearest_resistance as number).toFixed(2)}</span></div>
              )}
            </div>
          </div>

          {/* Indicator signals */}
          {signalsList.length > 0 && (
            <div className="glass rounded-xl p-3">
              <div className="text-[11px] font-semibold text-jarvis-muted mb-2">Indicator Signals</div>
              <div className="space-y-1.5">
                {signalsList.map((sig, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold shrink-0 capitalize ${SIG_COLOR[sig.signal] ?? SIG_COLOR.hold}`}>
                      {sig.signal.toUpperCase()}
                    </span>
                    {sig.indicator && <span className="text-[10px] text-jarvis-muted shrink-0 w-20 truncate">{sig.indicator}</span>}
                    {sig.reason && <span className="text-[10px] text-jarvis-text">{sig.reason}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      ) : (
        s && 'error' in s && (
          <div className="text-center text-jarvis-neon-red text-xs py-8 glass rounded-xl p-4">
            {(s as any).error === 'insufficient_data'
              ? 'Not enough data for this symbol/timeframe. Try a different timeframe or symbol.'
              : String((s as any).error)}
          </div>
        )
      )}

      {!s && !loading && (
        <div className="text-center text-jarvis-muted text-xs py-16">
          <Zap size={32} className="mx-auto mb-3 opacity-20" />
          <p>Enter a symbol and click Analyse to get intraday signals.</p>
        </div>
      )}
    </div>
  )
}
