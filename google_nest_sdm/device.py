from .auth import AbstractAuth

class Device:
  """Class that represents a device object in the Google Nest SDM API."""

  def __init__(self, raw_data: dict, auth: AbstractAuth):
    """Intiialize a device."""
    self._raw_data = raw_data
    self._auth = auth

  @property
  def name(self) -> str:
    """Return the full name and device identifier for the device."""
    return self._raw_data["name"] 

  @property
  def type(self) -> str:
    return self._raw_data["type"]
