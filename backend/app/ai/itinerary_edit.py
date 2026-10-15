"""Deterministic edits to verified existing stops; no invented POIs or LLM claims."""
import re


def edit_stop_ids(stops, instruction):
    if not isinstance(instruction, str) or not 1 <= len(instruction.strip()) <= 160:
        raise ValueError("请输入1–160字的修改要求")
    ids = [s["id"] for s in stops]
    if len(ids) < 2 or len(ids) > 6 or len(set(ids)) != len(ids):
        raise ValueError("当前行程无效，请重新生成")
    names = [(s["id"], s["name"]) for s in stops]
    text = instruction.strip()
    # Deliberately limited grammar. Unknown requests are rejected, never guessed.
    remove = re.fullmatch(r"(?:请)?(?:删除|移除|排除|去掉)(.+?)(?:这个景点)?[。！!\s]*", text)
    move = re.fullmatch(r"(?:请)?(?:把|将)(.+?)(?:调整|移动|放|移)到第([1-6])站[。！!\s]*", text)
    if not remove and not move:
        raise ValueError("当前支持“删除景点名称”或“将景点名称调整到第N站”；其他要求不会自动执行")
    target = (remove or move).group(1).strip()
    matches = [id_ for id_, name in names if target == name]
    if len(matches) != 1:
        raise ValueError("请提供当前行程中准确且唯一的景点名称")
    ident = matches[0]
    if remove:
        if len(ids) <= 2:
            raise ValueError("至少保留两个景点")
        ids.remove(ident)
        operation = "remove"
    else:
        position = int(move.group(2))
        if position > len(ids):
            raise ValueError("目标站次超出当前行程")
        ids.remove(ident)
        ids.insert(position - 1, ident)
        operation = "move"
    return {"place_ids": ids, "operation": operation, "matched_place_id": ident,
            "instruction": text}
