'use client'
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { openModal } from '@/components/HolographicModal'

// ── Shared HUD section label (clickable) ─────────────────────
function SectionLabel({ label, modalId }: { label: string; modalId?: string }) {
  return (
    <div
      className="flex items-center gap-2 mb-2 group"
      onClick={() => modalId && openModal(modalId)}
      style={{ cursor: modalId ? 'pointer' : 'default' }}
    >
      <motion.div className="w-1.5 h-1.5 rounded-full"
        style={{ background: '#00D9FF', boxShadow: '0 0 5px #00D9FF' }}
        animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1.6, repeat: Infinity }} />
      <span className="text-[8px] font-bold tracking-[0.28em] group-hover:text-white transition-colors"
        style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>{label}</span>
      <div className="flex-1 h-px" style={{ background: 'linear-gradient(90deg, rgba(0,217,255,0.3), transparent)' }} />
      {modalId && <span className="text-[6px] tracking-widest opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>›</span>}
    </div>
  )
}

// ── 2.1 System Status row ─────────────────────────────────────
function StatusRow({ icon, label, value, valueColor = '#D8FFFF' }: {
  icon: string; label: string; value: string; valueColor?: string
}) {
  return (
    <div className="flex items-center justify-between py-[3px]"
      style={{ borderBottom: '1px solid rgba(0,217,255,0.04)' }}>
      <div className="flex items-center gap-1.5">
        <span className="text-[9px]" style={{ color: '#2A5A6A' }}>{icon}</span>
        <span className="text-[8px] tracking-[0.12em]"
          style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>{label}</span>
      </div>
      <span className="text-[8px] font-bold tracking-[0.1em]"
        style={{ color: valueColor, fontFamily: 'IBM Plex Mono, monospace' }}>{value}</span>
    </div>
  )
}

// ── 2.2 Process row ───────────────────────────────────────────
function ProcessRow({ label, status, color }: { label: string; status: string; color: string }) {
  return (
    <div className="flex items-center justify-between py-[3px]"
      style={{ borderBottom: '1px solid rgba(0,217,255,0.04)' }}>
      <div className="flex items-center gap-1.5">
        <motion.div className="w-1 h-1 rounded-full"
          style={{ background: color, boxShadow: `0 0 4px ${color}` }}
          animate={{ opacity: [1, 0.2, 1], scale: [1, 0.6, 1] }}
          transition={{ duration: 1.4, repeat: Infinity }} />
        <span className="text-[8px] tracking-[0.1em]"
          style={{ color: '#80C8FF', fontFamily: 'Rajdhani, sans-serif' }}>{label}</span>
      </div>
      <span className="text-[7px] font-bold tracking-[0.14em]"
        style={{ color, fontFamily: 'IBM Plex Mono, monospace' }}>{status}</span>
    </div>
  )
}

// ── 2.3 Real Time Feed ────────────────────────────────────────
function RealTimeFeed() {
  const { messages } = useJarvisStore()
  const [logs, setLogs] = useState([
    { time: '', text: 'System boot sequence completed' },
    { time: '', text: 'AI Core initialized' },
    { time: '', text: 'Voice Engine online' },
    { time: '', text: 'Market data feed connected' },
    { time: '', text: 'All systems operational' },
    { time: '', text: 'Waiting for command' },
  ])

  // Stamp times on mount
  useEffect(() => {
    const now = new Date()
    setLogs(prev => prev.map((l, i) => ({
      ...l,
      time: new Date(now.getTime() - (prev.length - i) * 2000)
        .toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
    })))
  }, [])

  // Append new messages from chat
  useEffect(() => {
    const last = messages[messages.length - 1]
    if (!last) return
    const time = new Date(last.timestamp)
      .toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
    const text = last.content.slice(0, 38) + (last.content.length > 38 ? '…' : '')
    setLogs(prev => [...prev.slice(-9), { time, text }])
  }, [messages])

  return (
    <div className="space-y-[3px] overflow-hidden">
      {logs.map((log, i) => (
        <motion.div key={i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.04 }} className="flex items-start gap-1.5">
          <span className="text-[7px] shrink-0 tabular-nums"
            style={{ color: '#1a3a5c', fontFamily: 'IBM Plex Mono, monospace' }}>{log.time}</span>
          <span className="text-[7.5px] leading-tight"
            style={{ color: '#80C8FF', fontFamily: 'Space Grotesk, sans-serif' }}>| {log.text}</span>
        </motion.div>
      ))}
    </div>
  )
}

// ── LEFT PANEL ────────────────────────────────────────────────
export function LeftPanel() {
  const { connected, status } = useJarvisStore()
  const [tick, setTick] = useState(0)
  useEffect(() => { const id = setInterval(() => setTick(t => t + 1), 2000); return () => clearInterval(id) }, [])

  const health   = connected ? 'OPTIMAL' : 'DEGRADED'
  const power    = 58 + (tick % 8)
  const temp     = 42 + (tick % 4)
  const memory   = 43 + (tick % 5)
  const storage  = 66 + (tick % 3)

  const processes = [
    { label: 'AI CORE',        status: 'RUNNING',  color: '#00D9FF' },
    { label: 'NEURAL ENGINE',  status: 'RUNNING',  color: '#00D9FF' },
    { label: 'VOICE ENGINE',   status: status === 'listening' ? 'RUNNING' : 'RUNNING', color: '#00D9FF' },
    { label: 'VISION MODULE',  status: 'STANDBY',  color: '#FFC857' },
    { label: 'DATA ANALYTICS', status: 'RUNNING',  color: '#00D9FF' },
    { label: 'SECURITY SHIELD',status: 'ACTIVE',   color: '#00FF99' },
  ]

  return (
    <div
      className="flex flex-col h-full overflow-hidden shrink-0"
      style={{
        width: 210,
        background: 'linear-gradient(180deg, rgba(3,10,24,0.97) 0%, rgba(5,19,38,0.95) 100%)',
        borderRight: '1px solid rgba(0,217,255,0.1)',
        padding: '10px 12px',
        gap: 10,
      }}
    >
      {/* Corner brackets */}
      <div className="absolute top-0 left-0 w-3 h-3 pointer-events-none"
        style={{ borderTop: '1px solid rgba(0,217,255,0.4)', borderLeft: '1px solid rgba(0,217,255,0.4)' }} />

      {/* ── 2.1 System Status ── */}
      <div
        className="shrink-0 p-2"
        style={{ border: '1px solid rgba(0,217,255,0.08)', background: 'rgba(0,217,255,0.02)' }}
      >
        <SectionLabel label="SYSTEM STATUS" modalId="monitor" />
        <StatusRow icon="~" label="SYSTEM HEALTH"  value={health}       valueColor={connected ? '#00D9FF' : '#FF5A7A'} />
        <StatusRow icon="⚡" label="POWER USAGE"   value={`${power}%`}  valueColor="#D8FFFF" />
        <StatusRow icon="🌡" label="TEMPERATURE"   value={`${temp}°C`}  valueColor="#D8FFFF" />
        <StatusRow icon="◈" label="MEMORY"         value={`${memory}%`} valueColor="#D8FFFF" />
        <StatusRow icon="◉" label="STORAGE"        value={`${storage}%`}valueColor="#D8FFFF" />
        <StatusRow icon="⌁" label="NETWORK"        value={connected ? 'STABLE' : 'FAULT'} valueColor={connected ? '#00FF99' : '#FF5A7A'} />
      </div>

      {/* ── 2.2 Active Processes ── */}
      <div
        className="shrink-0 p-2"
        style={{ border: '1px solid rgba(0,217,255,0.08)', background: 'rgba(0,217,255,0.02)' }}
      >
        <SectionLabel label="ACTIVE PROCESSES" modalId="agents" />
        {processes.map(p => <ProcessRow key={p.label} {...p} />)}
      </div>

      {/* ── 2.3 Real Time Feed ── */}
      <div
        className="flex-1 p-2 overflow-hidden"
        style={{ border: '1px solid rgba(0,217,255,0.08)', background: 'rgba(0,217,255,0.02)', minHeight: 0 }}
      >
        <SectionLabel label="REAL TIME FEED" />
        <RealTimeFeed />
      </div>
    </div>
  )
}
