'use client'

import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { Activity, Brain, Database, MessageSquare } from 'lucide-react'

export function SystemMonitor() {
  const { systemStats } = useJarvisStore()

  const metrics = [
    { label: 'AI Confidence', value: systemStats.cpu, max: 100, icon: Brain, color: '#06b6d4' },
    { label: 'Memory Entries', value: systemStats.memory, max: 50, icon: Database, color: '#8b5cf6' },
    { label: 'Interactions', value: systemStats.network, max: 100, icon: MessageSquare, color: '#30d158' },
  ]

  return (
    <div className="glass rounded-xl p-4">
      <h3 className="text-[11px] text-jarvis-accent uppercase tracking-wider font-semibold mb-3 flex items-center gap-2">
        <Activity size={12} />
        System Monitor
      </h3>
      <div className="space-y-3">
        {metrics.map((m) => (
          <div key={m.label} className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-jarvis-muted flex items-center gap-1.5">
                <m.icon size={10} />
                {m.label}
              </span>
              <span className="text-[10px] text-jarvis-text font-mono">
                {m.label === 'AI Confidence' ? `${m.value}%` : m.value}
              </span>
            </div>
            <div className="h-1 bg-white/5 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: m.color }}
                initial={{ width: 0 }}
                animate={{ width: `${Math.min((m.value / m.max) * 100, 100)}%` }}
                transition={{ duration: 1, ease: 'easeOut' }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 pt-2 border-t border-jarvis-border">
        <span className="text-[10px] text-jarvis-muted">Uptime: {systemStats.uptime}</span>
      </div>
    </div>
  )
}
