from predictor_v1 import SleepPredictorV1
from services.quality_scorer import SleepQualityScorer, calculate_simple_score
from models.response import AnalysisResult, SleepStats
from pathlib import Path
import tempfile
import os

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
            # 2. 预处理
            epochs = self.predictor.preprocess(tmp_path)
            
            # 3. 推理
            result = self.predictor.predict(epochs)
            
            # 4. 高级质量评分
            scorer = SleepQualityScorer(result['hypnogram'])
            quality_report = scorer.calculate_comprehensive_score()
            
            # 5. 计算额外指标
            total_epochs = len(result['hypnogram'])
            duration_hours = total_epochs * 0.5 / 60
            
            # 睡眠效率
            total_sleep = sum(1 for x in result['hypnogram'] if x > 0)
            sleep_efficiency = (total_sleep / total_epochs) * 100
            
            # 6. 构建响应
            return AnalysisResult(
                hypnogram=result['hypnogram'],
                stats=SleepStats(**result['stats']),
                quality_score=quality_report['total_score'],
                total_epochs=total_epochs,
                duration_hours=round(duration_hours, 2),
                sleep_efficiency=round(sleep_efficiency, 2),
                sleep_latency=int(quality_report['metrics']['sleep_latency_min']),
                waso=int(quality_report['metrics']['waso_min']),
                rem_latency=int(quality_report['metrics']['rem_latency_min']) 
                    if quality_report['metrics']['rem_latency_min'] else None
            )
            
        finally:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
