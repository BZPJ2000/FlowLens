/**
 * useSmoothStream — 平滑流式文本 Hook
 *
 * 解决 AI 流式输出不均匀的问题：后端推送速度不恒定，
 * 此 Hook 维护一个字符缓冲区，以固定速度逐字符吐出，
 * 实现类似打字机的平滑效果。
 *
 * 来源: Proma-reusable-modules/14-react-ai-components
 */

import { useState, useEffect, useRef, useCallback } from 'react'

export interface UseSmoothStreamOptions {
  /** 平滑速度（ms/字符，默认 30） */
  speed?: number
  /** 每次吐出的字符数（默认 1） */
  batchSize?: number
}

export interface UseSmoothStreamResult {
  /** 当前平滑显示的文字 */
  displayedText: string
  /** 是否正在平滑输出中 */
  isAnimating: boolean
  /** 追加新文本到缓冲区 */
  append: (chunk: string) => void
  /** 立即完成（显示全部缓冲文本） */
  flush: () => void
  /** 重置状态 */
  reset: () => void
}

export function useSmoothStream(options: UseSmoothStreamOptions = {}): UseSmoothStreamResult {
  const { speed = 30, batchSize = 1 } = options

  const [displayedText, setDisplayedText] = useState('')
  const [isAnimating, setIsAnimating] = useState(false)

  const bufferRef = useRef('')
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const startAnimating = useCallback(() => {
    if (timerRef.current) return

    setIsAnimating(true)
    timerRef.current = setInterval(() => {
      setDisplayedText(prev => {
        const remaining = bufferRef.current
        if (remaining.length === 0) {
          if (timerRef.current) {
            clearInterval(timerRef.current)
            timerRef.current = null
          }
          setIsAnimating(false)
          return prev
        }

        const take = remaining.slice(0, batchSize)
        bufferRef.current = remaining.slice(batchSize)
        return prev + take
      })
    }, speed)
  }, [speed, batchSize])

  const append = useCallback((chunk: string) => {
    bufferRef.current += chunk
    if (!timerRef.current) {
      startAnimating()
    }
  }, [startAnimating])

  const flush = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    setDisplayedText(prev => prev + bufferRef.current)
    bufferRef.current = ''
    setIsAnimating(false)
  }, [])

  const reset = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    bufferRef.current = ''
    setDisplayedText('')
    setIsAnimating(false)
  }, [])

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [])

  return { displayedText, isAnimating, append, flush, reset }
}
