'use client'
import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'

interface Notif {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  body: string
  ts: number
}

const TYPE_COLOR = {
  info:    '#00D9FF',
  success: '#00FF9C',
  warning: '#FFB347',
  error:   '#FF4D6D',
}
const TYPE_ICON = {
  info:    '◈',
  success: '◆',
  warning: '⚠',
  error:   '✕',
}

let _push: ((n: Omit<Notif, 'id' | 'ts'>) => void) | null = null
export function pushNotif(n: Omit<Notif, 'id' | 'ts'>) {
  _push?.(n)
}

export function Notifications() {
  const [notifs, setNotifs] = useState<Notif[]>([])
  const { status, connected, messages } = useJarvisStore()
  const prevStatus = useState(status)
  const prevConnected = useState(connected)

  const push = useCallback((n: Omit<Notif, 'id' | 'ts'>) => {
    const notif: Notif = { ...n, id: crypto.randomUUID(), ts: Date.now() }
    setNotifs(s => [notif, ...s].slice(0, 5))
    setTimeout(() => setNotifs(s => s.filter(x => x.id !== notif.id)), 5000)
  }, [])

  useEffect(() => { _push = push; return () => { _push = null } }, [push])

  // Boot notifications
  useEffect(() => {
    setTimeout(() => push({ type: 'success', title: 'SYSTEM ONLINE', body: 'J.A.R.V.I.S OS initialized' }), 800)
    setTimeout(() => push({ type: 'info',    title: 'NEURAL ENGINE', body: 'AI core loaded — Groq LLM active' }), 1800)
    setTimeout(() => push({ type: 'info',    title: 'MARKET FEED',   body: 'Yahoo Finance data stream connected' }), 3000)
  }, [])

  // React to connection change
  useEffect(() => {
    if (connected) push({ type: 'success', title: 'BACKEND CONNECTED', body: 'FastAPI server online at :8000' })
    else push({ type: 'error', title: 'CONNECTION LOST', body: 'Backend unreachable — retrying...' })
  }, [connected])

  // React to JARVIS status changes
  useEffect(() => {
    if (status === 'listening') push({ type: 'info',    title: 'VOICE DETECTED',  body: 'Microphone active — listening...' })
    if (status === 'thinking')  push({ type: 'warning', title: 'PROCESSING',       body: 'Neural reasoning in progress' })
    if (status === 'executing') push({ type: 'warning', title: 'EXECUTING TASK',   body: 'Agent pipeline activated' })
  }, [status])

  // React to new assistant messages
  useEffect(() => {
    const last = messages[messages.length - 1]
    if (last?.role === 'assistant' && last.content.length > 10) {
      push({ type: 'success', title: 'TASK COMPLETE', body: last.content.slice(0, 48) + (last.content.length > 48 ? '…' : '') })
    }
  }, [messages.length])

  return (
    <div className="fixed top-14 right-3 z-[9990] flex flex-col gap-2 pointer-events-none" style={{ width: 240 }}>
      <AnimatePresence>
        {notifs.map((n) => {
          const color = TYPE_COLOR[n.type]
          return (
            <motion.div
              key={n.id}
              initial={{ x: 260, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 260, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 28 }}
              className="relative overflow-hidden pointer-events-auto"
              style={{
                background: 'linear-gradient(135deg, rgba(8,19,40,0.97) 0%, rgba(5,8,22,0.95) 100%)',
                border: `1px solid ${color}35`,
                borderRadius: 2,
                boxShadow: `0 0 20px ${color}15, 0 4px 24px rgba(0,0,0,0.6)`,
              }}
            >
              {/* Left accent bar */}
              <div className="absolute left-0 top-0 bottom-0 w-0.5" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />

              {/* Top shimmer */}
              <motion.div
                className="absolute top-0 left-0 right-0 h-px"
                style={{ background: `linear-gradient(90deg, transparent, ${color}80, transparent)` }}
                animate={{ x: ['-100%', '100%'] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
              />

              <div className="pl-3 pr-3 py-2">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-[10px]" style={{ color }}>{TYPE_ICON[n.type]}</span>
                  <span className="text-[8px] font-bold tracking-[0.2em]" style={{ color, fontFamily: 'Orbitron, sans-serif' }}>{n.title}</span>
                  <div className="ml-auto">
                    <motion.div
                      className="w-1 h-1 rounded-full"
                      style={{ background: color }}
                      animate={{ opacity: [1, 0.2, 1] }}
                      transition={{ duration: 1, repeat: Infinity }}
                    />
                  </div>
                </div>
                <p className="text-[8px] leading-tight" style={{ color: '#7ECFDF', fontFamily: 'Space Grotesk, sans-serif' }}>{n.body}</p>
              </div>

              {/* Auto-dismiss progress bar */}
              <motion.div
                className="absolute bottom-0 left-0 h-px"
                style={{ background: color, opacity: 0.4 }}
                initial={{ width: '100%' }}
                animate={{ width: '0%' }}
                transition={{ duration: 5, ease: 'linear' }}
              />
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
