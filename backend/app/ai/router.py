"""POST /api/ai/tourism-search: parse language, then retrieve ONLY real PostGIS POIs.

The DeepSeek model cannot write SQL, choose unverified places, or invent routes.
"""
import asyncio
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, HTTPException
from typing import Literal
from pydantic import BaseModel, Field

from ..db import get_db_connection
from ..itinerary import build_preview
from ..natural_language import parse_intent
from .tourism_agent import parse_tourism_intent
from .itinerary_planner import (
    build_personalized_itinerary, choose_candidates, resolve_travel_mode,
)

router = APIRouter(prefix="/api/ai", tags=["ai-tourism"])


class TourismSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    lng: float | None = Field(default=None, ge=-180, le=180)
    lat: float | None = Field(default=None, ge=-90, le=90)
    max_stops: int = Field(default=4, ge=2, le=6)


def query_pois(intent, origin=None):
    """Build parameterized SQL using ONLY validated category values."""
    filters = []
    params = []
    if intent["categories"]:
        filters.append("p.category = ANY(%s)")
        params.append(intent["categories"])
    if intent["avoid_categories"]:
        filters.append("NOT (p.category = ANY(%s))")
        params.append(intent["avoid_categories"])
    if intent["nearby"]:
        lng, lat = origin
        filters.append(
            "ST_DWithin(p.geom::geography, "
            "ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s)"
        )
        params.extend([lng, lat, intent["radius_m"]])
    sql = (
        "SELECT p.id,p.name,p.category,p.address,ST_X(p.geom),ST_Y(p.geom) "
        "FROM places AS p"
    )
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY p.id LIMIT 100"
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    finally:
        conn.close()
    return [
        {
            "type": "Feature",
            "properties": {
                "id": row[0], "name": row[1],
                "category": row[2], "address": row[3],
            },
            "geometry": {"type": "Point", "coordinates": [row[4], row[5]]},
        }
        for row in rows
    ]


@router.post("/tourism-search")
async def tourism_search(request: TourismSearchRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="请输入旅游需求")
    if (request.lng is None) != (request.lat is None):
        raise HTTPException(status_code=422, detail="地图中心经纬度必须同时提供")
    try:
        # Validate explicit radius before any paid provider request.
        parsed = parse_intent(query)
        intent, mode = await parse_tourism_intent(query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    origin = None if request.lng is None else (request.lng, request.lat)
    if intent["nearby"] and origin is None:
        raise HTTPException(status_code=422, detail="附近查询需要地图中心坐标")
    # Only SQL parameterization is used; user/model text is not interpolated into SQL.
    features = query_pois(intent, origin)
    named = [f for f in features if f["properties"]["name"] in query]
    if named:
        features = named
    preview = (
        build_preview(features, origin=origin, max_stops=request.max_stops)
        if origin is not None and features else None
    )
    limitations = list(parsed.unsupported)
    if intent["walking_level"] == "low":
        limitations.append("没有道路网络，无法保证少走路")
    if intent["duration_days"]:
        limitations.append("没有按营业时间与停留时长验证每日行程")
    limitations = list(dict.fromkeys(limitations))
    explanation = (
        "DeepSeek已解析条件，已从本地PostGIS召回已收录景点"
        if mode == "deepseek" else
        "DeepSeek暂不可用，使用可解释的规则检索"
        if mode == "rule_based_fallback" else
        "未配置DeepSeek，使用可解释的规则检索"
    )
    if not intent["categories"] and not named:
        explanation += "；未指定可执行类别，展示库内已收录景点"
    return {
        "mode": mode,
        "intent": intent,
        "explanation": explanation,
        "unsupported": limitations,
        "places": {"type": "FeatureCollection", "features": features},
        "candidate_count": len(features),
        "itinerary_preview": preview,
    }


class PersonalizedItineraryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    max_stops: int = Field(default=4, ge=3, le=6)
    budget_hours: int = Field(default=8, ge=3, le=12)
    start_time: str = Field(default="09:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    transport_mode: str | None = None


@router.post("/itinerary")
async def personalized_itinerary(request: PersonalizedItineraryRequest):
    """One-day AI-supported itinerary grounded in real PostGIS and Valhalla.

    A model only contributes validated intent. Never generate tourist POIs,
    fabricate missing travel costs or assert opening hours.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="请填写旅游需求")
    try:
        validated_intent = parse_intent(query)
        mode_override = request.transport_mode
        if mode_override is not None and mode_override not in ("pedestrian", "bicycle", "auto"):
            raise HTTPException(status_code=422, detail="交通方式仅支持步行、骑行或驾车")
        intent, ai_mode = await parse_tourism_intent(query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if intent.get("duration_days") is not None and intent["duration_days"] != 1:
        raise HTTPException(status_code=422, detail="当前仅支持单日行程，请输入一天的旅游需求")
    departure = int(request.start_time[:2]) * 60 + int(request.start_time[3:])
    if departure + request.budget_hours * 60 > 1440:
        raise HTTPException(status_code=422, detail="单日行程时间预算跨越午夜，请提前出发或缩短可用时间")

    origin = (request.lng, request.lat)
    mode = resolve_travel_mode(query, intent, mode_override)
    if intent["nearby"] and intent["radius_m"] is None:
        raise HTTPException(status_code=422, detail="缺少附近搜索半径")
    features = await asyncio.to_thread(query_pois, intent, origin)
    try:
        # Early validation before entering the public routing service.
        selected = await asyncio.to_thread(
            choose_candidates, features, origin, request.max_stops, request.budget_hours * 60,
            intent, query
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        plan = await asyncio.to_thread(
            build_personalized_itinerary, features, origin, intent,
            mode, request.max_stops, request.budget_hours, request.start_time, selected,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="景点资料已发生变化，请重新搜索") from exc
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="道路时间矩阵或实际路段暂不可用，无法生成可信的AI行程；请稍后重试",
        ) from exc

    limitations = plan["limitations"] + list(validated_intent.unsupported)
    if any(word in query for word in ("公交", "地铁", "公共交通")):
        limitations.append("公交与地铁时间尚未接入，当前只使用步行、骑行或驾车道路模型")
    if intent.get("walking_level") == "low":
        limitations.append("即使选择驾车也不代表景区内无需步行")
    plan["limitations"] = list(dict.fromkeys(limitations))
    plan["ai_mode"] = ai_mode
    plan["intent"] = intent
    plan["explanation"] = (
        "DeepSeek解析旅游偏好，PostGIS选择已入库景点，Valhalla计算道路行程"
        if ai_mode == "deepseek" else
        "采用本地规则解析旅游偏好，PostGIS与Valhalla提供实际景点及道路数据"
    )
    return plan


class EditItineraryRequest(BaseModel):
    """All place IDs are re-fetched from PostGIS, never trusted as POI facts."""
    place_ids: list[int] = Field(min_length=3, max_length=6)
    locked_place_ids: list[int] = Field(default_factory=list, max_length=6)
    transport_mode: Literal["pedestrian", "bicycle", "auto"] = "pedestrian"
    budget_hours: int = Field(default=8, ge=3, le=12)
    start_time: str = Field(default="09:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    auto_trim: bool = True


@router.post("/itinerary/replan")
async def edited_itinerary(request: EditItineraryRequest):
    """Recompute a user-edited single-day itinerary. Does not call DeepSeek."""
    from .itinerary_editor import BudgetConflict, replan_edited_itinerary

    if any(type(ident) is not int or ident <= 0 for ident in request.place_ids):
        raise HTTPException(status_code=422, detail="景点ID必须为正整数")
    if len(set(request.place_ids)) != len(request.place_ids):
        raise HTTPException(status_code=422, detail="行程不能包含重复景点")
    if any(type(ident) is not int or ident <= 0 for ident in request.locked_place_ids):
        raise HTTPException(status_code=422, detail="锁定景点ID必须为正整数")
    if not set(request.locked_place_ids).issubset(request.place_ids):
        raise HTTPException(status_code=422, detail="锁定景点必须在当前行程中")
    departure = int(request.start_time[:2]) * 60 + int(request.start_time[3:])
    if departure + request.budget_hours * 60 > 1440:
        raise HTTPException(status_code=422, detail="单日行程时间预算不能跨越午夜")

    try:
        return await asyncio.to_thread(
            replan_edited_itinerary,
            request.place_ids, request.locked_place_ids,
            request.transport_mode, request.budget_hours,
            request.start_time, request.auto_trim,
        )
    except BudgetConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (HTTPError, URLError, OSError, TimeoutError,
            KeyError, ValueError, TypeError) as exc:
        # All client inputs were validated before reaching the provider.
        # An invalid matrix/polyline is a provider-data failure, not 422.
        raise HTTPException(
            status_code=502,
            detail="道路时间矩阵或分段路线不可用，无法可靠地重新规划",
        ) from exc


class ChatHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=300)


class ConversationalPreviewRequest(BaseModel):
    message: str = Field(min_length=1, max_length=300)
    place_ids: list[int] = Field(min_length=3, max_length=6)
    locked_place_ids: list[int] = Field(default_factory=list, max_length=6)
    transport_mode: Literal["pedestrian", "bicycle", "auto"] = "pedestrian"
    budget_hours: int = Field(default=8, ge=3, le=12)
    start_time: str = Field(default="09:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    history: list[ChatHistoryTurn] = Field(default_factory=list, max_length=6)


@router.post("/itinerary/chat/preview")
async def conversational_edit_preview(request: ConversationalPreviewRequest):
    """LLM only proposes validated changes. NEVER apply or call Valhalla here."""
    from .conversation import parse_chat_edit, propose_edit
    from .itinerary_editor import fetch_selected_features

    if len(set(request.place_ids)) != len(request.place_ids) or any(
        type(item) is not int or item <= 0 for item in request.place_ids
    ):
        raise HTTPException(status_code=422, detail="景点ID必须为不重复的正整数")
    if len(set(request.locked_place_ids)) != len(request.locked_place_ids) or any(
        type(item) is not int or item <= 0 for item in request.locked_place_ids
    ) or not set(request.locked_place_ids).issubset(request.place_ids):
        raise HTTPException(status_code=422, detail="锁定景点只能是当前已选景点")
    if (int(request.start_time[:2]) * 60 + int(request.start_time[3:]) +
            request.budget_hours * 60 > 1440):
        raise HTTPException(status_code=422, detail="单日行程时间预算不能跨越午夜")

    try:
        current = await asyncio.to_thread(fetch_selected_features, request.place_ids)
        # Candidate IDs/names/categories are re-fetched from PostGIS, not LLM.
        candidates = await asyncio.to_thread(query_pois, {
            "categories": [], "avoid_categories": [], "nearby": False,
            "radius_m": None,
        })
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    names = [item["properties"]["name"] for item in current]
    operations, mode = await parse_chat_edit(
        request.message, names, [h.model_dump() for h in request.history]
    )
    try:
        preview = propose_edit(
            operations, request.place_ids, request.locked_place_ids,
            request.transport_mode, request.budget_hours, request.start_time,
            current, candidates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    preview["base_state"] = {
        "place_ids": request.place_ids,
        "locked_place_ids": request.locked_place_ids,
        "transport_mode": request.transport_mode,
        "budget_hours": request.budget_hours,
        "start_time": request.start_time,
    }
    preview["mode"] = mode
    preview["reply"] = "已找到可执行修改，请核对预览并手动确认；确认前地图与原路线不会改变。"
    return preview
