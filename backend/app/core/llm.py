"""Frino OS - LLM Abstraction Layer
Supports: Google Gemini, Groq, DeepSeek, OpenAI, Ollama
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Optional


@dataclass
class LLMMessage:
    role: str  # system, user, assistant
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_used: int = 0
    finish_reason: str = "stop"


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        pass

    @abstractmethod
    async def stream(self, messages: List[LLMMessage], **kwargs) -> AsyncGenerator[str, None]:
        pass


class OpenAICompatibleProvider(LLMProvider):
    """Works with any OpenAI-compatible API: OpenAI, Groq, DeepSeek, OpenRouter."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def generate(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        import httpx
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=payload, timeout=60.0
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            return LLMResponse(
                content=choice["message"]["content"],
                model=self.model,
                tokens_used=data.get("usage", {}).get("total_tokens", 0),
                finish_reason=choice.get("finish_reason", "stop")
            )

    async def stream(self, messages: List[LLMMessage], **kwargs) -> AsyncGenerator[str, None]:
        import httpx
        import json
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1024),
            "stream": True,
        }
        timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions",
                headers=headers, json=payload, timeout=timeout
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def generate(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        import httpx
        # Convert messages to Gemini format with strict alternation
        system_text = ""
        contents = []
        for m in messages:
            if m.role == "system":
                system_text = m.content
            else:
                role = "user" if m.role == "user" else "model"
                if contents and contents[-1]["role"] == role:
                    contents[-1]["parts"][0]["text"] += "\n" + m.content
                else:
                    contents.append({"role": role, "parts": [{"text": m.content}]})
        # Must start with user turn
        if contents and contents[0]["role"] == "model":
            contents = contents[1:]

        payload = {"contents": contents}
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        payload["generationConfig"] = {
            "temperature": kwargs.get("temperature", 0.7),
            "maxOutputTokens": kwargs.get("max_tokens", 1024),
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}",
                json=payload, timeout=60.0
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
            return LLMResponse(content=text, model=self.model, tokens_used=tokens)

    async def stream(self, messages: List[LLMMessage], **kwargs) -> AsyncGenerator[str, None]:
        import httpx
        import json
        system_text = ""
        contents = []
        for m in messages:
            if m.role == "system":
                system_text = m.content
            else:
                role = "user" if m.role == "user" else "model"
                # Gemini requires strict alternation — merge consecutive same-role turns
                if contents and contents[-1]["role"] == role:
                    contents[-1]["parts"][0]["text"] += "\n" + m.content
                else:
                    contents.append({"role": role, "parts": [{"text": m.content}]})
        # Must start with user turn
        if contents and contents[0]["role"] == "model":
            contents = contents[1:]

        payload = {"contents": contents}
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        payload["generationConfig"] = {
            "temperature": kwargs.get("temperature", 0.7),
            "maxOutputTokens": kwargs.get("max_tokens", 1024),
        }

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}",
                json=payload, timeout=60.0
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                yield parts[0]["text"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue


class OllamaProvider(LLMProvider):
    """Provider for Ollama local models."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": [{"role": m.role, "content": m.content} for m in messages], "stream": False},
                timeout=120.0
            )
            data = resp.json()
            return LLMResponse(
                content=data["message"]["content"],
                model=self.model,
                tokens_used=data.get("eval_count", 0)
            )

    async def stream(self, messages: List[LLMMessage], **kwargs) -> AsyncGenerator[str, None]:
        import httpx
        import json
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": [{"role": m.role, "content": m.content} for m in messages], "stream": True},
                timeout=120.0
            ) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]


class LLMRouter:
    """Routes to appropriate LLM provider based on config."""

    def __init__(self):
        self.providers = {}  # type: Dict[str, LLMProvider]
        self.default_provider = None  # type: Optional[str]

    def register(self, name: str, provider: LLMProvider, default: bool = False):
        self.providers[name] = provider
        if default or not self.default_provider:
            self.default_provider = name

    async def generate(self, messages: List[LLMMessage],
                       provider: str = None, **kwargs) -> LLMResponse:
        name = provider or self.default_provider
        if name not in self.providers:
            raise ValueError(f"Provider '{name}' not registered")
        return await self.providers[name].generate(messages, **kwargs)

    async def stream(self, messages: List[LLMMessage],
                     provider: str = None, **kwargs) -> AsyncGenerator[str, None]:
        name = provider or self.default_provider
        if name not in self.providers:
            raise ValueError(f"Provider '{name}' not registered")
        async for token in self.providers[name].stream(messages, **kwargs):
            yield token
