import json
import os
import random
from collections import Counter
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm


device = "cuda" if torch.cuda.is_available() else "cpu"
amp_enabled = device == "cuda"
data_dir = os.path.join(os.getcwd(), "sleep-edf", "data")
folds_root = os.path.join(data_dir, "folds")
global_cache_dir = os.path.join(data_dir, "global_cache1", "patient_data")
RUN_MODE = os.environ.get("RUN_MODE", "dev")
SELECTED_FOLDS_OVERRIDE = os.environ.get("SELECTED_FOLDS")
CLASS_NAMES = ["W", "N1", "N2", "N3", "REM"]


CONFIGS = {
    "dev": {
        "experiment_name": "tiny_sleepnet_repro",
        "batch_size": 15,
        "seq_length": 20,
        "chunk_size": 3000,
        "lr": 1e-4,
        "num_epochs": 200,
        "num_classes": 5,
        "early_stop_patience": 50,
        "random_seed": 42,
        "selected_folds": ["fold_02"],
        "signal_dropout": 0.5,
        "n_filters_1": 128,
        "filter_size_1": 50,
        "filter_stride_1": 6,
        "pool_size_1": 8,
        "pool_stride_1": 8,
        "n_filters_1x3": 128,
        "filter_size_1x3": 8,
        "pool_size_2": 4,
        "pool_stride_2": 4,
        "rnn_hidden_size": 128,
        "class_weights": [1.0, 1.5, 1.0, 1.0, 1.0],
        "cnn_l2_weight_decay": 1e-3,
        "grad_clip_norm": 5.0,
        "augment_seq": True,
        "max_seq_skip": 5,
        "signal_augment_prob": 0.5,
        "signal_augment_shift": 300,
    },
    "full": {
        "experiment_name": "tiny_sleepnet_repro",
        "batch_size": 15,
        "seq_length": 20,
        "chunk_size": 3000,
        "lr": 1e-4,
        "num_epochs": 200,
        "num_classes": 5,
        "early_stop_patience": 50,
        "random_seed": 42,
        "selected_folds": None,
        "signal_dropout": 0.5,
        "n_filters_1": 128,
        "filter_size_1": 50,
        "filter_stride_1": 6,
        "pool_size_1": 8,
        "pool_stride_1": 8,
        "n_filters_1x3": 128,
        "filter_size_1x3": 8,
        "pool_size_2": 4,
        "pool_stride_2": 4,
        "rnn_hidden_size": 128,
        "class_weights": [1.0, 1.5, 1.0, 1.0, 1.0],
        "cnn_l2_weight_decay": 1e-3,
        "grad_clip_norm": 5.0,
        "augment_seq": True,
        "max_seq_skip": 5,
        "signal_augment_prob": 0.5,
        "signal_augment_shift": 300,
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
seq_length = active_config["seq_length"]
chunk_size = active_config["chunk_size"]
lr = active_config["lr"]
num_epochs = active_config["num_epochs"]
num_classes = active_config["num_classes"]
early_stop_patience = active_config["early_stop_patience"]
random_seed = active_config["random_seed"]
selected_folds = parse_selected_folds(active_config["selected_folds"])
experiment_name = active_config["experiment_name"]
signal_dropout = active_config["signal_dropout"]
n_filters_1 = active_config["n_filters_1"]
filter_size_1 = active_config["filter_size_1"]
filter_stride_1 = active_config["filter_stride_1"]
pool_size_1 = active_config["pool_size_1"]
pool_stride_1 = active_config["pool_stride_1"]
n_filters_1x3 = active_config["n_filters_1x3"]
filter_size_1x3 = active_config["filter_size_1x3"]
pool_size_2 = active_config["pool_size_2"]
pool_stride_2 = active_config["pool_stride_2"]
rnn_hidden_size = active_config["rnn_hidden_size"]
class_weights = active_config["class_weights"]
cnn_l2_weight_decay = active_config["cnn_l2_weight_decay"]
grad_clip_norm = active_config["grad_clip_norm"]
augment_seq = active_config["augment_seq"]
max_seq_skip = active_config["max_seq_skip"]
signal_augment_prob = active_config["signal_augment_prob"]
signal_augment_shift = active_config["signal_augment_shift"]

model_root = os.path.join(data_dir, "model", "tiny_sleepnet")
model_dir = os.path.join(model_root, RUN_MODE)
os.makedirs(model_dir, exist_ok=True)
best_models_registry_path = os.path.join(model_root, "best_models.json")
run_timestamp = datetime.now().strftime("%m%d_%H%M")


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
                f"Missing cached record {record_id}. Run 2process.py to build the global cache first."
            )

        x = np.load(x_path).astype(np.float32)
        y = np.load(y_path).astype(np.int64)
        valid = y != -1
        patients[record_id] = {"x": x[valid], "y": y[valid]}

    return patients


class SleepSequenceDataset(Dataset):
    def __init__(
        self,
        patient_dict,
        seq_length,
        training=False,
        augment_seq=False,
        max_seq_skip=0,
        signal_augment_prob=0.0,
        signal_augment_shift=0,
    ):
        self.patient_dict = patient_dict
        self.seq_length = seq_length
        self.training = training
        self.augment_seq = augment_seq
        self.max_seq_skip = max_seq_skip
        self.signal_augment_prob = signal_augment_prob
        self.signal_augment_shift = signal_augment_shift
        first_record = next(iter(patient_dict.values()))
        self.signal_len = int(first_record["x"].shape[-1])
        self.samples = []
        self.refresh(randomize=training)

    def refresh(self, randomize):
        self.samples = []
        for record_id, data in self.patient_dict.items():
            n_epochs = len(data["y"])
            if n_epochs == 0:
                continue

            skip = 0
            if self.training and self.augment_seq and randomize and self.max_seq_skip > 0:
                skip = random.randint(0, self.max_seq_skip)
                skip = min(skip, max(0, n_epochs - 1))

            for start in range(skip, n_epochs, self.seq_length):
                stop = min(start + self.seq_length, n_epochs)
                self.samples.append((record_id, start, stop))

    def __len__(self):
        return len(self.samples)

    def _augment_signal(self, x_seq, valid_len):
        if self.signal_augment_prob <= 0.0 or self.signal_augment_shift <= 0:
            return x_seq
        if random.random() > self.signal_augment_prob:
            return x_seq

        augmented = np.array(x_seq, copy=True)
        for idx in range(valid_len):
            shift = random.randint(-self.signal_augment_shift, self.signal_augment_shift)
            augmented[idx, 0] = np.roll(augmented[idx, 0], shift)
        return augmented

    def __getitem__(self, index):
        record_id, start, stop = self.samples[index]
        x_seq = self.patient_dict[record_id]["x"][start:stop]
        y_seq = self.patient_dict[record_id]["y"][start:stop]
        valid_len = len(y_seq)

        if self.training:
            x_seq = self._augment_signal(x_seq, valid_len)

        x_padded = np.zeros((self.seq_length, 1, self.signal_len), dtype=np.float32)
        y_padded = np.zeros((self.seq_length,), dtype=np.int64)
        mask = np.zeros((self.seq_length,), dtype=np.float32)

        x_padded[:valid_len] = x_seq
        y_padded[:valid_len] = y_seq
        mask[:valid_len] = 1.0

        return (
            torch.from_numpy(x_padded).float(),
            torch.from_numpy(y_padded).long(),
            torch.from_numpy(mask).float(),
        )


class Conv1dSamePadding(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, bias=False):
        super().__init__()
        self.kernel_size = kernel_size
        self.stride = stride
        self.conv = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size,
            stride=stride,
            padding=0,
            bias=bias,
        )

    def forward(self, x):
        in_length = x.size(-1)
        out_length = int(np.ceil(in_length / self.stride))
        pad_needed = max((out_length - 1) * self.stride + self.kernel_size - in_length, 0)
        pad_left = pad_needed // 2
        pad_right = pad_needed - pad_left
        if pad_needed > 0:
            x = F.pad(x, (pad_left, pad_right))
        return self.conv(x)


class Conv1dBnReLU(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1):
        super().__init__()
        self.conv = Conv1dSamePadding(
            in_channels,
            out_channels,
            kernel_size=kernel_size,
            stride=stride,
            bias=False,
        )
        self.bn = nn.BatchNorm1d(out_channels, eps=1e-3, momentum=0.01)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        return self.relu(x)


class TinySleepNetFeatureExtractor(nn.Module):
    def __init__(
        self,
        chunk_size,
        dropout,
        n_filters_1,
        filter_size_1,
        filter_stride_1,
        pool_size_1,
        pool_stride_1,
        n_filters_1x3,
        filter_size_1x3,
        pool_size_2,
        pool_stride_2,
    ):
        super().__init__()
        self.conv1 = Conv1dBnReLU(1, n_filters_1, kernel_size=filter_size_1, stride=filter_stride_1)
        self.pool1 = nn.MaxPool1d(kernel_size=pool_size_1, stride=pool_stride_1)
        self.dropout1 = nn.Dropout(dropout)
        self.conv2_1 = Conv1dBnReLU(
            n_filters_1,
            n_filters_1x3,
            kernel_size=filter_size_1x3,
            stride=1,
        )
        self.conv2_2 = Conv1dBnReLU(
            n_filters_1x3,
            n_filters_1x3,
            kernel_size=filter_size_1x3,
            stride=1,
        )
        self.conv2_3 = Conv1dBnReLU(
            n_filters_1x3,
            n_filters_1x3,
            kernel_size=filter_size_1x3,
            stride=1,
        )
        self.pool2 = nn.MaxPool1d(kernel_size=pool_size_2, stride=pool_stride_2)
        self.dropout2 = nn.Dropout(dropout)
        out_length = chunk_size // filter_stride_1 // pool_stride_1 // pool_stride_2
        self.feature_dim = out_length * n_filters_1x3

    def forward(self, x):
        x = self.conv1(x)
        x = self.pool1(x)
        x = self.dropout1(x)
        x = self.conv2_1(x)
        x = self.conv2_2(x)
        x = self.conv2_3(x)
        x = self.pool2(x)
        x = self.dropout2(x)
        return x.flatten(1)

    def cnn_weight_parameters(self):
        return [
            self.conv1.conv.conv.weight,
            self.conv2_1.conv.conv.weight,
            self.conv2_2.conv.conv.weight,
            self.conv2_3.conv.conv.weight,
        ]


class TinySleepNetRepro(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.feature_extractor = TinySleepNetFeatureExtractor(
            chunk_size=chunk_size,
            dropout=signal_dropout,
            n_filters_1=n_filters_1,
            filter_size_1=filter_size_1,
            filter_stride_1=filter_stride_1,
            pool_size_1=pool_size_1,
            pool_stride_1=pool_stride_1,
            n_filters_1x3=n_filters_1x3,
            filter_size_1x3=filter_size_1x3,
            pool_size_2=pool_size_2,
            pool_stride_2=pool_stride_2,
        )
        self.rnn = nn.LSTM(
            input_size=self.feature_extractor.feature_dim,
            hidden_size=rnn_hidden_size,
            num_layers=1,
            bidirectional=False,
            batch_first=True,
        )
        self.classifier = nn.Linear(rnn_hidden_size, num_classes)
        self._reset_parameters()

    def _reset_parameters(self):
        for module in self.modules():
            if isinstance(module, nn.Conv1d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.BatchNorm1d):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)

        for name, param in self.rnn.named_parameters():
            if "weight_ih" in name:
                nn.init.xavier_uniform_(param)
            elif "weight_hh" in name:
                nn.init.orthogonal_(param)
            elif "bias" in name:
                nn.init.zeros_(param)
                hidden = self.rnn.hidden_size
                param.data[hidden : 2 * hidden] = 1.0

    def cnn_weight_parameters(self):
        return self.feature_extractor.cnn_weight_parameters()

    def forward(self, x):
        batch_size, time_steps, channels, signal_len = x.shape
        x = x.view(batch_size * time_steps, channels, signal_len)
        features = self.feature_extractor(x)
        features = features.view(batch_size, time_steps, -1)
        sequence_output, _ = self.rnn(features)
        return self.classifier(sequence_output)


def build_model():
    return TinySleepNetRepro(num_classes=num_classes)


def masked_sequence_cross_entropy(logits, targets, mask, criterion):
    per_step_loss = criterion(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
    weighted_loss = per_step_loss * mask.reshape(-1)
    return weighted_loss.sum() / mask.sum().clamp_min(1.0)


def cnn_l2_regularization(model):
    reg_loss = None
    for param in model.cnn_weight_parameters():
        value = 0.5 * torch.sum(param * param)
        reg_loss = value if reg_loss is None else reg_loss + value
    if reg_loss is None:
        return torch.tensor(0.0, device=device)
    return reg_loss


def evaluate(model, loader):
    model.eval()
    all_preds_5, all_labels_5 = [], []

    with torch.no_grad():
        for x, y, mask in loader:
            x = x.to(device, non_blocking=True)
            with torch.amp.autocast(device_type=device, enabled=amp_enabled):
                logits = model(x)

            preds = logits.argmax(-1).cpu()
            valid_mask = mask.bool()
            all_preds_5.extend(preds[valid_mask].numpy())
            all_labels_5.extend(y[valid_mask].numpy())

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

    train_dataset = SleepSequenceDataset(
        train_patients,
        seq_length=seq_length,
        training=True,
        augment_seq=augment_seq,
        max_seq_skip=max_seq_skip,
        signal_augment_prob=signal_augment_prob,
        signal_augment_shift=signal_augment_shift,
    )
    val_dataset = SleepSequenceDataset(
        val_patients,
        seq_length=seq_length,
        training=False,
        augment_seq=False,
    )
    test_dataset = SleepSequenceDataset(
        test_patients,
        seq_length=seq_length,
        training=False,
        augment_seq=False,
    )

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


def build_class_weights():
    weights = torch.tensor(class_weights, dtype=torch.float32, device=device)
    return weights, np.asarray(class_weights, dtype=np.float32)


def train_single_fold(fold_dir, fold_idx):
    fold_name = os.path.basename(fold_dir)
    print(f"\n{'=' * 80}\nTraining {fold_name}\n{'=' * 80}")

    seed_everything(random_seed + fold_idx)
    _, train_dataset, train_loader, val_loader, test_loader = build_loaders(fold_dir)
    cls_weights, weights_np = build_class_weights()
    print(f"{fold_name} class weights: {weights_np}")
    print(f"{fold_name} train sequences: {len(train_dataset)} | seq_length={seq_length}")

    model = build_model().to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss(weight=cls_weights, reduction="none")
    scaler = torch.amp.GradScaler(device, enabled=amp_enabled)

    best_val_acc = -1.0
    best_epoch = 0
    epochs_without_improvement = 0
    checkpoint_path = os.path.join(model_dir, f"{fold_name}_{run_timestamp}_best.pth")

    for epoch in range(1, num_epochs + 1):
        train_dataset.refresh(randomize=True)
        model.train()
        total_loss = 0.0
        pbar = tqdm(train_loader, desc=f"{fold_name} Epoch {epoch}")

        for x, y, mask in pbar:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            mask = mask.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type=device, enabled=amp_enabled):
                logits = model(x)
                loss = masked_sequence_cross_entropy(logits, y, mask, criterion)
                if cnn_l2_weight_decay > 0.0:
                    loss = loss + cnn_l2_weight_decay * cnn_l2_regularization(model)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=grad_clip_norm)
            scaler.step(optimizer)
            scaler.update()

            total_loss += loss.item()
            pbar.set_postfix(loss=total_loss / max(1, len(pbar)))

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
            "batch_size": batch_size,
            "seq_length": seq_length,
            "chunk_size": chunk_size,
            "lr": lr,
            "num_epochs": num_epochs,
            "early_stop_patience": early_stop_patience,
            "random_seed": random_seed,
            "selected_folds": selected_folds,
            "signal_dropout": signal_dropout,
            "n_filters_1": n_filters_1,
            "filter_size_1": filter_size_1,
            "filter_stride_1": filter_stride_1,
            "pool_size_1": pool_size_1,
            "pool_stride_1": pool_stride_1,
            "n_filters_1x3": n_filters_1x3,
            "filter_size_1x3": filter_size_1x3,
            "pool_size_2": pool_size_2,
            "pool_stride_2": pool_stride_2,
            "rnn_hidden_size": rnn_hidden_size,
            "class_weights": class_weights,
            "cnn_l2_weight_decay": cnn_l2_weight_decay,
            "grad_clip_norm": grad_clip_norm,
            "augment_seq": augment_seq,
            "max_seq_skip": max_seq_skip,
            "signal_augment_prob": signal_augment_prob,
            "signal_augment_shift": signal_augment_shift,
            "notes": {
                "official_tinysleepnet_alignment": [
                    "single-branch CNN feature extractor",
                    "single-layer unidirectional LSTM",
                    "sequence training with seq_length=20",
                    "mini-batch size 15",
                    "N1-upweighted cross entropy",
                    "sequence-start skip augmentation",
                    "best checkpoint selected by validation accuracy",
                ],
                "known_deviations": [
                    "uses PyTorch instead of TensorFlow 1.x",
                    "uses standard LSTM instead of peephole LSTM",
                    "uses 10-fold local subject split generated by 1split.py",
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


def append_best_models_registry(fold_results, summary_5, summary_4, cv_results_path):
    def to_serializable_metrics(metrics):
        return {
            "acc": float(metrics["acc"]),
            "f1": float(metrics["f1"]),
            "kappa": float(metrics["kappa"]),
            "cm": metrics["cm"].tolist(),
            "preds_counter": {str(key): int(value) for key, value in metrics["preds_counter"].items()},
        }

    record = {
        "run_timestamp": run_timestamp,
        "run_mode": RUN_MODE,
        "model_dir": model_dir,
        "cv_results_path": cv_results_path,
        "config": {
            "experiment_name": experiment_name,
            "batch_size": batch_size,
            "seq_length": seq_length,
            "chunk_size": chunk_size,
            "lr": lr,
            "num_epochs": num_epochs,
            "early_stop_patience": early_stop_patience,
            "random_seed": random_seed,
            "selected_folds": selected_folds,
            "signal_dropout": signal_dropout,
            "rnn_hidden_size": rnn_hidden_size,
            "class_weights": class_weights,
            "cnn_l2_weight_decay": cnn_l2_weight_decay,
            "grad_clip_norm": grad_clip_norm,
            "augment_seq": augment_seq,
            "max_seq_skip": max_seq_skip,
            "signal_augment_prob": signal_augment_prob,
            "signal_augment_shift": signal_augment_shift,
        },
        "summary_5class": summary_5,
        "summary_4class": summary_4,
        "folds": [
            {
                "fold_name": result["fold_name"],
                "best_epoch": int(result["best_epoch"]),
                "best_val_acc": float(result["best_val_acc"]),
                "checkpoint_path": result["checkpoint_path"],
                "test_5class": to_serializable_metrics(result["test_metrics"]["5class"]),
                "test_4class": to_serializable_metrics(result["test_metrics"]["4class"]),
            }
            for result in fold_results
        ],
    }

    if os.path.exists(best_models_registry_path):
        with open(best_models_registry_path, "r", encoding="utf-8") as file:
            try:
                registry = json.load(file)
            except json.JSONDecodeError:
                registry = []
    else:
        registry = []

    if not isinstance(registry, list):
        registry = []

    registry.append(record)

    with open(best_models_registry_path, "w", encoding="utf-8") as file:
        json.dump(registry, file, indent=2)

    print(f"Updated best model registry: {best_models_registry_path}")


if __name__ == "__main__":
    seed_everything(random_seed)
    if not os.path.isdir(global_cache_dir):
        raise FileNotFoundError(
            f"Global cache not found: {global_cache_dir}. Run 2process.py first."
        )

    print(
        f"Run mode: {RUN_MODE} | experiment: {experiment_name} | "
        f"folds: {selected_folds if selected_folds else 'all'} | "
        f"epochs: {num_epochs} | patience: {early_stop_patience} | "
        f"seq_length: {seq_length} | batch_size: {batch_size}"
    )

    fold_dirs = discover_fold_dirs(selected_folds)
    fold_results = []

    for fold_idx, fold_dir in enumerate(fold_dirs):
        fold_results.append(train_single_fold(fold_dir, fold_idx))

    summary_5 = summarize_fold_results(fold_results, "5class")
    summary_4 = summarize_fold_results(fold_results, "4class")

    print("\n" + "=" * 80)
    print("Cross-validation summary (held-out test folds)")
    print("=" * 80)
    print_cv_summary(summary_5, "5-class")
    print_cv_summary(summary_4, "4-class")

    cv_results_path = serialize_fold_results(fold_results, summary_5, summary_4)
    append_best_models_registry(fold_results, summary_5, summary_4, cv_results_path)
