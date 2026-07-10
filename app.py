import os
import urllib.parse
import threading
import time
from flask import Flask, jsonify, request, render_template, send_from_directory
import requests
import db
import scanner

app = Flask(__name__, template_folder='templates', static_folder='static')

# Ensure database is initialized
db.init_db()

# Global background release check status
check_status = {
    "active": False,
    "current_artist": "",
    "processed": 0,
    "total": 0,
    "new_releases": 0,
    "errors": []
}

check_lock = threading.Lock()

def check_releases_worker():
    global check_status
    with check_lock:
        check_status["active"] = True
        check_status["processed"] = 0
        check_status["new_releases"] = 0
        check_status["errors"] = []
        check_status["current_artist"] = "Initializing check..."
        
        artists = db.get_artists()
        check_status["total"] = len(artists)
        
        for artist in artists:
            # Check if execution was cancelled early
            if not check_status["active"]:
                break
                
            artist_id = artist['id']
            artist_name = artist['name']
            check_status["current_artist"] = artist_name
            
            deezer_id = artist['deezer_id']
            
            # 1. Resolve Deezer ID if missing
            if not deezer_id:
                try:
                    # Throttle requests to respect Deezer API limit
                    time.sleep(0.15)
                    search_url = f"https://api.deezer.com/search/artist?q={urllib.parse.quote(artist_name)}"
                    r = requests.get(search_url, timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get('data'):
                            matched = data['data'][0]
                            for item in data['data']:
                                if item['name'].lower() == artist_name.lower():
                                    matched = item
                                    break
                            deezer_id = str(matched['id'])
                            db.update_artist_deezer_id(artist_id, deezer_id)
                except Exception as e:
                    check_status["errors"].append(f"Search failed for {artist_name}: {str(e)}")
                    # Move to next artist
                    check_status["processed"] += 1
                    continue
                    
            if not deezer_id:
                check_status["errors"].append(f"No Deezer ID found for: {artist_name}")
                check_status["processed"] += 1
                continue
                
            # 2. Fetch Albums for resolved Deezer ID
            try:
                # Throttle requests to respect Deezer API limit
                time.sleep(0.15)
                albums_url = f"https://api.deezer.com/artist/{deezer_id}/albums"
                r = requests.get(albums_url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    releases = data.get('data', [])
                    for item in releases:
                        rel_id = str(item['id'])
                        title = item['title']
                        link = item['link']
                        cover_url = item.get('cover_medium') or item.get('cover')
                        release_date = item.get('release_date', '1970-01-01')
                        record_type = item.get('record_type', 'album')
                        
                        success = db.add_release(
                            artist_id=artist_id,
                            title=title,
                            type=record_type,
                            release_date=release_date,
                            deezer_id=rel_id,
                            link=link,
                            cover_url=cover_url,
                            status='pending'
                        )
                        if success:
                            check_status["new_releases"] += 1
            except Exception as e:
                check_status["errors"].append(f"Album fetch failed for {artist_name}: {str(e)}")
                
            check_status["processed"] += 1
            
        check_status["active"] = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/artists', methods=['GET'])
def get_artists():
    artists = db.get_artists()
    return jsonify(artists)

@app.route('/api/artists', methods=['POST'])
def add_artist():
    data = request.json or {}
    name = data.get('name')
    deezer_id = data.get('deezer_id')
    
    if not name:
        return jsonify({"error": "Artist name is required"}), 400
        
    artist_id = db.add_artist(name, deezer_id)
    return jsonify({"success": True, "artist_id": artist_id})

@app.route('/api/artists/<int:artist_id>', methods=['DELETE'])
def remove_artist(artist_id):
    db.remove_artist(artist_id)
    return jsonify({"success": True})

@app.route('/api/scan', methods=['POST'])
def scan_library():
    data = request.json or {}
    path = data.get('path', '/Users/athanasios/Music/Downloaded')
    
    if not os.path.exists(path):
        return jsonify({"error": f"Directory not found: {path}"}), 400
        
    found_artists = scanner.scan_directory(path)
    added_count = 0
    for name in found_artists:
        artist_id = db.add_artist(name)
        if artist_id:
            added_count += 1
            
    return jsonify({
        "success": True,
        "scanned_path": path,
        "found_artists": found_artists,
        "added_count": added_count
    })

@app.route('/api/releases', methods=['GET'])
def get_releases():
    status = request.args.get('status')
    limit = request.args.get('limit', 200, type=int)
    releases = db.get_releases(status_filter=status, limit=limit)
    return jsonify(releases)

@app.route('/api/releases/<int:release_id>/status', methods=['POST'])
def update_release_status(release_id):
    data = request.json or {}
    status = data.get('status')
    if status not in ('pending', 'downloaded', 'dismissed'):
        return jsonify({"error": "Invalid status."}), 400
        
    db.update_release_status(release_id, status)
    return jsonify({"success": True})

@app.route('/api/releases/check', methods=['POST'])
def trigger_releases_check():
    global check_status
    if check_status["active"]:
        return jsonify({"status": "already_running"}), 409
        
    # Start checking task in a background thread
    threading.Thread(target=check_releases_worker, daemon=True).start()
    return jsonify({"status": "started"})

@app.route('/api/releases/check/status', methods=['GET'])
def get_check_status():
    global check_status
    return jsonify(check_status)

@app.route('/api/releases/check/cancel', methods=['POST'])
def cancel_releases_check():
    global check_status
    if check_status["active"]:
        check_status["active"] = False
        return jsonify({"status": "cancelling"})
    return jsonify({"status": "idle"})

@app.route('/api/deezer/search/artist', methods=['GET'])
def search_deezer_artist():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
        
    try:
        search_url = f"https://api.deezer.com/search/artist?q={urllib.parse.quote(query)}"
        r = requests.get(search_url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return jsonify(data.get('data', []))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    return jsonify([])

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)
