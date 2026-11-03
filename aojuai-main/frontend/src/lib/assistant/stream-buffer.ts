export type StreamBufferOptions = {
  onFirstChunk?: () => void
  onText: (text: string) => void
  flushDelayMs?: number
}

export type StreamBufferController = {
  push: (delta: string) => void
  replace: (fullText: string) => void
  flush: () => void
  finish: () => void
  waitForIdle: () => Promise<void>
  stop: () => void
}

export function createStreamTextBuffer(options: StreamBufferOptions): StreamBufferController {
  const baseCharsPerSecond = 24
  const maxCharsPerSecond = 120
  const endCharsPerSecond = 180
  const backlogThreshold = 72
  const backlogFactor = 0.2
  const renderIntervalMs = Math.min(60, Math.max(24, Math.floor((options.flushDelayMs ?? 80) / 2)))

  let targetText = ''
  let renderedText = ''
  let started = false

  let running = false
  let ending = false
  let rafId: number | null = null
  let lastTs = 0
  let lastEmitTs = 0
  let charDebt = 0
  let idleResolvers: Array<() => void> = []

  const emit = (text: string, now = 0) => {
    options.onText(text)
    if (now > 0) {
      lastEmitTs = now
    }
  }

  const resolveIdle = () => {
    if (running) return
    if (targetText.length !== renderedText.length) return
    if (idleResolvers.length === 0) return
    const nextResolvers = idleResolvers
    idleResolvers = []
    nextResolvers.forEach((resolver) => resolver())
  }

  const markStarted = () => {
    if (started) return
    started = true
    options.onFirstChunk?.()
  }

  const computeSpeed = (backlog: number) => {
    if (ending) return endCharsPerSecond
    if (backlog <= backlogThreshold) return baseCharsPerSecond
    return Math.min(maxCharsPerSecond, baseCharsPerSecond + (backlog - backlogThreshold) * backlogFactor)
  }

  const stopRaf = () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    running = false
    lastTs = 0
    charDebt = 0
    resolveIdle()
  }

  const tick = (ts: number) => {
    if (!running) return

    if (!lastTs) {
      lastTs = ts
      rafId = requestAnimationFrame(tick)
      return
    }

    const elapsed = Math.max(8, ts - lastTs)
    lastTs = ts

    const backlog = Math.max(0, targetText.length - renderedText.length)
    if (backlog > 0) {
      const cps = computeSpeed(backlog)
      charDebt += (cps * elapsed) / 1000

      const renderCount = Math.floor(charDebt)
      if (renderCount >= 1) {
        charDebt -= renderCount
        const nextLength = Math.min(targetText.length, renderedText.length + renderCount)
        renderedText = targetText.slice(0, nextLength)

        if (ts - lastEmitTs >= renderIntervalMs || renderedText.length === targetText.length) {
          emit(renderedText, ts)
        }
      }
    }

    const rest = targetText.length - renderedText.length
    if (rest <= 0 && !ending) {
      stopRaf()
      return
    }

    if (rest <= 0 && ending) {
      emit(renderedText, ts)
      stopRaf()
      return
    }

    rafId = requestAnimationFrame(tick)
  }

  const ensureRunning = () => {
    if (running) return
    running = true
    rafId = requestAnimationFrame(tick)
  }

  return {
    push(delta: string) {
      const nextDelta = String(delta || '')
      if (!nextDelta) return
      markStarted()
      ending = false
      targetText += nextDelta
      ensureRunning()
    },
    replace(fullText: string) {
      const nextText = String(fullText || '')
      if (!nextText) return
      markStarted()
      ending = false

      if (nextText.startsWith(targetText)) {
        targetText = nextText
      } else {
        targetText = nextText
        if (renderedText.length > targetText.length) {
          renderedText = targetText
          emit(renderedText)
        }
      }

      ensureRunning()
    },
    flush() {
      ending = true
      targetText = targetText || renderedText
      renderedText = targetText
      emit(renderedText)
      stopRaf()
    },
    finish() {
      ending = true
      if (targetText.length <= renderedText.length) {
        emit(renderedText)
        stopRaf()
        return
      }
      ensureRunning()
    },
    waitForIdle() {
      if (!running && targetText.length === renderedText.length) {
        return Promise.resolve()
      }
      return new Promise<void>((resolve) => {
        idleResolvers.push(resolve)
      })
    },
    stop() {
      stopRaf()
    },
  }
}
