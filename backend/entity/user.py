from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, TIMESTAMP, Float
from sqlalchemy.sql import func

from deps.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.now())
    # 用户设置
    target_sleep_hours = Column(Float, default=8.0)  # 目标睡眠时长
    target_deep_ratio = Column(Float, default=0.2)   # 目标深睡比例
    target_rem_ratio = Column(Float, default=0.22)   # 目标REM比例
    timezone = Column(String(50), default='Asia/Shanghai')  # 时区设置

class SleepRecord(Base):
    __tablename__ = "sleep_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String(255))
    model_family = Column(String(100), nullable=True)
    model_name = Column(String(255), nullable=True)
    result_json = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

class UserSettings(BaseModel):
    target_sleep_hours: Optional[float] = 8.0
    target_deep_ratio: Optional[float] = 0.2
    target_rem_ratio: Optional[float] = 0.22
    timezone: Optional[str] = "Asia/Shanghai"


class PasswordChange(BaseModel):
    old_password: str
    new_password: str