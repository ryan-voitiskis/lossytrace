"""Read bound train/selection PCM windows on demand for the finished-music study.

The caller supplies the verified construction manifest and split allocation.
Descriptions in this module check consistency; they cannot prove provenance.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re

import numpy as np
import soundfile as sf
import torch

from music_verdict_calibration import CASES
from music_verdict_candidate import WINDOW_SECONDS, analysis_intervals, frontend
from music_verdict_training import SelectionFile, valid_group


@dataclass(frozen=True)
class PCMCase:
    group: str
    source_id: str  # Identifies the common base mix, including any pre-encode processing.
    partition: str
    state: str
    condition: str
    path: Path
    sha256: str
    rate: int
    channels: int
    bits: int
    frames: int

    def __post_init__(self):
        valid_group(self.group)
        valid_group(self.source_id)
        if self.partition not in ("train", "selection") or (self.state, self.condition) not in CASES:
            raise ValueError("invalid PCM case allocation or recipe")
        if not isinstance(self.sha256, str) or not re.fullmatch("[0-9a-f]{64}", self.sha256):
            raise ValueError("expected a complete file commitment")
        if type(self.channels) is not int or self.channels not in (1, 2):
            raise ValueError("unsupported channel count")
        if type(self.bits) is not int or self.bits not in (16, 24):
            raise ValueError("unsupported PCM depth")
        analysis_intervals(self.frames, self.rate)

    @contextmanager
    def open(self):
        # Hash and decode the very same open file, even if its pathname is replaced.
        with self.path.open("rb") as raw:
            before = os.fstat(raw.fileno())
            if hashlib.file_digest(raw, "sha256").hexdigest() != self.sha256:
                raise ValueError("bound PCM bytes changed")
            raw.seek(0)
            with sf.SoundFile(raw) as stream:
                header = (stream.samplerate, stream.channels, stream.subtype, stream.frames)
                if (stream.format not in ("WAV", "WAVEX", "FLAC")
                        or header != (self.rate, self.channels, f"PCM_{self.bits}", self.frames)):
                    raise ValueError("PCM header differs from the bound case")
                yield stream
            after = os.fstat(raw.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError("bound PCM changed during reading")

    def selection_file(self):
        if self.partition != "selection":
            raise ValueError("model-selection file requires its own allocation")
        return SelectionFile(self.group, int(self.state != "baseline"), FileWindows(self))


def read_window(stream, first, end):
    if stream.seek(first) != first:
        raise ValueError("could not seek to the planned native frame")
    pcm = stream.read(end - first, dtype="float32", always_2d=True)
    if pcm.shape != (end - first, stream.channels):
        raise ValueError("incomplete native PCM window")
    return torch.from_numpy(np.ascontiguousarray(pcm.T))


@dataclass(frozen=True)
class FileWindows:
    case: PCMCase

    def __len__(self):
        return len(analysis_intervals(self.case.frames, self.case.rate))

    def __iter__(self):
        case = self.case
        with case.open() as stream:
            for first, end in analysis_intervals(case.frames, case.rate):
                yield frontend(read_window(stream, first, end).unsqueeze(0), case.rate)


@dataclass(frozen=True)
class FileQuartet:
    clean: PCMCase
    coded: PCMCase
    processed_clean: PCMCase
    processed_coded: PCMCase
    first_frame: int

    def __post_init__(self):
        clean, coded, processed, both = self.members
        if any(case.partition != "train" for case in self.members):
            raise ValueError("quartets require training inputs")
        if len({(c.group, c.source_id, c.rate, c.channels, c.frames) for c in self.members}) != 1:
            raise ValueError("quartet sources or native frame grids differ")
        if (clean.state != "baseline" or clean.condition != "identity"
                or coded.state == "baseline" or coded.condition != "identity"
                or processed.state != "baseline" or both.state != coded.state
                or processed.condition != both.condition):
            raise ValueError("incorrect state or nuisance in matched quartet")
        if (type(self.first_frame) is not int or self.first_frame < 0
                or self.first_frame + WINDOW_SECONDS * clean.rate > clean.frames):
            raise ValueError("training crop outside complete native frames")

    @property
    def members(self):
        return self.clean, self.coded, self.processed_clean, self.processed_coded

    @property
    def group(self):
        return self.clean.group

    @property
    def features(self):
        end = self.first_frame + WINDOW_SECONDS * self.clean.rate
        windows = []
        for case in self.members:
            with case.open() as stream:
                windows.append(read_window(stream, self.first_frame, end))
        return frontend(torch.stack(windows), self.clean.rate)
