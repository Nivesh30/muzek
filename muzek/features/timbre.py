"""Timbral pattern extraction: brightness, energy dynamics, texture (MFCC)."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np


@dataclass
class TimbreProfile:
    frame_times: np.ndarray
    rms: np.ndarray
    spectral_centroid: np.ndarray
    spectral_bandwidth: np.ndarray
    mfcc: np.ndarray  # shape (n_mfcc, n_frames)


def analyze_timbre(y: np.ndarray, sr: int, n_mfcc: int = 13) -> TimbreProfile:
    rms = librosa.feature.rms(y=y)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    return TimbreProfile(
        frame_times=frame_times,
        rms=rms,
        spectral_centroid=centroid,
        spectral_bandwidth=bandwidth,
        mfcc=mfcc,
    )


def segment_timbre(profile: TimbreProfile, start: float, end: float) -> dict:
    mask = (profile.frame_times >= start) & (profile.frame_times < end)
    if not np.any(mask):
        mask = np.ones_like(profile.frame_times, dtype=bool)

    rms = profile.rms[mask]
    centroid = profile.spectral_centroid[mask]
    bandwidth = profile.spectral_bandwidth[mask]
    mfcc = profile.mfcc[:, mask]

    return {
        "energy_mean": float(np.mean(rms)),
        "energy_std": float(np.std(rms)),
        "spectral_centroid_mean": float(np.mean(centroid)),
        "spectral_bandwidth_mean": float(np.mean(bandwidth)),
        "mfcc_mean": np.mean(mfcc, axis=1).tolist(),
    }
