import os
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta


DB_PATH = os.environ.get(
    "SOUNDRADAR_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.db"),
)


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


@contextmanager
def connection():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_column(conn, table, definition):
    column = definition.split()[0]
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with connection() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                deezer_id TEXT,
                date_added TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS releases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                release_date TEXT NOT NULL,
                deezer_id TEXT NOT NULL UNIQUE,
                link TEXT NOT NULL,
                cover_url TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                date_added TEXT NOT NULL,
                FOREIGN KEY (artist_id) REFERENCES artists (id) ON DELETE CASCADE
            )
            """
        )

        _ensure_column(conn, "artists", "picture_url TEXT")
        _ensure_column(conn, "artists", "match_status TEXT NOT NULL DEFAULT 'unresolved'")
        _ensure_column(conn, "artists", "last_checked_at TEXT")
        _ensure_column(conn, "artists", "favorite INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "artists", "library_track_count INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "artists", "library_album_count INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            "UPDATE artists SET match_status = 'confirmed' "
            "WHERE deezer_id IS NOT NULL AND match_status = 'unresolved'"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_releases_date ON releases(release_date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_releases_status_date ON releases(status, release_date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_releases_artist ON releases(artist_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                release_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                deezer_id TEXT NOT NULL UNIQUE,
                link TEXT NOT NULL,
                preview_url TEXT,
                duration INTEGER NOT NULL DEFAULT 0,
                provider_rank INTEGER NOT NULL DEFAULT 0,
                track_position INTEGER NOT NULL DEFAULT 0,
                disk_number INTEGER NOT NULL DEFAULT 1,
                explicit_lyrics INTEGER NOT NULL DEFAULT 0,
                date_added TEXT NOT NULL,
                FOREIGN KEY (release_id) REFERENCES releases (id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS track_feedback (
                track_id INTEGER PRIMARY KEY,
                feedback TEXT NOT NULL CHECK(feedback IN ('love', 'not_for_me', 'already_heard')),
                updated_at TEXT NOT NULL,
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS radar_impressions (
                track_id INTEGER PRIMARY KEY,
                shown_at TEXT NOT NULL,
                show_count INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendation_scores (
                track_id INTEGER PRIMARY KEY,
                score REAL NOT NULL,
                components TEXT NOT NULL,
                reasons TEXT NOT NULL,
                calculated_at TEXT NOT NULL,
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_release ON tracks(release_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_value ON track_feedback(feedback)")


def upsert_artist(name, deezer_id=None, picture_url=None, confirmed=False):
    clean_name = " ".join((name or "").split())
    if not clean_name:
        raise ValueError("Artist name is required")

    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM artists WHERE name = ? COLLATE NOCASE", (clean_name,)
        ).fetchone()
        if row:
            updates = []
            params = []
            if deezer_id and (not row["deezer_id"] or confirmed):
                updates.append("deezer_id = ?")
                params.append(str(deezer_id))
            if picture_url:
                updates.append("picture_url = ?")
                params.append(picture_url)
            if confirmed and deezer_id:
                updates.append("match_status = 'confirmed'")
            if updates:
                params.append(row["id"])
                conn.execute(f"UPDATE artists SET {', '.join(updates)} WHERE id = ?", params)
            return {"id": row["id"], "created": False}

        cursor = conn.execute(
            """
            INSERT INTO artists (name, deezer_id, picture_url, match_status, date_added)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                clean_name,
                str(deezer_id) if deezer_id else None,
                picture_url,
                "confirmed" if confirmed and deezer_id else "unresolved",
                _now(),
            ),
        )
        return {"id": cursor.lastrowid, "created": True}


def add_artist(name, deezer_id=None):
    return upsert_artist(name, deezer_id, confirmed=bool(deezer_id))["id"]


def get_artists(search=None, limit=1000):
    query = """
        SELECT a.*,
               COUNT(r.id) AS release_count,
               SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) AS pending_count
        FROM artists a
        LEFT JOIN releases r ON r.artist_id = a.id
    """
    params = []
    if search:
        query += " WHERE a.name LIKE ? ESCAPE '\\'"
        params.append(f"%{_escape_like(search)}%")
    query += " GROUP BY a.id ORDER BY a.name COLLATE NOCASE ASC LIMIT ?"
    params.append(max(1, min(int(limit), 2000)))
    with connection() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def set_artist_favorite(artist_id, favorite):
    with connection() as conn:
        cursor = conn.execute(
            "UPDATE artists SET favorite = ? WHERE id = ?",
            (1 if favorite else 0, artist_id),
        )
        return cursor.rowcount > 0


def update_artist_library_counts(artist_id, track_count=0, album_count=0):
    with connection() as conn:
        cursor = conn.execute(
            """
            UPDATE artists
            SET library_track_count = ?, library_album_count = ?
            WHERE id = ?
            """,
            (max(0, int(track_count)), max(0, int(album_count)), artist_id),
        )
        return cursor.rowcount > 0


def reset_artist_library_counts():
    with connection() as conn:
        conn.execute(
            "UPDATE artists SET library_track_count = 0, library_album_count = 0"
        )


def remove_artist(artist_id):
    with connection() as conn:
        cursor = conn.execute("DELETE FROM artists WHERE id = ?", (artist_id,))
        return cursor.rowcount > 0


def add_release(artist_id, title, type, release_date, deezer_id, link, cover_url, status="pending"):
    return upsert_release(
        artist_id, title, type, release_date, deezer_id, link, cover_url, status
    )["created"]


def upsert_release(artist_id, title, type, release_date, deezer_id, link, cover_url, status="pending"):
    with connection() as conn:
        duplicate = conn.execute(
            """
            SELECT id FROM releases
            WHERE artist_id = ? AND lower(trim(title)) = lower(trim(?)) AND release_date = ?
            LIMIT 1
            """,
            (artist_id, title, release_date),
        ).fetchone()
        if duplicate:
            return {"id": duplicate["id"], "created": False}
        try:
            cursor = conn.execute(
                """
                INSERT INTO releases
                    (artist_id, title, type, release_date, deezer_id, link, cover_url, status, date_added)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (artist_id, title, type, release_date, deezer_id, link, cover_url, status, _now()),
            )
            return {"id": cursor.lastrowid, "created": True}
        except sqlite3.IntegrityError:
            existing = conn.execute(
                "SELECT id FROM releases WHERE deezer_id = ?", (str(deezer_id),)
            ).fetchone()
            return {"id": existing["id"] if existing else None, "created": False}


def release_has_tracks(release_id):
    with connection() as conn:
        return conn.execute(
            "SELECT 1 FROM tracks WHERE release_id = ? LIMIT 1", (release_id,)
        ).fetchone() is not None


def add_track(
    release_id,
    title,
    deezer_id,
    link,
    preview_url=None,
    duration=0,
    provider_rank=0,
    track_position=0,
    disk_number=1,
    explicit_lyrics=False,
):
    clean_title = " ".join((title or "").split())
    if not clean_title or not deezer_id:
        return False
    try:
        with connection() as conn:
            conn.execute(
                """
                INSERT INTO tracks (
                    release_id, title, deezer_id, link, preview_url, duration,
                    provider_rank, track_position, disk_number, explicit_lyrics, date_added
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    release_id,
                    clean_title,
                    str(deezer_id),
                    link or f"https://www.deezer.com/track/{deezer_id}",
                    preview_url,
                    max(0, int(duration or 0)),
                    max(0, int(provider_rank or 0)),
                    max(0, int(track_position or 0)),
                    max(1, int(disk_number or 1)),
                    1 if explicit_lyrics else 0,
                    _now(),
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def set_track_feedback(track_id, feedback):
    if feedback not in {"love", "not_for_me", "already_heard"}:
        raise ValueError("Invalid track feedback")
    with connection() as conn:
        exists = conn.execute("SELECT 1 FROM tracks WHERE id = ?", (track_id,)).fetchone()
        if not exists:
            return False
        conn.execute(
            """
            INSERT INTO track_feedback (track_id, feedback, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(track_id) DO UPDATE SET
                feedback = excluded.feedback,
                updated_at = excluded.updated_at
            """,
            (track_id, feedback, _now()),
        )
        return True


def mark_tracks_seen(track_ids):
    clean_ids = sorted({int(track_id) for track_id in track_ids if str(track_id).isdigit()})
    if not clean_ids:
        return 0
    now = _now()
    with connection() as conn:
        placeholders = ",".join("?" for _ in clean_ids)
        valid_ids = [
            row["id"]
            for row in conn.execute(
                f"SELECT id FROM tracks WHERE id IN ({placeholders})", clean_ids
            ).fetchall()
        ]
        conn.executemany(
            """
            INSERT INTO radar_impressions (track_id, shown_at, show_count)
            VALUES (?, ?, 1)
            ON CONFLICT(track_id) DO UPDATE SET
                shown_at = excluded.shown_at,
                show_count = radar_impressions.show_count + 1
            """,
            [(track_id, now) for track_id in valid_ids],
        )
        return len(valid_ids)


_VERSION_WORDS = (
    "acoustic|anniversary|clean|deluxe|demo|edit|explicit|instrumental|live|mix|mono|"
    "radio|regional|remaster(?:ed)?|sped up|slowed|stereo|version"
)


def canonical_track_title(title):
    value = " ".join((title or "").lower().split())
    value = re.sub(rf"\s*[\[(][^\])]*\b(?:{_VERSION_WORDS})\b[^\])]*[\])]\s*$", "", value)
    value = re.sub(rf"\s*[-–—]\s*(?:\d{{4}}\s+)?(?:{_VERSION_WORDS})\b.*$", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _radar_candidates(days):
    lower, upper = _date_bounds(days, future_days=0)
    with connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    t.*, r.title AS release_title, r.type AS release_type,
                    r.release_date, r.cover_url, r.status AS release_status,
                    r.link AS release_link, a.id AS artist_id, a.name AS artist_name,
                    a.favorite, a.library_track_count, a.library_album_count,
                    tf.feedback,
                    CASE WHEN ri.track_id IS NULL THEN 0 ELSE 1 END AS was_seen,
                    (
                        SELECT COUNT(*) FROM releases downloaded
                        WHERE downloaded.artist_id = a.id AND downloaded.status = 'downloaded'
                    ) AS downloaded_count,
                    (
                        SELECT COUNT(*) FROM track_feedback loved
                        JOIN tracks loved_track ON loved_track.id = loved.track_id
                        JOIN releases loved_release ON loved_release.id = loved_track.release_id
                        WHERE loved_release.artist_id = a.id AND loved.feedback = 'love'
                    ) AS loved_count
                FROM tracks t
                JOIN releases r ON r.id = t.release_id
                JOIN artists a ON a.id = r.artist_id
                LEFT JOIN track_feedback tf ON tf.track_id = t.id
                LEFT JOIN radar_impressions ri ON ri.track_id = t.id
                WHERE r.release_date BETWEEN ? AND ?
                  AND r.status = 'pending'
                  AND a.match_status = 'confirmed'
                ORDER BY r.release_date DESC, t.provider_rank DESC, t.id ASC
                """,
                (lower, upper),
            ).fetchall()
        ]


def _score_candidate(candidate):
    released = date.fromisoformat(candidate["release_date"])
    age_days = max(0, (date.today() - released).days)
    components = {
        "favorite": 60 if candidate["favorite"] else 0,
        "library_affinity": min(
            20,
            round(math.log2(max(0, candidate["library_track_count"]) + 1) * 4, 2),
        ),
        "download_history": min(12, candidate["downloaded_count"] * 4),
        "loved_artist": min(18, candidate["loved_count"] * 6),
        "recency": max(0, round(18 - (age_days * 0.6), 2)),
        "format": 9 if candidate["release_type"] == "single" else 5 if candidate["release_type"] == "ep" else 2,
        "provider_popularity": candidate["provider_rank"],
    }
    reasons = []
    if candidate["favorite"]:
        reasons.append("Favorite artist")
    if age_days <= 7:
        reasons.append("New this week")
    if candidate["library_track_count"] and len(reasons) < 2:
        count = candidate["library_track_count"]
        reasons.append(f"{count} {'track' if count == 1 else 'tracks'} in your library")
    if candidate["downloaded_count"] and len(reasons) < 2:
        reasons.append("You downloaded this artist before")
    if candidate["release_type"] == "single" and len(reasons) < 2:
        reasons.append("New single")
    if not reasons:
        reasons.append("Recent release from an artist you follow")
    personal_score = sum(
        value for name, value in components.items() if name != "provider_popularity"
    )
    return round(personal_score, 2), components, reasons[:2]


def get_radar(limit=12, days=90):
    limit = max(1, min(int(limit), 15))
    candidates = _radar_candidates(days)
    eligible = [
        candidate
        for candidate in candidates
        if not candidate["was_seen"] and candidate["feedback"] is None
    ]
    scored = []
    for candidate in eligible:
        score, components, reasons = _score_candidate(candidate)
        candidate.update(score=score, score_components=components, reasons=reasons)
        scored.append(candidate)
    scored.sort(
        key=lambda item: (
            -item["score"],
            -date.fromisoformat(item["release_date"]).toordinal(),
            -item["provider_rank"],
            item["id"],
        )
    )

    selected = []
    artist_counts = {}
    title_keys = set()
    for candidate in scored:
        title_key = (candidate["artist_id"], canonical_track_title(candidate["title"]))
        if title_key in title_keys or artist_counts.get(candidate["artist_id"], 0) >= 2:
            continue
        title_keys.add(title_key)
        artist_counts[candidate["artist_id"]] = artist_counts.get(candidate["artist_id"], 0) + 1
        selected.append(candidate)
        if len(selected) >= limit:
            break

    with connection() as conn:
        conn.executemany(
            """
            INSERT INTO recommendation_scores (track_id, score, components, reasons, calculated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(track_id) DO UPDATE SET
                score = excluded.score,
                components = excluded.components,
                reasons = excluded.reasons,
                calculated_at = excluded.calculated_at
            """,
            [
                (
                    candidate["id"],
                    candidate["score"],
                    json.dumps(candidate["score_components"], sort_keys=True),
                    json.dumps(candidate["reasons"]),
                    _now(),
                )
                for candidate in scored
            ],
        )

    picks = []
    for candidate in selected:
        picks.append(
            {
                key: candidate[key]
                for key in (
                    "id", "title", "artist_id", "artist_name", "release_title",
                    "release_type", "release_date", "cover_url", "link", "preview_url",
                    "duration", "explicit_lyrics", "score", "score_components", "reasons",
                )
            }
        )

    deeper_by_release = {}
    for candidate in scored:
        if candidate["release_type"] not in {"album", "ep"}:
            continue
        existing = deeper_by_release.get(candidate["release_id"])
        if not existing or candidate["score"] > existing["score"]:
            deeper_by_release[candidate["release_id"]] = candidate
    deeper_listens = []
    deeper_artists = set()
    for candidate in sorted(deeper_by_release.values(), key=lambda item: -item["score"]):
        if candidate["artist_id"] in deeper_artists:
            continue
        deeper_artists.add(candidate["artist_id"])
        deeper_listens.append(
            {
                "release_id": candidate["release_id"],
                "title": candidate["release_title"],
                "artist_name": candidate["artist_name"],
                "release_type": candidate["release_type"],
                "release_date": candidate["release_date"],
                "cover_url": candidate["cover_url"],
                "link": candidate["release_link"],
                "reason": candidate["reasons"][0],
            }
        )
        if len(deeper_listens) == 2:
            break

    return {
        "picks": picks,
        "deeper_listens": deeper_listens,
        "selected_count": len(picks),
        "track_count": len(candidates),
        "artist_count": len({candidate["artist_id"] for candidate in candidates}),
        "suppressed_count": len(candidates) - len(eligible),
        "days": days,
    }


def _escape_like(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _date_bounds(days=90, future_days=365):
    today = date.today()
    return (
        (today - timedelta(days=max(0, days))).isoformat(),
        (today + timedelta(days=max(0, future_days))).isoformat(),
    )


def get_releases(status=None, release_type=None, search=None, days=90, page=1, per_page=30):
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 100))
    lower, upper = _date_bounds(days)
    where = [
        "r.release_date BETWEEN ? AND ?",
        """
        r.id = (
            SELECT MIN(r2.id) FROM releases r2
            WHERE r2.artist_id = r.artist_id
              AND lower(trim(r2.title)) = lower(trim(r.title))
              AND r2.release_date = r.release_date
              AND r2.status = r.status
        )
        """,
    ]
    params = [lower, upper]

    if status and status != "all":
        where.append("r.status = ?")
        params.append(status)
    if release_type and release_type != "all":
        if release_type == "single":
            where.append("r.type IN ('single', 'ep')")
        else:
            where.append("r.type = ?")
            params.append(release_type)
    if search:
        term = f"%{_escape_like(search)}%"
        where.append("(r.title LIKE ? ESCAPE '\\' OR a.name LIKE ? ESCAPE '\\')")
        params.extend([term, term])

    base = " FROM releases r JOIN artists a ON a.id = r.artist_id WHERE " + " AND ".join(where)
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*)" + base, params).fetchone()[0]
        rows = conn.execute(
            """
            SELECT r.*, a.name AS artist_name, a.picture_url AS artist_picture_url
            """ + base + " ORDER BY r.release_date DESC, r.date_added DESC LIMIT ? OFFSET ?",
            [*params, per_page, (page - 1) * per_page],
        ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


def get_stats(days=90):
    lower, upper = _date_bounds(days)
    with connection() as conn:
        artist = conn.execute(
            """
            SELECT COUNT(*) total,
                   SUM(CASE WHEN match_status = 'confirmed' THEN 1 ELSE 0 END) confirmed,
                   SUM(CASE WHEN match_status != 'confirmed' THEN 1 ELSE 0 END) unresolved
            FROM artists
            """
        ).fetchone()
        release = conn.execute(
            """
            WITH grouped AS (
                SELECT artist_id, lower(trim(title)) title_key, release_date, status
                FROM releases
                WHERE release_date BETWEEN ? AND ?
                GROUP BY artist_id, title_key, release_date, status
            )
            SELECT COUNT(*) visible,
                   SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) pending,
                   SUM(CASE WHEN status = 'downloaded' THEN 1 ELSE 0 END) downloaded,
                   SUM(CASE WHEN release_date > date('now') THEN 1 ELSE 0 END) upcoming
            FROM grouped
            """,
            (lower, upper),
        ).fetchone()
    return {
        "artists": artist["total"] or 0,
        "confirmed_artists": artist["confirmed"] or 0,
        "unresolved_artists": artist["unresolved"] or 0,
        "visible_releases": release["visible"] or 0,
        "pending": release["pending"] or 0,
        "downloaded": release["downloaded"] or 0,
        "upcoming": release["upcoming"] or 0,
        "days": days,
    }


def update_release_status(release_id, status):
    with connection() as conn:
        cursor = conn.execute("UPDATE releases SET status = ? WHERE id = ?", (status, release_id))
        return cursor.rowcount > 0


def mark_artist_checked(artist_id):
    with connection() as conn:
        conn.execute("UPDATE artists SET last_checked_at = ? WHERE id = ?", (_now(), artist_id))


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
