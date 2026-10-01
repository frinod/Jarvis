'use client'

import React, { useEffect, useRef } from 'react'
import { ParticleBackground } from '@/components/ParticleBackground'
import { QuickTradeModal } from '@/components/QuickTradeModal'
import { HolographicModal } from '@/components/HolographicModal'
import { JarvisOverlay } from '@/components/JarvisOverlay'
import { NotificationToasts } from '@/components/NotificationToasts'
import { HudPanelManager } from '@/components/HudPanelManager'
import { VoiceBar } from '@/components/VoiceBar'
import { JarvisBoot } from '@/components/JarvisBoot'
import { Ignition } from '@/components/Ignition'
import { BladeSweep } from '@/components/BladeSweep'
import { JarvisEffects } from '@/components/JarvisEffects'
import { JarvisSuggestions } from '@/components/JarvisSuggestions'
import { useJarvisStore } from '@/store/jarvisStore'

import { TopHud } from '@/components/TopHud'
import { LeftSidebar } from '@/components/LeftSidebar'
import { CenterWorkspace } from '@/components/CenterWorkspace'
import { RightIntelPanel } from '@/components/RightIntelPanel'

import { StocksPage } from '@/components/StocksPage'
import { MarketDashboardPage } from '@/components/MarketDashboardPage'
import { TopPicksPage } from '@/components/TopPicksPage'
import { AIDiscoveryPage } from '@/components/AIDiscoveryPage'
import { IntradayAssistantPage } from '@/components/IntradayAssistantPage'
import { WatchlistPage } from '@/components/WatchlistPage'
import { PortfolioPage } from '@/components/PortfolioPage'
import { PaperTradingPage } from '@/components/PaperTradingPage'
import { BacktestPage } from '@/components/BacktestPage'
import { BudgetAdvisorPage } from '@/components/BudgetAdvisorPage'
import { NewsPage } from '@/components/NewsPage'
import { CalendarPage } from '@/components/CalendarPage'
import { AgentsPanel } from '@/components/AgentsPanel'
import { SystemMonitor } from '@/components/SystemMonitor'
import { LLMStatus } from '@/components/LLMStatus'
import { TaskPanel } from '@/components/TaskPanel'
import { SettingsPage } from '@/components/SettingsPage'

function ActiveModule({ id }: { id: string }) {
  switch (id) {
    case 'stocks':       return <StocksPage />
    case 'market':       return <MarketDashboardPage />
    case 'toppicks':     return <TopPicksPage />
    case 'discovery':    return <AIDiscoveryPage />
    case 'intraday':     return <IntradayAssistantPage />
    case 'watchlist':    return <WatchlistPage />
    case 'portfolio':    return <PortfolioPage />
    case 'papertrading': return <PaperTradingPage />
    case 'backtest':     return <BacktestPage />
    case 'budget':       return <BudgetAdvisorPage />
    case 'news':         return <NewsPage />
    case 'calendar':     return <CalendarPage />
    case 'agents':       return <div className="p-6"><AgentsPanel /></div>
    case 'monitor':      return <div className="p-6"><SystemMonitor /></div>
    case 'llm':          return <div className="p-6"><LLMStatus /></div>
    case 'tasks':        return <div className="p-6"><TaskPanel /></div>
    case 'settings':     return <SettingsPage />
    default:             return null
  }
}

export default function Home() {
  const status       = useJarvisStore(s => s.status)
  const activeNav    = useJarvisStore(s => s.activeNav)
  const setPhase     = useJarvisStore(s => s.setPhase)
  const phase        = useJarvisStore(s => s.phase)
  const glowRef      = useRef<HTMLDivElement>(null)
  const booting      = useRef(false)

  useEffect(() => {
    const stop = useJarvisStore.getState().startPolling()
    return stop
  }, []) // eslint-disable-line

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

  // Space bar also triggers power-on from offline
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat && useJarvisStore.getState().phase === 'offline') {
        e.preventDefault()
        void powerOn()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, []) // eslint-disable-line

  const powerOn = async () => {
    if (booting.current) return
    booting.current = true
    try {
      // Unlock audio INSIDE the click handler — browsers require a user gesture
      const sfx = await import('@/lib/sfx')
      await sfx.unlockAudio()
      setPhase('boot')
    } catch (err) {
      booting.current = false
      console.error('[jarvis] power-up failed:', err)
    }
  }

  const stateBg: Record<string, string> = {
    idle:      'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(0,157,255,0.03) 0%, transparent 70%)',
    listening: 'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(0,255,153,0.04) 0%, transparent 70%)',
    thinking:  'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(0,157,255,0.06) 0%, transparent 70%)',
    speaking:  'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(51,242,255,0.05) 0%, transparent 70%)',
    executing: 'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(255,200,87,0.04) 0%, transparent 70%)',
  }

  const isDashboard = activeNav === 'dashboard'

  return (
    <main className="h-screen flex flex-col overflow-hidden hud-grid" style={{ background: '#020812' }}>
      <ParticleBackground />
      <div className="noise-overlay" />
      <div className="fog-layer" />
      <div className="scan-line" />

      <div className="fixed inset-0 pointer-events-none transition-all duration-1000"
        style={{ background: stateBg[status] || stateBg.idle, zIndex: 1 }} />

      <div ref={glowRef} className="cursor-glow" />

      {/* Ignition — shown only when phase === 'offline'. Click unlocks audio + starts boot. */}
      <Ignition onStart={() => void powerOn()} />

      {/* Boot sequence — fullscreen overlay, auto-dismisses after 8.8s */}
      <JarvisBoot onComplete={() => {
        setPhase('dormant')
        useJarvisStore.getState().setVoiceActive(true)
      }} />

      {/* Blade sweep — light slivers during tooling */}
      <BladeSweep />

      {/* One-shot frame effects */}
      <JarvisEffects />

      {/* Modal overlays */}
      <QuickTradeModal />
      <HolographicModal />
      <JarvisOverlay />
      <NotificationToasts />
      <HudPanelManager />

      {/* Top HUD */}
      <TopHud />

      {/* Body */}
      <div className="flex-1 flex overflow-hidden" style={{ position: 'relative', zIndex: 10 }}>
        <LeftSidebar />

        {isDashboard ? (
          <CenterWorkspace />
        ) : (
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden"
            style={{ borderRight: '1px solid rgba(0,217,255,0.08)' }}>
            <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
              <ActiveModule id={activeNav} />
            </div>
          </div>
        )}

        <RightIntelPanel />
      </div>

      {/* Rotating suggestions — visible only while dormant + no messages */}
      <JarvisSuggestions />

      {/* VoiceBar — always visible at bottom */}
      <VoiceBar />
    </main>
  )
}
