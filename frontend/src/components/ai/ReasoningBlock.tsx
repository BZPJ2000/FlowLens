/**
 * ReasoningBlock — AI 推理过程折叠面板
 *
 * 用于展示 Claude/DeepSeek 等模型的 thinking/reasoning 内容。
 * 默认折叠，用户可点击展开。
 *
 * 来源: Proma-reusable-modules/14-react-ai-components
 */

import React, { useState } from 'react'

export interface ReasoningBlockProps {
  /** 推理文本内容 */
  content: string
  /** 面板标题（默认 "思考过程"） */
  title?: string
  /** 是否默认展开 */
  defaultOpen?: boolean
  /** 是否显示耗时（毫秒） */
  durationMs?: number
}

export function ReasoningBlock({
  content,
  title = '思考过程',
  defaultOpen = false,
  durationMs,
}: ReasoningBlockProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  if (!content.trim()) return null

  return (
    <div className="reasoning-block">
      <button
        className="reasoning-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span className="toggle-icon">{isOpen ? '▼' : '▶'}</span>
        <span className="toggle-title">{title}</span>
        {durationMs !== undefined && (
          <span className="toggle-duration">{(durationMs / 1000).toFixed(1)}s</span>
        )}
      </button>
      {isOpen && (
        <div className="reasoning-content">
          {content}
        </div>
      )}
    </div>
  )
}
