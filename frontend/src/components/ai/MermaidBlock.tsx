/**
 * MermaidBlock — Mermaid 图表渲染组件
 *
 * 使用 mermaid.js 渲染流程图、时序图等。
 * 支持深色/浅色主题切换。
 *
 * 来源: Proma-reusable-modules/14-react-ai-components
 */

import React, { useRef, useEffect, useState } from 'react'

export interface MermaidBlockProps {
  /** Mermaid 图表定义代码 */
  chart: string
  /** 主题（默认 'default'） */
  theme?: 'default' | 'dark' | 'neutral' | 'forest'
  /** CSS 类名 */
  className?: string
}

export function MermaidBlock({ chart, theme = 'default', className }: MermaidBlockProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function render() {
      try {
        const mermaid = (await import('mermaid')).default
        if (cancelled) return
        mermaid.initialize({ theme, startOnLoad: false })
        const { svg } = await mermaid.render('mermaid-' + Date.now(), chart)
        if (containerRef.current) {
          containerRef.current.innerHTML = svg
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : '渲染失败')
      }
    }

    render()
    return () => { cancelled = true }
  }, [chart, theme])

  if (error) {
    return (
      <div className={`mermaid-error ${className || ''}`}>
        <pre>{chart}</pre>
        <p className="error-message">{error}</p>
      </div>
    )
  }

  return <div ref={containerRef} className={`mermaid-block ${className || ''}`} />
}
