"""Feature -> color algorithms.

Each algorithm is a pure function from a merged segment-feature dict to an
HSL color, registered under a version string. Colors are cataloged alongside
their algorithm_version so multiple color mappings can coexist for the same
segment and be compared later.
"""

from __future__ import annotations

import colorsys
import math

Color = dict  # {algorithm_version, hue, saturation, lightness, hex}


def _to_hex(hue_deg: float, saturation: float, lightness: float) -> str:
    r, g, b = colorsys.hls_to_rgb((hue_deg % 360) / 360.0, lightness, saturation)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _chroma_hue(chroma_mean: list[float]) -> float | None:
    """Weighted circular mean of the 12 pitch classes, placed on the same
    30-degrees-per-semitone wheel as the discrete key mapping. Unlike picking
    a single best-fit key, this is continuous in the chroma vector: two
    segments with nearly identical harmonic content always get nearly
    identical hues, even if their discrete key estimates land on different
    (closely related) roots.
    """
    if not chroma_mean:
        return None
    x = sum(w * math.cos(math.radians(i * 30)) for i, w in enumerate(chroma_mean))
    y = sum(w * math.sin(math.radians(i * 30)) for i, w in enumerate(chroma_mean))
    if x == 0.0 and y == 0.0:
        return None
    return math.degrees(math.atan2(y, x)) % 360


def _v1_key_energy_brightness(features: dict) -> Color:
    """hue <- harmonic content (chroma wheel), saturation <- energy, lightness <- spectral brightness."""
    hue = _chroma_hue(features.get("chroma_mean", []))
    if hue is None:
        hue = (features.get("key_pitch_class", 0) * 30) % 360

    minor_weight = features.get("mode_minor_weight")
    if minor_weight is None:
        minor_weight = 1.0 if features.get("mode") == "minor" else 0.0
    hue = (hue + 200 * minor_weight) % 360

    # Scales calibrated against real songs (typical RMS energy ~0.05-0.4,
    # onset density ~1-8 events/sec, spectral centroid ~500-4000Hz at 22kHz sr).
    density_boost = min(features.get("onset_density", 0.0) / 15.0, 0.1)
    saturation = 0.3 + 0.6 * math.tanh(features.get("energy_mean", 0.0) / 0.35) + density_boost
    saturation = max(0.0, min(1.0, saturation))

    lightness = 0.15 + 0.65 * math.tanh(features.get("spectral_centroid_mean", 0.0) / 2500.0)
    lightness = max(0.05, min(0.95, lightness))

    return {
        "algorithm_version": "v1",
        "hue": hue,
        "saturation": saturation,
        "lightness": lightness,
        "hex": _to_hex(hue, saturation, lightness),
    }


ALGORITHMS = {
    "v1": _v1_key_energy_brightness,
}

DEFAULT_ALGORITHM = "v1"


def map_features_to_color(features: dict, algorithm_version: str = DEFAULT_ALGORITHM) -> Color:
    try:
        algorithm = ALGORITHMS[algorithm_version]
    except KeyError as exc:
        raise ValueError(f"Unknown color algorithm '{algorithm_version}'") from exc
    return algorithm(features)
