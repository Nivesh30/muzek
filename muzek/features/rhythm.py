"""Rhythmic pattern extraction: tempo, beat grid, onset density."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np


@dataclass
class RhythmProfile:
    tempo_bpm: float
    beat_frames: np.ndarray
    beat_times: np.ndarray
    onset_envelope: np.ndarray
    onset_times: np.ndarray
    onset_event_times: np.ndarray


def analyze_rhythm(y: np.ndarray, sr: int) -> RhythmProfile:
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    onset_times = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr)
    onset_event_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_event_times = librosa.frames_to_time(onset_event_frames, sr=sr)
    tempo_bpm = float(np.atleast_1d(tempo)[0])
    return RhythmProfile(
        tempo_bpm=tempo_bpm,
        beat_frames=beat_frames,
        beat_times=beat_times,
        onset_envelope=onset_env,
        onset_times=onset_times,
        onset_event_times=onset_event_times,
    )


def segment_rhythm(profile: RhythmProfile, start: float, end: float) -> dict:
    """Rhythmic descriptors for a single [start, end) time window."""
    duration = max(end - start, 1e-6)
    events_in_window = profile.onset_event_times[
        (profile.onset_event_times >= start) & (profile.onset_event_times < end)
    ]
    onset_density = float(len(events_in_window)) / duration  # onsets per second

    beats_in_window = profile.beat_times[
        (profile.beat_times >= start) & (profile.beat_times < end)
    ]
    if len(beats_in_window) >= 2:
        local_tempo = float(60.0 / np.mean(np.diff(beats_in_window)))
    else:
        local_tempo = profile.tempo_bpm

    return {
        "tempo_bpm": local_tempo,
        "onset_density": onset_density,
        "beat_count": int(len(beats_in_window)),
    }
