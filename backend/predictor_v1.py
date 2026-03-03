from abc import ABC, abstractmethod
import numpy as np

class BaseSleepPredictor(ABC):
    """
    抽象基类：定义标准接口
    任何模型必须实现这 3 个方法
    """
    @abstractmethod
    def load_model(self, model_path: str):
        """加载模型权重"""
        pass
    
    @abstractmethod
    def preprocess(self, edf_path: str) -> np.ndarray:
        """
        输入：EDF 文件路径
        输出：(N, 1, 3000) 的 numpy 数组
        """
        pass
    
    @abstractmethod
    def predict(self, epochs: np.ndarray) -> dict:
        """
        输入：预处理后的数据
        输出：标准格式的字典
        {
            "hypnogram": [0, 1, 2, ...],  # 每30s的分期
            "stats": {
                "W_ratio": 0.15,
                "REM_ratio": 0.20,
                "Light_ratio": 0.45,
                "Deep_ratio": 0.20
            },
            "quality_score": 85  # 0-100 分
        }
        """
        pass


import mne
import torch
import numpy as np
from train import SleepStageNetV8  
import os
from pathlib import Path


class SleepPredictorV1(BaseSleepPredictor):
    def __init__(self, model_path, device='cuda', window_size=15):
        self.model_path = model_path
        self.device = device if torch.cuda.is_available() else 'cpu'
        self.window_size = window_size
        self.model = None
    
    def load_model(self, model_class):
        """加载模型权重"""
        print(f"[加载模型] 路径: {self.model_path}")
        
        # 1. 先实例化模型
        self.model = model_class(num_classes=5, window_size=self.window_size).to(self.device)
        
        # 2. 加载权重 (确保 load_state_dict 拿到的是 state_dict)
        # map_location 处理设备差异
        state_dict = torch.load(self.model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
            
        self.model.eval()
        
        total_params = sum(p.numel() for p in self.model.parameters())
        print(f"[加载模型] 成功加载，参数量: {total_params:,}")

    
    def preprocess(self, edf_path):
        """严格按照你 process.py 的逻辑"""
        # 1. 读取并裁剪
        raw = mne.io.read_raw_edf(edf_path, preload=True, verbose=False)
        
        # 2. 通道选择
        if 'EEG Fpz-Cz' in raw.ch_names:
            raw.pick_channels(['EEG Fpz-Cz'])
        else:
            # 兼容其他数据集
            raw.pick_types(eeg=True)
        
        # 3. 重采样到 100Hz
        if raw.info['sfreq'] != 100:
            raw.resample(100, verbose=False)
        
        # 4. 滤波（与训练时保持一致）
        raw.filter(l_freq=0.3, h_freq=35, method='iir', verbose=False)
        
        # 5. 切分为 30s Epochs
        data = raw.get_data()[0]  # (n_samples,)
        epoch_len = 3000  # 30s * 100Hz
        n_epochs = len(data) // epoch_len
        
        epochs = []
        for i in range(n_epochs):
            epoch = data[i*epoch_len : (i+1)*epoch_len]
            
            # 6. Z-score 标准化（每个 epoch 独立）
            mean, std = epoch.mean(), epoch.std()
            epoch = (epoch - mean) / (std + 1e-8)
            epochs.append(epoch)
        
        return np.array(epochs).reshape(n_epochs, 1, 3000)  # (N, 1, 3000)
    
    def predict(self, epochs):
        half_window = self.window_size // 2
        results = []
        
        with torch.no_grad():
            for i in range(len(epochs)):
                # 构建时序窗口（边缘用 edge padding）
                start = max(0, i - half_window)
                end = min(len(epochs), i + half_window + 1)
                
                window = epochs[start:end]
                
                # 边缘填充到 window_size
                if len(window) < self.window_size:
                    pad_left = max(0, half_window - i)
                    pad_right = max(0, (i + half_window + 1) - len(epochs))
                    window = np.pad(window, ((pad_left, pad_right), (0, 0), (0, 0)), mode='edge')
                
                # 转为 Tensor (1, window_size, 1, 3000)
                x = torch.from_numpy(window).unsqueeze(0).float().to(self.device)
                
                # 预测（5 分类）
                output = self.model(x)
                pred = output.argmax(1).item()
                results.append(pred)
        
        # 映射 5 类 -> 4 类（与你的评估逻辑一致）
        def map_5to4(label):
            if label == 0: return 0  # W
            if label == 4: return 1  # REM
            if label in [1, 2]: return 2  # Light
            if label == 3: return 3  # Deep
            return label
        
        results_4cls = [map_5to4(r) for r in results]
        
        # 计算统计指标
        total = len(results_4cls)
        stats = {
            "W_ratio": results_4cls.count(0) / total,
            "REM_ratio": results_4cls.count(1) / total,
            "Light_ratio": results_4cls.count(2) / total,
            "Deep_ratio": results_4cls.count(3) / total
        }
        
        # 简易质量分数（可自定义算法）
        quality_score = int((stats["Deep_ratio"] * 0.3 + stats["REM_ratio"] * 0.3 + 
                            (1 - stats["W_ratio"]) * 0.4) * 100)
        
        return {
            "hypnogram": results_4cls,
            "stats": stats,
            "quality_score": quality_score
        }
    
    def get_robust_sleep_boundaries(self, starts, ends, stages, total_duration_sec):
        """
        使用双指针收缩法，排除入睡前和醒来后的零星干扰，寻找主要睡眠区间
        """
        GAP_THRESHOLD_FOR_BLOCK_SEPARATION = 1 * 3600
        GAP_THRESHOLD_FOR_EDGE_CLEANING = 1800
        MIN_SLEEP_BLOCK_DURATION = 3 * 3600
        MIN_SLEEP_LIMIT_FOR_ROBUSTNESS = 6 * 3600
        BUFFER_SEC = 1200
        
        # 1. 过滤有效睡眠阶段
        valid_sleep_stage_mask = (stages != 'W') & (stages != 'IGNORE')
        non_w_original_indices = np.where(valid_sleep_stage_mask)[0]
        
        if len(non_w_original_indices) == 0:
            print("⚠️ 未找到任何有效的睡眠阶段")
            return 0.0, total_duration_sec - 0.01
        
        # 2. 识别睡眠块
        sleep_blocks = []
        current_block_start_idx = non_w_original_indices[0]
        
        for i in range(len(non_w_original_indices) - 1):
            idx_current = non_w_original_indices[i]
            idx_next = non_w_original_indices[i+1]
            gap = starts[idx_next] - ends[idx_current]
            
            if gap > GAP_THRESHOLD_FOR_BLOCK_SEPARATION:
                sleep_blocks.append((current_block_start_idx, idx_current))
                current_block_start_idx = idx_next
        
        sleep_blocks.append((current_block_start_idx, non_w_original_indices[-1]))
        print(f"🔍 识别出 {len(sleep_blocks)} 个潜在睡眠块")
        
        # 3. 选择最长的睡眠块
        longest_block = None
        max_block_duration = 0
        
        for block_start_orig_idx, block_end_orig_idx in sleep_blocks:
            block_duration = ends[block_end_orig_idx] - starts[block_start_orig_idx]
            if block_duration > max_block_duration and block_duration >= MIN_SLEEP_BLOCK_DURATION:
                max_block_duration = block_duration
                longest_block = (block_start_orig_idx, block_end_orig_idx)
        
        if longest_block is None:
            print(f"⚠️ 未找到持续 {MIN_SLEEP_BLOCK_DURATION/3600:.1f}h 以上的睡眠块")
            return 0.0, total_duration_sec - 0.01
        
        # 4. 双指针收缩
        left_ptr_idx = np.where(non_w_original_indices == longest_block[0])[0][0]
        right_ptr_idx = np.where(non_w_original_indices == longest_block[1])[0][0]
        
        # 计算睡眠中心
        block_starts = starts[non_w_original_indices[left_ptr_idx:right_ptr_idx+1]]
        block_ends = ends[non_w_original_indices[left_ptr_idx:right_ptr_idx+1]]
        weighted_midpoints = (block_starts + block_ends) / 2
        weighted_durations = block_ends - block_starts
        
        if np.sum(weighted_durations) > 0:
            sleep_center_time = np.sum(weighted_midpoints * weighted_durations) / np.sum(weighted_durations)
        else:
            sleep_center_time = (block_starts[0] + block_ends[-1]) / 2
        
        # 收缩逻辑
        while left_ptr_idx < right_ptr_idx:
            current_onset = starts[non_w_original_indices[left_ptr_idx]]
            current_offset = ends[non_w_original_indices[right_ptr_idx]]
            current_span = current_offset - current_onset
            
            if current_span <= MIN_SLEEP_LIMIT_FOR_ROBUSTNESS and (right_ptr_idx - left_ptr_idx <= 1):
                break
            
            changed = False
            
            # 左指针右移
            if left_ptr_idx + 1 <= right_ptr_idx:
                idx_curr = non_w_original_indices[left_ptr_idx]
                idx_next = non_w_original_indices[left_ptr_idx + 1]
                gap = starts[idx_next] - ends[idx_curr]
                
                if gap > GAP_THRESHOLD_FOR_EDGE_CLEANING and starts[idx_next] < sleep_center_time:
                    left_ptr_idx += 1
                    changed = True
            
            # 右指针左移
            if right_ptr_idx - 1 >= left_ptr_idx:
                idx_curr = non_w_original_indices[right_ptr_idx]
                idx_prev = non_w_original_indices[right_ptr_idx - 1]
                gap = starts[idx_curr] - ends[idx_prev]
                
                if gap > GAP_THRESHOLD_FOR_EDGE_CLEANING and ends[idx_prev] > sleep_center_time:
                    right_ptr_idx -= 1
                    changed = True
            
            if not changed:
                break
        
        # 添加缓冲区
        final_onset = max(0.0, float(starts[non_w_original_indices[left_ptr_idx]]) - BUFFER_SEC)
        final_offset = min(total_duration_sec - 0.01, float(ends[non_w_original_indices[right_ptr_idx]]) + BUFFER_SEC)
        
        print(f"✅ 主睡眠区间: {final_onset/3600:.2f}h - {final_offset/3600:.2f}h (总时长 {(final_offset-final_onset)/3600:.2f}h)")
        return final_onset, final_offset
