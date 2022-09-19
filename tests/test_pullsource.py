import os
import re
from types import SimpleNamespace
import unittest
import unittest.mock as mock
from tempfile import NamedTemporaryFile, TemporaryDirectory

from charmtools import pullsource


class TestPullSource(unittest.TestCase):
    @mock.patch('builtins.print')
    def test__download_item_cs_prefix(self, mock_print):
        """Don't support downloads from any cs: prefix."""
        args = SimpleNamespace(item="cs:fake-charm")
        assert pullsource.download_item(args) == 1
        mock_print.assert_called_once_with("Cannot download source for charm cs:fake-charm")

    @mock.patch('builtins.print')
    def test__download_fake_layer_prefix(self, mock_print):
        """Confirm supports downloads from layers: prefix."""
        with TemporaryDirectory() as tmpdir:
            args = SimpleNamespace(item="layer:fake-layer", dir=tmpdir)
            assert pullsource.download_item(args) == 1
        mock_print.assert_called_once_with("Can't find source for layer:fake-layer (No fetcher for url: layer:fake-layer)")
        
    @mock.patch('builtins.print')
    @mock.patch.object(pullsource, 'fetchers')
    def test__download_layer_basic(self, mock_fetchers, mock_print):
        """Confirm supports downloads from layers: prefix."""
        fetcher = mock_fetchers.get_fetcher.return_value
        fetcher.revision = "abcdefghijklmnop"
        with TemporaryDirectory() as tmpdir:
            mkdir = fetcher.fetch.return_value = os.path.join(tmpdir, "source")
            os.mkdir(mkdir)
            with NamedTemporaryFile(dir=fetcher.fetch.return_value):
                args = SimpleNamespace(item="layer:fake-layer", dir=tmpdir)
                assert pullsource.download_item(args) is None
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        rev_match = re.search(r"rev: ([a-z0-9]+)", args[0])
        assert rev_match, f"'{args[0]}', didn't contain a match for rev: ([a-z0-9]+)"
        assert rev_match.groups()[0] == fetcher.revision
        
