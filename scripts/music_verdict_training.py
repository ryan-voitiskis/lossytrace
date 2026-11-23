#!/usr/bin/env python3
"""Unfrozen training core, verified on generated tensors only.

No audio reader, checkpoint loading/persistence, evaluation-set API or verdicts.
This code does not authorize fitting on pilot/library data. Scientific execution
still needs the source gate, exact allocation, loader and execution freeze.
"""
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
import math
from typing import Protocol

import torch

from music_verdict_candidate import SEED, mean_window_logit, quartet_loss

LEARNING_RATE = 0.001
WEIGHT_DECAY = 0.0001
EFFECTIVE_QUARTETS = 16
MAX_EPOCHS = 20


@dataclass(frozen=True)
class Quartet:
    group: str
    features: torch.Tensor  # [4, 3, frequency, time], x/Cx/Nx/NCx


class SelectionWindows(Protocol):
    """Re-iterable sequence of native frontend windows for one file."""

    def __len__(self) -> int: ...

    def __iter__(self) -> Iterator[torch.Tensor]: ...


@dataclass(frozen=True)
class SelectionFile:
    group: str
    label: int
    windows: SelectionWindows  # each [1, 3, frequency, time]


def valid_group(group):
    if not isinstance(group, str) or not group.strip():
        raise ValueError('expected nonempty component identity')


def validate_features(features, batch):
    if (not isinstance(features, torch.Tensor) or features.dtype != torch.float32
            or features.ndim != 4 or features.shape[:2] != (batch, 3)
            or min(features.shape[2:]) < 16 or features.requires_grad
            or not torch.isfinite(features).all().item()):
        raise ValueError('expected finite float32 frontend tensor')


def validate_inputs(quartets, selection):
    if not quartets or not selection:
        raise ValueError('training and model-selection inputs required')
    for item in quartets:
        valid_group(item.group)
    for item in selection:
        valid_group(item.group)
        if type(item.label) is not int or item.label not in (0, 1):
            raise ValueError('selection label must be zero or one')
        if not 6 <= len(item.windows) <= 24:
            raise ValueError('selection file requires six through 24 windows')
    training_groups = {item.group for item in quartets}
    selection_groups = {item.group for item in selection}
    if training_groups & selection_groups:
        raise ValueError('training/model-selection component overlap')
    cells = Counter((item.group, item.label) for item in selection)
    if any((group, label) not in cells for group in selection_groups for label in (0, 1)):
        raise ValueError('every selection group requires both classes')
    # Reject invalid allocations before opening any lazily bound PCM inputs.
    for item in quartets:
        validate_features(item.features, 4)
    for item in selection:
        for window in item.windows:
            validate_features(window, 1)


def class_balanced_selection_bce(model, selection):
    """Whole-file mean logits, equal component mass, half per class.

    Accept model-selection files only through the caller's bound allocation.
    Identity strings determine weighting, never network inputs.
    """
    if not selection: raise ValueError('selection required')
    cells = Counter((item.group, item.label) for item in selection)
    groups = {item.group for item in selection}
    if any((g, y) not in cells for g in groups for y in (0, 1)):
        raise ValueError('selection groups need both classes')
    previous_training = model.training
    try:
        model.eval(); total = 0.0
        with torch.inference_mode():
            for item in selection:
                outputs = [model(window).reshape(-1) for window in item.windows]
                if any(value.numel() != 1 for value in outputs):
                    raise ValueError('expected one selection logit per window')
                logit = mean_window_logit(torch.cat(outputs))
                loss = max(logit, 0)-item.label*logit+math.log1p(math.exp(-abs(logit)))
                total += loss/(2*len(groups)*cells[item.group, item.label])
        if not math.isfinite(total): raise ValueError('nonfinite selection loss')
        return total
    finally:
        model.train(previous_training)


def fit_core(model, quartets, selection, *, epochs=MAX_EPOCHS, partition='train'):
    """Fixed-seed AdamW, one quartet at a time, gradients accumulated over 16.

    This is an implementation core, not a provenance verifier. Callers must bind
    exact samples/crops and certify the scientific gates before scientific use.
    A short final accumulation uses the same 16-quartet denominator, is not
    dropped or padded, and is recorded. No scheduler, early stop or retries.
    Selection chooses strict minimum BCE, retaining earliest epoch on ties.
    Restore the selected state only after all planned epochs finish successfully.
    """
    if partition != 'train': raise ValueError('fitting requires train partition')
    if type(epochs) is not int or not 1 <= epochs <= MAX_EPOCHS:
        raise ValueError('epochs outside fixed implementation limit')
    validate_inputs(quartets, selection)
    counts = Counter(item.group for item in quartets)
    weights = [1/(len(counts)*counts[item.group]) for item in quartets]
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    generator = torch.Generator(device='cpu').manual_seed(SEED)
    best_loss = math.inf; best_state = None; best_epoch = None; history = []
    updates = 0
    for epoch in range(1, epochs+1):
        order = torch.randperm(len(quartets), generator=generator).tolist()
        model.train(); optimizer.zero_grad(set_to_none=True)
        weighted_loss = 0.0; epoch_steps = 0
        for offset, index in enumerate(order):
            logits = model(quartets[index].features)
            if logits.shape != (4,): raise ValueError('expected four quartet logits')
            terms = quartet_loss(logits.reshape(1, 4))
            # Expected minibatch gradient equals the component-balanced objective.
            # The fixed denominator also handles a short final accumulation.
            scaled = terms['loss']*(len(quartets)*weights[index]/EFFECTIVE_QUARTETS)
            scaled.backward()
            weighted_loss += float(terms['loss'].detach())*weights[index]
            if (offset+1) % EFFECTIVE_QUARTETS == 0 or offset+1 == len(order):
                if any(p.grad is not None and not torch.isfinite(p.grad).all().item() for p in model.parameters()):
                    raise ValueError('nonfinite gradients; no optimizer retry')
                optimizer.step(); updates += 1; epoch_steps += 1
                if any(not torch.isfinite(p).all().item() for p in model.parameters()):
                    raise ValueError('nonfinite parameters; no partial checkpoint')
                optimizer.zero_grad(set_to_none=True)
        loss = class_balanced_selection_bce(model, selection)
        if loss < best_loss:
            best_loss = loss; best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        history.append({'epoch': epoch, 'online_training_loss': weighted_loss,
                        'selection_bce': loss, 'optimizer_steps': epoch_steps,
                        'last_accumulation_quartets': (len(order)-1) % EFFECTIVE_QUARTETS+1})
    model.load_state_dict(best_state); model.eval()
    return {'selected_epoch': best_epoch, 'selected_bce': best_loss,
            'history': history, 'optimizer_steps': updates,
            'training_groups': len(counts), 'selection_groups': len({x.group for x in selection}),
            'scientific_execution_authorized_by_this_function': False}
