'use client'
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { Mic, MicOff } from 'lucide-react'

// ── 1.7 Clock ─────────────────────────────────────────────────
function Clock() {
  const [time, setTime] = useState('')
  const [date, setDate] = useState('')
  useEffect(() => {
    const tick = () => {
      const now = new Date()
      setTime(now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }))
      setDate(now.toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase())
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="flex flex-col items-end shrink-0">
      <div
        className="text-[26px] font-black tabular-nums leading-none"
        style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif', textShadow: '0 0 16px rgba(0,217,255,0.95), 0 0 32px rgba(0,217,255,0.5), 0 0 60px rgba(0,217,255,0.2)' }}
      >{time}</div>
      <div className="text-[8px] tracking-[0.2em] mt-1" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>{date} · IST</div>
    </div>
  )
}

// ── 1.6 Metric pill ───────────────────────────────────────────
function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col items-center px-3" style={{ borderRight: '1px solid rgba(0,217,255,0.08)' }}>
      <span className="text-[8px] tracking-[0.18em]" style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>{label}</span>
      <span className="text-[13px] font-black tabular-nums leading-tight" style={{ color: '#D8FFFF', fontFamily: 'Orbitron, sans-serif' }}>{value}</span>
    </div>
  )
}

// ── Voice waveform bars ───────────────────────────────────────
function WaveformBars({ active, color }: { active: boolean; color: string }) {
  const bars = Array.from({ length: 18 }, (_, i) => ({
    h: Math.random() * 14 + 3,
    dur: 0.2 + Math.random() * 0.4,
    delay: i * 0.04,
  }))
  return (
    <div className="flex items-center gap-[2px]" style={{ height: 20 }}>
      {bars.map((b, i) => (
        <motion.div
          key={i}
          style={{ width: 2, background: color, borderRadius: 1, opacity: active ? 1 : 0.2 }}
          animate={active ? { height: [2, b.h, 2] } : { height: 2 }}
          transition={{ duration: b.dur, repeat: Infinity, delay: b.delay, ease: 'easeInOut' }}
        />
      ))}
    </div>
  )
}

export function Header() {
  const { status, connected, voiceActive, setVoiceActive, setStatus, llmInfo } = useJarvisStore()
  const [tick, setTick] = useState(0)
  useEffect(() => { const id = setInterval(() => setTick(t => t + 1), 2000); return () => clearInterval(id) }, [])

  const isListening = status === 'listening'
  const isSpeaking  = status === 'speaking'
  const isThinking  = status === 'thinking'
  const isExecuting = status === 'executing'
  const isActive    = isListening || isSpeaking || isThinking || isExecuting

  const cpu  = 12 + (tick % 9)
  const ram  = 40 + (tick % 8)
  const gpu  = 28 + (tick % 6)
  const net  = `${(1.1 + (tick % 4) * 0.05).toFixed(1)} TB/s`

  const statusLabel =
    isListening ? 'LISTENING...' :
    isSpeaking  ? 'TRANSMITTING...' :
    isThinking  ? 'PROCESSING...' :
    isExecuting ? 'EXECUTING...' : 'STANDBY'

  const statusSub =
    isListening ? 'Waiting for your command' :
    isSpeaking  ? 'Speaking response' :
    isThinking  ? 'Analyzing request' :
    isExecuting ? 'Running operation' : 'System ready'

  const micColor = isListening ? '#00FF99' : '#00D9FF'

  const toggleMic = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) { alert('Use Chrome or Edge for voice support.'); return }
    setVoiceActive(!voiceActive)
  }

  return (
    <header
      className="relative shrink-0 flex items-center h-[72px] z-50"
      style={{
        background: 'linear-gradient(180deg, rgba(2,8,19,0.99) 0%, rgba(5,19,38,0.97) 100%)',
        borderBottom: '1px solid rgba(0,217,255,0.14)',
        boxShadow: '0 2px 40px rgba(0,0,0,0.8), 0 1px 0 rgba(0,217,255,0.08)',
      }}
    >
      {/* Top shimmer line */}
      <div className="absolute top-0 left-0 right-0 h-px border-shimmer" />

      {/* ── 1.1 Logo ── */}
      <div
        className="flex flex-col justify-center px-5 shrink-0"
        style={{ width: 200, borderRight: '1px solid rgba(0,217,255,0.12)', height: '100%' }}
      >
        <div
          className="text-[15px] font-black tracking-[0.36em]"
          style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif', textShadow: '0 0 16px rgba(0,217,255,0.9), 0 0 32px rgba(0,217,255,0.5), 0 0 60px rgba(0,217,255,0.2)' }}
        >J.A.R.V.I.S</div>
        <div className="text-[8px] tracking-[0.26em] mt-1" style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>
          AI OPERATING SYSTEM
        </div>
        {/* decorative dots row */}
        <div className="flex gap-1 mt-1.5">
          {[0,1,2,3,4,5,6,7].map(i => (
            <motion.div key={i} className="w-1 h-px" style={{ background: 'rgba(0,217,255,0.3)' }}
              animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.12 }} />
          ))}
        </div>
      </div>

      {/* ── 1.2 Voice Mode panel ── */}
      <div
        className="flex flex-col justify-center px-4 shrink-0"
        style={{ width: 160, borderRight: '1px solid rgba(0,217,255,0.12)', height: '100%' }}
      >
        <div className="flex items-center gap-1.5 mb-1">
          <motion.div className="w-1.5 h-1.5 rounded-full"
            style={{ background: '#00FF99', boxShadow: '0 0 6px #00FF99' }}
            animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1.2, repeat: Infinity }} />
          <span className="text-[8px] tracking-[0.2em]" style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>VOICE MODE</span>
        </div>
        <WaveformBars active={isActive} color={micColor} />
        <div className="mt-1">
          <span
            className="text-[8px] font-bold tracking-[0.15em]"
            style={{ color: '#00FF99', fontFamily: 'Orbitron, sans-serif', textShadow: '0 0 8px rgba(0,255,153,0.6)' }}
          >ACTIVE</span>
        </div>
      </div>

      {/* ── 1.3 Center mic button ── */}
      <div
        className="flex items-center justify-center shrink-0"
        style={{ width: 90, borderRight: '1px solid rgba(0,217,255,0.12)', height: '100%' }}
      >
        <motion.button
          onClick={toggleMic}
          className="relative flex items-center justify-center rounded-full"
          style={{
            width: 50, height: 50,
            background: isListening ? 'rgba(0,255,153,0.12)' : 'rgba(0,217,255,0.08)',
            border: `2px solid ${isListening ? '#00FF99' : '#00D9FF'}`,
            boxShadow: isListening
              ? '0 0 20px rgba(0,255,153,0.5), 0 0 40px rgba(0,255,153,0.2), inset 0 0 12px rgba(0,255,153,0.1)'
              : '0 0 16px rgba(0,217,255,0.4), 0 0 32px rgba(0,217,255,0.15), inset 0 0 10px rgba(0,217,255,0.08)',
          }}
          animate={isListening
            ? { boxShadow: ['0 0 20px rgba(0,255,153,0.5)', '0 0 40px rgba(0,255,153,0.8)', '0 0 20px rgba(0,255,153,0.5)'] }
            : { boxShadow: ['0 0 16px rgba(0,217,255,0.4)', '0 0 28px rgba(0,217,255,0.7)', '0 0 16px rgba(0,217,255,0.4)'] }
          }
          transition={{ duration: 1.5, repeat: Infinity }}
          whileTap={{ scale: 0.92 }}
        >
          {/* Outer ring pulse */}
          {isListening && (
            <motion.div
              className="absolute rounded-full pointer-events-none"
              style={{ inset: -6, border: '1px solid rgba(0,255,153,0.3)' }}
              animate={{ scale: [1, 1.3], opacity: [0.6, 0] }}
              transition={{ duration: 1.2, repeat: Infinity }}
            />
          )}
          <AnimatePresence mode="wait">
            {isListening
              ? <motion.div key="on"  initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}><Mic  size={18} style={{ color: '#00FF99', filter: 'drop-shadow(0 0 6px #00FF99)' }} /></motion.div>
              : <motion.div key="off" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}><Mic  size={18} style={{ color: '#00D9FF', filter: 'drop-shadow(0 0 4px #00D9FF)' }} /></motion.div>
            }
          </AnimatePresence>
        </motion.button>
      </div>

      {/* ── 1.4 LISTENING status ── */}
      <div
        className="flex flex-col justify-center px-4 shrink-0"
        style={{ width: 200, borderRight: '1px solid rgba(0,217,255,0.12)', height: '100%' }}
      >
        <motion.div
          className="text-[16px] font-black tracking-[0.14em]"
          style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif', textShadow: '0 0 12px rgba(0,217,255,0.8)' }}
          animate={{ opacity: isActive ? [1, 0.6, 1] : 1 }}
          transition={{ duration: 1, repeat: Infinity }}
        >{statusLabel}</motion.div>
        <div className="text-[8px] tracking-[0.14em] mt-0.5" style={{ color: '#2A5A6A', fontFamily: 'Space Grotesk, sans-serif' }}>
          {statusSub}
        </div>
      </div>

      {/* ── 1.5 WAKE WORD panel ── */}
      <div
        className="flex flex-col justify-center px-4 shrink-0"
        style={{ width: 130, borderRight: '1px solid rgba(0,217,255,0.12)', height: '100%' }}
      >
        <div className="text-[7px] tracking-[0.22em] mb-1" style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>WAKE WORD</div>
        <div
          className="text-[14px] font-black tracking-[0.22em]"
          style={{ color: '#D8FFFF', fontFamily: 'Orbitron, sans-serif', textShadow: '0 0 10px rgba(216,255,255,0.4)' }}
        >JARVIS</div>
      </div>

      {/* ── 1.6 CPU / RAM / GPU / NET ── */}
      <div className="flex items-center flex-1 justify-center gap-0" style={{ height: '100%', borderRight: '1px solid rgba(0,217,255,0.12)' }}>
        <MetricPill label="CPU"  value={`${cpu}%`} />
        <MetricPill label="RAM"  value={`${ram}%`} />
        <MetricPill label="GPU"  value={`${gpu}%`} />
        <div className="flex flex-col items-center px-3">
          <span className="text-[8px] tracking-[0.18em]" style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>NET</span>
          <span className="text-[11px] font-black tabular-nums leading-tight" style={{ color: '#D8FFFF', fontFamily: 'Orbitron, sans-serif' }}>{net}</span>
        </div>
      </div>

      {/* ── Connection badge ── */}
      <div className="flex items-center px-3 shrink-0" style={{ height: '100%', borderRight: '1px solid rgba(0,217,255,0.12)' }}>
        <motion.div
          className="flex items-center gap-1.5 px-2 py-1 rounded-sm"
          style={{
            background: connected ? 'rgba(0,255,153,0.05)' : 'rgba(255,90,122,0.05)',
            border: `1px solid ${connected ? 'rgba(0,255,153,0.22)' : 'rgba(255,90,122,0.22)'}`,
          }}
          animate={connected ? { boxShadow: ['0 0 4px rgba(0,255,153,0.1)', '0 0 10px rgba(0,255,153,0.3)', '0 0 4px rgba(0,255,153,0.1)'] } : {}}
          transition={{ duration: 2, repeat: Infinity }}
        >
          <motion.div className="w-1.5 h-1.5 rounded-full"
            style={{ background: connected ? '#00FF99' : '#FF5A7A', boxShadow: connected ? '0 0 5px #00FF99' : '0 0 5px #FF5A7A' }}
            animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
          <span className="text-[8px] font-bold" style={{ color: connected ? '#00FF99' : '#FF5A7A', fontFamily: 'IBM Plex Mono, monospace' }}>
            {connected ? 'ONLINE' : 'OFFLINE'}
          </span>
        </motion.div>
      </div>

      {/* ── 1.7 Clock ── */}
      <div className="flex items-center px-5 shrink-0" style={{ height: '100%' }}>
        <Clock />
      </div>
    </header>
  )
}
