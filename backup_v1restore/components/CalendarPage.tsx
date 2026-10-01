'use client'

import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { CalendarDays, RefreshCw, AlertCircle, Info } from 'lucide-react'
import { useJarvisStore } from '@/store/jarvisStore'

const IMPACT_COLOR: Record<string, string> = {
  high:   'text-jarvis-neon-red bg-jarvis-neon-red/10 border-jarvis-neon-red/30',
  medium: 'text-jarvis-neon-orange bg-jarvis-neon-orange/10 border-jarvis-neon-orange/30',
  low:    'text-jarvis-muted bg-white/5 border-white/10',
}

export function CalendarPage() {
  const { calendar, fetchCalendar } = useJarvisStore()
  const [tab, setTab] = useState<'events' | 'holidays'>('events')
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    await fetchCalendar()
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const items: any[] = tab === 'events' ? (calendar?.events ?? []) : (calendar?.holidays ?? [])

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold text-jarvis-text flex items-center gap-2">
          <CalendarDays size={15} className="text-jarvis-accent" /> Economic Calendar
        </h1>
        <button onClick={load} className="text-jarvis-muted hover:text-jarvis-accent transition-colors">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div className="flex gap-1.5">
        {(['events', 'holidays'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-3 py-1 rounded-full text-[11px] font-medium transition-all ${tab === t ? 'bg-jarvis-accent/20 text-jarvis-accent' : 'bg-white/5 text-jarvis-muted hover:text-jarvis-text'}`}>
            {t === 'events' ? 'Market Events' : 'Market Holidays'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-jarvis-muted text-xs">
          <RefreshCw size={16} className="animate-spin mr-2" /> Loading…
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
              className="glass-strong rounded-xl p-3 border border-white/5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-xs font-semibold text-jarvis-text">{item.title ?? item.name}</span>
                    {item.impact && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded border capitalize font-medium ${IMPACT_COLOR[item.impact] ?? IMPACT_COLOR.low}`}>
                        {item.impact}
                      </span>
                    )}
                  </div>
                  {item.description && (
                    <div className="text-[10px] text-jarvis-muted mb-1">{item.description}</div>
                  )}
                  <div className="flex items-center gap-3 text-[10px] text-jarvis-muted flex-wrap">
                    <span>{item.date}</span>
                    {item.time && <span>{item.time}</span>}
                    {item.category && <span className="capitalize">{item.category}</span>}
                  </div>
                  {(item.forecast !== undefined || item.previous !== undefined) && (
                    <div className="flex gap-3 mt-1 text-[10px]">
                      {item.forecast !== undefined && <span className="text-jarvis-accent">Forecast: {item.forecast}</span>}
                      {item.previous !== undefined && <span className="text-jarvis-muted">Prev: {item.previous}</span>}
                    </div>
                  )}
                </div>
                {item.impact === 'high'
                  ? <AlertCircle size={14} className="text-jarvis-neon-red flex-shrink-0 mt-0.5" />
                  : <Info size={14} className="text-jarvis-muted flex-shrink-0 mt-0.5" />
                }
              </div>
            </motion.div>
          ))}
          {items.length === 0 && !loading && (
            <div className="text-center text-jarvis-muted text-xs py-12">No {tab} found.</div>
          )}
        </div>
      )}
    </div>
  )
}
