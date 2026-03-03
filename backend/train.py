import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.optim.lr_scheduler as lr_scheduler
import numpy as np
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight
from tqdm import tqdm
import os
from collections import Counter
import matplotlib.pyplot as plt
import seaborn as sns


# --- 环境设置 ---
device = 'cuda' if torch.cuda.is_available() else 'cpu'
data_dir = os.path.join(os.getcwd(), 'sleep-edf', 'data')

# --- 超参数 ---
batch_size = 32
window_size = 15    # n
lr = 5e-4
num_epochs = 30
num_classes = 5

# --- 1. 载入原始的病人数据到内存 ---
def load_patient_data_to_dict(root_path):
    """
    只把每个病人的原始数据读入字典，不构建滑动窗口。
    内存占用将从 40GB 降到 约 1.5GB。
    """
    patient_dir = os.path.join(root_path, 'patient_data')
    patients = {}
    x_files = sorted([f for f in os.listdir(patient_dir) if f.endswith('_X.npy')])
    
    for f in tqdm(x_files, desc="Loading Patient Raw Data"):
        pid = f.replace('_X.npy', '')
        x = np.load(os.path.join(patient_dir, f)).astype(np.float32) # (N, 1, 3000)
        y = np.load(os.path.join(patient_dir, f"{pid}_y.npy")).astype(np.int64)
        
        # 预先清理无效标签
        valid = (y != -1)
        patients[pid] = {'x': x[valid], 'y': y[valid]}
        
    return patients


# --- 2. 数据集类（增强增广：噪声 + 随机遮罩，移除时间拉伸）---
class SleepContextDataset(Dataset):
    def __init__(self, patient_dict, window_size, augment=False):
        self.window_size = window_size
        self.half_window = window_size // 2
        self.augment = augment
        self.samples = []
        
        # 构建索引表：存储 (病人ID, 该中心Epoch的索引)
        for pid, data in patient_dict.items():
            n_epochs = len(data['y'])
            for i in range(self.half_window, n_epochs - self.half_window):
                self.samples.append((pid, i))
        
        self.patient_dict = patient_dict

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        pid, center_idx = self.samples[idx]
        
        # 实时切片：获取窗口数据 (window_size, 1, 3000)
        x = self.patient_dict[pid]['x'][center_idx - self.half_window : center_idx + self.half_window + 1]
        y = self.patient_dict[pid]['y'][center_idx]
        
        x = torch.from_numpy(x).float()
        y = torch.tensor(y, dtype=torch.long)
        
        # 数据增强...
        if self.augment:
            if torch.rand(1) < 0.2:
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
            nn.Sigmoid()
        )

    def forward(self, x):
        b, c, _, _ = x.size()
        y = self.avg_pool(x).view(b, c)
        y = self.fc(y).view(b, c, 1, 1)
        return x * y.expand_as(x)

class ResBlock(nn.Module):
    def __init__(self, in_ch, out_ch, stride=1):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, stride, 1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ELU(),
            nn.Conv2d(out_ch, out_ch, 3, 1, 1, bias=False),
            nn.BatchNorm2d(out_ch)
        )
        self.se = SEBlock(out_ch) # 新增注意力
        self.shortcut = nn.Sequential()
        if stride != 1 or in_ch != out_ch:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 1, stride, bias=False),
                nn.BatchNorm2d(out_ch)
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
            nn.ELU()
        )
        self.spec_stage = nn.Sequential(
            ResBlock(32, 64, stride=2),
            ResBlock(64, 128, stride=2),
            ResBlock(128, 128, stride=2), # 缩减输出通道为128
            nn.AdaptiveAvgPool2d((1, 1))
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
        self.rnn = nn.GRU(128 + 128, 128, num_layers=2, bidirectional=True, batch_first=True, dropout=0.3)
        
        # 分类器
        self.classifier = nn.Sequential(
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        # x: [Batch, n, 1, 3001]
        b, t, c, s = x.shape
        x_flat = x.view(b * t, c, s) # [B*T, 1, 3001]
        
        # --- 1. 频谱分支 (2D) ---
        # 在 forward 内部计算频谱
        win = torch.hann_window(self.n_fft).to(x.device)
        stft = torch.stft(x_flat.squeeze(1), n_fft=self.n_fft, hop_length=self.hop_length, 
                          window=win, return_complex=True, center=True)
        mag = (torch.abs(stft) + 1e-8).log().unsqueeze(1) # [B*T, 1, F, T]
        mag = mag[:, :, :128, :] # 取低频部分
        
        spec_fea = self.spec_stem(mag)
        spec_fea = self.spec_stage(spec_fea).flatten(1) # [B*T, 128]
        
        # --- 2. 原始波形分支 (1D) ---
        raw_fea = self.raw_branch(x_flat).flatten(1) # [B*T, 128]
        
        # --- 3. 特征融合 ---
        combined_fea = torch.cat([spec_fea, raw_fea], dim=1) # [B*T, 256]
        
        # --- 4. 还原序列维度过 RNN ---
        combined_fea = combined_fea.view(b, t, -1) # [B, n, 256]
        rnn_out, _ = self.rnn(combined_fea)  # [B, n, 256]
        
        # --- 5. 取中间 Epoch 输出 ---
        mid_idx = t // 2
        return self.classifier(rnn_out[:, mid_idx, :])



# --- 4. 评估 ---
def evaluate(model, loader):
    model.eval()
    all_p_4, all_l_4 = [], [] # 存放合并后的 4 分类结果
    
    # 定义 5类 到 4类 的映射规则 (根据你的实际标签定义)
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
            outputs = model(x.to(device)) # 输出是 5 维
            preds_5 = outputs.argmax(1).cpu().numpy()
            labels_5 = y.numpy()
            
            # 执行合并逻辑
            preds_4 = [map_5to4(p) for p in preds_5]
            labels_4 = [map_5to4(l) for l in labels_5]
            
            all_p_4.extend(preds_4)
            all_l_4.extend(labels_4)
            
    return accuracy_score(all_l_4, all_p_4), f1_score(all_l_4, all_p_4, average='macro'), \
           confusion_matrix(all_l_4, all_p_4), Counter(all_p_4)

def print_confusion_matrix(cm, acc, f1, epoch):
    plt.figure(figsize=(7, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
    plt.title(f"Epoch {epoch} | Acc: {acc:.4f} | F1: {f1:.4f}")
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.show()
    # 计算每个分类的准确率
    class_accuracies = cm.diagonal() / cm.sum(axis=1)
    print(f"Epoch {epoch} | Overall Acc: {acc:.4f} | F1: {f1:.4f}")
    print("Class-wise Accuracies:")
    for i, class_acc in enumerate(class_accuracies):
        print(f"  Class {i}: {class_acc:.4f}")

