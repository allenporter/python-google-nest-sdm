from .context import google_nest_sdm

import pytest
import aiohttp
from pytest_aiohttp import aiohttp_server

from google_nest_sdm.device import AbstractAuth
from google_nest_sdm import google_nest_api


class FakeAuth(AbstractAuth):
  def __init__(self, websession):
    super().__init__(websession, "")

  async def async_get_access_token(self) -> str:
    return "some-token"

class Recorder:
  request = None


def NewDeviceHandler(r: Recorder, devices: dict):
  async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
    assert request.headers['Authorization'] == 'Bearer some-token'
    s = await request.text()
    print(s)
    r.request = await request.json() if s else {}
    return aiohttp.web.json_response({'devices': devices})
  return handler


def NewRequestRecorder(r: Recorder, response: dict):
  async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
    assert request.headers['Authorization'] == 'Bearer some-token'
    s = await request.text()
    print("handler ", s)
    r.request = await request.json() if s else {}
    return aiohttp.web.json_response(response)
  return handler


async def test_get_devices(aiohttp_server) -> None:
  r = Recorder()
  handler = NewDeviceHandler(r, [
      {
        'name': 'enterprises/project-id/devices/device-id1',
        'type': 'sdm.devices.types.device-type1',
        'traits': { },
        'parentRelations': [ ],
      }, {
        'name': 'enterprises/project-id/devices/device-id2',
        'type': 'sdm.devices.types.device-type2',
        'traits': { },
        'parentRelations': [ ],
      }])

  app = aiohttp.web.Application()
  app.router.add_get('/devices', handler)
  server = await aiohttp_server(app)

  async with aiohttp.test_utils.TestClient(server) as client:
    api = google_nest_api.GoogleNestAPI(FakeAuth(client))
    devices = await api.async_get_devices()
    assert len(devices) == 2
    assert 'enterprises/project-id/devices/device-id1' == devices[0].name
    assert 'sdm.devices.types.device-type1' == devices[0].type
    assert 'enterprises/project-id/devices/device-id2' == devices[1].name
    assert 'sdm.devices.types.device-type2' == devices[1].type


async def test_thermostat_eco_set_mode(aiohttp_server) -> None:
  r = Recorder()
  handler = NewDeviceHandler(r, [{
      'name': 'enterprises/project-id/devices/device-id1',
      'traits': {
          'sdm.devices.traits.ThermostatEco' : {
              'availableModes' : ['MANUAL_ECO', 'OFF'],
              'mode' : 'MANUAL_ECO',
              'heatCelsius' : 20.0,
              'coolCelsius' : 22.0
          },
      },
    }])
  post_handler = NewRequestRecorder(r, {})

  app = aiohttp.web.Application()
  app.router.add_get('/devices', handler)
  app.router.add_post('/devices/device-id1:executeCommand', post_handler)
  server = await aiohttp_server(app)

  async with aiohttp.test_utils.TestClient(server) as client:
    api = google_nest_api.GoogleNestAPI(FakeAuth(client))
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert 'enterprises/project-id/devices/device-id1' == device.name
    trait = device.traits['sdm.devices.traits.ThermostatEco']
    assert trait.mode == 'MANUAL_ECO'
    await trait.set_mode('OFF')
    expected_request = {
        'command': 'sdm.devices.commands.ThermostatEco.SetMode',
        'params': {'mode': 'OFF'}
    }
    assert expected_request == r.request


async def test_thermostat_mode_set_mode(aiohttp_server) -> None:
  r = Recorder()
  handler = NewDeviceHandler(r, [{
      'name': 'enterprises/project-id/devices/device-id1',
      'traits': {
          'sdm.devices.traits.ThermostatMode' : {
              'availableModes' : ['HEAT', 'COOL', 'HEATCOOL', 'OFF'],
              'mode' : 'COOL',
          },
      },
    }])
  post_handler = NewRequestRecorder(r, {})

  app = aiohttp.web.Application()
  app.router.add_get('/devices', handler)
  app.router.add_post('/devices/device-id1:executeCommand', post_handler)
  server = await aiohttp_server(app)

  async with aiohttp.test_utils.TestClient(server) as client:
    api = google_nest_api.GoogleNestAPI(FakeAuth(client))
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert 'enterprises/project-id/devices/device-id1' == device.name
    trait = device.traits['sdm.devices.traits.ThermostatMode']
    assert trait.mode == 'COOL'
    await trait.set_mode('HEAT')
    expected_request = {
        'command': 'sdm.devices.commands.ThermostatMode.SetMode',
        'params': {'mode': 'HEAT'}
    }
    assert expected_request == r.request


async def test_thermostat_temperature_set_point(aiohttp_server) -> None:
  r = Recorder()
  handler = NewDeviceHandler(r, [{
      'name': 'enterprises/project-id/devices/device-id1',
      'traits': {
          'sdm.devices.traits.ThermostatTemperatureSetpoint' : {
              'heatCelsius': 23.0,
              'coolCelsius': 24.0,
          },
      },
    }])
  post_handler = NewRequestRecorder(r, {})

  app = aiohttp.web.Application()
  app.router.add_get('/devices', handler)
  app.router.add_post('/devices/device-id1:executeCommand', post_handler)
  server = await aiohttp_server(app)

  async with aiohttp.test_utils.TestClient(server) as client:
    api = google_nest_api.GoogleNestAPI(FakeAuth(client))
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert 'enterprises/project-id/devices/device-id1' == device.name
    trait = device.traits['sdm.devices.traits.ThermostatTemperatureSetpoint']
    assert trait.heat_celsius == 23.0
    assert trait.cool_celsius == 24.0
    await trait.set_heat(25.0)
    expected_request = {
        'command': 'sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat',
        'params': {'heatCelsius': 25.0 }
    }
    assert expected_request == r.request

    await trait.set_cool(26.0)
    expected_request = {
        'command': 'sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool',
        'params': {'coolCelsius': 26.0 }
    }
    assert expected_request == r.request

    await trait.set_range(27.0, 28.0)
    expected_request = {
        'command': 'sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange',
        'params': {
            'heatCelsius': 27.0,
            'coolCelsius': 28.0,
        }
    }
    assert expected_request == r.request
