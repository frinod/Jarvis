'use client'
import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { useJarvisStore } from '@/store/jarvisStore'

// ── Ring definitions ──────────────────────────────────────────
const RINGS = [
  { r: 36,  w: 0.5, speed: 14, dir:  1, color: 'rgba(0,217,255,0.80)', dash: [2,3],   ticks: 8  },
  { r: 50,  w: 1.0, speed: 22, dir: -1, color: 'rgba(0,217,255,0.60)', dash: [4,4],   ticks: 12 },
  { r: 64,  w: 0.5, speed: 32, dir:  1, color: 'rgba(51,242,255,0.45)', dash: [1,6],  ticks: 16 },
  { r: 78,  w: 1.2, speed: 19, dir: -1, color: 'rgba(0,217,255,0.40)', dash: [6,3],   ticks: 12 },
  { r: 92,  w: 0.4, speed: 42, dir:  1, color: 'rgba(0,157,255,0.30)', dash: [2,8],   ticks: 24 },
  { r: 106, w: 0.8, speed: 27, dir: -1, color: 'rgba(0,217,255,0.28)', dash: [8,4],   ticks: 16 },
  { r: 118, w: 0.5, speed: 52, dir:  1, color: 'rgba(51,242,255,0.22)', dash: [3,10], ticks: 8  },
  { r: 130, w: 1.0, speed: 24, dir: -1, color: 'rgba(0,255,153,0.18)', dash: [10,5],  ticks: 12 },
  { r: 142, w: 0.4, speed: 62, dir:  1, color: 'rgba(0,217,255,0.14)', dash: [2,12],  ticks: 32 },
  { r: 154, w: 0.7, speed: 37, dir: -1, color: 'rgba(0,217,255,0.10)', dash: [6,8],   ticks: 16 },
  { r: 164, w: 0.3, speed: 72, dir:  1, color: 'rgba(51,242,255,0.08)', dash: [1,14], ticks: 8  },
  { r: 174, w: 0.5, speed: 47, dir: -1, color: 'rgba(0,217,255,0.05)', dash: [4,16],  ticks: 24 },
]

// ── Orbit satellites ──────────────────────────────────────────
const SATELLITES = [
  { r: 64,  size: 3.5, speed: 7,  color: '#00FF99', offset: 0   },
  { r: 92,  size: 2.5, speed: 11, color: '#00D9FF', offset: 90  },
  { r: 118, size: 3.0, speed: 6,  color: '#009DFF', offset: 180 },
  { r: 142, size: 2.0, speed: 14, color: '#FFC857', offset: 270 },
  { r: 164, size: 2.5, speed: 9,  color: '#00D9FF', offset: 45  },
  { r: 78,  size: 2.0, speed: 16, color: '#00FF99', offset: 135 },
]

// ── Floating telemetry labels ─────────────────────────────────
const TELEM_LABELS = [
  { label: 'MEM',  angle: 0,    dist: 195, color: '#00D9FF' },
  { label: 'CPU',  angle: 51,   dist: 195, color: '#33F2FF' },
  { label: 'NET',  angle: 103,  dist: 195, color: '#009DFF' },
  { label: 'GPU',  angle: 154,  dist: 195, color: '#00FF99' },
  { label: 'AI',   angle: 205,  dist: 195, color: '#FFC857' },
  { label: 'SYS',  angle: 257,  dist: 195, color: '#00D9FF' },
  { label: 'DATA', angle: 308,  dist: 195, color: '#33F2FF' },
]

// ── State colors (new palette) ────────────────────────────────
const STATE_COLORS: Record<string, { core: string; glow: string; ring: string; particle: string; arc: string }> = {
  idle:      { core: '#00D9FF', glow: 'rgba(0,217,255,0.30)',   ring: 'rgba(0,217,255,0.50)',   particle: '#00D9FF', arc: '#009DFF' },
  listening: { core: '#00FF99', glow: 'rgba(0,255,153,0.40)',   ring: 'rgba(0,255,153,0.65)',   particle: '#00FF99', arc: '#00FF99' },
  thinking:  { core: '#009DFF', glow: 'rgba(0,157,255,0.45)',   ring: 'rgba(0,157,255,0.70)',   particle: '#33F2FF', arc: '#009DFF' },
  speaking:  { core: '#33F2FF', glow: 'rgba(51,242,255,0.50)',  ring: 'rgba(51,242,255,0.75)',  particle: '#33F2FF', arc: '#33F2FF' },
  executing: { core: '#FFC857', glow: 'rgba(255,200,87,0.45)',  ring: 'rgba(255,200,87,0.65)',  particle: '#FFC857', arc: '#FFC857' },
}

const STATE_LABELS: Record<string, string> = {
  idle: 'STANDBY', listening: 'LISTENING', thinking: 'PROCESSING',
  speaking: 'TRANSMITTING', executing: 'EXECUTING',
}

export function HolographicCore() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const status = useJarvisStore(s => s.status)
  const statusRef = useRef(status)
  useEffect(() => { statusRef.current = status }, [status])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const SIZE = 400
    canvas.width = SIZE; canvas.height = SIZE
    const CX = SIZE / 2, CY = SIZE / 2
    let raf: number, t = 0

    // ── Layer 2: Particle cloud (inward flowing) ──────────────
    type Particle = { angle: number; dist: number; speed: number; size: number; alpha: number }
    const particles: Particle[] = Array.from({ length: 120 }, () => ({
      angle: Math.random() * Math.PI * 2,
      dist:  170 + Math.random() * 20,
      speed: 0.25 + Math.random() * 0.85,
      size:  Math.random() * 1.6 + 0.3,
      alpha: Math.random() * 0.65 + 0.2,
    }))

    // ── Neural network nodes ──────────────────────────────────
    type Node = { x: number; y: number; vx: number; vy: number; r: number }
    const nodes: Node[] = Array.from({ length: 22 }, () => ({
      x:  CX + (Math.random() - 0.5) * 130,
      y:  CY + (Math.random() - 0.5) * 130,
      vx: (Math.random() - 0.5) * 0.28,
      vy: (Math.random() - 0.5) * 0.28,
      r:  Math.random() * 1.4 + 0.5,
    }))

    // ── Telemetry values (simulated) ──────────────────────────
    const telemVals = TELEM_LABELS.map(() => Math.floor(Math.random() * 80 + 15))

    const draw = () => {
      t += 0.016
      ctx.clearRect(0, 0, SIZE, SIZE)
      const sc = STATE_COLORS[statusRef.current] || STATE_COLORS.idle
      const pulse = 0.7 + 0.3 * Math.sin(t * 2.5)
      const fastPulse = statusRef.current === 'thinking' ? 2.4 : statusRef.current === 'speaking' ? 3.0 : statusRef.current === 'executing' ? 1.9 : 1

      // ── Layer 1: Deep background plasma bloom ─────────────
      const bgGrad = ctx.createRadialGradient(CX, CY, 0, CX, CY, 190)
      bgGrad.addColorStop(0,   `rgba(0,120,200,0.07)`)
      bgGrad.addColorStop(0.4, `rgba(0,80,150,0.04)`)
      bgGrad.addColorStop(1,   'transparent')
      ctx.beginPath(); ctx.arc(CX, CY, 190, 0, Math.PI * 2)
      ctx.fillStyle = bgGrad; ctx.fill()

      // Outer energy waves
      for (let i = 4; i >= 1; i--) {
        const waveR = 52 * i + 10 * Math.sin(t * 1.2 + i)
        const alpha = (0.055 / i) * pulse
        const gr = ctx.createRadialGradient(CX, CY, waveR * 0.6, CX, CY, waveR)
        gr.addColorStop(0, `rgba(0,217,255,${alpha})`)
        gr.addColorStop(1, 'transparent')
        ctx.beginPath(); ctx.arc(CX, CY, waveR, 0, Math.PI * 2)
        ctx.fillStyle = gr; ctx.fill()
      }

      // ── Layer 3: 12 rotating rings ────────────────────────
      RINGS.forEach(ring => {
        ctx.save()
        ctx.translate(CX, CY)
        ctx.rotate(t * (ring.dir / ring.speed))
        ctx.beginPath()
        ctx.arc(0, 0, ring.r, 0, Math.PI * 2)
        ctx.strokeStyle = ring.color
        ctx.lineWidth = ring.w
        ctx.setLineDash(ring.dash)
        ctx.shadowColor = ring.color
        ctx.shadowBlur = 4
        ctx.stroke()
        ctx.setLineDash([])
        ctx.shadowBlur = 0

        // Calibration ticks
        for (let i = 0; i < ring.ticks; i++) {
          const a = (i / ring.ticks) * Math.PI * 2
          const isLong = i % (ring.ticks / 4) === 0
          const inner = ring.r - (isLong ? 5 : 2.5)
          const outer = ring.r + (isLong ? 5 : 2.5)
          ctx.beginPath()
          ctx.moveTo(Math.cos(a) * inner, Math.sin(a) * inner)
          ctx.lineTo(Math.cos(a) * outer, Math.sin(a) * outer)
          ctx.strokeStyle = ring.color
          ctx.lineWidth = isLong ? 0.8 : 0.4
          ctx.stroke()
        }

        // Degree labels on outer ring
        if (ring.r > 128 && ring.r < 158) {
          for (let i = 0; i < 4; i++) {
            const a = (i / 4) * Math.PI * 2
            const lx = Math.cos(a) * (ring.r + 10)
            const ly = Math.sin(a) * (ring.r + 10)
            ctx.save()
            ctx.translate(lx, ly)
            ctx.rotate(-t * (ring.dir / ring.speed))
            ctx.fillStyle = ring.color
            ctx.font = '5px IBM Plex Mono'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.globalAlpha = 0.5
            ctx.fillText(`${(i * 90).toString().padStart(3, '0')}°`, 0, 0)
            ctx.globalAlpha = 1
            ctx.restore()
          }
        }
        ctx.restore()
      })

      // ── Layer 6: Orbit satellites with trails ─────────────
      SATELLITES.forEach(sat => {
        const angle = t * (360 / sat.speed) * (Math.PI / 180) + (sat.offset * Math.PI / 180)
        const x = CX + Math.cos(angle) * sat.r
        const y = CY + Math.sin(angle) * sat.r

        for (let i = 1; i <= 10; i++) {
          const ta = angle - i * 0.055
          const tx = CX + Math.cos(ta) * sat.r
          const ty = CY + Math.sin(ta) * sat.r
          ctx.beginPath()
          ctx.arc(tx, ty, sat.size * (1 - i * 0.09), 0, Math.PI * 2)
          ctx.fillStyle = sat.color
          ctx.globalAlpha = Math.max(0, 0.32 - i * 0.032)
          ctx.fill()
          ctx.globalAlpha = 1
        }

        ctx.beginPath()
        ctx.arc(x, y, sat.size, 0, Math.PI * 2)
        ctx.fillStyle = sat.color
        ctx.shadowColor = sat.color
        ctx.shadowBlur = 12
        ctx.fill()
        ctx.shadowBlur = 0
      })

      // ── Neural network (thinking / executing) ─────────────
      if (statusRef.current === 'thinking' || statusRef.current === 'executing') {
        nodes.forEach(n => {
          n.x += n.vx; n.y += n.vy
          const dx = n.x - CX, dy = n.y - CY
          if (Math.sqrt(dx * dx + dy * dy) > 85) { n.vx *= -1; n.vy *= -1 }
        })
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const dx = nodes[i].x - nodes[j].x
            const dy = nodes[i].y - nodes[j].y
            const d = Math.sqrt(dx * dx + dy * dy)
            if (d < 58) {
              ctx.beginPath()
              ctx.moveTo(nodes[i].x, nodes[i].y)
              ctx.lineTo(nodes[j].x, nodes[j].y)
              ctx.strokeStyle = sc.arc
              ctx.lineWidth = 0.4
              ctx.globalAlpha = (1 - d / 58) * 0.55
              ctx.stroke()
              ctx.globalAlpha = 1
            }
          }
          ctx.beginPath()
          ctx.arc(nodes[i].x, nodes[i].y, nodes[i].r, 0, Math.PI * 2)
          ctx.fillStyle = sc.arc
          ctx.globalAlpha = 0.65
          ctx.fill()
          ctx.globalAlpha = 1
        }
      }

      // ── Layer 2: Inward particles ─────────────────────────
      particles.forEach(p => {
        p.dist -= p.speed * fastPulse * 0.5
        if (p.dist < 24) {
          p.dist  = 170 + Math.random() * 20
          p.angle = Math.random() * Math.PI * 2
          p.alpha = Math.random() * 0.65 + 0.2
        }
        const x = CX + Math.cos(p.angle) * p.dist
        const y = CY + Math.sin(p.angle) * p.dist
        ctx.beginPath()
        ctx.arc(x, y, p.size, 0, Math.PI * 2)
        ctx.fillStyle = sc.particle
        ctx.globalAlpha = p.alpha * (1 - p.dist / 195) * 1.5
        ctx.fill()
        ctx.globalAlpha = 1
      })

      // ── Layer 4: Radar sweep ──────────────────────────────
      ctx.save()
      ctx.translate(CX, CY)
      ctx.rotate(t * (statusRef.current === 'thinking' ? 1.8 : 0.75))
      const sweepGrad = ctx.createLinearGradient(0, 0, 65, 0)
      sweepGrad.addColorStop(0, 'rgba(0,217,255,0.0)')
      sweepGrad.addColorStop(1, `rgba(0,217,255,${0.14 + 0.08 * pulse})`)
      ctx.beginPath()
      ctx.moveTo(0, 0)
      ctx.arc(0, 0, 178, -0.5, 0.5)
      ctx.closePath()
      ctx.fillStyle = sweepGrad
      ctx.fill()
      ctx.restore()

      // ── Electric arcs (speaking / executing) ─────────────
      if (statusRef.current === 'speaking' || statusRef.current === 'executing') {
        for (let a = 0; a < 4; a++) {
          const arcAngle = t * 3.2 + (a * Math.PI * 2) / 4
          ctx.save()
          ctx.translate(CX, CY)
          ctx.rotate(arcAngle)
          ctx.beginPath()
          ctx.moveTo(30, 0)
          for (let s = 0; s < 9; s++) {
            ctx.lineTo(30 + (s / 8) * 22, (Math.random() - 0.5) * 9)
          }
          ctx.strokeStyle = sc.arc
          ctx.lineWidth = 0.9
          ctx.globalAlpha = 0.5 + 0.3 * Math.sin(t * 9 + a)
          ctx.shadowColor = sc.arc
          ctx.shadowBlur = 7
          ctx.stroke()
          ctx.shadowBlur = 0
          ctx.globalAlpha = 1
          ctx.restore()
        }
      }

      // ── Layer 1: Core plasma sphere ───────────────────────
      const coreR = 28 + 4 * pulse + (statusRef.current === 'speaking' ? 5 * Math.sin(t * 6) : 0)
      const coreGrad = ctx.createRadialGradient(CX - 8, CY - 8, 1, CX, CY, coreR)
      coreGrad.addColorStop(0,    '#ffffff')
      coreGrad.addColorStop(0.12, sc.core)
      coreGrad.addColorStop(0.5,  sc.core + 'bb')
      coreGrad.addColorStop(1,    'transparent')
      ctx.beginPath()
      ctx.arc(CX, CY, coreR, 0, Math.PI * 2)
      ctx.fillStyle = coreGrad
      ctx.shadowColor = sc.core
      ctx.shadowBlur = 50 * pulse
      ctx.fill()
      ctx.shadowBlur = 0

      // Inner core ring
      ctx.beginPath()
      ctx.arc(CX, CY, coreR + 6, 0, Math.PI * 2)
      ctx.strokeStyle = sc.core
      ctx.lineWidth = 0.9
      ctx.globalAlpha = 0.4 + 0.3 * pulse
      ctx.stroke()
      ctx.globalAlpha = 1

      // Hexagonal markers around core
      for (let i = 0; i < 6; i++) {
        const a = (i / 6) * Math.PI * 2 + t * 0.22
        const hx = CX + Math.cos(a) * 42
        const hy = CY + Math.sin(a) * 42
        ctx.save()
        ctx.translate(hx, hy)
        ctx.rotate(a + t * 0.45)
        ctx.beginPath()
        for (let j = 0; j < 6; j++) {
          const ha = (j / 6) * Math.PI * 2
          j === 0
            ? ctx.moveTo(Math.cos(ha) * 4.5, Math.sin(ha) * 4.5)
            : ctx.lineTo(Math.cos(ha) * 4.5, Math.sin(ha) * 4.5)
        }
        ctx.closePath()
        ctx.strokeStyle = sc.core
        ctx.lineWidth = 0.7
        ctx.globalAlpha = 0.55 + 0.25 * Math.sin(t * 2 + i)
        ctx.stroke()
        ctx.globalAlpha = 1
        ctx.restore()
      }

      // Target lock corners
      const lockR = 36, lockSize = 10
      ;[[1,1],[1,-1],[-1,1],[-1,-1]].forEach(([sx, sy]) => {
        const blink = 0.5 + 0.5 * Math.sin(t * 3.5)
        ctx.strokeStyle = sc.core
        ctx.lineWidth = 1.5
        ctx.globalAlpha = blink * 0.9
        ctx.shadowColor = sc.core
        ctx.shadowBlur = 5
        ctx.beginPath()
        ctx.moveTo(CX + sx * lockR, CY + sy * (lockR - lockSize))
        ctx.lineTo(CX + sx * lockR, CY + sy * lockR)
        ctx.lineTo(CX + sx * (lockR - lockSize), CY + sy * lockR)
        ctx.stroke()
        ctx.shadowBlur = 0
        ctx.globalAlpha = 1
      })

      // ── Layer 7: Floating telemetry labels ────────────────
      TELEM_LABELS.forEach((tl, idx) => {
        const a = (tl.angle * Math.PI) / 180 + t * 0.04
        const lx = CX + Math.cos(a) * tl.dist
        const ly = CY + Math.sin(a) * tl.dist
        const val = telemVals[idx]
        const flicker = 0.7 + 0.3 * Math.sin(t * 1.5 + idx * 0.9)

        ctx.save()
        ctx.globalAlpha = flicker

        // Connector line
        const innerX = CX + Math.cos(a) * (tl.dist - 22)
        const innerY = CY + Math.sin(a) * (tl.dist - 22)
        ctx.beginPath()
        ctx.moveTo(innerX, innerY)
        ctx.lineTo(lx, ly)
        ctx.strokeStyle = tl.color
        ctx.lineWidth = 0.5
        ctx.globalAlpha = flicker * 0.35
        ctx.stroke()

        // Label box
        ctx.globalAlpha = flicker
        ctx.fillStyle = `rgba(2,8,19,0.75)`
        ctx.strokeStyle = tl.color
        ctx.lineWidth = 0.6
        const bw = 28, bh = 14
        ctx.beginPath()
        ctx.rect(lx - bw / 2, ly - bh / 2, bw, bh)
        ctx.fill()
        ctx.stroke()

        // Label text
        ctx.fillStyle = tl.color
        ctx.font = 'bold 5px Orbitron, sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(tl.label, lx, ly - 2.5)

        // Value text
        ctx.fillStyle = '#D8FFFF'
        ctx.font = '4.5px IBM Plex Mono, monospace'
        ctx.fillText(`${val}%`, lx, ly + 3.5)

        ctx.globalAlpha = 1
        ctx.restore()
      })

      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [])

  const sc = STATE_COLORS[status] || STATE_COLORS.idle

  return (
    <div className="relative flex flex-col items-center justify-center select-none hologram">
      {/* CSS outer energy rings */}
      {[1, 2, 3].map(i => (
        <motion.div
          key={i}
          className="absolute rounded-full pointer-events-none"
          style={{ width: 400 + i * 55, height: 400 + i * 55, border: `1px solid ${sc.ring}`, opacity: 0.10 / i }}
          animate={{ scale: [1, 1.03, 1], opacity: [0.10 / i, 0.05 / i, 0.10 / i] }}
          transition={{ duration: 2.5 + i, repeat: Infinity, ease: 'easeInOut' }}
        />
      ))}

      {/* Energy wave pulses */}
      {[0, 1, 2].map(i => (
        <motion.div
          key={i}
          className="absolute rounded-full pointer-events-none"
          style={{ width: 64, height: 64, border: `1px solid ${sc.core}` }}
          animate={{ scale: [1, 5.8], opacity: [0.55, 0] }}
          transition={{ duration: 3.8, repeat: Infinity, delay: i * 1.25, ease: 'easeOut' }}
        />
      ))}

      <canvas ref={canvasRef} style={{ width: 400, height: 400 }} />

      {/* State label */}
      <div className="absolute bottom-4 flex flex-col items-center gap-1.5">
        <div
          className="text-[9px] font-bold tracking-[0.38em]"
          style={{ color: sc.core, fontFamily: 'Orbitron, sans-serif', textShadow: `0 0 12px ${sc.core}, 0 0 24px ${sc.core}66` }}
        >
          {STATE_LABELS[status] || 'STANDBY'}
        </div>
        <div className="flex gap-1.5">
          {[0,1,2,3,4].map(i => (
            <motion.div
              key={i}
              className="w-1 h-1 rounded-full"
              style={{ background: sc.core }}
              animate={{ opacity: [0.15, 1, 0.15], scale: [0.8, 1.2, 0.8] }}
              transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.18 }}
            />
          ))}
        </div>
      </div>

      {/* J.A.R.V.I.S label */}
      <div
        className="absolute top-3 text-[11px] font-black tracking-[0.55em]"
        style={{ color: sc.core, fontFamily: 'Orbitron, sans-serif', textShadow: `0 0 14px ${sc.core}, 0 0 28px ${sc.core}55` }}
      >
        J.A.R.V.I.S
      </div>
    </div>
  )
}
