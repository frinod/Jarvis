'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import {
  TrendingUp, BarChart2, Star, Radar, Zap,
  BookOpen, Briefcase, CandlestickChart, FlaskConical, PiggyBank,
  Newspaper, Calendar,
  Bot, Monitor, Cpu, ListTodo, Settings,
  ChevronLeft, ChevronRight, LayoutDashboard,
} from 'lucide-react'

const NAV_GROUPS = [
  {
    id: 'CORE',
    items: [
      { id: 'dashboard', icon: LayoutDashboard, label: 'AI CORE' },
    ],
  },
  {
    id: 'MARKETS',
    items: [
      { id: 'stocks',    icon: TrendingUp,       label: 'Stocks'       },
      { id: 'market',    icon: BarChart2,         label: 'Market Hub'   },
      { id: 'toppicks',  icon: Star,              label: 'Top Picks'    },
      { id: 'discovery', icon: Radar,             label: 'AI Discovery' },
      { id: 'intraday',  icon: Zap,               label: 'Intraday'     },
    ],
  },
  {
    id: 'TRADING',
    items: [
      { id: 'watchlist',    icon: BookOpen,         label: 'Watchlist'    },
      { id: 'portfolio',    icon: Briefcase,        label: 'Portfolio'    },
      { id: 'papertrading', icon: CandlestickChart, label: 'Paper Trade'  },
      { id: 'backtest',     icon: FlaskConical,     label: 'Backtest'     },
      { id: 'budget',       icon: PiggyBank,        label: 'Budget AI'    },
    ],
  },
  {
    id: 'INTEL',
    items: [
      { id: 'news',     icon: Newspaper, label: 'Intel Feed' },
      { id: 'calendar', icon: Calendar,  label: 'Calendar'   },
    ],
  },
  {
    id: 'SYSTEM',
    items: [
      { id: 'agents',   icon: Bot,      label: 'Agents'     },
      { id: 'monitor',  icon: Monitor,  label: 'Monitor'    },
      { id: 'llm',      icon: Cpu,      label: 'LLM Engine' },
      { id: 'tasks',    icon: ListTodo, label: 'Tasks'      },
      { id: 'settings', icon: Settings, label: 'Settings'   },
    ],
  },
]

const STATE_LABELS: Record<string, string> = {
  idle: 'STANDBY', listening: 'LISTENING', thinking: 'PROCESSING',
  speaking: 'TRANSMITTING', executing: 'EXECUTING',
}
const STATE_COLORS: Record<string, string> = {
  idle: '#2A5A6A', listening: '#00FF99', thinking: '#009DFF',
  speaking: '#33F2FF', executing: '#FFC857',
}

export function LeftSidebar() {
  const { status, connected, activeNav, setActiveNav } = useJarvisStore()
  const [collapsed, setCollapsed] = useState(false)

  const stateColor = STATE_COLORS[status] || STATE_COLORS.idle

  return (
    <motion.aside
      animate={{ width: collapsed ? 56 : 260 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      className="relative shrink-0 flex flex-col h-full overflow-hidden z-40"
      style={{
        background: 'linear-gradient(180deg, rgba(2,7,18,0.99) 0%, rgba(4,14,30,0.98) 100%)',
        borderRight: '1px solid rgba(0,217,255,0.12)',
      }}
    >
      {/* Right edge glow */}
      <div className="absolute top-0 right-0 bottom-0 w-px pointer-events-none"
        style={{ background: 'linear-gradient(180deg, transparent 0%, rgba(0,217,255,0.25) 25%, rgba(0,217,255,0.25) 75%, transparent 100%)' }} />

      {/* Top corner bracket */}
      <div className="absolute top-0 left-0 w-4 h-4 pointer-events-none"
        style={{ borderTop: '2px solid rgba(0,217,255,0.5)', borderLeft: '2px solid rgba(0,217,255,0.5)' }} />

      {/* ── JARVIS Identity ── */}
      <div className="shrink-0 px-4 pt-4 pb-3" style={{ borderBottom: '1px solid rgba(0,217,255,0.08)' }}>
        <AnimatePresence mode="wait">
          {!collapsed ? (
            <motion.div key="exp" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              <div className="flex items-center gap-3 mb-2">
                {/* Animated AI core orb */}
                <div className="relative flex items-center justify-center shrink-0" style={{ width: 28, height: 28 }}>
                  <motion.div className="absolute rounded-full"
                    style={{ inset: 0, border: '1.5px solid rgba(0,217,255,0.5)' }}
                    animate={{ scale: [1, 1.18, 1], opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 2, repeat: Infinity }} />
                  <motion.div className="w-2.5 h-2.5 rounded-full"
                    style={{ background: 'radial-gradient(circle, #fff 0%, #00D9FF 55%, transparent 100%)', boxShadow: '0 0 10px #00D9FF' }}
                    animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
                </div>
                <div>
                  <div className="text-[15px] font-black tracking-[0.28em]"
                    style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif', textShadow: '0 0 14px rgba(0,217,255,0.8), 0 0 28px rgba(0,217,255,0.4)' }}>
                    JARVIS
                  </div>
                  <div className="text-[8px] tracking-[0.2em] mt-0.5" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>
                    AI OPERATING SYSTEM
                  </div>
                </div>
              </div>
              {/* Status indicators */}
              <div className="flex items-center gap-2 mt-1">
                <motion.div className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: stateColor, boxShadow: `0 0 6px ${stateColor}` }}
                  animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.4, repeat: Infinity }} />
                <span className="text-[9px] font-bold tracking-[0.16em]"
                  style={{ color: stateColor, fontFamily: 'Orbitron, sans-serif' }}>
                  {STATE_LABELS[status] || 'STANDBY'}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <div className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: connected ? '#00FF99' : '#FF5A7A', boxShadow: connected ? '0 0 5px #00FF99' : '0 0 5px #FF5A7A' }} />
                <span className="text-[9px] tracking-[0.14em]"
                  style={{ color: connected ? '#00FF99' : '#FF5A7A', fontFamily: 'Rajdhani, sans-serif' }}>
                  {connected ? 'CONNECTED' : 'OFFLINE'}
                </span>
              </div>
            </motion.div>
          ) : (
            <motion.div key="col" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex justify-center py-1">
              <motion.div className="w-4 h-4 rounded-full"
                style={{ background: 'radial-gradient(circle, #fff 0%, #00D9FF 55%, transparent 100%)', boxShadow: '0 0 10px #00D9FF' }}
                animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-2" style={{ scrollbarWidth: 'none' }}>
        {NAV_GROUPS.map(group => (
          <div key={group.id} className="mb-1">
            {/* Group separator label */}
            {!collapsed && (
              <div className="flex items-center gap-2 px-4 py-1.5">
                <div className="flex-1 h-px" style={{ background: 'rgba(0,217,255,0.08)' }} />
                <span className="text-[8px] font-bold tracking-[0.28em] shrink-0"
                  style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>{group.id}</span>
                <div className="flex-1 h-px" style={{ background: 'rgba(0,217,255,0.08)' }} />
              </div>
            )}
            {/* Nav items */}
            {group.items.map(item => {
              const Icon = item.icon
              const isActive = activeNav === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveNav(item.id)}
                  title={collapsed ? item.label : undefined}
                  className="w-full flex items-center relative overflow-hidden transition-all duration-150"
                  style={{
                    gap: collapsed ? 0 : 12,
                    padding: collapsed ? '10px 0' : '9px 16px',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    background: isActive
                      ? 'linear-gradient(90deg, rgba(0,217,255,0.1) 0%, rgba(0,217,255,0.04) 100%)'
                      : 'transparent',
                    borderLeft: isActive
                      ? '3px solid #00D9FF'
                      : '3px solid transparent',
                    borderRight: 'none',
                    borderTop: 'none',
                    borderBottom: 'none',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={e => {
                    if (!isActive) {
                      e.currentTarget.style.background = 'rgba(0,217,255,0.05)'
                      e.currentTarget.style.borderLeftColor = 'rgba(0,217,255,0.3)'
                    }
                  }}
                  onMouseLeave={e => {
                    if (!isActive) {
                      e.currentTarget.style.background = 'transparent'
                      e.currentTarget.style.borderLeftColor = 'transparent'
                    }
                  }}
                >
                  <Icon
                    size={16}
                    style={{
                      color: isActive ? '#00D9FF' : '#4A7A8A',
                      filter: isActive ? 'drop-shadow(0 0 5px #00D9FF)' : 'none',
                      flexShrink: 0,
                      transition: 'all 0.2s',
                    }}
                  />
                  <AnimatePresence>
                    {!collapsed && (
                      <motion.span
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -6 }}
                        transition={{ duration: 0.15 }}
                        style={{
                          fontSize: 12,
                          fontWeight: isActive ? 700 : 500,
                          color: isActive ? '#C8F9FF' : '#4A7A8A',
                          fontFamily: 'Space Grotesk, sans-serif',
                          letterSpacing: '0.04em',
                          transition: 'color 0.2s',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                  {/* Active pulse dot */}
                  {isActive && !collapsed && (
                    <motion.div
                      className="ml-auto w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ background: '#00D9FF', boxShadow: '0 0 6px #00D9FF' }}
                      animate={{ opacity: [1, 0.2, 1], scale: [1, 0.6, 1] }}
                      transition={{ duration: 1.4, repeat: Infinity }}
                    />
                  )}
                </button>
              )
            })}
          </div>
        ))}
      </nav>

      {/* ── Collapse toggle ── */}
      <div className="shrink-0 flex justify-center py-2.5" style={{ borderTop: '1px solid rgba(0,217,255,0.08)' }}>
        <button
          onClick={() => setCollapsed(c => !c)}
          className="flex items-center justify-center rounded-sm transition-all duration-150"
          style={{
            width: 28, height: 22,
            background: 'rgba(0,217,255,0.04)',
            border: '1px solid rgba(0,217,255,0.12)',
            cursor: 'pointer',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,217,255,0.1)'; e.currentTarget.style.borderColor = 'rgba(0,217,255,0.3)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(0,217,255,0.04)'; e.currentTarget.style.borderColor = 'rgba(0,217,255,0.12)' }}
        >
          {collapsed
            ? <ChevronRight size={11} style={{ color: '#4A7A8A' }} />
            : <ChevronLeft  size={11} style={{ color: '#4A7A8A' }} />
          }
        </button>
      </div>
    </motion.aside>
  )
}
