"""Chord progression estimation: within each structural segment, estimates
one chord per beat-to-beat window (using the same beat grid as structure
segmentation) via template matching against major/minor triad profiles,
then collapses consecutive repeats into readable runs -- e.g. a 16-beat
segment might become "Am - F - C - G" rather than a chord per beat.

This is finer-grained than the single per-segment key estimate in
harmony.py: key is "what the section is centered on", chords are "what
actually changes, beat to beat, within it".
"""

from __future__ import annotations

import numpy as np

from .harmony import HarmonyProfile, PITCH_CLASSES

_CHORD_INTERVALS = {"maj": (0, 4, 7), "min": (0, 3, 7)}


def _build_templates() -> dict[tuple[int, str], np.ndarray]:
    templates = {}
    for root in range(12):
        for quality, intervals in _CHORD_INTERVALS.items():
            vec = np.zeros(12)
            for interval in intervals:
                vec[(root + interval) % 12] = 1.0
            templates[(root, quality)] = vec
    return templates


_TEMPLATES = _build_templates()


def _best_chord(chroma_vec: np.ndarray) -> tuple[str, float] | None:
    norm = np.linalg.norm(chroma_vec)
    if norm == 0:
        return None
    unit = chroma_vec / norm

    best_key, best_score = None, -1.0
    for key, template in _TEMPLATES.items():
        score = float(np.dot(unit, template) / np.linalg.norm(template))
        if score > best_score:
            best_key, best_score = key, score

    root, quality = best_key
    label = PITCH_CLASSES[root] + ("m" if quality == "min" else "")
    return label, best_score


def estimate_progression(
    harmony: HarmonyProfile, beat_times: np.ndarray, seg_start: float, seg_end: float
) -> list[dict]:
    """One merged-run entry per distinct chord within [seg_start, seg_end),
    windows bounded by the beat grid so chord changes land on musically
    plausible boundaries rather than arbitrary fixed-size chunks."""
    beats_inside = beat_times[(beat_times > seg_start) & (beat_times < seg_end)]
    boundaries = np.unique(np.concatenate([[seg_start], beats_inside, [seg_end]]))

    raw: list[dict] = []
    for lo, hi in zip(boundaries[:-1], boundaries[1:]):
        mask = (harmony.frame_times >= lo) & (harmony.frame_times < hi)
        window = harmony.chroma[:, mask]
        if window.shape[1] == 0:
            continue
        result = _best_chord(np.mean(window, axis=1))
        if result is None:
            continue
        label, confidence = result
        raw.append({"start": float(lo), "end": float(hi), "chord": label, "confidence": confidence})

    if not raw:
        return []

    merged = [dict(raw[0])]
    for entry in raw[1:]:
        if entry["chord"] == merged[-1]["chord"]:
            merged[-1]["end"] = entry["end"]
            merged[-1]["confidence"] = max(merged[-1]["confidence"], entry["confidence"])
        else:
            merged.append(dict(entry))
    return merged
