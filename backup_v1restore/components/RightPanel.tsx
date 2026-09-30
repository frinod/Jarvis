'use client'
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { openModal } from '@/components/HolographicModal'

function SectionLabel({ label, modalId }: { label: string; modalId?: string }) {
  return (
    <div
      className="flex items-center gap-2 mb-2 group"
      onClick={() => modalId && openModal(modalId)}
      style={{ cursor: modalId ? 'pointer' : 'default' }}
    >
      <span className="text-[8px] font-bold tracking-[0.26em] group-hover:text-white transition-colors"
        style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>{label}</span>
      <div className="flex-1 h-px" style={{ background: 'linear-gradient(90deg, rgba(0,217,255,0.3), transparent)' }} />
      {modalId && (
        <span className="text-[6px] tracking-widest opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>EXPAND ›</span>
      )}
    </div>
  )
}

function Sparkline() {
  const pts = [28,32,30,35,33,38,36,40,37,42,39,44,41,43,45,42,46,44,48,45]
  const max = Math.max(...pts), min = Math.min(...pts)
  const norm = (v: number) => 28 - ((v - min) / (max - min)) * 24
  const d = pts.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i / (pts.length - 1)) * 148},${norm(v)}`).join(' ')
  return (
    <svg width="100%" height="30" viewBox="0 0 148 30" preserveAspectRatio="none">
      <defs>
        <linearGradient id="spk" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00D9FF" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#00D9FF" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={d + ` L148,30 L0,30 Z`} fill="url(#spk)" />
      <path d={d} fill="none" stroke="#00D9FF" strokeWidth="1.2"
        style={{ filter: 'drop-shadow(0 0 3px rgba(0,217,255,0.8))' }} />
    </svg>
  )
}

function ConfidenceDonut({ pct }: { pct: number }) {
  const r = 22, circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  return (
    <div className="relative flex items-center justify-center" style={{ width: 56, height: 56 }}>
      <svg width="56" height="56" viewBox="0 0 56 56">
        <circle cx="28" cy="28" r={r} fill="none" stroke="rgba(0,217,255,0.08)" strokeWidth="4" />
        <motion.circle cx="28" cy="28" r={r} fill="none" stroke="#00D9FF" strokeWidth="4"
          strokeLinecap="round" strokeDasharray={`${circ}`}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - dash }}
          transition={{ duration: 1.5, ease: 'easeOut' }}
          style={{ transformOrigin: '28px 28px', transform: 'rotate(-90deg)',
            filter: 'drop-shadow(0 0 4px rgba(0,217,255,0.8))' }} />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-[11px] font-black tabular-nums"
          style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif', lineHeight: 1 }}>{pct}%</span>
        <span className="text-[5px] tracking-[0.15em]"
          style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>CONF</span>
      </div>
    </div>
  )
}

function ModuleIcon({ label, status, icon }: { label: string; status: string; icon: string }) {
  const ok = status === 'CONNECTED' || status === 'ACTIVE'
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex items-center justify-center rounded-sm"
        style={{ width: 28, height: 28,
          background: ok ? 'rgba(0,217,255,0.08)' : 'rgba(255,90,122,0.06)',
          border: `1px solid ${ok ? 'rgba(0,217,255,0.22)' : 'rgba(255,90,122,0.2)'}` }}>
        <span style={{ fontSize: 13 }}>{icon}</span>
      </div>
      <span className="text-[6px] tracking-[0.1em] text-center"
        style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif', lineHeight: 1.2 }}>{label}</span>
      <span className="text-[6px] font-bold tracking-[0.1em]"
        style={{ color: ok ? '#00FF99' : '#FF5A7A', fontFamily: 'IBM Plex Mono, monospace' }}>{status}</span>
    </div>
  )
}

export function RightPanel() {
  const { connected, sendMessage } = useJarvisStore()
  const [tick, setTick] = useState(0)
  const [tf, setTf] = useState('1D')
  useEffect(() => { const id = setInterval(() => setTick(t => t + 1), 3000); return () => clearInterval(id) }, [])

  const indices = [
    { name: 'NIFTY 50',   value: '24,641.25', change: '+1.35%', up: true  },
    { name: 'SENSEX',     value: '80,567.71', change: '+1.25%', up: true  },
    { name: 'BANK NIFTY', value: '51,392.15', change: '+1.62%', up: true  },
    { name: 'INDIA VIX',  value: '12.47',     change: '-2.35%', up: false },
  ]

  const gainers = [
    { name: 'RELIANCE', val: '+2.45%' },
    { name: 'HDFCBANK', val: '+1.85%' },
    { name: 'TCS',      val: '+1.25%' },
  ]
  const losers = [
    { name: 'INFY',  val: '-1.35%' },
    { name: 'WIPRO', val: '-1.12%' },
    { name: 'TECHM', val: '-0.85%' },
  ]

  const modules = [
    { label: 'STOCK API', status: connected ? 'CONNECTED' : 'OFFLINE', icon: '📈' },
    { label: 'NEWS FEED', status: 'CONNECTED', icon: '📰' },
    { label: 'WEATHER',   status: 'CONNECTED', icon: '🌤' },
    { label: 'CALENDAR',  status: 'CONNECTED', icon: '📅' },
    { label: 'EMAIL',     status: 'ACTIVE',    icon: '🎙' },
  ]

  const suggestions = [
    { label: 'Show market overview', modal: 'market'    },
    { label: 'Analyze Nifty 50',     modal: null        },
    { label: 'Top gainers today',    modal: 'market'    },
    { label: 'News headlines',       modal: 'news'      },
    { label: 'My watchlist',         modal: 'watchlist' },
    { label: 'Portfolio summary',    modal: 'portfolio' },
    { label: 'System status',        modal: 'monitor'   },
  ]

  const timeframes = ['1D','1W','1M','3M','1Y','ALL']

  return (
    <div
      className="flex flex-col h-full overflow-y-auto overflow-x-hidden shrink-0"
      style={{
        width: 270,
        background: 'linear-gradient(180deg, rgba(3,10,24,0.98) 0%, rgba(5,19,38,0.96) 100%)',
        borderLeft: '1px solid rgba(0,217,255,0.12)',
        padding: '12px 12px',
        gap: 8,
        scrollbarWidth: 'none',
      }}
    >
      {/* Corner brackets */}
      <div className="absolute top-0 right-0 w-4 h-4 pointer-events-none"
        style={{ borderTop: '1.5px solid rgba(0,217,255,0.5)', borderRight: '1.5px solid rgba(0,217,255,0.5)' }} />
      <div className="absolute top-0 left-0 w-4 h-4 pointer-events-none"
        style={{ borderTop: '1.5px solid rgba(0,217,255,0.2)', borderLeft: '1.5px solid rgba(0,217,255,0.2)' }} />
      {/* Market Overview */}
      <div className="shrink-0 p-2.5"
        style={{ border: '1px solid rgba(0,217,255,0.1)', background: 'rgba(0,217,255,0.025)', boxShadow: 'inset 0 0 20px rgba(0,217,255,0.02)' }}>
        <SectionLabel label="MARKET OVERVIEW" modalId="market" />
        <div className="space-y-[3px] mb-2">
          {indices.map(idx => (
            <div key={idx.name} className="flex items-center justify-between py-[2px]"
              style={{ borderBottom: '1px solid rgba(0,217,255,0.04)' }}>
              <span className="text-[7.5px] tracking-[0.08em]"
                style={{ color: '#80C8FF', fontFamily: 'Rajdhani, sans-serif' }}>{idx.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-[8px] font-bold tabular-nums"
                  style={{ color: '#D8FFFF', fontFamily: 'IBM Plex Mono, monospace' }}>{idx.value}</span>
                <span className="text-[7.5px] font-bold"
                  style={{ color: idx.up ? '#00FF99' : '#FF5A7A', fontFamily: 'IBM Plex Mono, monospace' }}>{idx.change}</span>
              </div>
            </div>
          ))}
        </div>
        <Sparkline />
        <div className="flex gap-1 mt-1.5">
          {timeframes.map(t => (
            <button key={t} onClick={() => setTf(t)}
              className="flex-1 text-[6.5px] font-bold tracking-[0.1em] py-0.5 rounded-sm"
              style={{
                fontFamily: 'Orbitron, sans-serif',
                background: tf === t ? 'rgba(0,217,255,0.15)' : 'transparent',
                border: `1px solid ${tf === t ? 'rgba(0,217,255,0.4)' : 'rgba(0,217,255,0.08)'}`,
                color: tf === t ? '#00D9FF' : '#2A5A6A',
              }}>{t}</button>
          ))}
        </div>
      </div>

      {/* AI Insights */}
      <div className="shrink-0 p-2.5"
        style={{ border: '1px solid rgba(0,217,255,0.1)', background: 'rgba(0,217,255,0.025)', boxShadow: 'inset 0 0 20px rgba(0,217,255,0.02)' }}>
        <SectionLabel label="AI INSIGHTS" modalId="discovery" />
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="text-[7px] tracking-[0.16em] mb-0.5"
              style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>MARKET MOOD</div>
            <div className="text-[12px] font-black tracking-[0.14em]"
              style={{ color: '#00FF99', fontFamily: 'Orbitron, sans-serif', textShadow: '0 0 8px rgba(0,255,153,0.6)' }}>
              BULLISH
            </div>
          </div>
          <ConfidenceDonut pct={78} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <div className="text-[6.5px] font-bold tracking-[0.14em] mb-1"
              style={{ color: '#00FF99', fontFamily: 'Orbitron, sans-serif' }}>TOP GAINERS</div>
            {gainers.map(g => (
              <div key={g.name} className="flex justify-between py-[2px]">
                <span className="text-[7px]" style={{ color: '#80C8FF', fontFamily: 'Rajdhani, sans-serif' }}>{g.name}</span>
                <span className="text-[7px] font-bold" style={{ color: '#00FF99', fontFamily: 'IBM Plex Mono, monospace' }}>{g.val}</span>
              </div>
            ))}
          </div>
          <div>
            <div className="text-[6.5px] font-bold tracking-[0.14em] mb-1"
              style={{ color: '#FF5A7A', fontFamily: 'Orbitron, sans-serif' }}>TOP LOSERS</div>
            {losers.map(l => (
              <div key={l.name} className="flex justify-between py-[2px]">
                <span className="text-[7px]" style={{ color: '#80C8FF', fontFamily: 'Rajdhani, sans-serif' }}>{l.name}</span>
                <span className="text-[7px] font-bold" style={{ color: '#FF5A7A', fontFamily: 'IBM Plex Mono, monospace' }}>{l.val}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex gap-1 mt-2">
          {Array.from({ length: 10 }, (_, i) => (
            <div key={i} className="flex-1 h-1 rounded-sm"
              style={{ background: i < 7 ? '#00D9FF' : 'rgba(0,217,255,0.12)',
                boxShadow: i < 7 ? '0 0 4px rgba(0,217,255,0.5)' : 'none' }} />
          ))}
        </div>
      </div>

      {/* Connected Modules */}
      <div className="shrink-0 p-2.5"
        style={{ border: '1px solid rgba(0,217,255,0.1)', background: 'rgba(0,217,255,0.025)', boxShadow: 'inset 0 0 20px rgba(0,217,255,0.02)' }}>
        <SectionLabel label="CONNECTED MODULES" modalId="monitor" />
        <div className="flex justify-between">
          {modules.map(m => <ModuleIcon key={m.label} {...m} />)}
        </div>
      </div>

      {/* Suggested Commands */}
      <div className="shrink-0 p-2.5"
        style={{ border: '1px solid rgba(0,217,255,0.1)', background: 'rgba(0,217,255,0.025)', boxShadow: 'inset 0 0 20px rgba(0,217,255,0.02)' }}>
        <SectionLabel label="SUGGESTED COMMANDS" />
        <div className="space-y-[3px]">
          {suggestions.map(s => (
            <motion.button key={s.label}
              onClick={() => s.modal ? openModal(s.modal) : sendMessage(s.label)}
              className="w-full text-left flex items-center gap-1.5 py-[3px] px-1 rounded-sm"
              style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
              whileHover={{ background: 'rgba(0,217,255,0.05)', x: 2 }}
              transition={{ duration: 0.15 }}
            >
              <span style={{ color: '#00D9FF', fontSize: 8 }}>›</span>
              <span className="text-[8px]"
                style={{ color: '#80C8FF', fontFamily: 'Space Grotesk, sans-serif' }}>{s.label}</span>
            </motion.button>
          ))}
        </div>
      </div>
    </div>
  )
}
