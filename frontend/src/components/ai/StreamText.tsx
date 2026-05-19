/**
 * StreamText — 流式文本逐字展示组件
 *
 * 配合 useSmoothStream Hook 使用，实现打字机效果的文本渲染。
 *
 * 来源: Proma-reusable-modules/14-react-ai-components
 */

import React from 'react'

export interface StreamTextProps {
  /** 累积的完整文本 */
  text: string
  /** 是否正在流式输出 */
  isStreaming: boolean
  /** 平滑速度（ms/字符，默认 30） */
  speed?: number
  /** CSS 类名 */
  className?: string
  /** 流式结束后的闪烁光标 */
  showCursor?: boolean
}

export function StreamText({
  text,
  isStreaming,
  className,
  showCursor = false,
}: StreamTextProps) {
  return (
    <span className={`stream-text ${className || ''}`}>
      {text}
      {isStreaming && showCursor && (
        <span className="stream-cursor">|</span>
      )}
    </span>
  )
}
