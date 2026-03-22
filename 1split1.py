import glob
import json
import math
import os
import random
import shutil
from collections import defaultdict


SOURCE_FOLDER = r"./sleep-edf/sleep-cassette"
DATA_ROOT = r"./sleep-edf/data"
FOLDS_ROOT = os.path.join(DATA_ROOT, "folds")
NUM_FOLDS = 10
RANDOM_SEED = 42
VALIDATION_RATIO = 0.1


def record_id_from_path(file_path):
    return os.path.basename(file_path)[:6]


def subject_id_from_record(record_id):
    # Sleep-EDF cassette filenames such as SC4031E0 belong to subject SC403.
    return record_id[:5]


def build_record_pairs(source_folder):
    psg_files = glob.glob(os.path.join(source_folder, "*-PSG.edf"))
    hyp_files = glob.glob(os.path.join(source_folder, "*-Hypnogram.edf"))

    records = {}
    for psg_file in psg_files:
        record_id = record_id_from_path(psg_file)
        records[record_id] = {"psg": psg_file, "hyp": None}

    for hyp_file in hyp_files:
        record_id = record_id_from_path(hyp_file)
        if record_id in records:
            records[record_id]["hyp"] = hyp_file

    return {
        record_id: paths
        for record_id, paths in records.items()
        if paths["psg"] and paths["hyp"]
    }


def build_subject_groups(valid_records):
    subject_to_records = defaultdict(list)
    for record_id, paths in sorted(valid_records.items()):
        subject_id = subject_id_from_record(record_id)
        subject_to_records[subject_id].append(
            {
                "record_id": record_id,
                "psg": paths["psg"],
                "hyp": paths["hyp"],
            }
        )
    return dict(subject_to_records)


def split_subjects_into_folds(subject_ids, num_folds, random_seed):
    rng = random.Random(random_seed)
    shuffled = list(subject_ids)
    rng.shuffle(shuffled)

    folds = [[] for _ in range(num_folds)]
    for idx, subject_id in enumerate(shuffled):
        folds[idx % num_folds].append(subject_id)
    return folds


def ensure_clean_folder(folder_path):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    os.makedirs(folder_path, exist_ok=True)


def gather_records(subject_ids, subject_to_records):
    gathered = []
    for subject_id in sorted(subject_ids):
        gathered.extend(subject_to_records[subject_id])
    return gathered


def split_train_val_subjects(train_candidate_subjects, fold_idx, random_seed, validation_ratio):
    train_candidate_subjects = sorted(train_candidate_subjects)
    if len(train_candidate_subjects) < 2:
        raise ValueError("Need at least two training subjects to split train/val.")

    rng = random.Random(random_seed + fold_idx)
    shuffled = list(train_candidate_subjects)
    rng.shuffle(shuffled)

    n_val = max(1, math.ceil(len(shuffled) * validation_ratio))
    n_val = min(n_val, len(shuffled) - 1)

    val_subjects = set(shuffled[:n_val])
    train_subjects = set(shuffled[n_val:])
    return train_subjects, val_subjects


def write_manifest(fold_dir, split_name, subject_ids, records):
    manifest = {
        "subjects": sorted(subject_ids),
        "records": [record["record_id"] for record in records],
    }
    manifest_path = os.path.join(fold_dir, f"{split_name}_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def main():
    valid_records = build_record_pairs(SOURCE_FOLDER)
    subject_to_records = build_subject_groups(valid_records)
    subject_ids = sorted(subject_to_records.keys())

    if len(subject_ids) < NUM_FOLDS:
        raise ValueError(
            f"Not enough subjects ({len(subject_ids)}) for {NUM_FOLDS}-fold splitting."
        )

    ensure_clean_folder(FOLDS_ROOT)
    folds = split_subjects_into_folds(subject_ids, NUM_FOLDS, RANDOM_SEED)

    print(f"Valid records: {len(valid_records)}")
    print(f"Unique subjects: {len(subject_ids)}")
    print(f"Writing manifests only under {FOLDS_ROOT}")
    print(f"Validation split: {int(VALIDATION_RATIO * 100)}% of training subjects within each fold")

    for fold_idx in range(NUM_FOLDS):
        fold_name = f"fold_{fold_idx + 1:02d}"
        fold_dir = os.path.join(FOLDS_ROOT, fold_name)
        os.makedirs(fold_dir, exist_ok=True)

        test_subjects = set(folds[fold_idx])
        train_candidate_subjects = set(subject_ids) - test_subjects
        train_subjects, val_subjects = split_train_val_subjects(
            train_candidate_subjects=train_candidate_subjects,
            fold_idx=fold_idx,
            random_seed=RANDOM_SEED,
            validation_ratio=VALIDATION_RATIO,
        )

        split_subjects = {
            "train": train_subjects,
            "val": val_subjects,
            "test": test_subjects,
        }

        print(
            f"{fold_name}: train={len(train_subjects)} subjects, "
            f"val={len(val_subjects)} subjects, test={len(test_subjects)} subjects"
        )

        for split_name, split_subject_ids in split_subjects.items():
            records = gather_records(split_subject_ids, subject_to_records)
            write_manifest(fold_dir, split_name, split_subject_ids, records)
            print(
                f"  {split_name}: subjects={sorted(split_subject_ids)}, "
                f"records={len(records)}"
            )

    summary_path = os.path.join(FOLDS_ROOT, "cv_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "num_folds": NUM_FOLDS,
                "random_seed": RANDOM_SEED,
                "validation_ratio": VALIDATION_RATIO,
                "source_folder": SOURCE_FOLDER,
                "subjects": subject_ids,
                "folds": folds,
            },
            f,
            indent=2,
        )

    print(f"Subject-wise {NUM_FOLDS}-fold manifest split complete.")


if __name__ == "__main__":
    main()
