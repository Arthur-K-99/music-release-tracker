import os
import tempfile
import unittest
from collections import Counter
from datetime import date, timedelta

import db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.old_path
        self.temp_dir.cleanup()

    def test_artist_upsert_is_case_insensitive_and_can_confirm(self):
        created = db.upsert_artist("Example Artist")
        existing = db.upsert_artist(
            "example artist",
            deezer_id="123",
            picture_url="https://example.com/a.jpg",
            confirmed=True,
        )
        artists = db.get_artists()

        self.assertTrue(created["created"])
        self.assertFalse(existing["created"])
        self.assertEqual(created["id"], existing["id"])
        self.assertEqual(artists[0]["match_status"], "confirmed")
        self.assertEqual(artists[0]["deezer_id"], "123")

    def test_release_deduplicates_logical_editions(self):
        artist_id = db.upsert_artist("Example", deezer_id="1", confirmed=True)["id"]
        release_date = date.today().isoformat()
        first = db.add_release(artist_id, "Same Album", "album", release_date, "10", "https://d/10", None)
        duplicate = db.add_release(artist_id, " same album ", "album", release_date, "11", "https://d/11", None)

        self.assertTrue(first)
        self.assertFalse(duplicate)
        self.assertEqual(db.get_releases(days=90)["total"], 1)

    def test_recent_window_and_status_stats(self):
        artist_id = db.upsert_artist("Example", deezer_id="1", confirmed=True)["id"]
        recent = (date.today() - timedelta(days=5)).isoformat()
        old = (date.today() - timedelta(days=180)).isoformat()
        db.add_release(artist_id, "Recent", "single", recent, "20", "https://d/20", None)
        db.add_release(artist_id, "Old", "album", old, "21", "https://d/21", None)

        self.assertEqual(db.get_releases(days=30)["total"], 1)
        self.assertEqual(db.get_releases(days=365)["total"], 2)
        self.assertEqual(db.get_stats(days=30)["pending"], 1)

    def _add_track(self, artist_id, suffix, title=None, release_type="single", rank=0):
        release = db.upsert_release(
            artist_id,
            f"Release {suffix}",
            release_type,
            date.today().isoformat(),
            f"release-{suffix}",
            f"https://www.deezer.com/album/{suffix}",
            f"https://example.com/{suffix}.jpg",
        )
        added = db.add_track(
            release["id"],
            title or f"Track {suffix}",
            f"track-{suffix}",
            f"https://www.deezer.com/track/{suffix}",
            provider_rank=rank,
        )
        self.assertTrue(added)
        with db.connection() as conn:
            return conn.execute(
                "SELECT id FROM tracks WHERE deezer_id = ?", (f"track-{suffix}",)
            ).fetchone()["id"]

    def test_track_storage_deduplicates_provider_identity(self):
        artist_id = db.upsert_artist("Example", deezer_id="1", confirmed=True)["id"]
        track_id = self._add_track(artist_id, "one")
        with db.connection() as conn:
            release_id = conn.execute("SELECT release_id FROM tracks WHERE id = ?", (track_id,)).fetchone()[0]
        self.assertFalse(
            db.add_track(release_id, "Another title", "track-one", "https://www.deezer.com/track/one")
        )

    def test_radar_favorites_win_and_artist_diversity_is_limited(self):
        favorite_id = db.upsert_artist("Favorite", deezer_id="1", confirmed=True)["id"]
        familiar_id = db.upsert_artist("Familiar", deezer_id="2", confirmed=True)["id"]
        db.set_artist_favorite(favorite_id, True)
        db.update_artist_library_counts(familiar_id, track_count=500, album_count=20)

        self._add_track(favorite_id, "fav-1")
        self._add_track(favorite_id, "fav-2")
        self._add_track(favorite_id, "fav-3")
        self._add_track(familiar_id, "known-1", rank=1000000)

        radar = db.get_radar(limit=12, days=30)
        counts = Counter(pick["artist_name"] for pick in radar["picks"])
        self.assertEqual(radar["picks"][0]["artist_name"], "Favorite")
        self.assertEqual(counts["Favorite"], 2)
        self.assertEqual(counts["Familiar"], 1)
        self.assertEqual(radar["track_count"], 4)
        self.assertIn("Favorite artist", radar["picks"][0]["reasons"])
        with db.connection() as conn:
            stored = conn.execute("SELECT components, reasons FROM recommendation_scores").fetchall()
        self.assertEqual(len(stored), 4)

    def test_radar_collapses_versions_and_suppresses_feedback_and_seen_tracks(self):
        artist_id = db.upsert_artist("Example", deezer_id="1", confirmed=True)["id"]
        first_id = self._add_track(artist_id, "original", title="Signal")
        self._add_track(artist_id, "deluxe", title="Signal (Deluxe Version)")
        other_id = self._add_track(artist_id, "other", title="Other Song")

        radar = db.get_radar(limit=12, days=30)
        titles = [pick["title"] for pick in radar["picks"]]
        self.assertEqual(len([title for title in titles if title.startswith("Signal")]), 1)

        self.assertTrue(db.set_track_feedback(first_id, "not_for_me"))
        self.assertTrue(db.mark_tracks_seen([other_id]))
        refreshed = db.get_radar(limit=12, days=30)
        refreshed_ids = {pick["id"] for pick in refreshed["picks"]}
        self.assertNotIn(first_id, refreshed_ids)
        self.assertNotIn(other_id, refreshed_ids)
        self.assertGreaterEqual(refreshed["suppressed_count"], 2)

    def test_provider_popularity_cannot_overrule_personal_affinity(self):
        familiar_id = db.upsert_artist("Familiar", deezer_id="1", confirmed=True)["id"]
        generic_id = db.upsert_artist("Generic", deezer_id="2", confirmed=True)["id"]
        db.update_artist_library_counts(familiar_id, track_count=1)
        self._add_track(familiar_id, "familiar", rank=0)
        self._add_track(generic_id, "generic", rank=1000000)

        radar = db.get_radar(limit=2, days=30)
        self.assertEqual(radar["picks"][0]["artist_name"], "Familiar")


if __name__ == "__main__":
    unittest.main()
