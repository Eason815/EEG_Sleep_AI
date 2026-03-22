"""
睡眠分析结果解析和统计工具
"""
import json
from typing import Dict, Any, Optional

CORE_BUFFER_EPOCHS = 40


def parse_result_payload(result_json) -> Dict[str, Any]:
    """解析结果JSON数据"""
    if not result_json:
        return {}
    if isinstance(result_json, str):
        try:
            return json.loads(result_json)
        except json.JSONDecodeError:
            return {}
    return result_json


def serialize_result(result) -> str:
    """序列化结果对象为JSON字符串"""
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return json.loads(result.json())


def build_core_sleep_summary(result_data: Dict[str, Any]) -> tuple:
    """
    构建核心睡眠摘要统计
    
    Returns:
        tuple: (stats dict, duration_hours float)
    """
    core_hypnogram = result_data.get("sleep_hypnogram_raw") or []
    if not core_hypnogram:
        stats = result_data.get("stats", {}) or {}
        duration_hours = result_data.get("duration_hours", 0) or 0
        return stats, duration_hours

    if len(core_hypnogram) > CORE_BUFFER_EPOCHS * 2:
        effective_hypnogram = core_hypnogram[CORE_BUFFER_EPOCHS:-CORE_BUFFER_EPOCHS]
    else:
        effective_hypnogram = core_hypnogram

    total_epochs = len(effective_hypnogram)
    if total_epochs == 0:
        return {
            "W_ratio": 0.0,
            "REM_ratio": 0.0,
            "Light_ratio": 0.0,
            "Deep_ratio": 0.0,
        }, (result_data.get("duration_hours", 0) or 0.0)

    stats = {
        "W_ratio": effective_hypnogram.count(0) / total_epochs,
        "REM_ratio": effective_hypnogram.count(1) / total_epochs,
        "Light_ratio": effective_hypnogram.count(2) / total_epochs,
        "Deep_ratio": effective_hypnogram.count(3) / total_epochs,
    }
    duration_hours = result_data.get("duration_hours", 0) or round(len(core_hypnogram) * 30 / 3600, 2)
    return stats, duration_hours
