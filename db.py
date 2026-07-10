import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tracker.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enable foreign keys support
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Create artists table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS artists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        deezer_id TEXT,
        date_added TEXT NOT NULL
    )
    ''')
    
    # Create releases table
    cursor.execute('''
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
    ''')
    
    conn.commit()
    conn.close()

def add_artist(name, deezer_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    artist_id = None
    try:
        cursor.execute(
            "INSERT INTO artists (name, deezer_id, date_added) VALUES (?, ?, ?)",
            (name, deezer_id, now)
        )
        conn.commit()
        artist_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # Artist already exists
        cursor.execute("SELECT id, deezer_id FROM artists WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            artist_id = row['id']
            # Update Deezer ID if it was missing but is provided now
            if deezer_id and not row['deezer_id']:
                cursor.execute("UPDATE artists SET deezer_id = ? WHERE id = ?", (deezer_id, artist_id))
                conn.commit()
    conn.close()
    return artist_id

def get_artists():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM artists ORDER BY name ASC")
    rows = cursor.fetchall()
    artists = [dict(row) for row in rows]
    conn.close()
    return artists

def remove_artist(artist_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("DELETE FROM artists WHERE id = ?", (artist_id,))
    conn.commit()
    conn.close()

def add_release(artist_id, title, type, release_date, deezer_id, link, cover_url, status='pending'):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    success = False
    try:
        cursor.execute(
            """INSERT INTO releases 
               (artist_id, title, type, release_date, deezer_id, link, cover_url, status, date_added) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (artist_id, title, type, release_date, deezer_id, link, cover_url, status, now)
        )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False # Already exists (duplicate deezer_id)
    conn.close()
    return success

def get_releases(status_filter=None, limit=200):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT r.*, a.name as artist_name 
        FROM releases r
        JOIN artists a ON r.artist_id = a.id
    """
    params = []
    if status_filter:
        query += " WHERE r.status = ?"
        params.append(status_filter)
        
    query += " ORDER BY r.release_date DESC, r.date_added DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    releases = [dict(row) for row in rows]
    conn.close()
    return releases

def update_release_status(release_id, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE releases SET status = ? WHERE id = ?", (status, release_id))
    conn.commit()
    conn.close()

def update_artist_deezer_id(artist_id, deezer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE artists SET deezer_id = ? WHERE id = ?", (deezer_id, artist_id))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
