import torch
import torch.nn as nn

# --- 模型（n通道输入）---
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

