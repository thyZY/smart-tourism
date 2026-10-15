"""Versioned, additive itinerary contract for future routing integrations.

V1 fields remain unchanged; optional V2 metadata never implies scheduling or
routing features are already implemented.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Mode = Literal["pedestrian", "bicycle", "auto"]


class PlanningPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    departure_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    time_budget_hours: float | None = Field(default=None, ge=3, le=12)
    locked_place_ids: list[int] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_ids(self):
        if any(type(v) is not int or v <= 0 for v in self.locked_place_ids):
            raise ValueError("锁定景点ID必须为正整数")
        if len(set(self.locked_place_ids)) != len(self.locked_place_ids):
            raise ValueError("锁定景点ID不能重复")
        return self


class ItineraryProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    poi_source: Literal["postgis"] = "postgis"
    routing_status: Literal["verified_by_routing_service", "unavailable", "error"]
    schedule_status: Literal["not_computed"] = "not_computed"
    planning_method: str
    limitations: list[str] = Field(default_factory=list)


def attach_contract(plan: dict, preferences: PlanningPreferences | None = None):
    """Add metadata without changing V1 response body or implying real schedules."""
    route = plan.get("route") or {}
    status = route.get("status", "unavailable")
    if status not in ("verified_by_routing_service", "unavailable", "error"):
        status = "error"
    context = ItineraryProvenance(
        routing_status=status,
        planning_method=plan["planning_method"],
        limitations=["尚未计算出发时刻或预算内可行日程；开放时间与入园条件未核实"],
    )
    return {
        **plan,
        "contract_version": 2,
        "planning_preferences": (preferences or PlanningPreferences()).model_dump(),
        "provenance": context.model_dump(),
    }
