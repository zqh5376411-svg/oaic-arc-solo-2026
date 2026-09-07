"""Tiny OpenAI-compatible chat-completions client."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenAIChatClient:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> "OpenAIChatClient":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
        model = os.environ.get("MODEL", "").strip()
        missing = [
            name
            for name, value in (
                ("OPENAI_API_KEY", api_key),
                ("OPENAI_BASE_URL", base_url),
                ("MODEL", model),
            )
            if not value
        ]
        if missing:
            raise ValueError("missing model environment: " + ", ".join(missing))
        timeout = int(os.environ.get("JIANXIAN_MODEL_TIMEOUT", "120"))
        return cls(api_key, base_url, model, timeout)

    @property
    def endpoint(self) -> str:
        value = self.base_url.rstrip("/")
        return value if value.endswith("/chat/completions") else value + "/chat/completions"

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        body = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(2000).decode("utf-8", errors="replace")
            raise RuntimeError(f"model gateway returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"model gateway request failed: {exc}") from exc

        try:
            message = payload["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("model gateway response has no assistant message") from exc
        if not isinstance(message, dict):
            raise RuntimeError("model gateway assistant message is invalid")
        return message
