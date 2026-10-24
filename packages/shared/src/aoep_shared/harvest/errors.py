"""Exceptions shared by the harvest modules."""


class HarvestConfigError(RuntimeError):
    """Crawling is not configured safely (for example no contact in the User-Agent)."""


class FetchBlocked(PermissionError):
    """A fetch was refused on policy grounds (robots, denylist, login wall, paywall)."""
