import { clientLog } from "./clientLog";

export type DeviceStatus = {
  ok: boolean;
  busy: boolean;
  blocked_reason: string | null;
  last_error: string | null;
  last_activity_monotonic: number | null;
};

export type ChainElement = {
  id?: string;
  position?: number;
  rawValue?: number;
  displayName?: string;
  detailBlockID?: string | null;
  typeName?: string | null;
  isEnabled?: boolean | null;
  includeInDescription?: boolean;
  isReserved?: boolean;
  isOutput?: boolean;
};

export type PatchOverview = {
  patchName?: string | null;
  masterBPM?: number | null;
  masterPatchLevel?: number | null;
  masterKey?: string | null;
  signalChainElementCount?: number;
  detailBlockCount?: number;
};

export type ChainView = {
  overview?: PatchOverview;
  signalChainSummary?: string;
  descriptionSignalChainSummary?: string;
  elements?: ChainElement[];
  /** Blocks in audible signal order (divider → path A → branch → path B → mixer). */
  signalOrderElements?: ChainElement[];
  descriptionElements?: ChainElement[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const API_BASE = "";

function parseApiError(body: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    // Not JSON; use raw body.
  }
  return body;
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method ?? "GET";
  const started = performance.now();
  clientLog("debug", "api", `${method} ${path}`);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: init?.signal ?? AbortSignal.timeout(20_000),
    });
    const durationMs = Math.round(performance.now() - started);
    if (!response.ok) {
      const detail = parseApiError(await response.text());
      clientLog("error", "api", `${method} ${path} failed`, {
        status: response.status,
        durationMs,
        detail,
      });
      throw new Error(detail || `Request failed: ${response.status}`);
    }
    clientLog("debug", "api", `${method} ${path} ok`, { status: response.status, durationMs });
    return response.json() as Promise<T>;
  } catch (error) {
    const durationMs = Math.round(performance.now() - started);
    clientLog("error", "api", `${method} ${path} error`, {
      durationMs,
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

export async function getDeviceStatus(): Promise<DeviceStatus> {
  return fetchJson<DeviceStatus>("/api/device/status");
}

export async function getPatchPreview(refresh = false): Promise<ChainView> {
  const query = refresh ? "?refresh=1" : "";
  return fetchJson<ChainView>(`/api/patch/preview${query}`, {
    signal: AbortSignal.timeout(20_000),
  });
}

export async function getPatchChain(refresh = false): Promise<ChainView> {
  const query = refresh ? "?refresh=1" : "";
  return fetchJson<ChainView>(`/api/patch/chain${query}`, {
    signal: AbortSignal.timeout(60_000),
  });
}

export async function getConfig(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/config");
}

export type ProviderModels = {
  provider: string;
  models: string[];
  error: string | null;
};

export async function getProviderModels(provider: string): Promise<ProviderModels> {
  const params = new URLSearchParams({ provider });
  return fetchJson<ProviderModels>(`/api/models?${params.toString()}`);
}

export async function updateConfig(body: Record<string, unknown>): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function applyPlan(planId: string, verify = true): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/patch/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ planId, verify }),
  });
}

export async function streamChat(
  message: string,
  history: ChatMessage[],
  onEvent: (event: { type: string; data: Record<string, unknown> }) => void,
): Promise<void> {
  const started = performance.now();
  clientLog("info", "chat", "Chat stream started", {
    messagePreview: message.trim().slice(0, 120),
    historyCount: history.length,
  });
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
      signal: AbortSignal.timeout(240_000),
    });
    if (!response.ok || !response.body) {
      throw new Error(`Chat failed: ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (payload === "[DONE]") {
          clientLog("info", "chat", "Chat stream finished", {
            durationMs: Math.round(performance.now() - started),
          });
          return;
        }
        const event = JSON.parse(payload) as { type: string; data: Record<string, unknown> };
        if (event.type !== "assistant.delta") {
          clientLog("debug", "chat", `SSE ${event.type}`, { type: event.type });
        }
        onEvent(event);
      }
    }
    clientLog("info", "chat", "Chat stream ended without [DONE]", {
      durationMs: Math.round(performance.now() - started),
    });
  } catch (error) {
    clientLog("error", "chat", "Chat stream failed", {
      durationMs: Math.round(performance.now() - started),
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}
