import os
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm


# --- 环境设置 ---
device = "cuda" if torch.cuda.is_available() else "cpu"
data_dir = os.path.join(os.getcwd(), "sleep-edf", "data")
model_dir = os.path.join(data_dir, "model")
model_name = "model031401"
best_acc_save_path = os.path.join(model_dir, f"{model_name}.pth")
os.makedirs(model_dir, exist_ok=True)

# --- 超参数 ---
batch_size = 32
window_size = 15    # n
lr = 2e-3
weights_decay = 5e-4
num_epochs = 20
num_classes = 5
early_stop_patience = 7

# --- 1. 载入原始的病人数据到内存 ---
def load_patient_data_to_dict(root_path):
    """
    只把每个病人的原始数据读入字典，不构建滑动窗口。
    内存占用将从 40GB 降到 约 1.5GB。
    """
    patient_dir = os.path.join(root_path, "patient_data")
    patients = {}
    x_files = sorted([f for f in os.listdir(patient_dir) if f.endswith("_X.npy")])

    for file_name in tqdm(x_files, desc="Loading Patient Raw Data"):
        patient_id = file_name.replace("_X.npy", "")
        x = np.load(os.path.join(patient_dir, file_name)).astype(np.float32) # (N, 1, 3000)
        y = np.load(os.path.join(patient_dir, f"{patient_id}_y.npy")).astype(np.int64)
        
        # 预先清理无效标签
        valid = (y != -1)
        patients[patient_id] = {"x": x[valid], "y": y[valid]}

    return patients

# --- 2. 数据集类（增强增广：噪声 + 随机遮罩，移除时间拉伸）---
class SleepContextDataset(Dataset):
    def __init__(self, patient_dict, window_size, augment=False):
        self.window_size = window_size
        self.half_window = window_size // 2
        self.augment = augment
        self.samples = []
        self.patient_dict = patient_dict

        # 构建索引表：存储 (病人ID, 该中心Epoch的索引)
        for patient_id, data in patient_dict.items():
            n_epochs = len(data["y"])
            for center_idx in range(self.half_window, n_epochs - self.half_window):
                self.samples.append((patient_id, center_idx))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        patient_id, center_idx = self.samples[idx]

        # 实时切片：获取窗口数据 (window_size, 1, 3000)
        x = self.patient_dict[patient_id]["x"][center_idx - self.half_window : center_idx + self.half_window + 1]
        y = self.patient_dict[patient_id]["y"][center_idx]

        x = torch.from_numpy(x).float()
        y = torch.tensor(y, dtype=torch.long)

        # 数据增强...
        if self.augment and torch.rand(1) < 0.2:
            x = x + torch.randn_like(x) * 0.003

        return x, y

# --- 3. 模型（n通道输入）---
class SEBlock(nn.Module):
    def __init__(self, channel, reduction=16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(channel, channel // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channel // reduction, channel, bias=False),
            nn.Sigmoid(),
        )

    def forward(self, x):
        batch_size, channels, _, _ = x.size()
        y = self.avg_pool(x).view(batch_size, channels)
        y = self.fc(y).view(batch_size, channels, 1, 1)
        return x * y.expand_as(x)


class ResBlock(nn.Module):
    def __init__(self, in_ch, out_ch, stride=1):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, stride, 1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ELU(),
            nn.Conv2d(out_ch, out_ch, 3, 1, 1, bias=False),
            nn.BatchNorm2d(out_ch),
        )
        self.se = SEBlock(out_ch) # 新增注意力
        self.shortcut = nn.Sequential()
        if stride != 1 or in_ch != out_ch:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 1, stride, bias=False),
                nn.BatchNorm2d(out_ch),
            )
        self.elu = nn.ELU()

    def forward(self, x):
        out = self.conv(x)
        out = self.se(out) # 赋予特征通道权重
        return self.elu(out + self.shortcut(x))

# --- 修改后的主网络 ---
class SleepStageNetV8(nn.Module):
    def __init__(self, num_classes, window_size=15):
        super().__init__()
        self.window_size = window_size
        self.n_fft = 512
        self.hop_length = 64
        
        # --- 分支 A: 频谱特征提取 (2D CNN) ---
        self.spec_stem = nn.Sequential(
            nn.Conv2d(1, 32, 7, stride=2, padding=3, bias=False),
            nn.BatchNorm2d(32),
            nn.ELU(),
        )
        self.spec_stage = nn.Sequential(
            ResBlock(32, 64, stride=2),
            ResBlock(64, 128, stride=2),
            ResBlock(128, 128, stride=2), # 缩减输出通道为128
            nn.AdaptiveAvgPool2d((1, 1)),
        )

        # --- 分支 B: 原始波形特征提取 (1D CNN) ---
        # 模仿 TinySleepNet/DeepSleepNet 的小核+大核思想简化版
        self.raw_branch = nn.Sequential(
            # 第一层使用较大的卷积核捕捉低频节律 (如 Delta 波)
            nn.Conv1d(1, 64, kernel_size=64, stride=8, padding=32, bias=False),
            nn.BatchNorm1d(64),
            nn.ELU(),
            nn.MaxPool1d(kernel_size=8, stride=8),
            # 第二层捕捉局部细节
            nn.Conv1d(64, 128, kernel_size=16, stride=1, padding=8, bias=False),
            nn.BatchNorm1d(128),
            nn.ELU(),
            nn.AdaptiveAvgPool1d(1) # 输出维度 (B*T, 128, 1)
        )

        # --- 融合与时序层 ---
        # 两个分支各出 128 维，合起来是 256
        self.rnn = nn.GRU(
            128 + 128,
            128,
            num_layers=2,
            bidirectional=True,
            batch_first=True,
            dropout=0.3,
        )

        # 分类器
        self.classifier = nn.Sequential(
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        # x: [Batch, n, 1, 3001]
        batch_size, time_steps, channels, signal_len = x.shape
        x_flat = x.view(batch_size * time_steps, channels, signal_len) # [B*T, 1, 3001]

        # --- 1. 频谱分支 (2D) ---
        # 在 forward 内部计算频谱    
        window = torch.hann_window(self.n_fft, device=x.device)
        stft = torch.stft(
            x_flat.squeeze(1),
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            window=window,
            return_complex=True,
            center=True,
        )
        mag = (torch.abs(stft) + 1e-8).log().unsqueeze(1) # [B*T, 1, F, T]
        mag = mag[:, :, :128, :] # 取低频部分

        spec_fea = self.spec_stem(mag)
        spec_fea = self.spec_stage(spec_fea).flatten(1) # [B*T, 128]
        
        # --- 2. 原始波形分支 (1D) ---
        raw_fea = self.raw_branch(x_flat).flatten(1) # [B*T, 128]
        
        # --- 3. 特征融合 ---
        combined_fea = torch.cat([spec_fea, raw_fea], dim=1) # [B*T, 256]
        
        # --- 4. 还原序列维度过 RNN ---
        combined_fea = combined_fea.view(batch_size, time_steps, -1) # [B, n, 256]
        rnn_out, _ = self.rnn(combined_fea)  # [B, n, 256]
        
        # --- 5. 取中间 Epoch 输出 ---
        mid_idx = time_steps // 2
        return self.classifier(rnn_out[:, mid_idx, :])




# --- 4. 评估 ---
def evaluate(model, loader):
    model.eval()
    all_preds_5, all_labels_5 = [], []

    # 定义 5类 到 4类 的映射规则
    # 原始(5类): 0:W, 1:N1, 2:N2, 3:N3, 4:REM
    # 目标(4类): 0:W, 1:REM, 2:Light(N1+N2), 3:Deep(N3)
    def map_5to4(label):
        if label == 0: return 0 # W -> W
        if label == 4: return 1 # REM -> REM
        if label == 1 or label == 2: return 2 # N1, N2 -> Light
        if label == 3: return 3 # N3 -> Deep
        return label
    
    with torch.no_grad():
        for x, y in loader:
            outputs = model(x.to(device))
            all_preds_5.extend(outputs.argmax(1).cpu().numpy())
            all_labels_5.extend(y.numpy())

    all_preds_5 = np.array(all_preds_5)
    all_labels_5 = np.array(all_labels_5)
    all_preds_4 = np.array([map_5to4(pred) for pred in all_preds_5])
    all_labels_4 = np.array([map_5to4(label) for label in all_labels_5])

    metrics_4 = {
        "acc": accuracy_score(all_labels_4, all_preds_4),
        "f1": f1_score(all_labels_4, all_preds_4, average="macro"),
        "cm": confusion_matrix(all_labels_4, all_preds_4, labels=[0, 1, 2, 3]),
        "preds_counter": Counter(all_preds_4),
    }
    metrics_5 = {
        "acc": accuracy_score(all_labels_5, all_preds_5),
        "f1": f1_score(all_labels_5, all_preds_5, average="macro"),
        "cm": confusion_matrix(all_labels_5, all_preds_5, labels=[0, 1, 2, 3, 4]),
        "preds_counter": Counter(all_preds_5),
    }

    return {"4class": metrics_4, "5class": metrics_5}


def print_eval_summary(epoch, metrics):
    metrics_4 = metrics["4class"]
    metrics_5 = metrics["5class"]

    cm1 = metrics_4["cm"]  # 4-class confusion matrix
    cm2 = metrics_5["cm"]  # 5-class confusion matrix
    class_accuracies1 = cm1.diagonal() / cm1.sum(axis=1)
    class_accuracies2 = cm2.diagonal() / cm2.sum(axis=1)
    dist1 = {f"{i}": f"{acc:.4f}" for i, acc in zip(['W', 'REM', 'Light', 'Deep'],class_accuracies1)}
    dist2 = {f"{i}": f"{acc:.4f}" for i, acc in zip(['W', 'N1', 'N2', 'N3', 'REM'],class_accuracies2)}

    print(f"Epoch {epoch} | 4-class Acc: {metrics_4['acc']:.4f} | 4-class F1: {metrics_4['f1']:.4f} | Acc: {dist1}")
    print(f"Epoch {epoch} | 5-class Acc: {metrics_5['acc']:.4f} | 5-class F1: {metrics_5['f1']:.4f} | Acc: {dist2}")


def print_confusion_matrix(cm, acc, f1, epoch, title_prefix="Validation"):
    plt.figure(figsize=(7, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title(f"{title_prefix} Epoch {epoch} | Acc: {acc:.4f} | F1: {f1:.4f}")
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.show()

# --- 5. 主训练程序 ---
if __name__ == "__main__":
    
    # 1. 路径设置
    data_cache_train = os.path.join(data_dir, "train", "cache")
    data_cache_val = os.path.join(data_dir, "val", "cache")
    # 2. 载入原始数据
    print("Step 1: Loading raw data into memory...")
    train_patients = load_patient_data_to_dict(data_cache_train)
    val_patients = load_patient_data_to_dict(data_cache_val)
    # 3. 初始化 Dataset 
    train_dataset = SleepContextDataset(train_patients, window_size=window_size, augment=True)
    val_dataset = SleepContextDataset(val_patients, window_size=window_size)
    # 4. 计算类别权重（用于处理 N3 比例较低问题）
    print("Step 2: Calculating class weights...")
    # 从索引中提取所有 y 标签
    all_train_y = []
    for patient_id, center_idx in train_dataset.samples:
        all_train_y.append(train_patients[patient_id]["y"][center_idx])
    all_train_y = np.array(all_train_y)

    # 自动计算平衡权重
    weights = compute_class_weight("balanced", classes=np.unique(all_train_y), y=all_train_y)
    
    # 微调权重：针对 N3（索引3）和 REM（索引4）进一步加强
    weights[3] *= 1.2  # 进一步提升 N3 权重
    weights[4] *= 1.15  # 进一步提升 REM 权重
    cls_weights = torch.tensor(weights, dtype=torch.float32).to(device)
    print(f"Final Weights: {weights}")
    # 5. 定义 DataLoader
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        num_workers=0,
        pin_memory=True,
    )
    # 6. 初始化模型、优化器、缩放器
    model = SleepStageNetV8(num_classes=num_classes, window_size=window_size).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weights_decay)
    criterion = nn.CrossEntropyLoss(weight=cls_weights, label_smoothing=0.1)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)

    # 7. 训练循环
    best_acc = 0.0
    best_acc_epoch = 0
    epochs_without_improvement = 0

    for epoch in range(num_epochs):
        model.train()
        total_loss = 0.0
        pbar = tqdm(train_loader, desc=f"Epoch {epoch + 1}")

        for x, y in pbar:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            outputs = model(x)
            loss = criterion(outputs, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += loss.item()
            pbar.set_postfix(loss=total_loss / len(pbar))

        metrics = evaluate(model, val_loader)
        print_eval_summary(epoch + 1, metrics)
        scheduler.step()

        current_acc = metrics["4class"]["acc"]
        current_f1 = metrics["4class"]["f1"]

        if current_acc > best_acc:
            best_acc = current_acc
            best_acc_epoch = epoch + 1
            epochs_without_improvement = 0
            if current_acc > 0.84:
                torch.save(model.state_dict(), best_acc_save_path)
                print(f">>> New Best Acc Model Saved (Acc: {best_acc:.4f})")
                print_confusion_matrix(metrics["4class"]["cm"], current_acc, current_f1, epoch + 1, title_prefix="Best Acc")

        else:
            epochs_without_improvement += 1
            print(
                f"Early stopping counter: {epochs_without_improvement}/"
                f"{early_stop_patience}"
            )

        if epochs_without_improvement >= early_stop_patience:
            print(f"Early stopping triggered at epoch {epoch + 1}. ")
            break

    print(f"Final Best 4-class Acc: {best_acc:.4f} (epoch {best_acc_epoch})")