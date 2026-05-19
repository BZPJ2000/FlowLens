/**
 * Thinking 签名错误处理器
 *
 * 检测并格式化 Anthropic/DeepSeek 等模型的 thinking signature 错误。
 *
 * 来源: Proma-reusable-modules/04-thinking-error-handler
 */

export const THINKING_SIGNATURE_ERROR_CODE = 'thinking_signature_invalid'
export const THINKING_SIGNATURE_ERROR_TITLE = '思考内容无法继续'
export const THINKING_SIGNATURE_ERROR_MESSAGE =
  '这个错误通常是因为中途切换了模型，不同模型的思考标签不互认。可以先切回原来的模型再重试；如果这是很早之前的会话，也可以在新对话中引用当前会话继续。'

export function isThinkingSignatureError(...messages: Array<string | null | undefined>): boolean {
  const combined = messages.filter(Boolean).join('\n').replace(/`/g, '')
  return /(?:invalid\s+signature[\s\S]{0,240}thinking\s+block|thinking\s+block[\s\S]{0,240}invalid\s+signature)/i.test(combined)
}

export function formatThinkingSignatureError(): string {
  return `${THINKING_SIGNATURE_ERROR_TITLE}：${THINKING_SIGNATURE_ERROR_MESSAGE}`
}

export function normalizeThinkingSignatureError(error: string): string {
  return isThinkingSignatureError(error) ? formatThinkingSignatureError() : error
}
