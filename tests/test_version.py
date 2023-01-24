import toml

import corpus_base


def test_version():
    assert (
        toml.load("pyproject.toml")["tool"]["poetry"]["version"]
        == corpus_base.__version__
    )
