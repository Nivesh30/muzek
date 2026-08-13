"""Orchestrates a full analysis: load audio -> segment structure -> extract
rhythmic/harmonic/timbral features per segment -> map each segment to a
color -> persist the breakdown to the catalog. The audio itself is discarded
once analysis finishes; nothing but derived numbers ever reaches the catalog.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from . import audio as audio_mod
from .catalog import db
from .color.mapping import DEFAULT_ALGORITHM, map_features_to_color
from .features.chords import estimate_progression
from .features.harmony import analyze_harmony, segment_harmony
from .features.rhythm import analyze_rhythm, segment_rhythm
from .features.structure import segment_structure
from .features.timbre import analyze_timbre, segment_timbre


def analyze_song(
    path: str,
    conn: sqlite3.Connection,
    title: str | None = None,
    artist_hint: str | None = None,
    color_algorithm: str = DEFAULT_ALGORITHM,
    reanalyze: bool = False,
) -> dict:
    loaded = audio_mod.load_audio(path)

    existing = db.find_song_by_hash(conn, loaded.content_hash)
    if existing is not None:
        if not reanalyze:
            return db.get_breakdown(conn, existing["id"])
        db.delete_song(conn, existing["id"])

    rhythm_profile = analyze_rhythm(loaded.y, loaded.sr)
    harmony_profile = analyze_harmony(loaded.y, loaded.sr)
    timbre_profile = analyze_timbre(loaded.y, loaded.sr)
    sections = segment_structure(
        loaded.y, loaded.sr, loaded.duration_seconds, rhythm_profile.beat_frames
    )

    song_id = db.insert_song(
        conn,
        content_hash=loaded.content_hash,
        title=title,
        artist_hint=artist_hint,
        duration_seconds=loaded.duration_seconds,
        sample_rate=loaded.sr,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )

    for section in sections:
        segment_id = db.insert_segment(
            conn, song_id, section.index, section.start, section.end, section.label
        )

        features = {
            **segment_rhythm(rhythm_profile, section.start, section.end),
            **segment_harmony(harmony_profile, section.start, section.end),
            **segment_timbre(timbre_profile, section.start, section.end),
        }
        features["chord_progression"] = estimate_progression(
            harmony_profile, rhythm_profile.beat_times, section.start, section.end
        )
        db.insert_segment_features(conn, segment_id, features)

        color = map_features_to_color(features, algorithm_version=color_algorithm)
        db.insert_segment_color(conn, segment_id, color)

    return db.get_breakdown(conn, song_id)
