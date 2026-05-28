import { useState } from "react";
import type { ChatMessage } from "./api";
import { streamChat } from "./api";
import { clientLog } from "./clientLog";

const TOOL_LABELS: Record<string, string> = {
  get_patch_chain: "Reading signal chain",
  get_patch_overview: "Reading patch overview",
  get_patch_controls: "Reading patch controls",
  get_patch_musician_summary: "Reading musician summary",
  get_patch_block: "Reading effect block",
  list_ports: "Listing MIDI ports",
  plan_patch: "Building patch plan",
  load_skill_reference: "Loading GT-1000 reference",
};

const TOOL_CALL_MARKUP = /<tool_call>[\s\S]*?<\/tool_call>/gi;

function stripToolMarkup(text: string): string {
  return text.replace(TOOL_CALL_MARKUP, "").replace(/\n{3,}/g, "\n\n").trim();
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [toolLog, setToolLog] = useState<string[]>([]);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage() {
    const text = draft.trim();
    if (!text || streaming) return;
    setDraft("");
    setError(null);
    const history = messages;
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages([...nextMessages, { role: "assistant", content: "" }]);
    setStreaming(true);
    setToolLog([]);
    setStatusLine(null);
    clientLog("info", "chat-ui", "User sent message", { preview: text.slice(0, 120) });

    let assistant = "";
    try {
      await streamChat(text, history, (event) => {
        if (event.type === "assistant.clear") {
          assistant = "";
          setMessages((current) => {
            const copy = [...current];
            copy[copy.length - 1] = { role: "assistant", content: "" };
            return copy;
          });
        }
        if (event.type === "assistant.delta") {
          assistant += String(event.data.content ?? "");
          const visible = stripToolMarkup(assistant);
          setMessages((current) => {
            const copy = [...current];
            copy[copy.length - 1] = { role: "assistant", content: visible };
            return copy;
          });
        }
        if (event.type === "assistant.done") {
          assistant = stripToolMarkup(String(event.data.content ?? assistant));
          setStatusLine(null);
          setMessages((current) => {
            const copy = [...current];
            copy[copy.length - 1] = { role: "assistant", content: assistant };
            return copy;
          });
        }
        if (event.type === "assistant.status") {
          setStatusLine(String(event.data.message ?? ""));
        }
        if (event.type === "tool.start") {
          const name = String(event.data.name ?? "");
          const label = TOOL_LABELS[name] ?? `Running ${name}`;
          setToolLog((current) => [...current, label]);
          setStatusLine(label);
        }
        if (event.type === "tool.error") {
          const name = String(event.data.name ?? "tool");
          setToolLog((current) => [...current, `Failed: ${name}`]);
          clientLog("error", "chat-ui", `Tool failed: ${name}`, {
            error: String(event.data.error ?? ""),
          });
        }
        if (event.type === "error") {
          const message = String(event.data.message ?? "Chat error");
          setError(message);
          clientLog("error", "chat-ui", "Chat error event", { message });
        }
      });
    } catch (chatError) {
      const message = chatError instanceof Error ? chatError.message : String(chatError);
      setError(message);
      clientLog("error", "chat-ui", "Chat request failed", { error: message });
    } finally {
      setStreaming(false);
    }
  }

  return (
    <section className="panel chat-panel">
      <header className="panel-header">
        <h2>Agent chat</h2>
      </header>
      <div className="chat-log">
        {messages.length === 0 ? <p className="muted">Ask about the current patch or routing.</p> : null}
        {messages.map((message, index) => (
          <article key={`${message.role}-${index}`} className={`chat-message ${message.role}`}>
            <span className="chat-role">{message.role}</span>
            <div className="chat-body">{message.content}</div>
          </article>
        ))}
      </div>
      {statusLine ? <p className="chat-status muted">{statusLine}</p> : null}
      {toolLog.length > 0 ? (
        <ul className="tool-log">
          {toolLog.map((line, index) => (
            <li key={index}>{line}</li>
          ))}
        </ul>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      <div className="chat-input-row">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Explain this patch for a live gig…"
          rows={3}
          disabled={streaming}
        />
        <button type="button" onClick={sendMessage} disabled={streaming || !draft.trim()}>
          {streaming ? (statusLine ?? "Working…") : "Send"}
        </button>
      </div>
    </section>
  );
}
