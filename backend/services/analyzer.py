from models.predictor_v1 import SleepPredictorV1
from services.quality_scorer import SleepQualityScorer
from entity.response import AnalysisResult, SleepStats, SubScores, SleepMetrics
from utils.smoother import smooth_hypnogram, downsample_hypnogram
import tempfile
import os
import numpy as np
from datetime import datetime

class SleepAnalyzer:
    """睡眠分析服务"""
    
    def __init__(self, model_class, model_path: str, device: str = 'cuda'):
        """初始化分析器"""
        # 1. 传入路径初始化
        self.predictor = SleepPredictorV1(
            model_path=model_path, 
            device=device,
            window_size=15
        )

        # 2. 传入类对象加载
        self.predictor.load_model(model_class) 
    
    async def analyze_edf(self, file_content: bytes, filename: str) -> AnalysisResult:
        """
        分析EDF文件
        
        参数:
            file_content: 文件二进制内容
            filename: 文件名
        
        返回:
            AnalysisResult对象
        """
        # 1. 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.edf') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # 2. 预处理（会提取时间戳）
            epochs = self.predictor.preprocess(tmp_path)
            
            # 3. 推理 - 生成完整hypnogram
            result = self.predictor.predict(epochs)
            hypnogram_full = result['hypnogram']
            
            # 4. 调用睡眠边界算法
            total_duration_sec = len(hypnogram_full) * 30
            
            # 构建 starts, ends, stages 数组用于边界检测
            starts = np.array([i * 30 for i in range(len(hypnogram_full))])
            ends = np.array([(i + 1) * 30 for i in range(len(hypnogram_full))])
            stage_map = {0: 'W', 1: 'REM', 2: 'Light', 3: 'Deep'}
            stages = np.array([stage_map[s] for s in hypnogram_full])
            
            # 调用边界算法
            sleep_onset_sec, sleep_offset_sec = self.predictor.get_robust_sleep_boundaries(
                starts, ends, stages, total_duration_sec
            )
            
            # 转换为epoch索引
            sleep_onset_epoch = int(sleep_onset_sec / 30)
            sleep_offset_epoch = int(sleep_offset_sec / 30)
            
            # 5. 裁剪核心睡眠区间
            sleep_hypnogram_raw = hypnogram_full[sleep_onset_epoch:sleep_offset_epoch]
            
            # 6. 生成平滑和轻量版本
            sleep_hypnogram_smooth = smooth_hypnogram(sleep_hypnogram_raw, min_duration=3)
            sleep_hypnogram_lite = downsample_hypnogram(sleep_hypnogram_raw, window_size=4)
            
            # 7. 提取时间戳
            recording_start_time = self.predictor.recording_start_time
            if recording_start_time is None:
                recording_start_time = datetime.now().isoformat()
            
            # 8. 高级质量评分（基于核心睡眠区间）
            scorer = SleepQualityScorer(sleep_hypnogram_raw)
            quality_report = scorer.calculate_comprehensive_score()
            
            # 9. 计算统计指标（基于核心睡眠区间）
            total_epochs = len(hypnogram_full)
            duration_hours = (total_epochs * 0.5 - 40) / 60
            
            # 10. 构建响应
            return AnalysisResult(
                # 完整数据
                hypnogram_full=hypnogram_full,
                
                # 核心睡眠数据（3个版本）
                sleep_hypnogram_raw=sleep_hypnogram_raw,
                sleep_hypnogram_smooth=sleep_hypnogram_smooth,
                sleep_hypnogram_lite=sleep_hypnogram_lite,
                
                # 时间信息
                recording_start_time=recording_start_time,
                sleep_onset_epoch=sleep_onset_epoch,
                sleep_offset_epoch=sleep_offset_epoch,
                
                # 统计信息（基于核心睡眠区间）
                stats=SleepStats(**result['stats']),
                quality_score=quality_report['total_score'],
                total_epochs=total_epochs,
                duration_hours=round(duration_hours, 2),
                sleep_efficiency=int(quality_report['metrics']['sleep_efficiency']),
                sleep_latency=int(quality_report['metrics']['sleep_latency_min']),
                waso=int(quality_report['metrics']['waso_min']),
                rem_latency=int(quality_report['metrics']['rem_latency_min']) 
                    if quality_report['metrics']['rem_latency_min'] else None,
                
                # 新增：各维度得分
                sub_scores=SubScores(**quality_report['sub_scores']),
                
                # 新增：详细睡眠指标
                metrics=SleepMetrics(
                    sleep_efficiency=quality_report['metrics']['sleep_efficiency'],
                    sleep_latency_min=quality_report['metrics']['sleep_latency_min'],
                    waso_min=quality_report['metrics']['waso_min'],
                    rem_latency_min=quality_report['metrics']['rem_latency_min'],
                    num_cycles=quality_report['metrics']['num_cycles'],
                    num_awakenings=quality_report['metrics']['num_awakenings'],
                    fragmentation_index=quality_report['metrics']['fragmentation_index'],
                    total_sleep_time_hours=quality_report['metrics']['total_sleep_time_hours']
                ),
                
                # 新增：睡眠建议
                recommendations=quality_report['recommendations']
            )
            
        finally:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
