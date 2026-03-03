from pydantic import BaseModel, Field
from typing import List, Optional

class SleepStats(BaseModel):
    """睡眠统计数据"""
    W_ratio: float = Field(..., ge=0, le=1, description="清醒占比")
    REM_ratio: float = Field(..., ge=0, le=1, description="REM睡眠占比")
    Light_ratio: float = Field(..., ge=0, le=1, description="浅睡眠占比")
    Deep_ratio: float = Field(..., ge=0, le=1, description="深睡眠占比")

class AnalysisResult(BaseModel):
    """分析结果"""
    hypnogram: List[int] = Field(..., description="睡眠阶段序列")
    stats: SleepStats
    quality_score: int = Field(..., ge=0, le=100, description="质量评分")
    total_epochs: int = Field(..., description="总采样点数")
    duration_hours: float = Field(..., description="总时长(小时)")
    
    # 新增详细指标
    sleep_efficiency: Optional[float] = Field(None, description="睡眠效率")
    sleep_latency: Optional[int] = Field(None, description="入睡延迟(分钟)")
    waso: Optional[int] = Field(None, description="入睡后觉醒时间(分钟)")
    rem_latency: Optional[int] = Field(None, description="REM潜伏期(分钟)")

class APIResponse(BaseModel):
    """统一响应格式"""
    code: int
    message: str
    data: Optional[AnalysisResult] = None
    error: Optional[str] = None
