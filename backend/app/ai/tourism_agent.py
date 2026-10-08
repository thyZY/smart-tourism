"""Natural language tourism intent extraction helpers.

Stage 1 only: DeepSeek interprets user intent. POI selection remains database driven.
"""

import json
from typing import Any

from .deepseek_client import DeepSeekClient


SYSTEM_PROMPT = """
You are a tourism intent parser.
Extract only structured travel preferences from user text.
Return JSON with:
- theme
- duration
- constraints
- preferences
Do not invent attractions.
"""


async def parse_tourism_query(
    query: str,
    client: DeepSeekClient | None = None,
) -> dict[str, Any]:
    client = client or DeepSeekClient()

    result = await client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": query},
        ]
    )

    content = result["choices"][0]["message"]["content"]
    return json.loads(content)
