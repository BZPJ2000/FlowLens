/**
 * 通用 SSE 流式读取器
 *
 * 独立于 Provider 适配器的通用引擎。
 * fetch + ReadableStream（浏览器/Node.js/Bun 通用）
 *
 * 核心特性：
 * - 自动 buffer 管理 + 逐行分割
 * - [DONE] 哨兵 + "data: " 前缀解析
 * - AbortController 支持
 * - 自定义 fetch 注入（代理、拦截等场景）
 * - 累积 content / reasoning / thinkingBlocks / toolCalls
 *
 * 来源: Proma-reusable-modules/02-sse-stream-reader
 */

/** 流式事件回调 */
export type StreamEventCallback = (event: StreamEvent) => void

/** 通用流式事件类型 */
export type StreamEvent =
  | { type: 'chunk'; delta: string }
  | { type: 'reasoning'; delta: string }
  | { type: 'reasoning_signature'; signature: string }
  | { type: 'reasoning_block_start' }
  | { type: 'reasoning_block_stop' }
  | { type: 'error'; error: string }
  | { type: 'done'; stopReason?: string }
  | { type: 'tool_call_start'; toolCallId: string; toolName: string; metadata?: Record<string, unknown> }
  | { type: 'tool_call_delta'; toolCallId: string; argumentsDelta: string }

/** HTTP 请求配置 */
export interface ProviderRequest {
  url: string
  headers: Record<string, string>
  body: string
}

/** Provider 适配器的最小接口（SSE 读取器仅需 parseSSELine） */
export interface SSEAdapter {
  providerType: string
  parseSSELine(jsonLine: string): StreamEvent[]
}

/** 思考块 */
export interface ThinkingBlock {
  thinking: string
  signature?: string
}

/** 工具调用 */
export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  metadata?: Record<string, unknown>
}

/** streamSSE 输入选项 */
export interface StreamSSEOptions {
  request: ProviderRequest
  adapter: SSEAdapter
  onEvent: StreamEventCallback
  signal?: AbortSignal
  fetchFn?: typeof globalThis.fetch
}

/** streamSSE 返回结果 */
export interface StreamSSEResult {
  content: string
  reasoning: string
  thinkingBlocks: ThinkingBlock[]
  toolCalls: ToolCall[]
  stopReason?: string
}

/**
 * 执行流式 SSE 请求
 */
export async function streamSSE(options: StreamSSEOptions): Promise<StreamSSEResult> {
  const { request, adapter, onEvent, signal, fetchFn = fetch } = options

  const response = await fetchFn(request.url, {
    method: 'POST',
    headers: request.headers,
    body: request.body,
    signal,
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`${adapter.providerType} API 错误 (${response.status}): ${text.slice(0, 300)}`)
  }

  if (!response.body) {
    throw new Error('响应体为空')
  }

  let content = ''
  let reasoning = ''
  let stopReason: string | undefined
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const pendingToolCalls = new Map<string, { id: string; name: string; args: string; metadata?: Record<string, unknown> }>()
  let currentToolCallId: string | undefined

  const thinkingBlocks: ThinkingBlock[] = []
  let currentThinking: ThinkingBlock | null = null

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        let data: string
        if (line.startsWith('data: ')) {
          data = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          data = line.slice(5).trim()
        } else {
          continue
        }
        if (data === '[DONE]' || !data) continue

        const events = adapter.parseSSELine(data)

        for (const event of events) {
          if (event.type === 'chunk') {
            content += event.delta
          } else if (event.type === 'reasoning') {
            reasoning += event.delta
            if (currentThinking) {
              currentThinking.thinking += event.delta
            } else {
              currentThinking = { thinking: event.delta }
              thinkingBlocks.push(currentThinking)
            }
          } else if (event.type === 'reasoning_signature') {
            if (currentThinking) {
              currentThinking.signature = (currentThinking.signature ?? '') + event.signature
            } else {
              currentThinking = { thinking: '', signature: event.signature }
              thinkingBlocks.push(currentThinking)
            }
          } else if (event.type === 'reasoning_block_start') {
            currentThinking = { thinking: '' }
            thinkingBlocks.push(currentThinking)
          } else if (event.type === 'reasoning_block_stop') {
            currentThinking = null
          } else if (event.type === 'tool_call_start') {
            currentToolCallId = event.toolCallId
            pendingToolCalls.set(event.toolCallId, {
              id: event.toolCallId,
              name: event.toolName,
              args: '',
              metadata: event.metadata,
            })
          } else if (event.type === 'tool_call_delta') {
            const tcId = event.toolCallId || currentToolCallId
            if (tcId) {
              const pending = pendingToolCalls.get(tcId)
              if (pending) {
                pending.args += event.argumentsDelta
              }
            }
          } else if (event.type === 'done' && event.stopReason) {
            stopReason = event.stopReason
          }
          onEvent(event)
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  const toolCalls: ToolCall[] = []
  for (const [, pending] of pendingToolCalls) {
    try {
      toolCalls.push({
        id: pending.id,
        name: pending.name,
        arguments: pending.args ? JSON.parse(pending.args) : {},
        metadata: pending.metadata,
      })
    } catch {
      toolCalls.push({ id: pending.id, name: pending.name, arguments: {}, metadata: pending.metadata })
    }
  }

  if (toolCalls.length > 0 && !stopReason) {
    stopReason = 'tool_use'
  }

  onEvent({ type: 'done', stopReason })
  return { content, reasoning, thinkingBlocks, toolCalls, stopReason }
}
