'use client'

import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Wallet, Sparkles, RefreshCw } from 'lucide-react'
import { useJarvisStore } from '@/store/jarvisStore'

function ScoreBar({ score }: { score: number }) {
  const color = score >= 70 ? '#10b981' : score >= 45 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-[10px] font-bold" style={{ color }}>{score}</span>
    </div>
  )
}

export function BudgetAdvisorPage() {
  const { budgetAdvice, fetchRecommendations, addToWatchlist } = useJarvisStore()
  const [budget, setBudget] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function run() {
    const b = parseFloat(budget)
    if (isNaN(b) || b <= 0) { setErr('Enter a valid budget amount.'); return }
    setErr('')
    setLoading(true)
    await fetchRecommendations(b)
    setLoading(false)
  }

  const advice = budgetAdvice

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <h1 className="text-sm font-semibold text-jarvis-text flex items-center gap-2">
        <Wallet size={15} className="text-jarvis-accent" /> Budget Advisor
      </h1>

      <div className="glass rounded-xl p-4 space-y-3">
        <div className="text-xs text-jarvis-muted">Enter your investment budget and get AI-curated Nifty 50 picks that fit your budget.</div>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-jarvis-muted text-xs">₹</span>
            <input value={budget} onChange={e => setBudget(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && run()}
              placeholder="e.g. 50000"
              className="w-full bg-white/5 border border-jarvis-border/40 rounded-lg pl-7 pr-3 py-2 text-xs text-jarvis-text placeholder-jarvis-muted focus:outline-none focus:border-jarvis-accent/60" />
          </div>
          <button onClick={run} disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 bg-jarvis-accent/20 hover:bg-jarvis-accent/30 text-jarvis-accent rounded-lg text-xs transition-all disabled:opacity-50">
            {loading ? <RefreshCw size={13} className="animate-spin" /> : <Sparkles size={13} />}
            Analyse
          </button>
        </div>
        {err && <div className="text-[10px] text-jarvis-neon-red">{err}</div>}
      </div>

      {advice && !advice.error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Budget',    value: `₹${advice.budget.toLocaleString('en-IN')}` },
              { label: 'Analysed', value: `${advice.stocks_analyzed} stocks` },
              { label: 'Affordable', value: `${advice.stocks_affordable} stocks` },
            ].map(s => (
              <div key={s.label} className="glass-strong rounded-xl p-3 text-center">
                <div className="text-[10px] text-jarvis-muted mb-1">{s.label}</div>
                <div className="text-xs font-bold text-jarvis-text">{s.value}</div>
              </div>
            ))}
          </div>

          {advice.summary.top_pick && (
            <div className="glass rounded-lg px-3 py-2 text-[11px] text-jarvis-muted">
              Top pick: <span className="text-jarvis-accent font-semibold">{advice.summary.top_pick}</span>
              {advice.summary.avg_score > 0 && <span className="ml-2">Avg score: {advice.summary.avg_score.toFixed(0)}</span>}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {advice.recommendations.map((p, i) => (
              <motion.div key={p.symbol} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
                className="glass-strong rounded-xl p-3 border border-white/5 hover:border-jarvis-accent/30 transition-all">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="text-xs font-bold text-jarvis-text">{p.symbol.replace('.NS', '')}</div>
                    <div className="text-[10px] text-jarvis-muted">{p.name} · {p.sector}</div>
                  </div>
                  <button onClick={() => addToWatchlist({ symbol: p.symbol, name: p.name, addedAt: Date.now() })}
                    className="text-[10px] px-2 py-0.5 bg-jarvis-accent/10 text-jarvis-accent rounded hover:bg-jarvis-accent/20 transition-all">
                    + Watch
                  </button>
                </div>

                <div className="text-sm font-bold text-jarvis-text mb-1">₹{p.price.toFixed(2)}</div>

                <div className="mb-2">
                  <div className="flex justify-between text-[10px] text-jarvis-muted mb-0.5">
                    <span>Score · {p.grade}</span><span>{p.score}/100</span>
                  </div>
                  <ScoreBar score={p.score} />
                </div>

                <div className="grid grid-cols-2 gap-2 text-[10px] mb-2">
                  <div><span className="text-jarvis-muted">Shares: </span><span className="text-jarvis-text font-semibold">{p.qty}</span></div>
                  <div><span className="text-jarvis-muted">Cost: </span><span className="text-jarvis-text font-semibold">₹{(p.cost ?? 0).toFixed(0)}</span></div>
                  <div><span className="text-jarvis-muted">SL: </span><span className="text-jarvis-neon-red font-semibold">₹{(p.stop_loss ?? 0).toFixed(1)}</span></div>
                  <div><span className="text-jarvis-muted">T1: </span><span className="text-jarvis-accent font-semibold">₹{(p.target1 ?? 0).toFixed(1)}</span></div>
                </div>

                {p.reasons.length > 0 && (
                  <div className="text-[10px] text-jarvis-muted line-clamp-2">{p.reasons[0]}</div>
                )}

                <div className="flex items-center justify-between mt-2 text-[10px] text-jarvis-muted">
                  <span>R:R {(p.risk_reward ?? 0).toFixed(1)}x</span>
                  <span className="capitalize">{p.signal ?? '—'} · {p.trend ?? '—'}</span>
                  <span>Conf {p.confidence ?? 0}%</span>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      {advice?.error && (
        <div className="text-jarvis-neon-red text-xs glass rounded-lg p-3">{advice.error}</div>
      )}

      {!advice && !loading && (
        <div className="text-center text-jarvis-muted text-xs py-16">
          <Wallet size={32} className="mx-auto mb-3 opacity-20" />
          <p>Enter your budget above to get personalised stock recommendations.</p>
        </div>
      )}
    </div>
  )
}
