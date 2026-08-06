'use client'
import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { MarketDashboardPage } from '@/components/MarketDashboardPage'
import { AIDiscoveryPage } from '@/components/AIDiscoveryPage'
import { PortfolioPage } from '@/components/PortfolioPage'
import { StocksPage } from '@/components/StocksPage'
import { NewsPage } from '@/components/NewsPage'
import { CalendarPage } from '@/components/CalendarPage'
import { SettingsPage } from '@/components/SettingsPage'
import { SystemMonitor } from '@/components/SystemMonitor'
import { WatchlistPage } from '@/components/WatchlistPage'
import { PaperTradingPage } from '@/components/PaperTradingPage'
import { BacktestPage } from '@/components/BacktestPage'
import { BudgetAdvisorPage } from '@/components/BudgetAdvisorPage'
import { TopPicksPage } from '@/components/TopPicksPage'
import { IntradayAssistantPage } from '@/components/IntradayAssistantPage'
import { AgentsPanel } from '@/components/AgentsPanel'
import { LLMStatus } from '@/components/LLMStatus'
import { TaskPanel } from '@/components/TaskPanel'

// ── Modal map ─────────────────────────────────────────────────
const MODAL_MAP: Record<string, { title: string; component: React.ReactNode }> = {
  market:       { title: 'MARKET OVERVIEW',   component: <MarketDashboardPage /> },
  stocks:       { title: 'MARKETS / STOCKS',  component: <StocksPage /> },
  discovery:    { title: 'AI DISCOVERY',      component: <AIDiscoveryPage /> },
  portfolio:    { title: 'PORTFOLIO',         component: <PortfolioPage /> },
  watchlist:    { title: 'WATCHLIST',         component: <WatchlistPage /> },
  news:         { title: 'INTEL FEED / NEWS', component: <NewsPage /> },
  calendar:     { title: 'CALENDAR',          component: <CalendarPage /> },
  settings:     { title: 'SETTINGS',          component: <SettingsPage /> },
  monitor:      { title: 'SYSTEM MONITOR',    component: <SystemMonitor /> },
  papertrading: { title: 'PAPER TRADING',     component: <PaperTradingPage /> },
  backtest:     { title: 'BACKTEST LAB',      component: <BacktestPage /> },
  budget:       { title: 'BUDGET ADVISOR',    component: <BudgetAdvisorPage /> },
  toppicks:     { title: 'TOP PICKS',         component: <TopPicksPage /> },
  intraday:     { title: 'INTRADAY ASSISTANT',component: <IntradayAssistantPage /> },
  agents:       { title: 'AI AGENTS',         component: <AgentsPanel /> },
  llm:          { title: 'LLM ENGINE',        component: <LLMStatus /> },
  tasks:        { title: 'TASK PANEL',        component: <TaskPanel /> },
}

// ── Global singleton ──────────────────────────────────────────
type ModalListener = (id: string | null) => void
let _modalId: string | null = null
const _listeners = new Set<ModalListener>()

export function openModal(id: string) {
  _modalId = id
  _listeners.forEach(fn => fn(id))
}

export function closeModal() {
  _modalId = null
  _listeners.forEach(fn => fn(null))
}

function useModalState() {
  const [id, setId] = useState<string | null>(_modalId)
  useEffect(() => {
    _listeners.add(setId)
    return () => { _listeners.delete(setId) }
  }, [])
  return id
}

// ── Component ─────────────────────────────────────────────────
export function HolographicModal() {
  const modalId = useModalState()
  const entry   = modalId ? MODAL_MAP[modalId] : null
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeModal() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (!mounted) return null

  return createPortal(
    <AnimatePresence>
      {entry && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            style={{
              position: 'fixed', inset: 0, zIndex: 9998,
              background: 'rgba(2,8,19,0.88)',
              backdropFilter: 'blur(6px)',
              cursor: 'pointer',
            }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={closeModal}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            style={{
              position: 'fixed',
              top: '4%', left: '4%', right: '4%', bottom: '4%',
              zIndex: 9999,
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
              background: 'linear-gradient(135deg, rgba(3,10,24,0.99) 0%, rgba(5,19,38,0.98) 100%)',
              border: '1px solid rgba(0,217,255,0.3)',
              boxShadow: '0 0 80px rgba(0,217,255,0.2), inset 0 0 60px rgba(0,217,255,0.03)',
            }}
            initial={{ opacity: 0, scale: 0.93, y: 24 }}
            animate={{ opacity: 1, scale: 1,    y: 0  }}
            exit={{   opacity: 0, scale: 0.93, y: 24  }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
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
                width: 24, height: 24,
                borderStyle: 'solid', borderColor: 'rgba(0,217,255,0.7)',
                pointerEvents: 'none',
              }} />
            ))}

            {/* Header */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 24px', flexShrink: 0,
              borderBottom: '1px solid rgba(0,217,255,0.12)',
              background: 'rgba(0,217,255,0.03)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <motion.div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: '#00D9FF', boxShadow: '0 0 10px #00D9FF',
                }}
                  animate={{ opacity: [1, 0.2, 1] }}
                  transition={{ duration: 1.2, repeat: Infinity }}
                />
                <span style={{
                  fontSize: 11, fontWeight: 900, letterSpacing: '0.3em',
                  color: '#00D9FF', fontFamily: 'Orbitron, sans-serif',
                  textShadow: '0 0 14px rgba(0,217,255,0.8)',
                }}>
                  {entry.title}
                </span>
              </div>

              <motion.button
                onClick={closeModal}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 12px',
                  background: 'rgba(255,90,122,0.06)',
                  border: '1px solid rgba(255,90,122,0.3)',
                  borderRadius: 2, cursor: 'pointer',
                }}
                whileHover={{ background: 'rgba(255,90,122,0.14)', borderColor: 'rgba(255,90,122,0.6)' }}
                whileTap={{ scale: 0.95 }}
              >
                <X size={12} style={{ color: '#FF5A7A' }} />
                <span style={{
                  fontSize: 8, fontWeight: 700, letterSpacing: '0.18em',
                  color: '#FF5A7A', fontFamily: 'Orbitron, sans-serif',
                }}>CLOSE</span>
              </motion.button>
            </div>

            {/* Content */}
            <div style={{ flex: 1, overflowY: 'auto', scrollbarWidth: 'thin' }}>
              {entry.component}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}
