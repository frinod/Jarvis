'use client'
import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { TrendingUp, TrendingDown, Bell, X } from 'lucide-react'
import { openModal } from '@/components/HolographicModal'

// ── Toast type ────────────────────────────────────────────────
export interface ToastData {
  id: string
  type: 'buy' | 'sell' | 'alert' | 'info'
  title: string
  symbol?: string
  entry?: number
  target?: number
  confidence?: number
  body?: string
  modal?: string
}

// ── Global singleton ──────────────────────────────────────────
type ToastListener = (toasts: ToastData[]) => void
let _toasts: ToastData[] = []
const _toastListeners = new Set<ToastListener>()

export function pushToast(toast: Omit<ToastData, 'id'>) {
  const t: ToastData = { ...toast, id: Math.random().toString(36).slice(2) }
  _toasts = [t, ..._toasts].slice(0, 5)
  _toastListeners.forEach(fn => fn([..._toasts]))
}

function dismissToast(id: string) {
  _toasts = _toasts.filter(t => t.id !== id)
  _toastListeners.forEach(fn => fn([..._toasts]))
}

function useToasts() {
  const [toasts, setToasts] = useState<ToastData[]>([..._toasts])
  useEffect(() => {
    _toastListeners.add(setToasts)
    return () => { _toastListeners.delete(setToasts) }
  }, [])
  return toasts
}

// ── Single toast card ─────────────────────────────────────────
function ToastCard({ toast }: { toast: ToastData }) {
  useEffect(() => {
    const t = setTimeout(() => dismissToast(toast.id), 6000)
    return () => clearTimeout(t)
  }, [toast.id])

  const isBuy  = toast.type === 'buy'
  const isSell = toast.type === 'sell'
  const accent = isBuy ? '#00FF99' : isSell ? '#FF5A7A' : toast.type === 'alert' ? '#FFC857' : '#00D9FF'
  const bg     = isBuy ? 'rgba(0,255,153,0.05)' : isSell ? 'rgba(255,90,122,0.05)' : toast.type === 'alert' ? 'rgba(255,200,87,0.05)' : 'rgba(0,217,255,0.05)'
  const Icon   = isBuy ? TrendingUp : isSell ? TrendingDown : Bell

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 60, scale: 0.92 }}
      animate={{ opacity: 1, x: 0,  scale: 1    }}
      exit={{   opacity: 0, x: 60,  scale: 0.92 }}
      transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
      style={{
        position: 'relative', overflow: 'hidden',
        background: `linear-gradient(135deg, rgba(2,8,19,0.98) 0%, rgba(5,19,38,0.97) 100%)`,
        border: `1px solid ${accent}44`,
        boxShadow: `0 0 24px ${accent}22, 0 8px 32px rgba(0,0,0,0.6)`,
        backdropFilter: 'blur(16px)',
        width: 280,
        cursor: toast.modal ? 'pointer' : 'default',
      }}
      onClick={() => { if (toast.modal) { openModal(toast.modal); dismissToast(toast.id) } }}
    >
      {/* Left accent bar */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
        background: `linear-gradient(180deg, ${accent}, ${accent}44)`,
        boxShadow: `0 0 8px ${accent}`,
      }} />

      {/* Progress bar (auto-dismiss timer) */}
      <motion.div style={{
        position: 'absolute', bottom: 0, left: 0, height: 2,
        background: `linear-gradient(90deg, ${accent}, ${accent}44)`,
        boxShadow: `0 0 6px ${accent}`,
      }}
        initial={{ width: '100%' }}
        animate={{ width: '0%' }}
        transition={{ duration: 6, ease: 'linear' }}
      />

      <div style={{ padding: '10px 12px 12px 16px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 22, height: 22, borderRadius: '50%',
              background: bg, border: `1px solid ${accent}44`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon size={11} style={{ color: accent }} />
            </div>
            <span style={{
              fontSize: 9, fontWeight: 900, letterSpacing: '0.22em',
              color: accent, fontFamily: 'Orbitron, sans-serif',
              textShadow: `0 0 8px ${accent}88`,
            }}>
              {toast.title}
            </span>
          </div>
          <button
            onClick={e => { e.stopPropagation(); dismissToast(toast.id) }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#2A5A6A', padding: 2 }}
          >
            <X size={10} />
          </button>
        </div>

        {/* Symbol + metrics */}
        {toast.symbol && (
          <div style={{ marginBottom: 6 }}>
            <span style={{
              fontSize: 16, fontWeight: 900, letterSpacing: '0.08em',
              color: '#D8FFFF', fontFamily: 'Orbitron, sans-serif',
            }}>
              {toast.symbol}
            </span>
          </div>
        )}

        {(toast.entry || toast.target || toast.confidence) && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 4 }}>
            {toast.entry && (
              <div>
                <div style={{ fontSize: 7, color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.12em' }}>ENTRY</div>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#D8FFFF', fontFamily: 'IBM Plex Mono, monospace' }}>₹{toast.entry}</div>
              </div>
            )}
            {toast.target && (
              <div>
                <div style={{ fontSize: 7, color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.12em' }}>TARGET</div>
                <div style={{ fontSize: 11, fontWeight: 700, color: accent, fontFamily: 'IBM Plex Mono, monospace' }}>₹{toast.target}</div>
              </div>
            )}
            {toast.confidence && (
              <div>
                <div style={{ fontSize: 7, color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.12em' }}>CONF</div>
                <div style={{ fontSize: 11, fontWeight: 700, color: accent, fontFamily: 'IBM Plex Mono, monospace' }}>{toast.confidence}%</div>
              </div>
            )}
          </div>
        )}

        {toast.body && !toast.symbol && (
          <p style={{ fontSize: 10, color: '#8AAFBF', fontFamily: 'Space Grotesk, sans-serif', margin: 0, lineHeight: 1.5 }}>
            {toast.body}
          </p>
        )}

        {toast.modal && (
          <div style={{ marginTop: 6, fontSize: 7, color: accent, fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.14em' }}>
            TAP TO OPEN →
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ── Container ─────────────────────────────────────────────────
export function NotificationToasts() {
  const toasts  = useToasts()
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])
  if (!mounted) return null

  return createPortal(
    <div style={{
      position: 'fixed', bottom: 80, right: 16,
      zIndex: 9000,
      display: 'flex', flexDirection: 'column', gap: 8,
      pointerEvents: 'none',
    }}>
      <AnimatePresence mode="popLayout">
        {toasts.map(t => (
          <div key={t.id} style={{ pointerEvents: 'all' }}>
            <ToastCard toast={t} />
          </div>
        ))}
      </AnimatePresence>
    </div>,
    document.body
  )
}
