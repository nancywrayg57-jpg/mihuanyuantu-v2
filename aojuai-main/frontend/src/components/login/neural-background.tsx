'use client'

import { useEffect, useMemo, useRef } from 'react'

import { useT } from '@/lib/i18n'

type Particle = {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  alpha: number
  isText: boolean
  text?: string
}

const colorSchemes = {
  dark: {
    primary: '#22d3ee',
    line: '134, 239, 172',
    particle: '34, 211, 238',
    text: '226, 232, 240',
    textHover: '255, 255, 255',
  },
  light: {
    primary: '#6366f1',
    line: '165, 180, 252',
    particle: '99, 102, 241',
    text: '99, 102, 241',
    textHover: '67, 56, 202',
  },
}

function initParticles(width: number, height: number, quotes: string[]): Particle[] {
  const area = Math.max(1, width * height)
  const particleCount = Math.min(160, Math.floor(area / 10_000))

  const out: Particle[] = []
  for (let i = 0; i < particleCount; i++) {
    const isText = Math.random() > 0.4
    const text = isText && quotes.length > 0 ? quotes[Math.floor(Math.random() * quotes.length)] : undefined
    out.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      size: isText ? 14 : Math.random() * 2.5 + 1.5,
      isText,
      text,
      alpha: isText ? Math.random() * 0.5 + 0.4 : Math.random() * 0.5 + 0.2,
    })
  }
  return out
}

export function NeuralBackground({ isDark }: { isDark: boolean }) {
  const t = useT()
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const rafRef = useRef<number | null>(null)
  const particlesRef = useRef<Particle[]>([])
  const mouseRef = useRef({ x: 0, y: 0 })
  const quotes = useMemo(
    () => t('system.login.background.quotes').split('|').map((item) => item.trim()).filter(Boolean),
    [t],
  )

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const colors = isDark ? colorSchemes.dark : colorSchemes.light
    let destroyed = false

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
      particlesRef.current = initParticles(canvas.width, canvas.height, quotes)
    }

    const onMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY }
    }

    const draw = () => {
      if (destroyed) return
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const particles = particlesRef.current
      const mouse = mouseRef.current
      const interactionRadius = 300
      const maxConnectDist = 140

      for (let i = 0; i < particles.length; i++) {
        const p1 = particles[i]

        const dxMouse = p1.x - mouse.x
        const dyMouse = p1.y - mouse.y
        const distMouse = Math.sqrt(dxMouse * dxMouse + dyMouse * dyMouse)

        if (distMouse < interactionRadius) {
          const opacity = 1 - distMouse / interactionRadius
          ctx.lineWidth = 1.5 * opacity
          ctx.shadowBlur = 10 * opacity
          ctx.shadowColor = colors.primary
          ctx.strokeStyle = isDark
            ? `rgba(0, 242, 255, ${opacity})`
            : `rgba(37, 99, 235, ${opacity})`

          ctx.beginPath()
          ctx.moveTo(p1.x, p1.y)
          ctx.lineTo(mouse.x, mouse.y)
          ctx.stroke()
          ctx.shadowBlur = 0
        }

        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j]
          const dx = p1.x - p2.x
          const dy = p1.y - p2.y
          const distance = Math.sqrt(dx * dx + dy * dy)
          if (distance >= maxConnectDist) continue

          let opacity = (1 - distance / maxConnectDist) * 0.3
          let lineWidth = 0.5

          const dxMouse2 = p2.x - mouse.x
          const dyMouse2 = p2.y - mouse.y
          const distMouse2 = Math.sqrt(dxMouse2 * dxMouse2 + dyMouse2 * dyMouse2)

          if (distMouse < interactionRadius && distMouse2 < interactionRadius) {
            opacity = Math.min(0.8, opacity * 3)
            lineWidth = 1.2
            ctx.strokeStyle = isDark
              ? `rgba(189, 0, 255, ${opacity})`
              : `rgba(124, 58, 237, ${opacity})`
          } else {
            ctx.strokeStyle = `rgba(${colors.line}, ${opacity})`
          }

          ctx.lineWidth = lineWidth
          ctx.beginPath()
          ctx.moveTo(p1.x, p1.y)
          ctx.lineTo(p2.x, p2.y)
          ctx.stroke()
        }

        p1.x += p1.vx
        p1.y += p1.vy
        if (p1.x < 0 || p1.x > canvas.width) p1.vx *= -1
        if (p1.y < 0 || p1.y > canvas.height) p1.vy *= -1

        if (p1.isText && p1.text) {
          const hovered = distMouse < 150
          ctx.font = hovered ? '700 15px ui-sans-serif, system-ui' : '500 14px ui-sans-serif, system-ui'
          ctx.fillStyle = hovered
            ? `rgba(${colors.textHover}, ${Math.min(1, p1.alpha + 0.4)})`
            : `rgba(${colors.text}, ${p1.alpha})`
          ctx.fillText(p1.text, p1.x, p1.y)
        } else {
          ctx.beginPath()
          ctx.arc(p1.x, p1.y, p1.size, 0, Math.PI * 2)
          if (distMouse < interactionRadius) {
            ctx.fillStyle = isDark ? 'rgba(0, 242, 255, 0.9)' : 'rgba(37, 99, 235, 0.9)'
            ctx.shadowBlur = 8
            ctx.shadowColor = colors.primary
          } else {
            ctx.fillStyle = `rgba(${colors.particle}, ${p1.alpha})`
            ctx.shadowBlur = 0
          }
          ctx.fill()
          ctx.shadowBlur = 0
        }
      }

      rafRef.current = requestAnimationFrame(draw)
    }

    resize()
    draw()
    window.addEventListener('resize', resize)
    window.addEventListener('mousemove', onMouseMove)

    return () => {
      destroyed = true
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMouseMove)
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
    }
  }, [isDark, quotes])

  return <canvas ref={canvasRef} className="pointer-events-none fixed inset-0 z-0 h-full w-full" />
}
