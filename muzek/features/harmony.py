"""Harmonic pattern extraction: chroma content and key estimation.

Key estimation uses the Krumhansl-Schmuckler key-profile correlation method:
a segment's mean chroma vector is correlated against major/minor pitch-class
profiles rotated through all 12 roots, and the best match wins.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

PITCH_CLASSES = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
]

# Krumhansl-Kessler key profiles.
_MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)


@dataclass
class HarmonyProfile:
    chroma: np.ndarray  # shape (12, n_frames)
    frame_times: np.ndarray


def analyze_harmony(y: np.ndarray, sr: int) -> HarmonyProfile:
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    frame_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr)
    return HarmonyProfile(chroma=chroma, frame_times=frame_times)


def _best_per_mode(mean_chroma: np.ndarray) -> dict[str, tuple[str, float]]:
    """Best-matching root and score for each mode, independently."""
    best: dict[str, tuple[str, float]] = {}
    for mode, profile in (("major", _MAJOR_PROFILE), ("minor", _MINOR_PROFILE)):
        mode_best = ("C", -1.0)
        for root in range(12):
            rotated = np.roll(profile, root)
            score = float(np.corrcoef(mean_chroma, rotated)[0, 1])
            if score > mode_best[1]:
                mode_best = (PITCH_CLASSES[root], score)
        best[mode] = mode_best
    return best


def segment_harmony(profile: HarmonyProfile, start: float, end: float) -> dict:
    mask = (profile.frame_times >= start) & (profile.frame_times < end)
    window = profile.chroma[:, mask]
    if window.shape[1] == 0:
        mean_chroma = np.mean(profile.chroma, axis=1)
    else:
        mean_chroma = np.mean(window, axis=1)

    per_mode = _best_per_mode(mean_chroma)
    major_root, major_score = per_mode["major"]
    minor_root, minor_score = per_mode["minor"]

    if minor_score >= major_score:
        key_name, mode, confidence = minor_root, "minor", minor_score
    else:
        key_name, mode, confidence = major_root, "major", major_score
    key_pitch_class = PITCH_CLASSES.index(key_name)

    # Continuous major/minor blend for anything (like color) that shouldn't
    # snap discretely -- closely related keys (e.g. B minor / E minor share
    # nearly all pitch classes) can have near-tied scores, where a hard
    # argmax would flip unstably between two structurally identical segments.
    mode_minor_weight = 1.0 / (1.0 + np.exp(-8.0 * (minor_score - major_score)))

    return {
        "key_pitch_class": key_pitch_class,
        "key_name": key_name,
        "mode": mode,
        "key_confidence": max(0.0, min(1.0, (confidence + 1) / 2)),
        "mode_minor_weight": float(mode_minor_weight),
        "chroma_mean": mean_chroma.tolist(),
    }
