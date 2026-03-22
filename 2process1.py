import gc
import glob
import json
import os
import warnings
from collections import Counter

import joblib
import mne
import numpy as np
from tqdm import tqdm


warnings.filterwarnings("ignore", category=RuntimeWarning)
mne.set_log_level("WARNING")


SOURCE_FOLDER = r"./sleep-edf/sleep-cassette"
DATA_ROOT = r"./sleep-edf/data"
OUTPUT_CACHE_ROOT = os.path.join(DATA_ROOT, "global_cache1")
PATIENT_CACHE_DIR = os.path.join(OUTPUT_CACHE_ROOT, "patient_data")
SELECT_CH = "EEG Fpz-Cz"
EPOCH_DURATION_SEC = 30
W_EDGE_MINS = 30
PAPER_SLEEP_EDF_TOTAL_EPOCHS = 199352
SIGNAL_UNIT = "uV"
MNE_UNIT_SYNC_MODE = "try_get_data_units_then_scale"

n_jobs = 1
worker_timeout = 600
subset_records = None
overwrite_cache = os.environ.get("OVERWRITE_CACHE", "0") == "1"

STAGE_W = 0
STAGE_N1 = 1
STAGE_N2 = 2
STAGE_N3 = 3
STAGE_REM = 4
STAGE_MOVE = 5
STAGE_UNK = 6

CLASS_ID_TO_NAME = {
    STAGE_W: "W",
    STAGE_N1: "N1",
    STAGE_N2: "N2",
    STAGE_N3: "N3",
    STAGE_REM: "REM",
    STAGE_MOVE: "MOVE",
    STAGE_UNK: "UNK",
}

ANN2LABEL = {
    "Sleep stage W": STAGE_W,
    "Sleep stage 1": STAGE_N1,
    "Sleep stage 2": STAGE_N2,
    "Sleep stage 3": STAGE_N3,
    "Sleep stage 4": STAGE_N3,
    "Sleep stage R": STAGE_REM,
    "Sleep stage ?": STAGE_UNK,
    "Movement time": STAGE_MOVE,
}


def build_source_record_index(source_folder):
    psg_files = glob.glob(os.path.join(source_folder, "*-PSG.edf"))
    hyp_files = glob.glob(os.path.join(source_folder, "*-Hypnogram.edf"))

    record_index = {}
    for psg_file in psg_files:
        record_id = os.path.basename(psg_file)[:6]
        record_index[record_id] = {"psg": psg_file, "hyp": None}

    for hyp_file in hyp_files:
        record_id = os.path.basename(hyp_file)[:6]
        if record_id in record_index:
            record_index[record_id]["hyp"] = hyp_file

    return {
        record_id: paths
        for record_id, paths in record_index.items()
        if paths["psg"] and paths["hyp"]
    }


def annotation_to_label(desc):
    if desc in ANN2LABEL:
        return ANN2LABEL[desc]

    desc_norm = str(desc).strip().lower()
    if desc_norm in {"sleep stage w", "w"}:
        return STAGE_W
    if desc_norm in {"sleep stage 1", "1", "n1"}:
        return STAGE_N1
    if desc_norm in {"sleep stage 2", "2", "n2"}:
        return STAGE_N2
    if desc_norm in {"sleep stage 3", "sleep stage 4", "3", "4", "n3"}:
        return STAGE_N3
    if desc_norm in {"sleep stage r", "r", "rem"}:
        return STAGE_REM
    if "movement" in desc_norm:
        return STAGE_MOVE
    if "?" in desc_norm or "unknown" in desc_norm or "undefined" in desc_norm:
        return STAGE_UNK
    raise ValueError(f"Unsupported annotation label: {desc}")


def read_channel_signal_with_mne_sync(raw, record_id):
    try:
        signal = raw.get_data(units=SIGNAL_UNIT)[0]
        return signal.astype(np.float32), SIGNAL_UNIT
    except TypeError:
        signal = raw.get_data()[0]
    except ValueError:
        signal = raw.get_data()[0]

    original_unit = raw._orig_units.get(SELECT_CH, "") if hasattr(raw, "_orig_units") else ""
    if str(original_unit).strip().lower() == "uv":
        return signal.astype(np.float32), SIGNAL_UNIT

    # MNE often returns EEG in volts. TinySleepNet's original pipeline uses pyedflib,
    # so we rescale to microvolts here to keep the raw-input magnitude closer.
    return (signal * 1e6).astype(np.float32), SIGNAL_UNIT


def read_record_epochs(record_id, psg_file, annot_file):
    raw = mne.io.read_raw_edf(psg_file, preload=True, verbose=False)
    if SELECT_CH not in raw.ch_names:
        raise ValueError(f"{record_id}: channel {SELECT_CH} not found.")
    raw.pick_channels([SELECT_CH])

    sfreq = float(raw.info["sfreq"])
    if not np.isclose(sfreq, 100.0, atol=1e-3):
        raise ValueError(f"{record_id}: expected {SELECT_CH} at 100 Hz, got {sfreq} Hz.")
    epoch_samples = int(round(EPOCH_DURATION_SEC * sfreq))
    signal, signal_unit = read_channel_signal_with_mne_sync(raw, record_id)
    file_duration_sec = signal.shape[0] / sfreq

    ann = mne.read_annotations(annot_file)
    x_epochs = []
    y_epochs = []
    total_duration = 0.0

    for onset_sec, duration_sec, desc in zip(ann.onset, ann.duration, ann.description):
        onset_sec = float(onset_sec)
        duration_sec = float(duration_sec)
        if abs(onset_sec - total_duration) > 1.0:
            raise ValueError(
                f"{record_id}: annotation onset mismatch, got {onset_sec}, expected about {total_duration}."
            )

        label = annotation_to_label(desc)
        duration_epoch = int(round(duration_sec / EPOCH_DURATION_SEC))
        if not np.isclose(duration_epoch * EPOCH_DURATION_SEC, duration_sec, atol=1.0):
            raise ValueError(
                f"{record_id}: unexpected annotation duration {duration_sec} for epoch size {EPOCH_DURATION_SEC}."
            )

        for epoch_idx in range(duration_epoch):
            start_sec = onset_sec + epoch_idx * EPOCH_DURATION_SEC
            start_sample = int(round(start_sec * sfreq))
            stop_sample = start_sample + epoch_samples
            if stop_sample > len(signal):
                break
            epoch_signal = signal[start_sample:stop_sample]
            if len(epoch_signal) != epoch_samples:
                continue
            x_epochs.append(epoch_signal[np.newaxis, :].astype(np.float32))
            y_epochs.append(label)

        total_duration += duration_sec

    if not x_epochs:
        return None

    x = np.stack(x_epochs, axis=0)
    y = np.asarray(y_epochs, dtype=np.int64)

    if len(x) != len(y):
        raise ValueError(f"{record_id}: shape mismatch x={x.shape}, y={y.shape}")

    meta = {
        "sampling_rate": sfreq,
        "epoch_duration_sec": EPOCH_DURATION_SEC,
        "file_duration_sec": file_duration_sec,
        "n_all_epochs": int(len(y)),
        "signal_unit": signal_unit,
        "mne_unit_sync_mode": MNE_UNIT_SYNC_MODE,
    }
    return x, y, meta


def select_sleep_periods_tinysleepnet(x, y):
    non_w_indices = np.where(y != STAGE_W)[0]
    if len(non_w_indices) == 0:
        return None

    edge_epochs = W_EDGE_MINS * 2
    start_idx = max(0, int(non_w_indices[0] - edge_epochs))
    end_idx = min(len(y) - 1, int(non_w_indices[-1] + edge_epochs))

    x = x[start_idx : end_idx + 1]
    y = y[start_idx : end_idx + 1]

    valid_mask = (y != STAGE_MOVE) & (y != STAGE_UNK)
    x = x[valid_mask]
    y = y[valid_mask]
    return x, y


def process_single_record(record_id, psg_file, annot_file):
    cache_x_path = os.path.join(PATIENT_CACHE_DIR, f"{record_id}_X.npy")
    cache_y_path = os.path.join(PATIENT_CACHE_DIR, f"{record_id}_y.npy")

    if (
        not overwrite_cache
        and os.path.exists(cache_x_path)
        and os.path.exists(cache_y_path)
    ):
        cached_y = np.load(cache_y_path)
        return {
            "record_id": record_id,
            "n_epochs": int(len(cached_y)),
            "stage_counter": dict(Counter(cached_y.tolist())),
            "source": "cache",
        }

    record_payload = read_record_epochs(record_id, psg_file, annot_file)
    if record_payload is None:
        print(f"{record_id}: no valid epochs, skipping")
        return None

    x, y, meta = record_payload
    selected = select_sleep_periods_tinysleepnet(x, y)
    if selected is None:
        print(f"{record_id}: no non-wake epochs after selection, skipping")
        return None

    x_selected, y_selected = selected
    np.save(cache_x_path, x_selected)
    np.save(cache_y_path, y_selected)

    stage_counter = Counter(y_selected.tolist())
    stage_counter_named = {
        CLASS_ID_TO_NAME[int(label)]: int(count)
        for label, count in sorted(stage_counter.items())
    }

    print(
        f"{record_id}: fs={meta['sampling_rate']:.1f}Hz, "
        f"all={meta['n_all_epochs']} epochs -> kept={len(y_selected)} epochs, "
        f"dist={stage_counter_named}"
    )
    gc.collect()
    return {
        "record_id": record_id,
        "n_epochs": int(len(y_selected)),
        "stage_counter": {str(int(k)): int(v) for k, v in stage_counter.items()},
        "sampling_rate": float(meta["sampling_rate"]),
        "n_all_epochs": int(meta["n_all_epochs"]),
        "source": "processed",
    }


def save_cache_manifest(processed_records):
    total_counter = Counter()
    total_epochs = 0
    record_summaries = []

    for item in processed_records:
        total_epochs += int(item["n_epochs"])
        total_counter.update({int(k): int(v) for k, v in item["stage_counter"].items()})
        record_summaries.append(
            {
                "record_id": item["record_id"],
                "n_epochs": int(item["n_epochs"]),
                "n_all_epochs": int(item.get("n_all_epochs", item["n_epochs"])),
                "sampling_rate": float(item.get("sampling_rate", 100.0)),
                "source": item.get("source", "processed"),
            }
        )

    manifest = {
        "source_folder": SOURCE_FOLDER,
        "patient_cache_dir": PATIENT_CACHE_DIR,
        "records": sorted(item["record_id"] for item in processed_records),
        "record_summaries": sorted(record_summaries, key=lambda item: item["record_id"]),
        "selection_protocol": {
            "paper": "TinySleepNet EMBC 2020",
            "channel": SELECT_CH,
            "epoch_duration_sec": EPOCH_DURATION_SEC,
            "wake_edge_minutes": W_EDGE_MINS,
            "remove_labels": ["MOVE", "UNK"],
            "filtering": "none",
            "normalization": "none",
            "signal_unit": SIGNAL_UNIT,
            "mne_unit_sync_mode": MNE_UNIT_SYNC_MODE,
        },
        "global_stage_counter": {
            CLASS_ID_TO_NAME[int(label)]: int(count)
            for label, count in sorted(total_counter.items())
            if int(label) in CLASS_ID_TO_NAME
        },
        "total_epochs": int(total_epochs),
        "paper_reference_total_epochs": PAPER_SLEEP_EDF_TOTAL_EPOCHS,
        "paper_total_gap": int(total_epochs - PAPER_SLEEP_EDF_TOTAL_EPOCHS),
    }
    manifest_path = os.path.join(OUTPUT_CACHE_ROOT, "cache_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)
    print(f"Saved cache manifest to {manifest_path}")


if __name__ == "__main__":
    os.makedirs(PATIENT_CACHE_DIR, exist_ok=True)

    source_record_index = build_source_record_index(SOURCE_FOLDER)
    record_items = sorted(source_record_index.items())
    if subset_records:
        record_items = [item for item in record_items if item[0] in subset_records]

    print(f"Found {len(record_items)} valid source records in {SOURCE_FOLDER}")
    print(f"TinySleepNet-style cache directory: {PATIENT_CACHE_DIR}")
    print(f"overwrite_cache={overwrite_cache}")
    print(
        f"Protocol: keep {W_EDGE_MINS} min Wake before/after sleep, "
        f"remove MOVE/UNK, no filtering, no normalization, "
        f"MNE signal synced to {SIGNAL_UNIT}"
    )

    results = joblib.Parallel(n_jobs=n_jobs, backend="loky", timeout=worker_timeout, verbose=10)(
        joblib.delayed(process_single_record)(record_id, paths["psg"], paths["hyp"])
        for record_id, paths in tqdm(record_items, desc="Processing TinySleepNet cache")
    )

    processed_records = [item for item in results if item is not None]
    save_cache_manifest(processed_records)
    total_epochs = sum(item["n_epochs"] for item in processed_records)
    print(f"\nTinySleepNet-style cache ready: {len(processed_records)} records processed.")
    print(
        f"Total kept epochs={total_epochs} | "
        f"paper reference={PAPER_SLEEP_EDF_TOTAL_EPOCHS} | "
        f"gap={total_epochs - PAPER_SLEEP_EDF_TOTAL_EPOCHS}"
    )
