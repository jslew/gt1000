# GT-1000 Localhost App

Local web app with agent chat, signal-chain visualization, and live GT-1000 device status.

## Prerequisites

- macOS with CoreMIDI access to a connected GT-1000
- Python 3
- Node.js 20+ (for the frontend dev server or build)

## Backend

```sh
python3 -m venv app/backend/.venv
app/backend/.venv/bin/pip install -r app/backend/requirements.txt
app/backend/.venv/bin/python app/backend/run_dev.py
```

Backend listens on `http://127.0.0.1:38473`.

## Frontend (development)

```sh
cd app/frontend
npm install
npm run dev
```

Vite proxies `/api` and `/ws` to the backend.

## Frontend (production bundle served by backend)

```sh
cd app/frontend
npm install
npm run build
app/backend/.venv/bin/python app/backend/run_dev.py
```

Open `http://127.0.0.1:38473`.

## Model configuration

Settings are stored in `~/.gt1000-app/config.json`.

- **Ollama (default):** `provider: ollama`, ensure Ollama is running locally.
- **OpenAI BYO key:** set `provider: openai` and export `OPENAI_API_KEY`, or set `openaiApiKey` via the UI/config file. Environment wins over the config file and is never written to disk.
- Optional: `OPENAI_BASE_URL` for compatible API endpoints.
- **GPT-5.x** models use the OpenAI **Responses** API with `openaiReasoningEffort` (default `low`) and `openaiTextVerbosity` (default `low` for concise replies). Override via config or `OPENAI_REASONING_EFFORT` / `OPENAI_TEXT_VERBOSITY`.
- **Mock (tests/offline):** `provider: mock`

The UI loads available models from `GET /api/models` (Ollama `/api/tags`, OpenAI `/v1/models`).

## Agent skill (progressive disclosure)

Chat uses native LLM function/tool calling (OpenAI Chat Completions / Ollama tools API). The model chooses tools such as `get_patch_block`, `get_patch_chain`, and `load_skill_reference` (bundled `skills/gt1000` docs on demand). Up to four tool rounds per turn, then a streamed answer.

## Live verification

With a connected GT-1000:

```sh
curl -s http://127.0.0.1:38473/api/ports
curl -s http://127.0.0.1:38473/api/patch/preview
curl -s http://127.0.0.1:38473/api/patch/chain
```

Destructive writes should use disposable user slots and `--verify` flows from the CLI until you explicitly confirm UI apply targets.

## Debug logs

Server and browser logs are appended as JSON lines under `~/.gt1000-app/logs/` (override with `GT1000_APP_LOG_DIR`):

- `server.jsonl` — HTTP requests, chat/agent events, device busy/idle/errors
- `client.jsonl` — browser API calls, chat SSE, WebSocket events (posted from the UI)

Tail recent entries:

```sh
curl -s 'http://127.0.0.1:38473/api/logs?source=server&limit=50' | python3 -m json.tool
curl -s 'http://127.0.0.1:38473/api/logs?source=client&limit=50' | python3 -m json.tool
curl -s http://127.0.0.1:38473/api/logs/paths
```

Or from the shell:

```sh
tail -f ~/.gt1000-app/logs/server.jsonl
tail -f ~/.gt1000-app/logs/client.jsonl
```

## Tests

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_gt1000_app_chain tests.test_gt1000_app_api -q
```

## E2E automation (Playwright)

Repeatable UI flow for agent debugging lives in `app/scripts/e2e/`.

### Prerequisites

1. Backend running (`app/backend/run_dev.py`) and reachable at `http://127.0.0.1:38473` (override with `GT1000_APP_URL`).
2. Frontend available via production build (`npm run build` in `app/frontend`, then open the backend URL) **or** Vite dev with proxy on the same origin you pass to Playwright.
3. **OpenAI:** export `OPENAI_API_KEY` (or save a key in `~/.gt1000-app/config.json`). Test case 1 targets **OpenAI** and model **`gpt-5.5`** (override with `GT1000_E2E_MODEL`). If that id is missing from `GET /api/models`, the harness picks the closest `gpt-5*` id and sets it via `PUT /api/config` before driving the UI.
4. **Signal chain:** a connected GT-1000 with working live MIDI (`/api/patch/chain` returns `descriptionElements` or `elements`). Without hardware, the run fails unless you set `GT1000_E2E_SKIP_CHAIN=1` (chat/settings only).

Logs: `~/.gt1000-app/logs/` (`server.jsonl`, `client.jsonl`), also `GET /api/logs` and `GET /api/logs/paths`.

### Test case 1

Waits for the chain visualization, selects OpenAI + `gpt-5.5`, sends  
`What is the difference between the two div1 branches?`, and waits for a non-empty assistant reply.

```sh
chmod +x app/scripts/e2e/run-test-case-1.sh
export OPENAI_API_KEY=sk-…   # required for OpenAI chat
./app/scripts/e2e/run-test-case-1.sh
```

Manual equivalent:

```sh
cd app/scripts/e2e
npm install
npx playwright install chromium
GT1000_APP_URL=http://127.0.0.1:38473 npm run test:case1
```

Headed browser: `GT1000_E2E_HEADED=1 npm run test:case1:headed` from `app/scripts/e2e/`.

On failure the harness exits non-zero, saves a screenshot under `app/scripts/e2e/test-results/`, and prints log paths plus recent `/api/logs` tail.
