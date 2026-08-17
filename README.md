# SoundRadar

SoundRadar is a local-first release desk for music collectors. It scans an existing audio library for artist names, lets you confirm those artists against Deezer, and keeps a focused queue of recent and upcoming releases.

The guiding rule is simple: **new music, less catalog noise**. SoundRadar does not silently match ambiguous names and does not import an artist's entire history into the default queue.

## What v2 changes

- **Trusted artist matching:** library scans add unresolved names; only artists explicitly selected from Deezer are checked for releases.
- **Recent release window:** checks keep releases from the last 90 days through the next year by default. Implausible dates such as 2099 are ignored.
- **Paginated release API:** status, type, date, and text filters run in SQLite, with true database totals.
- **Safe background jobs:** release checks and library scans expose progress without blocking requests.
- **Persistent migration:** existing `tracker.db` files are upgraded additively; releases and statuses are preserved.
- **Accessible release desk:** compact cards, semantic labels, keyboard-friendly controls, reduced-motion support, and no external font/icon dependencies.
- **Your Radar:** a finite song-level shortlist ranked from favorites, local-library affinity, download history, freshness, and lightweight feedback.

## Your Radar

Your Radar turns the recent release window into 5 quick picks or a fuller shortlist of up to 12 songs. Every pick includes a concise reason, such as **Favorite artist**, **New this week**, or the number of that artist's tracks in your local library. No recommendation follows an artist or changes the release queue.

Mark followed artists as favorites from the **Artists** view, then use **Love it**, **Not for me**, and **Already heard** on song picks. Shown or rated tracks are kept out of later sessions, duplicate versions are collapsed, and no artist can take more than two spots. A release check fetches track lists for recent releases, including recent releases saved before this feature was added.

## Quick start

Requirements: Python 3.10+ and an internet connection for Deezer lookups.

```bash
git clone https://github.com/Arthur-K-99/music-release-tracker.git
cd music-release-tracker
chmod +x run.sh
./run.sh
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001).

The launcher creates `.venv`, installs dependencies when `requirements.txt` changes, initializes the SQLite schema, and starts the local Flask server.

## Workflow

1. Open **Library settings**, choose your music directory, and scan it.
2. Open **Artists**. Unresolved names are clearly marked.
3. Use **Find match** or the top search box and choose the correct Deezer artist.
4. Click **Check releases**.
5. Open **Your Radar** for the short list, or **Everything new** for the complete release desk.
6. Copy release info/links, mark downloads complete, or dismiss unwanted releases.

Existing catalog entries remain accessible by choosing **All history** in the Window filter.

## Upgrading from the original version

No manual database migration is required. On startup, SoundRadar adds the v2 artist metadata columns and indexes while preserving existing artists, releases, and statuses.

- Artists that already have a Deezer ID become **confirmed**.
- Scanned artists without a Deezer ID become **unresolved** and are skipped during checks until you choose a match.
- Historical releases remain in SQLite; the default queue shows only the configured recent window.
- Existing same-artist, same-title, same-date editions are collapsed in the interface without deleting stored records.

Backing up `tracker.db` before any major application upgrade is still recommended.

## Configuration

Copy `.env.example` to `.env` to customize local settings:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `SOUNDRADAR_LIBRARY_PATH` | `~/Music/Downloaded` | Default library scan path |
| `SOUNDRADAR_LOOKBACK_DAYS` | `90` | Past release window |
| `SOUNDRADAR_FUTURE_DAYS` | `365` | Maximum upcoming release window |
| `SOUNDRADAR_PORT` | `5001` | Local server port |
| `SOUNDRADAR_DB_PATH` | `./tracker.db` | SQLite database location |
| `SOUNDRADAR_DEBUG` | `0` | Set to `1` for Flask debug mode |

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The suite uses temporary databases and does not modify `tracker.db`.

## Local API

The browser interface uses a small JSON API:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/stats` | Accurate artist and release totals for a date window |
| `GET /api/releases` | Paginated status, type, date, and text filtering |
| `POST /api/releases/check` | Start a confirmed-artist release check |
| `GET /api/releases/check/status` | Read release-check progress and errors |
| `POST /api/scan` | Start an asynchronous local-library scan |
| `GET /api/scan/status` | Read scan progress |
| `GET /api/artists` | List followed artists and resolution state |
| `POST /api/artists` | Confirm a selected Deezer artist |
| `POST /api/artists/:id/favorite` | Add or remove a followed artist from Favorites |
| `GET /api/radar` | Return a quick (5) or full (up to 12) explainable song shortlist |
| `POST /api/radar/seen` | Persist songs shown during the current session |
| `POST /api/tracks/:id/feedback` | Record Love it, Not for me, or Already heard feedback |

Mutation endpoints validate statuses and return `404` when the target record does not exist. Release pages are capped at 100 records per request.

## Project structure

```text
app.py                 Flask API and background jobs
db.py                  SQLite schema, migrations, queries, and stats
scanner.py             Audio tag and filename artist extraction
templates/index.html   Release desk structure
static/app.js           Client state and safe DOM rendering
static/style.css        Responsive visual system
tests/                  Scanner, database, and API regression tests
.env.example            Optional local configuration template
CHANGELOG.md            User-facing release history
run.sh                  Local launcher
```

## Data and privacy

SoundRadar binds to `127.0.0.1`. Library filenames and paths stay local; artist and release queries are sent to Deezer when you search or run a release check. `tracker.db`, `.env`, and the virtual environment are ignored by Git.
