# SoundRadar — TODO

Tracked improvements, bugs, and feature ideas.

---

## 🐛 Bugs / Correctness

- [ ] **Fix broken artist card images**
  Artist cards construct image URLs using the Deezer numeric ID (`https://e-cdns-images.dzcdn.net/images/artist/{deezer_id}/...`), but that path requires the image hash, not the artist ID. Either store `picture_medium` from the Deezer search response in the DB and use that, or always fall back to the default avatar.
  — `static/app.js:469`

- [ ] **Handle Deezer album pagination**
  The release check worker fetches `/artist/{id}/albums` but only processes the first page (default 25 results). Artists with more than 25 releases will have older albums silently dropped. Follow the `next` cursor in the API response to fetch all pages.
  — `app.py:82–106`

- [ ] **Use server-side status filtering from the frontend**
  `fetchReleases()` in `app.js` always calls `/api/releases` without a `?status=` param, loading every release into memory and filtering client-side. The backend already supports `status_filter` — wire the frontend filter dropdown to use it so the payload stays small as the DB grows.
  — `static/app.js:184`, `db.py:110`

---

## 🔒 Robustness

- [ ] **Make library scan async**
  `POST /api/scan` runs the full directory walk synchronously. A large music library (tens of thousands of files) can take long enough to time out the HTTP request. Consider moving it to a background thread with progress polling, similar to the release check worker.
  — `app.py:141`

- [ ] **Improve thread safety on `check_status`**
  The global `check_status` dict is read by the status endpoint and written by the worker thread without synchronization on individual keys. Use a proper `threading.Lock` for reads (or a dataclass with a lock) to avoid fragile reliance on CPython's GIL.
  — `app.py:16`

- [ ] **Context-manage DB connections**
  Every function in `db.py` manually calls `conn.close()`. If an exception fires between `get_db_connection()` and `conn.close()`, the connection leaks. Use `with get_db_connection() as conn:` or a `try/finally` pattern throughout.
  — `db.py`

---

## ✨ Features / UX

- [ ] **Batch actions (select all / bulk status change)**
  After scanning a large library there can be dozens of pending releases. Add "mark all as downloaded", "dismiss all", or per-artist bulk actions to reduce clicking.

- [ ] **Release date range filter**
  The sidebar has status and type filters but no date range. Old releases from years ago clutter the feed alongside genuinely new drops. Add a "last 7 / 30 / 90 days" selector or a date picker.

- [ ] **Remove hardcoded personal paths**
  The README and default scan path reference `/Users/athanasios/Music/Downloaded`. Use `~/Music/Downloaded` or a config file / environment variable so the project is portable if shared.

- [ ] **Add a favicon**
  The browser tab shows the generic icon. Export the existing radar SVG as a small PNG or use an inline SVG favicon in `index.html`.
