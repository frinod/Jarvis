'use client'
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'

const CONNECTIONS = [
  { id: 'groq',     label: 'GROQ',     icon: '⚡', color: '#00FF9C', group: 'AI' },
  { id: 'backend',  label: 'API',      icon: '◈', color: '#00D9FF', group: 'AI' },
  { id: 'ws',       label: 'WS',       icon: '⟳', color: '#00D9FF', group: 'AI' },
  { id: 'github',   label: 'GITHUB',   icon: '⬡', color: '#7B5EA7', group: 'DEV' },
  { id: 'docker',   label: 'DOCKER',   icon: '◆', color: '#00D9FF', group: 'DEV' },
  { id: 'azure',    label: 'AZURE',    icon: '☁', color: '#00D9FF', group: 'CLOUD' },
  { id: 'aws',      label: 'AWS',      icon: '◉', color: '#FFB347', group: 'CLOUD' },
  { id: 'google',   label: 'GOOGLE',   icon: '◎', color: '#FF4D6D', group: 'CLOUD' },
  { id: 'jira',     label: 'JIRA',     icon: '◇', color: '#00D9FF', group: 'MGMT' },
  { id: 'yahoo',    label: 'YAHOO',    icon: '◈', color: '#7B5EA7', group: 'DATA' },
  { id: 'db',       label: 'DB',       icon: '▣', color: '#00FF9C', group: 'DATA' },
  { id: 'redis',    label: 'REDIS',    icon: '◆', color: '#FF4D6D', group: 'DATA' },
]

type ConnStatus = 'connected' | 'disconnected' | 'connecting'

export function ConnectionsPanel() {
  const { connected } = useJarvisStore()
  const [statuses, setStatuses] = useState<Record<string, ConnStatus>>({
    groq: 'connecting', backend: 'connecting', ws: 'connecting',
    github: 'disconnected', docker: 'disconnected', azure: 'disconnected',
    aws: 'disconnected', google: 'disconnected', jira: 'disconnected',
    yahoo: 'connecting', db: 'connecting', redis: 'disconnected',
  })

  // Simulate connections coming online
  useEffect(() => {
    const sequence = [
      { id: 'backend',  delay: 400,  status: 'connected' as ConnStatus },
      { id: 'ws',       delay: 700,  status: 'connected' as ConnStatus },
      { id: 'groq',     delay: 1200, status: connected ? 'connected' as ConnStatus : 'disconnected' as ConnStatus },
      { id: 'yahoo',    delay: 1600, status: 'connected' as ConnStatus },
      { id: 'db',       delay: 2000, status: 'connected' as ConnStatus },
      { id: 'github',   delay: 2400, status: 'connected' as ConnStatus },
      { id: 'docker',   delay: 2800, status: 'connected' as ConnStatus },
    ]
    sequence.forEach(({ id, delay, status }) => {
      setTimeout(() => setStatuses(s => ({ ...s, [id]: status })), delay)
    })
  }, [connected])

  useEffect(() => {
    setStatuses(s => ({
      ...s,
      backend: connected ? 'connected' : 'disconnected',
      ws: connected ? 'connected' : 'disconnected',
      groq: connected ? 'connected' : 'disconnected',
    }))
  }, [connected])

  const statusColor: Record<ConnStatus, string> = {
    connected: '#00FF9C', disconnected: '#2A5A6A', connecting: '#FFB347',
  }

  const connectedCount = Object.values(statuses).filter(s => s === 'connected').length

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2 px-1">
        <div className="flex items-center gap-2">
          <div className="w-1 h-1 rounded-full" style={{ background: '#00FF9C', boxShadow: '0 0 4px #00FF9C' }} />
          <span className="text-[8px] font-bold tracking-[0.22em]" style={{ color: '#00FF9C', fontFamily: 'Orbitron, sans-serif' }}>CONNECTIONS</span>
        </div>
        <span className="text-[7px] font-bold" style={{ color: '#00FF9C', fontFamily: 'IBM Plex Mono, monospace' }}>
          {connectedCount}/{CONNECTIONS.length}
        </span>
      </div>

      <div className="grid grid-cols-6 gap-1">
        {CONNECTIONS.map((conn, i) => {
          const st = statuses[conn.id] || 'disconnected'
          const sc = statusColor[st]
          const isConn = st === 'connected'
          const isConnecting = st === 'connecting'

          return (
            <motion.div
              key={conn.id}
              className="relative flex flex-col items-center gap-0.5 p-1.5"
              style={{
                background: isConn ? `rgba(0,255,156,0.04)` : 'rgba(8,19,40,0.5)',
                border: `1px solid ${isConn ? 'rgba(0,255,156,0.2)' : isConnecting ? 'rgba(255,179,71,0.2)' : 'rgba(0,217,255,0.06)'}`,
                borderRadius: 2,
              }}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.04 }}
              whileHover={{ scale: 1.06 }}
            >
              {/* Icon */}
              <span className="text-[11px] leading-none" style={{ color: isConn ? conn.color : '#2A5A6A', textShadow: isConn ? `0 0 6px ${conn.color}` : 'none' }}>
                {conn.icon}
              </span>

              {/* Label */}
              <span className="text-[5.5px] font-bold tracking-wide text-center" style={{ color: isConn ? '#7ECFDF' : '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>
                {conn.label}
              </span>

              {/* Status dot */}
              <motion.div
                className="w-1 h-1 rounded-full"
                style={{ background: sc }}
                animate={isConnecting ? { opacity: [1, 0.2, 1] } : isConn ? { boxShadow: [`0 0 2px ${sc}`, `0 0 6px ${sc}`, `0 0 2px ${sc}`] } : {}}
                transition={{ duration: isConnecting ? 0.8 : 2, repeat: Infinity }}
              />

              {/* Connecting shimmer */}
              {isConnecting && (
                <div className="absolute inset-0 overflow-hidden rounded-sm">
                  <motion.div
                    className="absolute inset-0"
                    style={{ background: 'linear-gradient(90deg, transparent, rgba(255,179,71,0.08), transparent)' }}
                    animate={{ x: ['-100%', '200%'] }}
                    transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
                  />
                </div>
              )}
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
