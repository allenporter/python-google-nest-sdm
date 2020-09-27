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

async def test_request(aiohttp_server) -> None:
  async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
    assert request.headers['Authorization'] == 'Bearer some-token'
    return aiohttp.web.json_response({
        'devices': [
            {
              'name': 'enterprises/project-id/devices/device-id1',
              'type': 'sdm.devices.types.device-type1',
              'traits': { },
              'parentRelations': [ ],
            },
            {
              'name': 'enterprises/project-id/devices/device-id2',
              'type': 'sdm.devices.types.device-type2',
              'traits': { },
              'parentRelations': [ ],
            },
        ]})

  app = aiohttp.web.Application()
  app.router.add_get('/devices', handler)
  server = await aiohttp_server(app)

  async with aiohttp.test_utils.TestClient(server) as client:
    auth = FakeAuth(client)
    api = google_nest_api.GoogleNestAPI(auth)
    devices = await api.async_get_devices()
    assert len(devices) == 2
    assert 'enterprises/project-id/devices/device-id1' == devices[0].name
    assert 'sdm.devices.types.device-type1' == devices[0].type
    assert 'enterprises/project-id/devices/device-id2' == devices[1].name
    assert 'sdm.devices.types.device-type2' == devices[1].type
