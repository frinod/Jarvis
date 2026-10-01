'use client'
import { useJarvisStore } from '@/store/jarvisStore'

/**
 * The start gate. Browsers block audio until a user gesture — this is that gesture.
 * A dead black screen with a spinning ring. Click it to power up.
 * NOT wrapped in AnimatePresence — an invisible fixed inset:0 button would eat
 * every click for the rest of the session if the exit animation never completed.
 */
export function Ignition({ onStart }: { onStart: () => void }) {
  const phase = useJarvisStore((s) => s.phase)
  if (phase !== 'offline') return null

  return (
    <button className="jarvis-ignition" onClick={onStart}>
      <span className="jarvis-ignition-ring" />
      <span className="jarvis-ignition-label">
        <span className="jarvis-ignition-word">INITIALISE</span>
        <span className="jarvis-ignition-sub">click to power up</span>
      </span>
    </button>
  )
}
