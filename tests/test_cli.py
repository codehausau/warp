import unittest

from click.testing import CliRunner

from warp.cli import cli
from warp.version import get_runtime_version


class CliTests(unittest.TestCase):

    def test_version_option_reports_warp_version_without_app_config(self):
        result = CliRunner().invoke(cli, ["--version"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn(f"warp, version {get_runtime_version()}", result.output)


if __name__ == "__main__":
    unittest.main()
