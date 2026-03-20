from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from deps import get_current_user, get_db
from entity.user import SleepRecord, User
from services.regulation import build_regulation_plan
from utils import parse_result_payload, build_core_sleep_summary

router = APIRouter()


@router.get("/regulation/plan")
async def get_regulation_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取基于最近睡眠分析的调控方案"""
    latest_record = (
        db.query(SleepRecord)
        .filter(SleepRecord.user_id == user.id)
        .order_by(SleepRecord.created_at.desc())
        .first()
    )

    if not latest_record:
        return {
            "has_plan": False,
            "message": "暂无睡眠分析记录，请先上传并分析一次睡眠数据。",
        }

    result_data = parse_result_payload(latest_record.result_json)
    if not result_data:
        return {
            "has_plan": False,
            "message": "最近一次记录缺少可用分析结果，暂时无法生成调控策略。",
        }

    core_stats, core_duration_hours = build_core_sleep_summary(result_data)
    normalized_result = {
        **result_data,
        "stats": core_stats,
        "duration_hours": core_duration_hours,
    }

    return {
        "has_plan": True,
        "source_record": {
            "id": latest_record.id,
            "filename": latest_record.filename,
            "created_at": latest_record.created_at.isoformat() if latest_record.created_at else None,
        },
        "plan": build_regulation_plan(normalized_result, user),
    }