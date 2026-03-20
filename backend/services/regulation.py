from typing import Dict, Any, List


def build_regulation_plan(result_data: Dict[str, Any], user) -> Dict[str, Any]:
    """
    根据睡眠分析结果和用户设置构建睡眠调控方案
    
    Args:
        result_data: 睡眠分析结果数据
        user: 用户对象（包含目标设置）
    
    Returns:
        调控方案字典
    """
    from utils.sleep_utils import build_core_sleep_summary
    
    stats, duration_hours = build_core_sleep_summary(result_data)
    metrics = result_data.get("metrics", {}) or {}
    quality_score = result_data.get("quality_score", 0) or 0

    target_sleep_hours = user.target_sleep_hours or 8.0
    target_deep_ratio = user.target_deep_ratio or 0.2
    target_rem_ratio = user.target_rem_ratio or 0.22

    deep_ratio = stats.get("Deep_ratio", 0)
    rem_ratio = stats.get("REM_ratio", 0)
    sleep_latency = metrics.get("sleep_latency_min", 0) or 0
    awakenings = metrics.get("num_awakenings", 0) or 0
    waso_min = metrics.get("waso_min", 0) or 0

    issues = _identify_sleep_issues(
        quality_score, duration_hours, target_sleep_hours,
        deep_ratio, target_deep_ratio, rem_ratio, target_rem_ratio,
        sleep_latency, awakenings, waso_min
    )

    baseline_state = _get_baseline_state()
    device_targets = _calculate_device_targets(issues, baseline_state)
    
    scene_name, scene_goal, strategy_reason = _determine_scene(issues, device_targets)
    
    expected_benefits = _generate_expected_benefits(deep_ratio, target_deep_ratio)
    automation_timeline = _build_automation_timeline(device_targets)

    return {
        "scene": {
            "name": scene_name,
            "goal": scene_goal,
            "reason": strategy_reason,
        },
        "sleep_snapshot": {
            "quality_score": quality_score,
            "duration_hours": duration_hours,
            "deep_ratio": deep_ratio,
            "rem_ratio": rem_ratio,
            "sleep_latency_min": sleep_latency,
            "num_awakenings": awakenings,
            "waso_min": waso_min,
        },
        "issues": issues,
        "baseline_state": baseline_state,
        "device_targets": device_targets,
        "automation_timeline": automation_timeline,
        "expected_benefits": expected_benefits,
    }


def _identify_sleep_issues(
    quality_score: float,
    duration_hours: float,
    target_sleep_hours: float,
    deep_ratio: float,
    target_deep_ratio: float,
    rem_ratio: float,
    target_rem_ratio: float,
    sleep_latency: float,
    awakenings: int,
    waso_min: float
) -> List[Dict[str, Any]]:
    """识别睡眠问题"""
    issues = []
    
    if quality_score < 75:
        issues.append({
            "title": "overall-quality",
            "label": "整体质量偏低",
            "severity": "high" if quality_score < 60 else "medium",
            "detail": f"本次睡眠评分为 {quality_score} 分，低于建议稳定区间。",
        })
    
    if duration_hours < max(target_sleep_hours - 0.5, 6):
        issues.append({
            "title": "insufficient-duration",
            "label": "核心睡眠时长不足",
            "severity": "medium",
            "detail": f"核心睡眠时长约 {duration_hours:.1f} 小时，低于目标 {target_sleep_hours:.1f} 小时。",
        })
    
    if deep_ratio < target_deep_ratio:
        issues.append({
            "title": "deep-sleep-low",
            "label": "深睡比例偏低",
            "severity": "high" if deep_ratio < target_deep_ratio * 0.8 else "medium",
            "detail": f"深睡比例为 {deep_ratio * 100:.1f}%，目标为 {target_deep_ratio * 100:.1f}%。",
        })
    
    if rem_ratio < target_rem_ratio:
        issues.append({
            "title": "rem-sleep-low",
            "label": "REM 比例偏低",
            "severity": "medium",
            "detail": f"REM 比例为 {rem_ratio * 100:.1f}%，目标为 {target_rem_ratio * 100:.1f}%。",
        })
    
    if sleep_latency > 30:
        issues.append({
            "title": "long-sleep-latency",
            "label": "入睡偏慢",
            "severity": "medium",
            "detail": f"入睡潜伏期约 {sleep_latency:.0f} 分钟，建议加强睡前灯光和温度调节。",
        })
    
    if awakenings > 3 or waso_min > 40:
        issues.append({
            "title": "fragmented-sleep",
            "label": "夜间连续性较差",
            "severity": "medium",
            "detail": f"夜醒 {awakenings} 次，WASO 约 {waso_min:.0f} 分钟，可加入降噪与恒温策略。",
        })
    
    return issues


def _get_baseline_state() -> Dict[str, Any]:
    """获取默认基准设备状态"""
    return {
        "temperature": {"label": "卧室温度", "type": "range", "value": 23, "unit": "°C", "min": 16, "max": 28, "step": 0.5},
        "light_brightness": {"label": "灯光亮度", "type": "range", "value": 70, "unit": "%", "min": 0, "max": 100, "step": 5},
        "light_color_temp": {"label": "灯光色温", "type": "range", "value": 5000, "unit": "K", "min": 2200, "max": 6500, "step": 100},
        "curtain_open": {"label": "窗帘开启", "type": "range", "value": 60, "unit": "%", "min": 0, "max": 100, "step": 5},
        "white_noise": {"label": "白噪音", "type": "toggle", "value": False, "unit": ""},
        "humidifier": {"label": "加湿器", "type": "toggle", "value": False, "unit": ""},
    }


def _calculate_device_targets(issues: List[Dict], baseline_state: Dict) -> Dict[str, Any]:
    """根据问题计算设备目标状态"""
    device_targets = {
        "temperature": {**baseline_state["temperature"], "value": 20},
        "light_brightness": {**baseline_state["light_brightness"], "value": 25},
        "light_color_temp": {**baseline_state["light_color_temp"], "value": 3000},
        "curtain_open": {**baseline_state["curtain_open"], "value": 10},
        "white_noise": {**baseline_state["white_noise"], "value": False},
        "humidifier": {**baseline_state["humidifier"], "value": False},
    }

    if any(item["title"] == "deep-sleep-low" for item in issues):
        device_targets["temperature"]["value"] = 19
        device_targets["humidifier"]["value"] = True

    if any(item["title"] == "long-sleep-latency" for item in issues):
        device_targets["light_brightness"]["value"] = 15
        device_targets["light_color_temp"]["value"] = 2700
        device_targets["curtain_open"]["value"] = 0

    if any(item["title"] == "fragmented-sleep" for item in issues):
        device_targets["white_noise"]["value"] = True
        device_targets["temperature"]["value"] = min(device_targets["temperature"]["value"], 19)

    if any(item["title"] == "insufficient-duration" for item in issues):
        device_targets["curtain_open"]["value"] = 0

    return device_targets


def _determine_scene(issues: List[Dict], device_targets: Dict) -> tuple:
    """确定场景名称、目标和策略原因"""
    scene_name = "舒眠巩固模式"
    scene_goal = "保持稳定睡眠环境，减少外界干扰。"
    strategy_reason = "根据最近一次核心睡眠结果，提供一套可演示的环境调控方案。"

    if any(item["title"] == "deep-sleep-low" for item in issues):
        scene_name = "深睡增强模式"
        scene_goal = "降低环境刺激，提升深睡恢复质量。"

    if any(item["title"] == "long-sleep-latency" for item in issues):
        scene_name = "睡前放松模式"
        scene_goal = "通过渐暗暖光和低刺激环境缩短入睡时间。"

    if any(item["title"] == "insufficient-duration" for item in issues):
        strategy_reason = "当前核心睡眠不足，建议通过更早进入低刺激环境延长有效睡眠。"

    return scene_name, scene_goal, strategy_reason


def _generate_expected_benefits(deep_ratio: float, target_deep_ratio: float) -> List[str]:
    """生成预期收益列表"""
    benefits = [
        "预计入睡准备时间缩短 10-20 分钟。",
        "预计夜间环境波动减少，有助于提升睡眠连续性。",
        "更适合答辩演示的智能家居闭环模拟，不依赖真实硬件。",
    ]
    if deep_ratio < target_deep_ratio:
        benefits.insert(1, "预计深睡比例可提升 2%-5%（模拟估计值）。")
    return benefits


def _build_automation_timeline(device_targets: Dict) -> List[Dict[str, str]]:
    """构建自动化时间线"""
    timeline = [
        {"time": "22:00", "action": "启动睡前场景，系统进入自动调控待命。"},
        {"time": "22:10", "action": f"卧室温度调整到 {device_targets['temperature']['value']}{device_targets['temperature']['unit']}。"},
        {
            "time": "22:15",
            "action": (
                f"灯光亮度降到 {device_targets['light_brightness']['value']}{device_targets['light_brightness']['unit']}，"
                f"色温切换到 {device_targets['light_color_temp']['value']}{device_targets['light_color_temp']['unit']}。"
            ),
        },
        {"time": "22:20", "action": f"窗帘收拢至 {device_targets['curtain_open']['value']}{device_targets['curtain_open']['unit']} 开启度。"},
    ]
    
    if device_targets["white_noise"]["value"]:
        timeline.append({"time": "22:25", "action": "开启白噪音设备，降低环境噪声波动。"})
    
    if device_targets["humidifier"]["value"]:
        timeline.append({"time": "22:30", "action": "开启加湿器，维持舒适湿度。"})
    
    timeline.append({"time": "07:00", "action": "进入晨起唤醒模式，逐步恢复环境亮度。"})
    
    return timeline