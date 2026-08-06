'use client'
import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { openModal } from '@/components/HolographicModal'
import {
  LayoutDashboard, TrendingUp, Briefcase, BarChart2,
  Newspaper, Calendar, Settings, Monitor,
} from 'lucide-react'

const HEX_CLIP = 'polygon(50% 0%, 95% 25%, 95% 75%, 50% 100%, 5% 75%, 5% 25%)'

const NAV_ITEMS = [
  { id: 'dashboard',   icon: LayoutDashboard, label: 'DASHBOARD',  modal: null        },
  { id: 'stocks',      icon: TrendingUp,      label: 'MARKETS',    modal: 'stocks'    },
  { id: 'portfolio',   icon: Briefcase,       label: 'PORTFOLIO',  modal: 'portfolio' },
  { id: 'market',      icon: BarChart2,       label: 'ANALYTICS',  modal: 'market'    },
  null,
  { id: 'news',        icon: Newspaper,       label: 'NEWS',       modal: 'news'      },
  { id: 'calendar',    icon: Calendar,        label: 'CALENDAR',   modal: 'calendar'  },
  { id: 'settings',    icon: Settings,        label: 'SETTINGS',   modal: 'settings'  },
  { id: 'monitor',     icon: Monitor,         label: 'SYSTEM',     modal: 'monitor'   },
]

// ── 6.2 Single hex tab ────────────────────────────────────────
function HexTab({ item, active, onClick }: {
  item: { id: string; icon: any; label: string; modal: string | null }
  active: boolean
  onClick: () => void
}) {
  const Icon = item.icon
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1 relative"
      style={{ background: 'transparent', border: 'none', cursor: 'pointer', minWidth: 64 }}
    >
      {/* Hex shape */}
      <motion.div
        style={{
          width: 44, height: 44,
          clipPath: HEX_CLIP,
          background: active
            ? 'linear-gradient(135deg, rgba(0,217,255,0.22) 0%, rgba(0,157,255,0.14) 100%)'
            : 'linear-gradient(135deg, rgba(5,19,38,0.9) 0%, rgba(2,8,19,0.95) 100%)',
          border: 'none',
          position: 'relative',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
        animate={active ? {
          filter: ['drop-shadow(0 0 6px rgba(0,217,255,0.6))', 'drop-shadow(0 0 14px rgba(0,217,255,0.9))', 'drop-shadow(0 0 6px rgba(0,217,255,0.6))'],
        } : { filter: 'drop-shadow(0 0 2px rgba(0,217,255,0.1))' }}
        transition={{ duration: 1.8, repeat: Infinity }}
        whileHover={{ filter: 'drop-shadow(0 0 10px rgba(0,217,255,0.7))' }}
      >
        {/* Hex border overlay */}
        <div style={{
          position: 'absolute', inset: 2,
          clipPath: HEX_CLIP,
          background: active ? 'rgba(0,217,255,0.08)' : 'transparent',
        }} />
        <Icon size={16} style={{
          color: active ? '#00D9FF' : '#2A5A6A',
          filter: active ? 'drop-shadow(0 0 5px #00D9FF)' : 'none',
          position: 'relative', zIndex: 1,
          transition: 'all 0.2s',
        }} />
      </motion.div>

      {/* Label */}
      <span className="text-[6.5px] font-bold tracking-[0.14em]"
        style={{
          color: active ? '#00D9FF' : '#2A5A6A',
          fontFamily: 'Orbitron, sans-serif',
          textShadow: active ? '0 0 8px rgba(0,217,255,0.6)' : 'none',
          transition: 'all 0.2s',
        }}>{item.label}</span>

      {/* Active indicator dot */}
      {active && (
        <motion.div className="absolute -bottom-0.5 w-1 h-1 rounded-full"
          style={{ background: '#00D9FF', boxShadow: '0 0 6px #00D9FF' }}
          animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1.2, repeat: Infinity }} />
      )}
    </button>
  )
}

// ── Center orb ────────────────────────────────────────────────
function CenterOrb() {
  return (
    <div className="flex flex-col items-center gap-1" style={{ minWidth: 64 }}>
      <motion.div
        className="relative flex items-center justify-center rounded-full"
        style={{
          width: 44, height: 44,
          background: 'radial-gradient(circle, rgba(0,217,255,0.25) 0%, rgba(0,157,255,0.1) 60%, transparent 100%)',
          border: '1.5px solid rgba(0,217,255,0.5)',
        }}
        animate={{
          boxShadow: [
            '0 0 12px rgba(0,217,255,0.4), 0 0 24px rgba(0,217,255,0.15)',
            '0 0 22px rgba(0,217,255,0.7), 0 0 44px rgba(0,217,255,0.25)',
            '0 0 12px rgba(0,217,255,0.4), 0 0 24px rgba(0,217,255,0.15)',
          ],
        }}
        transition={{ duration: 2, repeat: Infinity }}
      >
        {/* Outer pulse ring */}
        <motion.div className="absolute rounded-full pointer-events-none"
          style={{ inset: -6, border: '1px solid rgba(0,217,255,0.2)' }}
          animate={{ scale: [1, 1.25], opacity: [0.5, 0] }}
          transition={{ duration: 1.8, repeat: Infinity }} />
        {/* Inner core */}
        <motion.div className="w-3 h-3 rounded-full"
          style={{ background: 'radial-gradient(circle, #ffffff 0%, #00D9FF 50%, transparent 100%)',
            boxShadow: '0 0 10px #00D9FF' }}
          animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
      </motion.div>
      <span className="text-[6.5px] font-bold tracking-[0.14em]"
        style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif',
          textShadow: '0 0 8px rgba(0,217,255,0.6)' }}> </span>
    </div>
  )
}

// ── 6.3 Bottom nav bar ────────────────────────────────────────
export function BottomNav() {
  const { activeNav, setActiveNav } = useJarvisStore()

  return (
    <div
      className="relative shrink-0 flex flex-col"
      style={{
        background: 'linear-gradient(180deg, rgba(2,8,19,0.98) 0%, rgba(5,19,38,0.99) 100%)',
        borderTop: '1px solid rgba(0,217,255,0.12)',
        boxShadow: '0 -4px 40px rgba(0,0,0,0.7)',
      }}
    >
      {/* Top shimmer */}
      <div className="absolute top-0 left-0 right-0 h-px border-shimmer" />

      {/* Nav items row */}
      <div className="flex items-center justify-between px-6 py-2">
        {NAV_ITEMS.map((item, i) =>
          item === null
            ? <CenterOrb key="orb" />
            : (
              <HexTab
                key={item.id}
                item={item}
                active={activeNav === item.id}
                onClick={() => {
        if (item.id === 'dashboard') {
          setActiveNav('dashboard')
        } else if (item.modal) {
          openModal(item.modal)
        }
      }}
              />
            )
        )}
      </div>

      {/* 6.3 Bottom status bar */}
      <div className="flex items-center justify-between px-4 pb-1.5"
        style={{ borderTop: '1px solid rgba(0,217,255,0.05)' }}>
        <div className="flex items-center gap-2">
          <motion.div className="w-1 h-1 rounded-full"
            style={{ background: '#00D9FF', boxShadow: '0 0 4px #00D9FF' }}
            animate={{ opacity: [1, 0.2, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
          <span className="text-[6.5px] tracking-[0.2em]"
            style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>JARVIS v2.0.0</span>
          <span className="text-[6.5px]" style={{ color: '#0d2035', fontFamily: 'Rajdhani, sans-serif' }}>·</span>
          <span className="text-[6.5px] tracking-[0.2em]"
            style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>STARK INDUSTRIES</span>
        </div>

        {/* Connector dots between tabs */}
        <div className="flex items-center gap-1">
          {Array.from({ length: 12 }, (_, i) => (
            <motion.div key={i} className="w-1 h-px rounded-full"
              style={{ background: 'rgba(0,217,255,0.2)' }}
              animate={{ opacity: [0.2, 0.8, 0.2] }}
              transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.1 }} />
          ))}
        </div>

        <div className="flex items-center gap-1.5">
          <motion.div className="w-1.5 h-1.5 rounded-full"
            style={{ background: '#00FF99', boxShadow: '0 0 5px #00FF99' }}
            animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.2, repeat: Infinity }} />
          <span className="text-[6.5px] tracking-[0.2em]"
            style={{ color: '#00FF99', fontFamily: 'Rajdhani, sans-serif' }}>ALL SYSTEMS OPERATIONAL</span>
        </div>
      </div>
    </div>
  )
}
