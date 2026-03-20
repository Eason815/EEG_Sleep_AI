from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from deps import get_current_user, get_db
from entity.user import SleepRecord, User
from utils import parse_result_payload, build_core_sleep_summary

router = APIRouter()


@router.get("/history")
async def get_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户的睡眠分析历史记录列表"""
    records = (
        db.query(SleepRecord)
        .filter(SleepRecord.user_id == user.id)
        .order_by(SleepRecord.created_at.desc())
        .all()
    )

    result = []
    for record in records:
        result_data = parse_result_payload(record.result_json)
        _, core_duration_hours = build_core_sleep_summary(result_data)

        result.append({
            "id": record.id,
            "filename": record.filename,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "quality_score": result_data.get("quality_score"),
            "duration_hours": core_duration_hours,
            "model_name": record.model_name or result_data.get("model_name"),
            "model_family": record.model_family or result_data.get("model_family") or "sleep_stage_v8",
        })
    return result


@router.get("/history/{record_id}")
async def get_record_detail(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取单条睡眠记录详情"""
    record = (
        db.query(SleepRecord)
        .filter(SleepRecord.id == record_id, SleepRecord.user_id == user.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    result_data = parse_result_payload(record.result_json)
    core_stats, core_duration_hours = build_core_sleep_summary(result_data)
    if result_data:
        result_data = {
            **result_data,
            "stats": core_stats,
            "duration_hours": core_duration_hours,
            "model_name": record.model_name or result_data.get("model_name"),
            "model_family": record.model_family or result_data.get("model_family") or "sleep_stage_v8",
        }

    return {
        "id": record.id,
        "filename": record.filename,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "result": result_data,
    }


@router.delete("/history/{record_id}")
async def delete_record(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除单条睡眠记录"""
    record = (
        db.query(SleepRecord)
        .filter(SleepRecord.id == record_id, SleepRecord.user_id == user.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    db.delete(record)
    db.commit()
    return {"message": "记录已删除"}