"""
AI itinerary planning service.

This module only handles prompt construction and structured response parsing.
API keys are never stored here.
Credentials are loaded by DeepSeekClient from environment variables.
"""

from typing import Any

from .deepseek_client import DeepSeekClient


class ItineraryPlanner:
    """Generate tourism itineraries with LLM assistance."""

    def __init__(self, client: DeepSeekClient | None = None):
        self.client = client or DeepSeekClient()

    def generate(
        self,
        location: str,
        days: int = 1,
        style: str = "文化历史",
        people: str = "普通游客",
        walking_limit: str = "正常",
    ) -> dict[str, Any]:
        prompt = {
            "task": "generate tourism itinerary",
            "location": location,
            "days": days,
            "style": style,
            "people": people,
            "walking_limit": walking_limit,
            "output_format": {
                "title": "string",
                "summary": "string",
                "stops": [
                    {
                        "time": "string",
                        "poi": "string",
                        "reason": "string"
                    }
                ]
            },
        }

        return self.client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": "你是智慧旅游路线规划助手，只输出符合要求的JSON。",
                },
                {
                    "role": "user",
                    "content": str(prompt),
                },
            ]
        )
