from entity.response import AnalysisResult, SleepMetrics, SleepStats, SubScores
from services.quality_scorer import SleepQualityScorer
from utils import downsample_hypnogram, smooth_hypnogram
from datetime import datetime
import numpy as np
import os
import tempfile


def _build_core_sleep_stats(core_hypnogram):
    buffer_epochs = 40
    if len(core_hypnogram) > buffer_epochs * 2:
        effective_hypnogram = core_hypnogram[buffer_epochs:-buffer_epochs]
    else:
        effective_hypnogram = core_hypnogram

    total_epochs = len(effective_hypnogram)
    if total_epochs == 0:
        return {
            "W_ratio": 0.0,
            "REM_ratio": 0.0,
            "Light_ratio": 0.0,
            "Deep_ratio": 0.0,
        }

    return {
        "W_ratio": effective_hypnogram.count(0) / total_epochs,
        "REM_ratio": effective_hypnogram.count(1) / total_epochs,
        "Light_ratio": effective_hypnogram.count(2) / total_epochs,
        "Deep_ratio": effective_hypnogram.count(3) / total_epochs,
    }


class SleepAnalyzer:
    def __init__(self, predictor, model_id=None, model_name=None, model_family=None):
        self.predictor = predictor
        self.model_id = model_id
        self.model_name = model_name
        self.model_family = model_family

    async def analyze_edf(self, file_content: bytes, filename: str) -> AnalysisResult:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".edf") as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            epochs = self.predictor.preprocess(tmp_path)
            result = self.predictor.predict(epochs)
            hypnogram_full = result["hypnogram"]

            total_duration_sec = len(hypnogram_full) * 30
            starts = np.array([i * 30 for i in range(len(hypnogram_full))])
            ends = np.array([(i + 1) * 30 for i in range(len(hypnogram_full))])
            stage_map = {0: "W", 1: "REM", 2: "Light", 3: "Deep"}
            stages = np.array([stage_map[s] for s in hypnogram_full])

            sleep_onset_sec, sleep_offset_sec = self.predictor.get_robust_sleep_boundaries(
                starts, ends, stages, total_duration_sec
            )

            sleep_onset_epoch = int(sleep_onset_sec / 30)
            sleep_offset_epoch = int(sleep_offset_sec / 30)

            sleep_hypnogram_raw = hypnogram_full[sleep_onset_epoch:sleep_offset_epoch]
            sleep_hypnogram_smooth = smooth_hypnogram(sleep_hypnogram_raw, min_duration=3)
            sleep_hypnogram_lite = downsample_hypnogram(sleep_hypnogram_raw, window_size=4)

            recording_start_time = self.predictor.recording_start_time
            if recording_start_time is None:
                recording_start_time = datetime.now().isoformat()

            core_stats = _build_core_sleep_stats(sleep_hypnogram_raw)
            core_duration_hours = round(len(sleep_hypnogram_raw) * 30 / 3600, 2)

            scorer = SleepQualityScorer(sleep_hypnogram_raw)
            quality_report = scorer.calculate_comprehensive_score()
            total_epochs = len(hypnogram_full)

            return AnalysisResult(
                model_id=self.model_id,
                model_name=self.model_name,
                model_family=self.model_family,
                hypnogram_full=hypnogram_full,
                sleep_hypnogram_raw=sleep_hypnogram_raw,
                sleep_hypnogram_smooth=sleep_hypnogram_smooth,
                sleep_hypnogram_lite=sleep_hypnogram_lite,
                recording_start_time=recording_start_time,
                sleep_onset_epoch=sleep_onset_epoch,
                sleep_offset_epoch=sleep_offset_epoch,
                stats=SleepStats(**core_stats),
                quality_score=quality_report["total_score"],
                total_epochs=total_epochs,
                duration_hours=core_duration_hours,
                sleep_efficiency=int(quality_report["metrics"]["sleep_efficiency"]),
                sleep_latency=int(quality_report["metrics"]["sleep_latency_min"]),
                waso=int(quality_report["metrics"]["waso_min"]),
                rem_latency=(
                    int(quality_report["metrics"]["rem_latency_min"])
                    if quality_report["metrics"]["rem_latency_min"]
                    else None
                ),
                sub_scores=SubScores(**quality_report["sub_scores"]),
                metrics=SleepMetrics(
                    sleep_efficiency=quality_report["metrics"]["sleep_efficiency"],
                    sleep_latency_min=quality_report["metrics"]["sleep_latency_min"],
                    waso_min=quality_report["metrics"]["waso_min"],
                    rem_latency_min=quality_report["metrics"]["rem_latency_min"],
                    num_cycles=quality_report["metrics"]["num_cycles"],
                    num_awakenings=quality_report["metrics"]["num_awakenings"],
                    fragmentation_index=quality_report["metrics"]["fragmentation_index"],
                    total_sleep_time_hours=quality_report["metrics"]["total_sleep_time_hours"],
                ),
                recommendations=quality_report["recommendations"],
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
