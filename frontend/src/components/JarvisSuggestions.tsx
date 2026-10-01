'use client'
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'

const EXAMPLES = [
  'analyze Reliance Industries',
  'what are the top gainers today',
  'show me the market heatmap',
  'set alert for TCS above 4200',
  'compare Infosys and Wipro',
  'what is the NSE market session status',
  'show intraday signal for HDFC Bank',
  'what are the top picks today',
  'run a stock screener for high ROE',
  'show me the portfolio performance',
]

const ROTATE_MS = 4200

export function JarvisSuggestions() {
  const phase = useJarvisStore((s) => s.phase)
  const messages = useJarvisStore((s) => s.messages)
  const [i, setI] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % EXAMPLES.length), ROTATE_MS)
    return () => clearInterval(id)
  }, [])

  if (phase !== 'dormant' || messages.length > 0) return null

  return (
    <div className="jarvis-suggest">
      <span className="jarvis-suggest-lead">try</span>
      <AnimatePresence mode="wait">
        <motion.span
          key={i}
          className="jarvis-suggest-text"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.35 }}
        >
          "hey jarvis, {EXAMPLES[i]}"
        </motion.span>
      </AnimatePresence>
    </div>
  )
}
