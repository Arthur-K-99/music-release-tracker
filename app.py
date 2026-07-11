import os
import threading
import time
import urllib.parse
from copy import deepcopy
from datetime import date, datetime, timedelta

import requests
from flask import Flask, jsonify, render_template, request

import db
import scanner


app = Flask(__name__, template_folder="templates", static_folder="static")
db.init_db()

LOOKBACK_DAYS = int(os.environ.get("SOUNDRADAR_LOOKBACK_DAYS", "90"))
FUTURE_DAYS = int(os.environ.get("SOUNDRADAR_FUTURE_DAYS", "365"))
DEFAULT_LIBRARY_PATH = os.path.expanduser(
    os.environ.get("SOUNDRADAR_LIBRARY_PATH", "~/Music/Downloaded")
)

VALID_STATUSES = {"pending", "downloaded", "dismissed"}
VALID_TYPES = {"all", "album", "single"}

job_lock = threading.Lock()
check_status = {
    "active": False,
    "cancel_requested": False,
    "current_artist": "",
    "processed": 0,
    "total": 0,
    "new_releases": 0,
    "skipped_unresolved": 0,
    "errors": [],
    "finished_at": None,
}
scan_status = {
    "active": False,
    "path": "",
    "files_processed": 0,
    "artists_found": 0,
    "artists_added": 0,
    "current_file": "",
    "error": None,
    "finished_at": None,
}


def _job_snapshot(status):
    with job_lock:
        return deepcopy(status)


def _job_update(status, **changes):
    with job_lock:
        status.update(changes)


def _append_check_error(message):
    with job_lock:
        if len(check_status["errors"]) < 100:
            check_status["errors"].append(message)


def _request_json(url, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            response = requests.get(
                url,
                timeout=12,
                headers={"User-Agent": "SoundRadar/2.0 (local release tracker)"},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise RuntimeError(payload["error"].get("message", "Deezer API error"))
            return payload
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(0.4 * (2**attempt))
    raise RuntimeError(str(last_error))


def _release_in_window(release_date):
    try:
        parsed = date.fromisoformat(release_date)
    except (TypeError, ValueError):
        return False
    today = date.today()
    return today - timedelta(days=LOOKBACK_DAYS) <= parsed <= today + timedelta(days=FUTURE_DAYS)


def _fetch_recent_releases(artist):
    url = f"https://api.deezer.com/artist/{artist['deezer_id']}/albums?limit=100"
    pages = 0
    while url and pages < 10:
        if _job_snapshot(check_status)["cancel_requested"]:
            return
        time.sleep(0.15)
        payload = _request_json(url)
        releases = payload.get("data", [])
        for item in releases:
            release_date = item.get("release_date")
            if not _release_in_window(release_date):
                continue
            added = db.add_release(
                artist_id=artist["id"],
                title=item.get("title") or "Untitled release",
                type=item.get("record_type") or "album",
                release_date=release_date,
                deezer_id=str(item["id"]),
                link=item.get("link") or f"https://www.deezer.com/album/{item['id']}",
                cover_url=item.get("cover_medium") or item.get("cover"),
                status="pending",
            )
            if added:
                with job_lock:
                    check_status["new_releases"] += 1
        pages += 1
        url = payload.get("next")


def check_releases_worker():
    try:
        artists = db.get_artists(limit=2000)
        confirmed = [a for a in artists if a["match_status"] == "confirmed" and a["deezer_id"]]
        _job_update(
            check_status,
            total=len(confirmed),
            skipped_unresolved=len(artists) - len(confirmed),
            current_artist="Preparing release desk…",
        )
        for index, artist in enumerate(confirmed, start=1):
            if _job_snapshot(check_status)["cancel_requested"]:
                break
            _job_update(check_status, current_artist=artist["name"])
            try:
                _fetch_recent_releases(artist)
                db.mark_artist_checked(artist["id"])
            except Exception as exc:
                _append_check_error(f"{artist['name']}: {exc}")
            _job_update(check_status, processed=index)
    except Exception as exc:
        _append_check_error(f"Release check stopped: {exc}")
    finally:
        _job_update(
            check_status,
            active=False,
            cancel_requested=False,
            current_artist="",
            finished_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )


def scan_library_worker(path):
    try:
        def progress(files_processed, artists_found, current_file):
            _job_update(
                scan_status,
                files_processed=files_processed,
                artists_found=artists_found,
                current_file=os.path.basename(current_file) if current_file else "",
            )

        found_artists = scanner.scan_directory(path, progress_callback=progress)
        added = 0
        for name in found_artists:
            if db.upsert_artist(name)["created"]:
                added += 1
        _job_update(scan_status, artists_found=len(found_artists), artists_added=added)
    except Exception as exc:
        _job_update(scan_status, error=str(exc))
    finally:
        _job_update(
            scan_status,
            active=False,
            current_file="",
            finished_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )


def _int_arg(name, default, minimum, maximum):
    raw = request.args.get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@app.get("/")
def index():
    return render_template(
        "index.html",
        default_library_path=DEFAULT_LIBRARY_PATH,
        default_lookback_days=LOOKBACK_DAYS,
    )


@app.get("/api/artists")
def get_artists():
    return jsonify(db.get_artists(search=request.args.get("search"), limit=2000))


@app.post("/api/artists")
def add_artist():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    deezer_id = data.get("deezer_id")
    if not name or not deezer_id:
        return jsonify({"error": "Choose an artist from the search results."}), 400
    result = db.upsert_artist(
        name,
        deezer_id=deezer_id,
        picture_url=data.get("picture_url"),
        confirmed=True,
    )
    return jsonify({"success": True, "artist_id": result["id"], "created": result["created"]})


@app.delete("/api/artists/<int:artist_id>")
def remove_artist(artist_id):
    if not db.remove_artist(artist_id):
        return jsonify({"error": "Artist not found."}), 404
    return jsonify({"success": True})


@app.post("/api/scan")
def trigger_scan():
    data = request.get_json(silent=True) or {}
    path = os.path.abspath(os.path.expanduser(data.get("path") or DEFAULT_LIBRARY_PATH))
    if not os.path.isdir(path):
        return jsonify({"error": f"Directory not found: {path}"}), 400
    with job_lock:
        if scan_status["active"]:
            return jsonify({"error": "A library scan is already running."}), 409
        scan_status.update(
            active=True,
            path=path,
            files_processed=0,
            artists_found=0,
            artists_added=0,
            current_file="",
            error=None,
            finished_at=None,
        )
    threading.Thread(target=scan_library_worker, args=(path,), daemon=True).start()
    return jsonify({"status": "started", "path": path}), 202


@app.get("/api/scan/status")
def get_scan_status():
    return jsonify(_job_snapshot(scan_status))


@app.get("/api/releases")
def get_releases():
    status = request.args.get("status", "pending")
    release_type = request.args.get("type", "all")
    if status not in VALID_STATUSES | {"all"}:
        return jsonify({"error": "Invalid status filter."}), 400
    if release_type not in VALID_TYPES:
        return jsonify({"error": "Invalid release type filter."}), 400
    try:
        days = _int_arg("days", LOOKBACK_DAYS, 1, 3650)
        page = _int_arg("page", 1, 1, 100000)
        per_page = _int_arg("per_page", 30, 1, 100)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        db.get_releases(
            status=status,
            release_type=release_type,
            search=request.args.get("search", "").strip(),
            days=days,
            page=page,
            per_page=per_page,
        )
    )


@app.get("/api/stats")
def get_stats():
    try:
        days = _int_arg("days", LOOKBACK_DAYS, 1, 3650)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(db.get_stats(days=days))


@app.post("/api/releases/<int:release_id>/status")
def update_release_status(release_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in VALID_STATUSES:
        return jsonify({"error": "Invalid status."}), 400
    if not db.update_release_status(release_id, status):
        return jsonify({"error": "Release not found."}), 404
    return jsonify({"success": True})


@app.post("/api/releases/check")
def trigger_releases_check():
    with job_lock:
        if check_status["active"]:
            return jsonify({"status": "already_running"}), 409
        check_status.update(
            active=True,
            cancel_requested=False,
            current_artist="Starting…",
            processed=0,
            total=0,
            new_releases=0,
            skipped_unresolved=0,
            errors=[],
            finished_at=None,
        )
    threading.Thread(target=check_releases_worker, daemon=True).start()
    return jsonify({"status": "started"}), 202


@app.get("/api/releases/check/status")
def get_check_status():
    return jsonify(_job_snapshot(check_status))


@app.post("/api/releases/check/cancel")
def cancel_releases_check():
    with job_lock:
        if not check_status["active"]:
            return jsonify({"status": "idle"})
        check_status["cancel_requested"] = True
    return jsonify({"status": "cancelling"})


@app.get("/api/deezer/search/artist")
def search_deezer_artist():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    try:
        encoded = urllib.parse.quote(query)
        payload = _request_json(f"https://api.deezer.com/search/artist?q={encoded}&limit=8")
        return jsonify(payload.get("data", [])[:8])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    debug = os.environ.get("SOUNDRADAR_DEBUG", "0") == "1"
    app.run(host="127.0.0.1", port=int(os.environ.get("SOUNDRADAR_PORT", "5001")), debug=debug)
