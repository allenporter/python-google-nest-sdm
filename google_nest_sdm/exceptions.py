"""Library for exceptions using the Google Nest SDM API and subscriber."""


class GoogleNestException(Exception):
    """Base class for all client exceptions."""


class SubscriberException(GoogleNestException):
    """Raised during problems subscribing to events and updates."""


class ApiException(GoogleNestException):
    """Raised during problems talking to the API."""


class AuthException(ApiException):
    """Raised due to auth problems talking to API or subscriber."""


class NotFoundException(ApiException):
    """Raised when the API returns an error that a resource was not found."""


class ApiForbiddenException(ApiException):
    """Raised when the user is not authorized to perform a specific function."""


class ConfigurationException(GoogleNestException):
    """Raised due to misconfiguration problems."""


class DecodeException(GoogleNestException):
    """Raised when failing to decode a token."""


class TranscodeException(GoogleNestException):
    """Raised when failing to transcode media."""
