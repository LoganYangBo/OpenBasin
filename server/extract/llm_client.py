"""Provider-agnostic LLM client.

OpenBasin bundles no model. The extraction layer targets any OpenAI-compatible
``/v1/chat/completions`` endpoint — OpenAI, Anthropic, Ollama, Azure. The
provider is never hardcoded; everything routes through :class:`LLMConfig`.

The Ollama path must work fully offline, so this client adds no mandatory
cloud dependency — it is a thin ``httpx`` POST.
"""

from __future__ import annotations

import httpx

from server.config import LLMConfig


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def _endpoint(self) -> str:
        base = self.config.base_url.rstrip("/")
        # Allow base_url to be given with or without the /chat/completions tail.
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key = self.config.api_key
        if not key:
            return headers
        # Azure uses api-key; everyone else uses Bearer. Both are harmless to send,
        # but we match the provider's expectation to avoid 401s.
        if self.config.provider == "azure":
            headers["api-key"] = key
        else:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    async def complete(self, system: str, user: str) -> str:
        """Return the assistant message content for a system+user prompt."""
        body = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(self._endpoint(), json=body, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected LLM response shape: {data!r}") from exc
