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


if __name__ == "__main__":
    unittest.main()
