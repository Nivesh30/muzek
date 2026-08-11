from __future__ import annotations

import json
from pathlib import Path

import click

from .catalog import db
from .pipeline import analyze_song


@click.group()
def main() -> None:
    """muzek: break songs into patterns and map them to color."""


@main.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--title", default=None, help="Song title to record alongside the breakdown.")
@click.option("--artist", "artist_hint", default=None, help="Artist name to record alongside the breakdown.")
@click.option("--db-path", "db_path", default="catalog.sqlite", show_default=True)
@click.option("--algorithm", "color_algorithm", default="v1", show_default=True, help="Color mapping algorithm version.")
@click.option("--reanalyze", is_flag=True, help="Re-run analysis even if this song's content hash is already cataloged.")
@click.option("--json", "as_json", is_flag=True, help="Print the resulting breakdown as JSON.")
def analyze(path: str, title: str | None, artist_hint: str | None, db_path: str, color_algorithm: str, reanalyze: bool, as_json: bool) -> None:
    """Analyze PATH and store its pattern breakdown in the catalog. The audio is never stored."""
    with db.connect(db_path) as conn:
        db.init_schema(conn)
        breakdown = analyze_song(
            path,
            conn,
            title=title,
            artist_hint=artist_hint,
            color_algorithm=color_algorithm,
            reanalyze=reanalyze,
        )

    if as_json:
        click.echo(json.dumps(breakdown, indent=2))
        return

    song = breakdown["song"]
    click.echo(f"Song #{song['id']}  {song['title'] or Path(path).name}  ({song['duration_seconds']:.1f}s)")
    for seg in breakdown["segments"]:
        color = seg["colors"][0]["hex"] if seg["colors"] else "?"
        feat = seg["features"] or {}
        click.echo(
            f"  [{seg['label']}] {seg['start']:6.1f}s - {seg['end']:6.1f}s  "
            f"key={feat.get('key_name')}{feat.get('mode', '')[:1]} "
            f"tempo={feat.get('tempo_bpm', 0):.0f}bpm  color={color}"
        )


@main.command("list")
@click.option("--db-path", "db_path", default="catalog.sqlite", show_default=True)
def list_songs_cmd(db_path: str) -> None:
    """List all songs in the catalog."""
    with db.connect(db_path) as conn:
        db.init_schema(conn)
        for song in db.list_songs(conn):
            click.echo(f"#{song['id']}  {song['title'] or '(untitled)'}  {song['duration_seconds']:.1f}s  {song['analyzed_at']}")


@main.command()
@click.argument("song_id", type=int)
@click.option("--db-path", "db_path", default="catalog.sqlite", show_default=True)
def show(song_id: int, db_path: str) -> None:
    """Show the full stored breakdown for a song by its catalog id."""
    with db.connect(db_path) as conn:
        db.init_schema(conn)
        breakdown = db.get_breakdown(conn, song_id)
    if breakdown is None:
        raise click.ClickException(f"No song with id {song_id}")
    click.echo(json.dumps(breakdown, indent=2))


@main.command()
@click.option("--db-path", "db_path", default="catalog.sqlite", show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=5000, show_default=True)
def serve(db_path: str, host: str, port: int) -> None:
    """Start a local web UI for browsing the catalog's color breakdowns."""
    from .web.app import create_app

    app = create_app(db_path)
    click.echo(f"Serving catalog '{db_path}' at http://{host}:{port}")
    app.run(host=host, port=port, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
