"""Stateless conversational *preview* for an existing grounded itinerary.

The LLM parses bounded edit intentions. The service validates every operation
against current PostGIS POIs, never trusts fabricated names/IDs and NEVER routes
or changes the user's existing itinerary. The client must explicitly confirm
by calling /api/ai/itinerary/replan using the proposed state.
"""
import re
from math import isfinite

from ..itinerary import great_circle_km
from .deepseek_client import DeepSeekClient

ALLOWED_MODES = ("pedestrian", "bicycle", "auto")
CATEGORY_ALIASES = {
    "自然风光": ("自然景区", "城市公园"),
    "自然": ("自然景区", "城市公园"),
    "户外": ("自然景区", "城市公园"),
    "公园": ("城市公园", "自然景区"),
    "博物馆": ("博物馆",),
    "博物": ("博物馆",),
    "古迹": ("古迹遗址", "历史文化"),
    "历史": ("历史文化", "古迹遗址"),
    "文化": ("历史文化", "古迹遗址", "博物馆"),
    "寺庙": ("寺庙宗教",),
    "宗教": ("寺庙宗教",),
    "陵园": ("陵园景区",),
    "商业": ("文化商业",),
}
CATEGORIES = frozenset(cat for choices in CATEGORY_ALIASES.values() for cat in choices)
ORDINAL = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
MODEL_SYSTEM = (
    "你是南京智慧文旅项目的行程编辑意图解析器。只能输出合法 JSON 对象，"
    '格式为 {"operations":[{"action":"replace|remove|lock|unlock|mode|budget|start",'
    '"index":2,"name":null,"category":"自然景区","replacement_name":null,'
    '"mode":null,"hours":null,"time":null}]}。'
    "index 是当前路线从1开始的站点位置，name 是当前已选景点的准确名称；"
    "对于 replace，可选择category作为目标类别；必须来自："
    + "、".join(sorted(CATEGORIES)) + "。"
    "只解析用户明确表达的修改，不要补造景点名称或ID，不要自行生成路线。"
    "如果用户没有表达修改要求，operations为空数组。"
    "输出最多4个operations。"
)


def _index(segment):
    found = re.search(r"第([一二三四五六1-6])(?:个|站|处)?(?:景点|地点|站)?", segment)
    if found:
        return ORDINAL.get(found.group(1), int(found.group(1)) if found.group(1).isdigit() else None)
    return None


def _named_target(text, names):
    # Only resolve full current database names, longest first to avoid aliases.
    return next((name for name in sorted(names, key=len, reverse=True) if name and name in text), None)


def _category_from_text(text):
    for key in sorted(CATEGORY_ALIASES, key=len, reverse=True):
        if key in text:
            return CATEGORY_ALIASES[key][0]
    return None


def rule_operations(message, names, candidate_names=()):
    """Deterministic conservative fallback; no imaginary POI names."""
    operations = []
    segments = [s.strip() for s in re.split(r"[，,。；;]|但是|并且|然后|同时", message) if s.strip()]
    for seg in segments:
        idx = _index(seg)
        replacement_split = re.split(r"替换成|替换为|换成|换为|改成|改为", seg, maxsplit=1)
        source_text = replacement_split[0] if len(replacement_split) > 1 else seg
        name = _named_target(source_text, names)
        replacement_name = (
            _named_target(replacement_split[1], candidate_names)
            if len(replacement_split) > 1 else None
        )
        if any(term in seg for term in ("替换", "换成", "换为", "改成", "改为")) and any(
            w in seg for w in ("景点", "站", "替换", "换成", "换为")
        ):
            category = _category_from_text(seg)
            if idx is not None or name is not None:
                operations.append({"action": "replace", "index": idx,
                                   "name": name,
                                   "category": None if replacement_name else category,
                                   "replacement_name": replacement_name})
                continue
        if any(term in seg for term in ("锁定", "必须保留", "一定要去", "不能删除", "保留")):
            if idx is not None or name is not None:
                operations.append({"action": "lock", "index": idx, "name": name})
                continue
        if any(term in seg for term in ("解除锁定", "取消锁定", "不必保留")):
            if idx is not None or name is not None:
                operations.append({"action": "unlock", "index": idx, "name": name})
                continue
        if any(term in seg for term in ("删除", "移除", "去掉", "不要去")):
            if idx is not None or name is not None:
                operations.append({"action": "remove", "index": idx, "name": name})
                continue
        if any(term in seg for term in ("步行", "骑行", "骑车", "开车", "驾车", "自驾")):
            mode = ("bicycle" if any(w in seg for w in ("骑行", "骑车")) else
                    "auto" if any(w in seg for w in ("开车", "驾车", "自驾")) else
                    "pedestrian")
            operations.append({"action": "mode", "mode": mode})
            continue
        hours = re.search(r"([3-9]|1[0-2])\s*(?:个)?小时", seg)
        if hours and any(t in seg for t in ("时间", "预算", "缩短", "延长", "改成", "改为")):
            operations.append({"action": "budget", "hours": int(hours.group(1))})
            continue
        at = re.search(r"([01]?\d|2[0-3]):([0-5]\d)", seg)
        if at and any(t in seg for t in ("出发", "开始", "改成", "调整")):
            operations.append({"action": "start", "time": f"{int(at.group(1)):02d}:{at.group(2)}"})
    return operations[:4]


async def parse_chat_edit(message, names, history=(), client=None, candidate_names=()):
    """Bounded DeepSeek JSON, with documented rule-based fallback."""
    fallback = rule_operations(message, names, candidate_names)
    client = client or DeepSeekClient()
    if not client.enabled:
        return fallback, "rule_based"
    try:
        messages = [{"role": "system", "content": MODEL_SYSTEM},
                    {"role": "system", "content": "当前已有景点：" + "、".join(names)}]
        for item in history[-6:]:
            if item["role"] in ("user", "assistant"):
                messages.append({"role": item["role"], "content": item["content"][:300]})
        messages.append({"role": "user", "content": message})
        result = await client.chat_json(messages)
        ops = result.get("operations")
        if not isinstance(ops, list) or len(ops) > 4 or not ops:
            raise ValueError("No usable edit operations")
        if any(not isinstance(op, dict) for op in ops):
            raise ValueError("Invalid edit operations")
        if any(op.get("action") not in ("replace", "remove", "lock", "unlock",
                                         "mode", "budget", "start") for op in ops):
            raise ValueError("Unknown operation")
        # Explicit deterministic intent wins over contradictory model actions.
        if fallback and (any(op["action"] not in {x["action"] for x in fallback} for op in ops)):
            return fallback, "rule_based_fallback"
        if any(op.get("replacement_name") for op in fallback):
            # Exact POI names in the user's own wording outrank a model guess.
            return fallback, "rule_based_fallback"
        return ops, "deepseek"
    except Exception:
        return fallback, "rule_based_fallback"


def _target_index(op, ids, name_by_id):
    idx = op.get("index")
    named = op.get("name")
    by_index = None
    by_name = None
    if type(idx) is int and 1 <= idx <= len(ids):
        by_index = idx - 1
    if isinstance(named, str) and named.strip():
        candidates = [i for i, ident in enumerate(ids) if name_by_id[ident] == named.strip()]
        if len(candidates) == 1:
            by_name = candidates[0]
        else:
            raise ValueError("提及的景点名称不在当前行程中，请使用当前站点的完整名称")
    if by_index is not None and by_name is not None and by_index != by_name:
        # Model can put named replacements into "name"; prefer grounded ordinal
        # if the quoted name does not match that exact current stop.
        raise ValueError("站点序号与景点名称冲突，请明确指定其中一个")
    if by_index is None and by_name is None:
        raise ValueError("无法确认要修改哪一个景点，请指定第几个或当前景点名称")
    return by_index if by_index is not None else by_name


def propose_edit(ops, ids, locked, mode, hours, start_time, current, candidates,
                 auto_trim=True):
    """Return a preview of validated ID edits, never touching the map/roads."""
    if not 3 <= len(ids) <= 6 or len(set(ids)) != len(ids):
        raise ValueError("需先生成3—6个不同景点的有效行程")
    if not ops:
        raise ValueError("没有识别到可执行的修改；例如：锁定第三站、第二站换成自然景区")
    if len(ops) > 4:
        raise ValueError("单次最多执行4项修改，请拆成两次提出")
    by_id = {p["properties"]["id"]: p for p in current}
    name_by_id = {ident: by_id[ident]["properties"]["name"] for ident in ids}
    available = {p["properties"]["id"]: p for p in candidates}
    result = list(ids)
    locks = set(locked)
    updated_mode, updated_hours, updated_start = mode, hours, start_time
    changes = []
    for op in ops:
        action = op.get("action")
        if action in ("replace", "remove", "lock", "unlock"):
            idx = _target_index(op, result, name_by_id)
            old = result[idx]
            if action == "lock":
                locks.add(old)
                changes.append("保留并锁定：" + name_by_id[old])
            elif action == "unlock":
                locks.discard(old)
                changes.append("解除锁定：" + name_by_id[old])
            elif action == "remove":
                if idx == 0 or old in locks:
                    raise ValueError("第一站或锁定景点不能移除")
                if len(result) <= 3:
                    raise ValueError("至少保留3站，不能继续移除")
                result.pop(idx)
                changes.append("移除：" + name_by_id[old])
            else:
                if idx == 0 or old in locks:
                    raise ValueError("第一站或锁定景点不能替换")
                category = op.get("category")
                desired_name = op.get("replacement_name")
                if category is not None and (not isinstance(category, str) or
                                             category not in CATEGORIES):
                    raise ValueError("要求的景点类别尚不支持")
                if not category and not desired_name:
                    raise ValueError("请说明要替换成什么类别或具体景点")
                if desired_name is not None and not isinstance(desired_name, str):
                    raise ValueError("目标景点名称不合法")
                allowed_categories = next(
                    (values for values in CATEGORY_ALIASES.values() if category in values),
                    (category,) if category else (),
                )
                pool = [p for p in candidates
                        if p["properties"]["id"] not in result
                        and (not category or p["properties"].get("category") in allowed_categories)
                        and (not desired_name or p["properties"].get("name") == desired_name)]
                if not pool:
                    raise ValueError("PostGIS中没有符合要求且未入选的可替换景点")
                source = by_id[old]["geometry"]["coordinates"]
                pool.sort(key=lambda p: (
                    great_circle_km(tuple(source), tuple(p["geometry"]["coordinates"])),
                    p["properties"]["id"],
                ))
                replacement = pool[0]
                new_id = replacement["properties"]["id"]
                result[idx] = new_id
                name_by_id[new_id] = replacement["properties"]["name"]
                changes.append(f"替换：{name_by_id[old]} → {name_by_id[new_id]}（PostGIS已核实）")
        elif action == "mode":
            value = op.get("mode")
            if value not in ALLOWED_MODES:
                raise ValueError("仅支持步行、骑行、驾车模式")
            updated_mode = value
            changes.append("交通方式：" + {"pedestrian": "步行", "bicycle": "骑行",
                                        "auto": "驾车"}[value])
        elif action == "budget":
            value = op.get("hours")
            if type(value) is not int or not 3 <= value <= 12:
                raise ValueError("单日时间预算仅支持3—12小时")
            updated_hours = value
            changes.append(f"时间预算：{value}小时")
        elif action == "start":
            value = op.get("time")
            if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
                raise ValueError("出发时间格式必须为HH:MM")
            updated_start = value
            changes.append("出发时间：" + value)
        else:
            raise ValueError("没有识别到受支持的行程修改")
    if int(updated_start[:2]) * 60 + int(updated_start[3:]) + updated_hours * 60 > 1440:
        raise ValueError("单日时间预算不能跨越午夜")
    if any(item not in available for item in result):
        raise ValueError("修改后包含不属于本地POI数据库的景点")
    return {
        "proposed": {
            "place_ids": result,
            "locked_place_ids": [item for item in result if item in locks],
            "transport_mode": updated_mode,
            "budget_hours": updated_hours,
            "start_time": updated_start,
            "auto_trim": auto_trim,
        },
        "changes": changes,
        "selected_names": [available[item]["properties"]["name"] for item in result],
        "needs_confirmation": True,
        "warnings": [
            "这只是未应用的景点和参数修改预览；道路、预算及营业时间尚未核实",
            "确认后将通过独立的Valhalla重规划接口验证实际道路和时间约束",
        ],
    }
