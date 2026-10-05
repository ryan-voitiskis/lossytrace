#!/usr/bin/env python3
"""Untrained music-verdict-v1 building blocks for synthetic verification only.

No file reader, checkpoint loader, training loop or public verdict is exposed.
Constants below are proposed execution bindings, not an execution authorization.
Real-audio work still requires the study's source and execution gates.
"""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

SAMPLE_RATES = (44_100, 48_000)
WINDOW_SECONDS = 4
MIN_FILE_SECONDS = 30
MAX_ANALYSIS_SECONDS = 120
MAX_WINDOWS = 24
MIN_WINDOWS = 6
N_FFT = 2048
HOP_LENGTH = 512
RMS_EPSILON = 1e-8
SEED = 20260927
CONSISTENCY_WEIGHT = 0.1
PARAMETER_CEILING = 300_000
CHANNELS = (16, 32, 64, 96)


def _rate(sample_rate: int) -> None:
    if type(sample_rate) is not int or sample_rate not in SAMPLE_RATES:
        raise ValueError("unsupported sample rate")


def analysis_intervals(total_frames: int, sample_rate: int) -> tuple[tuple[int, int], ...]:
    """Content-independent, half-open source-frame intervals; no fake padding.

    Use as many non-overlapping four-second windows as fit, capped at 24,
    with starts spaced across the available first 120 seconds. Integer floor
    arithmetic makes rounding independent of floating-point duration estimates.
    """
    _rate(sample_rate)
    if type(total_frames) is not int or total_frames < MIN_FILE_SECONDS * sample_rate:
        raise ValueError("unsupported duration: at least 30 complete seconds required")
    stop = min(total_frames, MAX_ANALYSIS_SECONDS * sample_rate)
    width = WINDOW_SECONDS * sample_rate
    count = min(MAX_WINDOWS, stop // width)
    if count < MIN_WINDOWS:
        raise ValueError("insufficient complete analysis windows")
    starts = tuple(i * (stop - width) // (count - 1) for i in range(count))
    return tuple((start, start + width) for start in starts)


def _finite_tensor(value: torch.Tensor, dimensions: int) -> None:
    if not isinstance(value, torch.Tensor) or value.ndim != dimensions:
        raise ValueError("invalid tensor shape")
    if value.dtype != torch.float32 or value.numel() == 0:
        raise ValueError("expected nonempty float32 tensor")
    if not torch.isfinite(value).all().item():
        raise ValueError("non-finite input is unsupported, not negative evidence")


def frontend(pcm: torch.Tensor, sample_rate: int) -> torch.Tensor:
    """[batch, mono/stereo, exactly four seconds] -> [batch, 3, frequency, time].

    RMS is joint across original input channels and time. Mid=(L+R)/2 and
    side=(L-R)/2 preserve anti-phase material. Mono has an exactly zero side.
    Use log1p(abs(STFT)) with periodic Hann and center=False: no waveform edge
    reflection/padding. The rate plane is 0 for 44.1 kHz and 1 for 48 kHz.
    """
    _rate(sample_rate)
    _finite_tensor(pcm, 3)
    if pcm.shape[1] not in (1, 2) or pcm.shape[2] != WINDOW_SECONDS * sample_rate:
        raise ValueError("expected mono/stereo complete four-second windows")
    # Scale before squaring to prevent finite inputs overflowing the RMS.
    peak = pcm.abs().amax(dim=(1, 2), keepdim=True).clamp_min(RMS_EPSILON)
    scaled = pcm / peak
    rms = scaled.square().mean(dim=(1, 2), keepdim=True).sqrt()
    # Equivalent to dividing by max(joint RMS, epsilon), without peak*rms overflow.
    normalized = scaled / torch.maximum(rms, RMS_EPSILON / peak)
    if pcm.shape[1] == 1:
        mid, side = normalized[:, 0], torch.zeros_like(normalized[:, 0])
    else:
        mid = (normalized[:, 0] + normalized[:, 1]) * 0.5
        side = (normalized[:, 0] - normalized[:, 1]) * 0.5
    ms = torch.stack((mid, side), dim=1)
    window = torch.hann_window(N_FFT, periodic=True, device=pcm.device, dtype=pcm.dtype)
    spectrum = torch.stft(ms.flatten(0, 1), n_fft=N_FFT, hop_length=HOP_LENGTH,
                          win_length=N_FFT, window=window, center=False,
                          normalized=False, onesided=True, return_complex=True)
    magnitude = torch.log1p(spectrum.abs()).reshape(pcm.shape[0], 2, spectrum.shape[-2], spectrum.shape[-1])
    rate_value = (sample_rate - SAMPLE_RATES[0]) / (SAMPLE_RATES[1] - SAMPLE_RATES[0])
    rate_plane = torch.full_like(magnitude[:, :1], rate_value)
    result = torch.cat((magnitude, rate_plane), dim=1)
    if not torch.isfinite(result).all().item():
        raise ValueError("non-finite frontend output")
    return result


class CompactCandidate(nn.Module):
    """Four two-convolution blocks, GroupNorm, GELU and average pooling."""

    def __init__(self):
        super().__init__()
        layers = []
        incoming = 3
        for outgoing in CHANNELS:
            for _ in range(2):
                layers.extend((nn.Conv2d(incoming, outgoing, 3, padding=1, bias=False),
                               nn.GroupNorm(4, outgoing, eps=1e-5), nn.GELU()))
                incoming = outgoing
            layers.append(nn.AvgPool2d(2))
        self.blocks = nn.Sequential(*layers)
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(),
                                  nn.Linear(CHANNELS[-1], 64), nn.GELU(), nn.Linear(64, 1))
        if sum(parameter.numel() for parameter in self.parameters()) > PARAMETER_CEILING:
            raise ValueError("candidate exceeds prespecified parameter ceiling")

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        _finite_tensor(features, 4)
        if features.shape[1] != 3 or min(features.shape[-2:]) < 16:
            raise ValueError("invalid frontend dimensions")
        result = self.head(self.blocks(features)).squeeze(-1)
        if not torch.isfinite(result).all().item():
            raise ValueError("non-finite candidate output")
        return result


def build_candidate() -> CompactCandidate:
    """Fixed-seed CPU initialization without perturbing the caller's CPU RNG."""
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(SEED)
        return CompactCandidate()


def quartet_loss(logits: torch.Tensor) -> dict[str, torch.Tensor]:
    """Columns are x, C(x), N(x), N(C(x)); no reference is needed at inference."""
    _finite_tensor(logits, 2)
    if logits.shape[1] != 4:
        raise ValueError("expected one logit per matched quartet member")
    labels = logits.new_tensor([0.0, 1.0, 0.0, 1.0]).expand_as(logits)
    bce = F.binary_cross_entropy_with_logits(logits, labels, reduction="mean")
    consistency = torch.stack((logits[:, 0] - logits[:, 2],
                               logits[:, 1] - logits[:, 3]), dim=1).square().mean()
    loss = bce + CONSISTENCY_WEIGHT * consistency
    if not torch.isfinite(loss).item():
        raise ValueError("non-finite loss")
    return {"loss": loss, "bce": bce, "consistency": consistency}


def mean_window_logit(logits: torch.Tensor) -> float:
    """Equal-window logit mean, never a mean of probabilities or a verdict."""
    _finite_tensor(logits, 1)
    if not MIN_WINDOWS <= logits.numel() <= MAX_WINDOWS:
        raise ValueError("invalid number of analysis windows")
    # Float64 accumulation avoids overflow and unnecessary float32 sum error.
    result = float(logits.double().mean().item())
    if not math.isfinite(result):
        raise ValueError("non-finite file score")
    return result
