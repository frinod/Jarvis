'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import {
  LayoutDashboard, TrendingUp, BarChart2, Radar, Zap, Star,
  BookOpen, Briefcase, Newspaper, Calendar, PiggyBank, FlaskConical,
  Settings, ChevronRight, Bot, Monitor, Cpu, ListTodo,
  CandlestickChart,
} from 'lucide-react'

const NAV = [
  { id: 'dashboard',    icon: LayoutDashboard, label: 'COMMAND CENTER', group: 'CORE' },
  { id: 'stocks',       icon: TrendingUp,       label: 'STOCKS',         group: 'MARKETS' },
  { id: 'market',       icon: BarChart2,        label: 'MARKET HUB',     group: 'MARKETS' },
  { id: 'toppicks',     icon: Star,             label: 'TOP PICKS',      group: 'MARKETS' },
  { id: 'discovery',    icon: Radar,            label: 'AI DISCOVERY',   group: 'MARKETS' },
  { id: 'intraday',     icon: Zap,              label: 'INTRADAY',       group: 'MARKETS' },
  { id: 'watchlist',    icon: BookOpen,         label: 'WATCHLIST',      group: 'PORTFOLIO' },
  { id: 'portfolio',    icon: Briefcase,        label: 'PORTFOLIO',      group: 'PORTFOLIO' },
  { id: 'papertrading', icon: CandlestickChart, label: 'PAPER TRADE',    group: 'PORTFOLIO' },
  { id: 'backtest',     icon: FlaskConical,     label: 'BACKTEST',       group: 'PORTFOLIO' },
  { id: 'budget',       icon: PiggyBank,        label: 'BUDGET AI',      group: 'PORTFOLIO' },
  { id: 'news',         icon: Newspaper,        label: 'INTEL FEED',     group: 'INTEL' },
  { id: 'calendar',     icon: Calendar,         label: 'CALENDAR',       group: 'INTEL' },
  { id: 'agents',       icon: Bot,              label: 'AGENTS',         group: 'SYSTEM' },
  { id: 'monitor',      icon: Monitor,          label: 'MONITOR',        group: 'SYSTEM' },
  { id: 'llm',          icon: Cpu,              label: 'LLM ENGINE',     group: 'SYSTEM' },
  { id: 'tasks',        icon: ListTodo,         label: 'TASKS',          group: 'SYSTEM' },
  { id: 'settings',     icon: Settings,         label: 'SETTINGS',       group: 'SYSTEM' },
]

const GROUPS = ['CORE', 'MARKETS', 'PORTFOLIO', 'INTEL', 'SYSTEM']

export function Sidebar() {
  const { activeNav, setActiveNav, status } = useJarvisStore()
  const [collapsed, setCollapsed] = useState(false)
  const [hovered, setHovered] = useState<string | null>(null)

  return (
    <motion.aside
      animate={{ width: collapsed ? 52 : 180 }}
      transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
      className="relative shrink-0 flex flex-col h-full overflow-hidden z-40"
      style={{
        background: 'linear-gradient(180deg, rgba(3,7,18,0.99) 0%, rgba(6,20,37,0.97) 100%)',
        borderRight: '1px solid rgba(0,229,255,0.1)',
        backdropFilter: 'blur(20px)',
      }}
    >
      {/* Right edge glow line */}
      <div
        className="absolute top-0 right-0 bottom-0 w-px"
        style={{ background: 'linear-gradient(180deg, transparent 0%, rgba(0,229,255,0.25) 30%, rgba(0,229,255,0.25) 70%, transparent 100%)' }}
      />

      {/* Collapse toggle */}
      <motion.button
        onClick={() => setCollapsed(c => !c)}
        className="absolute top-3 right-2 z-10 w-5 h-5 flex items-center justify-center rounded-sm btn-neon"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
      >
        <motion.div animate={{ rotate: collapsed ? 0 : 180 }} transition={{ duration: 0.25 }}>
          <ChevronRight size={10} style={{ color: '#2A5A6A' }} />
        </motion.div>
      </motion.button>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden pt-3 pb-4" style={{ scrollbarWidth: 'none' }}>
        {GROUPS.map(group => {
          const items = NAV.filter(n => n.group === group)
          return (
            <div key={group} className="mb-1">
              {!collapsed && (
                <div className="px-3 py-1 mb-0.5 flex items-center gap-2">
                  <div className="flex-1 h-px" style={{ background: 'rgba(0,229,255,0.06)' }} />
                  <span className="text-[6.5px] tracking-[0.3em] shrink-0" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>{group}</span>
                  <div className="flex-1 h-px" style={{ background: 'rgba(0,229,255,0.06)' }} />
                </div>
              )}
              {items.map(item => {
                const active = activeNav === item.id
                const isHovered = hovered === item.id
                const Icon = item.icon
                return (
                  <motion.button
                    key={item.id}
                    onClick={() => setActiveNav(item.id)}
                    onHoverStart={() => setHovered(item.id)}
                    onHoverEnd={() => setHovered(null)}
                    className="w-full flex items-center gap-2.5 relative overflow-hidden"
                    style={{
                      padding: collapsed ? '7px 0' : '7px 12px',
                      justifyContent: collapsed ? 'center' : 'flex-start',
                      background: active ? 'rgba(0,229,255,0.07)' : 'transparent',
                      borderLeft: active ? '2px solid #00E5FF' : '2px solid transparent',
                    }}
                    whileTap={{ scale: 0.97 }}
                    title={collapsed ? item.label : undefined}
                  >
                    {/* Active bg gradient */}
                    {active && (
                      <motion.div
                        className="absolute inset-0"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        style={{ background: 'linear-gradient(90deg, rgba(0,229,255,0.07), transparent 80%)' }}
                      />
                    )}

                    {/* Hover shimmer */}
                    {isHovered && !active && (
                      <motion.div
                        className="absolute inset-0"
                        initial={{ x: '-100%' }}
                        animate={{ x: '200%' }}
                        transition={{ duration: 0.6, ease: 'easeOut' }}
                        style={{ background: 'linear-gradient(90deg, transparent, rgba(0,229,255,0.06), transparent)', width: '60%' }}
                      />
                    )}

                    <Icon
                      size={13}
                      style={{
                        color: active ? '#00E5FF' : isHovered ? '#57F0FF' : '#2A5A6A',
                        filter: active ? 'drop-shadow(0 0 5px #00E5FF)' : isHovered ? 'drop-shadow(0 0 3px #57F0FF)' : 'none',
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
                          className="text-[8px] font-bold tracking-[0.15em] truncate"
                          style={{
                            color: active ? '#00E5FF' : isHovered ? '#7ECFDF' : '#2A5A6A',
                            fontFamily: 'Rajdhani, sans-serif',
                            transition: 'color 0.2s',
                          }}
                        >
                          {item.label}
                        </motion.span>
                      )}
                    </AnimatePresence>

                    {/* Active pulse dot */}
                    {active && !collapsed && (
                      <motion.div
                        className="ml-auto w-1 h-1 rounded-full"
                        style={{ background: '#00E5FF', boxShadow: '0 0 5px #00E5FF' }}
                        animate={{ opacity: [1, 0.2, 1], scale: [1, 0.6, 1] }}
                        transition={{ duration: 1.4, repeat: Infinity }}
                      />
                    )}
                  </motion.button>
                )
              })}
            </div>
          )
        })}
      </nav>

      {/* Bottom status */}
      {!collapsed && (
        <div className="px-3 py-2.5" style={{ borderTop: '1px solid rgba(0,229,255,0.07)' }}>
          <div className="flex items-center gap-2">
            <motion.div
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: status === 'idle' ? '#2A5A6A' : '#00FF95', boxShadow: status !== 'idle' ? '0 0 6px #00FF95' : 'none' }}
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.6, repeat: Infinity }}
            />
            <span className="text-[7px] tracking-[0.2em]" style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>
              JARVIS ONLINE
            </span>
          </div>
        </div>
      )}
    </motion.aside>
  )
}
