"""Audio loading. The waveform lives only in memory for the duration of analysis
and is never written to the catalog -- only derived features are persisted."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import librosa
import numpy as np


@dataclass
class LoadedAudio:
    y: np.ndarray
    sr: int
    duration_seconds: float
    content_hash: str


def load_audio(path: str, mono: bool = True, sr: int | None = 22050) -> LoadedAudio:
    """Load an audio file into memory for analysis.

    content_hash identifies the song for catalog dedup/lookup without storing
    the audio itself -- it's a hash of the decoded samples, not the source file.
    """
    y, sr = librosa.load(path, sr=sr, mono=mono)
    duration = librosa.get_duration(y=y, sr=sr)
    content_hash = hashlib.sha256(np.ascontiguousarray(y).tobytes()).hexdigest()
    return LoadedAudio(y=y, sr=sr, duration_seconds=duration, content_hash=content_hash)
