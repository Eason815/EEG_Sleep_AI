from abc import ABC, abstractmethod

import mne
import numpy as np
import torch
from collections import Counter


class BaseSleepPredictor(ABC):
    @abstractmethod
    def load_model(self):
        pass

    @abstractmethod
    def preprocess(self, edf_path: str) -> np.ndarray:
        pass

    @abstractmethod
    def predict(self, epochs: np.ndarray) -> dict:
        pass


def map_5to4(label):
    if label == 0:
        return 0
    if label == 4:
        return 1
    if label in (1, 2):
        return 2
    if label == 3:
        return 3
    return label


def build_stage_stats(hypnogram):
    total = len(hypnogram)
    if total == 0:
        return {
            "W_ratio": 0.0,
            "REM_ratio": 0.0,
            "Light_ratio": 0.0,
            "Deep_ratio": 0.0,
        }

    return {
        "W_ratio": hypnogram.count(0) / total,
        "REM_ratio": hypnogram.count(1) / total,
        "Light_ratio": hypnogram.count(2) / total,
        "Deep_ratio": hypnogram.count(3) / total,
    }


class BaseTorchSleepPredictor(BaseSleepPredictor):
    def __init__(self, model_path, model_class, device="cuda"):
        self.model_path = model_path
        self.model_class = model_class
        self.device = device if device == "cuda" and torch.cuda.is_available() else "cpu"
        self.model = None
        self.recording_start_time = None

    @abstractmethod
    def get_model_init_kwargs(self):
        pass

    def load_model(self):
        print(f"[加载模型] 路径: {self.model_path}")
        self.model = self.model_class(**self.get_model_init_kwargs()).to(self.device)

        state_dict = torch.load(self.model_path, map_location=self.device)
        if isinstance(state_dict, dict):
            if "state_dict" in state_dict and isinstance(state_dict["state_dict"], dict):
                state_dict = state_dict["state_dict"]
            elif "model_state_dict" in state_dict and isinstance(state_dict["model_state_dict"], dict):
                state_dict = state_dict["model_state_dict"]

        self.model.load_state_dict(state_dict)
        self.model.eval()

        total_params = sum(p.numel() for p in self.model.parameters())
        print(f"[加载模型] 成功加载，参数量: {total_params:,}")

    def _load_single_channel_raw(self, edf_path):
        raw = mne.io.read_raw_edf(edf_path, preload=False, verbose=False)

        if raw.info["meas_date"] is not None:
            self.recording_start_time = raw.info["meas_date"].isoformat()
        else:
            self.recording_start_time = None

        if "EEG Fpz-Cz" in raw.ch_names:
            selected_channels = ["EEG Fpz-Cz"]
        else:
            eeg_channel_names = [
                ch_name
                for ch_name, ch_type in zip(raw.ch_names, raw.get_channel_types())
                if ch_type == "eeg"
            ]
            if not eeg_channel_names:
                raise ValueError("EDF 文件中未找到可用的 EEG 通道")
            selected_channels = [eeg_channel_names[0]]

        raw.pick(selected_channels)
        raw.load_data()
        return raw

    def _get_data_in_microvolts(self, raw):
        try:
            return raw.get_data(units="uV")[0].astype(np.float32)
        except Exception:
            data = raw.get_data()[0].astype(np.float32)
            original_unit = raw._orig_units.get(raw.ch_names[0], "") if hasattr(raw, "_orig_units") else ""
            if str(original_unit).strip().lower() != "uv":
                data = data * 1e6
            return data

    def preprocess(self, edf_path):
        raw = self._load_single_channel_raw(edf_path)

        if raw.info["sfreq"] != 100:
            raw.resample(100, verbose=False)

        raw.filter(l_freq=0.3, h_freq=35, method="iir", verbose=False)

        data = raw.get_data()[0]
        epoch_len = 3000
        n_epochs = len(data) // epoch_len

        epochs = []
        for i in range(n_epochs):
            epoch = data[i * epoch_len : (i + 1) * epoch_len]
            mean, std = epoch.mean(), epoch.std()
            epoch = (epoch - mean) / (std + 1e-8)
            epochs.append(epoch)

        return np.array(epochs, dtype=np.float32).reshape(n_epochs, 1, 3000)

    def get_robust_sleep_boundaries(self, starts, ends, stages, total_duration_sec):
        gap_threshold_for_block_separation = 1 * 3600
        gap_threshold_for_edge_cleaning = 1800
        min_sleep_block_duration = 3 * 3600
        min_sleep_limit_for_robustness = 6 * 3600
        buffer_sec = 1200

        valid_sleep_stage_mask = (stages != "W") & (stages != "IGNORE")
        non_w_original_indices = np.where(valid_sleep_stage_mask)[0]

        if len(non_w_original_indices) == 0:
            print("⚠️ 未找到任何有效的睡眠阶段")
            return 0.0, total_duration_sec - 0.01

        sleep_blocks = []
        current_block_start_idx = non_w_original_indices[0]

        for i in range(len(non_w_original_indices) - 1):
            idx_current = non_w_original_indices[i]
            idx_next = non_w_original_indices[i + 1]
            gap = starts[idx_next] - ends[idx_current]

            if gap > gap_threshold_for_block_separation:
                sleep_blocks.append((current_block_start_idx, idx_current))
                current_block_start_idx = idx_next

        sleep_blocks.append((current_block_start_idx, non_w_original_indices[-1]))
        print(f"📳 识别出 {len(sleep_blocks)} 个潜在睡眠块")

        longest_block = None
        max_block_duration = 0

        for block_start_orig_idx, block_end_orig_idx in sleep_blocks:
            block_duration = ends[block_end_orig_idx] - starts[block_start_orig_idx]
            if block_duration > max_block_duration and block_duration >= min_sleep_block_duration:
                max_block_duration = block_duration
                longest_block = (block_start_orig_idx, block_end_orig_idx)

        if longest_block is None:
            print(f"⚠️ 未找到持续 {min_sleep_block_duration/3600:.1f}h 以上的睡眠块")
            return 0.0, total_duration_sec - 0.01

        left_ptr_idx = np.where(non_w_original_indices == longest_block[0])[0][0]
        right_ptr_idx = np.where(non_w_original_indices == longest_block[1])[0][0]

        block_starts = starts[non_w_original_indices[left_ptr_idx : right_ptr_idx + 1]]
        block_ends = ends[non_w_original_indices[left_ptr_idx : right_ptr_idx + 1]]
        weighted_midpoints = (block_starts + block_ends) / 2
        weighted_durations = block_ends - block_starts

        if np.sum(weighted_durations) > 0:
            sleep_center_time = np.sum(weighted_midpoints * weighted_durations) / np.sum(weighted_durations)
        else:
            sleep_center_time = (block_starts[0] + block_ends[-1]) / 2

        while left_ptr_idx < right_ptr_idx:
            current_onset = starts[non_w_original_indices[left_ptr_idx]]
            current_offset = ends[non_w_original_indices[right_ptr_idx]]
            current_span = current_offset - current_onset

            if current_span <= min_sleep_limit_for_robustness and (right_ptr_idx - left_ptr_idx <= 1):
                break

            changed = False

            if left_ptr_idx + 1 <= right_ptr_idx:
                idx_curr = non_w_original_indices[left_ptr_idx]
                idx_next = non_w_original_indices[left_ptr_idx + 1]
                gap = starts[idx_next] - ends[idx_curr]

                if gap > gap_threshold_for_edge_cleaning and starts[idx_next] < sleep_center_time:
                    left_ptr_idx += 1
                    changed = True

            if right_ptr_idx - 1 >= left_ptr_idx:
                idx_curr = non_w_original_indices[right_ptr_idx]
                idx_prev = non_w_original_indices[right_ptr_idx - 1]
                gap = starts[idx_curr] - ends[idx_prev]

                if gap > gap_threshold_for_edge_cleaning and ends[idx_prev] > sleep_center_time:
                    right_ptr_idx -= 1
                    changed = True

            if not changed:
                break

        final_onset = max(0.0, float(starts[non_w_original_indices[left_ptr_idx]]) - buffer_sec)
        final_offset = min(total_duration_sec - 0.01, float(ends[non_w_original_indices[right_ptr_idx]]) + buffer_sec)

        print(
            f"✅ 主睡眠区间: {final_onset/3600:.2f}h - {final_offset/3600:.2f}h "
            f"(总时长 {(final_offset-final_onset)/3600:.2f}h)"
        )
        return final_onset, final_offset


class ContextWindowPredictor(BaseTorchSleepPredictor):
    def __init__(self, model_path, model_class, device="cuda", window_size=15, preprocess_mode="legacy_filtered_zscore"):
        super().__init__(model_path=model_path, model_class=model_class, device=device)
        self.window_size = window_size
        self.preprocess_mode = preprocess_mode

    def get_model_init_kwargs(self):
        return {"num_classes": 5, "window_size": self.window_size}

    def preprocess(self, edf_path):
        raw = self._load_single_channel_raw(edf_path)

        if raw.info["sfreq"] != 100:
            raw.resample(100, verbose=False)

        if self.preprocess_mode == "raw_microvolt":
            data = self._get_data_in_microvolts(raw)
            epoch_len = 3000
            n_epochs = len(data) // epoch_len
            if n_epochs == 0:
                return np.zeros((0, 1, epoch_len), dtype=np.float32)
            trimmed = data[: n_epochs * epoch_len]
            return trimmed.reshape(n_epochs, 1, epoch_len)

        raw.filter(l_freq=0.3, h_freq=35, method="iir", verbose=False)
        data = raw.get_data()[0]
        epoch_len = 3000
        n_epochs = len(data) // epoch_len

        epochs = []
        for i in range(n_epochs):
            epoch = data[i * epoch_len : (i + 1) * epoch_len]
            mean, std = epoch.mean(), epoch.std()
            epoch = (epoch - mean) / (std + 1e-8)
            epochs.append(epoch)

        return np.array(epochs, dtype=np.float32).reshape(n_epochs, 1, epoch_len)

    def predict(self, epochs):
        half_window = self.window_size // 2
        results = []

        with torch.no_grad():
            for i in range(len(epochs)):
                start = max(0, i - half_window)
                end = min(len(epochs), i + half_window + 1)
                window = epochs[start:end]

                if len(window) < self.window_size:
                    pad_left = max(0, half_window - i)
                    pad_right = max(0, (i + half_window + 1) - len(epochs))
                    window = np.pad(window, ((pad_left, pad_right), (0, 0), (0, 0)), mode="edge")

                x = torch.from_numpy(window).unsqueeze(0).float().to(self.device)
                output = self.model(x)
                pred = output.argmax(1).item()
                results.append(pred)

        results_4cls = [map_5to4(r) for r in results]
        print(f"[Predict] class distribution={dict(Counter(results_4cls))}")
        return {"hypnogram": results_4cls, "stats": build_stage_stats(results_4cls)}


class TinySleepNetPredictor(BaseTorchSleepPredictor):
    def __init__(self, model_path, model_class, device="cuda", seq_length=20):
        super().__init__(model_path=model_path, model_class=model_class, device=device)
        self.seq_length = seq_length

    def get_model_init_kwargs(self):
        return {"num_classes": 5}

    def preprocess(self, edf_path):
        raw = self._load_single_channel_raw(edf_path)

        if raw.info["sfreq"] != 100:
            raw.resample(100, verbose=False)

        data = self._get_data_in_microvolts(raw)

        epoch_len = 3000
        n_epochs = len(data) // epoch_len
        if n_epochs == 0:
            return np.zeros((0, 1, epoch_len), dtype=np.float32)

        trimmed = data[: n_epochs * epoch_len].astype(np.float32)
        return trimmed.reshape(n_epochs, 1, epoch_len)

    def predict(self, epochs):
        signal_len = epochs.shape[-1] if len(epochs) else 3000
        results = []

        with torch.no_grad():
            for start in range(0, len(epochs), self.seq_length):
                chunk = epochs[start : start + self.seq_length]
                valid_len = len(chunk)
                if valid_len == 0:
                    continue

                padded_chunk = np.zeros((self.seq_length, 1, signal_len), dtype=np.float32)
                padded_chunk[:valid_len] = chunk

                x = torch.from_numpy(padded_chunk).unsqueeze(0).float().to(self.device)
                output = self.model(x)[0, :valid_len]
                preds = output.argmax(dim=1).cpu().tolist()
                results.extend(preds)

        results_4cls = [map_5to4(r) for r in results]
        print(f"[Predict] class distribution={dict(Counter(results_4cls))}")
        return {"hypnogram": results_4cls, "stats": build_stage_stats(results_4cls)}
