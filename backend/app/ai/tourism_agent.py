"""Trust-boundary between an external language model and grounded POI queries."""
import re
from ..natural_language import parse_intent
from .deepseek_client import DeepSeekClient

ALLOWED_CATEGORIES = (
    "博物馆", "历史文化", "陵园景区", "寺庙宗教",
    "城市公园", "自然景区", "古迹遗址", "文化商业",
)
SYSTEM_PROMPT = (
    "你只负责解析南京旅游的中文用户需求，必须只输出 JSON 对象，不要解释、不要推荐景点。"
    "字段必须包含 categories（只能从以下类别中选取的字符串数组）、"
    "avoid_categories（同样的类别数组）、nearby（布尔值）、radius_km（数字或null）、"
    "duration_days（1/2/3或null）、walking_level（low/normal或null）。"
    "合法类别：" + "、".join(ALLOWED_CATEGORIES) + "。"
    "不要根据'不喜欢某类景点'将该类别放入正向 categories。"
    "预算、实时开放时间、路网、时刻表无法由你判断。只返回JSON。"
)


def _categories(value):
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(item for item in value
                              if isinstance(item, str) and item in ALLOWED_CATEGORIES))


def fallback_intent(query):
    parsed = parse_intent(query)
    days = next((days for terms, days in (
        (("三天", "3天"), 3), (("两天", "2天"), 2), (("一天", "1天"), 1),
    ) if any(term in query for term in terms)), None)
    walking = "low" if any(word in query for word in
        ("少走路", "不想走太多", "不累", "轻松", "老人", "腿脚不便")) else None
    # Existing rule parser intentionally refuses exclusions; preserve that safety.
    return {
        "categories": list(parsed.categories),
        "avoid_categories": [],
        "nearby": parsed.nearby,
        "radius_m": parsed.radius_m,
        "duration_days": days,
        "walking_level": walking,
    }


def normalize_model_intent(raw, query):
    """Validate untrusted model output: never accept invented categories/coordinates."""
    if not isinstance(raw, dict):
        raise ValueError("Model intent is not an object")
    local = fallback_intent(query)
    categories = _categories(raw.get("categories"))
    avoid = _categories(raw.get("avoid_categories"))
    if not categories and not avoid:
        categories = local["categories"]
    categories = [item for item in categories if item not in avoid]
    near = raw.get("nearby")
    # Never let model output override an explicit nearby request in user text.
    nearby = local["nearby"] or (near if isinstance(near, bool) else False)
    radius = raw.get("radius_km")
    radius_m = local["radius_m"]
    # Explicit distance in the user's own text always wins over the model.
    # When the user only says "nearby", a valid model radius can refine the
    # rule parser's default 5 km radius.
    user_provided_distance = re.search(r"(\\d+(?:\\.\\d+)?)\\s*(?:公里|千米|km)", query, re.I)
    if user_provided_distance is None and type(radius) in (int, float) and 0.1 <= radius <= 30:
        radius_m = round(radius * 1000)
    if nearby and radius_m is None:
        radius_m = 5000
    days = raw.get("duration_days")
    if type(days) is not int or days not in (1, 2, 3):
        days = local["duration_days"]
    walking = raw.get("walking_level")
    if walking not in ("low", "normal"):
        walking = local["walking_level"]
    return {
        "categories": categories, "avoid_categories": avoid,
        "nearby": nearby, "radius_m": radius_m if nearby else None,
        "duration_days": days, "walking_level": walking,
    }


async def parse_tourism_intent(query, client=None):
    """Return (intent, mode); provider failures gracefully fall back to rules."""
    client = client or DeepSeekClient()
    fallback = fallback_intent(query)
    if not client.enabled:
        return fallback, "rule_based"
    try:
        raw = await client.chat_json([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ])
        return normalize_model_intent(raw, query), "deepseek"
    except Exception:
        # Network/validation errors never expose user queries, API tokens or raw output.
        return fallback, "rule_based_fallback"
