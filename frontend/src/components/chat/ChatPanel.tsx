import { useState, useRef, useEffect } from "react";
import { X, Send, Loader2, MessageSquare } from "lucide-react";
import { useGraphStore } from "../../stores/graphStore";
import { api } from "../../api/client";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatPanel() {
  const showChatPanel = useGraphStore((s) => s.showChatPanel);
  const toggleChatPanel = useGraphStore((s) => s.toggleChatPanel);
  const analysisId = useGraphStore((s) => s.analysisId);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !analysisId || loading) return;
    const msg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setLoading(true);

    try {
      const res = await api.sendMessage(analysisId, msg, sessionId || undefined);
      setSessionId(res.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "AI 服务暂时不可用，请检查配置。" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!showChatPanel) return null;

  return (
    <div className="w-80 flex-shrink-0 bg-[#0a0a10] border-l border-[#1e1e3a] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between p-3 border-b border-[#1e1e3a]">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-[#a1a1aa]" />
          <h3 className="text-xs font-semibold text-[#f5f5f7] uppercase tracking-wider">
            AI 问答
          </h3>
        </div>
        <button
          onClick={toggleChatPanel}
          className="text-[#6b7280] hover:text-[#f5f5f7] transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-xs text-[#6b7280] mt-8">
            基于已分析的项目结构提问
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-xs leading-relaxed ${
              m.role === "user"
                ? "bg-[#7c3aed]/10 border border-[#7c3aed]/20 rounded-xl px-3 py-2 ml-6 text-[#f5f5f7]"
                : "bg-[#12121c] border border-[#1e1e3a] rounded-xl px-3 py-2 mr-4 text-[#a1a1aa]"
            }`}
          >
            {m.content}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-[#6b7280] text-xs px-2">
            <Loader2 className="w-3 h-3 animate-spin" />
            AI 正在思考...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 p-3 border-t border-[#1e1e3a]">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="询问项目架构..."
            disabled={loading}
            className="flex-1 bg-[#12121c] border border-[#1e1e3a] rounded-lg px-3 py-2 text-xs text-[#f5f5f7] placeholder-[#6b7280] focus:outline-none focus:border-[#7c3aed] focus:ring-1 focus:ring-[#7c3aed]/30 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="p-2 bg-[#7c3aed] hover:bg-[#6d28d9] disabled:bg-[#1e1e3a] disabled:text-[#6b7280] text-white rounded-lg transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
