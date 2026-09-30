'use client'
import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvisStore, JARVIS_PHASE_COLOR } from '@/store/jarvisStore'
import { cancelSpeech } from '@/store/jarvisStore'
import { Mic, MicOff, Volume2, Radio, Terminal, ChevronRight, Square, Zap } from 'lucide-react'
import { routeVoiceCommand } from '@/lib/voiceRouter'
import * as sfx from '@/lib/sfx'
import * as music from '@/lib/music'
import { makeAssembler, isEcho } from '@/lib/assembler'
import { makeWakeWordDetector } from '@/lib/wakeWord'
import { startSessionClock } from '@/lib/marketSession'
import { classifyVoiceIntent, updateConversationContext } from '@/lib/intentRouter'
import { executeToolPlan } from '@/lib/capabilityTools'
import type { Vad } from '@/lib/vad'

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
  const {
    voiceActive, setVoiceActive, status, sendMessage, setStatus, messages,
    phase, setPhase, lastJarvisUtterance, setLastJarvisUtterance,
    marketSession, setMarketSession, setVoiceIntent,
  } = useJarvisStore()

  const isListening = status === 'listening'
  const isSpeaking  = status === 'speaking'
  const isThinking  = status === 'thinking'
  const isExecuting = status === 'executing'
  const isDormant   = phase === 'dormant'
  const isTooling   = phase === 'tooling'

  // ── Session clock ─────────────────────────────────────────────────────
  useEffect(() => {
    return startSessionClock(setMarketSession)
  }, []) // eslint-disable-line

  const recognitionRef         = useRef<any>(null)
  const voiceActiveRef         = useRef(voiceActive)
  const statusRef              = useRef(status)
  const phaseRef               = useRef(phase)
  const restartingRef          = useRef(false)
  const vadRef                 = useRef<Vad | null>(null)
  const wakeWordRef            = useRef<ReturnType<typeof makeWakeWordDetector> | null>(null)
  const lastJarvisUtteranceRef = useRef(lastJarvisUtterance)
  const [lastCmd, setLastCmd]  = useState('')

  // Assembler: converts segments → complete turns, handles echo detection
  const assemblerRef = useRef(makeAssembler({
    onTurn: (transcript) => {
      if (!transcript.trim()) return
      if (isEcho(transcript, lastJarvisUtteranceRef.current)) return
      const corrected = correctVoiceInput(transcript)
      const handled = routeVoiceCommand(corrected)
      if (!handled) {
        const store = useJarvisStore.getState()
        const intent = classifyVoiceIntent(corrected, store.marketSession)
        store.setVoiceIntent(intent)
        // For non-general queries, run tool plan first then send enriched message
        if (intent.intent !== 'GENERAL_AI' && intent.intent !== 'DATE_TIME' && intent.toolPlan.length > 0 && !intent.toolPlan.every(t => t === 'GeneralAITool')) {
          sfx.play('tool')
          music.working(true)
          store.setPhase('tooling')
          const params: Record<string, unknown> = { query: corrected }
          if (intent.symbols.length > 0) params.symbol = intent.symbols[0]
          executeToolPlan(intent.toolPlan, params).then((results) => {
            sfx.play('done')
            music.working(false)
            store.setPhase('thinking')
            // Build tool context for backend — NEVER shown to user directly
            // Sent as a separate field, not appended to the user message
            const toolSummaries = results
              .filter(r => r.status !== 'error' || r.summary)
              .map(r => r.summary)
            const disclaimers = results
              .filter(r => r.disclaimer)
              .map(r => r.disclaimer as string)
            // Update conversation context with what we found
            updateConversationContext(intent.intent as any, intent.symbols, corrected, undefined, toolSummaries)
            // Send the original clean user message + tool context as metadata
            // The backend receives tool_context as a separate field, not in the message
            store.sendMessage(corrected, {
              toolContext: toolSummaries.join(' | '),
              disclaimers,
              intent: intent.intent,
              symbols: intent.symbols,
            })
          }).catch(() => {
            sfx.play('error')
            music.working(false)
            store.setPhase('thinking')
            updateConversationContext(intent.intent as any, intent.symbols, corrected)
            store.sendMessage(corrected)
          })
        } else {
          updateConversationContext(intent.intent as any, intent.symbols, corrected)
          store.sendMessage(corrected)
        }
      }
    },
    onInterim: (partial) => setLastCmd(partial),
  }))

  useEffect(() => { voiceActiveRef.current = voiceActive }, [voiceActive])
  useEffect(() => { statusRef.current = status }, [status])
  useEffect(() => { phaseRef.current = phase }, [phase])
  useEffect(() => { lastJarvisUtteranceRef.current = lastJarvisUtterance }, [lastJarvisUtterance])

  useEffect(() => {
    const userMsgs = messages.filter(m => m.role === 'user')
    if (userMsgs.length) setLastCmd(userMsgs[userMsgs.length - 1].content)
  }, [messages])

  // ── Duck sfx/music while JARVIS speaks, guard VAD ────────────────────
  useEffect(() => {
    sfx.duck(status === 'speaking')
    music.duck(status === 'speaking')
    vadRef.current?.setGuard(status === 'speaking')
  }, [status])

  // ── Restart mic after JARVIS finishes speaking ────────────────────────
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
      try {
        if (recognitionRef.current) recognitionRef.current.start()
      } catch {
        // InvalidStateError = already running, ignore
      }
    }, 120)
  }

  // ── Wake word detector: runs when voiceActive + phase === dormant ─────
  useEffect(() => {
    if (!voiceActive) {
      wakeWordRef.current?.stop()
      wakeWordRef.current = null
      return
    }

    if (phase === 'dormant') {
      // Stop command recognition while dormant
      if (recognitionRef.current) {
        recognitionRef.current.onend = null
        recognitionRef.current.abort()
        recognitionRef.current = null
      }

      if (!wakeWordRef.current) {
        wakeWordRef.current = makeWakeWordDetector(
          {
            onWake: (hint) => {
              sfx.play('wake')
              setPhase('waking')
              setTimeout(() => {
                sfx.play('listen')
                setPhase('listening')
                setStatus('listening')
                if (hint.trim().length > 3) {
                  const corrected = correctVoiceInput(hint)
                  const handled = routeVoiceCommand(corrected)
                  if (!handled) sendMessage(corrected)
                }
              }, 600)
            },
            onUnavailable: () => {
              // SpeechRecognition unavailable — skip dormant, go straight to listening
              setPhase('listening')
            },
          },
          { phrase: 'hey jarvis' }
        )
        wakeWordRef.current.start()
      }
    } else {
      // Not dormant — stop wake word, command recognition takes over
      wakeWordRef.current?.stop()
      wakeWordRef.current = null
    }
  }, [voiceActive, phase]) // eslint-disable-line

  // ── VAD: runs when voiceActive + phase is active (not dormant/offline/boot) ──
  useEffect(() => {
    const shouldRunVad =
      voiceActive &&
      phase !== 'dormant' &&
      phase !== 'offline' &&
      phase !== 'boot'

    if (!shouldRunVad) {
      vadRef.current?.stop()
      vadRef.current = null
      return
    }

    import('@/lib/vad').then(({ startVad }) => {
      startVad({
        onStart: () => {
          // Barge-in: cancel TTS immediately when user starts speaking
          if (statusRef.current === 'speaking') {
            cancelSpeech()
          }
          if (statusRef.current === 'idle') setStatus('listening')
        },
        onEnd: (_blob, _ms) => {
          // Blob available for future Whisper/backend transcription
          // Currently SpeechRecognition handles transcription
        },
        onLevel: (_level) => {
          // Future: drive waveform bar heights directly from VAD energy
        },
        onError: (msg) => {
          console.warn('[JARVIS VAD]', msg)
        },
      }).then((vad) => {
        vadRef.current = vad
        vad.setGuard(statusRef.current === 'speaking')
      })
    }).catch(() => {})

    return () => {
      vadRef.current?.stop()
      vadRef.current = null
    }
  }, [voiceActive, phase]) // eslint-disable-line

  // ── SpeechRecognition: command transcription (not dormant) ────────────
  useEffect(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) return

    const shouldRun =
      voiceActive &&
      phase !== 'dormant' &&
      phase !== 'offline' &&
      phase !== 'boot'

    if (shouldRun) {
      const rec = new SR()
      rec.continuous      = true
      rec.interimResults  = true
      rec.maxAlternatives = 3
      rec.lang            = 'en-US'

      rec.onstart = () => {
        if (statusRef.current === 'idle') setStatus('listening')
      }

      rec.onresult = (e: any) => {
        const results = Array.from(e.results) as SpeechRecognitionResult[]

        // Barge-in: cancel TTS on any speech energy
        const hasAnyResult = results.some(r => r[0].transcript.trim().length > 0)
        if (hasAnyResult && statusRef.current === 'speaking') {
          window.speechSynthesis?.cancel()
        }

        // Feed interim to assembler for live display
        const interims = results.filter(r => !r.isFinal)
        if (interims.length) {
          const interimText = interims.map(r => r[0].transcript).join(' ').trim()
          if (interimText) assemblerRef.current.addSegment(interimText, false)
        }

        const finals = results.filter(r => r.isFinal)
        if (!finals.length) return

        const transcript = finals.map(r => {
          let best = r[0]
          for (let i = 1; i < r.length; i++) if (r[i].confidence > best.confidence) best = r[i]
          return best.transcript
        }).join(' ').trim()

        if (!transcript) return

        if (statusRef.current === 'speaking') window.speechSynthesis?.cancel()

        // Feed final segment to assembler — assembler decides when to flush as a turn
        assemblerRef.current.addSegment(correctVoiceInput(transcript), true)
      }

      rec.onerror = (e: any) => {
        if (e.error === 'no-speech' || e.error === 'aborted') {
          restartMic()
          return
        }
        setVoiceActive(false)
        setStatus('idle')
        setPhase('offline')
      }

      rec.onend = () => {
        if (voiceActiveRef.current && phaseRef.current !== 'dormant') {
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
      if (!voiceActive) setStatus('idle')
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.onend = null
        recognitionRef.current.abort()
        recognitionRef.current = null
      }
    }
  }, [voiceActive, phase]) // eslint-disable-line

  const stopSpeaking = () => {
    cancelSpeech()
    setTimeout(() => {
      setStatus('idle')
      setPhase('dormant')
    }, 80)
  }

  const toggle = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) { alert('Use Chrome or Edge for voice support.'); return }
    if (!voiceActive && window.speechSynthesis) window.speechSynthesis.cancel()
    const nextActive = !voiceActive
    setVoiceActive(nextActive)
    if (nextActive) {
      setPhase('dormant')
    } else {
      setPhase('offline')
      assemblerRef.current.reset()
    }
  }

  // ── Visual state ──────────────────────────────────────────────────────
  const barColor =
    isListening ? '#00FF99' :
    isSpeaking  ? '#33F2FF' :
    isThinking  ? '#009DFF' :
    isExecuting ? '#FFC857' :
    isDormant   ? '#12908f' : '#1a3a5c'

  const barGlow =
    isListening ? 'rgba(0,255,153,0.4)' :
    isSpeaking  ? 'rgba(51,242,255,0.4)' :
    isThinking  ? 'rgba(0,157,255,0.4)' :
    isDormant   ? 'rgba(18,144,143,0.2)' : 'transparent'

  const active = isListening || isSpeaking || isThinking || isExecuting || isDormant

  const phaseLabel: Record<string, string> = {
    offline: 'OFFLINE', boot: 'BOOTING', dormant: 'DORMANT',
    waking: 'WAKING', listening: 'LIVE', thinking: 'THINKING',
    tooling: 'EXECUTING', speaking: 'SPEAKING',
  }

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
            background: isListening ? 'rgba(0,255,153,0.08)' : isDormant ? 'rgba(18,144,143,0.06)' : 'rgba(0,217,255,0.04)',
            border: `1px solid ${isListening ? 'rgba(0,255,153,0.42)' : isDormant ? 'rgba(18,144,143,0.3)' : 'rgba(0,217,255,0.12)'}`,
            boxShadow: isListening ? '0 0 18px rgba(0,255,153,0.22)' : isDormant ? '0 0 8px rgba(18,144,143,0.15)' : 'none',
          }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.96 }}
        >
          <AnimatePresence mode="wait">
            {isListening ? (
              <motion.div key="on" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                <Mic size={12} style={{ color: '#00FF99', filter: 'drop-shadow(0 0 5px #00FF99)' }} />
              </motion.div>
            ) : isDormant ? (
              <motion.div key="dormant" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                <Mic size={12} style={{ color: '#12908f', opacity: 0.7 }} />
              </motion.div>
            ) : (
              <motion.div key="off" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                <MicOff size={12} style={{ color: '#2A5A6A' }} />
              </motion.div>
            )}
          </AnimatePresence>
          <span className="text-[8px] font-bold tracking-[0.15em]" style={{
            color: isListening ? '#00FF99' : isDormant ? '#12908f' : '#2A5A6A',
            fontFamily: 'Orbitron, sans-serif',
          }}>
            {isListening ? 'LIVE' : isDormant ? 'DORMANT' : 'MIC OFF'}
          </span>
          {isListening && (
            <motion.div
              className="absolute inset-0"
              animate={{ opacity: [0.04, 0.14, 0.04] }}
              transition={{ duration: 1.4, repeat: Infinity }}
              style={{ background: 'linear-gradient(90deg, rgba(0,255,153,0.15), transparent)' }}
            />
          )}
          {isDormant && (
            <motion.div
              className="absolute inset-0"
              animate={{ opacity: [0.02, 0.06, 0.02] }}
              transition={{ duration: 2.5, repeat: Infinity }}
              style={{ background: 'linear-gradient(90deg, rgba(18,144,143,0.1), transparent)' }}
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

        {/* Last command / interim transcript */}
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
            <span className="text-[8px] tracking-widest" style={{ color: '#1a3a5c', fontFamily: 'Rajdhani, sans-serif' }}>
              {isDormant ? 'SAY "HEY JARVIS"...' : 'AWAITING INPUT...'}
            </span>
          )}
        </div>

        {/* Shortcut buttons */}
        <div className="flex items-center gap-1.5 shrink-0">
          {SHORTCUTS.map(s => (
            <motion.button
              key={s}
              onClick={() => {
                const handled = routeVoiceCommand(s.toLowerCase())
                if (!handled) {
                  const store = useJarvisStore.getState()
                  const intent = classifyVoiceIntent(s.toLowerCase(), store.marketSession)
                  updateConversationContext(intent.intent as any, intent.symbols, s.toLowerCase())
                  store.sendMessage(s.toLowerCase())
                }
              }}
              className="px-2 py-1 text-[7px] font-bold tracking-[0.12em] rounded-sm btn-neon"
              style={{ fontFamily: 'Orbitron, sans-serif' }}
              whileTap={{ scale: 0.93 }}
            >
              {s}
            </motion.button>
          ))}
        </div>

        {/* Phase indicator — shows current JARVIS phase */}
        <div className="flex items-center gap-1 shrink-0">
          <Zap size={8} style={{
            color: isTooling ? '#FFC857' : '#1a3a5c',
            opacity: isTooling ? 1 : 0.3,
          }} />
          <span className="text-[7px] tracking-[0.14em]" style={{
            color: isDormant ? '#12908f' : isTooling ? '#FFC857' : isThinking ? '#009DFF' : '#1a3a5c',
            fontFamily: 'Rajdhani, sans-serif',
          }}>{phaseLabel[phase] ?? 'READY'}</span>
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
