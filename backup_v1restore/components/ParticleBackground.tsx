'use client'
import { useEffect, useRef } from 'react'
import { useJarvisStore } from '@/store/jarvisStore'

export function ParticleBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const statusRef = useRef('idle')
  const { status } = useJarvisStore()
  useEffect(() => { statusRef.current = status }, [status])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: true })!
    let raf: number
    let W = window.innerWidth
    let H = window.innerHeight
    canvas.width = W; canvas.height = H

    const resize = () => {
      W = window.innerWidth; H = window.innerHeight
      canvas.width = W; canvas.height = H
    }
    window.addEventListener('resize', resize)

    // ── Particle types ──────────────────────────────────────
    type Particle = {
      x: number; y: number; vx: number; vy: number
      r: number; alpha: number; color: string
      layer: number // 0=far, 1=mid, 2=near
    }
    type Star = { x: number; y: number; r: number; alpha: number; phase: number; speed: number }
    type Streak = { x: number; y: number; vx: number; vy: number; len: number; alpha: number; color: string; life: number; maxLife: number }
    type DataNode = { x: number; y: number; vx: number; vy: number; r: number; alpha: number }

    const COLORS = [
      'rgba(0,217,255,',
      'rgba(51,242,255,',
      'rgba(0,157,255,',
      'rgba(0,255,153,',
      'rgba(123,94,167,',
    ]

    // 3 depth layers of particles
    const particles: Particle[] = Array.from({ length: 180 }, () => {
      const layer = Math.floor(Math.random() * 3)
      const speed = layer === 0 ? 0.12 : layer === 1 ? 0.22 : 0.38
      return {
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * speed,
        vy: (Math.random() - 0.5) * speed,
        r: layer === 0 ? Math.random() * 0.8 + 0.2 : layer === 1 ? Math.random() * 1.2 + 0.4 : Math.random() * 1.8 + 0.6,
        alpha: layer === 0 ? Math.random() * 0.25 + 0.05 : layer === 1 ? Math.random() * 0.4 + 0.1 : Math.random() * 0.55 + 0.15,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        layer,
      }
    })

    // Stars
    const stars: Star[] = Array.from({ length: 200 }, () => ({
      x: Math.random() * W,
      y: Math.random() * H,
      r: Math.random() * 0.9 + 0.1,
      alpha: Math.random() * 0.35 + 0.05,
      phase: Math.random() * Math.PI * 2,
      speed: 0.4 + Math.random() * 0.8,
    }))

    // Light streaks
    const streaks: Streak[] = []
    const spawnStreak = () => {
      const edge = Math.floor(Math.random() * 4)
      let x = 0, y = 0, vx = 0, vy = 0
      const speed = 1.5 + Math.random() * 3
      if (edge === 0) { x = Math.random() * W; y = 0; vx = (Math.random() - 0.5) * 0.5; vy = speed }
      else if (edge === 1) { x = W; y = Math.random() * H; vx = -speed; vy = (Math.random() - 0.5) * 0.5 }
      else if (edge === 2) { x = Math.random() * W; y = H; vx = (Math.random() - 0.5) * 0.5; vy = -speed }
      else { x = 0; y = Math.random() * H; vx = speed; vy = (Math.random() - 0.5) * 0.5 }
      const maxLife = 60 + Math.random() * 80
      streaks.push({ x, y, vx, vy, len: 20 + Math.random() * 60, alpha: 0.3 + Math.random() * 0.4, color: COLORS[Math.floor(Math.random() * 2)], life: 0, maxLife })
    }

    // Data nodes (active during thinking/executing)
    const dataNodes: DataNode[] = Array.from({ length: 30 }, () => ({
      x: Math.random() * W,
      y: Math.random() * H,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 2 + 1,
      alpha: Math.random() * 0.4 + 0.1,
    }))

    let t = 0
    let streakTimer = 0

    const draw = () => {
      t += 0.01
      streakTimer++
      if (streakTimer > 40 + Math.random() * 60) {
        spawnStreak()
        streakTimer = 0
      }

      ctx.clearRect(0, 0, W, H)
      const st = statusRef.current

      // ── Stars ──────────────────────────────────────────────
      stars.forEach(s => {
        const a = s.alpha * (0.5 + 0.5 * Math.sin(t * s.speed + s.phase))
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(200,249,255,${a})`
        ctx.fill()
      })

      // ── Light streaks ──────────────────────────────────────
      for (let i = streaks.length - 1; i >= 0; i--) {
        const sk = streaks[i]
        sk.x += sk.vx; sk.y += sk.vy; sk.life++
        const progress = sk.life / sk.maxLife
        const a = sk.alpha * Math.sin(progress * Math.PI)
        const grad = ctx.createLinearGradient(
          sk.x - sk.vx * sk.len, sk.y - sk.vy * sk.len,
          sk.x, sk.y
        )
        grad.addColorStop(0, sk.color + '0)')
        grad.addColorStop(1, sk.color + a + ')')
        ctx.beginPath()
        ctx.moveTo(sk.x - sk.vx * sk.len, sk.y - sk.vy * sk.len)
        ctx.lineTo(sk.x, sk.y)
        ctx.strokeStyle = grad
        ctx.lineWidth = 0.8
        ctx.stroke()
        if (sk.life >= sk.maxLife || sk.x < -100 || sk.x > W + 100 || sk.y < -100 || sk.y > H + 100) {
          streaks.splice(i, 1)
        }
      }

      // ── Particles by layer (far → near) ───────────────────
      for (let layer = 0; layer <= 2; layer++) {
        const layerParticles = particles.filter(p => p.layer === layer)
        const connDist = layer === 2 ? 120 : layer === 1 ? 80 : 50
        const connAlpha = layer === 2 ? 0.07 : layer === 1 ? 0.04 : 0.02

        layerParticles.forEach(p => {
          p.x += p.vx; p.y += p.vy
          if (p.x < 0) p.x = W; if (p.x > W) p.x = 0
          if (p.y < 0) p.y = H; if (p.y > H) p.y = 0
          ctx.beginPath()
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
          ctx.fillStyle = p.color + p.alpha + ')'
          ctx.fill()
        })

        // Connection lines (only near layer)
        if (layer === 2) {
          for (let i = 0; i < layerParticles.length; i++) {
            for (let j = i + 1; j < layerParticles.length; j++) {
              const dx = layerParticles[i].x - layerParticles[j].x
              const dy = layerParticles[i].y - layerParticles[j].y
              const d = Math.sqrt(dx * dx + dy * dy)
              if (d < connDist) {
                ctx.beginPath()
                ctx.moveTo(layerParticles[i].x, layerParticles[i].y)
                ctx.lineTo(layerParticles[j].x, layerParticles[j].y)
                ctx.strokeStyle = `rgba(0,217,255,${connAlpha * (1 - d / connDist)})`
                ctx.lineWidth = 0.4
                ctx.stroke()
              }
            }
          }
        }
      }

      // ── Data nodes (thinking/executing) ───────────────────
      if (st === 'thinking' || st === 'executing') {
        dataNodes.forEach(n => {
          n.x += n.vx; n.y += n.vy
          if (n.x < 0 || n.x > W) n.vx *= -1
          if (n.y < 0 || n.y > H) n.vy *= -1
          ctx.beginPath()
          ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(123,94,167,${n.alpha})`
          ctx.fill()
        })
        for (let i = 0; i < dataNodes.length; i++) {
          for (let j = i + 1; j < dataNodes.length; j++) {
            const dx = dataNodes[i].x - dataNodes[j].x
            const dy = dataNodes[i].y - dataNodes[j].y
            const d = Math.sqrt(dx * dx + dy * dy)
            if (d < 150) {
              ctx.beginPath()
              ctx.moveTo(dataNodes[i].x, dataNodes[i].y)
              ctx.lineTo(dataNodes[j].x, dataNodes[j].y)
              ctx.strokeStyle = `rgba(123,94,167,${0.06 * (1 - d / 150)})`
              ctx.lineWidth = 0.5
              ctx.stroke()
            }
          }
        }
      }

      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize) }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{ zIndex: 0 }}
    />
  )
}
