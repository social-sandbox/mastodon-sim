"""Test Mastodon Sim."""

import mastodon_sim


def test_import() -> None:
    """Test that the app can be imported."""
    assert isinstance(mastodon_sim.__name__, str)
