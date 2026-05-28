import type { APIRequestContext, Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

export const DEFAULT_APP_URL = "http://127.0.0.1:38473";
export const DEFAULT_PROVIDER = "openai";
export const DEFAULT_MODEL = "gpt-5.5";

export function appUrl(): string {
  return (process.env.GT1000_APP_URL ?? DEFAULT_APP_URL).replace(/\/$/, "");
}

export function preferredModel(): string {
  return process.env.GT1000_E2E_MODEL ?? DEFAULT_MODEL;
}

export function skipChain(): boolean {
  return process.env.GT1000_E2E_SKIP_CHAIN === "1";
}

export async function assertBackendHealthy(request: APIRequestContext): Promise<void> {
  const response = await request.get(`${appUrl()}/api/health`);
  if (!response.ok()) {
    throw new Error(
      `Backend not reachable at ${appUrl()} (GET /api/health → ${response.status()}). ` +
        "Start: app/backend/.venv/bin/python app/backend/run_dev.py",
    );
  }
}

export function resolveModelId(models: string[], preferred: string): { model: string; note: string } {
  if (models.includes(preferred)) {
    return { model: preferred, note: "exact match" };
  }
  const lower = preferred.toLowerCase();
  const caseInsensitive = models.find((id) => id.toLowerCase() === lower);
  if (caseInsensitive) {
    return { model: caseInsensitive, note: "case-insensitive match" };
  }
  const contains = models.find((id) => id.toLowerCase().includes(lower));
  if (contains) {
    return { model: contains, note: `substring match for ${preferred}` };
  }
  const gpt5 = models.find((id) => /gpt-5/i.test(id));
  if (gpt5) {
    return { model: gpt5, note: `closest gpt-5 family match (wanted ${preferred})` };
  }
  return { model: preferred, note: "not in model list; using preferred id via config only" };
}

export async function fetchOpenAiModels(request: APIRequestContext): Promise<string[]> {
  const response = await request.get(`${appUrl()}/api/models?provider=openai`);
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`GET /api/models?provider=openai failed (${response.status}): ${body}`);
  }
  const payload = (await response.json()) as { models?: string[]; error?: string | null };
  if (payload.error) {
    throw new Error(`OpenAI model list error: ${payload.error}`);
  }
  return payload.models ?? [];
}

export async function putConfig(
  request: APIRequestContext,
  body: { provider: string; model: string },
): Promise<Record<string, unknown>> {
  const response = await request.put(`${appUrl()}/api/config`, {
    data: body,
  });
  if (!response.ok()) {
    const text = await response.text();
    throw new Error(`PUT /api/config failed (${response.status}): ${text}`);
  }
  return response.json() as Promise<Record<string, unknown>>;
}

export async function chainHasContent(request: APIRequestContext): Promise<boolean> {
  try {
    const response = await request.get(`${appUrl()}/api/patch/chain`, { timeout: 90_000 });
    if (!response.ok()) {
      return false;
    }
    const chain = (await response.json()) as {
      descriptionElements?: unknown[];
      elements?: unknown[];
      descriptionSignalChainSummary?: string;
    };
    const elements = chain.descriptionElements ?? chain.elements ?? [];
    if (Array.isArray(elements) && elements.length > 0) {
      return true;
    }
    return Boolean(chain.descriptionSignalChainSummary?.trim());
  } catch {
    return false;
  }
}

export async function waitForChainUi(page: Page): Promise<void> {
  const chainPanel = page.locator("section.chain-panel");
  await chainPanel.waitFor({ state: "visible", timeout: 30_000 });

  if (skipChain()) {
    console.log("[e2e] GT1000_E2E_SKIP_CHAIN=1 — skipping chain population wait");
    return;
  }

  const apiReady = await chainHasContent(page.request);
  if (!apiReady) {
    console.warn(
      "[e2e] /api/patch/chain has no elements yet (device offline or MIDI blocked). " +
        "Waiting for UI chain nodes anyway…",
    );
  }

  const nodes = chainPanel.locator("article.chain-node");
  const summary = chainPanel.locator("p.chain-summary");
  const loadingDone = chainPanel.locator('button:has-text("From device")').filter({ hasNotText: "Reading…" });

  await loadingDone.waitFor({ state: "visible", timeout: 120_000 }).catch(() => undefined);

  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const nodeCount = await nodes.count();
    const summaryText = (await summary.textContent())?.trim() ?? "";
    const errorText = (await chainPanel.locator("p.error").textContent())?.trim() ?? "";
    if (nodeCount > 0) {
      console.log(`[e2e] Chain UI ready: ${nodeCount} node(s)`);
      return;
    }
    if (summaryText.length > 0) {
      console.log(`[e2e] Chain UI ready: summary present (${summaryText.length} chars)`);
      return;
    }
    if (errorText && !apiReady) {
      throw new Error(
        `Signal chain failed to load: ${errorText}. ` +
          "Connect a GT-1000 with CoreMIDI access, or set GT1000_E2E_SKIP_CHAIN=1 to skip this check.",
      );
    }
    await page.waitForTimeout(500);
  }

  throw new Error(
    "Timed out waiting for signal chain content (no .chain-node elements and no .chain-summary). " +
      "Ensure the backend can read /api/patch/chain from a live device.",
  );
}

export async function selectProviderAndModel(
  page: Page,
  provider: string,
  modelId: string,
): Promise<void> {
  const settings = page.locator("footer.settings-bar");
  const providerSelect = settings.locator('label:has-text("Provider") select');
  const modelSelect = settings.locator('label:has-text("Model") select');
  const modelInput = settings.locator('label:has-text("Model") input');

  await providerSelect.selectOption(provider);
  await page.waitForTimeout(500);

  // Model list loads asynchronously after provider change.
  const modelControl = modelSelect.or(modelInput);
  await modelControl.waitFor({ state: "visible", timeout: 60_000 });

  const hasSelect = (await modelSelect.count()) > 0;
  if (hasSelect) {
    const options = await modelSelect.locator("option").allTextContents();
    const { model, note } = resolveModelId(options, modelId);
    console.log(`[e2e] Selecting model ${model} (${note}); options: ${options.slice(0, 8).join(", ")}…`);
    await modelSelect.selectOption(model);
    await settings.getByRole("button", { name: "Save model settings" }).click();
    return;
  }

  console.log(`[e2e] Model dropdown empty; typing model ${modelId}`);
  await modelInput.fill(modelId);
  await settings.getByRole("button", { name: "Save model settings" }).click();
}

export async function sendChatAndWaitForReply(page: Page, message: string): Promise<string> {
  const panel = page.locator("section.chat-panel");
  const textarea = panel.locator("textarea");
  await textarea.fill(message);
  await panel.getByRole("button", { name: "Send" }).click();

  const assistant = panel.locator("article.chat-message.assistant .chat-body").last();
  const errorLine = panel.locator("p.error");

  const deadline = Date.now() + 240_000;
  while (Date.now() < deadline) {
    const err = (await errorLine.textContent())?.trim();
    if (err) {
      throw new Error(`Chat error in UI: ${err}`);
    }
    const streaming = await textarea.isDisabled();
    const text = (await assistant.textContent())?.trim() ?? "";
    if (text.length > 0 && !streaming) {
      return text;
    }
    await page.waitForTimeout(400);
  }

  const partial = (await assistant.textContent())?.trim() ?? "";
  throw new Error(
    `Timed out waiting for assistant reply (partial length ${partial.length}). ` +
      "Check OPENAI_API_KEY, model id, and /api/logs.",
  );
}

export async function dumpDebugArtifacts(page: Page, request: APIRequestContext, label: string): Promise<void> {
  const outDir = path.resolve("test-results", "debug-dumps");
  fs.mkdirSync(outDir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");

  await page.screenshot({ path: path.join(outDir, `${label}-${stamp}.png`), fullPage: true }).catch(() => undefined);

  let logPaths: Record<string, string> = {};
  try {
    const response = await request.get(`${appUrl()}/api/logs/paths`);
    if (response.ok()) {
      logPaths = (await response.json()) as Record<string, string>;
    }
  } catch {
    // ignore
  }

  console.error("\n=== GT-1000 e2e debug ===");
  console.error(`URL: ${appUrl()}`);
  console.error(`Screenshot: ${path.join(outDir, `${label}-${stamp}.png`)}`);
  if (logPaths.directory) {
    console.error(`Log directory: ${logPaths.directory}`);
    console.error(`Server log file: ${logPaths.server ?? "(unknown)"}`);
    console.error(`Client log file: ${logPaths.client ?? "(unknown)"}`);
  } else {
    console.error(`Log directory (default): ${path.join(process.env.HOME ?? "~", ".gt1000-app/logs")}`);
  }

  for (const source of ["server", "client"] as const) {
    try {
      const response = await request.get(`${appUrl()}/api/logs?source=${source}&limit=40`);
      if (response.ok()) {
        const payload = (await response.json()) as { entries?: Array<Record<string, unknown>> };
        const lines = (payload.entries ?? []).slice(-15);
        console.error(`\n--- Recent ${source} logs (API tail) ---`);
        for (const entry of lines) {
          console.error(JSON.stringify(entry));
        }
      }
    } catch {
      // ignore
    }
  }
  console.error("=========================\n");
}
