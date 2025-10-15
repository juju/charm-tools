from unittest import mock
from unittest import TestCase
from charmtools import version


class TestVersion(TestCase):

    @mock.patch("charmtools.version.USE_IMPORTLIB", True)
    @mock.patch("charmtools.version.files", create=True)
    def test_cached_charm_tools_version_by_version_file_and_importlib(self, files):
        version_file = files.return_value.joinpath.return_value
        version_file.is_file.return_value = True
        version_file.read_bytes.return_value = b'{"version": "1.2.3", "git": "abc123", "gitn": "5"}'
        result = version.cached_charm_tools_version()
        self.assertIsInstance(result, dict)
        self.assertEqual('1.2.3', result['version'])
        self.assertEqual('abc123', result['git'])
        self.assertEqual('5', result['gitn'])
