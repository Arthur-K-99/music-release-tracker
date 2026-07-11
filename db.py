import os
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
        conn.execute(
            "UPDATE artists SET match_status = 'confirmed' "
            "WHERE deezer_id IS NOT NULL AND match_status = 'unresolved'"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_releases_date ON releases(release_date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_releases_status_date ON releases(status, release_date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_releases_artist ON releases(artist_id)")


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


def remove_artist(artist_id):
    with connection() as conn:
        cursor = conn.execute("DELETE FROM artists WHERE id = ?", (artist_id,))
        return cursor.rowcount > 0


def add_release(artist_id, title, type, release_date, deezer_id, link, cover_url, status="pending"):
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
            return False
        try:
            conn.execute(
                """
                INSERT INTO releases
                    (artist_id, title, type, release_date, deezer_id, link, cover_url, status, date_added)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (artist_id, title, type, release_date, deezer_id, link, cover_url, status, _now()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


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
