'use client'

import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { Bot, Circle } from 'lucide-react'

export function AgentsPanel() {
  const { agents } = useJarvisStore()

  return (
    <div className="glass rounded-xl p-4">
      <h3 className="text-[11px] text-jarvis-accent uppercase tracking-wider font-semibold mb-3 flex items-center gap-2">
        <Bot size={12} />
        Active Agents
      </h3>
      <div className="space-y-2.5">
        {agents.map((agent) => (
          <motion.div
            key={agent.id}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2.5"
          >
            <div className={`w-1.5 h-1.5 rounded-full ${
              agent.status === 'active' ? 'bg-jarvis-neon-green animate-pulse' :
              agent.status === 'error' ? 'bg-jarvis-neon-red' :
              'bg-jarvis-muted'
            }`} />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-jarvis-text truncate">{agent.name}</p>
              {agent.task && (
                <p className="text-[10px] text-jarvis-muted truncate">{agent.task}</p>
              )}
            </div>
            <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${
              agent.status === 'active'
                ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green'
                : 'bg-white/5 text-jarvis-muted'
            }`}>
              {agent.status}
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
