"""Bounded model intent: model proposes only an operation and existing POI ID.

All actions execute through server-side verified IDs. Unsupported / ambiguous
instructions are rejected, never guessed or silently applied.
"""
import json
import os
from .deepseek_client import DeepSeekClient


def resolve_edit_intent(stops, instruction, client_factory=DeepSeekClient):
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise ValueError("该语句超出规则解析范围；配置 DeepSeek API Key 后可尝试自然语言解析")
    allowed = [{"id": p["id"], "name": p["name"]} for p in stops]
    system = (
        "你是严格的行程修改意图解析器，不是路线规划器。只输出JSON对象，字段必须且仅能是"
        "operation (remove/move/unsupported), place_id (整数或null), position (整数或null)。"
        "只可引用给出的当前站点ID。用户需求含糊、多操作、想添加新地点、减少步行、"
        "预算或时间安排时请输出unsupported；绝不能猜测，不要返回说明文本。"
    )
    user = json.dumps({"current_stops": allowed, "instruction": instruction},
                      ensure_ascii=False)
    try:
        raw = client_factory().chat_json(system, user)
    except Exception as exc:
        raise ValueError("DeepSeek 意图解析失败；原行程未变化，请重试或使用明确指令") from exc
    if not isinstance(raw, dict) or set(raw) != {"operation", "place_id", "position"}:
        raise ValueError("模型返回的修改结构无效；原行程未变化")
    op, ident, pos = raw["operation"], raw["place_id"], raw["position"]
    ids = [p["id"] for p in stops]
    if op not in ("remove", "move") or type(ident) is not int or ident not in ids:
        raise ValueError("模型未能确定当前行程中的唯一景点；未做修改")
    changed = ids.copy()
    changed.remove(ident)
    if op == "remove":
        if pos is not None or len(changed) < 2:
            raise ValueError("删除操作无效，至少保留两站")
    else:
        if type(pos) is not int or not 1 <= pos <= len(ids):
            raise ValueError("模型生成了无效站次")
        changed.insert(pos - 1, ident)
    if changed == ids:
        raise ValueError("新旧顺序一致，无须更新")
    return {"place_ids": changed, "operation": op, "matched_place_id": ident,
            "instruction": instruction, "intent_source": "deepseek_bounded_json"}
