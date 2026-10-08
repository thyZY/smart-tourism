"""Minimal async DeepSeek JSON client using only Python standard library HTTP.

No API key, user prompt, or provider response is logged. Configure the secret in
backend/.env; never commit .env. External requests happen only when a key exists.
"""
import asyncio
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class DeepSeekClient:
    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).rstrip("/")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    @property
    def enabled(self):
        return bool(self.api_key and self.api_key.strip())

    def _complete(self, messages):
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 360,
            "response_format": {"type": "json_object"},
        }, ensure_ascii=False).encode("utf-8")
        req = Request(
            self.base_url + "/chat/completions",
            data=payload,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(req, timeout=12) as response:
            result = json.load(response)
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("DeepSeek intent JSON must be an object")
        return parsed

    async def chat_json(self, messages):
        if not self.enabled:
            raise RuntimeError("DeepSeek API key not configured")
        return await asyncio.to_thread(self._complete, messages)
