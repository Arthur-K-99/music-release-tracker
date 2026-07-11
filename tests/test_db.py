import os
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
