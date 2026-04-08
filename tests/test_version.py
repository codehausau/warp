import os
import unittest
from unittest import mock

from warp.version import VERSION, get_runtime_version, get_version


class VersionTests(unittest.TestCase):

    def test_runtime_version_defaults_to_base_version(self):
        with mock.patch('warp.version._get_exact_git_tag', return_value=''), \
             mock.patch('warp.version._get_git_build_metadata', return_value=''), \
             mock.patch('warp.version.os.environ.get', return_value=''):
            self.assertEqual(get_runtime_version(), VERSION)

    def test_runtime_version_uses_clean_version_for_matching_tag(self):
        with mock.patch('warp.version._get_exact_git_tag', return_value=f'v{VERSION}'), \
             mock.patch('warp.version._get_git_build_metadata', return_value='252.g75e2575'), \
             mock.patch('warp.version.os.environ.get', return_value=''):
            self.assertEqual(get_runtime_version(), VERSION)

    def test_runtime_version_appends_git_build_metadata(self):
        with mock.patch('warp.version._get_exact_git_tag', return_value=''), \
             mock.patch('warp.version._get_git_build_metadata', return_value='252.g75e2575'), \
             mock.patch('warp.version.os.environ.get', return_value=''):
            self.assertEqual(get_runtime_version(), f"{VERSION}+252.g75e2575")

    def test_runtime_version_appends_git_and_env_build_metadata(self):
        with mock.patch('warp.version._get_exact_git_tag', return_value=''), \
             mock.patch('warp.version._get_git_build_metadata', return_value='252.g75e2575'), \
             mock.patch('warp.version.os.environ.get', return_value='feature-branch'):
            self.assertEqual(
                get_version(),
                f"{VERSION}+252.g75e2575.feature.branch"
            )


if __name__ == '__main__':
    unittest.main()
