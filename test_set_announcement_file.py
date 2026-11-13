import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from set_announcement_file import find_announcement_file, select_announcement_file


class AnnouncementRotationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name).resolve()
        (self.folder / "DUMMY~0.mp3").touch()

    def add_variants(self, variants):
        for variant in variants:
            (self.folder / f"42-{variant}~0.mp3").touch()

    def test_all_four_variants_cycle_and_wrap(self):
        self.add_variants([1, 2, 3, 4])
        count = 1
        selected = []
        for _ in range(5):
            path, count = select_announcement_file(self.folder, 42, count)
            selected.append(path.name)
        self.assertEqual(selected, [
            "42-1~0.mp3", "42-2~0.mp3", "42-3~0.mp3", "42-4~0.mp3", "42-1~0.mp3",
        ])

    def test_missing_year_variants_keep_alternating_original_variants(self):
        self.add_variants([1, 2])
        count = 3
        selected = []
        for _ in range(4):
            path, count = select_announcement_file(self.folder, 42, count)
            selected.append(path.name)
        self.assertEqual(selected, ["42-1~0.mp3", "42-2~0.mp3"] * 2)

    def test_skips_missing_variants_and_finds_nested_year_file(self):
        nested = self.folder / "nested"
        nested.mkdir()
        (nested / "42-4~0.mp3").touch()
        path, count = select_announcement_file(self.folder, 42, 2)
        self.assertEqual(path, nested / "42-4~0.mp3")
        self.assertEqual(count, 1)

    def test_no_variants_uses_dummy_without_advancing_rotation(self):
        path, count = select_announcement_file(self.folder, 42, 3)
        self.assertEqual(path.name, "DUMMY~0.mp3")
        self.assertEqual(count, 3)

    def test_database_error_fallback_does_not_select_normal_variants(self):
        (self.folder / "0-1~0.mp3").touch()
        path, _ = select_announcement_file(self.folder, 0, 0)
        self.assertEqual(path.name, "DUMMY~0.mp3")

    def test_missing_dummy_reports_failure(self):
        (self.folder / "DUMMY~0.mp3").unlink()
        with self.assertLogs(level="ERROR"):
            path, count = select_announcement_file(self.folder, 42, 1)
        self.assertIsNone(path)
        self.assertEqual(count, 1)

    def test_selected_file_is_linked_with_relative_target(self):
        self.add_variants([3])
        with patch("set_announcement_file.Path", return_value=self.folder):
            symlink, count = find_announcement_file(42, 3)
        self.assertEqual(symlink.resolve(), self.folder / "42-3~0.mp3")
        self.assertEqual(symlink.readlink(), Path("42-3~0.mp3"))
        self.assertEqual(count, 4)


if __name__ == "__main__":
    unittest.main()
