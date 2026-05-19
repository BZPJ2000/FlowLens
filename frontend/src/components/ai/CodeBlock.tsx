/**
 * CodeBlock — 带语法高亮、语言标签和复制按钮的代码块组件
 *
 * 基于 Shiki 实现语法高亮，支持多种主题。
 * 使用方式：在 Markdown 渲染中将 ```code``` 替换为 <CodeBlock>。
 *
 * 来源: Proma-reusable-modules/14-react-ai-components
 */

import React, { useMemo, useState } from 'react'

export interface CodeBlockProps {
  /** 代码内容 */
  code: string
  /** 编程语言标识 */
  language?: string
  /** Shiki 主题（默认 'dark-plus'） */
  theme?: string
  /** 额外的 CSS 类名 */
  className?: string
  /** 是否显示复制按钮 */
  showCopy?: boolean
  /** 异步高亮函数（由外部注入，支持懒加载 Shiki） */
  highlightFn?: (code: string, lang: string, theme: string) => Promise<string>
}

export function CodeBlock({
  code,
  language = 'text',
  theme = 'dark-plus',
  className,
  showCopy = true,
  highlightFn,
}: CodeBlockProps) {
  const [highlighted, setHighlighted] = useState('')
  const [copied, setCopied] = useState(false)

  useMemo(() => {
    if (highlightFn) {
      highlightFn(code, language, theme)
        .then(setHighlighted)
        .catch(() => setHighlighted(''))
    }
  }, [code, language, theme, highlightFn])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard API 不可用
    }
  }

  return (
    <div className={`code-block-wrapper ${className || ''}`}>
      <div className="code-block-header">
        <span className="code-language">{language}</span>
        {showCopy && (
          <button onClick={handleCopy} className="copy-button">
            {copied ? 'Copied!' : 'Copy'}
          </button>
        )}
      </div>
      {highlighted ? (
        <div
          className="code-block-content"
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      ) : (
        <pre className="code-block-fallback">
          <code>{code}</code>
        </pre>
      )}
    </div>
  )
}
