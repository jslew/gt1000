export type ClientLogLevel = "debug" | "info" | "warn" | "error";

export type ClientLogEntry = {
  level: ClientLogLevel;
  category: string;
  message: string;
  data?: Record<string, unknown>;
  ts: string;
};

const queue: ClientLogEntry[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let flushing = false;

function scheduleFlush(): void {
  if (flushTimer !== null) {
    return;
  }
  flushTimer = setTimeout(() => {
    flushTimer = null;
    void flushClientLogs();
  }, 1500);
}

export function clientLog(
  level: ClientLogLevel,
  category: string,
  message: string,
  data?: Record<string, unknown>,
): void {
  const entry: ClientLogEntry = {
    level,
    category,
    message,
    data,
    ts: new Date().toISOString(),
  };
  queue.push(entry);
  const consoleFn =
    level === "error"
      ? console.error
      : level === "warn"
        ? console.warn
        : level === "debug"
          ? console.debug
          : console.info;
  consoleFn(`[gt1000:${category}]`, message, data ?? "");
  scheduleFlush();
}

export async function flushClientLogs(): Promise<void> {
  if (flushing || queue.length === 0) {
    return;
  }
  flushing = true;
  const batch = queue.splice(0, 100);
  try {
    await fetch("/api/logs/client", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries: batch }),
      keepalive: true,
    });
  } catch (error) {
    queue.unshift(...batch);
    console.warn("[gt1000:logging] failed to flush client logs", error);
  } finally {
    flushing = false;
    if (queue.length > 0) {
      scheduleFlush();
    }
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    void flushClientLogs();
  });
}
