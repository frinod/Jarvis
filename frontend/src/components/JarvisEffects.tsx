'use client'
import { useEffect, useRef, useState } from 'react'
import { useJarvisStore } from '@/store/jarvisStore'

type EffectKind = 'glitch' | 'pulse' | 'scan' | 'shake' | 'flash'

const DURATION: Record<EffectKind, number> = {
  glitch: 620, pulse: 900, scan: 900, shake: 520, flash: 480,
}

export function JarvisEffects() {
  const [live, setLive] = useState<{ kind: EffectKind; at: number } | null>(null)
  const root = useRef<HTMLDivElement | null>(null)

  // Expose a global trigger so any component can fire an effect
  useEffect(() => {
    (window as unknown as Record<string, unknown>).__jarvisEffect = (kind: EffectKind) => {
      setLive({ kind, at: Date.now() })
      setTimeout(() => setLive(null), DURATION[kind] ?? 600)
    }
  }, [])

  useEffect(() => {
    if (!live || live.kind !== 'shake') return
    const hud = root.current?.closest('.jarvis-hud')
    if (!hud) return
    hud.classList.add('jarvis-fx-shaking')
    const done = setTimeout(() => hud.classList.remove('jarvis-fx-shaking'), DURATION.shake)
    return () => { clearTimeout(done); hud.classList.remove('jarvis-fx-shaking') }
  }, [live])

  if (!live) return null

  return (
    <div className="jarvis-fx" ref={root} aria-hidden="true">
      <div key={`${live.kind}-${live.at}`} className={`jarvis-fx-play jarvis-fx-${live.kind}`}>
        {live.kind === 'glitch' && (<><span className="jarvis-fx-slice" /><span className="jarvis-fx-slice" /><span className="jarvis-fx-slice" /></>)}
        {live.kind === 'pulse' && (<><span className="jarvis-fx-wave" /><span className="jarvis-fx-wave" /></>)}
      </div>
    </div>
  )
}
