'use client'
import { AnimatePresence, motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'

const SWEEP = [1, 2, 3, 4, 5, 6]

export function BladeSweep() {
  const phase = useJarvisStore((s) => s.phase)
  const activeToolName = useJarvisStore((s) => s.activeToolName)

  return (
    <AnimatePresence>
      {phase === 'tooling' && (
        <motion.div
          className="jarvis-blades"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        >
          <div className="jarvis-blade-field">
            {SWEEP.map((n) => (
              <span key={n} className={`jarvis-blade jarvis-blade-${n}`} />
            ))}
          </div>
          {activeToolName && (
            <div className="jarvis-blade-carrier">
              <span key={activeToolName} className="jarvis-blade-tool">
                {activeToolName.replace(/[_-]/g, ' ')}
              </span>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
