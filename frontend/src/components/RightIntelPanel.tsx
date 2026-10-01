'use client'
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { useJarvisStore as useStore } from '@/store/jarvisStore'

function SectionLabel({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <div
      className="flex items-center gap-2 mb-3 cursor-pointer group"
      onClick={onClick}
    >
      <motion.div className="w-2 h-2 rounded-full shrink-0"
        style={{ background: '#00D9FF', boxShadow: '0 0 6px #00D9FF' }}
        animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1.6, repeat: Infinity }} />
      <span className="text-[9px] font-bold tracking-[0.22em] group-hover:text-white transition-colors"
        style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>{label}</span>
      <div className="flex-1 h-px" style={{ background: 'linear-gradient(90deg, rgba(0,217,255,0.35), transparent)' }} />
    </div>
  )
}

function Sparkline() {
  const pts = [28, 32, 30, 35, 33, 38, 36, 40, 37, 42, 39, 44, 41, 43, 45, 42, 46, 44, 48, 45]
  const max = Math.max(...pts), min = Math.min(...pts)
  const norm = (v: number) => 28 - ((v - min) / (max - min)) * 24
  const d = pts.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i / (pts.length - 1)) * 160},${norm(v)}`).join(' ')
  return (
    <svg width="100%" height="32" viewBox="0 0 160 32" preserveAspectRatio="none">
      <defs>
        <linearGradient id="spkR" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00D9FF" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#00D9FF" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={d + ' L160,32 L0,32 Z'} fill="url(#spkR)" />
      <path d={d} fill="none" stroke="#00D9FF" strokeWidth="1.5"
        style={{ filter: 'drop-shadow(0 0 3px rgba(0,217,255,0.8))' }} />
    </svg>
  )
}

function ConfidenceDonut({ pct }: { pct: number }) {
  const r = 24, circ = 2 * Math.PI * r
  return (
    <div className="relative flex items-center justify-center" style={{ width: 60, height: 60 }}>
      <svg width="60" height="60" viewBox="0 0 60 60">
        <circle cx="30" cy="30" r={r} fill="none" stroke="rgba(0,217,255,0.08)" strokeWidth="4" />
        <motion.circle cx="30" cy="30" r={r} fill="none" stroke="#00D9FF" strokeWidth="4"
          strokeLinecap="round" strokeDasharray={`${circ}`}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - (pct / 100) * circ }}
          transition={{ duration: 1.5, ease: 'easeOut' }}
          style={{ transformOrigin: '30px 30px', transform: 'rotate(-90deg)', filter: 'drop-shadow(0 0 4px rgba(0,217,255,0.8))' }} />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-[13px] font-black tabular-nums"
          style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif', lineHeight: 1 }}>{pct}%</span>
        <span className="text-[7px] tracking-[0.12em]" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>CONF</span>
      </div>
    </div>
  )
}

function ModuleIcon({ label, status, icon }: { label: string; status: string; icon: string }) {
  const ok = status === 'CONNECTED' || status === 'ACTIVE'
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex items-center justify-center rounded-sm"
        style={{ width: 32, height: 32,
          background: ok ? 'rgba(0,217,255,0.08)' : 'rgba(255,90,122,0.06)',
          border: `1px solid ${ok ? 'rgba(0,217,255,0.22)' : 'rgba(255,90,122,0.2)'}` }}>
        <span style={{ fontSize: 15 }}>{icon}</span>
      </div>
      <span className="text-[7px] tracking-[0.08em] text-center"
        style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif', lineHeight: 1.3 }}>{label}</span>
      <span className="text-[7px] font-bold"
        style={{ color: ok ? '#00FF99' : '#FF5A7A', fontFamily: 'IBM Plex Mono, monospace' }}>{status}</span>
    </div>
  )
}

export function RightIntelPanel() {
  const { connected, sendMessage, setActiveNav } = useJarvisStore()
  const [tick, setTick] = useState(0)
  const [tf, setTf] = useState('1D')
  useEffect(() => { const id = setInterval(() => setTick(t => t + 1), 3000); return () => clearInterval(id) }, [])

  const indices = [
    { name: 'NIFTY 50',   value: '24,641', change: '+1.35%', up: true  },
    { name: 'SENSEX',     value: '80,567', change: '+1.25%', up: true  },
    { name: 'BANK NIFTY', value: '51,392', change: '+1.62%', up: true  },
    { name: 'INDIA VIX',  value: '12.47',  change: '-2.35%', up: false },
  ]
  const gainers = [{ name: 'RELIANCE', val: '+2.45%' }, { name: 'HDFCBANK', val: '+1.85%' }, { name: 'TCS', val: '+1.25%' }]
  const losers  = [{ name: 'INFY', val: '-1.35%' }, { name: 'WIPRO', val: '-1.12%' }, { name: 'TECHM', val: '-0.85%' }]
  const modules = [
    { label: 'STOCK API', status: connected ? 'CONNECTED' : 'OFFLINE', icon: '📈' },
    { label: 'NEWS',      status: 'CONNECTED', icon: '📰' },
    { label: 'WEATHER',   status: 'CONNECTED', icon: '🌤' },
    { label: 'CALENDAR',  status: 'CONNECTED', icon: '📅' },
    { label: 'VOICE',     status: 'ACTIVE',    icon: '🎙' },
  ]
  const suggestions = [
    { label: 'Market overview',    action: () => setActiveNav('market')    },
    { label: 'AI Discovery',       action: () => setActiveNav('discovery') },
    { label: 'Top gainers today',  action: () => sendMessage('Top gainers today') },
    { label: 'News headlines',     action: () => setActiveNav('news')      },
    { label: 'My watchlist',       action: () => setActiveNav('watchlist') },
    { label: 'Portfolio summary',  action: () => setActiveNav('portfolio') },
    { label: 'System status',      action: () => setActiveNav('monitor')   },
  ]
  const timeframes = ['1D', '1W', '1M', '3M']

  return (
    <div
      className="flex flex-col h-full overflow-y-auto overflow-x-hidden shrink-0"
      style={{
        width: 300,
        background: 'linear-gradient(180deg, rgba(2,7,18,0.99) 0%, rgba(4,14,30,0.98) 100%)',
        borderLeft: '1px solid rgba(0,217,255,0.12)',
        padding: '14px 14px',
        gap: 10,
        scrollbarWidth: 'none',
      }}
    >
      {/* Top corner bracket */}
      <div className="absolute top-0 right-0 w-4 h-4 pointer-events-none"
        style={{ borderTop: '2px solid rgba(0,217,255,0.5)', borderRight: '2px solid rgba(0,217,255,0.5)' }} />

      {/* ── Market Overview ── */}
      <div className="shrink-0 p-3"
        style={{ border: '1px solid rgba(0,217,255,0.1)', background: 'rgba(0,217,255,0.02)' }}>
        <SectionLabel label="MARKET OVERVIEW" onClick={() => setActiveNav('market')} />
        <div className="space-y-1 mb-3">
          {indices.map(idx => (
            <div key={idx.name} className="flex items-center justify-between py-1"
              style={{ borderBottom: '1px solid rgba(0,217,255,0.05)' }}>
              <span className="text-[11px]"
                style={{ color: '#80C8FF', fontFamily: 'Space Grotesk, sans-serif' }}>{idx.name}</span>
              <div className="flex items-center gap-3">
                <span className="text-[11px] font-bold tabular-nums"
                  style={{ color: '#D8FFFF', fontFamily: 'IBM Plex Mono, monospace' }}>{idx.value}</span>
                <span className="text-[10px] font-bold"
                  style={{ color: idx.up ? '#00FF99' : '#FF5A7A', fontFamily: 'IBM Plex Mono, monospace' }}>{idx.change}</span>
              </div>
            </div>
          ))}
        </div>
        <Sparkline />
        <div className="flex gap-1.5 mt-2">
          {timeframes.map(t => (
            <button key={t} onClick={() => setTf(t)}
              className="flex-1 text-[8px] font-bold tracking-[0.1em] py-1 rounded-sm"
              style={{
                fontFamily: 'Orbitron, sans-serif', cursor: 'pointer',
                background: tf === t ? 'rgba(0,217,255,0.14)' : 'transparent',
                border: `1px solid ${tf === t ? 'rgba(0,217,255,0.4)' : 'rgba(0,217,255,0.08)'}`,
                color: tf === t ? '#00D9FF' : '#2A5A6A',
              }}>{t}</button>
          ))}
        </div>
      </div>

      {/* ── AI Insights ── */}
      <div className="shrink-0 p-3"
        style={{ border: '1px solid rgba(0,217,255,0.1)', background: 'rgba(0,217,255,0.02)' }}>
        <SectionLabel label="AI INSIGHTS" onClick={() => setActiveNav('discovery')} />
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[8px] tracking-[0.16em] mb-1"
              style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>MARKET MOOD</div>
            <div className="text-[14px] font-black tracking-[0.12em]"
              style={{ color: '#00FF99', fontFamily: 'Orbitron, sans-serif', textShadow: '0 0 8px rgba(0,255,153,0.6)' }}>
              BULLISH
            </div>
          </div>
          <ConfidenceDonut pct={78} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-[8px] font-bold tracking-[0.14em] mb-1.5"
              style={{ color: '#00FF99', fontFamily: 'Orbitron, sans-serif' }}>TOP GAINERS</div>
            {gainers.map(g => (
              <div key={g.name} className="flex justify-between py-0.5">
                <span className="text-[10px]" style={{ color: '#80C8FF', fontFamily: 'Space Grotesk, sans-serif' }}>{g.name}</span>
                <span className="text-[10px] font-bold" style={{ color: '#00FF99', fontFamily: 'IBM Plex Mono, monospace' }}>{g.val}</span>
              </div>
            ))}
          </div>
          <div>
            <div className="text-[8px] font-bold tracking-[0.14em] mb-1.5"
              style={{ color: '#FF5A7A', fontFamily: 'Orbitron, sans-serif' }}>TOP LOSERS</div>
            {losers.map(l => (
              <div key={l.name} className="flex justify-between py-0.5">
                <span className="text-[10px]" style={{ color: '#80C8FF', fontFamily: 'Space Grotesk, sans-serif' }}>{l.name}</span>
                <span className="text-[10px] font-bold" style={{ color: '#FF5A7A', fontFamily: 'IBM Plex Mono, monospace' }}>{l.val}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Connected Modules ── */}
      <div className="shrink-0 p-3"
        style={{ border: '1px solid rgba(0,217,255,0.1)', background: 'rgba(0,217,255,0.02)' }}>
        <SectionLabel label="CONNECTED MODULES" />
        <div className="flex justify-between">
          {modules.map(m => <ModuleIcon key={m.label} {...m} />)}
        </div>
      </div>

      {/* ── Suggested Commands ── */}
      <div className="shrink-0 p-3"
        style={{ border: '1px solid rgba(0,217,255,0.1)', background: 'rgba(0,217,255,0.02)' }}>
        <SectionLabel label="QUICK ACTIONS" />
        <div className="space-y-0.5">
          {suggestions.map(s => (
            <button
              key={s.label}
              onClick={s.action}
              className="w-full text-left flex items-center gap-2 py-1.5 px-2 rounded-sm transition-all duration-100"
              style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,217,255,0.05)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <span style={{ color: '#00D9FF', fontSize: 10 }}>›</span>
              <span className="text-[11px]" style={{ color: '#4A7A8A', fontFamily: 'Space Grotesk, sans-serif' }}>{s.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
