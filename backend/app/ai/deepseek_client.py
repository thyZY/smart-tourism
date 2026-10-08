"""Minimal DeepSeek API client abstraction.

The API key must be provided through runtime environment variables:

DEEPSEEK_API_KEY=...

Never commit credentials into this repository.
"""

import os
from typing import Any

import httpx


class DeepSeekClient:
    """Small wrapper that keeps provider details away from business logic."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv(
            "DEEPSEEK_BASE_URL",
            "https://api.deepseek.com",
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("DeepSeek API is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
