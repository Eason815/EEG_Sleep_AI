import importlib.util
import json
import os
import random
from collections import Counter
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm


device = "cuda" if torch.cuda.is_available() else "cpu"
data_dir = os.path.join(os.getcwd(), "sleep-edf", "data")
folds_root = os.path.join(data_dir, "folds")
global_cache_dir = os.path.join(data_dir, "global_cache1", "patient_data")
RUN_MODE = os.environ.get("RUN_MODE", "dev")
SELECTED_FOLDS_OVERRIDE = os.environ.get("SELECTED_FOLDS")
CLASS_NAMES = ["W", "N1", "N2", "N3", "REM"]


CONFIGS = {
    "dev": {
        "experiment_name": "sleep_stage_net_v8_paper_protocol",
        "model_name": "sleep_stage_net_v8",
        "batch_size": 8,
        "window_size": 15,
        "lr": 2e-3,
        "weights_decay": 5e-4,
        "num_epochs": 20,
        "num_classes": 5,
        "early_stop_patience": 7,
        "random_seed": 42,
        "selected_folds": ["fold_02"],
        "label_smoothing": 0.1,
        "noise_augment_prob": 0.2,
        "noise_std": 0.003,
        "class_weight_multipliers": {"W": 1.0, "N1": 1.0, "N2": 1.0, "N3": 1.2, "REM": 1.15},
    },
    "full": {
        "experiment_name": "sleep_stage_net_v8_paper_protocol",
        "model_name": "sleep_stage_net_v8",
        "batch_size": 32,
        "window_size": 15,
        "lr": 2e-3,
        "weights_decay": 5e-4,
        "num_epochs": 20,
        "num_classes": 5,
        "early_stop_patience": 7,
        "random_seed": 42,
        "selected_folds": None,
        "label_smoothing": 0.1,
        "noise_augment_prob": 0.2,
        "noise_std": 0.003,
        "class_weight_multipliers": {"W": 1.0, "N1": 1.0, "N2": 1.0, "N3": 1.2, "REM": 1.15},
    },
}


if RUN_MODE not in CONFIGS:
    raise ValueError(f"Unsupported RUN_MODE: {RUN_MODE}")


def parse_selected_folds(default_value):
    if not SELECTED_FOLDS_OVERRIDE:
        return default_value
    folds = [item.strip() for item in SELECTED_FOLDS_OVERRIDE.split(",") if item.strip()]
    return folds or default_value


active_config = CONFIGS[RUN_MODE]
batch_size = active_config["batch_size"]
window_size = active_config["window_size"]
lr = active_config["lr"]
weights_decay = active_config["weights_decay"]
num_epochs = active_config["num_epochs"]
num_classes = active_config["num_classes"]
early_stop_patience = active_config["early_stop_patience"]
random_seed = active_config["random_seed"]
selected_folds = parse_selected_folds(active_config["selected_folds"])
experiment_name = active_config["experiment_name"]
model_name = active_config["model_name"]
label_smoothing = active_config["label_smoothing"]
noise_augment_prob = active_config["noise_augment_prob"]
noise_std = active_config["noise_std"]
class_weight_multipliers = active_config["class_weight_multipliers"]

model_root = os.path.join(data_dir, "model", model_name)
model_dir = os.path.join(model_root, RUN_MODE)
os.makedirs(model_dir, exist_ok=True)
best_models_registry_path = os.path.join(model_root, "best_models.json")
run_timestamp = datetime.now().strftime("%m%d_%H%M")


def load_sleep_stage_net_v8():
    model_path = os.path.join(os.getcwd(), "3mymodel.py")
    spec = importlib.util.spec_from_file_location("sleep_stage_net_v8_module", model_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load model module from {model_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "SleepStageNetV8"):
        raise AttributeError("3mymodel.py does not define SleepStageNetV8")
    return module.SleepStageNetV8


SleepStageNetV8 = load_sleep_stage_net_v8()


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


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


def load_split_record_ids(fold_dir, split_name):
    manifest_path = os.path.join(fold_dir, f"{split_name}_manifest.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as file:
        manifest = json.load(file)
    return manifest["records"]


def load_patient_data_to_dict(cache_root, record_ids):
    patients = {}
    if not os.path.isdir(cache_root):
        raise FileNotFoundError(f"Cache folder not found: {cache_root}")

    for record_id in tqdm(record_ids, desc=f"Loading {len(record_ids)} records"):
        x_path = os.path.join(cache_root, f"{record_id}_X.npy")
        y_path = os.path.join(cache_root, f"{record_id}_y.npy")
        if not os.path.exists(x_path) or not os.path.exists(y_path):
            raise FileNotFoundError(
                f"Missing cached record {record_id}. Run 2process1.py to build the paper cache first."
            )

        x = np.load(x_path).astype(np.float32)
        y = np.load(y_path).astype(np.int64)
        valid = y != -1
        patients[record_id] = {"x": x[valid], "y": y[valid]}

    return patients


class SleepContextDataset(Dataset):
    def __init__(self, patient_dict, window_size, augment=False, noise_augment_prob=0.0, noise_std=0.0):
        self.window_size = window_size
        self.half_window = window_size // 2
        self.augment = augment
        self.noise_augment_prob = noise_augment_prob
        self.noise_std = noise_std
        self.patient_dict = patient_dict
        self.samples = []

        for patient_id, data in patient_dict.items():
            n_epochs = len(data["y"])
            for center_idx in range(self.half_window, n_epochs - self.half_window):
                self.samples.append((patient_id, center_idx))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        patient_id, center_idx = self.samples[index]
        start = center_idx - self.half_window
        stop = center_idx + self.half_window + 1

        x = self.patient_dict[patient_id]["x"][start:stop]
        y = self.patient_dict[patient_id]["y"][center_idx]

        x = torch.from_numpy(x).float()
        y = torch.tensor(y, dtype=torch.long)

        if self.augment and torch.rand(1).item() < self.noise_augment_prob:
            x = x + torch.randn_like(x) * self.noise_std

        return x, y


def evaluate(model, loader):
    model.eval()
    all_preds_5, all_labels_5 = [], []

    with torch.no_grad():
        for x, y in loader:
            logits = model(x.to(device))
            preds = logits.argmax(dim=1).cpu().numpy()
            all_preds_5.extend(preds)
            all_labels_5.extend(y.numpy())

    all_preds_5 = np.asarray(all_preds_5)
    all_labels_5 = np.asarray(all_labels_5)
    all_preds_4 = np.asarray([map_5to4(label) for label in all_preds_5])
    all_labels_4 = np.asarray([map_5to4(label) for label in all_labels_5])

    metrics_4 = {
        "acc": accuracy_score(all_labels_4, all_preds_4),
        "f1": f1_score(all_labels_4, all_preds_4, average="macro"),
        "kappa": cohen_kappa_score(all_labels_4, all_preds_4),
        "cm": confusion_matrix(all_labels_4, all_preds_4, labels=[0, 1, 2, 3]),
        "preds_counter": Counter(all_preds_4),
    }
    metrics_5 = {
        "acc": accuracy_score(all_labels_5, all_preds_5),
        "f1": f1_score(all_labels_5, all_preds_5, average="macro"),
        "kappa": cohen_kappa_score(all_labels_5, all_preds_5),
        "cm": confusion_matrix(all_labels_5, all_preds_5, labels=[0, 1, 2, 3, 4]),
        "preds_counter": Counter(all_preds_5),
    }
    return {"4class": metrics_4, "5class": metrics_5}


def print_eval_summary(prefix, epoch, metrics):
    print(
        f"{prefix} Epoch {epoch} | "
        f"5-class Acc: {metrics['5class']['acc']:.4f} | "
        f"5-class F1: {metrics['5class']['f1']:.4f} | "
        f"5-class Kappa: {metrics['5class']['kappa']:.4f}"
    )
    print(
        f"{prefix} Epoch {epoch} | "
        f"4-class Acc: {metrics['4class']['acc']:.4f} | "
        f"4-class F1: {metrics['4class']['f1']:.4f} | "
        f"4-class Kappa: {metrics['4class']['kappa']:.4f}"
    )


def discover_fold_dirs(selected_fold_names=None):
    fold_dirs = sorted(
        os.path.join(folds_root, folder_name)
        for folder_name in os.listdir(folds_root)
        if folder_name.startswith("fold_") and os.path.isdir(os.path.join(folds_root, folder_name))
    )
    if not fold_dirs:
        raise FileNotFoundError("No fold directories found. Run 1split.py first.")

    if selected_fold_names:
        selected_fold_names = set(selected_fold_names)
        fold_dirs = [
            fold_dir
            for fold_dir in fold_dirs
            if os.path.basename(fold_dir) in selected_fold_names
        ]
        if not fold_dirs:
            raise FileNotFoundError(
                f"No matching fold directories found for {sorted(selected_fold_names)}."
            )
    return fold_dirs


def build_loaders(fold_dir):
    train_record_ids = load_split_record_ids(fold_dir, "train")
    val_record_ids = load_split_record_ids(fold_dir, "val")
    test_record_ids = load_split_record_ids(fold_dir, "test")

    train_patients = load_patient_data_to_dict(global_cache_dir, train_record_ids)
    val_patients = load_patient_data_to_dict(global_cache_dir, val_record_ids)
    test_patients = load_patient_data_to_dict(global_cache_dir, test_record_ids)

    train_dataset = SleepContextDataset(
        train_patients,
        window_size=window_size,
        augment=True,
        noise_augment_prob=noise_augment_prob,
        noise_std=noise_std,
    )
    val_dataset = SleepContextDataset(val_patients, window_size=window_size, augment=False)
    test_dataset = SleepContextDataset(test_patients, window_size=window_size, augment=False)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )

    return train_patients, train_dataset, train_loader, val_loader, test_loader


def build_class_weights(train_dataset, train_patients):
    all_train_y = []
    for patient_id, center_idx in train_dataset.samples:
        all_train_y.append(train_patients[patient_id]["y"][center_idx])
    all_train_y = np.asarray(all_train_y)

    present_classes = np.unique(all_train_y)
    present_weights = compute_class_weight(class_weight="balanced", classes=present_classes, y=all_train_y)
    base_weights = np.ones((num_classes,), dtype=np.float32)
    for class_id, class_weight in zip(present_classes, present_weights):
        base_weights[int(class_id)] = float(class_weight)
    for idx, class_name in enumerate(CLASS_NAMES):
        base_weights[idx] *= class_weight_multipliers.get(class_name, 1.0)

    return torch.tensor(base_weights, dtype=torch.float32, device=device), base_weights


def train_single_fold(fold_dir, fold_idx):
    fold_name = os.path.basename(fold_dir)
    print(f"\n{'=' * 80}\nTraining {fold_name}\n{'=' * 80}")

    seed_everything(random_seed + fold_idx)
    train_patients, train_dataset, train_loader, val_loader, test_loader = build_loaders(fold_dir)
    cls_weights, weights_np = build_class_weights(train_dataset, train_patients)
    print(f"{fold_name} class weights: {weights_np}")
    print(f"{fold_name} train windows: {len(train_dataset)} | window_size={window_size}")

    model = SleepStageNetV8(num_classes=num_classes, window_size=window_size).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weights_decay)
    criterion = nn.CrossEntropyLoss(weight=cls_weights, label_smoothing=label_smoothing)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)

    best_val_acc = -1.0
    best_epoch = 0
    epochs_without_improvement = 0
    checkpoint_path = os.path.join(model_dir, f"{fold_name}_{run_timestamp}_best.pth")

    for epoch in range(1, num_epochs + 1):
        model.train()
        total_loss = 0.0
        pbar = tqdm(train_loader, desc=f"{fold_name} Epoch {epoch}")

        for step_idx, (x, y) in enumerate(pbar, start=1):
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += loss.item()
            pbar.set_postfix(loss=total_loss / max(1, step_idx))

        scheduler.step()
        val_metrics = evaluate(model, val_loader)
        print_eval_summary(fold_name, epoch, val_metrics)

        current_val_acc = val_metrics["5class"]["acc"]
        if current_val_acc > best_val_acc:
            best_val_acc = current_val_acc
            best_epoch = epoch
            epochs_without_improvement = 0
            torch.save(model.state_dict(), checkpoint_path)
            print(
                f"{fold_name}: saved new best checkpoint at epoch {epoch} "
                f"(5-class val Acc={best_val_acc:.4f})"
            )
        else:
            epochs_without_improvement += 1
            print(f"{fold_name}: early stopping {epochs_without_improvement}/{early_stop_patience}")

        if epochs_without_improvement >= early_stop_patience:
            print(f"{fold_name}: early stopping triggered at epoch {epoch}")
            break

    model.load_state_dict(torch.load(checkpoint_path, map_location=device))
    test_metrics = evaluate(model, test_loader)
    print(
        f"{fold_name} best epoch {best_epoch} | "
        f"Test 5-class Acc={test_metrics['5class']['acc']:.4f}, "
        f"F1={test_metrics['5class']['f1']:.4f}, "
        f"Kappa={test_metrics['5class']['kappa']:.4f}"
    )

    return {
        "fold_name": fold_name,
        "best_epoch": best_epoch,
        "best_val_acc": best_val_acc,
        "test_metrics": test_metrics,
        "checkpoint_path": checkpoint_path,
    }


def summarize_fold_results(fold_results, scope):
    accs = np.asarray([result["test_metrics"][scope]["acc"] for result in fold_results], dtype=np.float64)
    f1s = np.asarray([result["test_metrics"][scope]["f1"] for result in fold_results], dtype=np.float64)
    kappas = np.asarray([result["test_metrics"][scope]["kappa"] for result in fold_results], dtype=np.float64)
    return {
        "acc_mean": float(accs.mean()),
        "acc_std": float(accs.std(ddof=0)),
        "f1_mean": float(f1s.mean()),
        "f1_std": float(f1s.std(ddof=0)),
        "kappa_mean": float(kappas.mean()),
        "kappa_std": float(kappas.std(ddof=0)),
    }


def print_cv_summary(summary, label):
    print(f"\n{label}")
    print(
        f"ACC: {summary['acc_mean']:.4f} +/- {summary['acc_std']:.4f}\n"
        f"Macro-F1: {summary['f1_mean']:.4f} +/- {summary['f1_std']:.4f}\n"
        f"Kappa: {summary['kappa_mean']:.4f} +/- {summary['kappa_std']:.4f}"
    )


def serialize_fold_results(fold_results, summary_5, summary_4):
    def to_serializable_metrics(metrics):
        return {
            "acc": float(metrics["acc"]),
            "f1": float(metrics["f1"]),
            "kappa": float(metrics["kappa"]),
            "cm": metrics["cm"].tolist(),
            "preds_counter": {str(key): int(value) for key, value in metrics["preds_counter"].items()},
        }

    payload = {
        "config": {
            "run_mode": RUN_MODE,
            "run_timestamp": run_timestamp,
            "experiment_name": experiment_name,
            "model_name": model_name,
            "batch_size": batch_size,
            "window_size": window_size,
            "lr": lr,
            "weights_decay": weights_decay,
            "num_epochs": num_epochs,
            "early_stop_patience": early_stop_patience,
            "random_seed": random_seed,
            "selected_folds": selected_folds,
            "label_smoothing": label_smoothing,
            "noise_augment_prob": noise_augment_prob,
            "noise_std": noise_std,
            "class_weight_multipliers": class_weight_multipliers,
            "notes": {
                "data_protocol": [
                    "uses subject-wise manifests generated by 1split.py",
                    "uses TinySleepNet-style cache from 2process1.py",
                    "same Sleep-EDF-78 / Fpz-Cz / 30s benchmark-style preprocessing",
                ],
                "model_protocol": [
                    "imports SleepStageNetV8 directly from 3mymodel.py",
                    "keeps original many-to-one context window training",
                    "evaluates both 5-class and merged 4-class metrics",
                ],
            },
        },
        "summary_5class": summary_5,
        "summary_4class": summary_4,
        "folds": [
            {
                "fold_name": result["fold_name"],
                "best_epoch": result["best_epoch"],
                "best_val_acc": result["best_val_acc"],
                "test_5class": to_serializable_metrics(result["test_metrics"]["5class"]),
                "test_4class": to_serializable_metrics(result["test_metrics"]["4class"]),
                "checkpoint_path": result["checkpoint_path"],
            }
            for result in fold_results
        ],
    }

    output_path = os.path.join(model_dir, "cv_results.json")
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
    print(f"\nSaved CV summary to {output_path}")
    return output_path


def append_run_registry(cv_results_path, fold_results, summary_5, summary_4):
    entry = {
        "run_timestamp": run_timestamp,
        "run_mode": RUN_MODE,
        "model_dir": model_dir,
        "cv_results_path": cv_results_path,
        "config": {
            "experiment_name": experiment_name,
            "model_name": model_name,
            "batch_size": batch_size,
            "window_size": window_size,
            "lr": lr,
            "weights_decay": weights_decay,
            "num_epochs": num_epochs,
            "early_stop_patience": early_stop_patience,
            "random_seed": random_seed,
            "selected_folds": selected_folds,
            "label_smoothing": label_smoothing,
            "noise_augment_prob": noise_augment_prob,
            "noise_std": noise_std,
            "class_weight_multipliers": class_weight_multipliers,
        },
        "summary_5class": summary_5,
        "summary_4class": summary_4,
        "folds": [
            {
                "fold_name": result["fold_name"],
                "best_epoch": result["best_epoch"],
                "best_val_acc": float(result["best_val_acc"]),
                "checkpoint_path": result["checkpoint_path"],
                "test_5class": {
                    "acc": float(result["test_metrics"]["5class"]["acc"]),
                    "f1": float(result["test_metrics"]["5class"]["f1"]),
                    "kappa": float(result["test_metrics"]["5class"]["kappa"]),
                },
                "test_4class": {
                    "acc": float(result["test_metrics"]["4class"]["acc"]),
                    "f1": float(result["test_metrics"]["4class"]["f1"]),
                    "kappa": float(result["test_metrics"]["4class"]["kappa"]),
                },
            }
            for result in fold_results
        ],
    }

    if os.path.exists(best_models_registry_path):
        with open(best_models_registry_path, "r", encoding="utf-8") as file:
            history = json.load(file)
    else:
        history = []

    history.append(entry)
    with open(best_models_registry_path, "w", encoding="utf-8") as file:
        json.dump(history, file, indent=2)
    print(f"Updated run registry at {best_models_registry_path}")


def main():
    print(f"Device: {device}")
    print(f"Run mode: {RUN_MODE}")
    print(f"Global cache: {global_cache_dir}")
    print(f"Selected folds: {selected_folds if selected_folds else 'all'}")

    fold_dirs = discover_fold_dirs(selected_folds)
    fold_results = []

    for fold_idx, fold_dir in enumerate(fold_dirs):
        fold_results.append(train_single_fold(fold_dir, fold_idx))

    summary_5 = summarize_fold_results(fold_results, "5class")
    summary_4 = summarize_fold_results(fold_results, "4class")
    print_cv_summary(summary_5, "5-class CV summary")
    print_cv_summary(summary_4, "4-class CV summary")

    cv_results_path = serialize_fold_results(fold_results, summary_5, summary_4)
    append_run_registry(cv_results_path, fold_results, summary_5, summary_4)


if __name__ == "__main__":
    main()
