# SoundRadar 📡

SoundRadar is a self-hosted, lightweight web application designed to help you keep track of new and upcoming album and single releases from your favorite artists. It is specifically designed to complement offline downloading workflows (such as `spotiflac next`) by scanning your existing music library, resolving artist profiles, and fetching new releases.

![SoundRadar Cover](static/default-avatar.png)

## Key Features

*   **Local Library Scanning:** Walks your download directory (defaults to `/Users/athanasios/Music/Downloaded`), reads metadata tags (MP3, FLAC, M4A, etc.) using `mutagen`, and falls back to parsing filename structures like `Song Title - Artist` to build your artist list.
*   **Asynchronous Release Check:** Utilizes a non-blocking background thread worker to query the public Deezer API for new releases. This ensures the app is responsive even with hundreds of followed artists and prevents web timeouts.
*   **Rate-Limit Safety:** Implements polite request throttling (`0.15s` delay between API hits) to respect the Deezer API rate limits.
*   **Persistent Tracking Database:** Uses a local SQLite database (`tracker.db`) to record followed artists and fetched release states (`pending`, `downloaded`, `dismissed`) so you never miss an alert or see duplicates.
*   **Premium Glassmorphic Dashboard:** Designed with vibrant neon violet-pink styling, dynamic radar animation, smooth scale transitions, and instant client-side search and filters.
*   **Quick Copy Workflows:** Release cards feature quick-action buttons to copy track info (`Song Title - Artist`) or copy direct Deezer links to your clipboard, generating animated success toasts.
*   **Easy Setup:** Bootstraps itself via a single script that manages Python virtual environment setups and runs the application.

---

## File Structure

```
├── app.py                  # Flask server endpoints & background worker threads
├── db.py                   # SQLite schema initialization and database queries
├── scanner.py              # Recursive library audio tag/filename parser
├── requirements.txt        # Python package dependencies
├── run.sh                  # Shell script launcher (automates venv setup and execution)
├── .gitignore              # Protects privacy (excludes tracker.db, .venv, etc.)
├── README.md               # Application documentation
├── templates/
│   └── index.html          # Frontend SPA dashboard structure
└── static/
    ├── app.js              # Frontend state, API handling, and progress polling
    ├── style.css           # Premium glassmorphic styling & radar keyframe sweeps
    └── default-avatar.png  # Neon record vinyl placeholder asset
```

---

## Prerequisites

*   **OS:** macOS / Linux / Windows
*   **Python:** Python 3.10+ (tested on Python 3.14)
*   **Git:** Configured locally (used for publishing)

---

## Installation & Setup

1.  **Clone or Relocate Project:**
    Ensure the folder structure is set up in your projects directory:
    ```bash
    cd /Users/athanasios/Projects/music-release-tracker
    ```

2.  **Run the Launcher:**
    Execute the launcher script. It will automatically check for a local Python virtual environment, install dependencies (`flask`, `mutagen`, `requests`), initialize the SQLite database structure, and start the local Flask server:
    ```bash
    chmod +x run.sh
    ./run.sh
    ```

3.  **Open the Web Dashboard:**
    Open your favorite web browser and go to:
    👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## How to Use SoundRadar

1.  **Seed Your Artist Library:**
    *   **Auto-Scan:** Enter the path to your downloaded music (e.g. `/Users/athanasios/Music/Downloaded`) in the path input box in the header and click **Scan Local**. SoundRadar will analyze your files and follow every unique artist found.
    *   **Manual Search:** Type an artist's name in the header search bar. A dropdown list of suggestions will appear from Deezer. Click an artist to follow them.
2.  **Check for New Releases:**
    *   Click the **Check For Releases** button in the stats bar.
    *   A radar modal overlay will appear showing real-time progress as SoundRadar queries Deezer for your artists.
3.  **Process Your Release Feed:**
    *   **Copy Info / Link:** Click the copy icons to copy `Song - Artist` or the Deezer URL to your clipboard.
    *   **Download:** Paste the links/search queries into your `spotiflac next` GUI to queue downloads.
    *   **Manage State:** Click the checkmark to mark a release as **Downloaded** or the trash icon to **Dismiss** it. Use the sidebar tabs and selectors to filter the feed.
