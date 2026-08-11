"""Structural segmentation: split a song into sections and label repeated ones.

Chroma + MFCC frames are first synced to the beat grid (each beat's frames
averaged into one column) so cluster boundaries snap to actual beats instead
of landing mid-beat. Agglomerative clustering over that beat-synced feature
matrix then finds section boundaries (a standard music-structure-analysis
approach). Segments with similar mean feature vectors are given the same
letter label (A, B, C, ...), so a verse that repeats later in the song is
recognized as "the same piece".
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np


@dataclass
class Section:
    index: int
    start: float
    end: float
    label: str


def _num_segments(duration: float, target_seconds: float, min_segments: int, max_segments: int) -> int:
    estimate = round(duration / target_seconds)
    return int(np.clip(estimate, min_segments, max_segments))


def _label_by_similarity(mean_vectors: list[np.ndarray], threshold: float = 0.92) -> list[str]:
    labels: list[str] = []
    representatives: list[np.ndarray] = []
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for vec in mean_vectors:
        norm = np.linalg.norm(vec)
        unit = vec / norm if norm > 0 else vec
        best_idx, best_sim = -1, -1.0
        for idx, rep in enumerate(representatives):
            sim = float(np.dot(unit, rep))
            if sim > best_sim:
                best_idx, best_sim = idx, sim
        if best_sim >= threshold:
            labels.append(alphabet[best_idx % len(alphabet)])
        else:
            representatives.append(unit)
            labels.append(alphabet[(len(representatives) - 1) % len(alphabet)])

    return labels


def segment_structure(
    y: np.ndarray,
    sr: int,
    duration: float,
    beat_frames: np.ndarray,
    target_segment_seconds: float = 15.0,
    min_segments: int = 3,
    max_segments: int = 12,
) -> list[Section]:
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

    n_frames = min(chroma.shape[1], mfcc.shape[1])
    chroma, mfcc = chroma[:, :n_frames], mfcc[:, :n_frames]

    beat_frames = beat_frames[(beat_frames >= 0) & (beat_frames < n_frames)]
    # sync_frames are the beat-grid boundaries used to average frames into beats;
    # 0 and n_frames are always included so no audio at the ends is dropped.
    sync_frames = np.unique(np.concatenate([[0], beat_frames, [n_frames]]))

    if len(sync_frames) < 3:
        # Too few beats detected (e.g. very short or beatless audio) to be
        # useful as a clustering grid -- fall back to raw frames.
        sync_frames = np.arange(n_frames + 1)

    chroma_sync = librosa.util.sync(chroma, sync_frames[:-1], aggregate=np.mean)
    mfcc_sync = librosa.util.sync(mfcc, sync_frames[:-1], aggregate=np.mean)
    n_units = min(chroma_sync.shape[1], mfcc_sync.shape[1])
    chroma_sync, mfcc_sync = chroma_sync[:, :n_units], mfcc_sync[:, :n_units]
    unit_frames = sync_frames[: n_units + 1]

    def _normalize(feat: np.ndarray) -> np.ndarray:
        std = np.std(feat, axis=1, keepdims=True)
        std[std == 0] = 1.0
        return (feat - np.mean(feat, axis=1, keepdims=True)) / std

    stacked = np.vstack([_normalize(chroma_sync), _normalize(mfcc_sync)])

    k = _num_segments(duration, target_segment_seconds, min_segments, max_segments)
    k = min(k, n_units) if n_units > 0 else 1
    k = max(k, 1)

    if k == 1 or n_units < 2:
        boundary_units = np.array([0, n_units])
    else:
        boundary_units = librosa.segment.agglomerative(stacked, k)
        boundary_units = np.unique(np.concatenate([[0], boundary_units, [n_units]]))

    boundary_frames = unit_frames[boundary_units]
    boundary_times = librosa.frames_to_time(boundary_frames, sr=sr)
    boundary_times[-1] = duration

    mean_vectors = []
    for i in range(len(boundary_units) - 1):
        lo, hi = boundary_units[i], boundary_units[i + 1]
        window = stacked[:, lo:hi] if hi > lo else stacked[:, lo : lo + 1]
        mean_vectors.append(np.mean(window, axis=1))

    labels = _label_by_similarity(mean_vectors)

    sections = [
        Section(index=i, start=float(boundary_times[i]), end=float(boundary_times[i + 1]), label=labels[i])
        for i in range(len(labels))
    ]

    min_section_seconds = 0.5
    sections = [s for s in sections if s.end - s.start >= min_section_seconds]

    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    relabel: dict[str, str] = {}
    for i, section in enumerate(sections):
        section.index = i
        if section.label not in relabel:
            relabel[section.label] = alphabet[len(relabel) % len(alphabet)]
        section.label = relabel[section.label]

    return sections
