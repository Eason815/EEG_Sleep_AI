import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
import mne
mne.set_log_level('WARNING')
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

def short_stage(desc):
    s = str(desc).lower().strip()
    # 精确匹配单字符标注或包含“sleep stage X”等形式
    if re.search(r'\bw\b', s) or 'wake' in s or 'awake' in s:
        return 'W'
    if re.search(r'\br\b', s) or 'rem' in s:
        return 'R'
    if 'stage 1' in s or s in ('1', 'n1'):
        return 'N1'
    if 'stage 2' in s or s in ('2', 'n2'):
        return 'N2'
    if 'stage 3' in s or 'stage 4' in s or 'n3' in s or 'sws' in s:
        return 'N3'
    if '?' in desc or 'unknown' in desc or 'undefined' in desc: return 'IGNORE' 
    return s  # 保留原描述以便调试

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

def trim_raw(patient_id, psg_file, annot_file):
    raw = mne.io.read_raw_edf(psg_file, preload=True, verbose=False)

    total_duration_sec = raw.times[-1] 
    # 在裁剪逻辑之前，统一将 raw.annotations 的 duration 进行微调
    # 确保标注的结束时间不会超出 signal 的末端
    raw.annotations.duration[raw.annotations.onset + raw.annotations.duration > total_duration_sec] -= 0.01
    # --- 加载并设置标注 ---
    if os.path.exists(annot_file):
        annot = mne.read_annotations(annot_file)
        processed_descriptions = [short_stage(d) for d in annot.description]
        fixed_ann = mne.Annotations(
            onset=annot.onset,
            duration=annot.duration,
            description=processed_descriptions
        )        
        raw.set_annotations(fixed_ann)

    sfreq = raw.info['sfreq']
    total_samples = raw.n_times
    total_duration_sec = total_samples / sfreq
    
    # 提取标注信息
    ann = raw.annotations
    onsets = np.array(ann.onset, dtype=float)
    raw_durs = np.array(ann.duration, dtype=float)
    descs = np.array(ann.description, dtype=object)
    
    # 用相邻 onset 差值推导可能的 duration (针对只有 onset 没有 duration 的数据集)
    derived = np.diff(np.append(onsets, total_duration_sec))
    durs = np.where(raw_durs > 0, raw_durs, derived[:len(onsets)])

    descs = np.array(ann.description, dtype=object)
    
    # 计算 starts / ends 如前（durs 已经用 derived 填充）
    starts = onsets
    ends = starts + durs

    # 过滤：去掉 start >= total_duration，或 end <= start，或时长太短（例如 < 1s）
    valid_mask = (starts < total_duration_sec) & (ends > starts + 1.0)
    starts = starts[valid_mask]
    ends = ends[valid_mask]
    descs = descs[valid_mask]

    # 转换标签
    f_stages = np.array([short_stage(d) for d in descs], dtype=object)
    non_w_idx = np.where((f_stages != 'W') & (f_stages != 'IGNORE'))[0]
    
    if len(non_w_idx) > 0:
        sleep_onset, wake_time = get_robust_sleep_boundaries(starts, ends, f_stages, raw.times[-1])
        
        # --- 执行物理裁剪前输出验证 ---
        clipped_duration = wake_time - sleep_onset
        reduction_ratio = (1 - clipped_duration / total_duration_sec) * 100
    
    print(f"patient_id {patient_id},sleep onset at {timedelta(seconds=int(sleep_onset))}, wake at {timedelta(seconds=int(wake_time))}, "
                f"Clipped={clipped_duration/3600:.1f}h, Discarded={reduction_ratio:.1f}%")
    raw.crop(tmin=sleep_onset, tmax=wake_time)        
    return raw

# --- 配置部分 ---
# 定义要处理的文件夹：字典键是 "类型" (train/val/test)，值是文件夹路径
folder_configs = {
    'train': r'./sleep-edf/data/train',  
    'val': r'./sleep-edf/data/val',      
    # 'test': r'./sleep-edf/data/test'     
}

n_jobs = 1  # 并行核心数（1 代表串行，稳定性高）
worker_timeout = 600  # 超时秒数
subset_patients = None  # 调试用：如 ['SC4001']，设 None 处理全部
cleanup_cache = False  # 是否在 resampled 生成后清理病人级缓存（*.npy）

# 睡眠阶段映射
stage_dict = {
    'Sleep stage W': 0,
    'Sleep stage 1': 1,
    'Sleep stage 2': 2,
    'Sleep stage 3': 3,
    'Sleep stage 4': 3,
    'Sleep stage R': 4,
    'Sleep stage ?': -1,
    'W': 0, 'w': 0,
    '1': 1,
    '2': 2,
    '3': 3,
    '4': 3,
    'R': 4, 'r': 4,
}
custom_stage_dict = {"W": 0, "N1": 1, "N2": 2, "N3": 3, "R": 4}


def process_single_patient(patient_id, psg_file, annot_file):
    """处理单个病人的数据"""
    cache_x_path = os.path.join(cache_dir, f"{patient_id}_X.npy")
    cache_y_path = os.path.join(cache_dir, f"{patient_id}_y.npy")
    
    if not os.path.exists(annot_file):
        print(f"Missing annotation for {patient_id}, skipping")
        return None

    # 0: 裁剪
    raw = trim_raw(patient_id, psg_file, annot_file)
    
    # 1: 选择通道
    raw.pick_channels(['EEG Fpz-Cz'])
    
    # 2: 重采样
    if raw.info['sfreq'] != 100:
        raw.resample(100, verbose=False)
    
    # 3: 带通滤波
    raw.filter(l_freq=0.3, h_freq=35, method='iir', verbose=False)
    
    # 4: 提取事件
    events, event_id = mne.events_from_annotations(
        raw, 
        event_id=custom_stage_dict, 
        chunk_duration=30.0, 
        verbose=False
    )
    if len(events) == 0:
        print(f"No valid events for {patient_id}, skipping")
        return None
    
    print(f"Event counts for {patient_id}: {Counter(events[:, 2])}")
    
    # 5: 创建 Epochs
    epoques = mne.Epochs(
        raw, events, event_id, 
        tmin=0, tmax=30.0 - 1/raw.info['sfreq'], # 精准获得 3000 点
        baseline=None, 
        verbose=False, 
        on_missing='ignore',
        preload=True
    )
    
    if len(epoques) == 0:
        print(f"No valid epochs for {patient_id}, skipping")
        return None
    
    # 6: 提取数据
    X_epoch = epoques.get_data()  # (n_epochs, 1, 3000)
    y_epoch = epoques.events[:, 2]
    
    # 7: Z-score 归一化（每个 epoch 独立）
    for i in range(X_epoch.shape[0]):
        epoch_signal = X_epoch[i, 0, :]  # (3000,)
        mean = epoch_signal.mean()
        std = epoch_signal.std()
        X_epoch[i, 0, :] = (epoch_signal - mean) / (std + 1e-8)

    # 8: 保存缓存
    np.save(cache_x_path, X_epoch)
    np.save(cache_y_path, y_epoch)
    print(f"Processed {patient_id}: {X_epoch.shape[0]} epochs")
    gc.collect()
    return X_epoch, y_epoch

def merge_batches(data_list, batch_size=50):
    """分批合并数据"""
    merged = []
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i:i + batch_size]
        if batch:
            merged.append(np.concatenate(batch, axis=0))
    return np.concatenate(merged, axis=0) if merged else np.array([])

def process_folder(folder_path):
    """处理单个文件夹：扫描+配对+处理+合并+保存"""
    global cache_dir  # 全局变量，用于缓存路径（每个文件夹独立）
    cache_dir = os.path.join(folder_path, 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    # 1. 扫描和匹配文件
    psg_files = glob.glob(os.path.join(folder_path, '*-PSG.edf'))
    hyp_files = glob.glob(os.path.join(folder_path, '*-Hypnogram.edf'))
    
    patient_dict = {}
    for psg in psg_files:
        patient_id = os.path.basename(psg)[:6]
        patient_dict[patient_id] = {'psg': psg, 'hyp': None}
    for hyp in hyp_files:
        patient_id = os.path.basename(hyp)[:6]
        if patient_id in patient_dict:
            patient_dict[patient_id]['hyp'] = hyp
    
    valid_patients = [(pid, data['psg'], data['hyp']) for pid, data in patient_dict.items() if data['hyp']]
    if subset_patients:
        valid_patients = [p for p in valid_patients if p[0] in subset_patients]
    
    print(f"Found {len(valid_patients)} valid patients in {os.path.basename(folder_path)}")
    
    # 2. 并行处理病人
    results = joblib.Parallel(n_jobs=n_jobs, backend='loky', timeout=worker_timeout, verbose=10)(
        joblib.delayed(process_single_patient)(*pat) for pat in tqdm(valid_patients, desc=f"Processing {os.path.basename(folder_path)}")
    )
    
    # 3. 合并数据
    results = [r for r in results if r is not None]
    if not results:
        print(f"No valid results for {os.path.basename(folder_path)}, skipping")
        return
    
    X_list = [r[0] for r in results]
    y_list = [r[1] for r in results]
    X = merge_batches(X_list)
    y = merge_batches(y_list)
    print(f"Merged data shape for {os.path.basename(folder_path)}: {X.shape}, Unique labels: {np.unique(y)}")
    
    # 4. 保存
    final_X_path = os.path.join(cache_dir, 'X_original.npy')
    final_y_path = os.path.join(cache_dir, 'y_original.npy')
    np.save(final_X_path, X)
    np.save(final_y_path, y)
    print(f"Original data for {os.path.basename(folder_path)}: {X.shape}, Distribution: {Counter(y)}")
    
# --- 主函数 ---
if __name__ == "__main__":
    for folder_type, folder_path in folder_configs.items():
        print(f"\n=== Processing {folder_type} folder ===")
        process_folder(folder_path)
    
    print("\nAll folders processed. Data ready for training.")
    import os
    import shutil

    # 根目录路径
    base_path = os.path.join(os.getcwd(), 'sleep-edf', 'data')
    # 需要处理的子阶段
    stages = ['train', 'val']
    # 新文件夹的名称
    target_folder_name = 'patient_data'

    for stage in stages:
        # 构建 cache 文件夹的完整路径
        cache_dir = os.path.join(base_path, stage, 'cache')
        
        # 检查 cache 目录是否存在
        if not os.path.exists(cache_dir):
            print(f"跳过：找不到路径 {cache_dir}")
            continue
        
        # 创建目标文件夹 (如果不存在)
        target_dir = os.path.join(cache_dir, target_folder_name)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            print(f"已创建目录: {target_dir}")

        # 遍历 cache 目录下的文件
        for filename in os.listdir(cache_dir):
            # 筛选以 'SC' 开头的文件
            if filename.startswith('SC'):
                source_file = os.path.join(cache_dir, filename)
                target_file = os.path.join(target_dir, filename)
                
                # 移动文件
                shutil.move(source_file, target_file)
                print(f"已移动: {filename} -> {target_folder_name}/")

    print("整理完成！")
