'use client'
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'

const AGENTS = [
  { id: 'research',  label: 'RESEARCH',  icon: '◈', color: '#00D9FF', task: 'Scanning market news...' },
  { id: 'finance',   label: 'FINANCE',   icon: '◆', color: '#00FF9C', task: 'Analysing portfolio...' },
  { id: 'developer', label: 'DEV',       icon: '⬡', color: '#7B5EA7', task: 'Code execution ready' },
  { id: 'devops',    label: 'DEVOPS',    icon: '⬢', color: '#FFB347', task: 'Monitoring services...' },
  { id: 'system',    label: 'SYSTEM',    icon: '◉', color: '#00D9FF', task: 'Resource management' },
  { id: 'personal',  label: 'PERSONAL',  icon: '◎', color: '#00FF9C', task: 'Calendar sync active' },
  { id: 'content',   label: 'CONTENT',   icon: '◇', color: '#FF4D6D', task: 'Idle — awaiting task' },
]

type AgentStatus = 'active' | 'idle' | 'busy' | 'error'

export function AgentCards() {
  const { status, connected } = useJarvisStore()
  const [agentStates, setAgentStates] = useState<Record<string, AgentStatus>>({
    research: 'active', finance: 'active', developer: 'idle',
    devops: 'active', system: 'active', personal: 'idle', content: 'idle',
  })
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 3000)
    return () => clearInterval(id)
  }, [])

  // React to JARVIS status
  useEffect(() => {
    if (status === 'thinking') {
      setAgentStates(s => ({ ...s, research: 'busy', finance: 'busy' }))
    } else if (status === 'executing') {
      setAgentStates(s => ({ ...s, developer: 'busy', devops: 'busy' }))
    } else if (status === 'idle') {
      setAgentStates(s => ({ ...s, research: 'active', finance: 'active', developer: 'idle', devops: 'active' }))
    }
  }, [status])

  const statusColor: Record<AgentStatus, string> = {
    active: '#00FF9C', idle: '#2A5A6A', busy: '#FFB347', error: '#FF4D6D',
  }
  const statusLabel: Record<AgentStatus, string> = {
    active: 'ONLINE', idle: 'STANDBY', busy: 'BUSY', error: 'ERROR',
  }

  return (
    <div className="w-full">
      <div className="flex items-center gap-2 mb-2 px-1">
        <div className="w-1 h-1 rounded-full" style={{ background: '#00D9FF', boxShadow: '0 0 4px #00D9FF' }} />
        <span className="text-[8px] font-bold tracking-[0.22em]" style={{ color: '#00D9FF', fontFamily: 'Orbitron, sans-serif' }}>
          AI AGENTS — {Object.values(agentStates).filter(s => s !== 'idle').length}/7 ACTIVE
        </span>
      </div>

      <div className="grid grid-cols-7 gap-1.5">
        {AGENTS.map((agent, i) => {
          const st = agentStates[agent.id] || 'idle'
          const sc = statusColor[st]
          const isBusy = st === 'busy'
          const isActive = st === 'active'

          return (
            <motion.div
              key={agent.id}
              className="relative flex flex-col items-center gap-1 p-2 cursor-pointer"
              style={{
                background: isActive || isBusy
                  ? `rgba(${agent.color === '#00D9FF' ? '0,217,255' : agent.color === '#00FF9C' ? '0,255,156' : agent.color === '#7B5EA7' ? '123,94,167' : agent.color === '#FFB347' ? '255,179,71' : agent.color === '#FF4D6D' ? '255,77,109' : '0,217,255'},0.06)`
                  : 'rgba(8,19,40,0.6)',
                border: `1px solid ${isActive || isBusy ? agent.color + '40' : 'rgba(0,217,255,0.08)'}`,
                borderRadius: 2,
              }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ scale: 1.04, borderColor: agent.color + '80' }}
            >
              {/* Corner brackets */}
              <div className="absolute top-0 left-0 w-2 h-2" style={{ borderTop: `1px solid ${agent.color}60`, borderLeft: `1px solid ${agent.color}60` }} />
              <div className="absolute bottom-0 right-0 w-2 h-2" style={{ borderBottom: `1px solid ${agent.color}60`, borderRight: `1px solid ${agent.color}60` }} />

              {/* Icon */}
              <motion.div
                className="text-[14px] leading-none"
                style={{ color: isActive || isBusy ? agent.color : '#2A5A6A', textShadow: isActive || isBusy ? `0 0 8px ${agent.color}` : 'none' }}
                animate={isBusy ? { opacity: [1, 0.4, 1] } : isActive ? { scale: [1, 1.1, 1] } : {}}
                transition={{ duration: isBusy ? 0.6 : 2, repeat: Infinity }}
              >
                {agent.icon}
              </motion.div>

              {/* Label */}
              <span className="text-[6px] font-bold tracking-[0.15em] text-center leading-tight" style={{ color: isActive || isBusy ? agent.color : '#2A5A6A', fontFamily: 'Orbitron, sans-serif' }}>
                {agent.label}
              </span>

              {/* Status dot */}
              <motion.div
                className="w-1 h-1 rounded-full"
                style={{ background: sc, boxShadow: st !== 'idle' ? `0 0 4px ${sc}` : 'none' }}
                animate={st !== 'idle' ? { opacity: [1, 0.3, 1] } : {}}
                transition={{ duration: 1.2, repeat: Infinity }}
              />

              {/* Busy beam */}
              {isBusy && (
                <div className="absolute bottom-0 left-0 right-0 h-px overflow-hidden load-beam" style={{ background: 'rgba(255,179,71,0.15)' }} />
              )}
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
