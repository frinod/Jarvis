'use client'
import { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'

/**
 * JarvisBoot — 4-beat startup sequence.
 * Plays sfx 'boot' cue + boot-music + ambient on mount.
 * Timing driven by setInterval (not rAF — rAF throttles in background tabs).
 */

const T = { rings: 2600, suit: 5200, reactor: 7200, done: 8800 }

const LOG_LINES = [
  'MOUNT F:/BACKUP/GHOST (HIDDEN)',
  'EXTEND SYSTEM MEMORY .......... OK',
  'TELEMETRY / COMP CALIBRATION',
  'LOAD MARKET INTELLIGENCE ENGINE',
  'XGBOOST MODELS ................ OK',
  'ANGEL ONE FEED ................ STANDBY',
  'CHECKSUM ...................... OK',
  'RUN SYSTEM TOOL',
]

type Stage = 'bar' | 'rings' | 'suit' | 'reactor'

export function JarvisBoot({ onComplete }: { onComplete?: () => void }) {
  const phase = useJarvisStore((s) => s.phase)
  const reduced = useReducedMotion()
  const [t, setT] = useState(0)

  useEffect(() => {
    if (phase !== 'boot') { setT(0); return }

    // Play audio — must be called after user gesture (Ignition click)
    import('@/lib/sfx').then((sfx) => sfx.play('boot'))
    import('@/lib/music').then((music) => { music.enable(); music.playBoot(); music.startAmbient() })

    const start = Date.now()
    setT(0)
    const id = setInterval(() => {
      const elapsed = Date.now() - start
      setT(elapsed)
      if (elapsed >= T.done) {
        clearInterval(id)
        onComplete?.()
        // Welcome greeting after boot completes
        setTimeout(() => {
          if (typeof window === 'undefined' || !window.speechSynthesis) return
          const hour = new Date().getHours()
          const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
          const msg = `${greeting}, Sir. Welcome to J.A.R.V.I.S. All systems are online and standing by for your command.`
          const chunks = msg.match(/[^.!?]+[.!?]*/g)?.map(s => s.trim()).filter(Boolean) || [msg]
          const voices = window.speechSynthesis.getVoices()
          const voice =
            voices.find(v => v.name.toLowerCase().includes('google uk english male')) ||
            voices.find(v => v.name.toLowerCase().includes('david')) ||
            voices.find(v => v.name.toLowerCase().includes('daniel')) ||
            voices.find(v => v.lang.startsWith('en-')) || null
          window.speechSynthesis.cancel()
          let i = 0
          const next = () => {
            if (i >= chunks.length) return
            const utt = new SpeechSynthesisUtterance(chunks[i++])
            utt.lang = 'en-IN'; utt.rate = 1.0; utt.pitch = 0.85; utt.volume = 1
            if (voice) utt.voice = voice
            utt.onend = next
            window.speechSynthesis.speak(utt)
          }
          setTimeout(next, 80)
        }, 400)
      }
    }, 50)
    return () => clearInterval(id)
  }, [phase]) // eslint-disable-line

  if (phase !== 'boot') return null

  const stage: Stage =
    t >= T.reactor ? 'reactor' : t >= T.suit ? 'suit' : t >= T.rings ? 'rings' : 'bar'

  const logShown = Math.min(LOG_LINES.length, Math.floor((t / T.rings) * (LOG_LINES.length + 1)))
  const barPct = Math.min(1, t / (T.rings - 300))

  return (
    <AnimatePresence>
      <motion.div
        key="boot"
        className="jarvis-boot"
        initial={{ opacity: 1 }}
        exit={{ opacity: 0, filter: 'blur(10px)' }}
        transition={{ duration: 0.8 }}
      >
        {/* Beat 1: status bar */}
        <div className={`jarvis-boot-bar${stage !== 'bar' ? ' jarvis-boot-bar-dim' : ''}`}>
          <div className="jarvis-boot-bar-frame">
            <span className="jarvis-boot-bar-title">
              INITIATING SYSTEM 1<span className="jarvis-boot-dots">…</span>
              <span className="jarvis-boot-cursor" />
            </span>
            <div className="jarvis-boot-seg">
              {Array.from({ length: 22 }, (_, i) => (
                <span key={i} className="jarvis-boot-seg-cell" data-on={i / 22 < barPct ? '1' : '0'} />
              ))}
            </div>
          </div>
          <div className="jarvis-boot-log">
            {LOG_LINES.slice(0, logShown).map((l) => (
              <div key={l} className="jarvis-boot-log-line">{l}</div>
            ))}
          </div>
        </div>

        {/* Beats 2-4: centre stage */}
        <div className="jarvis-boot-stage">
          {stage === 'rings'   && <BootRings   reduced={!!reduced} />}
          {stage === 'suit'    && <BootSuit     reduced={!!reduced} />}
          {stage === 'reactor' && <BootReactor  reduced={!!reduced} t={t - T.reactor} />}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

// ── Beat 2: concentric reticle rings ─────────────────────────────────────────

function BootRings({ reduced }: { reduced: boolean }) {
  const ease = 'easeOut'
  const ring = (r: number, delay: number, dash: string, w = 1) => (
    <motion.circle cx="0" cy="0" r={r} className="jarvis-boot-ring"
      strokeDasharray={dash} strokeWidth={w}
      initial={reduced ? { opacity: 1 } : { opacity: 0, rotate: -40, scale: 1.15 }}
      animate={{ opacity: 1, rotate: 0, scale: 1 }}
      transition={{ duration: 0.7, delay, ease }}
    />
  )
  return (
    <svg className="jarvis-boot-rings" viewBox="-160 -160 320 320">
      <g>
        {ring(150, 0.0, '3 6')}
        {ring(128, 0.08, '40 8 12 8', 1.4)}
        {ring(104, 0.16, '2 4')}
        {ring(84,  0.24, '30 6 6 6', 1.6)}
        {ring(60,  0.34, '1 3')}
      </g>
      <motion.text x="0" y="6" className="jarvis-boot-name"
        initial={reduced ? { opacity: 1 } : { opacity: 0, letterSpacing: '1.4em' } as any}
        animate={{ opacity: 1, letterSpacing: '0.42em' }}
        transition={{ duration: 0.7, delay: 0.5, ease }}
      >
        J.A.R.V.I.S
      </motion.text>
    </svg>
  )
}

// ── Beat 3: suit schematic ────────────────────────────────────────────────────

function BootSuit({ reduced }: { reduced: boolean }) {
  return (
    <svg className="jarvis-boot-suit" viewBox="-200 -150 400 300">
      <motion.g className="jarvis-boot-suit-fig"
        initial={reduced ? { opacity: 1 } : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <motion.path className="jarvis-boot-wire"
          d="M0,-118 C11,-118 17,-108 17,-96 C17,-86 12,-80 12,-74
             L22,-64 L30,-30 L26,26 L34,64 L28,66 L18,30 L16,64 L20,110
             L6,112 L2,66 L-2,66 L-6,112 L-20,110 L-16,64 L-18,30 L-28,66
             L-34,64 L-26,26 L-30,-30 L-22,-64 L-12,-74 C-12,-80 -17,-86 -17,-96
             C-17,-108 -11,-118 0,-118 Z"
          initial={reduced ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 1.4, ease: 'easeInOut' }}
        />
        <path className="jarvis-boot-wire jarvis-boot-wire-dim" d="M-9,-104 L9,-104 M-8,-96 L8,-96 M0,-92 L0,-84" />
        <circle className="jarvis-boot-wire" cx="0" cy="-40" r="9" />
        <path className="jarvis-boot-wire jarvis-boot-wire-dim" d="M0,-49 L0,-31 M-9,-40 L9,-40" />
      </motion.g>
      {([-150, 150] as number[]).map((x, i) => (
        <motion.g key={x} className="jarvis-boot-callout"
          initial={reduced ? { opacity: 1 } : { opacity: 0, x: x > 0 ? 20 : -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.3 + i * 0.12 }}
        >
          <circle className="jarvis-boot-wire" cx={x} cy="-10" r="26" strokeDasharray="30 6 6 6" />
          <circle className="jarvis-boot-wire jarvis-boot-wire-dim" cx={x} cy="-10" r="15" />
          <circle className="jarvis-boot-wire" cx={x} cy="-10" r="3" />
          <path className="jarvis-boot-wire jarvis-boot-wire-dim"
            d={x > 0 ? `M${x - 26},-10 L60,-10` : `M${x + 26},-10 L-60,-10`} />
        </motion.g>
      ))}
      <text x="-150" y="34" className="jarvis-boot-tag">MARKET / DATA</text>
      <text x="150"  y="34" className="jarvis-boot-tag">XGBOOST / AI</text>
    </svg>
  )
}

// ── Beat 4: arc reactor ───────────────────────────────────────────────────────

function BootReactor({ reduced, t }: { reduced: boolean; t: number }) {
  const glow = reduced ? 1 : Math.min(1, Math.max(0, t / 1400))
  const seg = Array.from({ length: 16 }, (_, i) => i)
  return (
    <svg className="jarvis-boot-reactor" viewBox="-120 -120 240 240"
      style={{ ['--glow' as string]: glow }}
    >
      {seg.map((i) => {
        const a = (i / seg.length) * Math.PI * 2 - Math.PI / 2
        const on = i / seg.length < glow * 1.05
        return (
          <line key={i}
            x1={Math.cos(a) * 70} y1={Math.sin(a) * 70}
            x2={Math.cos(a) * 100} y2={Math.sin(a) * 100}
            className={on ? 'jarvis-boot-r-seg jarvis-boot-r-on' : 'jarvis-boot-r-seg'}
          />
        )
      })}
      <circle className="jarvis-boot-r-ring" cx="0" cy="0" r="102" />
      <circle className="jarvis-boot-r-ring jarvis-boot-r-ring-in" cx="0" cy="0" r="66" />
      <path className="jarvis-boot-r-tri" d="M0,-52 L46,30 L-46,30 Z" />
      <path className="jarvis-boot-r-tri jarvis-boot-r-tri-in" d="M0,-30 L28,20 L-28,20 Z" />
      <path className="jarvis-boot-r-v" d="M-11,-4 L0,14 L11,-4" />
    </svg>
  )
}
