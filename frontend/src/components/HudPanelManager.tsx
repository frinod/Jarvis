'use client'
import React, { useEffect, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Minus, Maximize2, GripHorizontal } from 'lucide-react'

// ── Panel registry ────────────────────────────────────────────
// Lazy-loaded so we don't import every page component upfront
const PANEL_REGISTRY: Record<string, {
  title: string
  defaultW: number
  defaultH: number
  defaultPos: { x: number; y: number }
  load: () => Promise<{ default: React.ComponentType<any> } | { [k: string]: React.ComponentType<any> }>
  exportName?: string
}> = {
  monitor:      { title: 'SYSTEM STATUS',       defaultW: 420, defaultH: 480, defaultPos: { x: 40,  y: 80  }, load: () => import('@/components/SystemMonitor'),          exportName: 'SystemMonitor' },
  market:       { title: 'MARKET OVERVIEW',     defaultW: 700, defaultH: 560, defaultPos: { x: 120, y: 80  }, load: () => import('@/components/MarketDashboardPage'),    exportName: 'MarketDashboardPage' },
  portfolio:    { title: 'PORTFOLIO',           defaultW: 640, defaultH: 520, defaultPos: { x: 80,  y: 80  }, load: () => import('@/components/PortfolioPage'),           exportName: 'PortfolioPage' },
  stocks:       { title: 'STOCKS',              defaultW: 720, defaultH: 560, defaultPos: { x: 100, y: 80  }, load: () => import('@/components/StocksPage'),              exportName: 'StocksPage' },
  discovery:    { title: 'AI DISCOVERY',        defaultW: 680, defaultH: 540, defaultPos: { x: 90,  y: 80  }, load: () => import('@/components/AIDiscoveryPage'),         exportName: 'AIDiscoveryPage' },
  watchlist:    { title: 'WATCHLIST',           defaultW: 520, defaultH: 480, defaultPos: { x: 60,  y: 80  }, load: () => import('@/components/WatchlistPage'),           exportName: 'WatchlistPage' },
  news:         { title: 'INTEL FEED',          defaultW: 480, defaultH: 520, defaultPos: { x: 60,  y: 80  }, load: () => import('@/components/NewsPage'),                exportName: 'NewsPage' },
  calendar:     { title: 'CALENDAR',            defaultW: 560, defaultH: 500, defaultPos: { x: 80,  y: 80  }, load: () => import('@/components/CalendarPage'),            exportName: 'CalendarPage' },
  settings:     { title: 'SETTINGS',            defaultW: 560, defaultH: 500, defaultPos: { x: 80,  y: 80  }, load: () => import('@/components/SettingsPage'),            exportName: 'SettingsPage' },
  agents:       { title: 'AI AGENTS',           defaultW: 480, defaultH: 460, defaultPos: { x: 60,  y: 80  }, load: () => import('@/components/AgentsPanel'),             exportName: 'AgentsPanel' },
  llm:          { title: 'LLM ENGINE',          defaultW: 440, defaultH: 420, defaultPos: { x: 60,  y: 80  }, load: () => import('@/components/LLMStatus'),               exportName: 'LLMStatus' },
  tasks:        { title: 'TASK PANEL',          defaultW: 440, defaultH: 420, defaultPos: { x: 60,  y: 80  }, load: () => import('@/components/TaskPanel'),               exportName: 'TaskPanel' },
  papertrading: { title: 'PAPER TRADING',       defaultW: 680, defaultH: 540, defaultPos: { x: 90,  y: 80  }, load: () => import('@/components/PaperTradingPage'),        exportName: 'PaperTradingPage' },
  backtest:     { title: 'BACKTEST LAB',        defaultW: 680, defaultH: 540, defaultPos: { x: 90,  y: 80  }, load: () => import('@/components/BacktestPage'),            exportName: 'BacktestPage' },
  budget:       { title: 'BUDGET ADVISOR',      defaultW: 600, defaultH: 500, defaultPos: { x: 80,  y: 80  }, load: () => import('@/components/BudgetAdvisorPage'),       exportName: 'BudgetAdvisorPage' },
  toppicks:     { title: 'TOP PICKS',           defaultW: 600, defaultH: 500, defaultPos: { x: 80,  y: 80  }, load: () => import('@/components/TopPicksPage'),            exportName: 'TopPicksPage' },
  intraday:     { title: 'INTRADAY ASSISTANT',  defaultW: 640, defaultH: 520, defaultPos: { x: 80,  y: 80  }, load: () => import('@/components/IntradayAssistantPage'),   exportName: 'IntradayAssistantPage' },
}

// ── Panel instance ────────────────────────────────────────────
interface PanelInstance {
  id: string          // unique instance id
  panelKey: string    // key into PANEL_REGISTRY
  x: number
  y: number
  w: number
  h: number
  minimized: boolean
  zIndex: number
}

// ── Global singleton ──────────────────────────────────────────
type HudListener = (panels: PanelInstance[]) => void
let _panels: PanelInstance[] = []
let _zTop = 7000
const _hudListeners = new Set<HudListener>()

function notify() { _hudListeners.forEach(fn => fn([..._panels])) }

export function openHudPanel(panelKey: string) {
  if (!PANEL_REGISTRY[panelKey]) return
  // If already open, bring to front
  const existing = _panels.find(p => p.panelKey === panelKey)
  if (existing) {
    _zTop++
    _panels = _panels.map(p => p.id === existing.id ? { ...p, zIndex: _zTop, minimized: false } : p)
    notify(); return
  }
  const reg = PANEL_REGISTRY[panelKey]
  // Cascade offset so multiple panels don't stack exactly
  const offset = _panels.length * 28
  _zTop++
  const inst: PanelInstance = {
    id: Math.random().toString(36).slice(2),
    panelKey,
    x: Math.min(reg.defaultPos.x + offset, window.innerWidth  - reg.defaultW - 20),
    y: Math.min(reg.defaultPos.y + offset, window.innerHeight - reg.defaultH - 20),
    w: reg.defaultW,
    h: reg.defaultH,
    minimized: false,
    zIndex: _zTop,
  }
  _panels = [..._panels, inst]
  notify()
}

export function closeHudPanel(id: string) {
  _panels = _panels.filter(p => p.id !== id)
  notify()
}

export function closeAllHudPanels() {
  _panels = []
  notify()
}

function useHudPanels() {
  const [panels, setPanels] = useState<PanelInstance[]>([..._panels])
  useEffect(() => {
    _hudListeners.add(setPanels)
    return () => { _hudListeners.delete(setPanels) }
  }, [])
  return panels
}

// ── Lazy content loader ───────────────────────────────────────
function PanelContent({ panelKey }: { panelKey: string }) {
  const [Comp, setComp] = useState<React.ComponentType<any> | null>(null)
  const [err,  setErr]  = useState(false)

  useEffect(() => {
    const reg = PANEL_REGISTRY[panelKey]
    if (!reg) return
    reg.load().then(mod => {
      const C = reg.exportName
        ? (mod as any)[reg.exportName]
        : (mod as any).default
      if (C) setComp(() => C)
      else setErr(true)
    }).catch(() => setErr(true))
  }, [panelKey])

  if (err)  return <div style={{ padding: 24, color: '#FF5A7A', fontFamily: 'Orbitron, sans-serif', fontSize: 11 }}>LOAD ERROR</div>
  if (!Comp) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8 }}>
      {[0,1,2].map(i => (
        <motion.div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: '#00D9FF' }}
          animate={{ y: [0, -8, 0], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }} />
      ))}
    </div>
  )
  return <Comp />
}

// ── Single draggable panel ────────────────────────────────────
function HudPanel({ inst, onFocus }: { inst: PanelInstance; onFocus: (id: string) => void }) {
  const reg = PANEL_REGISTRY[inst.panelKey]
  const posRef = useRef({ x: inst.x, y: inst.y })
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  const [pos, setPos] = useState({ x: inst.x, y: inst.y })
  const [minimized, setMinimized] = useState(inst.minimized)

  // Drag logic — native pointer events for zero-latency
  const onPointerDown = useCallback((e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('[data-no-drag]')) return
    e.currentTarget.setPointerCapture(e.pointerId)
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y }
    onFocus(inst.id)
  }, [pos, inst.id, onFocus])

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragRef.current) return
    const nx = dragRef.current.origX + (e.clientX - dragRef.current.startX)
    const ny = dragRef.current.origY + (e.clientY - dragRef.current.startY)
    // Clamp to viewport
    const clamped = {
      x: Math.max(0, Math.min(nx, window.innerWidth  - inst.w)),
      y: Math.max(0, Math.min(ny, window.innerHeight - (minimized ? 44 : inst.h))),
    }
    posRef.current = clamped
    setPos(clamped)
  }, [inst.w, inst.h, minimized])

  const onPointerUp = useCallback(() => { dragRef.current = null }, [])

  return (
    <motion.div
      ref={panelRef}
      style={{
        position: 'fixed',
        left: pos.x, top: pos.y,
        width: inst.w,
        height: minimized ? 44 : inst.h,
        zIndex: inst.zIndex,
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
        background: 'linear-gradient(135deg, rgba(2,8,19,0.97) 0%, rgba(5,19,38,0.96) 100%)',
        border: '1px solid rgba(0,217,255,0.28)',
        boxShadow: '0 0 40px rgba(0,217,255,0.12), 0 20px 60px rgba(0,0,0,0.7)',
        backdropFilter: 'blur(18px)',
        WebkitBackdropFilter: 'blur(18px)',
        userSelect: 'none',
      }}
      initial={{ opacity: 0, scale: 0.88, y: 24 }}
      animate={{ opacity: 1, scale: 1,    y: 0  }}
      exit={{   opacity: 0, scale: 0.88, y: 24  }}
      transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
      onClick={() => onFocus(inst.id)}
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
          width: 14, height: 14,
          borderStyle: 'solid', borderColor: 'rgba(0,217,255,0.6)',
          pointerEvents: 'none', zIndex: 2,
        }} />
      ))}

      {/* Title bar — drag handle */}
      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 10px', height: 44, flexShrink: 0,
          borderBottom: minimized ? 'none' : '1px solid rgba(0,217,255,0.1)',
          background: 'rgba(0,217,255,0.03)',
          cursor: 'grab',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <GripHorizontal size={10} style={{ color: 'rgba(0,217,255,0.3)' }} />
          <motion.div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#00D9FF', boxShadow: '0 0 8px #00D9FF',
          }}
            animate={{ opacity: [1, 0.2, 1] }}
            transition={{ duration: 1.4, repeat: Infinity }}
          />
          <span style={{
            fontSize: 9, fontWeight: 900, letterSpacing: '0.26em',
            color: '#00D9FF', fontFamily: 'Orbitron, sans-serif',
            textShadow: '0 0 10px rgba(0,217,255,0.6)',
          }}>
            {reg?.title ?? inst.panelKey.toUpperCase()}
          </span>
        </div>

        {/* Window controls */}
        <div data-no-drag style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <motion.button
            onClick={() => setMinimized(m => !m)}
            style={btnStyle('#FFC857')}
            whileHover={{ background: 'rgba(255,200,87,0.18)' }}
            whileTap={{ scale: 0.9 }}
          >
            <Minus size={9} style={{ color: '#FFC857' }} />
          </motion.button>
          <motion.button
            onClick={() => closeHudPanel(inst.id)}
            style={btnStyle('#FF5A7A')}
            whileHover={{ background: 'rgba(255,90,122,0.18)' }}
            whileTap={{ scale: 0.9 }}
          >
            <X size={9} style={{ color: '#FF5A7A' }} />
          </motion.button>
        </div>
      </div>

      {/* Content */}
      {!minimized && (
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', scrollbarWidth: 'thin' }}>
          <PanelContent panelKey={inst.panelKey} />
        </div>
      )}

      {/* Bottom glow line */}
      <motion.div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: 1,
        background: 'linear-gradient(90deg, transparent, rgba(0,217,255,0.4), transparent)',
        pointerEvents: 'none',
      }}
        animate={{ opacity: [0.3, 0.9, 0.3] }}
        transition={{ duration: 2.5, repeat: Infinity }}
      />
    </motion.div>
  )
}

function btnStyle(color: string): React.CSSProperties {
  return {
    width: 20, height: 20, borderRadius: 2,
    background: `${color}10`,
    border: `1px solid ${color}30`,
    cursor: 'pointer', display: 'flex',
    alignItems: 'center', justifyContent: 'center',
  }
}

// ── Manager component — mount once in page.tsx ────────────────
export function HudPanelManager() {
  const panels  = useHudPanels()
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  const bringToFront = useCallback((id: string) => {
    _zTop++
    _panels = _panels.map(p => p.id === id ? { ...p, zIndex: _zTop } : p)
    notify()
  }, [])

  if (!mounted) return null

  return createPortal(
    <AnimatePresence>
      {panels.map(inst => (
        <HudPanel key={inst.id} inst={inst} onFocus={bringToFront} />
      ))}
    </AnimatePresence>,
    document.body
  )
}
