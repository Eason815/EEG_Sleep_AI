import torch
import torch.nn as nn


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
        self.se = SEBlock(out_ch)
        self.shortcut = nn.Sequential()
        if stride != 1 or in_ch != out_ch:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 1, stride, bias=False),
                nn.BatchNorm2d(out_ch),
            )
        self.elu = nn.ELU()

    def forward(self, x):
        out = self.conv(x)
        out = self.se(out)
        return self.elu(out + self.shortcut(x))


class SleepStageNetV8(nn.Module):
    def __init__(self, num_classes, window_size=15):
        super().__init__()
        self.window_size = window_size
        self.n_fft = 512
        self.hop_length = 64

        self.spec_stem = nn.Sequential(
            nn.Conv2d(1, 32, 7, stride=2, padding=3, bias=False),
            nn.BatchNorm2d(32),
            nn.ELU(),
        )
        self.spec_stage = nn.Sequential(
            ResBlock(32, 64, stride=2),
            ResBlock(64, 128, stride=2),
            ResBlock(128, 128, stride=2),
            nn.AdaptiveAvgPool2d((1, 1)),
        )

        self.raw_branch = nn.Sequential(
            nn.Conv1d(1, 64, kernel_size=64, stride=8, padding=32, bias=False),
            nn.BatchNorm1d(64),
            nn.ELU(),
            nn.MaxPool1d(kernel_size=8, stride=8),
            nn.Conv1d(64, 128, kernel_size=16, stride=1, padding=8, bias=False),
            nn.BatchNorm1d(128),
            nn.ELU(),
            nn.AdaptiveAvgPool1d(1),
        )

        self.rnn = nn.GRU(
            256,
            128,
            num_layers=2,
            bidirectional=True,
            batch_first=True,
            dropout=0.3,
        )

        self.classifier = nn.Sequential(
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        batch_size, time_steps, channels, signal_len = x.shape
        x_flat = x.view(batch_size * time_steps, channels, signal_len)

        window = torch.hann_window(self.n_fft, device=x.device)
        stft = torch.stft(
            x_flat.squeeze(1),
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            window=window,
            return_complex=True,
            center=True,
        )
        mag = (torch.abs(stft) + 1e-8).log().unsqueeze(1)
        mag = mag[:, :, :128, :]

        spec_fea = self.spec_stem(mag)
        spec_fea = self.spec_stage(spec_fea).flatten(1)

        raw_fea = self.raw_branch(x_flat).flatten(1)
        combined_fea = torch.cat([spec_fea, raw_fea], dim=1)
        combined_fea = combined_fea.view(batch_size, time_steps, -1)

        rnn_out, _ = self.rnn(combined_fea)
        mid_idx = time_steps // 2
        return self.classifier(rnn_out[:, mid_idx, :])
