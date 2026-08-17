import os
import re
from collections import Counter, defaultdict

import mutagen

SUPPORTED_EXTENSIONS = ('.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.opus', '.wav')

def clean_artist_name(name):
    if not name:
        return ""
    # Strip whitespace
    name = name.strip()
    # Remove common featuring patterns at the end if any (e.g. "Artist A feat. Artist B" -> "Artist A")
    # Splitting on feat/ft helps simplify artist searches on Deezer
    name = re.split(r'\s+(?:feat\.?|ft\.?)\s+', name, flags=re.IGNORECASE)[0]
    # Remove trailing/leading quotes or brackets
    name = name.strip('\'"()[]{}')
    return name.strip()

def extract_artist_from_filename(filename):
    # Strip extension
    base = os.path.splitext(filename)[0]
    # Check for "Song Title - Artist"
    if ' - ' in base:
        parts = base.split(' - ')
        # The user says: "Song Title - Artist"
        # So the last part is the Artist
        artist = parts[-1].strip()
        return clean_artist_name(artist)
    return ""

def scan_directory_summary(directory_path, progress_callback=None):
    track_counts = Counter()
    album_names = defaultdict(set)
    if not os.path.isdir(directory_path):
        return {"artists": [], "track_counts": {}, "album_counts": {}, "files_processed": 0}

    processed = 0
    for root, _, files in os.walk(directory_path):
        for file in files:
            if not file.lower().endswith(SUPPORTED_EXTENSIONS):
                continue

            processed += 1
            filepath = os.path.join(root, file)
            tag_artist = ""
            tag_album = ""
            try:
                # Load with easy=True for a unified dictionary interface
                audio = mutagen.File(filepath, easy=True)
                if audio and 'artist' in audio and audio['artist']:
                    tag_artist = audio['artist'][0]
                if audio and 'album' in audio and audio['album']:
                    tag_album = audio['album'][0].strip()
            except Exception:
                pass
                
            artist = clean_artist_name(tag_artist)
            if not artist:
                # Fallback to filename parsing
                artist = extract_artist_from_filename(file)
                
            if artist and artist.lower() not in ('unknown', 'various artists', 'various', 'va'):
                track_counts[artist] += 1
                if tag_album:
                    album_names[artist].add(tag_album.casefold())

            if progress_callback and (processed == 1 or processed % 50 == 0):
                progress_callback(processed, len(track_counts), filepath)

    if progress_callback:
        progress_callback(processed, len(track_counts), "")
    artists = sorted(track_counts, key=str.casefold)
    return {
        "artists": artists,
        "track_counts": dict(track_counts),
        "album_counts": {artist: len(album_names[artist]) for artist in artists},
        "files_processed": processed,
    }


def scan_directory(directory_path, progress_callback=None):
    return scan_directory_summary(directory_path, progress_callback)["artists"]

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Music/Downloaded")
    print(f"Scanning: {path}")
    results = scan_directory(path)
    print(f"Found {len(results)} artists:")
    for a in results:
        print(f"- {a}")
