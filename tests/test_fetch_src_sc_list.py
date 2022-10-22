from pathlib import Path

from corpus_cite import Justice


def test_setup():
    l = Justice.from_api(Path(__file__).parent.joinpath("test.yaml"))
    assert isinstance(l, Path)
    assert l.exists()
    l.unlink()  # remove the file after setup
