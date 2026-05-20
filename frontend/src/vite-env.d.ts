/// <reference types="vite/client" />

declare module 'mermaid' {
  interface MermaidConfig {
    theme?: string
    startOnLoad?: boolean
    [key: string]: unknown
  }
  interface MermaidInstance {
    initialize(config: MermaidConfig): void
    render(id: string, text: string): Promise<{ svg: string }>
  }
  const mermaid: MermaidInstance
  export default mermaid
}
