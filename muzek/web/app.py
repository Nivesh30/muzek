"""Local Flask app for browsing the catalog: song list + per-song color timeline.

Reads only from the SQLite catalog (patterns/colors) -- never touches or
serves the original audio files. Uploaded songs are written to a temp file
just long enough to run analysis, then deleted immediately afterward.
"""

from __future__ import annotations

import os
import tempfile

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from ..catalog import db
from ..dna import encode_codon
from ..pipeline import analyze_song
from ..similarity import build_song_vector, cosine_similarity, rank_similar


def _with_codons(breakdown: dict) -> dict:
    for segment in breakdown["segments"]:
        segment["codon"] = encode_codon(segment.get("features") or {})
    return breakdown

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100MB


def create_app(db_path: str) -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/songs")
    def api_songs():
        with db.connect(app.config["DB_PATH"]) as conn:
            db.init_schema(conn)
            songs = db.list_songs(conn)
            swatches = db.get_signature_colors(conn)
            result = []
            for song in songs:
                song_dict = dict(song)
                song_dict["swatch"] = swatches.get(song["id"])
                result.append(song_dict)
            return jsonify(result)

    @app.route("/api/songs/<int:song_id>")
    def api_song(song_id: int):
        with db.connect(app.config["DB_PATH"]) as conn:
            db.init_schema(conn)
            breakdown = db.get_breakdown(conn, song_id)
        if breakdown is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(_with_codons(breakdown))

    @app.route("/api/songs/<int:song_id>/similar")
    def api_similar(song_id: int):
        limit = request.args.get("limit", default=6, type=int)
        with db.connect(app.config["DB_PATH"]) as conn:
            db.init_schema(conn)
            segments_by_song = db.get_all_segment_features(conn)
            vectors = {
                sid: vec
                for sid, segs in segments_by_song.items()
                if (vec := build_song_vector(segs)) is not None
            }
            ranked = rank_similar(song_id, vectors, limit=limit)

            songs_by_id = {s["id"]: dict(s) for s in db.list_songs(conn)}
            swatches = db.get_signature_colors(conn)

        result = [
            {
                "song_id": sid,
                "title": songs_by_id[sid]["title"],
                "duration_seconds": songs_by_id[sid]["duration_seconds"],
                "similarity": score,
                "swatch": swatches.get(sid),
            }
            for sid, score in ranked
            if sid in songs_by_id
        ]
        return jsonify(result)

    @app.route("/api/similarity-matrix")
    def api_similarity_matrix():
        raw_ids = request.args.get("ids", "")
        ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        if len(ids) < 2:
            return jsonify({"pairs": []})

        with db.connect(app.config["DB_PATH"]) as conn:
            db.init_schema(conn)
            segments_by_song = db.get_all_segment_features(conn)
            vectors = {
                sid: vec
                for sid in ids
                if sid in segments_by_song and (vec := build_song_vector(segments_by_song[sid])) is not None
            }

        pairs = []
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                if a in vectors and b in vectors:
                    pairs.append({"a": a, "b": b, "similarity": cosine_similarity(vectors[a], vectors[b])})

        return jsonify({"pairs": pairs})

    @app.route("/api/analyze", methods=["POST"])
    def api_analyze():
        upload = request.files.get("file")
        if upload is None or upload.filename == "":
            return jsonify({"error": "No file uploaded"}), 400

        title = (request.form.get("title") or "").strip() or None
        artist_hint = (request.form.get("artist") or "").strip() or None

        suffix = os.path.splitext(secure_filename(upload.filename))[1] or ".audio"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            upload.save(tmp_path)
            with db.connect(app.config["DB_PATH"]) as conn:
                db.init_schema(conn)
                breakdown = analyze_song(
                    tmp_path, conn, title=title, artist_hint=artist_hint
                )
        except Exception as exc:  # noqa: BLE001 - surface analysis failures to the UI
            return jsonify({"error": f"Analysis failed: {exc}"}), 400
        finally:
            os.remove(tmp_path)

        return jsonify(_with_codons(breakdown)), 201

    return app
