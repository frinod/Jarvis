'use client'
import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { Mic, MicOff, Send, Terminal, ChevronDown, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { routeVoiceCommand } from '@/lib/voiceRouter'
// Voice engine is in VoiceBar.tsx — this panel only controls the store flag

// ── Voice waveform bars ───────────────────────────────────────
const BARS = Array.from({ length: 40 }, (_, i) => ({
  maxH: Math.random() * 28 + 4,
  dur:  0.18 + Math.random() * 0.45,
  delay: i * 0.018,
}))

// ── 5.1 Voice Command Panel ───────────────────────────────────
// NOTE: actual SpeechRecognition engine lives in VoiceBar (mounted in page.tsx)
// This panel is purely UI — it reads/writes the same voiceActive store flag
function VoiceCommandPanel() {
  const { status, voiceActive, setVoiceActive } = useJarvisStore()
  const isListening = status === 'listening'
  const isActive    = ['listening','speaking','thinking','executing'].includes(status)

  const barColor = isListening ? '#00FF99' : isActive ? '#00D9FF' : '#1a3a5c'

  const toggle = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) { alert('Use Chrome or Edge for voice support.'); return }
    // Toggling voiceActive triggers the engine in VoiceBar
    setVoiceActive(!voiceActive)
  }

  return (
    <div
      className="flex flex-col shrink-0"
      style={{
        width: 280,
        background: 'rgba(3,10,24,0.97)',
        border: '1px solid rgba(0,217,255,0.12)',
        borderRadius: 2,
        padding: '12px 14px',
        boxShadow: 'inset 0 0 20px rgba(0,217,255,0.02)',
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <motion.div className="w-1.5 h-1.5 rounded-full"
          style={{ background: '#00D9FF', boxShadow: '0 0 5px #00D9FF' }}
          animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1.4, repeat: Infinity }} />
        <span className="text-[8px] font-bold tracking-[0.24em]"
          style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>VOICE COMMAND</span>
      </div>

      {/* Waveform */}
      <div className="flex items-center gap-[1.5px] mb-3 relative" style={{ height: 56 }}>
        {isActive && (
          <div className="absolute inset-0 pointer-events-none"
            style={{ background: `radial-gradient(ellipse 70% 100% at 50% 50%, ${barColor}22 0%, transparent 70%)` }} />
        )}
        {BARS.map((b, i) => (
          <motion.div key={i}
            style={{ width: 2, background: isActive ? `linear-gradient(180deg, ${barColor}, ${barColor}66)` : '#1a3a5c',
              borderRadius: 1, boxShadow: isActive ? `0 0 3px ${barColor}` : 'none' }}
            animate={isActive ? { height: [2, b.maxH * (0.3 + 0.7 * Math.random()), 2] } : { height: 2 }}
            transition={{ duration: b.dur, repeat: Infinity, delay: b.delay, ease: 'easeInOut' }}
          />
        ))}
      </div>

      {/* Status text */}
      <div className="flex items-center justify-between">
        <div>
          <motion.div className="text-[9px] font-bold tracking-[0.14em]"
            style={{ color: isListening ? '#00FF99' : '#2A5A6A', fontFamily: 'Orbitron, sans-serif' }}
            animate={isListening ? { opacity: [1, 0.4, 1] } : {}}
            transition={{ duration: 1, repeat: Infinity }}>
            {isListening ? 'Listening...' : 'Speak now'}
          </motion.div>
          <div className="text-[7.5px] mt-0.5"
            style={{ color: '#2A5A6A', fontFamily: 'Space Grotesk, sans-serif' }}>
            {isListening ? 'Processing voice input' : 'Click mic to activate'}
          </div>
        </div>

        {/* Mic button */}
        <motion.button onClick={toggle}
          className="flex items-center justify-center rounded-full"
          style={{
            width: 32, height: 32,
            background: isListening ? 'rgba(0,255,153,0.1)' : 'rgba(0,217,255,0.06)',
            border: `1.5px solid ${isListening ? '#00FF99' : 'rgba(0,217,255,0.3)'}`,
            boxShadow: isListening ? '0 0 14px rgba(0,255,153,0.4)' : '0 0 8px rgba(0,217,255,0.2)',
          }}
          animate={isListening ? { boxShadow: ['0 0 14px rgba(0,255,153,0.4)', '0 0 24px rgba(0,255,153,0.7)', '0 0 14px rgba(0,255,153,0.4)'] } : {}}
          transition={{ duration: 1.2, repeat: Infinity }}
          whileTap={{ scale: 0.9 }}
        >
          {isListening
            ? <Mic size={14} style={{ color: '#00FF99', filter: 'drop-shadow(0 0 4px #00FF99)' }} />
            : <MicOff size={14} style={{ color: '#2A5A6A' }} />
          }
        </motion.button>
      </div>
    </div>
  )
}

// ── Provider labels ───────────────────────────────────────────
const PROVIDER_LABELS: Record<string, { label: string; color: string }> = {
  openrouter: { label: 'OpenRouter', color: '#FF6B6B' },
  gemini:     { label: 'Gemini',     color: '#00D9FF' },
  groq:       { label: 'Groq',       color: '#7B5EA7' },
  deepseek:   { label: 'DeepSeek',   color: '#00F5FF' },
  openai:     { label: 'OpenAI',     color: '#00FF9C' },
  ollama:     { label: 'Ollama',     color: '#FFB347' },
}

interface TradeProposal {
  confirmation_id: string; symbol: string; trade_type: string
  qty: number; price: number; estimated_cost: number
  signal: string; confidence: number; trend: string
  stop_loss: number; target1: number; target2: number; risk_reward: number
}

// ── 5.2 Command Console ───────────────────────────────────────
function CommandConsole() {
  const [input, setInput] = useState('')
  const [providerOpen, setProviderOpen] = useState(false)
  const [tradeProposal, setTradeProposal] = useState<TradeProposal | null>(null)
  const [tradeConfirming, setTradeConfirming] = useState(false)
  const { messages, sendMessage, status, llmInfo, selectedStock } = useJarvisStore()
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
        ? `Trade executed. ${tradeProposal.trade_type} ${tradeProposal.qty} × ${tradeProposal.symbol} @ Rs.${tradeProposal.price}. ${data.message ?? ''}`
        : `Trade cancelled.`
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

  // Executing confidence ring value
  const confidence = 86

  return (
    <div className="flex-1 flex overflow-hidden"
      style={{ border: '1px solid rgba(0,217,255,0.12)', borderRadius: 2, background: 'rgba(3,10,24,0.97)', boxShadow: 'inset 0 0 20px rgba(0,217,255,0.02)' }}>

      {/* Console area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 shrink-0"
          style={{ borderBottom: '1px solid rgba(0,217,255,0.08)', background: 'rgba(0,217,255,0.02)' }}>
          <div className="flex items-center gap-2">
            <Terminal size={10} style={{ color: '#00D9FF' }} />
            <span className="text-[8px] font-bold tracking-[0.22em]"
              style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>COMMAND CONSOLE</span>
          </div>
          <div className="flex items-center gap-2">
            {/* Executing badge */}
            <motion.div className="flex items-center gap-1.5 px-2 py-0.5"
              style={{ background: 'rgba(255,200,87,0.08)', border: '1px solid rgba(255,200,87,0.3)', borderRadius: 2 }}
              animate={{ opacity: status === 'executing' ? [1, 0.5, 1] : 1 }}
              transition={{ duration: 0.8, repeat: Infinity }}>
              <motion.div className="w-1 h-1 rounded-full"
                style={{ background: '#FFC857', boxShadow: '0 0 4px #FFC857' }}
                animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 0.6, repeat: Infinity }} />
              <span className="text-[7px] font-bold tracking-[0.16em]"
                style={{ color: '#FFC857', fontFamily: 'Orbitron, sans-serif' }}>
                {status === 'executing' ? 'EXECUTING' : status === 'thinking' ? 'PROCESSING' : 'READY'}
              </span>
            </motion.div>
            {/* Provider switcher */}
            {available.length > 1 && (
              <div className="relative">
                <button onClick={() => setProviderOpen(o => !o)}
                  className="flex items-center gap-1 text-[7px] font-bold px-2 py-0.5 tracking-widest"
                  style={{ color: activeLabel.color, background: `${activeLabel.color}12`,
                    border: `1px solid ${activeLabel.color}30`, borderRadius: 2, fontFamily: 'Orbitron, sans-serif' }}>
                  {activeLabel.label.toUpperCase()}
                  {switchable.length > 0 && <ChevronDown size={7} />}
                </button>
                {providerOpen && switchable.length > 0 && (
                  <div className="absolute top-full right-0 mt-1 z-50 min-w-[80px]"
                    style={{ background: '#081328', border: '1px solid rgba(0,217,255,0.18)', borderRadius: 2 }}>
                    {switchable.map(p => {
                      const pl = PROVIDER_LABELS[p] ?? { label: p, color: '#2A5A6A' }
                      return (
                        <button key={p} onClick={() => switchProvider(p)}
                          className="w-full text-left px-3 py-1.5 text-[7px] font-bold tracking-widest"
                          style={{ color: pl.color, fontFamily: 'Orbitron, sans-serif' }}
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
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
              className="mx-3 mt-2 p-3 shrink-0"
              style={{ background: 'rgba(255,179,71,0.04)', border: '1px solid rgba(255,179,71,0.3)', borderRadius: 2 }}>
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={10} style={{ color: '#FFB347' }} />
                <span className="text-[8px] font-bold tracking-[0.16em]"
                  style={{ color: '#FFB347', fontFamily: 'Orbitron, sans-serif' }}>AWAITING CONFIRMATION</span>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[9px] mb-2">
                {[
                  ['Action', <span style={{ color: tradeProposal.trade_type === 'BUY' ? '#00FF9C' : '#FF4D6D', fontWeight: 700 }}>{tradeProposal.trade_type}</span>],
                  ['Symbol', <span style={{ color: '#C8F9FF' }}>{tradeProposal.symbol}</span>],
                  ['Qty',    <span style={{ color: '#C8F9FF' }}>{tradeProposal.qty}</span>],
                  ['Price',  <span style={{ color: '#C8F9FF' }}>Rs.{tradeProposal.price}</span>],
                ].map(([l, v], i) => (
                  <div key={i} className="flex gap-1">
                    <span style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>{l}:</span>{v}
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleTradeConfirm(true)} disabled={tradeConfirming}
                  className="flex items-center gap-1 px-3 py-1 text-[8px] font-bold tracking-widest disabled:opacity-50"
                  style={{ background: 'rgba(0,255,156,0.1)', border: '1px solid rgba(0,255,156,0.35)',
                    color: '#00FF9C', borderRadius: 2, fontFamily: 'Orbitron, sans-serif' }}>
                  <CheckCircle size={9} /> CONFIRM
                </button>
                <button onClick={() => handleTradeConfirm(false)} disabled={tradeConfirming}
                  className="flex items-center gap-1 px-3 py-1 text-[8px] font-bold tracking-widest disabled:opacity-50"
                  style={{ background: 'rgba(255,77,109,0.1)', border: '1px solid rgba(255,77,109,0.35)',
                    color: '#FF4D6D', borderRadius: 2, fontFamily: 'Orbitron, sans-serif' }}>
                  <XCircle size={9} /> CANCEL
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5" style={{ scrollbarWidth: 'none' }}>
          {messages.length === 0 && (
            <div className="flex flex-col items-start gap-1 pt-1">
              {[
                { role: 'user', text: '>>> Hello Jarvis' },
                { role: 'assistant', text: 'JARVIS: Hello Sir, how can I assist you today?' },
                { role: 'user', text: '>>> Show me today\'s market summary' },
                { role: 'assistant', text: 'JARVIS: Displaying market summary for today.' },
              ].map((m, i) => (
                <div key={i} className="text-[9px] leading-relaxed"
                  style={{ color: m.role === 'user' ? '#D8FFFF' : '#00D9FF',
                    fontFamily: 'IBM Plex Mono, monospace' }}>{m.text}</div>
              ))}
              <div className="text-[9px]" style={{ color: '#D8FFFF', fontFamily: 'IBM Plex Mono, monospace' }}>
                {'>>> '}
                <motion.span animate={{ opacity: [1, 0, 1] }} transition={{ duration: 1, repeat: Infinity }}>▋</motion.span>
              </div>
            </div>
          )}
          <AnimatePresence>
            {messages.map(msg => (
              <motion.div key={msg.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}>
                {msg.role === 'user' ? (
                  <div className="text-[9px]" style={{ color: '#D8FFFF', fontFamily: 'IBM Plex Mono, monospace' }}>
                    {'>>> '}{msg.content}
                  </div>
                ) : (
                  <div className="text-[9px] leading-relaxed" style={{ color: '#00D9FF', fontFamily: 'IBM Plex Mono, monospace' }}>
                    JARVIS: {msg.content}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
          {status === 'thinking' && (
            <div className="flex items-center gap-1.5">
              <span className="text-[8px]" style={{ color: '#2A5A6A', fontFamily: 'IBM Plex Mono, monospace' }}>JARVIS:</span>
              {[0,1,2].map(i => (
                <motion.div key={i} className="w-1 h-1 rounded-full"
                  style={{ background: '#009DFF' }}
                  animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
                  transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.12 }} />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-3 pb-2 shrink-0" style={{ borderTop: '1px solid rgba(0,217,255,0.06)' }}>
          <div className="flex items-center gap-2 px-2 py-1.5 mt-2"
            style={{ background: 'rgba(0,217,255,0.03)', border: '1px solid rgba(0,217,255,0.1)', borderRadius: 2 }}>
            <span style={{ color: '#00D9FF', fontFamily: 'IBM Plex Mono, monospace', fontSize: 11 }}>›</span>
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              placeholder="Command JARVIS, Sir..."
              className="flex-1 bg-transparent outline-none text-[10px]"
              style={{ color: '#C8F9FF', fontFamily: 'Space Grotesk, sans-serif' }} />
            <motion.button onClick={handleSend} disabled={!input.trim()}
              style={{ background: input.trim() ? 'rgba(0,217,255,0.12)' : 'transparent',
                border: `1px solid ${input.trim() ? 'rgba(0,217,255,0.3)' : 'rgba(0,217,255,0.06)'}`,
                borderRadius: 2, padding: '3px 6px', color: input.trim() ? '#00D9FF' : '#2A5A6A' }}
              whileTap={input.trim() ? { scale: 0.95 } : {}}>
              <Send size={10} />
            </motion.button>
          </div>
        </div>
      </div>

      {/* ── Confidence ring (right side) ── */}
      <div className="flex items-center justify-center shrink-0 px-3"
        style={{ borderLeft: '1px solid rgba(0,217,255,0.08)', width: 80 }}>
        <div className="relative flex items-center justify-center" style={{ width: 64, height: 64 }}>
          {/* Spinning dashes ring */}
          <motion.div className="absolute rounded-full"
            style={{ inset: 0, border: '2px dashed rgba(0,217,255,0.25)' }}
            animate={{ rotate: 360 }} transition={{ duration: 8, repeat: Infinity, ease: 'linear' }} />
          <svg width="64" height="64" viewBox="0 0 64 64" className="absolute">
            <circle cx="32" cy="32" r="26" fill="none" stroke="rgba(0,217,255,0.06)" strokeWidth="4" />
            <motion.circle cx="32" cy="32" r="26" fill="none" stroke="#00D9FF" strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={`${2 * Math.PI * 26}`}
              initial={{ strokeDashoffset: 2 * Math.PI * 26 }}
              animate={{ strokeDashoffset: 2 * Math.PI * 26 * (1 - confidence / 100) }}
              transition={{ duration: 1.5, ease: 'easeOut' }}
              style={{ transformOrigin: '32px 32px', transform: 'rotate(-90deg)',
                filter: 'drop-shadow(0 0 4px rgba(0,217,255,0.8))' }} />
          </svg>
          <div className="flex flex-col items-center">
            <span className="text-[14px] font-black tabular-nums"
              style={{ color: '#D8FFFF', fontFamily: 'Orbitron, sans-serif', lineHeight: 1 }}>{confidence}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── BOTTOM ROW ────────────────────────────────────────────────
export function BottomRow() {
  return (
    <div className="flex shrink-0 gap-2 overflow-hidden"
      style={{ height: 200, padding: '0 10px 8px 10px' }}>
      <VoiceCommandPanel />
      <CommandConsole />
    </div>
  )
}
