'use client'
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { SESSION_COLOR, sessionCountdown } from '@/lib/marketSession'
import { Mic, MicOff } from 'lucide-react'

function Clock() {
  const [time, setTime] = useState('')
  const [date, setDate] = useState('')
  useEffect(() => {
    const tick = () => {
      const n = new Date()
      setTime(n.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }))
      setDate(n.toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short' }).toUpperCase())
    }
    tick(); const id = setInterval(tick, 1000); return () => clearInterval(id)
  }, [])
  return (
    <div className="flex flex-col items-end shrink-0">
      <div className="text-[18px] font-black tabular-nums leading-none"
        style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif', textShadow: '0 0 12px rgba(0,217,255,0.9), 0 0 24px rgba(0,217,255,0.4)' }}>
        {time}
      </div>
      <div className="text-[7px] tracking-[0.2em] mt-0.5" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>{date} · IST</div>
    </div>
  )
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col items-center px-2.5" style={{ borderRight: '1px solid rgba(0,217,255,0.07)' }}>
      <span className="text-[7px] tracking-[0.18em]" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>{label}</span>
      <span className="text-[11px] font-black tabular-nums leading-tight" style={{ color: '#D8FFFF', fontFamily: 'Orbitron, sans-serif' }}>{value}</span>
    </div>
  )
}

function ScreenCorners() {
  return (
    <>
      <div className="jarvis-corner jarvis-corner-tl" />
      <div className="jarvis-corner jarvis-corner-tr" />
      <div className="jarvis-corner jarvis-corner-bl" />
      <div className="jarvis-corner jarvis-corner-br" />
    </>
  )
}

export function TopHud() {
  const status       = useJarvisStore(s => s.status)
  const connected    = useJarvisStore(s => s.connected)
  const voiceActive  = useJarvisStore(s => s.voiceActive)
  const setVoiceActive = useJarvisStore(s => s.setVoiceActive)
  const llmInfo      = useJarvisStore(s => s.llmInfo)
  const marketSession = useJarvisStore(s => s.marketSession)
  const [tick, setTick] = useState(0)
  useEffect(() => { const id = setInterval(() => setTick(t => t + 1), 5000); return () => clearInterval(id) }, [])

  const isListening = status === 'listening'
  const isActive    = ['listening', 'speaking', 'thinking', 'executing'].includes(status)

  const cpu = 12 + (tick % 9)
  const ram = 40 + (tick % 8)
  const gpu = 28 + (tick % 6)

  const stateMsg: Record<string, string> = {
    idle:      '● SYSTEM READY',
    listening: '● LISTENING — VOICE INPUT ACTIVE',
    thinking:  '● PROCESSING — AI ANALYSIS RUNNING',
    speaking:  '● TRANSMITTING — JARVIS SPEAKING',
    executing: '● EXECUTING — OPERATION IN PROGRESS',
  }
  const stateColor: Record<string, string> = {
    idle: '#1a3a5c', listening: '#00FF99', thinking: '#009DFF', speaking: '#33F2FF', executing: '#FFC857',
  }

  const toggleMic = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) { alert('Use Chrome or Edge for voice support.'); return }
    setVoiceActive(!voiceActive)
  }

  return (
    <header
      className="relative shrink-0 flex items-center h-[44px] z-50"
      style={{
        background: 'linear-gradient(180deg, rgba(2,8,19,0.99) 0%, rgba(4,14,30,0.97) 100%)',
        borderBottom: '1px solid rgba(0,217,255,0.1)',
        boxShadow: '0 1px 30px rgba(0,0,0,0.8)',
      }}
    >
      <ScreenCorners />
      {/* Top shimmer */}
      <div className="absolute top-0 left-0 right-0 h-px border-shimmer" />

      {/* State message */}
      <div className="flex items-center px-4 flex-1 min-w-0">
        <motion.span
          className="text-[8px] font-bold tracking-[0.22em] truncate"
          style={{ color: stateColor[status] || stateColor.idle, fontFamily: 'Rajdhani, sans-serif' }}
          animate={isActive ? { opacity: [1, 0.5, 1] } : { opacity: 1 }}
          transition={{ duration: 1.2, repeat: Infinity }}
        >
          {stateMsg[status] || stateMsg.idle}
        </motion.span>
      </div>

      {/* Market session badge */}
      <div className="flex items-center px-2.5 shrink-0" style={{ borderLeft: '1px solid rgba(0,217,255,0.07)', height: '100%' }}>
        <div className="flex flex-col items-center">
          <div className="flex items-center gap-1">
            <motion.div
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: SESSION_COLOR[marketSession.status], boxShadow: `0 0 4px ${SESSION_COLOR[marketSession.status]}` }}
              animate={marketSession.status === 'open' ? { opacity: [1, 0.3, 1] } : { opacity: 1 }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span className="text-[8px] font-bold tracking-[0.12em]" style={{ color: SESSION_COLOR[marketSession.status], fontFamily: 'Orbitron, sans-serif' }}>
              {marketSession.label.toUpperCase()}
            </span>
          </div>
          {sessionCountdown(marketSession) && (
            <span className="text-[6px] tracking-[0.1em]" style={{ color: 'rgba(255,255,255,0.3)', fontFamily: 'IBM Plex Mono, monospace' }}>
              {sessionCountdown(marketSession)}
            </span>
          )}
        </div>
      </div>

      {/* Metrics */}
      <div className="flex items-center shrink-0" style={{ borderLeft: '1px solid rgba(0,217,255,0.07)', height: '100%' }}>
        <MetricPill label="CPU" value={`${cpu}%`} />
        <MetricPill label="RAM" value={`${ram}%`} />
        <MetricPill label="GPU" value={`${gpu}%`} />
        <div className="flex flex-col items-center px-2.5" style={{ borderRight: '1px solid rgba(0,217,255,0.07)' }}>
          <span className="text-[7px] tracking-[0.18em]" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>LLM</span>
          <span className="text-[9px] font-black tabular-nums leading-tight truncate max-w-[60px]"
            style={{ color: llmInfo.status === 'connected' ? '#00FF99' : '#FF5A7A', fontFamily: 'Orbitron, sans-serif' }}>
            {llmInfo.provider !== '—' ? llmInfo.provider.toUpperCase() : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* Mic toggle */}
      <div className="flex items-center px-3 shrink-0" style={{ borderLeft: '1px solid rgba(0,217,255,0.07)', height: '100%' }}>
        <motion.button
          onClick={toggleMic}
          className="flex items-center justify-center rounded-full"
          style={{
            width: 28, height: 28,
            background: isListening ? 'rgba(0,255,153,0.1)' : 'rgba(0,217,255,0.06)',
            border: `1.5px solid ${isListening ? '#00FF99' : 'rgba(0,217,255,0.25)'}`,
          }}
          animate={isListening ? { boxShadow: ['0 0 10px rgba(0,255,153,0.4)', '0 0 20px rgba(0,255,153,0.7)', '0 0 10px rgba(0,255,153,0.4)'] } : {}}
          transition={{ duration: 1.2, repeat: Infinity }}
          whileTap={{ scale: 0.9 }}
        >
          {isListening
            ? <Mic size={12} style={{ color: '#00FF99', filter: 'drop-shadow(0 0 4px #00FF99)' }} />
            : <MicOff size={12} style={{ color: '#2A5A6A' }} />
          }
        </motion.button>
      </div>

      {/* Connection */}
      <div className="flex items-center px-3 shrink-0" style={{ borderLeft: '1px solid rgba(0,217,255,0.07)', height: '100%' }}>
        <motion.div
          className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm"
          style={{
            background: connected ? 'rgba(0,255,153,0.04)' : 'rgba(255,90,122,0.04)',
            border: `1px solid ${connected ? 'rgba(0,255,153,0.18)' : 'rgba(255,90,122,0.18)'}`,
          }}
        >
          <motion.div className="w-1.5 h-1.5 rounded-full"
            style={{ background: connected ? '#00FF99' : '#FF5A7A', boxShadow: connected ? '0 0 5px #00FF99' : '0 0 5px #FF5A7A' }}
            animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
          <span className="text-[7px] font-bold" style={{ color: connected ? '#00FF99' : '#FF5A7A', fontFamily: 'IBM Plex Mono, monospace' }}>
            {connected ? 'ONLINE' : 'OFFLINE'}
          </span>
        </motion.div>
      </div>

      {/* Clock */}
      <div className="flex items-center px-4 shrink-0" style={{ borderLeft: '1px solid rgba(0,217,255,0.07)', height: '100%' }}>
        <Clock />
      </div>
    </header>
  )
}
