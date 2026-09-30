'use client'
import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'
import { Mic, MicOff, Volume2, Radio, Terminal, ChevronRight, Square } from 'lucide-react'
import { routeVoiceCommand } from '@/lib/voiceRouter'

// ── Voice correction map — fixes common speech-to-text errors ──
const VOICE_CORRECTIONS: [RegExp, string][] = [
  // Trading terms
  [/\btraits\b/gi,        'trades'],
  [/\btrait\b/gi,         'trade'],
  [/\btrading history\b/gi, 'trade history'],
  [/\bstocks\s+history\b/gi, 'trade history'],
  [/\bpaper\s+trading\s+history\b/gi, 'trade history'],
  [/\bprofit\s+and\s+loss\b/gi, 'P&L'],
  [/\bpee\s+and\s+el\b/gi, 'P&L'],
  [/\bpnl\b/gi,           'P&L'],
  [/\bportfolio\s+value\b/gi, 'portfolio'],
  [/\bopen\s+positions\b/gi, 'open positions'],
  [/\bwin\s+rate\b/gi,    'win rate'],
  [/\bstop\s+loss\b/gi,   'stop loss'],
  [/\bstop\s+lost\b/gi,   'stop loss'],
  [/\btarget\s+price\b/gi, 'target'],
  [/\bbullish\b/gi,       'bullish'],
  [/\bbearish\b/gi,       'bearish'],
  [/\bnifty\b/gi,         'NIFTY'],
  [/\bsensex\b/gi,        'SENSEX'],
  [/\breliance\b/gi,      'RELIANCE'],
  [/\binfosys\b/gi,       'INFOSYS'],
  [/\btata\s+motors\b/gi, 'TATAMOTORS'],
  [/\bhdfc\s+bank\b/gi,   'HDFCBANK'],
  [/\bicici\s+bank\b/gi,  'ICICIBANK'],
  [/\baxis\s+bank\b/gi,   'AXISBANK'],
  [/\bstate\s+bank\b/gi,  'SBIN'],
  // Common misheard words
  [/\bjarvis\b/gi,        'Jarvis'],
  [/\bshow\s+me\s+the\s+history\b/gi, 'show me the trade history'],
  [/\bhistory\s+of\s+traits\b/gi, 'history of trades'],
  [/\btoday'?s?\s+traits\b/gi, "today's trades"],
  [/\bmy\s+traits\b/gi,   'my trades'],
  // Auto-trade commands
  [/\bstart\s+auto\s+trait\b/gi,   'start auto trade'],
  [/\brun\s+auto\s+trait\b/gi,     'run auto trade'],
  [/\bstart\s+auto\s+trader\b/gi,  'start auto trade'],
  [/\brun\s+auto\s+trader\b/gi,    'run auto trade'],
  [/\bauto\s+trait\s+start\b/gi,   'auto trade start'],
  [/\bstop\s+auto\s+trait\b/gi,    'stop auto trade'],
  [/\bauto\s+test\b/gi,            'autotest'],
  [/\bauto\s+taste\b/gi,           'autotest'],
  [/\bauto\s+text\b/gi,            'autotest'],
]

function correctVoiceInput(text: string): string {
  let corrected = text
  for (const [pattern, replacement] of VOICE_CORRECTIONS) {
    corrected = corrected.replace(pattern, replacement)
  }
  return corrected
}

const BAR_COUNT = 64
const BARS = Array.from({ length: BAR_COUNT }, (_, i) => ({
  maxH:  Math.random() * 32 + 4,
  dur:   0.2 + Math.random() * 0.5,
  delay: i * 0.01,
}))

const SHORTCUTS = ['ANALYSE', 'NIFTY', 'PORTFOLIO', 'NEWS', 'HELP']

export function VoiceBar() {
  const { voiceActive, setVoiceActive, status, sendMessage, setStatus, messages } = useJarvisStore()
  const isListening = status === 'listening'
  const isSpeaking  = status === 'speaking'
  const isThinking  = status === 'thinking'
  const isExecuting = status === 'executing'

  const recognitionRef  = useRef<any>(null)
  const voiceActiveRef  = useRef(voiceActive)
  const statusRef       = useRef(status)
  const restartingRef   = useRef(false)   // guard against double-start races
  const [lastCmd, setLastCmd] = useState('')

  useEffect(() => { voiceActiveRef.current = voiceActive }, [voiceActive])
  useEffect(() => { statusRef.current = status }, [status])

  useEffect(() => {
    const userMsgs = messages.filter(m => m.role === 'user')
    if (userMsgs.length) setLastCmd(userMsgs[userMsgs.length - 1].content)
  }, [messages])

  // ── Restart mic after JARVIS finishes speaking ────────────────
  // When status returns to idle the mic may have died — kick it back
  useEffect(() => {
    if (status === 'idle' && voiceActiveRef.current) {
      restartMic()
    }
  }, [status]) // eslint-disable-line

  function restartMic() {
    if (!voiceActiveRef.current) return
    if (restartingRef.current) return
    restartingRef.current = true
    setTimeout(() => {
      restartingRef.current = false
      if (!voiceActiveRef.current) return
      // If recognition is already running, nothing to do
      try {
        if (recognitionRef.current) {
          recognitionRef.current.start()
        }
      } catch {
        // InvalidStateError = already running, ignore
      }
    }, 120)
  }

  useEffect(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) return

    if (voiceActive) {
      const rec = new SR()
      rec.continuous      = true
      rec.interimResults  = true
      rec.maxAlternatives = 3
      rec.lang            = 'en-US'

      rec.onstart = () => {
        // Mark listening whenever mic comes alive — even mid-speaking
        // (status will be overwritten by sendMessage → 'thinking' immediately)
        if (statusRef.current === 'idle') setStatus('listening')
      }

      rec.onresult = (e: any) => {
        const results = Array.from(e.results) as SpeechRecognitionResult[]

        // ── Barge-in detection on interim results ─────────────
        // As soon as the user starts speaking (even interim), cancel TTS
        const hasAnyResult = results.some(r => r[0].transcript.trim().length > 0)
        if (hasAnyResult && statusRef.current === 'speaking') {
          window.speechSynthesis?.cancel()
          // Don't set idle here — sendMessage will set 'thinking'
        }

        const finals = results.filter(r => r.isFinal)
        if (!finals.length) return

        const transcript = finals.map(r => {
          let best = r[0]
          for (let i = 1; i < r.length; i++) if (r[i].confidence > best.confidence) best = r[i]
          return best.transcript
        }).join(' ').trim()

        if (!transcript) return

        // Cancel TTS on final result too (belt-and-suspenders)
        if (statusRef.current === 'speaking') window.speechSynthesis?.cancel()

        // Route: UI commands open HUD panels directly, others go to AI backend
        const handled = routeVoiceCommand(correctVoiceInput(transcript))
        if (!handled) sendMessage(correctVoiceInput(transcript))
      }

      rec.onerror = (e: any) => {
        // 'no-speech' and 'aborted' are normal — just restart
        if (e.error === 'no-speech' || e.error === 'aborted') {
          restartMic()
          return
        }
        setVoiceActive(false)
        setStatus('idle')
      }

      rec.onend = () => {
        // Always restart — regardless of current status
        // This is the key fix: mic must stay alive during speaking/thinking
        if (voiceActiveRef.current) {
          restartMic()
        }
      }

      rec.start()
      recognitionRef.current = rec
    } else {
      if (recognitionRef.current) {
        recognitionRef.current.onend = null
        recognitionRef.current.abort()
        recognitionRef.current = null
      }
      setStatus('idle')
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.onend = null
        recognitionRef.current.abort()
        recognitionRef.current = null
      }
    }
  }, [voiceActive]) // eslint-disable-line

  const stopSpeaking = () => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel()
      setTimeout(() => setStatus('idle'), 80)
    }
  }

  const toggle = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) { alert('Use Chrome or Edge for voice support.'); return }
    if (!voiceActive && window.speechSynthesis) window.speechSynthesis.cancel()
    setVoiceActive(!voiceActive)
  }

  // New palette bar colors
  const barColor =
    isListening ? '#00FF99' :
    isSpeaking  ? '#33F2FF' :
    isThinking  ? '#009DFF' :
    isExecuting ? '#FFC857' : '#1a3a5c'

  const barGlow =
    isListening ? 'rgba(0,255,153,0.4)' :
    isSpeaking  ? 'rgba(51,242,255,0.4)' :
    isThinking  ? 'rgba(0,157,255,0.4)' : 'transparent'

  const active = isListening || isSpeaking || isThinking || isExecuting

  return (
    <footer
      className="relative shrink-0 z-40"
      style={{
        background: 'linear-gradient(180deg, rgba(5,19,38,0.97) 0%, rgba(2,8,19,0.99) 100%)',
        borderTop: '1px solid rgba(0,217,255,0.1)',
        boxShadow: '0 -4px 32px rgba(0,0,0,0.6)',
      }}
    >
      {/* Top shimmer */}
      <div className="absolute top-0 left-0 right-0 h-px border-shimmer" />

      <div className="flex items-center h-14 px-4 gap-3">

        {/* Mic toggle */}
        <motion.button
          onClick={toggle}
          className="flex items-center gap-2 px-3 py-2 relative overflow-hidden shrink-0 rounded-sm"
          style={{
            background: isListening ? 'rgba(0,255,153,0.08)' : 'rgba(0,217,255,0.04)',
            border: `1px solid ${isListening ? 'rgba(0,255,153,0.42)' : 'rgba(0,217,255,0.12)'}`,
            boxShadow: isListening ? '0 0 18px rgba(0,255,153,0.22)' : 'none',
          }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.96 }}
        >
          <AnimatePresence mode="wait">
            {isListening ? (
              <motion.div key="on" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                <Mic size={12} style={{ color: '#00FF99', filter: 'drop-shadow(0 0 5px #00FF99)' }} />
              </motion.div>
            ) : (
              <motion.div key="off" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                <MicOff size={12} style={{ color: '#2A5A6A' }} />
              </motion.div>
            )}
          </AnimatePresence>
          <span className="text-[8px] font-bold tracking-[0.15em]" style={{ color: isListening ? '#00FF99' : '#2A5A6A', fontFamily: 'Orbitron, sans-serif' }}>
            {isListening ? 'LIVE' : 'MIC OFF'}
          </span>
          {isListening && (
            <motion.div
              className="absolute inset-0"
              animate={{ opacity: [0.04, 0.14, 0.04] }}
              transition={{ duration: 1.4, repeat: Infinity }}
              style={{ background: 'linear-gradient(90deg, rgba(0,255,153,0.15), transparent)' }}
            />
          )}
        </motion.button>

        {/* Waveform visualizer */}
        <div className="flex items-center gap-[1.5px] h-10 relative flex-1 justify-center overflow-hidden">
          {active && (
            <div
              className="absolute inset-0 pointer-events-none"
              style={{ background: `radial-gradient(ellipse 60% 100% at 50% 50%, ${barGlow} 0%, transparent 70%)`, opacity: 0.3 }}
            />
          )}
          {BARS.map((bar, i) => (
            <motion.div
              key={i}
              className="rounded-full relative z-10 origin-center"
              style={{
                width: 2,
                background: active
                  ? `linear-gradient(180deg, ${barColor}, ${barColor}88)`
                  : '#1a3a5c',
                boxShadow: active ? `0 0 3px ${barColor}` : 'none',
              }}
              animate={{
                height: active ? [3, bar.maxH * (0.4 + 0.6 * Math.random()), 3] : 3,
                opacity: active ? 1 : 0.2,
              }}
              transition={{ duration: bar.dur, repeat: Infinity, delay: bar.delay, ease: 'easeInOut' }}
            />
          ))}
        </div>

        {/* Last command */}
        <div className="flex flex-col justify-center shrink-0 max-w-[180px]">
          {lastCmd ? (
            <>
              <div className="flex items-center gap-1 mb-0.5">
                <Terminal size={8} style={{ color: '#2A5A6A' }} />
                <span className="text-[7px] tracking-[0.18em]" style={{ color: '#2A5A6A', fontFamily: 'Rajdhani, sans-serif' }}>LAST INPUT</span>
              </div>
              <div className="flex items-center gap-1">
                <ChevronRight size={8} style={{ color: '#00D9FF' }} />
                <span className="text-[9px] truncate" style={{ color: '#80C8FF', fontFamily: 'IBM Plex Mono, monospace' }}>{lastCmd}</span>
              </div>
            </>
          ) : (
            <span className="text-[8px] tracking-widest" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>AWAITING INPUT...</span>
          )}
        </div>

        {/* Shortcut buttons */}
        <div className="flex items-center gap-1.5 shrink-0">
          {SHORTCUTS.map(s => (
            <motion.button
              key={s}
              onClick={() => {
                const handled = routeVoiceCommand(s.toLowerCase())
                if (!handled) sendMessage(s.toLowerCase())
              }}
              className="px-2 py-1 text-[7px] font-bold tracking-[0.12em] rounded-sm btn-neon"
              style={{ fontFamily: 'Orbitron, sans-serif' }}
              whileTap={{ scale: 0.93 }}
            >
              {s}
            </motion.button>
          ))}
        </div>

        {/* Speaker / stop */}
        <div className="flex items-center gap-2 shrink-0">
          <motion.button
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm"
            style={{
              background: isSpeaking ? 'rgba(51,242,255,0.08)' : 'rgba(0,217,255,0.03)',
              border: `1px solid ${isSpeaking ? 'rgba(51,242,255,0.38)' : 'rgba(0,217,255,0.08)'}`,
              cursor: isSpeaking ? 'pointer' : 'default',
            }}
            onClick={isSpeaking ? stopSpeaking : undefined}
            whileHover={isSpeaking ? { scale: 1.03 } : {}}
          >
            {isSpeaking ? (
              <Square size={10} style={{ color: '#FF5A7A' }} />
            ) : (
              <Volume2 size={10} style={{ color: '#2A5A6A' }} />
            )}
            <span className="text-[8px] font-bold tracking-[0.12em]" style={{ color: isSpeaking ? '#33F2FF' : '#2A5A6A', fontFamily: 'Orbitron, sans-serif' }}>
              {isSpeaking ? 'STOP' : 'READY'}
            </span>
          </motion.button>

          <div className="flex items-center gap-1">
            <Radio size={9} style={{ color: '#1a3a5c' }} />
            <span className="text-[7px] tracking-[0.14em]" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>VOICE ENGINE</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
