from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from deps import get_current_user, get_db
from entity.user import SleepRecord, User
from utils import parse_result_payload, build_core_sleep_summary

router = APIRouter()


@router.get("/trends")
async def get_trends(
    period: str = "week",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取睡眠趋势分析数据"""
    query = db.query(SleepRecord).filter(SleepRecord.user_id == user.id)

    now = datetime.now()
    if period == "week":
        query = query.filter(SleepRecord.created_at >= now - timedelta(days=7))
    elif period == "month":
        query = query.filter(SleepRecord.created_at >= now - timedelta(days=30))

    records = query.order_by(SleepRecord.created_at.asc()).all()
    if not records:
        return {"period": period, "records": [], "summary": None, "chart_data": None}

    parsed_records = []
    for record in records:
        result_data = parse_result_payload(record.result_json)
        if not result_data:
            continue

        core_stats, core_duration_hours = build_core_sleep_summary(result_data)
        parsed_records.append({
            "id": record.id,
            "filename": record.filename,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "date": record.created_at.strftime("%Y-%m-%d") if record.created_at else None,
            "quality_score": result_data.get("quality_score", 0),
            "duration_hours": core_duration_hours,
            "stats": core_stats,
            "metrics": result_data.get("metrics", {}),
        })

    summary = _calculate_summary(parsed_records)
    chart_data = _build_chart_data(parsed_records)

    return {
        "period": period,
        "records": parsed_records,
        "summary": summary,
        "chart_data": chart_data,
    }


def _calculate_summary(parsed_records: list) -> dict:
    """计算汇总统计"""
    if not parsed_records:
        return None

    quality_scores = [r["quality_score"] for r in parsed_records if r["quality_score"] is not None]
    durations = [r["duration_hours"] for r in parsed_records if r["duration_hours"] is not None]

    avg_stats = {"W_ratio": 0, "REM_ratio": 0, "Light_ratio": 0, "Deep_ratio": 0}
    valid_stats = [r["stats"] for r in parsed_records if r["stats"]]
    if valid_stats:
        for key in avg_stats:
            values = [stats.get(key, 0) for stats in valid_stats if stats.get(key) is not None]
            avg_stats[key] = sum(values) / len(values) if values else 0

    return {
        "total_records": len(parsed_records),
        "avg_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
        "avg_duration_hours": sum(durations) / len(durations) if durations else 0,
        "best_score": max(quality_scores) if quality_scores else 0,
        "worst_score": min(quality_scores) if quality_scores else 0,
        "avg_stats": avg_stats,
    }


def _build_chart_data(parsed_records: list) -> dict:
    """构建图表数据"""
    return {
        "dates": [r["date"] for r in parsed_records],
        "quality_scores": [r["quality_score"] for r in parsed_records],
        "durations": [r["duration_hours"] for r in parsed_records],
        "deep_ratios": [r["stats"].get("Deep_ratio", 0) if r["stats"] else 0 for r in parsed_records],
        "rem_ratios": [r["stats"].get("REM_ratio", 0) if r["stats"] else 0 for r in parsed_records],
        "light_ratios": [r["stats"].get("Light_ratio", 0) if r["stats"] else 0 for r in parsed_records],
    }