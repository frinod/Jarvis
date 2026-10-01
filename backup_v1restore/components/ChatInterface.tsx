'use client'

import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, ChevronDown, AlertTriangle, CheckCircle, XCircle, Terminal } from 'lucide-react'
import { useJarvisStore, Message } from '@/store/jarvisStore'

const PROVIDER_LABELS: Record<string, { label: string; color: string }> = {
  gemini:   { label: 'Gemini',   color: '#00D9FF' },
  groq:     { label: 'Groq',     color: '#7B5EA7' },
  deepseek: { label: 'DeepSeek', color: '#00F5FF' },
  openai:   { label: 'OpenAI',   color: '#00FF9C' },
  ollama:   { label: 'Ollama',   color: '#FFB347' },
}

interface TradeProposal {
  confirmation_id: string
  symbol: string
  trade_type: string
  qty: number
  price: number
  estimated_cost: number
  signal: string
  confidence: number
  trend: string
  stop_loss: number
  target1: number
  target2: number
  risk_reward: number
}

export function ChatInterface() {
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
    sendMessage(input.trim())
    setInput('')
  }

  const handleTradeConfirm = async (approved: boolean) => {
    if (!tradeProposal) return
    setTradeConfirming(true)
    try {
      const { API_URL } = await import('@/store/jarvisStore')
      const res = await fetch(`${API_URL}/api/paper/ai-trade/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirmation_id: tradeProposal.confirmation_id, approved }),
      })
      const data = await res.json()
      const msg = approved
        ? `Trade executed, Sir. ${tradeProposal.trade_type} ${tradeProposal.qty} × ${tradeProposal.symbol} @ ₹${tradeProposal.price}. ${data.message ?? ''}`
        : `Trade cancelled as instructed, Sir.`
      useJarvisStore.getState().addSystemMessage(msg)
    } catch {
      useJarvisStore.getState().addSystemMessage('Trade confirmation failed, Sir. Please retry.')
    } finally {
      setTradeProposal(null)
      setTradeConfirming(false)
    }
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
    <div
      className="flex-1 flex flex-col overflow-hidden"
      style={{
        background: 'rgba(8,19,40,0.8)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(0,217,255,0.1)',
        borderRadius: 2,
      }}
    >
      {/* Console header */}
      <div
        className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ borderBottom: '1px solid rgba(0,217,255,0.08)', background: 'rgba(0,217,255,0.02)' }}
      >
        <div className="flex items-center gap-2">
          <Terminal size={11} style={{ color: '#00D9FF' }} />
          <span className="text-[9px] font-bold tracking-[0.2em]" style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>
            COMMAND CONSOLE
          </span>
        </div>
        {available.length > 1 && (
          <div className="relative">
            <button
              onClick={() => setProviderOpen(o => !o)}
              disabled={switchable.length === 0}
              className="flex items-center gap-1 text-[8px] font-bold px-2 py-0.5 tracking-widest"
              style={{
                color: activeLabel.color,
                background: `${activeLabel.color}12`,
                border: `1px solid ${activeLabel.color}30`,
                borderRadius: 2,
                fontFamily: 'Orbitron, sans-serif',
              }}
            >
              {activeLabel.label.toUpperCase()}
              {switchable.length > 0 && <ChevronDown size={8} />}
            </button>
            {providerOpen && switchable.length > 0 && (
              <div
                className="absolute top-full right-0 mt-1 z-50 overflow-hidden min-w-[90px]"
                style={{ background: '#081328', border: '1px solid rgba(0,217,255,0.18)', borderRadius: 2 }}
              >
                {switchable.map(p => {
                  const pl = PROVIDER_LABELS[p] ?? { label: p, color: '#2A5A6A' }
                  return (
                    <button
                      key={p}
                      onClick={() => switchProvider(p)}
                      className="w-full text-left px-3 py-1.5 text-[8px] font-bold tracking-widest"
                      style={{ color: pl.color, fontFamily: 'Orbitron, sans-serif' }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,217,255,0.06)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      {pl.label.toUpperCase()}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stock context */}
      {selectedStock && (
        <div
          className="flex items-center gap-1.5 px-3 py-1.5 shrink-0"
          style={{ background: 'rgba(0,217,255,0.04)', borderBottom: '1px solid rgba(0,217,255,0.06)' }}
        >
          <span className="text-[8px]">📈</span>
          <span className="text-[8px] tracking-widest" style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>MONITORING:</span>
          <span className="text-[9px] font-bold" style={{ color: '#00D9FF', fontFamily: 'IBM Plex Mono, monospace' }}>{selectedStock}</span>
        </div>
      )}

      {/* Trade confirmation */}
      <AnimatePresence>
        {tradeProposal && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mx-3 mt-3 p-4 shrink-0"
            style={{
              background: 'rgba(255,179,71,0.04)',
              border: '1px solid rgba(255,179,71,0.3)',
              borderRadius: 2,
              boxShadow: '0 0 20px rgba(255,179,71,0.08)',
            }}
          >
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle size={12} style={{ color: '#FFB347' }} />
              <span className="text-[9px] font-bold tracking-[0.18em]" style={{ color: '#FFB347', fontFamily: 'Orbitron, sans-serif' }}>
                AWAITING CONFIRMATION, SIR
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[10px] mb-3">
              {[
                ['Action',    <span style={{ color: tradeProposal.trade_type === 'BUY' ? '#00FF9C' : '#FF4D6D', fontWeight: 700 }}>{tradeProposal.trade_type}</span>],
                ['Symbol',    <span style={{ color: '#C8F9FF', fontFamily: 'IBM Plex Mono, monospace' }}>{tradeProposal.symbol}</span>],
                ['Qty',       <span style={{ color: '#C8F9FF' }}>{tradeProposal.qty} shares</span>],
                ['Price',     <span style={{ color: '#C8F9FF' }}>₹{tradeProposal.price}</span>],
                ['Est. Cost', <span style={{ color: '#C8F9FF' }}>₹{tradeProposal.estimated_cost.toLocaleString()}</span>],
                ['Confidence',<span style={{ color: '#00D9FF' }}>{tradeProposal.confidence}%</span>],
                ['Stop Loss', <span style={{ color: '#FF4D6D' }}>₹{tradeProposal.stop_loss}</span>],
                ['Target',    <span style={{ color: '#00FF9C' }}>₹{tradeProposal.target1}</span>],
                ['R:R Ratio', <span style={{ color: '#C8F9FF' }}>{tradeProposal.risk_reward}</span>],
                ['Trend',     <span style={{ color: '#C8F9FF', textTransform: 'capitalize' }}>{tradeProposal.trend}</span>],
              ].map(([label, val], i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>{label}:</span>
                  {val}
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleTradeConfirm(true)}
                disabled={tradeConfirming}
                className="flex items-center gap-1.5 px-4 py-1.5 text-[9px] font-bold tracking-widest disabled:opacity-50"
                style={{ background: 'rgba(0,255,156,0.1)', border: '1px solid rgba(0,255,156,0.35)', color: '#00FF9C', borderRadius: 2, fontFamily: 'Orbitron, sans-serif' }}
              >
                <CheckCircle size={11} /> CONFIRM
              </button>
              <button
                onClick={() => handleTradeConfirm(false)}
                disabled={tradeConfirming}
                className="flex items-center gap-1.5 px-4 py-1.5 text-[9px] font-bold tracking-widest disabled:opacity-50"
                style={{ background: 'rgba(255,77,109,0.1)', border: '1px solid rgba(255,77,109,0.35)', color: '#FF4D6D', borderRadius: 2, fontFamily: 'Orbitron, sans-serif' }}
              >
                <XCircle size={11} /> CANCEL
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 py-8">
            <motion.div
              className="w-8 h-8 rounded-full"
              style={{ background: 'radial-gradient(circle, rgba(0,217,255,0.3), transparent)', border: '1px solid rgba(0,217,255,0.2)' }}
              animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <p className="text-[9px] tracking-[0.2em]" style={{ color: '#2A5A6A', fontFamily: 'Orbitron, sans-serif' }}>
              JARVIS ONLINE — AWAITING COMMAND
            </p>
          </div>
        )}
        <AnimatePresence>
          {messages.map(msg => <ChatBubble key={msg.id} message={msg} />)}
        </AnimatePresence>
        {status === 'thinking' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 px-3 py-2">
            <span className="text-[8px] tracking-widest" style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>PROCESSING</span>
            {[0, 1, 2].map(i => (
              <motion.div
                key={i}
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: '#7B5EA7', boxShadow: '0 0 6px #7B5EA7' }}
                animate={{ y: [0, -5, 0], opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
              />
            ))}
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 shrink-0" style={{ borderTop: '1px solid rgba(0,217,255,0.08)' }}>
        <div
          className="flex items-center gap-2 px-3 py-2"
          style={{
            background: 'rgba(0,217,255,0.04)',
            border: '1px solid rgba(0,217,255,0.12)',
            borderRadius: 2,
          }}
          onFocus={() => {}}
        >
          <span style={{ color: '#00D9FF', fontFamily: 'IBM Plex Mono, monospace', fontSize: 11 }}>›</span>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="Command JARVIS, Sir..."
            className="flex-1 bg-transparent outline-none"
            style={{
              color: '#C8F9FF',
              fontSize: 12,
              fontFamily: 'Space Grotesk, sans-serif',
            }}
          />
          <motion.button
            onClick={handleSend}
            disabled={!input.trim()}
            style={{
              background: input.trim() ? 'rgba(0,217,255,0.15)' : 'transparent',
              border: `1px solid ${input.trim() ? 'rgba(0,217,255,0.35)' : 'rgba(0,217,255,0.08)'}`,
              borderRadius: 2,
              padding: '4px 8px',
              color: input.trim() ? '#00D9FF' : '#2A5A6A',
            }}
            whileHover={input.trim() ? { scale: 1.05 } : {}}
            whileTap={input.trim() ? { scale: 0.95 } : {}}
          >
            <Send size={12} />
          </motion.button>
        </div>
      </div>
    </div>
  )
}

function ChatBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className="max-w-[88%] px-3 py-2 relative"
        style={{
          background: isUser
            ? 'rgba(0,217,255,0.08)'
            : 'rgba(8,19,40,0.9)',
          border: `1px solid ${isUser ? 'rgba(0,217,255,0.25)' : 'rgba(0,217,255,0.08)'}`,
          borderRadius: 2,
          boxShadow: isUser ? '0 0 12px rgba(0,217,255,0.08)' : 'none',
        }}
      >
        {/* Corner accent for JARVIS messages */}
        {!isUser && (
          <>
            <div className="absolute top-0 left-0 w-2 h-2" style={{ borderTop: '1px solid rgba(0,217,255,0.4)', borderLeft: '1px solid rgba(0,217,255,0.4)' }} />
            <div className="absolute bottom-0 right-0 w-2 h-2" style={{ borderBottom: '1px solid rgba(0,217,255,0.4)', borderRight: '1px solid rgba(0,217,255,0.4)' }} />
          </>
        )}
        {!isUser && (
          <div className="flex items-center gap-1.5 mb-1">
            <div className="w-1 h-1 rounded-full" style={{ background: '#00D9FF', boxShadow: '0 0 4px #00D9FF' }} />
            <span className="text-[7px] tracking-[0.2em]" style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>JARVIS</span>
          </div>
        )}
        <p className="whitespace-pre-wrap leading-relaxed text-xs" style={{ color: '#C8F9FF', fontFamily: 'Space Grotesk, sans-serif' }}>
          {message.content}
        </p>
        <p className="text-[8px] mt-1 opacity-40" style={{ color: '#7ECFDF', fontFamily: 'IBM Plex Mono, monospace' }}>
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </motion.div>
  )
}
