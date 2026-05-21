"""Health / freshness tools."""

from personal_finance import __version__


def get_data_freshness() -> dict:
    """Report when each connected account was last updated.

    Returns:
        Server version and a placeholder accounts list. Wired up to real data
        once the ingest pipeline lands.
    """
    return {
        "server_version": __version__,
        "accounts": [],
        "_stub": "Not implemented yet — no accounts connected.",
    }
