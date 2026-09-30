'use client'

import React, { useEffect, useRef } from 'react'
import { Header } from '@/components/Header'
import { LeftPanel } from '@/components/LeftPanel'
import { CenterColumn } from '@/components/CenterColumn'
import { RightPanel } from '@/components/RightPanel'
import { BottomRow } from '@/components/BottomRow'
import { BottomNav } from '@/components/BottomNav'
import { ParticleBackground } from '@/components/ParticleBackground'
import { QuickTradeModal } from '@/components/QuickTradeModal'
import { Sidebar } from '@/components/Sidebar'
import { VoiceBar } from '@/components/VoiceBar'
import { HolographicModal } from '@/components/HolographicModal'
import { JarvisOverlay } from '@/components/JarvisOverlay'
import { NotificationToasts } from '@/components/NotificationToasts'
import { HudPanelManager } from '@/components/HudPanelManager'
import { useJarvisStore } from '@/store/jarvisStore'

// ── Sub-page imports ──────────────────────────────────────────
import { StocksPage } from '@/components/StocksPage'
import { SettingsPage } from '@/components/SettingsPage'
import { MarketDashboardPage } from '@/components/MarketDashboardPage'
import { AIDiscoveryPage } from '@/components/AIDiscoveryPage'
import { WatchlistPage } from '@/components/WatchlistPage'
import { PortfolioPage } from '@/components/PortfolioPage'
import { NewsPage } from '@/components/NewsPage'
import { CalendarPage } from '@/components/CalendarPage'
import { BudgetAdvisorPage } from '@/components/BudgetAdvisorPage'
import { TopPicksPage } from '@/components/TopPicksPage'
import { IntradayAssistantPage } from '@/components/IntradayAssistantPage'
import { PaperTradingPage } from '@/components/PaperTradingPage'
import { BacktestPage } from '@/components/BacktestPage'
import { AgentsPanel } from '@/components/AgentsPanel'
import { SystemMonitor } from '@/components/SystemMonitor'
import { LLMStatus } from '@/components/LLMStatus'
import { TaskPanel } from '@/components/TaskPanel'

// ── Sub-page router ───────────────────────────────────────────
function ActivePage({ nav }: { nav: string }) {
  switch (nav) {
    case 'stocks':       return <StocksPage />
    case 'market':       return <MarketDashboardPage />
    case 'toppicks':     return <TopPicksPage />
    case 'discovery':    return <AIDiscoveryPage />
    case 'intraday':     return <IntradayAssistantPage />
    case 'watchlist':    return <WatchlistPage />
    case 'portfolio':    return <PortfolioPage />
    case 'papertrading': return <PaperTradingPage />
    case 'backtest':     return <BacktestPage />
    case 'news':         return <NewsPage />
    case 'calendar':     return <CalendarPage />
    case 'budget':       return <BudgetAdvisorPage />
    case 'settings':     return <SettingsPage />
    case 'agents':       return <div className="p-5 max-w-lg"><AgentsPanel /></div>
    case 'monitor':      return <div className="p-5 max-w-lg"><SystemMonitor /></div>
    case 'llm':          return <div className="p-5 max-w-lg"><LLMStatus /></div>
    case 'tasks':        return <div className="p-5 max-w-lg"><TaskPanel /></div>
    default:             return null
  }
}

// ── ROOT ──────────────────────────────────────────────────────
export default function Home() {
  const startPolling = useJarvisStore(s => s.startPolling)
  const activeNav    = useJarvisStore(s => s.activeNav)
  const status       = useJarvisStore(s => s.status)
  const glowRef      = useRef<HTMLDivElement>(null)

  useEffect(() => { const stop = startPolling(); return stop }, [startPolling])

  // Cursor glow follow
  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (glowRef.current) {
        glowRef.current.style.left = e.clientX + 'px'
        glowRef.current.style.top  = e.clientY + 'px'
      }
    }
    window.addEventListener('mousemove', move)
    return () => window.removeEventListener('mousemove', move)
  }, [])

  const isDashboard = activeNav === 'dashboard'

  // State-based ambient background
  const stateBg: Record<string, string> = {
    idle:      'radial-gradient(ellipse 90% 50% at 50% 100%, rgba(0,157,255,0.04) 0%, transparent 70%)',
    listening: 'radial-gradient(ellipse 90% 50% at 50% 100%, rgba(0,255,153,0.05) 0%, transparent 70%)',
    thinking:  'radial-gradient(ellipse 90% 50% at 50% 100%, rgba(0,157,255,0.07) 0%, transparent 70%)',
    speaking:  'radial-gradient(ellipse 90% 50% at 50% 100%, rgba(51,242,255,0.07) 0%, transparent 70%)',
    executing: 'radial-gradient(ellipse 90% 50% at 50% 100%, rgba(255,200,87,0.05) 0%, transparent 70%)',
  }

  return (
    <main
      className="h-screen flex flex-col overflow-hidden hud-grid"
      style={{ background: '#020813' }}
    >
      <ParticleBackground />
      <div className="noise-overlay" />
      <div className="fog-layer" />
      <div className="scan-line" />

      {/* Ambient state glow */}
      <div
        className="fixed inset-0 pointer-events-none transition-all duration-1000"
        style={{ background: stateBg[status] || stateBg.idle, zIndex: 1 }}
      />

      <div ref={glowRef} className="cursor-glow" />
      <QuickTradeModal />
      <HolographicModal />
      <JarvisOverlay />
      <NotificationToasts />
      <HudPanelManager />

      {/* VoiceBar engine — hidden, always mounted so SpeechRecognition runs */}
      <div className="hidden">
        <VoiceBar />
      </div>

      {/* ── Header (full width) ── */}
      <Header />

      {/* ── Body ── */}
      <div className="flex-1 flex overflow-hidden" style={{ position: 'relative', zIndex: 10 }}>

        {isDashboard ? (
          // ── Dashboard layout: Left | Center | Right ──
          <div className="flex-1 flex flex-col overflow-hidden">

            {/* Main 3-column row */}
            <div className="flex-1 flex overflow-hidden" style={{ padding: '8px 8px 0 8px', gap: 8 }}>

              {/* Left panel */}
              <div className="hidden lg:flex relative">
                <LeftPanel />
              </div>

              {/* Center column */}
              <CenterColumn />

              {/* Right panel */}
              <div className="hidden lg:flex">
                <RightPanel />
              </div>

            </div>

            {/* Bottom row: Voice + Console */}
            <BottomRow />

          </div>
        ) : (
          // ── Sub-page layout: Sidebar + content ──
          <div className="flex-1 flex overflow-hidden">
            <div className="hidden md:flex">
              <Sidebar />
            </div>
            <div className="flex-1 overflow-y-auto">
              <ActivePage nav={activeNav} />
            </div>
          </div>
        )}

      </div>

      {/* ── Bottom Nav (always visible) ── */}
      <BottomNav />

    </main>
  )
}
