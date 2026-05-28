import { test } from "@playwright/test";
import {
  DEFAULT_PROVIDER,
  assertBackendHealthy,
  dumpDebugArtifacts,
  fetchOpenAiModels,
  preferredModel,
  putConfig,
  resolveModelId,
  selectProviderAndModel,
  sendChatAndWaitForReply,
  waitForChainUi,
} from "../lib/helpers.js";

const CHAT_PROMPT = "What is the difference between the two div1 branches?";

test.describe("Test case 1", () => {
  test("chain, OpenAI gpt-5.5, div1 branch question", async ({ page, request }) => {
    let failed = false;
    try {
      await assertBackendHealthy(request);

      const wantedModel = preferredModel();
      let models: string[] = [];
      try {
        models = await fetchOpenAiModels(request);
      } catch (error) {
        console.warn(`[e2e] Could not list OpenAI models: ${error}`);
      }

      const { model: resolvedModel, note } = resolveModelId(models, wantedModel);
      console.log(`[e2e] Configuring API: provider=${DEFAULT_PROVIDER} model=${resolvedModel} (${note})`);
      await putConfig(request, { provider: DEFAULT_PROVIDER, model: resolvedModel });

      await page.goto("/");
      await waitForChainUi(page);

      await selectProviderAndModel(page, DEFAULT_PROVIDER, resolvedModel);

      const providerValue = await page.locator('footer.settings-bar label:has-text("Provider") select').inputValue();
      const modelControl = page.locator('footer.settings-bar label:has-text("Model") select').or(
        page.locator('footer.settings-bar label:has-text("Model") input'),
      );
      const modelValue =
        (await page.locator('footer.settings-bar label:has-text("Model") select').count()) > 0
          ? await page.locator('footer.settings-bar label:has-text("Model") select').inputValue()
          : await page.locator('footer.settings-bar label:has-text("Model") input').inputValue();

      console.log(`[e2e] UI settings: provider=${providerValue} model=${modelValue}`);
      test.expect(providerValue).toBe(DEFAULT_PROVIDER);
      const modelOk =
        modelValue === resolvedModel ||
        modelValue.toLowerCase() === resolvedModel.toLowerCase() ||
        modelValue.toLowerCase().includes(wantedModel.toLowerCase()) ||
        resolvedModel.toLowerCase().includes(modelValue.toLowerCase());
      test.expect(modelOk, `UI model ${modelValue} should match ${resolvedModel}`).toBeTruthy();

      const reply = await sendChatAndWaitForReply(page, CHAT_PROMPT);
      console.log(`[e2e] Assistant reply (${reply.length} chars): ${reply.slice(0, 200)}…`);
      test.expect(reply.length).toBeGreaterThan(0);
    } catch (error) {
      failed = true;
      await dumpDebugArtifacts(page, request, "test-case-1");
      throw error;
    } finally {
      if (!failed) {
        console.log("[e2e] Test case 1 passed.");
      }
    }
  });
});
