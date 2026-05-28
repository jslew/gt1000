from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol

import httpx

from gt1000_app.config import AppConfig
from gt1000_app.llm_tools import normalize_tool_calls, to_chat_completions_tools, to_ollama_tools


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ChatChunk:
    content: str = ""
    done: bool = False


@dataclass(frozen=True)
class ChatCompletion:
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def to_openai_message(message: ChatMessage) -> dict[str, Any]:
    if message.role == "tool":
        if not message.tool_call_id:
            raise ValueError("tool messages require tool_call_id")
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content,
        }
    if message.role == "assistant" and message.tool_calls:
        payload: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or None,
            "tool_calls": [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call.get("arguments") or {}),
                    },
                }
                for call in message.tool_calls
                if call.get("id") and call.get("name")
            ],
        }
        return payload
    return {"role": message.role, "content": message.content}


class LLMProvider(Protocol):
    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[ChatChunk]:
        ...

    async def complete_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> ChatCompletion:
        ...


def uses_openai_responses_api(model_id: str) -> bool:
    lowered = model_id.lower()
    return lowered.startswith("gpt-5") or lowered.startswith("o1") or lowered.startswith("o3") or lowered.startswith("o4")


def messages_for_responses_api(messages: list[ChatMessage]) -> tuple[str | None, list[dict[str, Any]]]:
    instructions: str | None = None
    input_items: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "system":
            instructions = (
                f"{instructions}\n\n{message.content}".strip()
                if instructions
                else message.content
            )
            continue
        if message.role == "tool" and message.tool_call_id:
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": message.tool_call_id,
                    "output": message.content,
                }
            )
            continue
        input_items.append({"role": message.role, "content": message.content})
    return instructions, input_items


def _openai_error_detail(response: httpx.Response) -> str:
    body = response.content.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(body)
        message = (parsed.get("error") or {}).get("message")
        if isinstance(message, str) and message:
            return message
    except json.JSONDecodeError:
        pass
    return body


class OpenAIProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str = "low",
        text_verbosity: str = "low",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._text_verbosity = text_verbosity

    async def complete_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> ChatCompletion:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [to_openai_message(message) for message in messages],
            "tools": tools,
            "tool_choice": "auto",
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            if response.status_code >= 400:
                raise ValueError(
                    f"OpenAI tool request failed ({response.status_code}): "
                    f"{_openai_error_detail(response)}"
                )
            data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        raw_calls = message.get("tool_calls") or []
        parsed_calls = []
        for call in raw_calls:
            if not isinstance(call, dict):
                continue
            function = call.get("function") or {}
            parsed_calls.append(
                {
                    "id": str(call.get("id") or ""),
                    "name": str(function.get("name") or ""),
                    "arguments": function.get("arguments"),
                }
            )
        return ChatCompletion(
            content=str(message.get("content") or ""),
            tool_calls=normalize_tool_calls(parsed_calls),
        )

    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[ChatChunk]:
        if not is_openai_chat_model(self._model):
            raise ValueError(
                f"Model {self._model!r} is not supported for chat completions. "
                "Choose a GPT chat model such as gpt-4o-mini."
            )
        if uses_openai_responses_api(self._model):
            async for chunk in self._stream_responses(messages):
                yield chunk
            return
        async for chunk in self._stream_chat_completions(messages):
            yield chunk

    async def _stream_chat_completions(self, messages: list[ChatMessage]) -> AsyncIterator[ChatChunk]:
        payload = {
            "model": self._model,
            "messages": [to_openai_message(message) for message in messages],
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    raise ValueError(
                        f"OpenAI chat request failed ({response.status_code}): "
                        f"{_openai_error_detail(response)}"
                    )
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        yield ChatChunk(done=True)
                        return
                    data = json.loads(data_text)
                    delta = (data.get("choices") or [{}])[0].get("delta") or {}
                    content = delta.get("content") or ""
                    if content:
                        yield ChatChunk(content=content)
        yield ChatChunk(done=True)

    async def _stream_responses(self, messages: list[ChatMessage]) -> AsyncIterator[ChatChunk]:
        instructions, input_items = messages_for_responses_api(messages)
        payload: dict[str, Any] = {
            "model": self._model,
            "input": input_items,
            "stream": True,
            "reasoning": {"effort": self._reasoning_effort},
            "text": {"verbosity": self._text_verbosity},
        }
        if instructions:
            payload["instructions"] = instructions
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/responses",
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    raise ValueError(
                        f"OpenAI responses request failed ({response.status_code}): "
                        f"{_openai_error_detail(response)}"
                    )
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        yield ChatChunk(done=True)
                        return
                    try:
                        data = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue
                    if data.get("type") == "response.output_text.delta":
                        delta = data.get("delta") or ""
                        if delta:
                            yield ChatChunk(content=delta)
                    if data.get("type") == "response.completed":
                        yield ChatChunk(done=True)
                        return
        yield ChatChunk(done=True)


class OllamaProvider:
    def __init__(self, *, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def complete_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> ChatCompletion:
        payload = {
            "model": self._model,
            "messages": [to_openai_message(message) for message in messages],
            "tools": tools,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        message = data.get("message") or {}
        raw_calls = message.get("tool_calls") or []
        parsed_calls = []
        for call in raw_calls:
            if not isinstance(call, dict):
                continue
            function = call.get("function") or {}
            parsed_calls.append(
                {
                    "id": str(call.get("id") or ""),
                    "name": str(function.get("name") or ""),
                    "arguments": function.get("arguments"),
                }
            )
        return ChatCompletion(
            content=str(message.get("content") or ""),
            tool_calls=normalize_tool_calls(parsed_calls),
        )

    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[ChatChunk]:
        payload = {
            "model": self._model,
            "messages": [to_openai_message(message) for message in messages],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self._base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message") or {}
                    content = message.get("content") or ""
                    if content:
                        yield ChatChunk(content=content)
                    if data.get("done"):
                        yield ChatChunk(done=True)
                        return
        yield ChatChunk(done=True)


class MockProvider:
    def __init__(
        self,
        *,
        response: str = "Mock response.",
        tool_calls: list[dict[str, Any]] | None = None,
        tool_calls_once: bool = True,
    ) -> None:
        self._response = response
        self._tool_calls = tool_calls or []
        self._tool_calls_once = tool_calls_once
        self._tools_sent = False

    async def complete_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> ChatCompletion:
        if self._tool_calls_once and self._tools_sent:
            return ChatCompletion()
        if self._tool_calls:
            self._tools_sent = True
            return ChatCompletion(tool_calls=list(self._tool_calls))
        return ChatCompletion()

    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(content=self._response)
        yield ChatChunk(done=True)


def openai_tools_for_provider(provider_name: str, definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if provider_name in {"ollama", "local"}:
        return to_ollama_tools(definitions)
    return to_chat_completions_tools(definitions)


def is_openai_chat_model(model_id: str) -> bool:
    lowered = model_id.lower()
    blocked = (
        "embed",
        "tts",
        "whisper",
        "dall-e",
        "transcribe",
        "realtime",
        "audio",
        "moderation",
        "davinci",
        "image",
        "gpt-image",
        "codex",
        "instruct",
        "search",
        "similarity",
    )
    if any(token in lowered for token in blocked):
        return False
    if lowered.startswith(("gpt-", "chatgpt-", "o1", "o3", "o4")):
        return True
    if "gpt-5" in lowered:
        return True
    return lowered in {"o1", "o1-mini", "o1-preview", "o3-mini"}


HTTP_TIMEOUT = httpx.Timeout(12.0, connect=3.0)


async def fetch_ollama_models(base_url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(f"{base_url.rstrip('/')}/api/tags")
        response.raise_for_status()
        payload = response.json()
    models = []
    for entry in payload.get("models", []):
        if isinstance(entry, dict):
            name = entry.get("name") or entry.get("model")
            if isinstance(name, str) and name:
                models.append(name)
    return sorted(set(models), key=str.lower)


async def fetch_openai_models(*, api_key: str, base_url: str) -> list[str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
        response.raise_for_status()
        payload = response.json()
    models = []
    for entry in payload.get("data", []):
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if isinstance(model_id, str) and model_id:
            models.append(model_id)
    chat_models = [model_id for model_id in models if is_openai_chat_model(model_id)]
    return sorted(set(chat_models), key=str.lower)


def preferred_openai_chat_model(models: list[str]) -> str | None:
    if not models:
        return None
    preferred_order = [
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
        "o4-mini",
        "o3-mini",
        "o1",
    ]
    model_set = set(models)
    for candidate in preferred_order:
        if candidate in model_set:
            return candidate
    return models[0]


async def list_provider_models(config: AppConfig, *, provider: str | None = None) -> dict[str, Any]:
    selected = (provider or config.provider).strip().lower()
    if selected == "mock":
        return {"provider": "mock", "models": ["mock"], "error": None}
    if selected in {"ollama", "local"}:
        try:
            models = await fetch_ollama_models(config.ollama_base_url)
            return {"provider": selected, "models": models, "error": None}
        except Exception as error:
            return {"provider": selected, "models": [], "error": str(error)}
    if selected == "openai":
        if not config.openai_api_key:
            return {
                "provider": "openai",
                "models": [],
                "error": "OpenAI API key is not configured. Set OPENAI_API_KEY or save a key in settings.",
            }
        try:
            models = await fetch_openai_models(api_key=config.openai_api_key, base_url=config.openai_base_url)
            return {"provider": "openai", "models": models, "error": None}
        except Exception as error:
            return {"provider": "openai", "models": [], "error": str(error)}
    return {"provider": selected, "models": [], "error": f"unsupported provider {selected}"}


def build_provider(config: AppConfig) -> LLMProvider:
    provider = config.provider.strip().lower()
    if provider == "openai":
        if not config.openai_api_key:
            raise ValueError("OpenAI provider requires OPENAI_API_KEY or openaiApiKey in config")
        if not is_openai_chat_model(config.model):
            preferred = preferred_openai_chat_model(
                ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
            )
            raise ValueError(
                f"Model {config.model!r} is not supported for chat completions. "
                f"Choose a chat model such as {preferred or 'gpt-4o-mini'}."
            )
        return OpenAIProvider(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=config.model,
            reasoning_effort=config.openai_reasoning_effort,
            text_verbosity=config.openai_text_verbosity,
        )
    if provider in {"ollama", "local"}:
        return OllamaProvider(base_url=config.ollama_base_url, model=config.model)
    if provider == "mock":
        return MockProvider()
    raise ValueError(f"unsupported provider {config.provider}")
