from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from deps.auth import get_current_user, verify_password, get_password_hash, get_db
from entity.user import User, UserSettings, PasswordChange
from utils import parse_result_payload

router = APIRouter()


@router.get("/user/settings")
async def get_user_settings(user: User = Depends(get_current_user)):
    """获取用户设置"""
    return {
        "target_sleep_hours": user.target_sleep_hours or 8.0,
        "target_deep_ratio": user.target_deep_ratio or 0.2,
        "target_rem_ratio": user.target_rem_ratio or 0.22,
        "timezone": user.timezone or "Asia/Shanghai",
    }


@router.put("/user/settings")
async def update_user_settings(
    settings: UserSettings,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新用户设置"""
    if settings.target_sleep_hours is not None:
        user.target_sleep_hours = settings.target_sleep_hours
    if settings.target_deep_ratio is not None:
        user.target_deep_ratio = settings.target_deep_ratio
    if settings.target_rem_ratio is not None:
        user.target_rem_ratio = settings.target_rem_ratio
    if settings.timezone is not None:
        user.timezone = settings.timezone

    db.commit()
    return {"message": "设置已更新", "settings": settings.dict()}


@router.post("/user/password")
async def change_password(
    password_data: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改用户密码"""
    if not verify_password(password_data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")

    user.password_hash = get_password_hash(password_data.new_password)
    db.commit()
    return {"message": "密码修改成功"}


@router.get("/user/profile")
async def get_user_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户个人资料"""
    from entity.user import SleepRecord
    
    total_records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).count()

    latest_record = (
        db.query(SleepRecord)
        .filter(SleepRecord.user_id == user.id)
        .order_by(SleepRecord.created_at.desc())
        .first()
    )

    latest_score = None
    if latest_record:
        result_data = parse_result_payload(latest_record.result_json)
        latest_score = result_data.get("quality_score")

    return {
        "username": user.username,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "total_records": total_records,
        "latest_score": latest_score,
        "settings": {
            "target_sleep_hours": user.target_sleep_hours or 8.0,
            "target_deep_ratio": user.target_deep_ratio or 0.2,
            "target_rem_ratio": user.target_rem_ratio or 0.22,
            "timezone": user.timezone or "Asia/Shanghai",
        },
    }