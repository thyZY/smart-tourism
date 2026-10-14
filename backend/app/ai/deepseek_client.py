import json
import os

from openai import OpenAI


class DeepSeekClient:
    """Wrapper for DeepSeek compatible OpenAI API."""

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv(
            "DEEPSEEK_BASE_URL",
            "https://api.deepseek.com"
        )
        self.model = os.getenv(
            "DEEPSEEK_MODEL",
            "deepseek-chat"
        )

        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def chat_json(self, system_prompt: str, user_prompt: str):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        return json.loads(content)
