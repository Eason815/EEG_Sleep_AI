import math

import torch
import torch.nn as nn
import torch.nn.functional as F


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
        out_length = int(math.ceil(in_length / self.stride))
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
        chunk_size=3000,
        dropout=0.5,
        n_filters_1=128,
        filter_size_1=50,
        filter_stride_1=6,
        pool_size_1=8,
        pool_stride_1=8,
        n_filters_1x3=128,
        filter_size_1x3=8,
        pool_size_2=4,
        pool_stride_2=4,
    ):
        super().__init__()
        self.conv1 = Conv1dBnReLU(1, n_filters_1, kernel_size=filter_size_1, stride=filter_stride_1)
        self.pool1 = nn.MaxPool1d(kernel_size=pool_size_1, stride=pool_stride_1)
        self.dropout1 = nn.Dropout(dropout)
        self.conv2_1 = Conv1dBnReLU(n_filters_1, n_filters_1x3, kernel_size=filter_size_1x3, stride=1)
        self.conv2_2 = Conv1dBnReLU(n_filters_1x3, n_filters_1x3, kernel_size=filter_size_1x3, stride=1)
        self.conv2_3 = Conv1dBnReLU(n_filters_1x3, n_filters_1x3, kernel_size=filter_size_1x3, stride=1)
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


class TinySleepNetRepro(nn.Module):
    def __init__(
        self,
        num_classes,
        chunk_size=3000,
        signal_dropout=0.5,
        n_filters_1=128,
        filter_size_1=50,
        filter_stride_1=6,
        pool_size_1=8,
        pool_stride_1=8,
        n_filters_1x3=128,
        filter_size_1x3=8,
        pool_size_2=4,
        pool_stride_2=4,
        rnn_hidden_size=128,
    ):
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

    def forward(self, x):
        batch_size, time_steps, channels, signal_len = x.shape
        x = x.view(batch_size * time_steps, channels, signal_len)
        features = self.feature_extractor(x)
        features = features.view(batch_size, time_steps, -1)
        sequence_output, _ = self.rnn(features)
        return self.classifier(sequence_output)
