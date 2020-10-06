from .auth import AbstractAuth

import datetime

from abc import abstractproperty, ABCMeta

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


class Command:
  """Base class for executing commands."""

  def __init__(self, device_id: str, auth: AbstractAuth):
    self._device_id = device_id
    self._auth = auth

  async def execute(self, data):
    return await self._auth.request(
        "post", f"{self._device_id}:executeCommand", json=data)


class ConnectivityTrait:
  """This trait belongs to any device that has connectivity information."""

  NAME = 'sdm.devices.traits.Connectivity'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def status(self) -> str:
    """Device connectivity status.

    Return:
      "OFFLINE", "ONLINE"
    """
    return self._data[STATUS]


class InfoTrait:
  """This trait belongs to any device for device-related information."""

  NAME = 'sdm.devices.traits.Info'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def custom_name(self) -> str:
    """Custom name of the device."""
    return self._data[CUSTOM_NAME]


class HumidityTrait:
  """This trait belongs to any device that has a sensor to measure humidity."""

  NAME = 'sdm.devices.traits.Humidity'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def ambient_humidity_percent(self) -> float:
    """Percent humidity, measured at the device."""
    return self._data[AMBIENT_HUMIDITY_PERCENT]


class TemperatureTrait:
  """This trait belongs to any device that has a sensor to measure temperature."""

  NAME = 'sdm.devices.traits.Temperature'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def ambient_temperature_celsius(self) -> float:
    """Percent humidity, measured at the device."""
    return self._data[AMBIENT_TEMPERATURE_CELSIUS]


class ThermostatEcoTrait:
  """This trait belongs to any device that has a sensor to measure temperature."""

  NAME = 'sdm.devices.traits.ThermostatEco'

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def available_modes(self) -> list:
    """List of supported Eco modes."""
    return self._data[AVAILABLE_MODES]

  @property
  def mode(self) -> str:
    """The current Eco mode of the thermostat."""
    return self._data[MODE]

  async def set_mode(self, mode):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatEco.SetMode",
        "params" : { "mode" : mode }
    }
    return await self._cmd.execute(data)


  @property
  def heat_celsius(self) -> float:
    """Lowest temperature where Eco mode begins heating."""
    return self._data[HEAT_CELSIUS]

  @property
  def cool_celsius(self) -> float:
    """Highest cooling temperature where Eco mode begins cooling."""
    return self._data[COOL_CELSIUS]


class ThermostatHvacTrait:
  """This trait belongs to devices that can report HVAC details."""

  NAME = 'sdm.devices.traits.ThermostatHvac'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def status(self) -> list:
    """Current HVAC status of the thermostat."""
    return self._data[STATUS]


class ThermostatModeTrait:
  """This trait belongs to devices that support different thermostat modes."""

  NAME = 'sdm.devices.traits.ThermostatMode'

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def available_modes(self) -> list:
    """List of supported thermostat modes."""
    return self._data[AVAILABLE_MODES]

  @property
  def mode(self) -> str:
    """The current mode of the thermostat."""
    return self._data[MODE]

  async def set_mode(self, mode):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatMode.SetMode",
        "params" : { "mode" : mode }
    }
    return await self._cmd.execute(data)


class ThermostatTemperatureSetpointTrait:
  """This trait belongs to devices that support setting target temperature."""

  NAME = 'sdm.devices.traits.ThermostatTemperatureSetpoint'

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def heat_celsius(self) -> float:
    """Lowest temperature where Eco mode begins heating."""
    return self._data[HEAT_CELSIUS]

  @property
  def cool_celsius(self) -> list:
    """Highest cooling temperature where Eco mode begins cooling."""
    return self._data[COOL_CELSIUS]

  async def set_heat(self, heat: float):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params" : { "heatCelsius" : heat }
    }
    return await self._cmd.execute(data)

  async def set_cool(self, cool: float):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
        "params" : { "coolCelsius" : cool }
    }
    return await self._cmd.execute(data)

  async def set_range(self, heat: float, cool: float):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
        "params" : {
            "heatCelsius" : heat,
            "coolCelsius" : cool,
        }
    }
    return await self._cmd.execute(data)


class Resolution:
  """Maximum Resolution of an image or stream."""
  width = None
  height = None


class CameraImageTrait:
  """This trait belongs to any device that supports taking images."""

  NAME = 'sdm.devices.traits.CameraImage'

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def max_image_resolution(self) -> Resolution:
    r = Resolution()
    r.width = self._data[MAX_IMAGE_RESOLUTION][WIDTH]
    r.height = self._data[MAX_IMAGE_RESOLUTION][HEIGHT]
    return r


class RtspStream:
  """Provides access an RTSP live stream URL."""

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def rtsp_stream_url(self) -> str:
    """RTSP live stream URL."""
    return self._data[STREAM_URLS][RTSP_URL]

  @property
  def stream_token(self) -> str:
    """Token to use to access an RTSP live stream."""
    return self._data[STREAM_TOKEN]

  @property
  def stream_extension_token(self) -> str:
    """Token to use to access an RTSP live stream."""
    return self._data[STREAM_EXTENSION_TOKEN]

  @property
  def expires_at(self) -> datetime:
    """Time at which both streamExtensionToken and streamToken expire."""
    t = self._data[EXPIRES_AT]
    return datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))

  async def extend_rtsp_stream(self):
    """Request a new RTSP live stream URL access token."""
    data = {
        "command" : "sdm.devices.commands.CameraLiveStream.ExtendRtspStream",
        "params" : {
            "streamExtensionToken": self.stream_extension_token
        }
    }
    resp = await self._cmd.execute(data)
    resp.raise_for_status()
    response_data = await resp.json()
    results = response_data[RESULTS]
    return RtspStream(results, self._cmd)

  async def stop_rtsp_stream(self):
    """Invalidates a valid RTSP access token and stops the RTSP live stream."""
    data = {
        "command" : "sdm.devices.commands.CameraLiveStream.StopRtspStream",
        "params" : {
            "streamExtensionToken": self.stream_extension_token
        }
    }
    resp = await self._cmd.execute(data)
    resp.raise_for_status()


class CameraLiveStreamTrait:
  """This trait belongs to any device that supports live streaming."""

  NAME = 'sdm.devices.traits.CameraLiveStream'

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def max_video_resolution(self) -> Resolution:
    """Maximum resolution of the video live stream."""
    r = Resolution()
    r.width = self._data[MAX_VIDEO_RESOLUTION][WIDTH]
    r.height = self._data[MAX_VIDEO_RESOLUTION][HEIGHT]
    return r

  @property
  def video_codecs(self) -> list:
    """Video codecs supported for the live stream."""
    return self._data[VIDEO_CODECS]

  @property
  def audio_codecs(self) -> list:
    """Audio codecs supported for the live stream."""
    return self._data[AUDIO_CODECS]

  async def generate_rtsp_stream(self) -> RtspStream:
    """Request a token to access an RTSP live stream URL."""
    data = {
        "command" : "sdm.devices.commands.CameraLiveStream.GenerateRtspStream",
        "params" : {}
    }
    resp = await self._cmd.execute(data)
    resp.raise_for_status()
    response_data = await resp.json()
    results = response_data[RESULTS]
    return RtspStream(results, self._cmd)


class EventImage:
  """Provides access an RTSP live stream URL.

  Use a ?width or ?height query parameters to customize the resolution
  of the downloaded image. Only one of these parameters need to specified.
  The other parameter is scaled automatically according to the camera's
  aspect ratio.

  The token should be added as an HTTP header:
  Authorization: Basic <token>
  """

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def url(self) -> str:
    """The URL to download the camera image from."""

    return self._data[URL]

  @property
  def token(self) -> str:
    """Token to use in the HTTP Authorization header when downloading."""
    return self._data[TOKEN]


class CameraEventImageTrait:
  """This trait belongs to any device that generates images from events."""

  NAME = 'sdm.devices.traits.CameraEventImage'

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  async def generate_image(self, eventId: str) -> EventImage:
    """Provides a URL to download a camera image from."""
    data = {
        "command" : "sdm.devices.commands.CameraEventImage.GenerateImage",
        "params" : {
            "eventId": eventId,
        }
    }
    resp = await self._cmd.execute(data)
    resp.raise_for_status()
    response_data = await resp.json()
    results = response_data[RESULTS]
    return EventImage(results, self._cmd)


_ALL_TRAITS = [
  ConnectivityTrait,
  InfoTrait,
  HumidityTrait,
  TemperatureTrait,
  ThermostatEcoTrait,
  ThermostatHvacTrait,
  ThermostatModeTrait,
  ThermostatTemperatureSetpointTrait,
  CameraImageTrait,
  CameraLiveStreamTrait,
  CameraEventImageTrait,
]
_ALL_TRAIT_MAP = { cls.NAME: cls for cls in _ALL_TRAITS }


def _TraitsDict(traits: dict, trait_map: dict, cmd: Command):
  d = {}
  for (trait, trait_data) in traits.items():
    if not trait in trait_map:
      continue
    cls = trait_map[trait]
    d[trait] = cls(trait_data, cmd)
  return d


class Device:
  """Class that represents a device object in the Google Nest SDM API."""

  def __init__(self, raw_data: dict, traits: dict):
    """Initialize a device."""
    self._raw_data = raw_data
    self._traits = traits

  @staticmethod
  def MakeDevice(raw_data: dict, auth: AbstractAuth):
    """Creates a device with the appropriate traits."""
    traits = raw_data.get(DEVICE_TRAITS, {})
    device_id = raw_data.get(DEVICE_NAME)
    cmd = Command(device_id, auth)
    traits_dict = _TraitsDict(traits, _ALL_TRAIT_MAP, cmd)
    return Device(raw_data, traits_dict)

  @property
  def name(self) -> str:
    """The resource name of the device such as 'enterprises/XYZ/devices/123'."""
    return self._raw_data[DEVICE_NAME] 

  @property
  def type(self) -> str:
    """Type of device for display purposes.

    The device type should not be used to deduce or infer functionality of
    the actual device it is assigned to. Instead, use the returned traits for
    the device.
    """
    return self._raw_data[DEVICE_TYPE]

  @property
  def traits(self) -> dict:
    """Return a trait mixin on None."""
    return self._traits

  def _traits_data(self, trait) -> dict:
    """Return the raw dictionary for the specified trait."""
    traits_dict = self._raw_data.get(DEVICE_TRAITS, {})
    return traits_dict.get(trait, {})

  @property
  def parent_relations(self) -> dict:
    """"Assignee details of the device (e.g. room/structure)."""
    relations = {}
    for d in self._raw_data.get(DEVICE_PARENT_RELATIONS, []):
      if not PARENT in d or not DISPLAYNAME in d:
        continue
      relations[d[PARENT]] = d[DISPLAYNAME]
    return relations
