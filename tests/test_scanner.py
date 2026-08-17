import unittest
import os
import tempfile
from unittest import mock

import scanner


class ScannerTests(unittest.TestCase):
    def test_clean_artist_name_removes_feature_credit(self):
        self.assertEqual(scanner.clean_artist_name("  Artist A feat. Artist B  "), "Artist A")
        self.assertEqual(scanner.clean_artist_name("Artist A ft Artist B"), "Artist A")

    def test_filename_fallback_uses_final_segment(self):
        self.assertEqual(
            scanner.extract_artist_from_filename("Song - Live Mix - Artist Name.flac"),
            "Artist Name",
        )

    def test_filename_without_separator_is_ignored(self):
        self.assertEqual(scanner.extract_artist_from_filename("Unknown Song.mp3"), "")

    def test_scan_summary_retains_track_and_album_frequency(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [os.path.join(directory, name) for name in ("one.mp3", "two.mp3", "three.mp3")]
            for path in paths:
                open(path, "ab").close()

            metadata = [
                {"artist": ["Favorite"], "album": ["First"]},
                {"artist": ["Favorite"], "album": ["First"]},
                {"artist": ["Favorite"], "album": ["Second"]},
            ]
            with mock.patch("scanner.mutagen.File", side_effect=metadata):
                summary = scanner.scan_directory_summary(directory)

        self.assertEqual(summary["artists"], ["Favorite"])
        self.assertEqual(summary["track_counts"]["Favorite"], 3)
        self.assertEqual(summary["album_counts"]["Favorite"], 2)


if __name__ == "__main__":
    unittest.main()
