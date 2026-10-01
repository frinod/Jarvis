'use client'

import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Newspaper, RefreshCw, ExternalLink, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { useJarvisStore } from '@/store/jarvisStore'

const SENTIMENTS = ['all', 'positive', 'negative', 'neutral'] as const
type Filter = typeof SENTIMENTS[number]

const IMPACT_COLOR: Record<string, string> = {
  high:   'text-jarvis-neon-red bg-jarvis-neon-red/10',
  medium: 'text-jarvis-neon-orange bg-jarvis-neon-orange/10',
  low:    'text-jarvis-muted bg-white/5',
}

function SentimentBadge({ s }: { s: string }) {
  const map: Record<string, { color: string; icon: React.ReactNode }> = {
    positive: { color: 'text-jarvis-neon-green bg-jarvis-neon-green/10', icon: <TrendingUp size={10} /> },
    negative: { color: 'text-jarvis-neon-red bg-jarvis-neon-red/10',     icon: <TrendingDown size={10} /> },
    neutral:  { color: 'text-jarvis-muted bg-white/5',                   icon: <Minus size={10} /> },
  }
  const cfg = map[s] ?? map.neutral
  return (
    <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium capitalize ${cfg.color}`}>
      {cfg.icon}{s}
    </span>
  )
}

function parseDate(dateStr: string): number {
  // new Date() fails on RSS pubDate format in Firefox/Safari — normalize it
  const d = new Date(dateStr)
  if (!isNaN(d.getTime())) return d.getTime()
  // Try stripping timezone name e.g. "Mon, 12 May 2025 10:30:00 +0530"
  const normalized = dateStr.replace(/(\+|-)\d{4}.*$/, '').trim()
  const d2 = new Date(normalized)
  return isNaN(d2.getTime()) ? Date.now() : d2.getTime()
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - parseDate(dateStr)
  const m = Math.floor(diff / 60000)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

export function NewsPage() {
  const { news, fetchNews } = useJarvisStore()
  const [filter, setFilter] = useState<Filter>('all')
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    await fetchNews()
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const filtered = filter === 'all' ? news : news.filter(n => n.sentiment === filter)

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold text-jarvis-text flex items-center gap-2">
          <Newspaper size={15} className="text-jarvis-accent" /> Market News
        </h1>
        <button onClick={load} className="text-jarvis-muted hover:text-jarvis-accent transition-colors">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div className="flex gap-1.5 flex-wrap">
        {SENTIMENTS.map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-[11px] font-medium capitalize transition-all ${filter === f ? 'bg-jarvis-accent/20 text-jarvis-accent' : 'bg-white/5 text-jarvis-muted hover:text-jarvis-text'}`}>
            {f}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-jarvis-muted self-center">{filtered.length} articles</span>
      </div>

      {loading && filtered.length === 0 ? (
        <div className="flex items-center justify-center h-48 text-jarvis-muted text-xs">
          <RefreshCw size={16} className="animate-spin mr-2" /> Fetching news…
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((item, i) => (
            <motion.div key={item.link} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
              className="glass-strong rounded-xl p-3 border border-white/5 hover:border-jarvis-accent/20 transition-all">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-jarvis-text leading-snug mb-1">{item.title}</div>
                  {item.summary && (
                    <div className="text-[10px] text-jarvis-muted line-clamp-2 mb-2">{item.summary}</div>
                  )}
                  <div className="flex items-center gap-2 flex-wrap">
                    <SentimentBadge s={item.sentiment} />
                    <span className={`text-[10px] px-1.5 py-0.5 rounded capitalize ${IMPACT_COLOR[item.impact] ?? IMPACT_COLOR.low}`}>{item.impact}</span>
                    <span className="text-[10px] text-jarvis-muted">{item.source}</span>
                    <span className="text-[10px] text-jarvis-muted">{timeAgo(item.published)}</span>
                  </div>
                </div>
                <a href={item.link} target="_blank" rel="noopener noreferrer"
                  className="text-jarvis-muted hover:text-jarvis-accent transition-colors flex-shrink-0 mt-0.5">
                  <ExternalLink size={13} />
                </a>
              </div>
            </motion.div>
          ))}
          {filtered.length === 0 && !loading && (
            <div className="text-center text-jarvis-muted text-xs py-12">No news found.</div>
          )}
        </div>
      )}
    </div>
  )
}
