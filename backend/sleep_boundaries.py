import numpy as np
import os
import glob
from imblearn.over_sampling import RandomOverSampler
import joblib
from tqdm import tqdm
from collections import Counter
import gc
import re
from datetime import timedelta

def get_robust_sleep_boundaries(starts, ends, stages, total_duration_sec):
    """
    使用双指针收缩法，排除入睡前和醒来后的零星干扰，寻找主要睡眠区间。
    GAP_THRESHOLD: 判定为“非睡眠长间隔”的阈值
    MIN_SLEEP_LIMIT: 预期的最小睡眠跨度，默认6小时
    BUFFER_SEC: 在最终结果中，睡眠前后各增加的缓冲时间
    """
    # 参数定义
    GAP_THRESHOLD_FOR_BLOCK_SEPARATION = 1 * 3600  # 区分不同睡眠块的清醒间隔：1小时
    GAP_THRESHOLD_FOR_EDGE_CLEANING = 1800  # 清理块边缘的清醒间隔：30分钟
    MIN_SLEEP_BLOCK_DURATION = 3 * 3600 # 最短的有效睡眠块时长：3小时
    MIN_SLEEP_LIMIT_FOR_ROBUSTNESS = 6 * 3600 # 鲁棒性检查的最小睡眠跨度：6小时
    BUFFER_SEC = 1200
    # 1. 过滤掉 'W' 和 'IGNORE' 阶段
    # 确保 stages 数组在外部已经被正确处理，例如 'sleep stage ?' 标记为 'IGNORE'
    valid_sleep_stage_mask = (stages != 'W') & (stages != 'IGNORE')
    
    # 获取这些有效睡眠阶段在原始 `starts` 数组中的索引
    non_w_original_indices = np.where(valid_sleep_stage_mask)[0]
    if len(non_w_original_indices) == 0:
        print("警告: 未找到任何有效的睡眠阶段 (非W且非IGNORE)。")
        return 0.0, total_duration_sec - 0.01
    # 2. 识别所有独立的睡眠块 (Sleep Blocks)
    sleep_blocks = [] # 存储每个睡眠块的 [(start_idx_in_non_w_original_indices, end_idx_in_non_w_original_indices)]
    current_block_start_idx = non_w_original_indices[0]
    
    for i in range(len(non_w_original_indices) - 1):
        idx_current = non_w_original_indices[i]
        idx_next = non_w_original_indices[i+1]
        
        # 计算当前有效睡眠阶段结束 到 下一个有效睡眠阶段开始 之间的清醒间隔
        gap = starts[idx_next] - ends[idx_current]
        
        if gap > GAP_THRESHOLD_FOR_BLOCK_SEPARATION:
            # 发现一个大间隔，这意味着一个新的睡眠块开始
            block_start = current_block_start_idx
            block_end = idx_current
            sleep_blocks.append((block_start, block_end))
            current_block_start_idx = idx_next
            
    # 添加最后一个睡眠块
    sleep_blocks.append((current_block_start_idx, non_w_original_indices[-1]))
    print(f"识别出 {len(sleep_blocks)} 个潜在睡眠块。")
    # 3. 计算每个睡眠块的持续时间并选择最长的
    longest_block = None
    max_block_duration = 0
    for block_start_orig_idx, block_end_orig_idx in sleep_blocks:
        block_onset = starts[block_start_orig_idx]
        block_offset = ends[block_end_orig_idx]
        block_duration = block_offset - block_onset
        if block_duration > max_block_duration and block_duration >= MIN_SLEEP_BLOCK_DURATION:
            max_block_duration = block_duration
            longest_block = (block_start_orig_idx, block_end_orig_idx)
    if longest_block is None:
        print(f"警告: 未找到持续时间超过 {MIN_SLEEP_BLOCK_DURATION / 3600:.1f} 小时的主要睡眠块。")
        # 如果没有找到足够长的主睡眠块，可以返回空或者整个数据的范围，取决于你的处理逻辑
        return 0.0, total_duration_sec - 0.01 
    # 4. 对选定的主睡眠块应用双指针收缩
    # 将 longest_block 的原始索引转换回其在 `non_w_original_indices` 中的相应位置
    # 这样可以兼容之前的双指针逻辑
    left_ptr_idx = np.where(non_w_original_indices == longest_block[0])[0][0]
    right_ptr_idx = np.where(non_w_original_indices == longest_block[1])[0][0]
    # 重新计算这个块的睡眠中心时间
    block_starts_for_center = starts[non_w_original_indices[left_ptr_idx:right_ptr_idx+1]]
    block_ends_for_center = ends[non_w_original_indices[left_ptr_idx:right_ptr_idx+1]]
    
    weighted_midpoints = (block_starts_for_center + block_ends_for_center) / 2
    weighted_durations = block_ends_for_center - block_starts_for_center
    if np.sum(weighted_durations) > 0:
        sleep_center_time = np.sum(weighted_midpoints * weighted_durations) / np.sum(weighted_durations)
    else:
        sleep_center_time = (block_starts_for_center[0] + block_ends_for_center[-1]) / 2
    # 执行收缩，类似于 get_robust_sleep_boundaries_v2 的逻辑
    while left_ptr_idx < right_ptr_idx:
        current_onset_candidate = starts[non_w_original_indices[left_ptr_idx]]
        current_offset_candidate = ends[non_w_original_indices[right_ptr_idx]]
        
        current_sleep_span = current_offset_candidate - current_onset_candidate
        
        if current_sleep_span <= MIN_SLEEP_LIMIT_FOR_ROBUSTNESS and (right_ptr_idx - left_ptr_idx <= 1):
            break
            
        changed = False
        
        # 左指针右移
        if left_ptr_idx + 1 <= right_ptr_idx:
            original_idx_current = non_w_original_indices[left_ptr_idx]
            original_idx_next_valid_sleep = non_w_original_indices[left_ptr_idx + 1]
            gap_duration = starts[original_idx_next_valid_sleep] - ends[original_idx_current]
            if gap_duration > GAP_THRESHOLD_FOR_EDGE_CLEANING:
                if starts[original_idx_next_valid_sleep] < sleep_center_time:
                    left_ptr_idx += 1
                    changed = True
                elif left_ptr_idx == np.where(non_w_original_indices == longest_block[0])[0][0]: # 如果是这个块的第一个有效睡眠段，允许移动
                    left_ptr_idx += 1
                    changed = True
        
        # 右指针左移
        if right_ptr_idx - 1 >= left_ptr_idx:
            original_idx_current = non_w_original_indices[right_ptr_idx]
            original_idx_prev_valid_sleep = non_w_original_indices[right_ptr_idx - 1]
            gap_duration = starts[original_idx_current] - ends[original_idx_prev_valid_sleep]
            if gap_duration > GAP_THRESHOLD_FOR_EDGE_CLEANING:
                if ends[original_idx_prev_valid_sleep] > sleep_center_time:
                    right_ptr_idx -= 1
                    changed = True
                elif right_ptr_idx == np.where(non_w_original_indices == longest_block[1])[0][0]: # 如果是这个块的最后一个有效睡眠段，允许移动
                    right_ptr_idx -= 1
                    changed = True
        
        if not changed:
            break
    final_onset = float(starts[non_w_original_indices[left_ptr_idx]])
    final_offset = float(ends[non_w_original_indices[right_ptr_idx]])
    
    final_onset = max(0.0, final_onset - BUFFER_SEC)
    final_offset = min(total_duration_sec - 0.01, final_offset + BUFFER_SEC)
        
    return final_onset, final_offset