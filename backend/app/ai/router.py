from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .tourism_agent import TourismIntentAgent

router = APIRouter(prefix="/api/ai", tags=["ai-tourism"])
agent = TourismIntentAgent()


class TourismSearchRequest(BaseModel):
    query: str


@router.post("/tourism-search")
def tourism_search(request: TourismSearchRequest):
    if len(request.query.strip()) == 0:
        raise HTTPException(status_code=422, detail="请输入旅游需求")
    if len(request.query) > 300:
        raise HTTPException(status_code=422, detail="查询内容不得超过300字")

    return {
        "mode": "deepseek_ready",
        "intent": agent.parse(request.query),
        "message": "AI意图解析接口已建立，景点召回将在下一阶段接入PostGIS"
    }
