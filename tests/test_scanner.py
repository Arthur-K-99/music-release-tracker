import unittest

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


if __name__ == "__main__":
    unittest.main()
