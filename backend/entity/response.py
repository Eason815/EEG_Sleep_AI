from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class SleepStats(BaseModel):
    W_ratio: float = Field(..., ge=0, le=1, description="清醒占比")
    REM_ratio: float = Field(..., ge=0, le=1, description="REM睡眠占比")
    Light_ratio: float = Field(..., ge=0, le=1, description="浅睡眠占比")
    Deep_ratio: float = Field(..., ge=0, le=1, description="深睡眠占比")


class SubScores(BaseModel):
    efficiency: float = Field(..., description="睡眠效率得分")
    architecture: float = Field(..., description="睡眠结构得分")
    continuity: float = Field(..., description="睡眠连续性得分")
    timing: float = Field(..., description="时间特征得分")


class SleepMetrics(BaseModel):
    sleep_efficiency: float = Field(..., description="睡眠效率(%)")
    sleep_latency_min: float = Field(..., description="入睡延迟(分钟)")
    waso_min: float = Field(..., description="入睡后觉醒时间(分钟)")
    rem_latency_min: Optional[float] = Field(None, description="REM潜伏期(分钟)")
    num_cycles: int = Field(..., description="睡眠周期数")
    num_awakenings: int = Field(..., description="觉醒次数")
    fragmentation_index: float = Field(..., description="碎片化指数")
    total_sleep_time_hours: float = Field(..., description="总睡眠时长(小时)")


class AnalysisResult(BaseModel):
    model_id: Optional[str] = Field(None, description="选中的模型ID")
    model_name: Optional[str] = Field(None, description="选中的模型文件名")
    model_family: Optional[str] = Field(None, description="选中的模型类别")

    hypnogram_full: List[int] = Field(..., description="完整记录数据")
    sleep_hypnogram_raw: List[int] = Field(..., description="原始核心睡眠数据")
    sleep_hypnogram_smooth: List[int] = Field(..., description="平滑版本")
    sleep_hypnogram_lite: List[int] = Field(..., description="轻量版本")

    recording_start_time: str = Field(..., description="记录开始时间(ISO格式)")
    sleep_onset_epoch: int = Field(..., description="睡眠开始epoch索引")
    sleep_offset_epoch: int = Field(..., description="睡眠结束epoch索引")

    stats: SleepStats
    quality_score: int = Field(..., ge=0, le=100, description="质量评分")
    total_epochs: int = Field(..., description="总采样点数")
    duration_hours: float = Field(..., description="总时长(小时)")

    sleep_efficiency: Optional[float] = Field(None, description="睡眠效率")
    sleep_latency: Optional[int] = Field(None, description="入睡延迟(分钟)")
    waso: Optional[int] = Field(None, description="入睡后觉醒时间(分钟)")
    rem_latency: Optional[int] = Field(None, description="REM潜伏期(分钟)")

    sub_scores: Optional[SubScores] = Field(None, description="各维度得分")
    metrics: Optional[SleepMetrics] = Field(None, description="详细睡眠指标")
    recommendations: Optional[List[str]] = Field(None, description="睡眠改善建议")


class APIResponse(BaseModel):
    code: int
    message: str
    data: Optional[AnalysisResult] = None
    error: Optional[str] = None
