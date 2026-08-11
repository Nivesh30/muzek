"""Cross-song similarity: compares cataloged pattern breakdowns to find songs
with similar harmonic/rhythmic/timbral character. Never touches audio -- it
only aggregates the same per-segment features already in the catalog.
"""

from __future__ import annotations

import json

import numpy as np

# Same normalization scales used to calibrate the color mapping (see
# color/mapping.py) -- reused here so "similar" means similar on the same
# terms the colors are built from, not an arbitrary second scale.
_SCALES = {
    "energy_mean": 0.35,
    "spectral_centroid_mean": 2500.0,
    "tempo_bpm": 150.0,
    "onset_density": 8.0,
}


def _weighted_mean(segments: list[dict], key: str) -> float:
    total_weight = sum(seg["duration"] for seg in segments) or 1.0
    return sum(seg[key] * seg["duration"] for seg in segments) / total_weight


def build_song_vector(segments: list[dict]) -> np.ndarray | None:
    """Duration-weighted song-level summary: a scalar block (energy, brightness,
    tempo, onset density, each scaled to roughly 0-1) concatenated with a
    duration-weighted, L2-normalized average chroma vector (the song's overall
    harmonic "shape", independent of how loud it is).
    """
    if not segments:
        return None

    scalar_block = np.array(
        [_weighted_mean(segments, key) / scale for key, scale in _SCALES.items()]
    )

    total_weight = sum(seg["duration"] for seg in segments) or 1.0
    chroma_sum = np.zeros(12)
    for seg in segments:
        chroma = np.array(json.loads(seg["chroma_mean_json"]))
        chroma_sum += chroma * seg["duration"]
    chroma_mean = chroma_sum / total_weight
    norm = np.linalg.norm(chroma_mean)
    chroma_shape = chroma_mean / norm if norm > 0 else chroma_mean

    return np.concatenate([scalar_block, chroma_shape])


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def rank_similar(
    target_id: int, vectors_by_song: dict[int, np.ndarray], limit: int = 5
) -> list[tuple[int, float]]:
    target_vec = vectors_by_song.get(target_id)
    if target_vec is None:
        return []

    scored = [
        (song_id, cosine_similarity(target_vec, vec))
        for song_id, vec in vectors_by_song.items()
        if song_id != target_id
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]
