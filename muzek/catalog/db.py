"""SQLite catalog: stores derived patterns/breakdowns and colors, never audio.

Schema
------
songs            -- one row per analyzed song, keyed by a hash of its decoded
                     samples (content_hash), not by file path or raw audio.
segments         -- structural sections within a song (verse/chorus-shaped,
                     labeled A/B/C/... by similarity).
segment_features -- rhythmic/harmonic/timbral descriptors for each segment.
segment_colors   -- one row per (segment, color algorithm version), so
                     multiple color mappings can be cataloged and compared.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY,
    content_hash TEXT UNIQUE NOT NULL,
    title TEXT,
    artist_hint TEXT,
    duration_seconds REAL NOT NULL,
    sample_rate INTEGER NOT NULL,
    analyzed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    seg_index INTEGER NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    label TEXT NOT NULL,
    UNIQUE(song_id, seg_index)
);

CREATE TABLE IF NOT EXISTS segment_features (
    segment_id INTEGER PRIMARY KEY REFERENCES segments(id) ON DELETE CASCADE,
    tempo_bpm REAL,
    onset_density REAL,
    key_pitch_class INTEGER,
    key_name TEXT,
    mode TEXT,
    key_confidence REAL,
    chroma_mean_json TEXT,
    energy_mean REAL,
    energy_std REAL,
    spectral_centroid_mean REAL,
    spectral_bandwidth_mean REAL,
    mfcc_mean_json TEXT
);

CREATE TABLE IF NOT EXISTS segment_colors (
    id INTEGER PRIMARY KEY,
    segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    algorithm_version TEXT NOT NULL,
    hue REAL NOT NULL,
    saturation REAL NOT NULL,
    lightness REAL NOT NULL,
    hex TEXT NOT NULL,
    UNIQUE(segment_id, algorithm_version)
);

CREATE INDEX IF NOT EXISTS idx_segments_song ON segments(song_id);
CREATE INDEX IF NOT EXISTS idx_colors_segment ON segment_colors(segment_id);
"""


@contextmanager
def connect(db_path: str | Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def find_song_by_hash(conn: sqlite3.Connection, content_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM songs WHERE content_hash = ?", (content_hash,)
    ).fetchone()


def insert_song(
    conn: sqlite3.Connection,
    content_hash: str,
    title: str | None,
    artist_hint: str | None,
    duration_seconds: float,
    sample_rate: int,
    analyzed_at: str,
) -> int:
    cur = conn.execute(
        """INSERT INTO songs (content_hash, title, artist_hint, duration_seconds, sample_rate, analyzed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (content_hash, title, artist_hint, duration_seconds, sample_rate, analyzed_at),
    )
    return int(cur.lastrowid)


def delete_song(conn: sqlite3.Connection, song_id: int) -> None:
    conn.execute("DELETE FROM songs WHERE id = ?", (song_id,))


def insert_segment(
    conn: sqlite3.Connection, song_id: int, seg_index: int, start: float, end: float, label: str
) -> int:
    cur = conn.execute(
        """INSERT INTO segments (song_id, seg_index, start_time, end_time, label)
           VALUES (?, ?, ?, ?, ?)""",
        (song_id, seg_index, start, end, label),
    )
    return int(cur.lastrowid)


def insert_segment_features(conn: sqlite3.Connection, segment_id: int, features: dict) -> None:
    conn.execute(
        """INSERT INTO segment_features (
            segment_id, tempo_bpm, onset_density, key_pitch_class, key_name, mode,
            key_confidence, chroma_mean_json, energy_mean, energy_std,
            spectral_centroid_mean, spectral_bandwidth_mean, mfcc_mean_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            segment_id,
            features.get("tempo_bpm"),
            features.get("onset_density"),
            features.get("key_pitch_class"),
            features.get("key_name"),
            features.get("mode"),
            features.get("key_confidence"),
            json.dumps(features.get("chroma_mean", [])),
            features.get("energy_mean"),
            features.get("energy_std"),
            features.get("spectral_centroid_mean"),
            features.get("spectral_bandwidth_mean"),
            json.dumps(features.get("mfcc_mean", [])),
        ),
    )


def insert_segment_color(conn: sqlite3.Connection, segment_id: int, color: dict) -> None:
    conn.execute(
        """INSERT INTO segment_colors (segment_id, algorithm_version, hue, saturation, lightness, hex)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(segment_id, algorithm_version) DO UPDATE SET
             hue=excluded.hue, saturation=excluded.saturation,
             lightness=excluded.lightness, hex=excluded.hex""",
        (
            segment_id,
            color["algorithm_version"],
            color["hue"],
            color["saturation"],
            color["lightness"],
            color["hex"],
        ),
    )


def list_songs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM songs ORDER BY analyzed_at DESC").fetchall()


def get_all_segment_features(conn: sqlite3.Connection) -> dict[int, list[dict]]:
    """All segments' durations + features, grouped by song_id.

    This is the raw material for cross-song similarity: each segment's
    duration (used as a similarity weight -- a 60s chorus should count more
    than a 2s transition) alongside its rhythmic/harmonic/timbral features.
    """
    rows = conn.execute(
        """
        SELECT s.song_id, s.start_time, s.end_time, sf.*
        FROM segments s
        JOIN segment_features sf ON sf.segment_id = s.id
        ORDER BY s.song_id, s.seg_index
        """
    ).fetchall()

    by_song: dict[int, list[dict]] = {}
    for row in rows:
        entry = dict(row)
        entry["duration"] = entry["end_time"] - entry["start_time"]
        by_song.setdefault(entry["song_id"], []).append(entry)
    return by_song


def get_signature_colors(conn: sqlite3.Connection) -> dict[int, str]:
    """Per song, the color of its longest segment -- a quick visual fingerprint
    for catalog list views, picked without needing to load the full breakdown."""
    rows = conn.execute(
        """
        SELECT s.song_id, sc.hex
        FROM segments s
        JOIN segment_colors sc ON sc.segment_id = s.id
        WHERE (s.end_time - s.start_time) = (
            SELECT MAX(s2.end_time - s2.start_time)
            FROM segments s2
            WHERE s2.song_id = s.song_id
        )
        GROUP BY s.song_id
        """
    ).fetchall()
    return {row["song_id"]: row["hex"] for row in rows}


def get_breakdown(conn: sqlite3.Connection, song_id: int) -> dict | None:
    song = conn.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
    if song is None:
        return None

    segments = conn.execute(
        "SELECT * FROM segments WHERE song_id = ? ORDER BY seg_index", (song_id,)
    ).fetchall()

    breakdown_segments = []
    for seg in segments:
        features = conn.execute(
            "SELECT * FROM segment_features WHERE segment_id = ?", (seg["id"],)
        ).fetchone()
        colors = conn.execute(
            "SELECT * FROM segment_colors WHERE segment_id = ?", (seg["id"],)
        ).fetchall()
        breakdown_segments.append(
            {
                "index": seg["seg_index"],
                "start": seg["start_time"],
                "end": seg["end_time"],
                "label": seg["label"],
                "features": dict(features) if features else None,
                "colors": [dict(c) for c in colors],
            }
        )

    return {"song": dict(song), "segments": breakdown_segments}
