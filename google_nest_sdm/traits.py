from .auth import AbstractAuth

import datetime

from abc import abstractproperty, ABCMeta
from typing import Callable, TypeVar

DEVICE_NAME = 'name'
DEVICE_TYPE = 'type'
DEVICE_TRAITS = 'traits'
DEVICE_PARENT_RELATIONS = 'parentRelations'
STATUS = 'status'
CUSTOM_NAME = 'customName'
AMBIENT_HUMIDITY_PERCENT = 'ambientHumidityPercent'
AMBIENT_TEMPERATURE_CELSIUS = 'ambientTemperatureCelsius'
AVAILABLE_MODES = 'availableModes'
MODE = 'mode'
HEAT_CELSIUS = 'heatCelsius'
COOL_CELSIUS = 'coolCelsius'
MAX_IMAGE_RESOLUTION = 'maxImageResolution'
MAX_VIDEO_RESOLUTION = 'maxVideoResolution'
WIDTH = 'width'
HEIGHT = 'height'
VIDEO_CODECS = 'videoCodecs'
AUDIO_CODECS = 'audioCodecs'
STREAM_URLS = 'streamUrls'
RESULTS = 'results'
RTSP_URL = 'rtspUrl'
STREAM_EXTENSION_TOKEN = 'streamExtensionToken'
STREAM_TOKEN = 'streamToken'
URL = 'url'
TOKEN = 'token'
EXPIRES_AT = 'expiresAt'
PARENT = 'parent'
DISPLAYNAME = 'displayName'

CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)  # pylint: disable=invalid-name

class Registry(dict):
    """Registry of items."""

    def register(self) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Return decorator to register item with a specific name."""

        def decorator(func: CALLABLE_T) -> CALLABLE_T:
            """Register decorated function."""
            self[func.NAME] = func
            return func

        return decorator

TRAIT_MAP = Registry()

class Command:
  """Base class for executing commands."""

  def __init__(self, device_id: str, auth: AbstractAuth):
    self._device_id = device_id
    self._auth = auth

  async def execute(self, data):
    return await self._auth.request(
        "post", f"{self._device_id}:executeCommand", json=data)


def _TraitsDict(traits: dict, trait_map: dict, cmd: Command):
  d = {}
  for (trait, trait_data) in traits.items():
    if not trait in trait_map:
      continue
    cls = trait_map[trait]
    d[trait] = cls(trait_data, cmd)
  return d


def BuildTraits(raw_data: dict, cmd: Command) -> dict:
    """Builds a trait map out of a response dict."""
    traits = raw_data.get(DEVICE_TRAITS, {})
    return _TraitsDict(traits, TRAIT_MAP, cmd)

