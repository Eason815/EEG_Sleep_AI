"""
睡眠数据平滑和下采样工具
"""
import numpy as np
from scipy.ndimage import median_filter
from scipy.stats import mode


def smooth_hypnogram(hypnogram, min_duration=3):
    """
    平滑睡眠阶梯图，去除短暂的抖动和噪声
    
    参数:
        hypnogram: 原始睡眠分期数组
        min_duration: 最小持续时间（epoch数），短于此的片段会被合并
    
    返回:
        平滑后的睡眠分期数组
    """
    # 1. 中值滤波（去除单点噪声）
    smoothed = median_filter(hypnogram, size=3, mode='nearest')
    
    # 2. 合并短暂片段
    result = list(smoothed)
    i = 0
    while i < len(result):
        current_stage = result[i]
        # 找到当前阶段的结束位置
        j = i
        while j < len(result) and result[j] == current_stage:
            j += 1
        
        # 如果持续时间太短，用前一个阶段替换
        if j - i < min_duration and i > 0 and j < len(result):
            # 用前一个阶段填充
            for k in range(i, j):
                result[k] = result[i-1]
        
        i = j
    
    return result


def downsample_hypnogram(hypnogram, window_size=4):
    """
    下采样睡眠阶梯图到更大的时间窗口
    
    参数:
        hypnogram: 原始数组
        window_size: 聚合窗口大小（4 = 2分钟，因为每个epoch是30秒）
    
    返回:
        下采样后的数组（数据量减少到1/window_size）
    """
    downsampled = []
    for i in range(0, len(hypnogram), window_size):
        window = hypnogram[i:i+window_size]
        # 使用众数（最频繁的阶段）
        most_common = mode(window, keepdims=True).mode[0]
        downsampled.append(int(most_common))
    
    return downsampled
