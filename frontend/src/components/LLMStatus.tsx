'use client'

import { useJarvisStore } from '@/store/jarvisStore'
import { Brain, Zap, Wifi, WifiOff } from 'lucide-react'

export function LLMStatus() {
  const { llmInfo, connected } = useJarvisStore()

  return (
    <div className="glass rounded-xl p-4">
      <h3 className="text-[11px] text-jarvis-accent uppercase tracking-wider font-semibold mb-3 flex items-center gap-2">
        <Brain size={12} />
        LLM Status
      </h3>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-jarvis-muted">Provider</span>
          <span className="text-[11px] text-jarvis-text font-mono truncate max-w-[120px]">{llmInfo.provider}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-jarvis-muted">Available</span>
          <span className="text-[11px] text-jarvis-text font-mono truncate max-w-[120px]">{llmInfo.model}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-jarvis-muted">Status</span>
          <span className={`text-[10px] flex items-center gap-1 ${
            llmInfo.status === 'connected' ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'
          }`}>
            {llmInfo.status === 'connected' ? <Wifi size={9} /> : <WifiOff size={9} />}
            {llmInfo.status}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-jarvis-muted">Backend</span>
          <span className={`text-[10px] flex items-center gap-1 ${
            connected ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'
          }`}>
            <Zap size={9} />
            {connected ? 'online' : 'offline'}
          </span>
        </div>
      </div>
    </div>
  )
}
