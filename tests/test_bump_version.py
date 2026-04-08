import pathlib
import tempfile
import unittest

from scripts.bump_version import bump_version_file, bump_version_text


class BumpVersionTests(unittest.TestCase):

    def test_patch_bump_increments_patch(self):
        text, version = bump_version_text('VERSION = "2.0.0"\n', part="patch")
        self.assertEqual(version, "2.0.1")
        self.assertIn('VERSION = "2.0.1"', text)

    def test_minor_bump_resets_patch(self):
        text, version = bump_version_text('VERSION = "2.4.9"\n', part="minor")
        self.assertEqual(version, "2.5.0")
        self.assertIn('VERSION = "2.5.0"', text)

    def test_bump_version_file_updates_version_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "version.py"
            path.write_text('VERSION = "1.2.3"\n', encoding="utf8")

            new_version = bump_version_file(path=path, part="patch")

            self.assertEqual(new_version, "1.2.4")
            self.assertEqual(path.read_text(encoding="utf8"), 'VERSION = "1.2.4"\n')


if __name__ == "__main__":
    unittest.main()
