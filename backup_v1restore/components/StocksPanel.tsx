'use client'

import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, BarChart2, Wifi, WifiOff } from 'lucide-react'
import { useJarvisStore } from '@/store/jarvisStore'

// StocksPanel reads from shared store — WebSocket is owned by StocksPage
export function StocksPanel() {
  const { indices, stocks, setActiveNav, stocksLoading } = useJarvisStore()

  const topMovers = stocks.slice(0, 5)

  return (
    <div className="glass rounded-xl p-4">
      <h3
        className="text-[11px] text-jarvis-accent uppercase tracking-wider font-semibold mb-3 flex items-center gap-2 cursor-pointer hover:text-jarvis-glow transition-colors"
        onClick={() => setActiveNav('stocks')}
      >
        <BarChart2 size={12} />
        Markets
        <span className="ml-auto">
          {stocks.length > 0
            ? <Wifi size={9} className="text-jarvis-neon-green" />
            : <WifiOff size={9} className="text-jarvis-muted" />}
        </span>
      </h3>

      {indices.length === 0 ? (
        <p className="text-[10px] text-jarvis-muted">Connecting to live feed...</p>
      ) : (
        <>
          {/* Indices */}
          <div className="space-y-1.5 mb-3">
            {indices.slice(0, 3).map((idx) => (
              <div key={idx.symbol} className="flex items-center justify-between">
                <span className="text-[10px] text-jarvis-muted truncate max-w-[90px]">{idx.name}</span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-jarvis-text font-mono">
                    {idx.price.toLocaleString('en-IN')}
                  </span>
                  <span className={`text-[9px] font-mono ${idx.change_pct >= 0 ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
                    {idx.change_pct >= 0 ? '+' : ''}{idx.change_pct.toFixed(2)}%
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-jarvis-border mb-2.5" />

          <p className="text-[9px] text-jarvis-muted uppercase tracking-wider mb-2">Top Movers</p>
          <div className="space-y-1.5">
            {topMovers.map((s) => (
              <motion.div
                key={s.symbol}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center justify-between"
              >
                <div className="flex items-center gap-1.5">
                  {s.change_pct >= 0
                    ? <TrendingUp size={9} className="text-jarvis-neon-green" />
                    : <TrendingDown size={9} className="text-jarvis-neon-red" />}
                  <span className="text-[10px] text-jarvis-text font-mono">{s.symbol}</span>
                </div>
                <span className={`text-[9px] font-mono ${s.change_pct >= 0 ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
                  {s.change_pct >= 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
                </span>
              </motion.div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
