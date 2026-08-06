'use client'
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { HolographicCore } from '@/components/HolographicCore'

// ── 3.2 / 3.3 Floating side labels ───────────────────────────
function SideLabel({ label, side }: { label: string; side: 'left' | 'right' }) {
  return (
    <motion.div
      className="flex items-center gap-1.5 px-2 py-1"
      style={{
        background: 'rgba(2,8,19,0.85)',
        border: '1px solid rgba(0,217,255,0.18)',
        borderRadius: 2,
        minWidth: 52,
        justifyContent: side === 'left' ? 'flex-start' : 'flex-end',
      }}
      animate={{ opacity: [0.7, 1, 0.7] }}
      transition={{ duration: 2.5, repeat: Infinity }}
    >
      {side === 'left' && (
        <motion.div className="w-1 h-1 rounded-full shrink-0"
          style={{ background: '#00D9FF', boxShadow: '0 0 4px #00D9FF' }}
          animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1.2, repeat: Infinity }} />
      )}
      <span className="text-[8px] font-bold tracking-[0.18em]"
        style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>{label}</span>
      {side === 'right' && (
        <>
          <div className="w-3 h-px" style={{ background: 'rgba(0,217,255,0.4)' }} />
          <span className="text-[7px]" style={{ color: '#2A5A6A', fontFamily: 'IBM Plex Mono, monospace' }}>••</span>
        </>
      )}
    </motion.div>
  )
}

// ── 3.4 AI Core Status waveform ───────────────────────────────
function StatusWaveform({ active }: { active: boolean }) {
  const bars = Array.from({ length: 32 }, (_, i) => ({
    h: Math.random() * 16 + 2,
    dur: 0.15 + Math.random() * 0.35,
    delay: i * 0.025,
  }))
  return (
    <div className="flex items-center gap-[1.5px]" style={{ height: 20 }}>
      {bars.map((b, i) => (
        <motion.div key={i}
          style={{ width: 2, background: 'rgba(0,217,255,0.6)', borderRadius: 1 }}
          animate={active ? { height: [1, b.h, 1] } : { height: 2 }}
          transition={{ duration: b.dur, repeat: Infinity, delay: b.delay, ease: 'easeInOut' }}
        />
      ))}
    </div>
  )
}

// ── CENTER COLUMN ─────────────────────────────────────────────
export function CenterColumn() {
  const { status, connected } = useJarvisStore()
  const [uptime, setUptime] = useState({ h: 5, m: 24, s: 19 })

  useEffect(() => {
    const id = setInterval(() => {
      setUptime(u => {
        let s = u.s + 1, m = u.m, h = u.h
        if (s >= 60) { s = 0; m++ }
        if (m >= 60) { m = 0; h++ }
        return { h, m, s }
      })
    }, 1000)
    return () => clearInterval(id)
  }, [])

  const uptimeStr = `${String(uptime.h).padStart(2,'0')}:${String(uptime.m).padStart(2,'0')}:${String(uptime.s).padStart(2,'0')}`

  const coreStatus = status === 'idle' ? 'OPTIMAL' :
    status === 'thinking'  ? 'PROCESSING' :
    status === 'speaking'  ? 'TRANSMITTING' :
    status === 'listening' ? 'LISTENING' : 'EXECUTING'

  const coreColor = status === 'idle' ? '#00FF99' :
    status === 'thinking'  ? '#009DFF' :
    status === 'speaking'  ? '#33F2FF' :
    status === 'listening' ? '#00FF99' : '#FFC857'

  return (
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden"
      style={{ borderRight: '1px solid rgba(0,217,255,0.1)' }}>

      {/* ── Core area ── */}
      <div className="flex-1 flex items-center justify-center relative min-h-0 overflow-hidden"
        style={{ background: 'linear-gradient(135deg, #051326 0%, #020813 100%)' }}>

        {/* Background radial glow */}
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse 60% 70% at 50% 50%, rgba(0,217,255,0.04) 0%, transparent 70%)' }} />

        {/* Corner brackets */}
        {[
          { top: 8, left: 8,   borderWidth: '1.5px 0 0 1.5px' },
          { top: 8, right: 8,  borderWidth: '1.5px 1.5px 0 0' },
          { bottom: 8, left: 8,  borderWidth: '0 0 1.5px 1.5px' },
          { bottom: 8, right: 8, borderWidth: '0 1.5px 1.5px 0' },
        ].map((s, i) => (
          <div key={i} className="absolute pointer-events-none"
            style={{ ...s, width: 20, height: 20, borderStyle: 'solid', borderColor: 'rgba(0,217,255,0.4)' }} />
        ))}

        {/* ── 3.2 Left labels (SYS / NET / AI) ── */}
        <div className="absolute left-4 flex flex-col gap-2" style={{ top: '50%', transform: 'translateY(-50%)' }}>
          {['SYS', 'NET', 'AI'].map(l => <SideLabel key={l} label={l} side="left" />)}
        </div>

        {/* ── 3.1 Holographic Core ── */}
        <div className="flex items-center justify-center" style={{ transform: 'scale(0.88)' }}>
          <HolographicCore />
        </div>

        {/* ── 3.3 Right labels (MEM / CPU / GPU) ── */}
        <div className="absolute right-4 flex flex-col gap-2" style={{ top: '50%', transform: 'translateY(-50%)' }}>
          {['MEM', 'CPU', 'GPU'].map(l => <SideLabel key={l} label={l} side="right" />)}
        </div>
      </div>

      {/* ── 3.4 AI Core Status bar ── */}
      <div
        className="shrink-0 flex items-center gap-4 px-4"
        style={{
          height: 48,
          background: 'rgba(2,8,19,0.95)',
          borderTop: '1px solid rgba(0,217,255,0.12)',
        }}
      >
        {/* Status label */}
        <div className="flex flex-col shrink-0">
          <span className="text-[7px] tracking-[0.22em]"
            style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>AI CORE STATUS</span>
          <motion.span
            className="text-[10px] font-black tracking-[0.18em]"
            style={{ color: coreColor, fontFamily: 'Orbitron, sans-serif', textShadow: `0 0 8px ${coreColor}` }}
            animate={{ opacity: [1, 0.6, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >{coreStatus}</motion.span>
        </div>

        {/* Waveform */}
        <div className="flex-1">
          <StatusWaveform active={status !== 'idle'} />
        </div>

        {/* Uptime */}
        <div className="flex flex-col items-end shrink-0">
          <span className="text-[7px] tracking-[0.22em]"
            style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>UPTIME</span>
          <span className="text-[11px] font-black tabular-nums"
            style={{ color: '#D8FFFF', fontFamily: 'Orbitron, sans-serif' }}>{uptimeStr}</span>
        </div>
      </div>
    </div>
  )
}
