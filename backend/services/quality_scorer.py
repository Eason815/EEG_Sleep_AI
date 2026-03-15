"""
睡眠质量评分系统 - 基于临床睡眠医学研究

参考文献:
1. Ohayon et al. (2017). National Sleep Foundation's sleep quality recommendations.
   Sleep Health, 3(1), 6-19.
   
2. Buysse et al. (1989). The Pittsburgh Sleep Quality Index (PSQI).
   Psychiatry Research, 28(2), 193-213.
   
3. Berry et al. (2017). AASM Scoring Manual Version 2.4.
   American Academy of Sleep Medicine.
   
4. Van Dongen et al. (2003). Sleep architecture and cognitive performance.
   Sleep, 26(2), 117-126.

5. Walker (2017). Why We Sleep: Unlocking the Power of Sleep and Dreams.
   Scribner. (Matthew Walker, UC Berkeley 神经科学教授)
"""

import numpy as np
from typing import List, Dict, Tuple

class SleepQualityScorer:
    """
    多维度睡眠质量评分系统
    
    评分维度（基于 AASM 和 NSF 标准）:
    1. 睡眠效率 (Sleep Efficiency)
    2. 睡眠结构 (Sleep Architecture)
    3. 睡眠连续性 (Sleep Continuity)
    4. 昼夜节律 (Circadian Alignment)
    """
    
    # 理想睡眠结构（成年人标准，来源: AASM 2017）
    IDEAL_ARCHITECTURE = {
        'W': (0.02, 0.05),      # 2-5% (仅计入睡后)
        'REM': (0.20, 0.25),    # 20-25%
        'Light': (0.45, 0.55),  # 45-55% (N1+N2)
        'Deep': (0.13, 0.23)    # 13-23% (N3)
    }
    
    # 权重配置（可调整）
    WEIGHTS = {
        'efficiency': 0.20,      # 睡眠效率
        'architecture': 0.30,    # 睡眠结构
        'continuity': 0.30,      # 睡眠连续性
        'timing': 0.20          # 时间特征
    }
    
    def __init__(self, hypnogram: List[int]):
        """
        参数:
            hypnogram: 睡眠阶段序列 [0:W, 1:REM, 2:Light, 3:Deep]
        """
        self.hypnogram = np.array(hypnogram)
        self.total_epochs = len(hypnogram)
        self.epoch_duration = 0.5  # 每个epoch=30秒=0.5分钟
        
    def calculate_comprehensive_score(self) -> Dict:
        """
        计算综合睡眠质量评分
        
        返回:
            {
                'total_score': 总分(0-100),
                'sub_scores': 各维度得分,
                'metrics': 详细指标,
                'recommendations': 改善建议
            }
        """
        # 1. 计算基础指标
        metrics = self._calculate_metrics()
        
        # 2. 各维度评分
        efficiency_score = self._score_efficiency(metrics)
        architecture_score = self._score_architecture(metrics)
        continuity_score = self._score_continuity(metrics)
        timing_score = self._score_timing(metrics)
        
        # 3. 加权总分
        total_score = int(
            efficiency_score * self.WEIGHTS['efficiency'] +
            architecture_score * self.WEIGHTS['architecture'] +
            continuity_score * self.WEIGHTS['continuity'] +
            timing_score * self.WEIGHTS['timing']
        )
        
        # 4. 生成建议
        recommendations = self._generate_recommendations(metrics, total_score)
        
        return {
            'total_score': total_score,
            'sub_scores': {
                'efficiency': round(efficiency_score, 1),
                'architecture': round(architecture_score, 1),
                'continuity': round(continuity_score, 1),
                'timing': round(timing_score, 1)
            },
            'metrics': metrics,
            'recommendations': recommendations
        }
    
    def _calculate_metrics(self) -> Dict:
        """计算所有基础睡眠指标"""
        
        # 1. 睡眠效率 (Sleep Efficiency)
        # 定义: 实际睡眠时间 / 卧床时间 × 100%
        total_sleep = sum(1 for x in self.hypnogram if x > 0)
        sleep_efficiency = (total_sleep / self.total_epochs) * 100
        
        # 2. 入睡延迟 (Sleep Onset Latency, SOL)
        # 定义: 从躺下到进入N1的时间
        first_sleep_idx = np.where(self.hypnogram > 0)[0]
        sleep_latency = first_sleep_idx[0] if len(first_sleep_idx) > 0 else 0
        sleep_latency_min = sleep_latency * self.epoch_duration
        
        # 3. 入睡后觉醒 (Wake After Sleep Onset, WASO)
        if len(first_sleep_idx) > 0:
            after_sleep_onset = self.hypnogram[first_sleep_idx[0]:]
            waso = np.sum(after_sleep_onset == 0)
            waso_min = waso * self.epoch_duration
        else:
            waso_min = 0
        
        # 4. REM 潜伏期 (REM Latency)
        # 定义: 从入睡到第一个REM期的时间
        first_rem_idx = np.where(self.hypnogram == 1)[0]
        if len(first_rem_idx) > 0 and len(first_sleep_idx) > 0:
            rem_latency = (first_rem_idx[0] - first_sleep_idx[0]) * self.epoch_duration
        else:
            rem_latency = None
        
        # 5. 睡眠阶段比例
        stage_ratios = {
            'W': np.mean(self.hypnogram == 0),
            'REM': np.mean(self.hypnogram == 1),
            'Light': np.mean(self.hypnogram == 2),
            'Deep': np.mean(self.hypnogram == 3)
        }
        
        # 6. 睡眠周期分析
        cycles = self._detect_sleep_cycles()
        
        # 7. 觉醒次数 (Number of Awakenings)
        # 定义: 入睡后清醒的次数（持续时间>1分钟）
        awakenings = self._count_awakenings()
        
        # 8. 睡眠碎片化指数 (Sleep Fragmentation Index)
        fragmentation_index = self._calculate_fragmentation()
        
        return {
            'sleep_efficiency': sleep_efficiency,
            'sleep_latency_min': sleep_latency_min,
            'waso_min': waso_min,
            'rem_latency_min': rem_latency,
            'stage_ratios': stage_ratios,
            'num_cycles': len(cycles),
            'num_awakenings': awakenings,
            'fragmentation_index': fragmentation_index,
            'total_sleep_time_hours': total_sleep * self.epoch_duration / 60
        }
    
    def _score_efficiency(self, metrics: Dict) -> float:
        """
        睡眠效率评分
        
        标准 (Ohayon et al. 2017):
        - 优秀: ≥85%
        - 良好: 75-85%
        - 一般: 65-75%
        - 较差: <65%
        """
        efficiency = metrics['sleep_efficiency']
        return efficiency
    
    def _score_architecture(self, metrics: Dict) -> float:
        """
        睡眠结构评分
        
        评估标准:
        1. 各阶段比例是否在理想范围
        2. 深睡眠是否充足 (特别重要)
        3. REM睡眠是否正常
        
        参考: Berry et al. (2017) AASM标准

        深睡眠 (Deep)		恢复体力的关键阶段
        REM睡眠	    	    记忆巩固、情绪调节
        浅睡眠 (Light)	 	占比最大，过渡阶段
        清醒 (W)	    	睡眠中断指标
        """
        ratios = metrics['stage_ratios']
        score = 100
        
        # 1. 深睡眠评分 (权重最高，占40%)
        deep_ratio = ratios['Deep']
        ideal_deep = self.IDEAL_ARCHITECTURE['Deep']
        if ideal_deep[0] <= deep_ratio <= ideal_deep[1]:
            deep_score = 100
        elif deep_ratio < ideal_deep[0]:
            # 深睡眠不足扣分
            deficit = (ideal_deep[0] - deep_ratio) / ideal_deep[0]
            deep_score = max(0, 100 - deficit * 150)
        else:
            # 过多深睡眠（少见但也扣分）
            excess = (deep_ratio - ideal_deep[1]) / ideal_deep[1]
            deep_score = max(60, 100 - excess * 80)
        
        # 2. REM睡眠评分 (权重30%)
        rem_ratio = ratios['REM']
        ideal_rem = self.IDEAL_ARCHITECTURE['REM']
        if ideal_rem[0] <= rem_ratio <= ideal_rem[1]:
            rem_score = 100
        elif rem_ratio < ideal_rem[0]:
            deficit = (ideal_rem[0] - rem_ratio) / ideal_rem[0]
            rem_score = max(0, 100 - deficit * 120)
        else:
            excess = (rem_ratio - ideal_rem[1]) / ideal_rem[1]
            rem_score = max(70, 100 - excess * 60)
        
        # 3. 浅睡眠评分 (权重20%)
        light_ratio = ratios['Light']
        ideal_light = self.IDEAL_ARCHITECTURE['Light']
        if ideal_light[0] <= light_ratio <= ideal_light[1]:
            light_score = 100
        else:
            deviation = abs(light_ratio - np.mean(ideal_light)) / np.mean(ideal_light)
            light_score = max(60, 100 - deviation * 100)
        
        # 4. 清醒比例评分 (权重10%)
        w_ratio = ratios['W']
        if w_ratio <= 0.05:
            wake_score = 100
        elif w_ratio <= 0.15:
            wake_score = 100 - (w_ratio - 0.05) * 400
        else:
            wake_score = max(0, 60 - (w_ratio - 0.15) * 300)
        
        # 加权平均
        total = (deep_score * 0.4 + rem_score * 0.3 + 
                light_score * 0.2 + wake_score * 0.1)
        
        return total
    
    def _score_continuity(self, metrics: Dict) -> float:
        """
        睡眠连续性评分
        
        评估指标:
        1. WASO (入睡后觉醒时间)
        2. 觉醒次数
        3. 碎片化指数
        
        参考: Buysse et al. (1989) PSQI标准
        """
        score = 100
        
        # 1. WASO评分 (权重40%)
        waso = metrics['waso_min']
        if waso <= 20:
            waso_score = 100
        elif waso <= 40:
            waso_score = 100 - (waso - 20) * 2
        elif waso <= 60:
            waso_score = 60 - (waso - 40) * 1.5
        else:
            waso_score = max(0, 30 - (waso - 60) * 0.5)
        
        # 2. 觉醒次数评分 (权重30%)
        awakenings = metrics['num_awakenings']
        if awakenings <= 2:
            awakening_score = 100
        elif awakenings <= 5:
            awakening_score = 100 - (awakenings - 2) * 15
        else:
            awakening_score = max(0, 55 - (awakenings - 5) * 10)
        
        # 3. 碎片化指数评分 (权重30%)
        frag_index = metrics['fragmentation_index']
        if frag_index <= 10:
            frag_score = 100
        elif frag_index <= 20:
            frag_score = 100 - (frag_index - 10) * 3
        else:
            frag_score = max(0, 70 - (frag_index - 20) * 2)
        
        total = (waso_score * 0.4 + awakening_score * 0.3 + frag_score * 0.3)
        return total
    
    def _score_timing(self, metrics: Dict) -> float:
        """
        时间特征评分
        
        评估:
        1. 入睡延迟
        2. REM潜伏期
        3. 睡眠周期数
        """
        score = 100
        
        # 1. 入睡延迟评分 (权重40%)
        latency = metrics['sleep_latency_min']
        if latency <= 15:
            latency_score = 100
        elif latency <= 30:
            latency_score = 100 - (latency - 15) * 2
        else:
            latency_score = max(0, 70 - (latency - 30))
        
        # 2. REM潜伏期评分 (权重30%)
        # 正常范围: 70-120分钟
        rem_lat = metrics['rem_latency_min']
        if rem_lat is None:
            rem_score = 0  # 无REM严重扣分
        elif 70 <= rem_lat <= 120:
            rem_score = 100
        elif rem_lat < 70:
            # 过早进入REM（可能是睡眠剥夺或嗜睡症）
            rem_score = 100 - (70 - rem_lat) * 0.8
        else:
            # REM延迟
            rem_score = max(50, 100 - (rem_lat - 120) * 0.5)
        
        # 3. 睡眠周期评分 (权重30%)
        # 正常: 4-6个完整周期
        cycles = metrics['num_cycles']
        if 4 <= cycles <= 6:
            cycle_score = 100
        elif cycles == 3 or cycles == 7:
            cycle_score = 85
        elif cycles == 2 or cycles == 8:
            cycle_score = 70
        else:
            cycle_score = 50
        
        total = (latency_score * 0.4 + rem_score * 0.3 + cycle_score * 0.3)
        return total
    
    def _detect_sleep_cycles(self) -> List[Tuple[int, int]]:
        """检测睡眠周期 - 带时间约束"""
        MIN_CYCLE_EPOCHS = 120   # 最小周期: 60分钟
        MIN_REM_EPOCHS = 6       # REM至少持续: 3分钟
        
        cycles = []
        cycle_start = None
        
        # 1. 先找到入睡点
        for i, stage in enumerate(self.hypnogram):
            if stage > 0:  # 找到第一个非清醒阶段
                cycle_start = i
                break
        
        if cycle_start is None:
            return []  # 没有睡眠数据
        
        # 2. 检测REM阶段作为周期边界
        i = cycle_start
        while i < len(self.hypnogram):
            # 寻找下一个REM开始
            rem_start = None
            while i < len(self.hypnogram):
                if self.hypnogram[i] == 1:
                    # 检查REM是否足够长
                    rem_len = 0
                    j = i
                    while j < len(self.hypnogram) and self.hypnogram[j] == 1:
                        rem_len += 1
                        j += 1
                    if rem_len >= MIN_REM_EPOCHS:
                        rem_start = i
                        break
                    else:
                        i = j  # 跳过短暂REM
                else:
                    i += 1
            
            if rem_start is None:
                break
            
            # 检查当前周期长度是否合理
            cycle_duration = rem_start - cycle_start
            if cycle_duration >= MIN_CYCLE_EPOCHS:
                cycles.append((cycle_start, rem_start))
                cycle_start = rem_start
            
            i = rem_start + 1
        
        # 最后一个周期
        if cycle_start is not None:
            cycles.append((cycle_start, len(self.hypnogram) - 1))
        
        return cycles
    
    def _count_awakenings(self) -> int:
        """计算觉醒次数（持续>1分钟的清醒期）"""
        from utils.smoother import smooth_hypnogram
        sleep_hypnogram_smooth = smooth_hypnogram(self.hypnogram, min_duration=3)

        count = 0
        wake_duration = 0
        
        for stage in sleep_hypnogram_smooth:
            if stage == 0:
                    wake_duration += 1
            else:
                if wake_duration >= 1:  # >1分钟
                    count += 1
                    wake_duration = 0

        if wake_duration >= 1:  # >1分钟
            count += 1
            wake_duration = 0

        return count - 2
    
    def _calculate_fragmentation(self) -> float:
        """
        睡眠碎片化指数
        
        定义: 睡眠阶段转换次数 / 总epoch数 × 100
        """
        transitions = np.sum(np.diff(self.hypnogram) != 0)
        return (transitions / self.total_epochs) * 100
    
    def _generate_recommendations(self, metrics: Dict, score: int) -> List[str]:
        """生成个性化改善建议"""
        recommendations = []
        
        # 1. 睡眠效率建议
        if metrics['sleep_efficiency'] < 85:
            recommendations.append(
                "💡 睡眠效率偏低，建议:\n"
                "  - 固定作息时间，培养睡眠-觉醒节律\n"
                "  - 避免在床上进行非睡眠活动（刺激控制疗法）"
            )
        
        # 2. 深睡眠建议
        if metrics['stage_ratios']['Deep'] < 0.13:
            recommendations.append(
                "💤 深睡眠不足，建议:\n"
                "  - 睡前3-4小时进行中等强度运动\n"
                "  - 保持卧室温度在18-20°C\n"
                "  - 减少酒精和咖啡因摄入"
            )
        
        # 3. REM睡眠建议
        if metrics['stage_ratios']['REM'] < 0.15:
            recommendations.append(
                "🧠 REM睡眠不足，建议:\n"
                "  - 保证7-9小时睡眠时长\n"
                "  - 避免睡前饮酒（抑制REM）\n"
                "  - 减轻压力，REM与情绪调节相关"
            )
        
        # 4. 睡眠连续性建议
        if metrics['num_awakenings'] > 3:
            recommendations.append(
                "🌙 睡眠碎片化，建议:\n"
                "  - 检查睡眠环境（噪音、光线、温度）\n"
                "  - 考虑筛查睡眠呼吸暂停\n"
                "  - 避免睡前大量饮水"
            )
        
        # 5. 入睡困难建议
        if metrics['sleep_latency_min'] > 30:
            recommendations.append(
                "😴 入睡困难，建议:\n"
                "  - 睡前1小时避免蓝光暴露\n"
                "  - 尝试渐进性肌肉放松训练\n"
                "  - 建立固定的睡前仪式"
            )
        
        if not recommendations:
            recommendations.append("✅ 睡眠质量良好，继续保持健康作息！")
        
        return recommendations


# 简化版本（供快速调用）
# def calculate_simple_score(stats: Dict) -> int:
#     """
#     快速评分版本（兼容现有接口）
    
#     参数:
#         stats: {'W_ratio': 0.1, 'REM_ratio': 0.2, ...}
    
#     返回:
#         质量分数 0-100
#     """
#     score = 100
    
#     # 深睡眠权重30%
#     if 0.13 <= stats['Deep_ratio'] <= 0.23:
#         deep_score = 100
#     elif stats['Deep_ratio'] < 0.13:
#         deep_score = (stats['Deep_ratio'] / 0.13) * 100
#     else:
#         deep_score = 100 - (stats['Deep_ratio'] - 0.23) * 200
    
#     # REM权重30%
#     if 0.20 <= stats['REM_ratio'] <= 0.25:
#         rem_score = 100
#     elif stats['REM_ratio'] < 0.20:
#         rem_score = (stats['REM_ratio'] / 0.20) * 100
#     else:
#         rem_score = 100 - (stats['REM_ratio'] - 0.25) * 200
    
#     # 清醒权重40%
#     wake_score = max(0, 100 - stats['W_ratio'] * 500)
    
#     total = int(deep_score * 0.3 + rem_score * 0.3 + wake_score * 0.4)
#     return max(0, min(100, total))
