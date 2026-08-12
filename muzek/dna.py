"""Encodes a song's "DNA" -- each structural section becomes a short,
genetic-style codon capturing its key, mode, energy, brightness, and
rhythmic density. Strung together in order, a song's codons form its
"genome": a compact, readable fingerprint of how it moves from section to
section, built entirely from features already in the catalog.

Codon format: <key><mode><energy><brightness><rhythm>
  key        - pitch class name, e.g. "F#"
  mode       - "M" (major) or "m" (minor)
  energy     - L/M/H tier of energy_mean
  brightness - L/M/H tier of spectral_centroid_mean
  rhythm     - 1-4 tier of onset_density

Example: "F#mHM3" = F# minor, high energy, medium brightness, rhythm tier 3.

Tier thresholds reuse the same calibration scales as the color mapping
(color/mapping.py) so a song's DNA and its colors agree on what "high
energy" or "bright" means.
"""

from __future__ import annotations

ENERGY_SCALE = 0.35
BRIGHTNESS_SCALE = 2500.0
RHYTHM_BREAKPOINTS = (2.0, 4.0, 6.0)  # onset_density (/s) -> tier 1..4


def _tier_lmh(value: float, scale: float) -> str:
    if value < scale * 0.45:
        return "L"
    if value < scale * 1.0:
        return "M"
    return "H"


def _rhythm_tier(onset_density: float) -> int:
    for tier, breakpoint in enumerate(RHYTHM_BREAKPOINTS, start=1):
        if onset_density < breakpoint:
            return tier
    return len(RHYTHM_BREAKPOINTS) + 1


def encode_codon(features: dict) -> dict:
    """Encode one segment's features into a codon dict, including the
    human-readable `code` string and each decoded component."""
    key = features.get("key_name") or "C"
    mode = features.get("mode") or "major"
    mode_letter = "m" if mode == "minor" else "M"
    energy_tier = _tier_lmh(features.get("energy_mean", 0.0), ENERGY_SCALE)
    brightness_tier = _tier_lmh(features.get("spectral_centroid_mean", 0.0), BRIGHTNESS_SCALE)
    rhythm_tier = _rhythm_tier(features.get("onset_density", 0.0))

    code = f"{key}{mode_letter}{energy_tier}{brightness_tier}{rhythm_tier}"

    return {
        "code": code,
        "key": key,
        "mode": mode,
        "energy_tier": energy_tier,
        "brightness_tier": brightness_tier,
        "rhythm_tier": rhythm_tier,
    }


def build_genome(segments: list[dict]) -> list[dict]:
    """Codon per segment, in order -- a song's full genome."""
    return [encode_codon(seg.get("features") or {}) for seg in segments]
