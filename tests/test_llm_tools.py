import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "app" / "backend"
for path in (BACKEND_DIR, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gt1000_app.llm_tools import (  # noqa: E402
    normalize_tool_calls,
    to_chat_completions_tools,
)
from gt1000_app.providers import ChatMessage, to_openai_message  # noqa: E402


class LlmToolsTests(unittest.TestCase):
    def test_openai_tool_schema_shape(self) -> None:
        tools = to_chat_completions_tools(
            [
                {
                    "name": "get_patch_block",
                    "description": "Read block",
                    "parameters": {
                        "type": "object",
                        "properties": {"blockId": {"type": "string"}},
                        "required": ["blockId"],
                    },
                }
            ]
        )
        self.assertEqual(tools[0]["type"], "function")
        self.assertEqual(tools[0]["function"]["name"], "get_patch_block")

    def test_normalize_tool_calls_parses_json_arguments(self) -> None:
        calls = normalize_tool_calls(
            [{"id": "c1", "name": "get_patch_block", "arguments": '{"blockId": "dist1"}'}]
        )
        self.assertEqual(calls[0]["arguments"]["blockId"], "dist1")

    def test_tool_message_serializes_for_openai(self) -> None:
        payload = to_openai_message(
            ChatMessage(role="tool", content='{"blockId":"dist1"}', tool_call_id="call_1")
        )
        self.assertEqual(payload["role"], "tool")
        self.assertEqual(payload["tool_call_id"], "call_1")


if __name__ == "__main__":
    unittest.main()
