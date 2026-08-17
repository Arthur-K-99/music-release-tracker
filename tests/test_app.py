import os
import tempfile
import unittest
from datetime import date, timedelta

import app as app_module
import db


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.temp_dir.name, "api.db")
        db.init_db()
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()

    def tearDown(self):
        db.DB_PATH = self.old_path
        self.temp_dir.cleanup()

    def test_artist_requires_selected_deezer_identity(self):
        response = self.client.post("/api/artists", json={"name": "Ambiguous"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/api/artists",
            json={"name": "Confirmed", "deezer_id": "123", "picture_url": "https://example.com/a.jpg"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["created"])

    def test_release_filters_are_validated(self):
        self.assertEqual(self.client.get("/api/releases?status=nope").status_code, 400)
        self.assertEqual(self.client.get("/api/releases?per_page=500").status_code, 400)
        self.assertEqual(self.client.get("/api/releases?days=abc").status_code, 400)

    def test_status_update_returns_not_found(self):
        response = self.client.post("/api/releases/999/status", json={"status": "downloaded"})
        self.assertEqual(response.status_code, 404)

    def test_release_window_rejects_implausible_dates(self):
        self.assertTrue(app_module._release_in_window(date.today().isoformat()))
        self.assertFalse(app_module._release_in_window("2099-12-31"))
        too_old = (date.today() - timedelta(days=app_module.LOOKBACK_DAYS + 1)).isoformat()
        self.assertFalse(app_module._release_in_window(too_old))

    def _add_radar_track(self):
        artist_id = db.upsert_artist("Radar Artist", deezer_id="123", confirmed=True)["id"]
        release = db.upsert_release(
            artist_id,
            "Radar Single",
            "single",
            date.today().isoformat(),
            "radar-release",
            "https://www.deezer.com/album/10",
            None,
        )
        db.add_track(
            release["id"],
            "Radar Song",
            "radar-track",
            "https://www.deezer.com/track/20",
        )
        with db.connection() as conn:
            track_id = conn.execute("SELECT id FROM tracks WHERE deezer_id = 'radar-track'").fetchone()[0]
        return artist_id, track_id

    def test_favorite_endpoint_validates_and_updates_artist(self):
        artist_id, _ = self._add_radar_track()
        self.assertEqual(
            self.client.post(f"/api/artists/{artist_id}/favorite", json={"favorite": "yes"}).status_code,
            400,
        )
        response = self.client.post(
            f"/api/artists/{artist_id}/favorite", json={"favorite": True}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.get_artists()[0]["favorite"], 1)

    def test_radar_feedback_and_seen_endpoints(self):
        _, track_id = self._add_radar_track()
        response = self.client.get("/api/radar?mode=quick&days=30")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["selected_count"], 1)
        self.assertEqual(self.client.get("/api/radar?mode=everything").status_code, 400)

        self.assertEqual(
            self.client.post(f"/api/tracks/{track_id}/feedback", json={"feedback": "skip"}).status_code,
            400,
        )
        feedback = self.client.post(
            f"/api/tracks/{track_id}/feedback", json={"feedback": "already_heard"}
        )
        self.assertEqual(feedback.status_code, 200)
        self.assertEqual(self.client.get("/api/radar?mode=radar&days=30").get_json()["selected_count"], 0)

        seen = self.client.post("/api/radar/seen", json={"track_ids": [track_id, 999999]})
        self.assertEqual(seen.status_code, 200)
        self.assertEqual(seen.get_json()["marked"], 1)


if __name__ == "__main__":
    unittest.main()
