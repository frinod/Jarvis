'use client'
import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { HolographicCore } from '@/components/HolographicCore'
import { Send, Terminal, ChevronDown, AlertTriangle, CheckCircle, XCircle, Cpu, Activity } from 'lucide-react'
import { routeVoiceCommand } from '@/lib/voiceRouter'
import { classifyVoiceIntent, updateConversationContext } from '@/lib/intentRouter'
import { executeToolPlan } from '@/lib/capabilityTools'
import * as sfx from '@/lib/sfx'
import * as music from '@/lib/music'

// ── Side HUD node ─────────────────────────────────────────────
function HudNode({ label, side }: { label: string; side: 'left' | 'right' }) {
  return (
    <motion.div
      className="flex items-center gap-2 px-3 py-1.5"
      style={{
        background: 'rgba(2,8,19,0.85)',
        border: '1px solid rgba(0,217,255,0.18)',
        borderRadius: 2,
        minWidth: 58,
        justifyContent: side === 'left' ? 'flex-start' : 'flex-end',
      }}
      animate={{ opacity: [0.65, 1, 0.65] }}
      transition={{ duration: 2.5, repeat: Infinity }}
    >
      {side === 'left' && (
        <motion.div className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: '#00D9FF', boxShadow: '0 0 5px #00D9FF' }}
          animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1.2, repeat: Infinity }} />
      )}
      <span className="text-[10px] font-bold tracking-[0.2em]"
        style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>{label}</span>
      {side === 'right' && (
        <motion.div className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: '#00D9FF', boxShadow: '0 0 5px #00D9FF' }}
          animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1.2, repeat: Infinity }} />
      )}
    </motion.div>
  )
}

// ── Status waveform ───────────────────────────────────────────
const WAVEFORM_BARS = Array.from({ length: 40 }, (_, i) => ({
  h: Math.random() * 20 + 2, dur: 0.15 + Math.random() * 0.35, delay: i * 0.02,
}))
function StatusWaveform({ active }: { active: boolean }) {
  const bars = WAVEFORM_BARS
  return (
    <div className="flex items-center gap-[2px]" style={{ height: 24 }}>
      {bars.map((b, i) => (
        <motion.div key={i}
          style={{ width: 2, background: 'rgba(0,217,255,0.5)', borderRadius: 1 }}
          animate={active ? { height: [1, b.h, 1] } : { height: 2 }}
          transition={{ duration: b.dur, repeat: Infinity, delay: b.delay, ease: 'easeInOut' }}
        />
      ))}
    </div>
  )
}

// ── Provider labels ───────────────────────────────────────────
const PROVIDER_LABELS: Record<string, { label: string; color: string }> = {
  gemini: { label: 'Gemini', color: '#00D9FF' }, groq: { label: 'Groq', color: '#7B5EA7' },
  deepseek: { label: 'DeepSeek', color: '#00F5FF' }, openai: { label: 'OpenAI', color: '#00FF9C' },
  ollama: { label: 'Ollama', color: '#FFB347' },
}

interface TradeProposal {
  confirmation_id: string; symbol: string; trade_type: string
  qty: number; price: number; estimated_cost: number
  signal: string; confidence: number; trend: string
  stop_loss: number; target1: number; target2: number; risk_reward: number
}

// ── Command Console ───────────────────────────────────────────
function CommandConsole() {
  const [input, setInput] = useState('')
  const [providerOpen, setProviderOpen] = useState(false)
  const [tradeProposal, setTradeProposal] = useState<TradeProposal | null>(null)
  const [tradeConfirming, setTradeConfirming] = useState(false)
  const { messages, sendMessage, status, llmInfo } = useJarvisStore()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => {
    const last = messages[messages.length - 1]
    if (last?.role === 'assistant' && last.tradeProposal) setTradeProposal(last.tradeProposal)
  }, [messages])

  const handleSend = () => {
    if (!input.trim()) return
    const handled = routeVoiceCommand(input.trim())
    if (!handled) sendMessage(input.trim())
    setInput('')
  }

  const handleTradeConfirm = async (approved: boolean) => {
    if (!tradeProposal) return
    setTradeConfirming(true)
    try {
      const { API_URL } = await import('@/store/jarvisStore')
      const res = await fetch(`${API_URL}/api/paper/ai-trade/confirm`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirmation_id: tradeProposal.confirmation_id, approved }),
      })
      const data = await res.json()
      const msg = approved
        ? `Trade executed. ${tradeProposal.trade_type} ${tradeProposal.qty} × ${tradeProposal.symbol} @ ₹${tradeProposal.price}. ${data.message ?? ''}`
        : 'Trade cancelled.'
      useJarvisStore.getState().addSystemMessage(msg)
    } catch { useJarvisStore.getState().addSystemMessage('Trade confirmation failed.') }
    finally { setTradeProposal(null); setTradeConfirming(false) }
  }

  const activeLabel = PROVIDER_LABELS[llmInfo.provider] ?? { label: llmInfo.provider, color: '#2A5A6A' }
  const available   = llmInfo.model !== '—' ? llmInfo.model.split(', ').filter(Boolean) : []
  const switchable  = available.filter(p => p !== llmInfo.provider)

  const switchProvider = async (name: string) => {
    try {
      const { API_URL } = await import('@/store/jarvisStore')
      await fetch(`${API_URL}/api/llm/provider/${name}`, { method: 'POST' })
      useJarvisStore.getState().fetchStatus()
    } catch {}
    setProviderOpen(false)
  }

  return (
    <div className="flex flex-col overflow-hidden"
      style={{ height: 210, borderTop: '1px solid rgba(0,217,255,0.12)', background: 'rgba(2,8,19,0.98)' }}>

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-2 shrink-0"
        style={{ borderBottom: '1px solid rgba(0,217,255,0.08)', background: 'rgba(0,217,255,0.02)' }}>
        <div className="flex items-center gap-2.5">
          <Terminal size={11} style={{ color: '#00D9FF' }} />
          <span className="text-[9px] font-bold tracking-[0.22em]"
            style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>COMMAND CONSOLE</span>
        </div>
        <div className="flex items-center gap-2">
          <motion.div className="flex items-center gap-1.5 px-2.5 py-1"
            style={{ background: 'rgba(255,200,87,0.06)', border: '1px solid rgba(255,200,87,0.25)', borderRadius: 2 }}
            animate={{ opacity: status === 'executing' ? [1, 0.5, 1] : 1 }}
            transition={{ duration: 0.8, repeat: Infinity }}>
            <motion.div className="w-1.5 h-1.5 rounded-full"
              style={{ background: '#FFC857', boxShadow: '0 0 4px #FFC857' }}
              animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 0.6, repeat: Infinity }} />
            <span className="text-[8px] font-bold tracking-[0.14em]"
              style={{ color: '#FFC857', fontFamily: 'Orbitron, sans-serif' }}>
              {status === 'executing' ? 'EXECUTING' : status === 'thinking' ? 'PROCESSING' : 'READY'}
            </span>
          </motion.div>
          {available.length > 1 && (
            <div className="relative">
              <button onClick={() => setProviderOpen(o => !o)}
                className="flex items-center gap-1 text-[8px] font-bold px-2 py-1 tracking-widest"
                style={{ color: activeLabel.color, background: `${activeLabel.color}12`,
                  border: `1px solid ${activeLabel.color}30`, borderRadius: 2, fontFamily: 'Orbitron, sans-serif', cursor: 'pointer' }}>
                {activeLabel.label.toUpperCase()}
                {switchable.length > 0 && <ChevronDown size={8} />}
              </button>
              {providerOpen && switchable.length > 0 && (
                <div className="absolute top-full right-0 mt-1 z-50 min-w-[90px]"
                  style={{ background: '#081328', border: '1px solid rgba(0,217,255,0.18)', borderRadius: 2 }}>
                  {switchable.map(p => {
                    const pl = PROVIDER_LABELS[p] ?? { label: p, color: '#2A5A6A' }
                    return (
                      <button key={p} onClick={() => switchProvider(p)}
                        className="w-full text-left px-3 py-2 text-[8px] font-bold tracking-widest"
                        style={{ color: pl.color, fontFamily: 'Orbitron, sans-serif', cursor: 'pointer' }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,217,255,0.06)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                        {pl.label.toUpperCase()}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Trade confirmation */}
      <AnimatePresence>
        {tradeProposal && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            className="mx-4 mt-2 p-3 shrink-0"
            style={{ background: 'rgba(255,179,71,0.04)', border: '1px solid rgba(255,179,71,0.28)', borderRadius: 2 }}>
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={10} style={{ color: '#FFB347' }} />
              <span className="text-[8px] font-bold tracking-[0.16em]"
                style={{ color: '#FFB347', fontFamily: 'Orbitron, sans-serif' }}>AWAITING CONFIRMATION</span>
            </div>
            <div className="grid grid-cols-4 gap-x-4 gap-y-1 text-[9px] mb-2">
              {[
                ['Action', <span key="a" style={{ color: tradeProposal.trade_type === 'BUY' ? '#00FF9C' : '#FF4D6D', fontWeight: 700 }}>{tradeProposal.trade_type}</span>],
                ['Symbol', <span key="s" style={{ color: '#C8F9FF' }}>{tradeProposal.symbol}</span>],
                ['Qty',    <span key="q" style={{ color: '#C8F9FF' }}>{tradeProposal.qty}</span>],
                ['Price',  <span key="p" style={{ color: '#C8F9FF' }}>₹{tradeProposal.price}</span>],
              ].map(([l, v], i) => (
                <div key={i} className="flex gap-1">
                  <span style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>{l}:</span>{v}
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <button onClick={() => handleTradeConfirm(true)} disabled={tradeConfirming}
                className="flex items-center gap-1.5 px-3 py-1 text-[8px] font-bold tracking-widest disabled:opacity-50"
                style={{ background: 'rgba(0,255,156,0.08)', border: '1px solid rgba(0,255,156,0.3)',
                  color: '#00FF9C', borderRadius: 2, fontFamily: 'Orbitron, sans-serif', cursor: 'pointer' }}>
                <CheckCircle size={9} /> CONFIRM
              </button>
              <button onClick={() => handleTradeConfirm(false)} disabled={tradeConfirming}
                className="flex items-center gap-1.5 px-3 py-1 text-[8px] font-bold tracking-widest disabled:opacity-50"
                style={{ background: 'rgba(255,77,109,0.08)', border: '1px solid rgba(255,77,109,0.3)',
                  color: '#FF4D6D', borderRadius: 2, fontFamily: 'Orbitron, sans-serif', cursor: 'pointer' }}>
                <XCircle size={9} /> CANCEL
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-2 space-y-1.5" style={{ scrollbarWidth: 'none' }}>
        {messages.length === 0 && (
          <div className="flex flex-col gap-1 pt-0.5">
            {[
              { role: 'user', text: '>>> Hello Jarvis' },
              { role: 'assistant', text: 'JARVIS: Hello Sir. All systems operational. How can I assist you today?' },
            ].map((m, i) => (
              <div key={i} className="text-[10px] leading-relaxed"
                style={{ color: m.role === 'user' ? '#D8FFFF' : '#00D9FF', fontFamily: 'IBM Plex Mono, monospace' }}>
                {m.text}
              </div>
            ))}
            <div className="text-[10px]" style={{ color: '#D8FFFF', fontFamily: 'IBM Plex Mono, monospace' }}>
              {'>>> '}
              <motion.span animate={{ opacity: [1, 0, 1] }} transition={{ duration: 1, repeat: Infinity }}>▋</motion.span>
            </div>
          </div>
        )}
        <AnimatePresence>
          {messages.map(msg => (
            <motion.div key={msg.id} initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }}>
              {msg.role === 'user'
                ? <div className="text-[10px]" style={{ color: '#D8FFFF', fontFamily: 'IBM Plex Mono, monospace' }}>{'>>> '}{msg.content}</div>
                : <div className="text-[10px] leading-relaxed" style={{ color: '#00D9FF', fontFamily: 'IBM Plex Mono, monospace' }}>JARVIS: {msg.content}</div>
              }
            </motion.div>
          ))}
        </AnimatePresence>
        {status === 'thinking' && (
          <div className="flex items-center gap-2">
            <span className="text-[9px]" style={{ color: '#2A5A6A', fontFamily: 'IBM Plex Mono, monospace' }}>JARVIS:</span>
            {[0, 1, 2].map(i => (
              <motion.div key={i} className="w-1.5 h-1.5 rounded-full" style={{ background: '#009DFF' }}
                animate={{ y: [0, -5, 0], opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.12 }} />
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-5 pb-3 shrink-0" style={{ borderTop: '1px solid rgba(0,217,255,0.07)' }}>
        <div className="flex items-center gap-2.5 px-3 py-2 mt-2"
          style={{ background: 'rgba(0,217,255,0.025)', border: '1px solid rgba(0,217,255,0.12)', borderRadius: 2 }}>
          <span style={{ color: '#00D9FF', fontFamily: 'IBM Plex Mono, monospace', fontSize: 13 }}>›</span>
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="Command JARVIS, Sir..."
            className="flex-1 bg-transparent outline-none"
            style={{ fontSize: 11, color: '#C8F9FF', fontFamily: 'Space Grotesk, sans-serif' }} />
          <motion.button onClick={handleSend} disabled={!input.trim()}
            style={{ background: input.trim() ? 'rgba(0,217,255,0.1)' : 'transparent',
              border: `1px solid ${input.trim() ? 'rgba(0,217,255,0.3)' : 'rgba(0,217,255,0.07)'}`,
              borderRadius: 2, padding: '4px 8px', color: input.trim() ? '#00D9FF' : '#2A5A6A', cursor: 'pointer' }}
            whileTap={input.trim() ? { scale: 0.95 } : {}}>
            <Send size={11} />
          </motion.button>
        </div>
      </div>
    </div>
  )
}

// ── CENTER WORKSPACE ──────────────────────────────────────────
export function CenterWorkspace() {
  const { status } = useJarvisStore()
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

  const uptimeStr = `${String(uptime.h).padStart(2, '0')}:${String(uptime.m).padStart(2, '0')}:${String(uptime.s).padStart(2, '0')}`

  const coreStatus = status === 'idle' ? 'OPTIMAL' : status === 'thinking' ? 'PROCESSING'
    : status === 'speaking' ? 'TRANSMITTING' : status === 'listening' ? 'LISTENING' : 'EXECUTING'
  const coreColor = status === 'idle' ? '#00FF99' : status === 'thinking' ? '#009DFF'
    : status === 'speaking' ? '#33F2FF' : status === 'listening' ? '#00FF99' : '#FFC857'

  const isActive = status !== 'idle'

  return (
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden"
      style={{ borderRight: '1px solid rgba(0,217,255,0.08)' }}>

      {/* ── AI Core area ── */}
      <div className="flex-1 flex items-center justify-center relative min-h-0 overflow-hidden"
        style={{ background: 'linear-gradient(135deg, rgba(4,14,30,0.8) 0%, rgba(2,8,19,0.9) 100%)' }}>

        {/* Background radial glow */}
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse 50% 60% at 50% 50%, rgba(0,217,255,0.03) 0%, transparent 70%)' }} />

        {/* Corner brackets */}
        {[
          { top: 12, left: 12,   borderWidth: '1.5px 0 0 1.5px' },
          { top: 12, right: 12,  borderWidth: '1.5px 1.5px 0 0' },
          { bottom: 12, left: 12,  borderWidth: '0 0 1.5px 1.5px' },
          { bottom: 12, right: 12, borderWidth: '0 1.5px 1.5px 0' },
        ].map((s, i) => (
          <div key={i} className="absolute pointer-events-none"
            style={{ ...s, width: 24, height: 24, borderStyle: 'solid', borderColor: 'rgba(0,217,255,0.35)' }} />
        ))}

        {/* Left HUD nodes */}
        <div className="absolute left-6 flex flex-col gap-3" style={{ top: '50%', transform: 'translateY(-50%)' }}>
          {['SYS', 'NET', 'AI'].map(l => <HudNode key={l} label={l} side="left" />)}
        </div>

        {/* Holographic Core — scaled to 70% of 400px = 280px effective */}
        <div className="flex items-center justify-center" style={{ transform: 'scale(0.70)', transformOrigin: 'center center' }}>
          <HolographicCore />
        </div>

        {/* Right HUD nodes */}
        <div className="absolute right-6 flex flex-col gap-3" style={{ top: '50%', transform: 'translateY(-50%)' }}>
          {['MEM', 'CPU', 'GPU'].map(l => <HudNode key={l} label={l} side="right" />)}
        </div>
      </div>

      {/* ── AI Core status bar ── */}
      <div className="shrink-0 flex items-center gap-5 px-6"
        style={{ height: 52, background: 'rgba(2,8,19,0.98)', borderTop: '1px solid rgba(0,217,255,0.12)' }}>
        <div className="flex flex-col shrink-0">
          <span className="text-[8px] tracking-[0.2em]" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>AI CORE STATUS</span>
          <motion.span className="text-[11px] font-black tracking-[0.16em]"
            style={{ color: coreColor, fontFamily: 'Orbitron, sans-serif', textShadow: `0 0 8px ${coreColor}` }}
            animate={{ opacity: [1, 0.6, 1] }} transition={{ duration: 1.5, repeat: Infinity }}>
            {coreStatus}
          </motion.span>
        </div>
        <div className="flex-1"><StatusWaveform active={isActive} /></div>
        <div className="flex flex-col items-end shrink-0">
          <span className="text-[8px] tracking-[0.2em]" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>UPTIME</span>
          <span className="text-[12px] font-black tabular-nums"
            style={{ color: '#D8FFFF', fontFamily: 'Orbitron, sans-serif' }}>{uptimeStr}</span>
        </div>
      </div>

      {/* ── Command Console ── */}
      <CommandConsole />
    </div>
  )
}
