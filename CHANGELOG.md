# Changelog

Notable SoundRadar changes are documented here.

## Unreleased

### Added

- Your Radar song overview with five-pick quick glance and twelve-pick full views.
- Explainable recommendation scoring from Favorites, local-library frequency, download history, recency, and provider popularity tie-breaking.
- Track-level release storage, lightweight song feedback, seen-item suppression, duplicate-version collapse, and per-artist diversity limits.
- A small Deeper Listens section for the strongest recent albums and EPs.
- Editorial, responsive release-desk interface for desktop and mobile.
- Confirmed and unresolved artist states to prevent ambiguous automatic matching.
- Configurable recent and upcoming release windows.
- Paginated release and artist views with server-side release filtering.
- Accurate database-backed statistics and compact progress reporting.
- Asynchronous library scanning with progress status.
- Environment-based configuration through `.env`.
- Regression tests for scanner behavior, database queries, migrations, and API validation.

### Changed

- Release checks now fetch track listings for recent releases so Radar rankings never require historical-catalog imports.
- Release checks now inspect only confirmed artists and stop importing irrelevant catalog history.
- Deezer requests now use bounded pagination, timeouts, retry backoff, and explicit error handling.
- Existing logical duplicate editions are collapsed in the interface without deleting data.
- SQLite connections now use context management, foreign keys, busy timeouts, and WAL mode.
- The launcher installs dependencies only when `requirements.txt` changes.
- The large raster placeholder was replaced by a lightweight vector asset.

### Fixed

- Incorrect Deezer artist image URLs.
- Misleading release statistics calculated from only the first 200 client-side records.
- Race conditions when starting or cancelling background release checks.
- Synchronous scans that could block large-library requests.
- Unsafe insertion of remote or file-derived text through `innerHTML`.
- Hardcoded personal paths and the obsolete port 5000 documentation link.
