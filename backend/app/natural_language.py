"""Transparent rule-based Chinese POI intent parsing (no LLM/API key required).

This module understands only a limited set of positive place-category and
proximity requests. It deliberately does NOT generate itineraries, infer
opening hours, or claim personalized AI recommendations.
"""
from dataclasses import dataclass
import re


CATEGORY_RULES = (
    (("博物馆", "博物院", "看展", "展览"), ("博物馆",)),
    (("寺庙", "寺院", "祈福", "宗教"), ("寺庙宗教",)),
    (("陵园", "中山陵", "明孝陵"), ("陵园景区",)),
    (("公园", "绿地"), ("城市公园",)),
    (("自然", "山水", "风景", "徒步"), ("自然景区", "城市公园")),
    (("古迹", "遗址", "古建筑"), ("古迹遗址", "历史文化")),
    (("历史", "人文", "文化景点"), ("历史文化", "古迹遗址", "博物馆", "陵园景区")),
    (("购物", "商业街", "商圈"), ("文化商业",)),
)
NEAR_TERMS = ("附近", "周边", "周围", "离我近", "近一点", "不太远")
GENERAL_TERMS = ("景点", "旅游", "游玩", "去哪", "哪里玩", "逛逛", "南京")
EXCLUSION_TERMS = ("不喜欢", "不要去", "不想去", "避开", "排除")


@dataclass(frozen=True)
class ParsedIntent:
    categories: tuple[str, ...]
    nearby: bool
    radius_m: int | None
    generic: bool
    unsupported: tuple[str, ...]


def parse_intent(text: str) -> ParsedIntent:
    """Return grounded filters; never mistake planning preferences for filtering."""
    message = text.strip()
    if not message:
        raise ValueError("请输入景点检索需求")

    unsupported = []
    for terms, label in (
        (("预算", "便宜", "免费", "花费"), "预算筛选"),
        (("一天", "两天", "三天", "行程", "路线", "上午", "下午"), "行程安排"),
        (("少走路", "不累", "轻松", "步行少"), "步行负担"),
        (("开放", "营业", "几点关门"), "实时开放时间"),
    ):
        if any(term in message for term in terms):
            unsupported.append(label)

    exclusion = any(term in message for term in EXCLUSION_TERMS)
    if exclusion:
        unsupported.append("排除式偏好")

    distance = re.search(r"(\d+(?:\.\d+)?)\s*(?:公里|千米|km)", message, re.I)
    radius_m = None
    if distance:
        km = float(distance.group(1))
        if not 0.1 <= km <= 30:
            raise ValueError("检索半径应在0.1至30公里之间")
        radius_m = round(km * 1000)

    nearby = any(term in message for term in NEAR_TERMS) or radius_m is not None
    if nearby and radius_m is None:
        radius_m = 5000

    categories = []
    if not exclusion:
        for needles, targets in CATEGORY_RULES:
            if any(word in message for word in needles):
                for category in targets:
                    if category not in categories:
                        categories.append(category)

    return ParsedIntent(
        categories=tuple(categories),
        nearby=nearby,
        radius_m=radius_m,
        generic=any(term in message for term in GENERAL_TERMS) and not exclusion,
        unsupported=tuple(unsupported),
    )
