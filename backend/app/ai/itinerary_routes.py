"""AI itinerary API: verified database records only."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .itinerary_geo_service import fetch_candidates, valhalla_route
from .itinerary_planner import ItineraryPlanner
from .itinerary_contract import attach_contract
from .road_optimizer import plan_verified_route
from .itinerary_edit import edit_stop_ids

router = APIRouter(prefix="/api/ai/itinerary", tags=["AI Itinerary"])


class ItineraryRequest(BaseModel):
    location: str = Field(..., min_length=1, max_length=160, description="行程需求及目标区域")
    days: int = Field(default=1, ge=1, le=1, description="第一版仅支持单日")
    style: str = Field(default="历史文化", max_length=80)
    people: str = Field(default="普通游客", max_length=80)
    walking_limit: str = Field(default="中等", max_length=80)
    max_stops: int = Field(default=4, ge=2, le=6)
    excluded_place_ids: list[int] = Field(default_factory=list, max_length=40)
    travel_mode: str = Field(default="pedestrian", pattern="^(pedestrian|bicycle|auto)$")


@router.post("/generate")
def generate_itinerary(request: ItineraryRequest):
    try:
        candidates = fetch_candidates()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="POI数据库暂不可用") from exc
    if not candidates:
        raise HTTPException(status_code=404, detail="数据库中没有可规划的景点")
    excluded = request.excluded_place_ids
    if any(type(id_) is not int or id_ <= 0 for id_ in excluded) or len(set(excluded)) != len(excluded):
        raise HTTPException(status_code=422, detail="排除景点ID必须是无重复的正整数")
    available_ids = {p["id"] for p in candidates}
    if any(id_ not in available_ids for id_ in excluded):
        raise HTTPException(status_code=422, detail="排除列表包含数据库中不存在的景点")
    excluded_set = set(excluded)
    candidates = [p for p in candidates if p["id"] not in excluded_set]
    if len(candidates) < 2:
        raise HTTPException(status_code=422, detail="排除后剩余景点不足2个，请减少排除项")
    try:
        plan = ItineraryPlanner().generate(
            location=request.location, days=request.days, style=request.style,
            people=request.people, walking_limit=request.walking_limit,
            candidates=candidates, max_stops=request.max_stops,
            travel_mode=request.travel_mode, excluded_place_ids=excluded,
        )
        return attach_contract(plan)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class RestoreRequest(BaseModel):
    place_ids: list[int] = Field(..., min_length=2, max_length=6)
    travel_mode: str = Field(default="pedestrian", pattern="^(pedestrian|bicycle|auto)$")


@router.post("/restore")
def restore_itinerary(request: RestoreRequest):
    """Reload by verified DB IDs, never trust browser-supplied coordinates."""
    ids = request.place_ids
    if len(ids) != len(set(ids)) or any(id_ <= 0 for id_ in ids):
        raise HTTPException(status_code=422, detail="景点ID无效或重复")
    try:
        candidates = fetch_candidates()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="POI数据库暂不可用") from exc
    by_id = {item["id"]: item for item in candidates}
    if any(id_ not in by_id for id_ in ids):
        raise HTTPException(status_code=409, detail="历史行程存在已失效景点，请重新规划")
    places = [by_id[id_] for id_ in ids]
    stops = [{
        "id": p["id"], "name": p["name"], "category": p["category"],
        "address": p["address"], "lng": p["lng"], "lat": p["lat"],
        "reason": "已从当前数据库重新核实；游览条件请自行确认"
    } for p in places]
    route = valhalla_route(places, request.travel_mode)
    return attach_contract({
        "schema_version": 1, "title": "恢复的历史行程", "days": 1,
        "summary": "站点来自当前数据库；路网已重新请求（如配置）。",
        "planning_method": "restored_from_verified_ids",
        "mode": request.travel_mode, "stops": stops, "route": route,
        "selected_places": {"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "properties": {"id": p["id"], "name": p["name"],
                           "category": p["category"], "address": p["address"]},
            "geometry": {"type": "Point", "coordinates": [p["lng"], p["lat"]]}
        } for p in places]},
        "warnings": [
            "已重新查询PostGIS景点和尝试请求道路；开放时间与通行性未核实"
        ]
    })


class RoadCalculationRequest(BaseModel):
    place_ids: list[int] = Field(..., min_length=2, max_length=6)
    travel_mode: str = Field(default="pedestrian", pattern="^(pedestrian|bicycle|auto)$")
    optimize: bool = False


@router.post("/road")
def calculate_road(request: RoadCalculationRequest):
    """Optional local Valhalla route; only verified DB IDs are accepted."""
    try:
        return plan_verified_route(request.place_ids, request.travel_mode, request.optimize)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="道路服务调用失败，原直线预览保持不变") from exc


class EditPreviewRequest(BaseModel):
    place_ids: list[int] = Field(..., min_length=2, max_length=6)
    instruction: str = Field(..., min_length=1, max_length=160)
    travel_mode: str = Field(default="pedestrian", pattern="^(pedestrian|bicycle|auto)$")


@router.post("/edit-preview")
def preview_itinerary_edit(request: EditPreviewRequest):
    """Read-only edit preview; must be explicitly confirmed by browser."""
    if any(type(i) is not int or i <= 0 for i in request.place_ids) or len(set(request.place_ids)) != len(request.place_ids):
        raise HTTPException(status_code=422, detail="原行程景点ID无效或重复")
    try:
        current = {p["id"]: p for p in fetch_candidates()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="POI数据库暂不可用") from exc
    if any(i not in current for i in request.place_ids):
        raise HTTPException(status_code=409, detail="原行程包含已失效景点，无法修改")
    try:
        edited = edit_stop_ids([current[i] for i in request.place_ids], request.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    plan = restore_itinerary(RestoreRequest(
        place_ids=edited["place_ids"], travel_mode=request.travel_mode))
    plan["title"] = "待确认的行程修改预览"
    plan["planning_method"] = "deterministic_edit_preview"
    plan["edit_summary"] = edited
    plan["warnings"].append("修改由明确的规则解析完成，尚未应用到地图；仅确认后生效")
    plan["provenance"]["planning_method"] = "deterministic_edit_preview"
    return plan
