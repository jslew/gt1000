import { useCallback, useEffect, useRef, useState } from "react";
import {
  applyPlan,
  getConfig,
  getDeviceStatus,
  getPatchChain,
  getPatchPreview,
  getProviderModels,
  updateConfig,
  type ChainView,
  type DeviceStatus,
} from "./api";
import { ChainView as ChainPanel } from "./ChainView";
import { ChatPanel } from "./ChatPanel";
import { clientLog } from "./clientLog";
import { StatusBar } from "./StatusBar";

export function App() {
  const [status, setStatus] = useState<DeviceStatus | null>(null);
  const [chain, setChain] = useState<ChainView | null>(null);
  const [chainLoading, setChainLoading] = useState(false);
  const [chainDetailLoading, setChainDetailLoading] = useState(false);
  const [chainError, setChainError] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<string | null>(null);
  const [provider, setProvider] = useState("ollama");
  const [model, setModel] = useState("llama3.2");
  const [openaiKey, setOpenaiKey] = useState("");
  const [openaiKeyFromEnv, setOpenaiKeyFromEnv] = useState(false);
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const chainLoadingRef = useRef(false);
  const pendingChainRefreshRef = useRef(false);
  const modelRef = useRef(model);
  modelRef.current = model;

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await getDeviceStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  const refreshChain = useCallback(async (forceRefresh = false) => {
    if (chainLoadingRef.current) {
      if (forceRefresh) {
        pendingChainRefreshRef.current = true;
      }
      return;
    }
    chainLoadingRef.current = true;
    setChainError(null);
    setChainDetailLoading(true);
    try {
      if (forceRefresh) {
        clientLog("info", "chain", "Loading full patch chain (refresh)");
        setChainLoading(true);
        setChain(await getPatchChain(true));
        return;
      }
      clientLog("info", "chain", "Loading patch preview");
      setChain(await getPatchPreview(false));
      setChainLoading(true);
      clientLog("info", "chain", "Loading full patch chain");
      setChain(await getPatchChain(false));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setChainError(message);
      clientLog("error", "chain", "Chain load failed", { error: message });
    } finally {
      chainLoadingRef.current = false;
      setChainLoading(false);
      setChainDetailLoading(false);
      if (pendingChainRefreshRef.current) {
        pendingChainRefreshRef.current = false;
        void refreshChain(true);
      }
    }
  }, []);

  const refreshModels = useCallback(async (selectedProvider: string, preferredModel?: string) => {
    setModelsLoading(true);
    setModelsError(null);
    try {
      const result = await getProviderModels(selectedProvider);
      setModelOptions(result.models);
      setModelsError(result.error);
      if (result.models.length > 0) {
        const preferred = preferredModel ?? modelRef.current;
        const pickDefault = () => {
          if (selectedProvider === "openai") {
            const defaults = [
              "gpt-5.5",
              "gpt-5.4",
              "gpt-5.2",
              "gpt-5",
              "gpt-4o-mini",
              "gpt-4o",
              "gpt-4.1-mini",
              "gpt-4.1",
              "gpt-4-turbo",
              "gpt-4",
              "gpt-3.5-turbo",
            ];
            for (const candidate of defaults) {
              if (result.models.includes(candidate)) {
                return candidate;
              }
            }
          }
          return result.models[0];
        };
        const nextModel =
          preferred && result.models.includes(preferred) ? preferred : pickDefault();
        setModel(nextModel);
        return nextModel;
      }
    } catch (error) {
      setModelOptions([]);
      setModelsError(error instanceof Error ? error.message : String(error));
    } finally {
      setModelsLoading(false);
    }
    return preferredModel ?? modelRef.current;
  }, []);

  useEffect(() => {
    refreshStatus();
    getConfig()
      .then((config) => {
        const selectedProvider = String(config.provider ?? "ollama");
        const selectedModel = String(config.model ?? "llama3.2");
        setProvider(selectedProvider);
        setModel(selectedModel);
        setOpenaiKeyFromEnv(Boolean(config.openaiApiKeyFromEnv));
        refreshModels(selectedProvider, selectedModel)
          .then(async (resolved) => {
            if (resolved && resolved !== selectedModel) {
              await updateConfig({ provider: selectedProvider, model: resolved });
            }
          })
          .catch(() => undefined);
      })
      .catch(() => undefined);
    refreshChain();
    const interval = window.setInterval(refreshStatus, 2000);
    return () => window.clearInterval(interval);
    // Mount-only bootstrap; do not re-run when model list refresh updates local state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function persistSettings(nextProvider: string, nextModel: string) {
    await updateConfig({
      provider: nextProvider,
      model: nextModel,
      openaiApiKey: openaiKey || undefined,
    });
    setOpenaiKey("");
  }

  async function handleProviderChange(nextProvider: string) {
    setProvider(nextProvider);
    const nextModel = (await refreshModels(nextProvider, modelRef.current)) ?? modelRef.current;
    try {
      await persistSettings(nextProvider, nextModel);
    } catch (error) {
      setModelsError(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/events`);
    socket.onopen = () => {
      setWsConnected(true);
      clientLog("info", "ws", "WebSocket connected");
    };
    socket.onclose = () => {
      setWsConnected(false);
      clientLog("warn", "ws", "WebSocket disconnected");
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as { type: string; data?: Record<string, unknown> };
        setLastEvent(event.type);
        clientLog("debug", "ws", `Event ${event.type}`, { type: event.type });
        if (event.type === "patch.updated") {
          const view = String(event.data?.view ?? "");
          if (view === "apply") {
            refreshChain(true);
          }
        }
        if (event.type.startsWith("device.")) refreshStatus();
      } catch {
        setLastEvent("parse-error");
        clientLog("error", "ws", "WebSocket message parse error");
      }
    };
    return () => socket.close();
  }, [refreshChain, refreshStatus]);

  async function saveConfig() {
    await persistSettings(provider, model);
    await refreshModels(provider, model);
  }

  return (
    <div className="app-shell">
      <StatusBar status={status} wsConnected={wsConnected} lastEvent={lastEvent} />
      <main className="app-grid">
        <ChainPanel
          chain={chain}
          loading={chainLoading}
          detailLoading={chainDetailLoading}
          error={chainError}
          onRefresh={() => refreshChain(true)}
        />
        <ChatPanel />
      </main>
      <footer className="settings-bar">
        <label>
          Provider
          <select
            value={provider}
            onChange={(event) => {
              handleProviderChange(event.target.value).catch(() => undefined);
            }}
          >
            <option value="ollama">Ollama (local)</option>
            <option value="openai">OpenAI (BYO key)</option>
            <option value="mock">Mock</option>
          </select>
        </label>
        <label>
          Model
          {modelOptions.length > 0 ? (
            <select
              value={model}
              disabled={modelsLoading}
              onChange={(event) => setModel(event.target.value)}
            >
              {modelOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={model}
              disabled={modelsLoading}
              onChange={(event) => setModel(event.target.value)}
              placeholder={modelsLoading ? "Loading models…" : "No models found"}
            />
          )}
          {modelsLoading ? <span className="muted">Loading models…</span> : null}
          {modelsError ? <span className="error">{modelsError}</span> : null}
        </label>
        {provider === "openai" ? (
          <label>
            API key
            {openaiKeyFromEnv ? (
              <span className="muted">Using OPENAI_API_KEY from environment</span>
            ) : (
              <input
                type="password"
                value={openaiKey}
                onChange={(event) => setOpenaiKey(event.target.value)}
                placeholder="sk-…"
              />
            )}
          </label>
        ) : null}
        <button type="button" className="secondary" onClick={() => saveConfig().catch(console.error)}>
          Save model settings
        </button>
        <button type="button" className="secondary" onClick={() => refreshChain(true)}>
          Refresh chain
        </button>
        <button
          type="button"
          className="danger"
          onClick={() => applyPlan("default", true).catch(console.error)}
        >
          Apply default plan (verify)
        </button>
      </footer>
    </div>
  );
}
