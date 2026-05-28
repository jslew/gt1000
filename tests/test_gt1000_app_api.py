import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "app" / "backend"
for path in (BACKEND_DIR, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi.testclient import TestClient  # noqa: E402

from gt1000_app.agent import AgentService  # noqa: E402
from gt1000_app.app import create_app  # noqa: E402
from gt1000_app.config import AppConfig, load_config  # noqa: E402
from gt1000_app.device import DeviceService  # noqa: E402
from gt1000_app.events import EventBus  # noqa: E402


class GT1000AppApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = EventBus()
        self.device = DeviceService(self.events)
        self.agent = AgentService(self.device, AppConfig(provider="mock", model="mock"))
        self.app = create_app(self.device, self.agent)
        self.client = TestClient(self.app)

    def test_health_and_device_status(self) -> None:
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["ok"])

        status = self.client.get("/api/device/status")
        self.assertEqual(status.status_code, 200)
        self.assertIn("busy", status.json())

    def test_patch_chain_endpoint_uses_device_service(self) -> None:
        sample = {
            "signalChainSummary": "A -> B",
            "elements": [{"id": "chain-1", "displayName": "COMP", "includeInDescription": True}],
            "descriptionElements": [{"id": "chain-1", "displayName": "COMP", "includeInDescription": True}],
        }
        self.device.patch_chain = AsyncMock(return_value=sample)  # type: ignore[method-assign]
        response = self.client.get("/api/patch/chain")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["signalChainSummary"], "A -> B")

    def test_patch_chain_cache_avoids_repeat_device_reads(self) -> None:
        import copy

        sample = {"signalChainSummary": "cached", "elements": []}
        read_count = 0
        device = self.device

        async def fake_patch_read_cached(  # type: ignore[no-untyped-def]
            field: str,
            *,
            label: str,
            force_refresh: bool,
            load,
            thread_timeout: float,
        ) -> dict:
            del label, load, thread_timeout
            nonlocal read_count
            if force_refresh:
                device.invalidate_patch_cache()
            cached = device._cached_value(field)
            if cached is not None:
                return cached
            read_count += 1
            if field == "chain":
                device._store_chain_view(sample)
            else:
                device._store_cached_field(field, sample)
            return copy.deepcopy(sample)

        device._patch_read_cached = fake_patch_read_cached  # type: ignore[method-assign]

        async def run() -> None:
            first = await device.patch_chain()
            second = await device.patch_chain()
            self.assertEqual(first["signalChainSummary"], "cached")
            self.assertEqual(second["signalChainSummary"], "cached")
            self.assertEqual(read_count, 1)
            await device.patch_chain(force_refresh=True)
            self.assertEqual(read_count, 2)
            device.invalidate_patch_cache()
            await device.patch_chain()
            self.assertEqual(read_count, 3)

        asyncio.run(run())

    def test_patch_plan_endpoint(self) -> None:
        self.device.build_plan = AsyncMock(return_value={"id": "default", "writeCount": 3, "writes": []})  # type: ignore[method-assign]
        response = self.client.post("/api/patch/plan", json={"planId": "default"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "default")

    def test_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            os.environ["GT1000_APP_CONFIG_DIR"] = directory
            try:
                response = self.client.put(
                    "/api/config",
                    json={"provider": "mock", "model": "test-model"},
                )
            finally:
                os.environ.pop("GT1000_APP_CONFIG_DIR", None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "mock")
        self.assertEqual(response.json()["model"], "test-model")

    def test_load_skill_reference_routing(self) -> None:
        from gt1000_app.skill_context import load_skill_reference

        loaded = load_skill_reference("skill-routing")
        self.assertNotIn("error", loaded)
        self.assertIn("Progressive Disclosure", loaded.get("content", ""))

    def test_compact_block_payload_for_agent(self) -> None:
        import json
        from pathlib import Path

        from gt1000_app.tool_payload import compact_block_for_agent, tool_results_message
        from skills.gt1000.tools.gt1000 import agent_cli

        fixture = Path(__file__).resolve().parent / "fixtures" / "full_patch.json"
        snapshot = json.loads(fixture.read_text(encoding="utf-8"))
        args = agent_cli.build_parser().parse_args(["patch", "block", "preamp1", "--file", str(fixture)])
        detail = agent_cli.cmd_patch_block(args)
        compact = compact_block_for_agent(detail)
        self.assertEqual(compact["blockId"], "preamp1")
        self.assertTrue(compact["parameters"])
        self.assertEqual(compact["parameters"][0]["id"], "sw")
        self.assertNotIn("rawDataHex", json.dumps(compact))
        message = tool_results_message([{"name": "get_patch_block", "result": detail}])
        self.assertIn("preamp1", message)
        self.assertIn("DIAMOND AMP", message)

    def test_compact_chain_payload_for_agent(self) -> None:
        import json
        from pathlib import Path

        from gt1000_app.tool_payload import compact_chain_for_agent, tool_results_message

        fixture = Path(__file__).resolve().parent / "fixtures" / "full_patch.json"
        snapshot = json.loads(fixture.read_text(encoding="utf-8"))
        from skills.gt1000.tools.gt1000 import agent_cli

        chain = agent_cli.chain_from_full(snapshot)
        compact = compact_chain_for_agent(chain)
        self.assertIn("descriptionElements", compact)
        self.assertIn("signalOrderElements", compact)
        self.assertNotIn("activeAssigns", json.dumps(compact))
        message = tool_results_message([{"name": "get_patch_chain", "result": chain}])
        self.assertLess(len(message), 120_000)

    def test_strip_tool_calls_from_assistant_text(self) -> None:
        from gt1000_app.chat_display import VisibleStreamFilter, parse_tool_calls, strip_tool_calls

        raw = 'Checking…\n<tool_call>{"name": "get_patch_chain", "arguments": {}}</tool_call>\n\nDone.'
        self.assertNotIn("tool_call", strip_tool_calls(raw))
        nested = '<tool_call>{"name": "load_skill_reference", "arguments": {"docId": "midi-assigns"}}</tool_call>'
        parsed = parse_tool_calls(nested)
        self.assertEqual(parsed[0]["name"], "load_skill_reference")
        self.assertEqual(parsed[0]["arguments"]["docId"], "midi-assigns")
        filt = VisibleStreamFilter()
        parts = [filt.feed(part) for part in ("<tool_", "call>{\"name\": \"x\"}</tool_call>", " Hello")]
        self.assertEqual("".join(parts) + filt.flush(), " Hello")

    def test_openai_chat_model_filter_excludes_image_models(self) -> None:
        from gt1000_app.providers import is_openai_chat_model

        self.assertFalse(is_openai_chat_model("chatgpt-image-latest"))
        self.assertTrue(is_openai_chat_model("gpt-4o-mini"))

    def test_live_worker_timeout_exceeds_request_timeout(self) -> None:
        self.assertGreater(DeviceService.live_worker_timeout(25.0), 25.0)

    def test_list_models_mock_provider(self) -> None:
        response = self.client.get("/api/models", params={"provider": "mock"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["models"], ["mock"])

    def test_openai_api_key_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            os.environ["GT1000_APP_CONFIG_DIR"] = directory
            os.environ["OPENAI_API_KEY"] = "test-env-key"
            try:
                config = load_config()
                self.assertEqual(config.openai_api_key, "test-env-key")
                response = self.client.get("/api/config")
            finally:
                os.environ.pop("GT1000_APP_CONFIG_DIR", None)
                os.environ.pop("OPENAI_API_KEY", None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("openaiApiKeyFromEnv"))

    def test_client_log_ingest_and_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            os.environ["GT1000_APP_LOG_DIR"] = directory
            try:
                response = self.client.post(
                    "/api/logs/client",
                    json={
                        "entries": [
                            {
                                "level": "info",
                                "category": "test",
                                "message": "client test line",
                                "ts": "2026-01-01T00:00:00+00:00",
                            }
                        ]
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["ingested"], 1)

                paths = self.client.get("/api/logs/paths")
                self.assertEqual(paths.status_code, 200)
                self.assertTrue(str(paths.json()["client"]).endswith("client.jsonl"))

                tail = self.client.get("/api/logs", params={"source": "client", "limit": 5})
                self.assertEqual(tail.status_code, 200)
                messages = [entry["message"] for entry in tail.json()["entries"]]
                self.assertIn("client test line", messages)
            finally:
                os.environ.pop("GT1000_APP_LOG_DIR", None)

    def test_block_parameter_question_uses_native_tool_call(self) -> None:
        from unittest.mock import patch

        from gt1000_app.providers import MockProvider

        self.device.patch_block = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "block": {
                    "id": "dist1",
                    "displayName": "DISTORTION 1",
                    "typeName": "T-SCREAM",
                    "isEnabled": True,
                    "parameters": [
                        {"id": "sw", "displayName": "SW", "displayValue": "ON"},
                        {"id": "drive", "displayName": "DRIVE", "displayValue": "45"},
                    ],
                },
                "overview": {"patchName": "IMPRESSION"},
                "chainPositions": [2],
            }
        )
        mock_provider = MockProvider(
            response="DIST 1 is on with T-SCREAM.",
            tool_calls=[
                {"id": "call_dist1", "name": "get_patch_block", "arguments": {"blockId": "dist1"}},
            ],
        )

        async def run() -> None:
            tool_names: list[str] = []
            with patch("gt1000_app.agent.build_provider", return_value=mock_provider):
                async for event in self.agent.stream_chat(
                    "What are the dist 1 parameters for the current patch?"
                ):
                    if event.type == "tool.start":
                        tool_names.append(str(event.data.get("name")))
            self.assertEqual(tool_names, ["get_patch_block"])
            self.device.patch_block.assert_awaited_once_with("dist1")  # type: ignore[attr-defined]

        asyncio.run(run())

    def test_chat_stream_mock_provider(self) -> None:
        async def run() -> None:
            events = []
            async for event in self.agent.stream_chat("hello"):
                events.append(event)
            self.assertTrue(any(item.type == "assistant.done" for item in events))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
