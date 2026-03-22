import glob
import json
import os
import re

import mne
import numpy as np


SOURCE_FOLDER = r"./sleep-edf/sleep-cassette"
OUTPUT_JSON = r"./sleep-edf/data/crop_eval_summary.json"
DEFAULT_BUFFER_SEC = 0
EPOCH_SEC = 30
MIN_SLEEP_EPOCHS = 6


def short_stage(desc):
    text = str(desc).lower().strip()
    if re.search(r"\bw\b", text) or "wake" in text or "awake" in text:
        return "W"
    if re.search(r"\br\b", text) or "rem" in text:
        return "R"
    if "stage 1" in text or text in ("1", "n1"):
        return "N1"
    if "stage 2" in text or text in ("2", "n2"):
        return "N2"
    if "stage 3" in text or "stage 4" in text or "n3" in text or "sws" in text:
        return "N3"
    return "IGNORE"


def get_robust_sleep_boundaries(starts, ends, stages, total_duration_sec):
    gap_threshold_block = 3600
    gap_threshold_edge = 1800
    min_sleep_block_duration = 3 * 3600
    min_sleep_span = 6 * 3600

    valid_sleep = (stages != "W") & (stages != "IGNORE")
    non_w_idx = np.where(valid_sleep)[0]
    if len(non_w_idx) == 0:
        return 0.0, total_duration_sec - 0.01

    blocks = []
    block_start = non_w_idx[0]
    for i in range(len(non_w_idx) - 1):
        cur_idx = non_w_idx[i]
        next_idx = non_w_idx[i + 1]
        if starts[next_idx] - ends[cur_idx] > gap_threshold_block:
            blocks.append((block_start, cur_idx))
            block_start = next_idx
    blocks.append((block_start, non_w_idx[-1]))

    longest_block = None
    longest_duration = 0.0
    for left, right in blocks:
        duration = ends[right] - starts[left]
        if duration >= min_sleep_block_duration and duration > longest_duration:
            longest_block = (left, right)
            longest_duration = duration

    if longest_block is None:
        return 0.0, total_duration_sec - 0.01

    left_ptr = np.where(non_w_idx == longest_block[0])[0][0]
    right_ptr = np.where(non_w_idx == longest_block[1])[0][0]

    part_starts = starts[non_w_idx[left_ptr : right_ptr + 1]]
    part_ends = ends[non_w_idx[left_ptr : right_ptr + 1]]
    part_duration = part_ends - part_starts
    part_center = (part_starts + part_ends) / 2

    if np.sum(part_duration) > 0:
        sleep_center = float(np.sum(part_center * part_duration) / np.sum(part_duration))
    else:
        sleep_center = float((part_starts[0] + part_ends[-1]) / 2)

    init_left = left_ptr
    init_right = right_ptr

    while left_ptr < right_ptr:
        current_span = ends[non_w_idx[right_ptr]] - starts[non_w_idx[left_ptr]]
        if current_span <= min_sleep_span and (right_ptr - left_ptr <= 1):
            break

        changed = False

        if left_ptr + 1 <= right_ptr:
            cur_idx = non_w_idx[left_ptr]
            next_idx = non_w_idx[left_ptr + 1]
            if starts[next_idx] - ends[cur_idx] > gap_threshold_edge:
                if starts[next_idx] < sleep_center or left_ptr == init_left:
                    left_ptr += 1
                    changed = True

        if right_ptr - 1 >= left_ptr:
            cur_idx = non_w_idx[right_ptr]
            prev_idx = non_w_idx[right_ptr - 1]
            if starts[cur_idx] - ends[prev_idx] > gap_threshold_edge:
                if ends[prev_idx] > sleep_center or right_ptr == init_right:
                    right_ptr -= 1
                    changed = True

        if not changed:
            break

    onset = max(0.0, float(starts[non_w_idx[left_ptr]]) - DEFAULT_BUFFER_SEC)
    offset = min(total_duration_sec - 0.01, float(ends[non_w_idx[right_ptr]]) + DEFAULT_BUFFER_SEC)
    return onset, offset


def get_record_pairs(folder):
    pairs = {}

    for psg_file in glob.glob(os.path.join(folder, "*-PSG.edf")):
        record_id = os.path.basename(psg_file)[:6]
        pairs.setdefault(record_id, {})["psg"] = psg_file

    for hyp_file in glob.glob(os.path.join(folder, "*-Hypnogram.edf")):
        record_id = os.path.basename(hyp_file)[:6]
        pairs.setdefault(record_id, {})["hyp"] = hyp_file

    result = []
    for record_id in sorted(pairs.keys()):
        if "psg" in pairs[record_id] and "hyp" in pairs[record_id]:
            result.append((record_id, pairs[record_id]["psg"], pairs[record_id]["hyp"]))
    return result


def load_annotations(psg_file, hyp_file):
    raw = mne.io.read_raw_edf(psg_file, preload=False, verbose=False)
    total_duration_sec = raw.n_times / raw.info["sfreq"]

    annot = mne.read_annotations(hyp_file)
    starts = np.asarray(annot.onset, dtype=float)
    durations = np.asarray(annot.duration, dtype=float)
    durations = np.where(
        starts + durations > total_duration_sec,
        np.maximum(0.0, total_duration_sec - starts - 0.01),
        durations,
    )
    ends = starts + durations
    stages = np.asarray([short_stage(desc) for desc in annot.description], dtype=object)

    valid = (starts < total_duration_sec) & (ends > starts + 1.0)
    return total_duration_sec, starts[valid], ends[valid], stages[valid]


def get_ground_truth_boundaries(starts, ends, stages, total_duration_sec):
    n_epochs = int(total_duration_sec // EPOCH_SEC)
    labels = ["IGNORE"] * n_epochs

    for start, end, stage in zip(starts, ends, stages):
        if stage == "IGNORE":
            continue
        start_idx = max(0, int(np.floor(start / EPOCH_SEC)))
        end_idx = min(n_epochs, int(np.ceil(end / EPOCH_SEC)))
        for i in range(start_idx, end_idx):
            labels[i] = stage

    sleep_mask = np.array([label in {"N1", "N2", "N3", "R"} for label in labels], dtype=bool)
    runs = []
    run_start = None

    for i, value in enumerate(sleep_mask):
        if value and run_start is None:
            run_start = i
        elif not value and run_start is not None:
            runs.append((run_start, i))
            run_start = None

    if run_start is not None:
        runs.append((run_start, len(sleep_mask)))

    runs = [(start, end) for start, end in runs if end - start >= MIN_SLEEP_EPOCHS]
    if not runs:
        return None

    onset = runs[0][0] * EPOCH_SEC
    offset = runs[-1][1] * EPOCH_SEC
    return onset, offset


def calc_iou(a_start, a_end, b_start, b_end):
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union

if __name__ == "__main__":
    pairs = get_record_pairs(SOURCE_FOLDER)
    if not pairs:
        raise SystemExit(f"no paired EDF files found in {SOURCE_FOLDER}")

    records = []
    onset_errors = []
    offset_errors = []
    duration_errors = []
    ious = []

    for record_id, psg_file, hyp_file in pairs:
        total_duration_sec, starts, ends, stages = load_annotations(psg_file, hyp_file)
        gt = get_ground_truth_boundaries(starts, ends, stages, total_duration_sec)
        if gt is None:
            continue

        pred_onset, pred_offset = get_robust_sleep_boundaries(starts, ends, stages, total_duration_sec)
        gt_onset, gt_offset = gt

        onset_error = abs(pred_onset - gt_onset) / 60.0
        offset_error = abs(pred_offset - gt_offset) / 60.0
        duration_error = abs((pred_offset - pred_onset) - (gt_offset - gt_onset)) / 60.0
        iou = calc_iou(pred_onset, pred_offset, gt_onset, gt_offset)

        onset_errors.append(onset_error)
        offset_errors.append(offset_error)
        duration_errors.append(duration_error)
        ious.append(iou)

        records.append(
            {
                "record_id": record_id,
                "gt_onset_min": round(gt_onset / 60.0, 2),
                "gt_offset_min": round(gt_offset / 60.0, 2),
                "pred_onset_min": round(pred_onset / 60.0, 2),
                "pred_offset_min": round(pred_offset / 60.0, 2),
                "onset_error_min": round(onset_error, 2),
                "offset_error_min": round(offset_error, 2),
                "duration_error_min": round(duration_error, 2),
                "iou": round(iou, 4),
            }
        )

    summary = {
        "record_count": len(records),
        "DEFAULT_BUFFER_SEC": DEFAULT_BUFFER_SEC,
        "mean_iou": round(float(np.mean(ious)), 6),
        "onset_within_15min_ratio": round(float(np.mean(np.array(onset_errors) <= 15)), 6),
        "offset_within_15min_ratio": round(float(np.mean(np.array(offset_errors) <= 15)), 6),
        "onset_within_30min_ratio": round(float(np.mean(np.array(onset_errors) <= 30)), 6),
        "offset_within_30min_ratio": round(float(np.mean(np.array(offset_errors) <= 30)), 6),
        "records": records,
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps({k: v for k, v in summary.items() if k != "records"}, ensure_ascii=False, indent=2))
    print(f"saved to: {os.path.abspath(OUTPUT_JSON)}")

