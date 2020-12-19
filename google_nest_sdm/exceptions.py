"""Library for exceptions using the Google Nest SDM API and subscriber."""


class GoogleNestException(Exception):
    """Base class for all client exceptions."""


class SubscriberException(GoogleNestException):
    """Raised during problems subscribing to events and updates."""


class ApiException(GoogleNestException):
    """Raised during problems talking to the API."""


class AuthException(GoogleNestException):
    """Raised due to auth problems talking to API or subscriber."""


class ConfigurationException(GoogleNestException):
    """Raised due to misconfiguration problems."""
