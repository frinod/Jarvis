'use client'
import React, { useEffect, useState, useRef } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Mic, ExternalLink } from 'lucide-react'
import { useJarvisStore } from '@/store/jarvisStore'
import { openModal } from '@/components/HolographicModal'

// ── Waveform ──────────────────────────────────────────────────
const BARS = Array.from({ length: 32 }, (_, i) => ({
  maxH: 6 + Math.random() * 22,
  dur:  0.15 + Math.random() * 0.35,
  delay: i * 0.022,
}))

function Waveform({ active }: { active: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 2, height: 32 }}>
      {BARS.map((b, i) => (
        <motion.div key={i}
          style={{ width: 2, borderRadius: 1,
            background: active
              ? `linear-gradient(180deg, #00D9FF, #00D9FF66)`
              : 'rgba(0,217,255,0.15)',
            boxShadow: active ? '0 0 3px rgba(0,217,255,0.6)' : 'none',
          }}
          animate={active ? { height: [2, b.maxH, 2] } : { height: 3 }}
          transition={{ duration: b.dur, repeat: Infinity, delay: b.delay, ease: 'easeInOut' }}
        />
      ))}
    </div>
  )
}

// ── Detect action keywords in response ───────────────────────
function parseActions(text: string): { label: string; modal: string }[] {
  const actions: { label: string; modal: string }[] = []
  if (/market|nifty|sensex|index/i.test(text))   actions.push({ label: 'Open Market',    modal: 'market' })
  if (/portfolio|holding/i.test(text))            actions.push({ label: 'Open Portfolio', modal: 'portfolio' })
  if (/stock|equity|share/i.test(text))           actions.push({ label: 'Open Stocks',    modal: 'stocks' })
  if (/news|headline/i.test(text))                actions.push({ label: 'Open News',      modal: 'news' })
  if (/watchlist/i.test(text))                    actions.push({ label: 'Open Watchlist', modal: 'watchlist' })
  if (/discovery|opportunity|buy signal/i.test(text)) actions.push({ label: 'AI Discovery', modal: 'discovery' })
  return actions.slice(0, 2)
}

// ── Global singleton ──────────────────────────────────────────
type OverlayListener = (msg: string | null) => void
let _overlayMsg: string | null = null
const _overlayListeners = new Set<OverlayListener>()

export function showJarvisOverlay(msg: string) {
  _overlayMsg = msg
  _overlayListeners.forEach(fn => fn(msg))
}

export function hideJarvisOverlay() {
  _overlayMsg = null
  _overlayListeners.forEach(fn => fn(null))
}

function useOverlayState() {
  const [msg, setMsg] = useState<string | null>(_overlayMsg)
  useEffect(() => {
    _overlayListeners.add(setMsg)
    return () => { _overlayListeners.delete(setMsg) }
  }, [])
  return msg
}

// ── Component ─────────────────────────────────────────────────
export function JarvisOverlay() {
  const message = useOverlayState()
  const status  = useJarvisStore(s => s.status)
  const [mounted, setMounted] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => { setMounted(true) }, [])

  // Auto-dismiss 4s after JARVIS goes idle
  useEffect(() => {
    if (status === 'idle' && message) {
      timerRef.current = setTimeout(hideJarvisOverlay, 4000)
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [status, message])

  const isSpeaking = status === 'speaking'
  const actions    = message ? parseActions(message) : []

  if (!mounted) return null

  return createPortal(
    <AnimatePresence>
      {message && (
        <motion.div
          key="jarvis-overlay"
          style={{
            position: 'fixed',
            top: 80, // below header
            left: '50%',
            zIndex: 8000,
            width: 520,
            maxWidth: 'calc(100vw - 32px)',
            transform: 'translateX(-50%)',
            background: 'linear-gradient(135deg, rgba(2,8,19,0.97) 0%, rgba(5,19,38,0.96) 100%)',
            border: '1px solid rgba(0,217,255,0.3)',
            boxShadow: '0 0 60px rgba(0,217,255,0.18), 0 24px 80px rgba(0,0,0,0.7)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
          }}
          initial={{ opacity: 0, y: -20, scale: 0.96 }}
          animate={{ opacity: 1, y: 0,   scale: 1    }}
          exit={{   opacity: 0, y: -16,  scale: 0.96 }}
          transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
        >
          {/* Corner brackets */}
          {[
            { top: 0,    left: 0,    borderWidth: '2px 0 0 2px' },
            { top: 0,    right: 0,   borderWidth: '2px 2px 0 0' },
            { bottom: 0, left: 0,    borderWidth: '0 0 2px 2px' },
            { bottom: 0, right: 0,   borderWidth: '0 2px 2px 0' },
          ].map((s, i) => (
            <div key={i} style={{
              position: 'absolute', ...s,
              width: 16, height: 16,
              borderStyle: 'solid', borderColor: 'rgba(0,217,255,0.7)',
              pointerEvents: 'none',
            }} />
          ))}

          {/* Header bar */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '8px 14px',
            borderBottom: '1px solid rgba(0,217,255,0.1)',
            background: 'rgba(0,217,255,0.03)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <motion.div style={{
                width: 7, height: 7, borderRadius: '50%',
                background: isSpeaking ? '#00FF99' : '#00D9FF',
                boxShadow: isSpeaking ? '0 0 10px #00FF99' : '0 0 8px #00D9FF',
              }}
                animate={{ opacity: [1, 0.2, 1] }}
                transition={{ duration: 0.9, repeat: Infinity }}
              />
              <span style={{
                fontSize: 9, fontWeight: 900, letterSpacing: '0.28em',
                color: '#00D9FF', fontFamily: 'Orbitron, sans-serif',
                textShadow: '0 0 10px rgba(0,217,255,0.7)',
              }}>
                J.A.R.V.I.S
              </span>
              <span style={{
                fontSize: 8, letterSpacing: '0.16em',
                color: isSpeaking ? '#00FF99' : '#2A5A6A',
                fontFamily: 'Rajdhani, sans-serif',
              }}>
                {isSpeaking ? '● TRANSMITTING' : '● RESPONSE'}
              </span>
            </div>
            <motion.button
              onClick={hideJarvisOverlay}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: '#2A5A6A', padding: 4, display: 'flex',
              }}
              whileHover={{ color: '#FF5A7A' }}
            >
              <X size={12} />
            </motion.button>
          </div>

          {/* Waveform */}
          <div style={{ padding: '10px 14px 6px', borderBottom: '1px solid rgba(0,217,255,0.06)' }}>
            <Waveform active={isSpeaking} />
          </div>

          {/* Message */}
          <div style={{ padding: '12px 16px' }}>
            <p style={{
              fontSize: 13, lineHeight: 1.65,
              color: '#D8FFFF',
              fontFamily: 'Space Grotesk, sans-serif',
              margin: 0,
              maxHeight: 160,
              overflowY: 'auto',
              scrollbarWidth: 'none',
            }}>
              {message}
            </p>
          </div>

          {/* Action buttons */}
          {actions.length > 0 && (
            <div style={{
              display: 'flex', gap: 8, padding: '0 16px 14px',
              borderTop: '1px solid rgba(0,217,255,0.06)',
              paddingTop: 10,
            }}>
              {actions.map((a, i) => (
                <motion.button key={i}
                  onClick={() => { openModal(a.modal); hideJarvisOverlay() }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '5px 12px',
                    background: 'rgba(0,217,255,0.07)',
                    border: '1px solid rgba(0,217,255,0.25)',
                    borderRadius: 2, cursor: 'pointer',
                    fontSize: 8, fontWeight: 700, letterSpacing: '0.16em',
                    color: '#00D9FF', fontFamily: 'Orbitron, sans-serif',
                  }}
                  whileHover={{ background: 'rgba(0,217,255,0.14)', borderColor: 'rgba(0,217,255,0.5)' }}
                  whileTap={{ scale: 0.95 }}
                >
                  <ExternalLink size={9} />
                  {a.label.toUpperCase()}
                </motion.button>
              ))}
            </div>
          )}

          {/* Bottom scan line */}
          <motion.div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, height: 1,
            background: 'linear-gradient(90deg, transparent, rgba(0,217,255,0.5), transparent)',
          }}
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  )
}
